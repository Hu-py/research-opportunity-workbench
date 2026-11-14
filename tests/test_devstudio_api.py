"""Development Studio P0: real persisted governance, permissions, and no hidden release."""
import pytest
from fastapi.testclient import TestClient

import backend.api as server
from backend.team import create_member
from research_workbench.core import session_factory


def headers(token=""):
    value = {"Authorization": "Bearer devstudio-test-service-key"}
    if token:
        value["X-Research-Session"] = token
    return value


def sign_in(client, email, password):
    response = client.post("/api/auth/login", headers=headers(), json={
        "email": email, "password": password,
    })
    assert response.status_code == 200, response.text
    return response.json()["token"]


@pytest.fixture
def studio(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_BEARER_TOKEN", "devstudio-test-service-key")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WORKER_MODE", "queue")
    factory = session_factory("sqlite:///" + str(tmp_path / "devstudio.db"))
    monkeypatch.setattr(server, "get_factory", lambda: factory)
    with factory() as db:
        create_member(db, "admin@lab.example", "Admin",
                      "integration-admin-password-2026", role="admin", initial=True)
        create_member(db, "researcher@lab.example", "Researcher",
                      "integration-research-password-2026", role="researcher")
        create_member(db, "viewer@lab.example", "Viewer",
                      "integration-viewer-password-2026", role="viewer")
    with TestClient(server.app) as client:
        yield (client,
               sign_in(client, "admin@lab.example", "integration-admin-password-2026"),
               sign_in(client, "researcher@lab.example", "integration-research-password-2026"),
               sign_in(client, "viewer@lab.example", "integration-viewer-password-2026"))


def test_source_change_needs_separate_approver_and_never_modifies_live_sources(studio):
    client, admin, researcher, viewer = studio
    assert client.get("/api/devstudio/overview", headers=headers()).status_code == 401
    initial = client.get("/api/devstudio/sources", headers=headers(admin)).json()
    assert initial["legacy_registry"]
    assert all(x["atlas_classification_status"] == "not_migrated"
               and x["atlas_source_groups"] == [] for x in initial["legacy_registry"])
    proposal = {
        "module_id": "DISCOVERY",
        "kind": "source",
        "title": "Add a reviewed B category journal",
        "reason": "The previous source registry is not equivalent to the new three-source plan.",
        "proposed": {"operation": "add", "name": "New B journal",
                     "source_groups": ["urban_science"]},
    }
    assert client.post("/api/devstudio/changes", json=proposal,
                       headers=headers(viewer)).status_code == 403
    r = client.post("/api/devstudio/changes", json=proposal, headers=headers(researcher))
    assert r.status_code == 201, r.text
    change_id = r.json()["id"]
    assert r.json()["status"] == "submitted"
    assert r.json()["risk"] == "medium"
    assert client.get("/api/devstudio/sources", headers=headers(viewer)).json()["source_proposals"][0]["id"] == change_id
    r = client.post("/api/devstudio/changes/" + change_id + "/decisions",
                    headers=headers(researcher), json={"decision": "approve",
                                                        "reason": "Seems acceptable"})
    assert r.status_code == 403
    r = client.post("/api/devstudio/changes/" + change_id + "/decisions",
                    headers=headers(admin), json={"decision": "approve",
                                                  "reason": "Reviewed official venue identity"})
    assert r.status_code == 201, r.text
    assert r.json()["change"]["status"] == "approved_pending_release"
    assert r.json()["applied_to_production"] is False
    r = client.post("/api/devstudio/changes/" + change_id + "/decisions",
                    headers=headers(admin), json={"decision": "approve",
                                                  "reason": "Try approving twice"})
    assert r.status_code == 409
    after = client.get("/api/devstudio/sources", headers=headers(admin)).json()
    assert after["legacy_registry"] == initial["legacy_registry"]
    assert after["source_proposals"][0]["status"] == "approved_pending_release"


def test_self_approval_blocked_and_invalid_source_changes_rejected(studio):
    client, admin, researcher, viewer = studio
    root = {"module_id": "DISCOVERY", "kind": "source",
            "title": "Potential source change",
            "reason": "Need to evaluate a new research source for the next weekly run.",
            "proposed": {"operation": "add", "name": "Future source",
                         "source_groups": ["computational_methods"]}}
    self_change = client.post("/api/devstudio/changes", json=root,
                              headers=headers(admin)).json()
    r = client.post("/api/devstudio/changes/" + self_change["id"] + "/decisions",
                    headers=headers(admin), json={"decision": "approve",
                                                  "reason": "I approve my own change"})
    assert r.status_code == 403
    broken = {**root, "proposed": {"operation": "add", "name": "Bad item",
                                  "source_groups": ["RadarB"]}}
    assert client.post("/api/devstudio/changes", json=broken,
                       headers=headers(researcher)).status_code == 422


