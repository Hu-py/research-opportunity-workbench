"""One-time, idempotent, evidence-labeled Research Atlas development-history import.

NOT a general production importer. Called only by the isolated E2E start script
after its DB-name/schema verification. Never alters pre-existing experiment data,
sessions, passwords, or account roles. Historical milestones retain their
original occurrence dates separately from the *actual* import timestamp.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.devstudio import DevExperiment, DevIssue, MODULE_IDS
from backend.experiment_management import (
    ExperimentEvent, ExperimentProfile, OBJECTIVES, SCENARIOS, OBJECTS, STATUSES,
)
from backend.team import add_audit

MANIFEST = Path(__file__).resolve().parent / "fixtures" / "research_atlas_history_20261114.json"
DATABASE = "research_atlas_test_db"
SCHEMA = "atlas_devstudio_e2e_20261114"
IMPORT_ACTOR = "system_backfill_20261114"


def load_manifest(path: Path = MANIFEST) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(data)
    return data


def validate_manifest(data: dict) -> None:
    if data.get("schema_version") != "devstudio-history-snapshot-v1":
        raise ValueError("Unexpected history manifest format")
    if data.get("snapshot_date") != "2026-11-14":
        raise ValueError("Unexpected history snapshot date")
    if data.get("scope", "").find("independent paper and simulation studies excluded") < 0:
        raise ValueError("Import must exclude independent scientific papers")
    ids = set()
    for entry in data["experiments"]:
        if not entry["id"].startswith("exp_hist_") or len(entry["id"]) > 32:
            raise ValueError("Only prefixed and bounded history experiment IDs allowed")
        if entry["id"] in ids:
            raise ValueError("Duplicate experiment ID")
        ids.add(entry["id"])
        if entry["module_id"] not in MODULE_IDS:
            raise ValueError("Invalid research module")
        for key, values in (("objective", OBJECTIVES), ("scenario", SCENARIOS),
                            ("change_object", OBJECTS), ("status", STATUSES)):
            if entry[key] not in values:
                raise ValueError("Invalid experiment "+key)
        if entry["status"] == "completed":
            raise ValueError("Historical import must not fabricate reviewed experiments")
        if not entry["primary_evidence"].startswith("https://github.com/Hu-py/research-opportunity-workbench/"):
            raise ValueError("Missing authoritative GitHub evidence")
        if not 10 <= len(entry["hypothesis"]) <= 4000:
            raise ValueError("Invalid hypothesis")
        if len(entry["title"]) > 200 or len(entry["metrics"]) > 20:
            raise ValueError("Experiment exceeds model limits")
        for field in ("method", "expected_result", "conclusion", "next_action"):
            if len(entry[field]) > (2000 if field == "next_action" else 3000):
                raise ValueError("Experiment field too long: " + field)
        for m in entry["milestones"]:
            datetime.fromisoformat(m["occurred_on"])
            if not m["evidence"].startswith("https://github.com/Hu-py/research-opportunity-workbench/"):
                raise ValueError("Invalid milestone evidence")

    todo_ids = set()
    for t in data["todos"]:
        if not t["id"].startswith("issue_hist_") or len(t["id"]) > 32:
            raise ValueError("Only bounded historic issue IDs allowed")
        if t["id"] in todo_ids:
            raise ValueError("Duplicate todo ID")
        todo_ids.add(t["id"])
        if t["module_id"] not in MODULE_IDS or t["experiment_id"] not in ids:
            raise ValueError("Invalid todo module/experiment linkage")
        if t["priority"] not in ("P0", "P1", "P2"):
            raise ValueError("Invalid task priority")
        if len(t["title"]) > 190:
            raise ValueError("Todo title too long")
        if not t["evidence"].startswith("https://github.com/Hu-py/research-opportunity-workbench/"):
            raise ValueError("Todo lacks GitHub evidence")


def _guard(db: Session) -> None:
    url = os.getenv("DATABASE_URL", "")
    if urlsplit(url).path.lstrip("/") != DATABASE:
        raise RuntimeError("Refusing history import outside the approved test DB")
    if os.getenv("DEVSTUDIO_E2E_ISOLATED") != "1" or os.getenv("DEVSTUDIO_E2E_IMPORT_HISTORY") != "1":
        raise RuntimeError("History import disabled")
    if db.bind.dialect.name != "postgresql":
        raise RuntimeError("History import requires isolated PostgreSQL")
    if db.execute(text("SELECT current_schema()")).scalar_one() != SCHEMA:
        raise RuntimeError("History import refuses a nonisolated schema")
    if os.getenv("TEAM_AUTH_ENABLED", "").lower() not in ("1", "true"):
        raise RuntimeError("History import requires team authentication")


def import_history(db: Session) -> dict:
    """Insert only missing fixed-ID rows; never edit historical or user rows."""
    _guard(db)
    data = load_manifest()
    created_exp = 0
    created_issues = 0
    created_events = 0
    for e in data["experiments"]:
        if db.get(DevExperiment, e["id"]) is not None:
            # Existing record (including an Owner-edited one) is authoritative.
            continue
        base = DevExperiment(
            id=e["id"], module_id=e["module_id"], title=e["title"],
            hypothesis=e["hypothesis"], baseline=e["baseline"],
            input_snapshot_ref=e["primary_evidence"],
            metrics_json=json.dumps(e["metrics"], ensure_ascii=False),
            status=e["status"], created_by=IMPORT_ACTOR,
        )
        profile = ExperimentProfile(
            experiment_id=e["id"], objective=e["objective"],
            scenario=e["scenario"], change_object=e["change_object"],
            method=e["method"], expected_result=e["expected_result"],
            conclusion=e["conclusion"], next_action=e["next_action"],
            revision=1, updated_by=IMPORT_ACTOR,
        )
        db.add(base)
        db.flush()  # parent row must exist before profile's FK
        db.add(profile)
        # The creation time of these events is the time of import, NOT
        # the historical event date embedded in details_json.
        for i, milestone in enumerate(e["milestones"]):
            db.add(ExperimentEvent(
                id="evt_" + e["id"][4:] + "_" + str(i),
                experiment_id=e["id"], revision=0,
                action="historical_evidence",
                details_json=json.dumps({
                    **milestone, "import_kind": "retrospective_source_record",
                    "note": "Historical occurrence date is not the database insertion date",
                }, ensure_ascii=False), actor_id=IMPORT_ACTOR,
            ))
            created_events += 1
        db.add(ExperimentEvent(
            id="evt_" + e["id"][4:] + "_import",
            experiment_id=e["id"], revision=1,
            action="history_snapshot_imported",
            details_json=json.dumps({
                "snapshot_date": data["snapshot_date"],
                "primary_evidence": e["primary_evidence"],
                "status_at_snapshot": e["status"],
                "source_provenance": "curated GitHub records + prior product decisions",
                "is_human_reviewed": False,
                "was_existing_live_experiment": False,
                "note": "Backfilled development history. Not evidence of scientific success.",
            }, ensure_ascii=False), actor_id=IMPORT_ACTOR,
        ))
        created_events += 1
        created_exp += 1
    for t in data["todos"]:
        if db.get(DevIssue, t["id"]) is not None:
            continue
        description = (
            "【2026-11-14 研发待办快照；需 Owner 审核】\n"
            + "优先级：" + t["priority"]
            + "\n关联实验：" + t["experiment_id"]
            + "\n问题/行动：" + t["description"]
            + "\n验收标准：" + t["acceptance"]
            + "\n来源：" + t["evidence"]
        )
        if len(description) > 6000:
            raise ValueError("Issue description too long")
        db.add(DevIssue(
            id=t["id"], module_id=t["module_id"],
            title="[" + t["priority"] + "] " + t["title"],
            description=description,
            severity={"P0": "high", "P1": "medium", "P2": "low"}[t["priority"]],
            status="open", created_by=IMPORT_ACTOR,
        ))
        created_issues += 1
    if created_exp or created_issues:
        add_audit(
            db, "devstudio.history_snapshot_imported", None,
            "history_snapshot_20261114",
            "experiments=" + str(created_exp) + "; issues=" + str(created_issues)
            + "; source=curated_github_history; author=system_backfill",
        )
    db.commit()
    ids = [e["id"] for e in data["experiments"]]
    issue_ids = [t["id"] for t in data["todos"]]
    found_exp = sum(1 for key in ids if db.get(DevExperiment, key) is not None)
    found_issue = sum(1 for key in issue_ids if db.get(DevIssue, key) is not None)
    if found_exp != len(ids) or found_issue != len(issue_ids):
        raise RuntimeError("Post-import persistence verification failed")
    return {
        "result": "PASS_IMPORTED" if created_exp or created_issues else "PASS_EXISTING",
        "schema": SCHEMA,
        "experiments_new": created_exp,
        "experiments_present": found_exp,
        "todos_new": created_issues,
        "todos_present": found_issue,
        "evidence_events_new": created_events,
        "unreviewed_historical_import": True,
    }
