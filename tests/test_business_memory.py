"""Integration tests for append-only Business Agent research memory."""
import pytest
from fastapi.testclient import TestClient

import backend.api as api
from backend.team import create_member
from backend.repository import TeamAchievement
from backend.cusp import CuspDataset
from research_workbench.core import session_factory


def service(session=None):
    headers = {"Authorization": "Bearer integration-test-service"}
    if session:
        headers["X-Research-Session"] = session
    return headers


def agent_headers():
    return {"X-Research-Agent-Key": "t" * 48}


@pytest.fixture
def setup_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_BEARER_TOKEN", "integration-test-service")
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("WORKER_MODE", "queue")
    monkeypatch.setenv("BUSINESS_AGENT_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("BUSINESS_AGENT_BRIDGE_TOKEN", "t" * 48)
    monkeypatch.setenv("BUSINESS_AGENT_SHARING_APPROVED", "true")
    factory = session_factory("sqlite:///" + str(tmp_path / "agent-memory.db"))
    monkeypatch.setattr(api, "get_factory", lambda: factory)
    with factory() as db:
        create_member(db, "admin@example.org", "Admin",
                      "secure-test-admin-password", role="admin", initial=True)
        create_member(db, "scientist@example.org", "Researcher",
                      "secure-test-research-password", role="researcher")
        db.add(TeamAchievement(
            id="verified-public-output", title="Urban science synthetic output",
            year=2025, kind="paper", status="verified", tags_json='["urban"]'))
        db.add(CuspDataset(id="safe-public-asset", name="Public synthetic tiles",
                           sensitivity="public"))
        db.add(CuspDataset(id="private-asset", name="SECRET INTERNAL PROJECT",
                           sensitivity="internal"))
        db.commit()
    with TestClient(api.app) as client:
        def sign_in(email, password):
            response = client.post("/api/auth/login", headers=service(),
                                   json={"email": email, "password": password})
            assert response.status_code == 200, response.text
            return response.json()["token"]
        yield client, sign_in("admin@example.org", "secure-test-admin-password"), sign_in(
            "scientist@example.org", "secure-test-research-password")


def payload(context):
    ref = "team_achievements:" + context["context"]["achievements"][0]["id"]
    return {
        "run_key": "research-week-2026-W45-v1",
        "context_hash": context["context_hash"],
        "agent_version": "advisor-v1",
        "topic": "Urban research opportunity exploration",
        "proposals": [{
            "title": "Urban research question with testable hypothesis",
            "question": "Which spatial mechanisms produce testable differences in urban outcomes?",
            "novelty_gap": "Prior research may not have tested this mechanism; requires direct prior-art verification.",
            "method": "Use spatial panel methods and explicit baseline controls for a falsifiable design.",
            "first_experiment": "Inspect labels and build a baseline before making causal interpretations.",
            "evidence_refs": [ref],
            "external_papers_unverified": ["https://doi.org/10.0000/example-not-verified"],
        }],
    }


def test_database_memory_roundtrip_feedback_and_idempotency(setup_client):
    client, admin, researcher = setup_client
    base = "/api/business-agent"
    assert client.get(base + "/context").status_code == 401
    response = client.get(base + "/context", headers=agent_headers())
    assert response.status_code == 200, response.text
    context = response.json()
    assert "private-asset" not in response.text
    assert "SECRET INTERNAL PROJECT" not in response.text

    body = payload(context)
    created = client.post(base + "/runs", headers=agent_headers(), json=body)
    assert created.status_code == 201, created.text
    run = created.json()
    assert len(run["ideas"]) == 1
    idea_id = run["ideas"][0]["id"]
    again = client.post(base + "/runs", headers=agent_headers(), json=body)
    assert again.status_code == 201 and again.json()["run_id"] == run["run_id"]
    changed = {**body, "topic": "different topic"}
    assert client.post(base + "/runs", headers=agent_headers(),
                       json=changed).status_code == 409


    # The external agent must read back persisted ideas through its own narrow key.
    assert client.get(base + "/agent-runs").status_code == 401
    history = client.get(base + "/agent-runs", headers=agent_headers())
    assert history.status_code == 200, history.text
    assert len(history.json()["items"]) == 1
    assert history.json()["items"][0]["run_id"] == run["run_id"]
    detail = client.get(base + "/agent-runs/" + run["run_id"],headers=agent_headers())
    assert detail.status_code == 200
    assert detail.json()["ideas"][0]["id"] == idea_id
    assert client.get(base + "/agent-runs/bad-id",headers=agent_headers()).status_code == 422
    assert client.get(base + "/agent-runs/00000000-0000-4000-a000-000000000000",
                      headers=agent_headers()).status_code == 404

    assert client.get(base + "/runs", headers=service(researcher)).status_code == 200
    feedback_route = base + "/ideas/" + idea_id + "/feedback"
    vote = {"decision": "revise", "novelty": 3, "feasibility": 4,
            "scientific_value": 5, "testability": 4,
            "comment": "Prioritize mechanism, not only predictive accuracy."}
    assert client.post(feedback_route, headers=agent_headers(), json=vote).status_code == 401
    stored = client.post(feedback_route, headers=service(researcher), json=vote)
    assert stored.status_code == 200, stored.text
    assert stored.json()["stored"] is True
    assert client.post(feedback_route, headers=service(researcher),
                       json=vote).status_code == 409
    new_context = client.get(base + "/context", headers=agent_headers()).json()
    assert new_context["context_hash"] != context["context_hash"]
    assert new_context["context"]["meeting_history"][0]["decision"] == "revise"
    assert "mechanism" in new_context["context"]["meeting_history"][0]["comment"]

    audit = client.get(base + "/storage-audit", headers=service(admin))
    assert audit.status_code == 200, audit.text
    assert audit.json()["new_record_counts"]["business_agent_runs"] == 1
    assert audit.json()["new_record_counts"]["business_meeting_feedback"] == 1
    assert client.get(base + "/storage-audit", headers=service(researcher)).status_code == 403


def test_unapproved_context_invalid_references_and_revision(setup_client, monkeypatch):
    client, admin, _ = setup_client
    base = "/api/business-agent"
    ctx = client.get(base + "/context", headers=agent_headers()).json()
    bad = payload(ctx)
    bad["proposals"][0]["evidence_refs"] = ["papers:does-not-exist"]
    assert client.post(base + "/runs", headers=agent_headers(), json=bad).status_code == 422
    bad["proposals"][0]["evidence_refs"] = payload(ctx)["proposals"][0]["evidence_refs"]
    bad["proposals"][0]["parent_idea_id"] = "missing-id"
    assert client.post(base + "/runs", headers=agent_headers(), json=bad).status_code == 422
    assert client.get(base + "/storage-audit",
                      headers=service(admin)).json()["new_record_counts"]["business_agent_runs"] == 0

    monkeypatch.setenv("BUSINESS_AGENT_SHARING_APPROVED", "false")
    assert client.get(base + "/context", headers=agent_headers()).status_code == 403
    monkeypatch.setenv("BUSINESS_AGENT_SHARING_APPROVED", "true")
    monkeypatch.setenv("BUSINESS_AGENT_BRIDGE_ENABLED", "false")
    assert client.get(base + "/context", headers=agent_headers()).status_code == 404
