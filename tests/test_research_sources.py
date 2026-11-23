"""Academic source registry CRUD, seeding and authorization tests."""
from fastapi.testclient import TestClient
import backend.api as api
from research_workbench.core import session_factory
from backend.research_sources import ResearchSource, domain_counts
from sqlalchemy import select

HEADERS={"Authorization":"Bearer registry-test-token"}

def test_registry_seed_is_idempotent_and_domain_split(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"sources.db"))
    with factory() as db:
        rows=db.scalars(select(ResearchSource)).all()
        assert len(rows)>=50
        before=domain_counts(db)
        assert before["total"]>=50
        from backend.research_sources import seed_default_sources
        assert seed_default_sources(db)==0

def test_registry_api_admin_crud_soft_delete_and_resolution_auth(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","registry-test-token")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","false")
    factory=session_factory("sqlite:///"+str(tmp_path/"api.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    client=TestClient(api.app)
    assert client.get("/api/research-sources").status_code==401
    listing=client.get("/api/research-sources",headers=HEADERS)
    assert listing.status_code==200 and listing.json()["summary"]["total"]>=50
    payload={"name":"Example Urban Computing Journal","abbreviation":"EUCJ",
      "kind":"journal","domain":"urban_planning","rank_label":"自定义",
      "ranking_system":"团队自定义","source_url":"https://example.org/journal",
      "aliases":["Example UCJ"],"notes":"test","enabled":True}
    created=client.post("/api/research-sources",headers=HEADERS,json=payload)
    assert created.status_code==200,created.text
    ident=created.json()["id"]
    updated=client.patch("/api/research-sources/"+ident,headers=HEADERS,
                         json={"enabled":False})
    assert updated.status_code==200 and updated.json()["enabled"] is False
    deleted=client.delete("/api/research-sources/"+ident,headers=HEADERS)
    assert deleted.status_code==200 and deleted.json()["enabled"] is False
    duplicate=client.post("/api/research-sources",headers=HEADERS,json=payload)
    assert duplicate.status_code==400


def test_openalex_resolver_queries_curated_aliases_exactly():
    from backend.research_sources import _openalex_source_candidates

    class Response:
        def __init__(self, results):
            self._results = results
        def raise_for_status(self):
            return None
        def json(self):
            return {"results": self._results}

    class Client:
        def __init__(self):
            self.queries = []
        def get(self, url, params):
            self.queries.append(params["search"])
            if params["search"] == "Advances in Neural Information Processing Systems":
                return Response([{
                    "id": "https://openalex.org/S4363606243",
                    "display_name": "neural information processing systems",
                    "abbreviated_title": "Neural Information Processing Systems",
                    "alternate_titles": ["Advances in neural information processing systems"],
                    "type": "conference",
                }])
            return Response([])

    row = ResearchSource(
        id="neurips-test", name="Conference on Neural Information Processing Systems",
        abbreviation="NeurIPS", kind="conference", domain="ai_ml",
        aliases_json='["NeurIPS", "Advances in Neural Information Processing Systems"]',
    )
    client = Client()
    matches = _openalex_source_candidates(row, client)
    assert [ident for _, ident in matches] == ["S4363606243"]
    assert "Advances in Neural Information Processing Systems" in client.queries
