"""Offline tests for the database-backed Academic Source Registry."""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
from backend.academic_sources import (
    AcademicSource, seed_registry, list_sources, create_source, update_source,
    source_history, create_domain, import_sources_csv, export_sources_csv,
    resolve_sources, resolved_source_ids_by_channel,
)
from research_workbench.core import query_openalex, session_factory

HEADERS={"Authorization":"Bearer academic-registry-test-token"}


def payload(name="Test Journal"):
    return {
        "name":name,"abbreviation":"TJ","kind":"journal",
        "domains":["urban_planning"],"rank_label":"重点",
        "ranking_system":"团队自定义遴选","ranking_version":"2026",
        "ranking_source_url":"https://example.org/ranking",
        "source_url":"https://example.org/journal","aliases":["Test J."],
        "notes":"Offline test source","retrieval_channels":["direct"],
        "enabled":True,
    }


def test_seed_registry_is_idempotent_and_preserves_manual_edits(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"registry.db"))
    with factory() as db:
        first=seed_registry(db)
        assert first["domains_added"]==18
        assert first["sources_added"]==108
        assert len(list_sources(db))==108
        neurips=next(x for x in list_sources(db) if x["abbreviation"]=="NeurIPS")
        update_source(db,neurips["id"],{"rank_label":"团队优先观察"},"reviewer")
        second=seed_registry(db)
        assert second["domains_added"]==0 and second["sources_added"]==0
        saved= db.get(AcademicSource,neurips["id"])
        assert saved.rank_label=="团队优先观察"
        assert second["catalogue_version"]=="2026.11.1"


def test_source_crud_revision_and_identity_change_invalidates_openalex_id(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"crud.db"))
    with factory() as db:
        seed_registry(db)
        row=create_source(db,payload("Example Journal"),"admin-1")
        assert row["resolution_status"]=="unresolved"
        updated=update_source(db,row["id"],{"openalex_source_id":"S12345"},"admin-1")
        assert updated["resolution_status"]=="resolved"
        changed=update_source(db,row["id"],{"name":"Renamed Example Journal"},"admin-1")
        assert changed["openalex_source_id"]==""
        assert changed["resolution_status"]=="unresolved"
        history=source_history(db,row["id"])
        assert len(history)==3
        assert history[0]["action"]=="updated"
        assert history[0]["before"]["name"]=="Example Journal"
        with pytest.raises(ValueError):
            create_source(db,payload("Renamed Example Journal"))


def test_domains_are_extendable_and_cannot_be_deleted_while_in_use(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"domains.db"))
    with factory() as db:
        seed_registry(db)
        domain=create_domain(db,{"slug":"digital_twin","name":"数字孪生与仿真",
            "group_name":"计算机前沿","description":"仿真与数字孪生",
            "default_channels":["method"]})
        assert domain["slug"]=="digital_twin"
        row=create_source(db,{**payload("Digital Twin Journal"),
            "domains":["digital_twin"],"retrieval_channels":["method"]})
        from backend.academic_sources import delete_domain
        with pytest.raises(ValueError):
            delete_domain(db,"digital_twin")
        update_source(db,row["id"],{"domains":["urban_planning"]})
        assert delete_domain(db,"digital_twin")["deleted"]=="digital_twin"


def test_csv_import_export_upserts_by_normalized_name(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"csv.db"))
    csv_text=("name,abbreviation,kind,domains,rank_label,ranking_system,ranking_version,ranking_source_url,"
              "source_url,aliases,notes,retrieval_channels,enabled\n"
              "Example Review,ER,journal,urban_planning,核心,Team selection,2026,https://example.org/rank,"
              "https://example.org,Example R.|ER review,Urban studies,direct,true\n")
    with factory() as db:
        seed_registry(db)
        first=import_sources_csv(db,csv_text)
        assert first["created"]==1 and not first["errors"]
        second=import_sources_csv(db,csv_text.replace("核心","重点"))
        assert second["updated"]==1 and second["created"]==0
        exported=export_sources_csv(db)
        assert "Example Review" in exported and "retrieval_channels" in exported
        assert "https://example.org/rank" in exported


def test_openalex_resolution_requires_exact_match_and_routes_by_channel(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"resolve.db"))
    with factory() as db:
        seed_registry(db)
        row=create_source(db,{**payload("Exact Test Journal"),
            "abbreviation":"ETJ","aliases":["Exact Test J."],
            "retrieval_channels":["direct","method"]})
        def responder(request):
            return httpx.Response(200,json={"results":[{
                "id":"https://openalex.org/S998877","display_name":"Exact Test Journal",
                "abbreviated_title":"ETJ","alternate_titles":["Exact Test J."],"type":"journal"
            }]})
        with httpx.Client(transport=httpx.MockTransport(responder)) as client:
            result=resolve_sources(db,[row["id"]],client=client)
        assert result["resolved"]==1
        channels=resolved_source_ids_by_channel(db)
        assert "S998877" in channels["direct"]
        assert "S998877" in channels["method"]


def test_query_openalex_applies_strict_source_filter():
    seen={}
    def responder(request):
        seen["filter"]=request.url.params.get("filter","")
        seen["sort"]=request.url.params.get("sort","")
        return httpx.Response(200,json={"results":[]})
    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        assert query_openalex("urban graph","2026-01-01",5,client,source_ids=["S123","https://openalex.org/S456"])==[]
    assert "primary_location.source.id:S123|S456" in seen["filter"]
    assert seen["sort"]=="relevance_score:desc"


def test_registry_api_requires_auth_and_supports_crud_export(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","academic-registry-test-token")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","false")
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","false")
    factory=session_factory("sqlite:///"+str(tmp_path/"api.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with TestClient(api.app) as client:
        assert client.get("/api/academic-sources").status_code==401
        listed=client.get("/api/academic-sources",headers=HEADERS)
        assert listed.status_code==200 and listed.json()["summary"]["total"]==108
        created=client.post("/api/academic-sources",headers=HEADERS,json=payload("API Test Journal"))
        assert created.status_code==201,created.text
        ident=created.json()["id"]
        paused=client.patch("/api/academic-sources/"+ident,headers=HEADERS,
                            json={"enabled":False})
        assert paused.status_code==200 and paused.json()["enabled"] is False
        exported=client.get("/api/academic-sources/export",headers=HEADERS)
        assert exported.status_code==200 and "API Test Journal" in exported.json()["content"]
        domain=client.post("/api/academic-domains",headers=HEADERS,json={
            "slug":"new_frontier","name":"新兴计算方向","default_channels":["method"]})
        assert domain.status_code==201,domain.text
