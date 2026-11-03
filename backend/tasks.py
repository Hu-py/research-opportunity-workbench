"""Durable task records shared by FastAPI and the independent worker."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text, select, update
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base

def utc_now():
    return datetime.now(timezone.utc)

class ResearchTask(Base):
    __tablename__ = "research_tasks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    query: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    events_json: Mapped[str] = mapped_column(Text, default="[]")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

def enqueue(db, kind: str, query: str = "") -> ResearchTask:
    if kind not in ("explore", "sync", "weekly"):
        raise ValueError("Unknown task kind")
    task = ResearchTask(id=str(uuid.uuid4()), kind=kind, query=query.strip())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def event(db, task: ResearchTask, step: str, detail: str):
    log = json.loads(task.events_json or "[]")
    log.append({"at": utc_now().isoformat(), "step": step, "detail": detail[:600]})
    task.events_json = json.dumps(log[-70:], ensure_ascii=False)
    task.updated_at = utc_now()
    db.commit()

def claim(db, task_id: str) -> bool:
    result = db.execute(
        update(ResearchTask)
        .where(ResearchTask.id == task_id, ResearchTask.status == "queued")
        .values(status="running", updated_at=utc_now())
    )
    db.commit()
    return bool(result.rowcount)

def next_queued(db):
    task_id = db.scalar(select(ResearchTask.id).where(ResearchTask.status == "queued")
                        .order_by(ResearchTask.created_at.asc()).limit(1))
    return task_id if task_id and claim(db, task_id) else None

def as_dict(task: ResearchTask) -> dict:
    return {
        "id":task.id, "kind":task.kind, "query":task.query,
        "status":task.status, "events":json.loads(task.events_json or "[]"),
        "result":json.loads(task.result_json or "{}"), "error":task.error,
        "created_at":task.created_at.isoformat() if task.created_at else None,
        "updated_at":task.updated_at.isoformat() if task.updated_at else None,
    }
