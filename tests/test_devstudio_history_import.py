"""Safeguards for idempotent Research Atlas development-history backfill."""
import copy
import json

import pytest
from sqlalchemy import select, func

import backend.api as server  # ensures all ORM tables are registered
import backend.devstudio_history_import as importer
from backend.devstudio import DevExperiment, DevIssue
from backend.experiment_management import ExperimentEvent, ExperimentProfile
from research_workbench.core import session_factory


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    factory = session_factory("sqlite:///" + str(tmp_path / "backfill.db"))
    # Unit tests use a disposable SQLite database; production import will
    # only run inside the strictly guarded PostgreSQL isolated E2E schema.
    monkeypatch.setattr(importer, "_guard", lambda _: None)
    with factory() as connection:
        yield connection


def test_manifest_has_trusted_provenance_and_excludes_scientific_research():
    payload = importer.load_manifest()
    assert payload["snapshot_date"] == "2026-11-14"
    assert len(payload["experiments"]) == 11
    assert len(payload["todos"]) == 14
    assert all(x["status"] != "completed" for x in payload["experiments"])
    assert all(x["primary_evidence"].startswith("https://github.com/") for x in payload["experiments"])
    assert all(x["priority"] in {"P0", "P1", "P2"} for x in payload["todos"])
    assert any("radar_a" == x["scenario"] for x in payload["experiments"])
    assert any("radar_b" == x["scenario"] for x in payload["experiments"])


def test_manifest_rejects_fabricated_success_and_missing_evidence():
    payload = importer.load_manifest()
    bad = copy.deepcopy(payload)
    bad["experiments"][0]["status"] = "completed"
    with pytest.raises(ValueError, match="fabricate"):
        importer.validate_manifest(bad)
    bad = copy.deepcopy(payload)
    bad["experiments"][0]["primary_evidence"] = "https://arbitrary.example/fake"
    with pytest.raises(ValueError, match="evidence"):
        importer.validate_manifest(bad)


def test_first_import_is_additive_and_second_import_does_not_overwrite_owner(db):
    first = importer.import_history(db)
    assert first["result"] == "PASS_IMPORTED"
    assert first["experiments_new"] == 11
    assert first["todos_new"] == 14
    assert first["evidence_events_new"] >= 22
    experiment = db.get(DevExperiment, "exp_hist_v04_261114")
    assert experiment is not None
    assert experiment.status == "review"
    assert experiment.created_by == importer.IMPORT_ACTOR
    profile = db.get(ExperimentProfile, experiment.id)
    assert profile is not None and profile.revision == 1
    milestones = db.scalars(select(ExperimentEvent).where(
        ExperimentEvent.experiment_id == experiment.id,
        ExperimentEvent.action == "historical_evidence"
    )).all()
    assert milestones
    detail = json.loads(milestones[0].details_json)
    assert detail["occurred_on"] == "2026-11-14"
    assert detail["import_kind"] == "retrospective_source_record"

    todo = db.get(DevIssue, "issue_hist_uiqa_261114")
    assert todo is not None
    assert todo.severity == "high"
    assert todo.status == "open"
    assert "exp_hist_v04_261114" in todo.description
    assert "验收标准" in todo.description

    experiment.title = "[Owner edited title; do not overwrite]"
    profile.next_action = "Owner-specific new task"
    db.commit()
    second = importer.import_history(db)
    assert second["result"] == "PASS_EXISTING"
    assert second["experiments_new"] == 0
    assert second["todos_new"] == 0
    assert second["evidence_events_new"] == 0
    assert db.get(DevExperiment, experiment.id).title == "[Owner edited title; do not overwrite]"
    assert db.get(ExperimentProfile, experiment.id).next_action == "Owner-specific new task"
    assert db.scalar(select(func.count()).select_from(DevExperiment).where(
        DevExperiment.id.like("exp_hist_%")
    )) == 11
    assert db.scalar(select(func.count()).select_from(DevIssue).where(
        DevIssue.id.like("issue_hist_%")
    )) == 14


def test_import_guard_rejects_unapproved_database(db, monkeypatch):
    monkeypatch.undo()
    with pytest.raises(RuntimeError, match="approved test DB"):
        importer._guard(db)
