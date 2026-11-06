"""Read-only metadata export: no raw data, no path/custodian or accidental sharing."""
import json
import pytest
from fastapi.testclient import TestClient

import backend.api as api
from backend.team import create_member
from backend.repository import TeamAchievement
from backend.cusp import CuspDataset
from backend.research_evidence_export import team_evidence_bundle
from research_workbench.core import session_factory


@pytest.fixture
def export_client(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_BEARER_TOKEN", "service-test")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WORKER_MODE", "queue")
    monkeypatch.setenv("RESEARCH_EXPORT_TOKEN", "x" * 40)
    monkeypatch.setenv("RESEARCH_EXPORT_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_EXPORT_LLM_SHARING_APPROVED", "true")
    factory = session_factory("sqlite:///" + str(tmp_path / "research-export.db"))
    monkeypatch.setattr(api, "get_factory", lambda: factory)
    with factory() as db:
        create_member(db, "admin@example.com", "Admin", "long-test-password-123",
                      role="admin", initial=True)
        db.add(TeamAchievement(id="verified-output", title="Synthetic urban graph paper",
                               year=2025, kind="paper", status="verified",
                               tags_json=json.dumps(["network"])))
        db.add(TeamAchievement(id="pending-output", title="Pending work",
                               year=2026, kind="paper", status="review"))
        db.add(CuspDataset(id="dataset-public", name="Public synthetic land use",
                           sensitivity="public", description="Synthetic metadata",
                           custodian="PRIVATE-NAME", f_drive="PRIVATE-PATH",
                           backup="listed"))
        db.add(CuspDataset(id="dataset-internal", name="Internal synthetic dataset",
                           sensitivity="internal", description="PRIVATE-PROJECT"))
        db.add(CuspDataset(id="dataset-restricted", name="儿童健康个人轨迹",
                           sensitivity="public", description="PRIVATE-TRAJECTORY"))
        db.commit()
    with TestClient(api.app) as client:
        yield client


def test_readonly_safe_export_requires_scoped_token(export_client):
    route = "/api/integrations/research-agent-lab/evidence"
    assert export_client.get(route).status_code in (401, 403, 404)
    response = export_client.get(route, headers={"X-Research-Export-Token": "x" * 40})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source"] == "authorized_database_export"
    assert data["sharing_approved"] is True
    assert data["achievements"]
    assert {x["id"] for x in data["achievements"]} >= {"verified-output"}
    assert "pending-output" not in {x["id"] for x in data["achievements"]}
    assert {x["id"] for x in data["datasets"]} == {"dataset-public"}
    response_json = response.text
    assert "PRIVATE-" not in response_json
    assert "dataset-internal" not in response_json
    assert "dataset-restricted" not in response_json
    assert "no-store" in response.headers.get("cache-control", "")


def test_scoped_export_fails_closed_without_approval(export_client, monkeypatch):
    monkeypatch.setenv("RESEARCH_EXPORT_LLM_SHARING_APPROVED", "false")
    response = export_client.get(
        "/api/integrations/research-agent-lab/evidence",
        headers={"X-Research-Export-Token": "x" * 40}
    )
    assert response.status_code == 403
    monkeypatch.setenv("RESEARCH_EXPORT_LLM_SHARING_APPROVED", "true")
    monkeypatch.setenv("RESEARCH_EXPORT_ENABLED", "false")
    response = export_client.get(
        "/api/integrations/research-agent-lab/evidence",
        headers={"X-Research-Export-Token": "x" * 40}
    )
    assert response.status_code == 404
