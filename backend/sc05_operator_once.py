"""Isolated, one-shot SC05 operator for a user-delegated staging experiment.

This is NOT a public API endpoint or a general auth bypass. It can operate
only in the preexisting disposable Development Studio test database/schema.
It requires a Render-control-plane environment instruction, preserves the
existing Owner's attribution and auditable cost limits, and never reads or
prints credentials. A paid request ID may execute only once.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
from urllib.parse import urlsplit

from sqlalchemy import select, text

from backend.sc05_eval_api import (
    SC05Case, SC05Run, check_fact_type_resume,
    eligible_unstarted_gate_migration, execute, load, now,
    pipeline_sha,
)
from backend.team import AuditEntry, TeamMember, add_audit
from research_workbench.core import session_factory

SCHEMA = "atlas_devstudio_e2e_20261114"
DB_NAME = "research_atlas_test_db"
KNOWN_SOURCE = "f8138694727ee27d4e399533311364eb137250d66b62d4b0f16d47d4c781a181"
PAIRS = {
    "sc05pair_c6a7665198a643e885e5f4fd699d",
    "sc05pair_335281590c6d4d5f8fb5025de97a",
}
ACTIONS = {"inspect", "run"}
MAX_EXISTING_CALLS_PER_ARM = 40


def _guard():
    url = os.getenv("DATABASE_URL", "")
    if urlsplit(url).path.lstrip("/") != DB_NAME:
        raise RuntimeError("Refusing operator command: database allowlist mismatch")
    if os.getenv("PGOPTIONS") != "-c search_path=" + SCHEMA:
        raise RuntimeError("Refusing operator command: isolated schema not active")
    if os.getenv("DEVSTUDIO_E2E_ISOLATED") != "1":
        raise RuntimeError("Refusing operator command: isolation flag missing")
    if os.getenv("SC05_EXECUTION_MODE", "background") != "background":
        raise RuntimeError("Refusing operator command: execution mode not background")


def _pair(factory, pair_id):
    with factory() as db:
        rows = db.scalars(select(SC05Run).where(SC05Run.pair_id == pair_id)).all()
        if len(rows) != 2 or {r.variant for r in rows} != {"science_gate_off", "science_gate_on"}:
            raise RuntimeError("SC05 pair missing or malformed")
        if len({r.case_id for r in rows}) != 1:
            raise RuntimeError("SC05 pair source mismatch")
        case = db.get(SC05Case, rows[0].case_id)
        if not case or case.source_sha != KNOWN_SOURCE:
            raise RuntimeError("Source paper SHA256 does not match approved input")
        owner = db.get(TeamMember, rows[0].member_id)
        if not owner or not owner.active or owner.role != "owner":
            raise RuntimeError("Saved pair not owned by an active Owner")
        if any(r.member_id != owner.id for r in rows):
            raise RuntimeError("Saved pair member mismatch")
        return {r.variant: r.id for r in rows}


def _inspect(factory, run_id):
    with factory() as db:
        row = db.get(SC05Run, run_id)
        doc = db.get(SC05Case, row.case_id)
        if row.calls > MAX_EXISTING_CALLS_PER_ARM:
            raise RuntimeError("Saved model call count exceeds operator cap")
        checkpoints = load(row.checkpoints_json, [])
        if not isinstance(checkpoints, list):
            raise RuntimeError("Saved checkpoint array is invalid")
        result = {"status": row.status, "calls": row.calls,
                  "checkpoints": len(checkpoints), "variant": row.variant,
                  "stage": row.stage,
                  "error": (row.error or "")[:180],
                  "sha_is_current": row.pipeline_sha == pipeline_sha()}
        if row.status == "failed":
            if row.pipeline_sha == pipeline_sha():
                # Even same-version checkpoints must be source verified.
                # Quote-only legacy failures may be revalidated through the
                # exact-prompt preflight, without trusting the UI's ready flag.
                result["eligible"] = False
                result["reason"] = "same-version failure requires explicit diagnosis"
            else:
                try:
                    if row.error == "Invalid diagnosis classification":
                        from backend.sc05_replay import verify_diagnosis_prefix
                        repair = verify_diagnosis_prefix(row, doc)
                        result["verified_cached_stages"] = repair["cached_stages"]
                        result["missing_confidences"] = repair["missing_confidences"]
                        result["inference_classes"] = repair["inference_classes"]
                        result["next_stage"] = repair["next_stage"]
                    else:
                        repair = check_fact_type_resume(row, doc)
                        result["verified_facts"] = repair["facts"]
                        result["rejected_quotes"] = repair.get("rejected_quotes", 0)
                    result["prompt_matches"] = True
                except Exception as exc:
                    result["eligible"] = False
                    result["reason"] = type(exc).__name__ + ": " + str(exc)[:100]
                else:
                    result["eligible"] = True
        elif row.status == "prepared":
            result["eligible"] = row.calls == 0 and not checkpoints
        elif row.status == "completed":
            result["eligible"] = True
        else:
            result["eligible"] = False
            result["reason"] = "another process is already working"
        return result


def _claim_one_time(factory, pair_id, request_id):
    target = pair_id + ":" + request_id
    with factory() as db:
        rows = db.scalars(select(SC05Run).where(SC05Run.pair_id == pair_id)
                          .order_by(SC05Run.id).with_for_update()).all()
        if len(rows) != 2:
            raise RuntimeError("SC05 pair altered during operator preflight")
        owner_id = rows[0].member_id
        previous = db.scalars(select(AuditEntry).where(
            AuditEntry.action == "sc05.operator_authorized",
            AuditEntry.target == target,
        ).limit(1)).first()
        if previous:
            print("SC05 OPERATOR: duplicate one-shot request refused",flush=True)
            return False
        if any(x.status in ("queued", "claimed", "running") for x in rows):
            raise RuntimeError("An active SC05 run already exists")
        add_audit(db, "sc05.operator_authorized", owner_id, target,
                  "User-delegated isolated experiment, source_sha=" + KNOWN_SOURCE[:16])
        db.commit()
    return True


def _execute_arm(factory, run_id):
    with factory() as db:
        row = db.get(SC05Run, run_id)
        if row.status == "completed":
            return
        if row.status not in ("failed", "prepared"):
            raise RuntimeError("Unrecognized SC05 run state")
        doc = db.get(SC05Case, row.case_id)
        current = pipeline_sha()
        if row.pipeline_sha != current:
            if eligible_unstarted_gate_migration(db, row, doc, current):
                row.pipeline_sha = current
            else:
                if row.error == "Invalid diagnosis classification":
                    from backend.sc05_replay import verify_diagnosis_prefix
                    verify_diagnosis_prefix(row, doc)
                else:
                    check_fact_type_resume(row, doc)
                row.pipeline_sha = current
        if row.variant == "science_gate_on" and not doc.shared_evidence_json:
            raise RuntimeError("Frozen A evidence missing; B cannot start")
        if row.calls > MAX_EXISTING_CALLS_PER_ARM:
            raise RuntimeError("SC05 call cap exceeded")
        row.status = "queued"
        row.error = ""
        row.updated_at = now()
        add_audit(db, "sc05.operator_started", row.member_id, row.id,
                  "resuming_saved_checkpoints=True")
        db.commit()
    # Calls existing approved pipeline and daily token/call budgets.
    execute(factory, run_id)
    with factory() as db:
        row = db.get(SC05Run, run_id)
        if row.status != "completed":
            raise RuntimeError("SC05 arm ended without completed report; subsequent arms blocked")


def run_once():
    action = os.getenv("SC05_OPERATOR_ACTION", "").strip().lower()
    if action not in ACTIONS:
        return
    try:
        _guard()
        pair_id = os.getenv("SC05_OPERATOR_PAIR_ID", "").strip()
        if pair_id not in PAIRS:
            raise RuntimeError("Not an allowlisted SC05 published-paper pair")
        request_id = os.getenv("SC05_OPERATOR_REQUEST_ID", "").strip()
        if not re.fullmatch(r"sc05once_[a-z0-9]{8,40}", request_id):
            raise RuntimeError("Missing valid one-shot request identifier")
        factory = session_factory()
        ids = _pair(factory, pair_id)
        preflight = {variant: _inspect(factory, run_id) for variant,run_id in ids.items()}
        print("SC05 OPERATOR PREFLIGHT:",preflight,flush=True)
        if action == "inspect":
            print("SC05 OPERATOR: read-only inspection complete; paid calls=0",flush=True)
            return
        if os.getenv("SC05_OPERATOR_PAID_APPROVAL") != pair_id + ":RUN_ONCE":
            raise RuntimeError("Paid model execution not explicitly authorized by Render operator")
        if preflight["science_gate_off"]["status"] != "completed" and not preflight["science_gate_off"].get("eligible"):
            raise RuntimeError("Baseline saved checkpoint is unsafe; no additional paid calls")
        if not _claim_one_time(factory, pair_id, request_id):
            return
        _execute_arm(factory, ids["science_gate_off"])
        _execute_arm(factory, ids["science_gate_on"])
        print("SC05 OPERATOR: both paid A/B arms completed",flush=True)
    except Exception as exc:
        print("SC05 OPERATOR STOP:", type(exc).__name__, str(exc)[:180],flush=True)


def start_if_requested():
    if os.getenv("SC05_OPERATOR_ACTION","").strip().lower() not in ACTIONS:
        return
    # Do not hold the free Web Service's HTTP health check hostage.
    threading.Thread(target=run_once, name="isolated-sc05-once", daemon=True).start()
