"""Verified public achievement catalogue and directory-metadata inference tests."""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
from backend.repository import (
    TeamAchievement, ResearchDataAsset, ResearchRefreshRun,
    seed_verified, list_outputs, create_refresh, refresh_public_works, ORCID
)
from backend.team import create_member
from research_workbench.core import session_factory

@pytest.fixture
def archive(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","test-service-secret")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","false")
    factory=session_factory("sqlite:///"+str(tmp_path/"research.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        create_member(db,"admin@example.org","Research Admin",
                      "unique-test-password-2026",role="admin",initial=True)
    with TestClient(api.app) as client:
        r=client.post("/api/auth/login",headers={"Authorization":"Bearer test-service-secret"},
             json={"email":"admin@example.org","password":"unique-test-password-2026"})
        assert r.status_code==200,r.text
        headers={"Authorization":"Bearer test-service-secret",
                 "X-Research-Session":r.json()["token"]}
        yield client,headers,factory

def test_verified_seed_is_idempotent_and_independent_of_external_paper_feed(archive):
    client,headers,factory=archive
    r=client.get("/api/team-repository",headers=headers)
    assert r.status_code==200,r.text
    assert r.json()["count"]>=36
    assert {x["kind"] for x in r.json()["items"]}=={"paper","project"}
    assert all(x["status"]=="verified" and x["source_url"] for x in r.json()["items"])
    assert any("Skyscraper urbanisation" in x["title"] for x in r.json()["items"])
    with factory() as db:
        assert seed_verified(db)==0
        assert db.scalars(select(TeamAchievement)).all()

def test_directory_metadata_is_private_and_supports_explainable_suggestions(archive):
    client,headers,factory=archive
    listing="buildings_2022.csv\nPOI_floor.xlsx\nstreet_network.shp\nstreet_network.dbf\nrainfall_daily.nc\n"
    r=client.post("/api/data-assets/import-directory",headers=headers,json={"listing":listing})
    assert r.status_code==200,r.text
    assert r.json()["new"]==4
    assert client.post("/api/data-assets/import-directory",headers=headers,
                       json={"listing":listing}).json()["new"]==0
    rows=client.get("/api/data-assets",headers=headers).json()["items"]
    assert {x["format"] for x in rows}=={"CSV","Excel","Shapefile","NetCDF"}
    assert all("raw" not in x for x in rows)
    inferred=client.get("/api/data-assets/opportunities",headers=headers).json()
    assert inferred["items"] and "仅基于目录" in inferred["disclaimer"]
    asset=rows[0]
    patched=client.patch("/api/data-assets/"+asset["id"],headers=headers,
                         json={"fields":["latitude","longitude"],"spatial_scale":"500 m"})
    assert patched.status_code==200 and patched.json()["spatial_scale"]=="500 m"
    bad=client.post("/api/data-assets/import-directory",headers=headers,
                    json={"listing":"../../secrets.csv\n/etc/passwd"})
    assert bad.status_code==200 and bad.json()["new"]==0

def test_refresh_requires_service_secret_and_author_is_disambiguated(archive,monkeypatch):
    client,headers,factory=archive
    bad=client.post("/api/team-repository/refresh-scheduled",headers=headers)
    assert bad.status_code==403
    monkeypatch.setenv("ATLAS_SYNC_SECRET","nonproduction-valid-secure-token-123456")
    bad2=client.post("/api/team-repository/refresh-scheduled",
        headers={**headers,"X-Atlas-Sync-Secret":"wrong"})
    assert bad2.status_code==403
    # Avoid live network during API request tests: exercise the scanner with a mock client.
    with factory() as db:
        run=create_refresh(db,"test")
    def responder(req):
        return httpx.Response(200,json={"results":[
            {"id":"https://openalex.org/W700001","title":"New urban geometry study with verified author",
             "publication_year":2026,"doi":"https://doi.org/10.5555/test-research",
             "authorships":[{"author":{"display_name":"Yao Shen","orcid":"https://orcid.org/"+ORCID}}],
             "primary_location":{"source":{"display_name":"Test Journal"}}},
            {"id":"https://openalex.org/W700002","title":"A different researcher shares the same name",
             "publication_year":2026,
             "authorships":[{"author":{"display_name":"Yao Shen","orcid":"https://orcid.org/0000-0001-7417-2233"}}],
             "primary_location":{"source":{"display_name":"Unrelated Journal"}}},
        ]})
    with httpx.Client(transport=httpx.MockTransport(responder)) as http:
        refresh_public_works(factory,run.id,client=http)
    with factory() as db:
        refreshed=db.get(ResearchRefreshRun,run.id)
        assert refreshed.status=="completed"
        assert refreshed.inserted==1
        candidate=db.get(TeamAchievement,"ach_123")
        titles=[x for x in list_outputs(db) if x["status"]=="review"]
        assert len(titles)==1
        assert "verified author" in titles[0]["title"]
        status=client.patch("/api/team-repository/"+titles[0]["id"],headers=headers,
            json={"status":"verified"})
        assert status.status_code==200,status.text
        assert status.json()["status"]=="verified"
