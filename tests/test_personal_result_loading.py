"""Regression: existing personal portraits can bind missing scientific trial results.

This uses a real local SQLite auth session and the same API routes as the site.
No personal passwords, study subjects or model keys are involved.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
from backend.personal_research import (
    PersonalResearchProfile, PersonalResearchResult, seed_public_pilots,
)
from backend.team import create_member
from research_workbench.core import session_factory

KEY = "test-isolation-api-bearer"


@pytest.fixture
def studio(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_BEARER_TOKEN", KEY)
    monkeypatch.delenv("PERSONAL_RESEARCH_OWNER_EMAIL", raising=False)
    db_factory = session_factory("sqlite:///" + str(tmp_path / "personal-load.db"))
    monkeypatch.setattr(api, "get_factory", lambda: db_factory)
    with db_factory() as db:
        admin = create_member(db, "admin@example.invalid", "Admin",
                              "test-admin-secret-123456789", role="admin", initial=True)
        guest = create_member(db, "guest@example.invalid", "Researcher",
                              "test-guest-secret-123456789", role="researcher")
        assert seed_public_pilots(db)["available"] == 2
        db.add(PersonalResearchProfile(
            member_id=admin.id,
            payload_json=json.dumps({
                "version": "0.1.0", "scope": "personal",
                "explicitly_declared_interests": ["儿童健康空间外推","三维竖向城市化"],
                "note": "My independently customized research notes",
            }, ensure_ascii=False), status="user_confirmed",
        ))
        db.commit()
    with TestClient(api.app) as client:
        def token(email, password):
            res = client.post("/api/auth/login",
                              headers={"Authorization":"Bearer "+KEY},
                              json={"email":email,"password":password})
            assert res.status_code == 200, res.text
            return res.json()["token"]
        yield client, db_factory, token("admin@example.invalid","test-admin-secret-123456789"),token("guest@example.invalid","test-guest-secret-123456789")


def auth(token):
    return {"Authorization": "Bearer "+KEY, "X-Research-Session":token}


def test_existing_profile_with_no_linked_results_can_import_without_overwrite(studio):
    client, factory, admin, guest = studio
    p = client.get("/api/personal-research/me", headers=auth(admin))
    assert p.status_code == 200
    assert p.json()["profile"]["note"] == "My independently customized research notes"
    empty = client.get("/api/personal-research/me/results", headers=auth(admin))
    assert empty.status_code == 200
    state = empty.json()
    assert state["count"] == 0
    assert state["expected_count"] == 2
    assert state["available_public_count"] == 2
    assert state["requires_explicit_import"] is True
    assert len(state["missing_topic_keys"]) == 2

    linked = client.post("/api/personal-research/me/initialize", headers=auth(admin))
    assert linked.status_code == 200, linked.text
    assert linked.json()["linked_count"] == 2
    assert len(linked.json()["results"]) == 2
    for result in linked.json()["results"]:
        assert len(result["run"]["topic"]["probes"]) == 3
        assert result["visibility"] == "personal"
        assert result["review_status"] == "needs_scientific_review"

    after = client.get("/api/personal-research/me/results", headers=auth(admin)).json()
    assert after["count"] == 2
    assert after["requires_explicit_import"] is False
    assert after["missing_topic_keys"] == []
    assert client.post("/api/personal-research/me/initialize", headers=auth(admin)).status_code == 200
    with factory() as db:
        assert len(db.scalars(select(PersonalResearchResult)).all()) == 2
    p2 = client.get("/api/personal-research/me", headers=auth(admin)).json()
    assert p2["profile"]["note"] == "My independently customized research notes"
    assert client.get("/api/personal-research/me/results", headers=auth(guest)).json()["count"] == 0


def test_missing_public_evidence_returns_explicit_error(studio):
    client, factory, admin, _guest = studio
    from backend.personal_research import PublicPilotEvidence
    with factory() as db:
        for item in db.scalars(select(PublicPilotEvidence)).all():
            db.delete(item)
        db.commit()
    response = client.post("/api/personal-research/me/initialize", headers=auth(admin))
    assert response.status_code == 503
    assert "公开文献快照" in response.json()["detail"]
    assert client.get("/api/personal-research/me/results", headers=auth(admin)).json()["available_public_count"] == 0