def test_document_experiment_runs_and_lineage(studio):
    client, admin, researcher, viewer = studio
    doc = client.post("/api/devstudio/documents", headers=headers(researcher),
                      json={"module_id": "PLATFORM", "title": "Technical workflow architecture",
                            "category": "architecture",
                            "authoritative_url": "https://github.com/Hu-py/research-opportunity-workbench/blob/main/docs/ARCHITECTURE.md"})
    assert doc.status_code == 201, doc.text
    assert doc.json()["status"] == "indexed_draft"
    assert client.post("/api/devstudio/documents", headers=headers(researcher),
                       json={"module_id": "PLATFORM", "title": "Unsafe local file",
                             "category": "operations",
                             "authoritative_url": "http://internal.example/file"}).status_code == 422
    issue = client.post("/api/devstudio/issues", headers=headers(researcher), json={
        "module_id": "DISCOVERY", "title": "C venue missing in recent index",
        "description": "Official JMLR publication does not appear in the venue-filtered API results.",
    })
    assert issue.status_code == 201
    change = client.post("/api/devstudio/changes", headers=headers(researcher), json={
        "module_id": "DISCOVERY", "issue_id": issue.json()["id"], "kind": "code",
        "title": "Add second publisher evidence channel",
        "reason": "Recent official JMLR papers are absent from the source-filtered API snapshot.",
        "proposed": {"github_pr": "https://github.com/Hu-py/research-opportunity-workbench/pull/57"},
    })
    assert change.status_code == 201
    exp = client.post("/api/devstudio/experiments", headers=headers(researcher), json={
        "module_id": "DISCOVERY",
        "change_id": change.json()["id"],
        "title": "OpenAlex versus official journal sample",
        "hypothesis": "Complete pagination will increase the known-sentinel hit count.",
        "baseline": "Previous capped API run",
        "input_snapshot_ref": "experiments/atlas_pilot_2026_11_14/official_sentinels.json",
        "metrics": ["sentinel_hit_fraction", "data_source_validity"],
    })
    assert exp.status_code == 201, exp.text
    run = client.post("/api/devstudio/experiments/" + exp.json()["id"] + "/runs",
                      headers=headers(researcher), json={
                          "kind": "github_actions",
                          "external_url": "https://github.com/Hu-py/research-opportunity-workbench/actions/runs/43552802805",
                          "code_sha": "abcd1234",
                          "note": "Run is externally linked and not yet verified by API",
                      })
    assert run.status_code == 201, run.text
    assert run.json()["status"] == "unverified"
    bad = client.post("/api/devstudio/experiments/" + exp.json()["id"] + "/runs",
                      headers=headers(researcher), json={
                          "kind": "github_actions",
                          "external_url": "https://github.com/another/repo/actions/runs/1"})
    assert bad.status_code == 422
    evaluation = client.post("/api/devstudio/runs/" + run.json()["id"] + "/evaluations",
                             headers=headers(researcher), json={
                                 "rubric_version": "source-sentinel-v1",
                                 "scores": {"traceability": 4, "coverage": 3},
                                 "limitations": "Not a full journal census",
                             })
    assert evaluation.status_code == 201, evaluation.text
    lineage = client.get("/api/devstudio/lineage/DISCOVERY",
                         headers=headers(viewer)).json()
    assert len(lineage["issues"]) == 1
    assert any(x["id"] == change.json()["id"] for x in lineage["changes"])
    assert lineage["experiments"][0]["id"] == exp.json()["id"]
    assert lineage["runs"][0]["status"] == "unverified"
    assert client.get("/api/devstudio/runs/" + run.json()["id"] + "/evaluations",
                      headers=headers(viewer)).json()["items"][0]["scores"]["traceability"] == 4
    assert client.get("/api/team/audit", headers=headers(admin)).status_code == 200


def test_studio_requires_team_auth_in_legacy_mode(studio, monkeypatch):
    client, admin, researcher, viewer = studio
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "false")
    assert client.get("/api/devstudio/overview", headers=headers()).status_code == 403
    assert client.post("/api/devstudio/issues", headers=headers(),
                       json={"module_id": "DISCOVERY", "title": "Unsafe legacy edit",
                             "description": "Should not bypass member attribution."}).status_code == 403
