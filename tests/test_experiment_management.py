"""Versioned Development Studio experiment CRUD/search/workflow in an isolated SQLite DB."""
import pytest
from fastapi.testclient import TestClient

import backend.api as server
from backend.team import create_member
from research_workbench.core import session_factory

SERVICE = {"Authorization": "Bearer studio-experiment-management-test"}
BASE = "/api/devstudio/experiment-management"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("API_BEARER_TOKEN", SERVICE["Authorization"].split(" ", 1)[1])
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WORKER_MODE", "queue")
    factory = session_factory("sqlite:///" + str(tmp_path / "experiments.db"))
    monkeypatch.setattr(server, "get_factory", lambda: factory)
    with factory() as db:
        create_member(db, "admin@example.invalid", "Admin", "admin-password-minimum-2026",
                      role="admin", initial=True)
        create_member(db, "editor@example.invalid", "Editor", "editor-password-minimum-2026",
                      role="researcher")
        create_member(db, "viewer@example.invalid", "Viewer", "viewer-password-minimum-2026",
                      role="viewer")
    with TestClient(server.app) as c:
        def token(email, password):
            res = c.post("/api/auth/login", headers=SERVICE,
                         json={"email": email, "password": password})
            assert res.status_code == 200, res.text
            return {**SERVICE, "X-Research-Session": res.json()["token"]}
        yield c, token("admin@example.invalid", "admin-password-minimum-2026"), \
              token("editor@example.invalid", "editor-password-minimum-2026"), \
              token("viewer@example.invalid", "viewer-password-minimum-2026")


def payload(**overrides):
    return {
        "module_id": "PLATFORM",
        "title": "Development Studio experiment lifecycle",
        "hypothesis": "A versioned registry can preserve experiment history and classification.",
        "baseline": "Old experiment form",
        "input_snapshot_ref": "snapshots/stage1.json",
        "metrics": ["accuracy", "latency"],
        "objective": "reliability",
        "scenario": "platform",
        "change_object": "backend",
        "method": "Replay several verified snapshots",
        "expected_result": "No stale writes or missing revisions",
        **overrides,
    }


def test_create_filter_edit_history_and_stale_conflict(env):
    c, admin, editor, viewer = env
    assert c.get(BASE, headers=SERVICE).status_code == 401
    assert c.post(BASE, json=payload(), headers=viewer).status_code == 403
    res = c.post(BASE, json=payload(), headers=editor)
    assert res.status_code == 201, res.text
    exp = res.json()
    assert exp["revision"] == 1 and exp["objective"] == "reliability"
    exp_id = exp["id"]
    assert c.get(BASE, headers=viewer).json()["count"] == 1
    assert c.get(BASE + "?objective=quality", headers=viewer).json()["items"] == []
    assert c.get(BASE + "?scenario=platform&query=versioned", headers=viewer).json()["count"] == 1
    assert c.get(BASE + "?scenario=bad-scenario", headers=viewer).status_code == 422
    patch = c.patch(BASE + "/" + exp_id, headers=editor, json={
        "expected_revision": 1, "objective": "performance", "title": "Latency baseline test",
        "method": "Run both datasets with equal partitions",
    })
    assert patch.status_code == 200, patch.text
    assert patch.json()["revision"] == 2
    assert patch.json()["method"] == "Run both datasets with equal partitions"
    assert c.patch(BASE + "/" + exp_id, headers=editor, json={
        "expected_revision": 1, "title": "Stale edit should fail",
    }).status_code == 409
    assert c.patch(BASE + "/" + exp_id, headers=viewer, json={
        "expected_revision": 2, "title": "Unauthorized editor",
    }).status_code == 403
    events = c.get(BASE + "/" + exp_id + "/history", headers=viewer).json()["items"]
    assert [x["revision"] for x in events] == [2, 1]
    assert events[0]["details"]["objective"]["before"] == "reliability"
    assert events[0]["details"]["objective"]["after"] == "performance"
    assert c.get("/api/team/audit", headers=admin).status_code == 200


