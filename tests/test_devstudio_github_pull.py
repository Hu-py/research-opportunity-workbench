"""Public GitHub read-only sync: cached and independent of webhook secrets."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from backend.devstudio_github_pull import poll, public_snapshot
from backend.devstudio_github_sync import DevGithubActivity
from research_workbench.core import session_factory


def fake_api(path):
    if path.startswith("/commits"):
        return [{"sha": "a"*40, "author": {"login": "Hu-py"}, "commit": {
            "message": "feat: child health probe\nmore details",
            "author": {"name": "Hu-py"},
            "committer": {"date": "2026-11-14T15:01:00Z"}}}]
    if path.startswith("/pulls"):
        return [{"number": 70, "title": "SC01 three-source paper probes",
                 "state": "open", "draft": True, "merged_at": None,
                 "updated_at": "2026-11-14T15:02:00Z",
                 "user": {"login": "Hu-py"},
                 "head": {"ref": "experiment/sc01", "sha": "b"*40}}]
    if path.startswith("/issues"):
        return [{"number": 24, "title": "Review topic coverage", "state": "open",
                 "updated_at": "2026-11-14T15:02:00Z",
                 "user": {"login": "Hu-py"}},
                {"number": 70, "pull_request": {"url": "https://api.github.com/repos/test"},
                 "title": "This is a PR, not an issue"}]
    if path.startswith("/actions/runs"):
        return {"workflow_runs": [{"id": 43608073111, "name": "CI",
                 "status": "completed", "conclusion": "success", "run_number": 1182,
                 "updated_at": "2026-11-14T15:04:00Z",
                 "head_branch": "experiment/sc01", "head_sha": "c"*40,
                 "actor": {"login": "Hu-py"}}]}
    raise AssertionError("Unexpected URL or path")


def test_live_source_shapes_and_scope(monkeypatch):
    import backend.devstudio_github_pull as source
    monkeypatch.setattr(source, "_json", fake_api)
    result = public_snapshot()
    assert len(result) == 4
    assert {x["kind"] for x in result} == {"push", "pull_request", "issue", "workflow_run"}
    assert all(x["url"].startswith("https://github.com/Hu-py/research-opportunity-workbench/") for x in result)
    assert next(x for x in result if x["kind"] == "pull_request")["status"] == "draft"


def test_poll_is_automated_but_rate_limited(monkeypatch, tmp_path):
    import backend.api as api
    import backend.devstudio_github_pull as source
    factory = session_factory("sqlite:///" + str(tmp_path / "github-poll.db"))
    monkeypatch.setenv("DEVSTUDIO_GITHUB_PUBLIC_POLL_ENABLED", "1")
    calls = []
    def snapshot():
        calls.append("one batch")
        return [fake for fake in [
            {"event_key": "pull_request:70", "kind": "pull_request",
             "title": "SC01 child health", "url": "https://github.com/Hu-py/research-opportunity-workbench/pull/70",
             "status": "draft", "actor": "Hu-py", "branch": "experiment/sc01",
             "sha": "d"*40, "detail": "Public repo", "source_updated_at": "2026-11-14T15:00:00Z"}]]
    monkeypatch.setattr(source, "public_snapshot", snapshot)
    with factory() as db:
        first = poll(db)
        second = poll(db)
        assert first["state"] == "updated"
        assert second["state"] == "cached"
        assert len(calls) == 1
        assert db.get(DevGithubActivity, "pull_request:70").status == "draft"
        from backend.devstudio import DevExperiment, DevEvaluation, DevDecision
        assert db.query(DevExperiment).count() == 0
        assert db.query(DevEvaluation).count() == 0
        assert db.query(DevDecision).count() == 0


def test_out_of_order_api_snapshots_do_not_roll_back_merged_status(monkeypatch, tmp_path):
    import backend.api as api
    from backend.devstudio_github_pull import _upsert
    factory = session_factory("sqlite:///" + str(tmp_path / "snapshots.db"))
    base = {"event_key": "pull_request:70", "kind": "pull_request",
            "title": "SC01 child health",
            "url": "https://github.com/Hu-py/research-opportunity-workbench/pull/70",
            "actor": "Hu-py", "branch": "experiment/sc01", "sha": "a"*40, "detail": ""}
    with factory() as db:
        assert _upsert(db, {**base, "status": "merged", "source_updated_at": "2026-11-14T16:00:00Z"})
        db.commit()
        assert not _upsert(db, {**base, "status": "draft", "source_updated_at": "2026-11-14T15:00:00Z"})
        db.commit()
        assert db.get(DevGithubActivity, "pull_request:70").status == "merged"


def test_poll_disabled_by_default(monkeypatch, tmp_path):
    import backend.api as api
    monkeypatch.delenv("DEVSTUDIO_GITHUB_PUBLIC_POLL_ENABLED", raising=False)
    factory = session_factory("sqlite:///" + str(tmp_path / "disabled.db"))
    with factory() as db:
        assert poll(db)["state"] == "disabled"
