"""Durable SC05 queue consumer; runs only when explicitly enabled in Render.

The Owner-authenticated API creates a durable queued row. This consumer
claims it in PostgreSQL and executes the already-approved scientific run.
No session token is needed on the worker: authorization happened at enqueue.
"""
from __future__ import annotations

from sqlalchemy import select

from backend.sc05_eval_api import SC05Run, execute, now


def execute_once(factory) -> bool:
    with factory() as db:
        if db.get_bind().dialect.name != "postgresql":
            raise RuntimeError("SC05 durable worker requires PostgreSQL")
        # Keep a single SC05 run at a time per staging database, preventing
        # the B arm from racing ahead of the common evidence snapshot.
        active = db.scalar(
            select(SC05Run.id)
            .where(SC05Run.status.in_(("claimed", "running")))
            .limit(1)
        )
        if active:
            return False
        queued = db.scalars(
            select(SC05Run)
            .where(SC05Run.status == "queued")
            .order_by(SC05Run.created_at, SC05Run.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if queued is None:
            return False
        run_id = queued.id
        queued.status = "claimed"
        queued.stage = "worker_claimed"
        queued.updated_at = now()
        db.commit()
    execute(factory, run_id, claimed_by_worker=True)
    return True
