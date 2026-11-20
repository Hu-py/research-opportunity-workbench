"""Offline, deterministic tests for signed Development Studio GitHub synchronization."""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import backend.api as server
from backend.team import create_member
from backend.devstudio_github_sync import REPO, DevGithubActivity, DevGithubDelivery
from research_workbench.core import session_factory

SECRET = "devstudio-github-test-secret-" + "k" * 40
SHA = "a" * 40
ROOT = {"repository": {"full_name": REPO}, "sender": {"login": "maintainer"}}


@pytest.fixture
def studio(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_BEARER_TOKEN", "devstudio-service-test-token")
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("DEVSTUDIO_GITHUB_SYNC_ENABLED", "true")
    monkeypatch.setenv("DEVSTUDIO_GITHUB_SYNC_SECRET", SECRET)
    factory = session_factory("sqlite:///" + str(tmp_path / "studio-github.db"))
    monkeypatch.setattr(server, "get_factory", lambda: factory)
    with factory() as db:
        create_member(db, "owner@lab.example", "Owner",
                      "long-test-credential-owner-111", role="admin", initial=True)
        create_member(db, "reader@lab.example", "Reader",
                      "long-test-credential-reader-111", role="viewer")
    with TestClient(server.app) as client:
        def login(email, password):
            response = client.post("/api/auth/login",
                headers={"Authorization": "Bearer devstudio-service-test-token"},
                json={"email": email, "password": password})
            assert response.status_code == 200, response.text
            return response.json()["token"]
        yield client, factory, login("owner@lab.example", "long-test-credential-owner-111"), login("reader@lab.example", "long-test-credential-reader-111")


def auth(token):
    return {"Authorization": "Bearer devstudio-service-test-token",
            "X-Research-Session": token}


def send(client, event, payload, delivery, sign=True):
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    digest = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/api/devstudio/github/webhook", content=raw, headers={
        "Content-Type": "application/json",
        "X-Hub-Signature-256": digest if sign else "sha256=" + "0"*64,
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery,
    })


def pr(number=70, state="open", updated="2026-11-14T09:00:00Z", draft=True):
    return {**ROOT, "action": "synchronize", "number": number,
        "pull_request": {"number": number, "title": "SC01 research case",
            "state": state, "draft": draft, "merged": False,
            "updated_at": updated, "head": {"ref": "experiment/sc01", "sha": SHA},
            "user": {"login": "maintainer"}}}


def run(event_status="completed", conclusion="success", updated="2026-11-14T09:30:00Z"):
    return {**ROOT, "action": "completed", "workflow_run": {
        "id": 43608073111, "name": "CI", "run_number": 1182,
        "status": event_status, "conclusion": conclusion,
        "updated_at": updated, "head_sha": SHA, "head_branch": "experiment/sc01",
        "actor": {"login": "maintainer"}}}


def test_webhook_rejects_bad_signatures_repo_and_disabled(studio, monkeypatch):
    client, _factory, owner, viewer = studio
    assert send(client, "pull_request", pr(), "delivery-1", sign=False).status_code == 401
    bad = pr()
    bad["repository"] = {"full_name": "someone/other-repo"}
    assert send(client, "pull_request", bad, "delivery-2").status_code == 422
    assert client.get("/api/devstudio/github/activity", headers=auth(viewer)).json()["items"] == []
    assert client.get("/api/devstudio/github/activity").status_code == 401
    monkeypatch.setenv("DEVSTUDIO_GITHUB_SYNC_ENABLED", "false")
    assert send(client, "pull_request", pr(), "delivery-3").status_code == 503
    assert client.get("/api/devstudio/github/activity", headers=auth(owner)).json()["integration_status"] == "disabled"


