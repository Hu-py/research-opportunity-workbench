"""Isolated, DB-backed SC05 worker for delegated ChatGPT experiments.

In production, an independent paid Worker can call execute_once(factory).
For no-fixed-worker-cost staging, an opt-in thread in the existing Render web
process consumes only MCP-authorized rows. Every claim is committed BEFORE
calling the provider. Ambiguous/in-flight jobs are never stolen or retried
automatically, because the provider may have already charged the account.

The synthetic probe is strictly separate from SC05Run and calls NO model.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from research_workbench.core import Base
from backend.sc05_eval_api import SC05Run, execute, now


class SC05DelegatedAuthorization(Base):
    __tablename__ = "sc05_delegated_worker_authorizations"
    run_id: Mapped[str] = mapped_column(
        String(55), ForeignKey("sc05_runs.id"), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(24), default="approved")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class SC05WorkerProbe(Base):
    __tablename__ = "sc05_worker_probes"
    id: Mapped[str] = mapped_column(String(75), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


def flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("true", "1", "yes")


def require_postgres(factory):
    with factory() as db:
        if db.get_bind().dialect.name != "postgresql":
            raise RuntimeError("SC05 durable worker requires PostgreSQL")


def queue_smoke_probe(factory, probe_id: str) -> bool:
    """Idempotent synthetic queue item for LIVE Render verification; no LLM."""
    if not re.fullmatch(r"sc05probe_[a-zA-Z0-9_-]{8,60}", probe_id):
        raise ValueError("Invalid isolated SC05 worker probe ID")
    require_postgres(factory)
    with factory() as db:
        if db.get(SC05WorkerProbe, probe_id):
            return False
        db.add(SC05WorkerProbe(id=probe_id, status="queued"))
        db.commit()
    return True


def run_openalex_probe_once(factory, probe_id: str, *, require_pg: bool = True) -> str:
    """One explicitly configured, bounded OpenAlex probe with a durable no-retry marker.

    This tests external academic metadata retrieval only, never DeepSeek.
    A committed 'started' row prevents duplicate API quota use after a crash.
    """
    import httpx
    from sqlalchemy.exc import IntegrityError
    from research_workbench.core import query_openalex

    if not re.fullmatch(r"sc05probe_openalex_[a-zA-Z0-9_-]{6,45}", probe_id):
        raise ValueError("Invalid OpenAlex one-shot probe identifier")
    if require_pg:
        require_postgres(factory)
    with factory() as db:
        if db.get(SC05WorkerProbe, probe_id):
            return "already_recorded"
        db.add(SC05WorkerProbe(id=probe_id, status="openalex_started"))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return "already_recorded"

    try:
        works = query_openalex("urban transit resilience", "2020-01-01", limit=2)
        if not isinstance(works, list):
            raise ValueError("Invalid OpenAlex results type")
        valid = sum(
            1 for row in works
            if isinstance(row, dict) and str(
                row.get("title") or row.get("display_name") or "").strip()
        )
        status = "openalex_ready_" + str(min(valid, 2)) if valid else "openalex_empty"
    except httpx.HTTPStatusError as exc:
        status = "openalex_http_" + str(exc.response.status_code)
    except httpx.TimeoutException:
        status = "openalex_timeout"
    except httpx.TransportError:
        status = "openalex_network"
    except Exception:
        status = "openalex_error"

    with factory() as db:
        probe = db.get(SC05WorkerProbe, probe_id)
        if probe is None or probe.status != "openalex_started":
            return "missing_or_changed"
        probe.status = status
        probe.completed_at = now()
        db.commit()
    logging.getLogger("uvicorn.error").info(
        "SC05 OPENALEX ONE SHOT: %s; model_calls=0", status)
    return status


def execute_probe_once(factory, *, require_pg=True) -> str | None:
    """Atomic PostgreSQL queue write/read smoke; NEVER calls DeepSeek or R2."""
    if require_pg:
        require_postgres(factory)
    with factory() as db:
        probe = db.scalars(
            select(SC05WorkerProbe)
            .where(SC05WorkerProbe.status == "queued")
            .order_by(SC05WorkerProbe.queued_at, SC05WorkerProbe.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if probe is None:
            return None
        probe.status = "completed"
        probe.completed_at = now()
        probe_id = probe.id
        db.commit()
    return probe_id


def execute_once(factory, *, delegated_only: bool = False,
                 require_pg: bool = True) -> bool:
    """Claim one paid job. Delegated mode never consumes legacy queued runs."""
    if require_pg:
        require_postgres(factory)
    with factory() as db:
        # A previous paid call may be in flight. Never assume it is safe to retry.
        active = db.scalar(
            select(SC05Run.id)
            .where(SC05Run.status.in_(("claimed", "running")))
            .limit(1)
        )
        if active:
            return False
        query = select(SC05Run).where(SC05Run.status == "queued")
        if delegated_only:
            query = query.join(
                SC05DelegatedAuthorization,
                SC05DelegatedAuthorization.run_id == SC05Run.id,
            ).where(SC05DelegatedAuthorization.status == "approved")
        queued = db.scalars(
            query.order_by(SC05Run.created_at, SC05Run.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if queued is None:
            return False
        run_id = queued.id
        queued.status = "claimed"
        queued.stage = "worker_claimed"
        queued.updated_at = now()
        if delegated_only:
            auth = db.get(SC05DelegatedAuthorization, run_id)
            if auth is None or auth.status != "approved" or auth.member_id != queued.member_id:
                raise RuntimeError("SC05 worker authorization mismatch")
            auth.status = "claimed"
        db.commit()
    try:
        execute(factory, run_id, claimed_by_worker=True)
    finally:
        if delegated_only:
            with factory() as db:
                auth = db.get(SC05DelegatedAuthorization, run_id)
                run = db.get(SC05Run, run_id)
                if auth and run:
                    # Do not auto-resume an interrupted run: even an unsuccessful
                    # provider request may have billed for a token.
                    auth.status = (
                        "completed" if run.status == "completed" else "needs_review"
                    )
                    auth.processed_at = now()
                    db.commit()
    return True


def worker_status(factory) -> dict:
    """Credential-free diagnostics; deliberately no user content."""
    with factory() as db:
        probes = db.scalars(
            select(SC05WorkerProbe)
            .order_by(SC05WorkerProbe.queued_at.desc())
            .limit(5)
        ).all()
        approved = db.scalar(
            select(func.count()).select_from(SC05DelegatedAuthorization)
            .where(SC05DelegatedAuthorization.status == "approved")
        )
        active = db.scalar(
            select(func.count()).select_from(SC05Run)
            .where(SC05Run.status.in_(("claimed","running")))
        )
    return {
        "inline_worker_enabled": flag("SC05_INLINE_WORKER_ENABLED"),
        "live_execution_enabled": flag("SC05_INLINE_WORKER_LIVE_ENABLED"),
        "mcp_paid_start_enabled": flag("SC05_MCP_PAID_ENABLED"),
        "execution_mode": os.getenv("SC05_EXECUTION_MODE", "background"),
        "r2_archive_enabled": flag("SC05_R2_ARCHIVE_ENABLED"),
        "approved_queued_dispatches": int(approved or 0),
        "inflight_runs": int(active or 0),
        "recent_probes": [
            {"id":p.id,"status":p.status,
             "completed_at":p.completed_at.isoformat() if p.completed_at else None}
            for p in probes
        ],
    }


def inline_worker_loop(factory, stop_event, *, interval_seconds=3):
    logger = logging.getLogger("uvicorn.error")
    while not stop_event.is_set():
        try:
            probe_id = execute_probe_once(factory)
            if probe_id:
                logger.info("SC05 WORKER PROBE: completed %s; paid_calls=0", probe_id)
            # Never start paid work merely because a historical row was queued.
            if (flag("SC05_INLINE_WORKER_LIVE_ENABLED")
                and flag("SC05_MCP_PAID_ENABLED")
                and os.getenv("SC05_EXECUTION_MODE", "").lower() == "worker"
                and execute_once(factory, delegated_only=True)):
                logger.info("SC05 INLINE WORKER: delegated job ended; inspect database for result")
        except Exception as exc:
            # Fail closed, keep the queued row for inspection. Never print
            # provider payloads, access tokens or database credentials.
            logger.error("SC05 INLINE WORKER ERROR: %s", type(exc).__name__)
        stop_event.wait(interval_seconds)