def test_status_flow_archive_and_review_gate(env):
    c, admin, editor, viewer = env
    exp = c.post(BASE, json=payload(), headers=admin).json()
    path = BASE + "/" + exp["id"]
    assert c.patch(path, json={"expected_revision": 1, "status": "completed"},
                   headers=admin).status_code == 409
    running = c.patch(path, json={"expected_revision": 1, "status": "running"},
                      headers=admin)
    assert running.status_code == 200
    assert c.patch(path, json={"expected_revision": 2, "status": "completed"},
                   headers=admin).status_code == 409
    review = c.patch(path, json={"expected_revision": 2, "status": "review"},
                     headers=admin)
    assert review.status_code == 200
    assert c.patch(path, json={"expected_revision": 3, "status": "completed"},
                   headers=admin).status_code == 409

    run = c.post("/api/devstudio/experiments/" + exp["id"] + "/runs",
                 json={"kind": "internal", "external_url": "/api/tasks/example1234"},
                 headers=editor)
    assert run.status_code == 201, run.text
    grade = c.post("/api/devstudio/runs/" + run.json()["id"] + "/evaluations",
                   json={"rubric_version": "manual-v1", "scores": {"quality": 4},
                         "limitations": "Manual evaluation, not an automated result."},
                   headers=editor)
    assert grade.status_code == 201
    complete = c.patch(path, json={"expected_revision": 3, "status": "completed",
                                   "conclusion": "Manual review was recorded"}, headers=admin)
    assert complete.status_code == 200 and complete.json()["status"] == "completed"
    archived = c.patch(path, json={"expected_revision": 4, "status": "archived"},
                       headers=admin)
    assert archived.status_code == 200
    assert c.get(BASE, headers=viewer).json()["count"] == 0
    assert c.get(BASE + "?include_archived=true", headers=viewer).json()["count"] == 1
    assert c.patch(path, json={"expected_revision": 5, "title": "Cannot silently edit archived"},
                   headers=admin).status_code == 409
    reopened = c.patch(path, json={"expected_revision": 5, "status": "planned"}, headers=admin)
    assert reopened.status_code == 200


def test_legacy_experiment_remains_readable_and_editable(env):
    c, admin, editor, viewer = env
    legacy = c.post("/api/devstudio/experiments", headers=editor, json={
        "module_id": "PLATFORM", "title": "Existing legacy experiment",
        "hypothesis": "Old records remain readable after adding new profile tables",
        "metrics": ["test"],
    })
    assert legacy.status_code == 201
    legacy_id = legacy.json()["id"]
    res = c.get(BASE + "/" + legacy_id, headers=viewer)
    assert res.status_code == 200 and res.json()["revision"] == 0
    patch = c.patch(BASE + "/" + legacy_id, headers=admin,
                    json={"expected_revision": 0, "scenario": "radar_a",
                          "objective": "coverage"})
    assert patch.status_code == 200 and patch.json()["revision"] == 1
    assert patch.json()["metrics"] == ["test"]
    assert c.get(BASE + "?scenario=radar_a", headers=viewer).json()["count"] == 1


def test_invalid_classification_and_missing_change_are_rejected(env):
    c, admin, editor, viewer = env
    assert c.post(BASE, headers=editor, json=payload(objective="madeup")).status_code == 422
    assert c.post(BASE, headers=editor, json=payload(
        metrics=["same", "same"])).status_code == 422
    assert c.post(BASE, headers=editor, json=payload(
        change_id="change_nonexistent")).status_code == 422
    new = c.post(BASE, headers=editor, json=payload()).json()
    assert c.patch(BASE + "/" + new["id"], headers=editor,
                   json={"expected_revision": 1, "change_id": "nope"}).status_code == 422
    assert c.patch(BASE + "/" + new["id"], headers=editor,
                   json={"expected_revision": 1, "status": "archived",
                         "conclusion": "Keep an audited close-out"}).status_code == 200