def test_pr_updates_in_place_and_replayed_deliveries_are_idempotent(studio):
    client, factory, owner, _viewer = studio
    first = send(client, "pull_request", pr(), "delivery-a")
    assert first.status_code == 200, first.text
    assert first.json() == {"state": "applied", "events": 1}
    again = send(client, "pull_request", pr(), "delivery-a")
    assert again.status_code == 200
    assert again.json()["state"] == "duplicate"
    closed = pr(state="closed", updated="2026-11-14T11:00:00Z", draft=False)
    closed["pull_request"]["merged"] = True
    res = send(client, "pull_request", closed, "delivery-b")
    assert res.status_code == 200, res.text
    # A delayed older webhook cannot revert the later merged status.
    assert send(client, "pull_request", pr(), "delivery-c").status_code == 200
    feed = client.get("/api/devstudio/github/activity", headers=auth(owner)).json()
    assert len(feed["items"]) == 1
    assert feed["items"][0]["status"] == "merged"
    with factory() as db:
        assert db.get(DevGithubActivity, "pull_request:70").status == "merged"
        assert db.get(DevGithubDelivery, "delivery-a") is not None


def test_push_issue_and_ci_are_factual_only(studio):
    client, factory, owner, viewer = studio
    push = {**ROOT, "ref": "refs/heads/feature/abc", "after": SHA,
        "size": 3, "head_commit": {"message": "feat: add probe pipeline",
                                  "timestamp": "2026-11-14T10:00:00Z"},
        "pusher": {"name": "Hu-py"}}
    issue = {**ROOT, "action": "opened", "issue": {
        "number": 24, "title": "source registry review", "state": "open",
        "updated_at": "2026-11-14T10:00:00Z"}}
    assert send(client, "push", push, "push-a").status_code == 200
    assert send(client, "issues", issue, "issue-a").status_code == 200
    assert send(client, "workflow_run", run(), "run-a").status_code == 200
    result = client.get("/api/devstudio/github/activity", headers=auth(viewer))
    assert result.status_code == 200
    feed = result.json()
    assert len(feed["items"]) == 3
    assert {row["kind"] for row in feed["items"]} == {"push", "issue", "workflow_run"}
    assert all(row["url"].startswith("https://github.com/Hu-py/research-opportunity-workbench/") for row in feed["items"])
    with factory() as db:
        from backend.devstudio import DevEvaluation, DevExperiment, DevChange
        assert not db.query(DevEvaluation).count()
        assert not db.query(DevExperiment).count()
        assert not db.query(DevChange).count()


def test_ci_signal_upgrades_only_manually_linked_run_not_science(studio):
    client, factory, owner, _viewer = studio
    assert send(client, "workflow_run", run(), "ci-initial").status_code == 200
    exp = client.post("/api/devstudio/experiments", headers=auth(owner), json={
        "module_id": "SIGNAL_L1", "title": "Child health A/B/C probe",
        "hypothesis": "Test real three-source bibliographic retrieval and source evidence.",
        "baseline": "Offline fixed metadata", "input_snapshot_ref": "https://github.com/Hu-py/research-opportunity-workbench/pull/70",
    })
    assert exp.status_code == 201, exp.text
    exp_id = exp.json()["id"]
    url = "https://github.com/" + REPO + "/actions/runs/43608073111"
    added = client.post("/api/devstudio/experiments/" + exp_id + "/runs", headers=auth(owner),
                        json={"kind": "github_actions", "external_url": url, "code_sha": SHA})
    assert added.status_code == 201, added.text
    run_id = added.json()["id"]
    assert added.json()["status"] == "ci_success"
    assert send(client, "workflow_run",
                run(conclusion="failure", updated="2026-11-14T12:00:00Z"),
                "ci-new").status_code == 200
    entries = client.get("/api/devstudio/experiments/" + exp_id + "/runs", headers=auth(owner)).json()["items"]
    assert entries[0]["status"] == "ci_failure"
    assert client.get("/api/devstudio/runs/" + run_id + "/evaluations", headers=auth(owner)).json()["items"] == []
    assert exp.json()["status"] == "planned"
    with factory() as db:
        from backend.devstudio import DevEvaluation, DevDecision
        assert not db.query(DevEvaluation).count()
        assert not db.query(DevDecision).count()
