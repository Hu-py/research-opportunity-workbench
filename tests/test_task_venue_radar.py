"""Offline integration tests for the child-health task-only journal discovery.

OpenAlex requests are mocked. No LLM, external API spending, or production DB.
"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
import backend.task_venue_radar as radar
from backend.research_sources import ResearchSource
from backend.team import create_member
from research_workbench.core import session_factory

SECRET = "test-child-health-source-service-token"
NAMES = {
    "A": ("S900001", "Health & Place"),
    "B": ("S900002", "Journal of Spatial Epidemiology"),
    "C": ("S900003", "Methods in Machine Learning"),
}


def _paper(source_id, name, number):
    return {
        "id": "https://openalex.org/W" + source_id[1:] + str(number),
        "display_name": "Relevant publication number " + str(number) + " in " + name,
        "doi": "https://doi.org/10.55555/test." + source_id + "." + str(number),
        "publication_year": 2025,
        "primary_location": {"source": {
            "id": "https://openalex.org/" + source_id,
            "display_name": name, "type": "journal", "issn_l": "1234-5678",
        }},
    }


def _mock_transport(request):
    query = request.url.params.get("search") or ""
    if "child" in query or "early childhood" in query:
        group = "A"
    elif "spatial generalization" in query or "geographical transfer" in query:
        group = "B"
    else:
        group = "C"
    sid, name = NAMES[group]
    # One source-backed journal observed on more than one relevant paper.
    papers = [_paper(sid, name, 1), _paper(sid, name, 2)]
    # A known baseline is NOT a novel recommendation.
    if group == "A":
        papers += [_paper("S900004", "Cities", 3), _paper("S900004", "Cities", 4)]
    papers.append({
        **_paper("S900005", "Random Preprint Repository", 5),
        "primary_location": {"source": {
            "id": "https://openalex.org/S900005",
            "display_name": "Random Preprint Repository", "type": "repository",
        }}
    })
    assert request.url.host == "api.openalex.org"
    assert request.url.path == "/works"
    assert "primary_location.source.type:journal" in request.url.params.get("filter", "")
    assert int(request.url.params.get("per-page")) <= 40
    return httpx.Response(200, json={"results": papers})


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_BEARER_TOKEN", SECRET)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    factory = session_factory("sqlite:///" + str(tmp_path / "journals.db"))
    monkeypatch.setattr(api, "get_factory", lambda: factory)
    with factory() as db:
        create_member(db, "owner@research.test", "Test Owner", "1234567890-test-admin",
                      role="admin", initial=True)
        create_member(db, "other@research.test", "Other Researcher", "1234567890-test-other",
                      role="researcher")
    client_http = httpx.Client(transport=httpx.MockTransport(_mock_transport))
    real_run = radar.execute_discovery
    monkeypatch.setattr(radar, "execute_discovery",
                        lambda f, i: real_run(f, i, client=client_http))
    def fake_query(query, since, limit=15, client=None, source_ids=None):
        assert source_ids is not None and len(source_ids) > 0
        # Only a previously approved OpenAlex Source ID or baseline resolved ID.
        assert set(source_ids).issubset({"S900001","S900002","S900003","S100001"})
        sid = source_ids[0]
        return [_paper(sid, "Verified Selected Journal", 8)]
    monkeypatch.setattr(radar, "query_openalex", fake_query)
    with TestClient(api.app) as client:
        def login(email, password):
            response = client.post("/api/auth/login",json={"email":email,"password":password},
                         headers={"Authorization":"Bearer "+SECRET})
            assert response.status_code == 200, response.text
            return response.json()["token"]
        yield client, factory, login("owner@research.test","1234567890-test-admin"),login("other@research.test","1234567890-test-other")


def headers(token):
    return {"Authorization":"Bearer "+SECRET,"X-Research-Session":token}


def url(path=""):
    return "/api/personal-research/me/journal-radar" + path


def test_requires_login_and_initial_task_directory_is_narrow(workspace):
    client, factory, owner, other = workspace
    assert client.get(url()).status_code == 401
    data = client.get(url(),headers=headers(owner)).json()
    assert data["task_key"] == radar.TASK_KEY
    assert len(data["baseline"]) == 9
    assert data["directory"] == []
    assert data["candidates"] == []
    assert data["limits"]["llm_calls"] == 0
    assert data["limits"]["automated_approval"] is False
    assert sum(len(v) for v in data["search_plan"].values()) == 6
    assert client.get(url(),headers=headers(other)).json()["candidates"] == []


def test_discovery_creates_review_queue_not_global_approval(workspace):
    client, factory, owner, other = workspace
    with factory() as db:
        sources_before = db.query(ResearchSource).count()
    response = client.post(url("/discover"),headers=headers(owner))
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    view = client.get(url(),headers=headers(owner)).json()
    last = view["runs"][0]
    assert last["id"] == run_id and last["status"] == "completed"
    assert last["requests_made"] == 6
    assert last["works_seen"] > 6
    assert view["directory"] == []  # absolutely no auto-approval
    assert {c["probe_group"] for c in view["candidates"]} == {"A","B","C"}
    assert all(c["status"] == "pending" for c in view["candidates"])
    assert all(c["evidence"]["sample_papers"] for c in view["candidates"])
    assert not any(c["name"] == "Cities" for c in view["candidates"])
    assert not any("Repository" in c["name"] for c in view["candidates"])
    assert client.get(url(),headers=headers(other)).json()["candidates"] == []
    with factory() as db:
        assert db.query(ResearchSource).count() == sources_before
    # An immediate second run is rate-limited / previous run cannot fan out.
    assert client.post(url("/discover"),headers=headers(owner)).status_code == 409


def test_approval_updates_only_my_task_allowlist_and_can_be_paused(workspace):
    client, factory, owner, other = workspace
    client.post(url("/discover"),headers=headers(owner))
    data = client.get(url(),headers=headers(owner)).json()
    cand = next(x for x in data["candidates"] if x["probe_group"] == "A")
    candidate_id = cand["id"]
    assert client.post(url("/candidates/"+candidate_id+"/review"),
                       headers=headers(other),
                       json={"decision":"approve","reason":"This journal has relevant child health papers"}).status_code == 404
    assert client.post(url("/candidates/"+candidate_id+"/review"),
                       headers=headers(owner),
                       json={"decision":"approve","reason":"x"}).status_code == 422
    response = client.post(url("/candidates/"+candidate_id+"/review"),
                      headers=headers(owner),
                      json={"decision":"approve","reason":"Child health evidence and environmental exposures"})
    assert response.status_code == 200, response.text
    view = client.get(url(),headers=headers(owner)).json()
    assert len(view["directory"]) == 1
    entry = view["directory"][0]
    assert entry["name"] == "Health & Place"
    assert entry["probe_group"] == "A"
    assert "S900001" in view["active_source_ids"]["A"]
    assert client.post(url("/candidates/"+candidate_id+"/review"),
                       headers=headers(owner),
                       json={"decision":"approve","reason":"Repeat approval"}).status_code == 409
    assert client.get(url(),headers=headers(other)).json()["directory"] == []
    scan = client.post(url("/scan-approved"),headers=headers(owner))
    assert scan.status_code == 202, scan.text
    assert "S900001" in scan.json()["source_ids"]["A"]
    entry_id = entry["id"]
    assert client.post(url("/directory/"+entry_id+"/status"),headers=headers(other),
                       json={"action":"pause","reason":"Not appropriate anymore"}).status_code == 404
    pause = client.post(url("/directory/"+entry_id+"/status"),headers=headers(owner),
                       json={"action":"pause","reason":"Temporary pause after evaluation"})
    assert pause.status_code == 200 and pause.json()["active"] is False
    view = client.get(url(),headers=headers(owner)).json()
    assert "S900001" not in view["active_source_ids"]["A"]
    assert client.post(url("/directory/"+entry_id+"/status"),headers=headers(owner),
                       json={"action":"resume","reason":"Restore after review"}).status_code == 200
    assert "S900001" in client.get(url(),headers=headers(owner)).json()["active_source_ids"]["A"]
    with factory() as db:
        assert db.query(ResearchSource).filter(ResearchSource.name=="Health & Place").count() == 0


def test_rejected_candidates_are_recorded_but_not_applied(workspace):
    client, factory, owner, other = workspace
    client.post(url("/discover"),headers=headers(owner))
    c=client.get(url(),headers=headers(owner)).json()["candidates"][0]
    r=client.post(url("/candidates/"+c["id"]+"/review"),headers=headers(owner),
                  json={"decision":"reject","reason":"Journal subject coverage is not appropriate"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert not client.get(url(),headers=headers(owner)).json()["directory"]


def test_scanner_uses_only_explicit_source_ids_and_stores_paper_evidence(workspace,monkeypatch):
    client, factory, owner, other = workspace
    client.post(url("/discover"),headers=headers(owner))
    cand=client.get(url(),headers=headers(owner)).json()["candidates"][0]
    approved=client.post(url("/candidates/"+cand["id"]+"/review"),headers=headers(owner),
                        json={"decision":"approve","reason":"Research source selected after evidence review"})
    assert approved.status_code == 200
    real_scan=radar.execute_paper_scan
    monkeypatch.setattr(radar,"execute_paper_scan",lambda f,i: real_scan(f,i,client=None))
    response=client.post(url("/scan-approved"),headers=headers(owner))
    assert response.status_code == 202
    data=client.get(url(),headers=headers(owner)).json()
    assert data["paper_runs"][0]["status"] == "completed"
    assert len(data["paper_runs"][0]["papers"]) >= 1
    assert all(p["url"].startswith("https://") for p in data["paper_runs"][0]["papers"])
    assert client.get(url(),headers=headers(other)).json()["paper_runs"] == []
