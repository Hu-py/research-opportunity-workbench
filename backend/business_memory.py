"""Durable, opt-in Business research-agent bridge.

This adds three tables without altering legacy paper, profile, or agent tables.
The database is authoritative; no ChatGPT conversation memory is required.
External agent access is scoped to public-safe metadata and proposal submission.
Human feedback requires an authenticated team member and cannot be forged via
the agent service token.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel as Schema, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, inspect, select, text as sql_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.research_evidence_export import team_evidence_bundle
from backend.team import add_audit


def utcnow():
    return datetime.now(timezone.utc)


class BusinessAgentRun(Base):
    __tablename__ = "business_agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    context_hash: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(240))
    agent_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="submitted")
    snapshot_json: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessAgentIdea(Base):
    __tablename__ = "business_agent_ideas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("business_agent_runs.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(240))
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessMeetingFeedback(Base):
    __tablename__ = "business_meeting_feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idea_id: Mapped[str] = mapped_column(ForeignKey("business_agent_ideas.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(36), index=True)
    decision: Mapped[str] = mapped_column(String(24))
    novelty: Mapped[int] = mapped_column(Integer)
    feasibility: Mapped[int] = mapped_column(Integer)
    scientific_value: Mapped[int] = mapped_column(Integer)
    testability: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("idea_id", "reviewer_id", name="uq_business_idea_review"),
    )


class Proposal(Schema):
    title: str = Field(min_length=6, max_length=240)
    question: str = Field(min_length=15, max_length=1800)
    novelty_gap: str = Field(min_length=15, max_length=2400)
    method: str = Field(min_length=15, max_length=2400)
    first_experiment: str = Field(min_length=15, max_length=2400)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs: list[str] = Field(min_length=1, max_length=16)
    external_papers_unverified: list[str] = Field(default_factory=list, max_length=15)
    parent_idea_id: str | None = Field(default=None, max_length=36)


class RunSubmission(Schema):
    run_key: str = Field(min_length=12, max_length=120)
    context_hash: str = Field(min_length=64, max_length=64)
    agent_version: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=3, max_length=240)
    proposals: list[Proposal] = Field(min_length=1, max_length=5)
    notes: str = Field(default="", max_length=3000)


class MeetingReview(Schema):
    decision: str = Field(pattern=r"^(adopt|revise|defer|reject)$")
    novelty: int = Field(ge=1, le=5)
    feasibility: int = Field(ge=1, le=5)
    scientific_value: int = Field(ge=1, le=5)
    testability: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=3000)


def _digest(data: object) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _agent_auth(request: Request):
    if os.getenv("BUSINESS_AGENT_BRIDGE_ENABLED", "").strip().lower() != "true":
        raise HTTPException(404, "Agent integration disabled")
    secret = os.getenv("BUSINESS_AGENT_BRIDGE_TOKEN", "").strip()
    actual = request.headers.get("X-Research-Agent-Key", "")
    if len(secret) < 40 or not hmac.compare_digest(actual, secret):
        raise HTTPException(401, "Invalid integration credentials")
    if os.getenv("BUSINESS_AGENT_SHARING_APPROVED", "").strip().lower() != "true":
        raise HTTPException(403, "Team owner has not approved model sharing")


def _context(db: Session):
    """Public-safe team evidence, source registry and prior human decisions."""
    bundle = team_evidence_bundle(db, sharing_approved=True)

    # Promote the official, sanitized research lines to an explicit top-level
    # field so a Workspace Agent does not need to infer their location.
    profile=bundle.get("old_profile") or {}
    research_lines=profile.get("research_lines",[])
    bundle["research_lines"] = [{
        "id":line.get("id",""),"name":line.get("name",""),
        "problem":line.get("problem",""),
        "keywords":line.get("keywords",[])[:12],
    } for line in research_lines[:12] if isinstance(line,dict)] if isinstance(research_lines,list) else []

    # Reuse the same curated source registry as the production evolution engine.
    from backend.research_sources import list_sources
    bundle["academic_source_registry"] = [{
        "name":src["name"],"kind":src["kind"],"domain":src["domain"],
        "rank_label":src["rank_label"]
    } for src in list_sources(db,enabled_only=True)[:25]]

    reviews = db.execute(
        select(BusinessMeetingFeedback, BusinessAgentIdea)
        .join(BusinessAgentIdea, BusinessMeetingFeedback.idea_id == BusinessAgentIdea.id)
        .order_by(BusinessMeetingFeedback.created_at.desc()).limit(12)
    ).all()
    bundle["meeting_history"] = [
        {"idea_id":idea.id, "title":idea.title[:180], "decision":review.decision,
         "scores":{"novelty":review.novelty, "feasibility":review.feasibility,
                   "scientific_value":review.scientific_value,
                   "testability":review.testability},
         "comment":(review.comment or "")[:500]}
        for review, idea in reviews
    ]

    # Include final reviews of the production topic-discovery engine as
    # decision memory, without exposing reviewer identities.
    from backend.research_evolution import EvolutionFeedback, EvolutionRun
    evolution_reviews=db.execute(
        select(EvolutionFeedback,EvolutionRun)
        .join(EvolutionRun,EvolutionFeedback.run_id==EvolutionRun.id)
        .order_by(EvolutionFeedback.created_at.desc()).limit(12)
    ).all()
    bundle["recent_evolution_feedback"] = [{
        "run_id":run.id,"line_id":run.line_id,"decision":review.decision,
        "scores":{"novelty":review.novelty,"feasibility":review.feasibility,
                  "scientific_value":review.scientific_value,
                  "testability":review.testability},
        "comment":(review.comment or "")[:500],
        "created_at":review.created_at.isoformat() if review.created_at else None,
    } for review,run in evolution_reviews]
    bundle["memory_schema"] = "business_agent_v2"
    packed=json.dumps(bundle,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    if len(packed)>72_000:
        raise ValueError("Business Agent context exceeds the safe 72 KB response budget")
    return bundle


def _refs(bundle):
    return (
        {"team_achievements:" + x["id"] for x in bundle["achievements"]}
        | {"cusp_datasets:" + x["id"] for x in bundle["datasets"]}
        | {"papers:" + x["id"] for x in bundle["external_papers"]}
    )


def _run_view(db: Session, row: BusinessAgentRun):
    ideas = db.scalars(select(BusinessAgentIdea)
                       .where(BusinessAgentIdea.run_id == row.id)
                       .order_by(BusinessAgentIdea.created_at, BusinessAgentIdea.id)).all()
    return {
        "run_id": row.id, "run_key": row.run_key, "status": row.status,
        "topic": row.topic, "agent_version": row.agent_version,
        "context_hash": row.context_hash,
        "created_at": row.created_at.isoformat(),
        "ideas": [{
            "id":idea.id, "parent_id":idea.parent_id, "version":idea.version,
            **json.loads(idea.payload_json)
        } for idea in ideas]
    }




def persist_run(db: Session, payload: RunSubmission) -> dict:
    """Shared validation and persistence used by HTTP and future OAuth MCP.

    No agent auth belongs here: transport adapters must authorize first.
    """
    body = payload.model_dump()
    request_hash = _digest(body)
    previous = db.scalar(select(BusinessAgentRun).where(
        BusinessAgentRun.run_key == payload.run_key))
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(409, "The run key was already used for different content")
        return _run_view(db, previous)
    try:
        context_data = _context(db)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if payload.context_hash != _digest(context_data):
        raise HTTPException(409, "Research context changed; retrieve it again")
    allowed = _refs(context_data)
    for idea in payload.proposals:
        if any(ref not in allowed for ref in idea.evidence_refs):
            raise HTTPException(422, "A proposal cites a non-existent or unapproved evidence ID")
        if len(set(idea.evidence_refs)) != len(idea.evidence_refs):
            raise HTTPException(422, "Duplicate evidence IDs")
    run = BusinessAgentRun(
        id=str(uuid.uuid4()), run_key=payload.run_key, request_hash=request_hash,
        context_hash=payload.context_hash, topic=payload.topic,
        agent_version=payload.agent_version,
        snapshot_json=json.dumps(context_data, ensure_ascii=False),
        notes=payload.notes,
    )
    db.add(run)
    for p in payload.proposals:
        version = 1
        if p.parent_idea_id:
            parent = db.get(BusinessAgentIdea, p.parent_idea_id)
            if parent is None:
                db.rollback()
                raise HTTPException(422, "Parent proposal does not exist")
            version = parent.version + 1
        db.add(BusinessAgentIdea(
            id=str(uuid.uuid4()), run_id=run.id, parent_id=p.parent_idea_id,
            version=version, title=p.title,
            payload_json=json.dumps(p.model_dump(), ensure_ascii=False),
        ))
    add_audit(db, "business_agent.submitted", None, run.id,
              "external_agent; ideas=" + str(len(payload.proposals)))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Duplicate run key; retry with the same payload") from exc
    return _run_view(db, run)

def secure_new_tables(db: Session) -> None:
    """Enforce table-level RLS and prevent direct Supabase Data API access.

    New tables are strictly server-side; no client-side SELECT policies exist.
    The Supabase project's public schema is already closed to API roles.
    """
    if db.get_bind().dialect.name!="postgresql":
        return
    protected=("business_agent_runs","business_agent_ideas","business_meeting_feedback")
    allowed=set(inspect(db.get_bind()).get_table_names(schema="public"))
    if not set(protected).issubset(allowed):
        raise RuntimeError("New Business memory tables are not present")
    for name in protected:
        db.execute(sql_text("ALTER TABLE public."+name+" ENABLE ROW LEVEL SECURITY"))
        db.execute(sql_text("REVOKE ALL ON TABLE public."+name+" FROM PUBLIC"))
    for role in ("anon","authenticated","service_role"):
        present=db.execute(sql_text(
            "SELECT count(*) FROM pg_roles WHERE rolname=:r"),{"r":role}).scalar_one()
        if present:
            for name in protected:
                # Role and table identifiers are fixed literals from this module.
                db.execute(sql_text("REVOKE ALL ON TABLE public."+name+" FROM "+role))
    db.commit()


def mount(app, *, get_db, require_actor, require_editor, require_admin):
    router = APIRouter()

    @router.get("/api/business-agent/context")
    def context(request: Request, db: Session = Depends(get_db)):
        _agent_auth(request)
        try:
            data = _context(db)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return JSONResponse({"context_hash": _digest(data), "context": data},
                            headers={"Cache-Control": "no-store, private"})

    @router.post("/api/business-agent/runs", status_code=201)
    def submit(request: Request, payload: RunSubmission, db: Session = Depends(get_db)):
        _agent_auth(request)
        return persist_run(db,payload)

    @router.get("/api/business-agent/agent-runs")
    def agent_run_history(request: Request, db: Session = Depends(get_db)):
        """Agent-scoped, authenticated read-back. Never grants human feedback writes."""
        _agent_auth(request)
        rows=db.scalars(select(BusinessAgentRun)
                        .order_by(BusinessAgentRun.created_at.desc(),
                                  BusinessAgentRun.id.desc()).limit(20)).all()
        return JSONResponse({"items":[_run_view(db,row) for row in rows]},
                            headers={"Cache-Control":"no-store, private"})

    @router.get("/api/business-agent/agent-runs/{run_id}")
    def agent_run_detail(run_id: str, request: Request,
                         db: Session = Depends(get_db)):
        _agent_auth(request)
        try:
            uuid.UUID(run_id)
        except ValueError:
            raise HTTPException(422,"Invalid run identifier") from None
        row=db.get(BusinessAgentRun,run_id)
        if row is None:
            raise HTTPException(404,"Research run not found")
        return JSONResponse(_run_view(db,row),
                            headers={"Cache-Control":"no-store, private"})

    @router.get("/api/business-agent/runs", dependencies=[Depends(require_actor)])
    def list_runs(db: Session = Depends(get_db)):
        runs = db.scalars(select(BusinessAgentRun).order_by(
            BusinessAgentRun.created_at.desc()).limit(30)).all()
        return {"items": [_run_view(db, row) for row in runs]}

    @router.get("/api/business-agent/runs/{run_id}", dependencies=[Depends(require_actor)])
    def run_detail(run_id: str, db: Session = Depends(get_db)):
        row = db.get(BusinessAgentRun, run_id)
        if row is None:
            raise HTTPException(404, "Run not found")
        return _run_view(db, row)

    @router.post("/api/business-agent/ideas/{idea_id}/feedback",
                 dependencies=[Depends(require_editor)])
    def review(idea_id: str, payload: MeetingReview,
               actor=Depends(require_editor), db: Session = Depends(get_db)):
        # Never accept 'human' feedback from the integration key.
        if actor is None:
            raise HTTPException(403, "An identified team member is required")
        idea = db.get(BusinessAgentIdea, idea_id)
        if idea is None:
            raise HTTPException(404, "Proposal not found")
        existing = db.scalar(select(BusinessMeetingFeedback).where(
            BusinessMeetingFeedback.idea_id == idea_id,
            BusinessMeetingFeedback.reviewer_id == actor.id))
        if existing is not None:
            raise HTTPException(409, "This reviewer has already reviewed this version")
        item = BusinessMeetingFeedback(
            id=str(uuid.uuid4()), idea_id=idea_id, reviewer_id=actor.id,
            **payload.model_dump())
        db.add(item)
        add_audit(db, "business_agent.feedback", actor.id, idea_id,
                  "decision=" + payload.decision)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Duplicate feedback") from exc
        return {"feedback_id": item.id, "idea_id": idea_id,
                "decision": payload.decision, "stored": True}

    @router.get("/api/business-agent/storage-audit",
                dependencies=[Depends(require_admin)])
    def storage_audit(db: Session = Depends(get_db)):
        # Counts only. No credentials, user names, dataset names, row contents.
        expected = ["profiles", "team_profile_revisions", "team_achievements",
                    "cusp_datasets", "papers", "ideas",
                    "research_evolution_runs", "research_evolution_feedback",
                    "business_agent_runs", "business_agent_ideas",
                    "business_meeting_feedback"]
        available = set(inspect(db.get_bind()).get_table_names())
        counts = {}
        for cls in (BusinessAgentRun, BusinessAgentIdea, BusinessMeetingFeedback):
            if cls.__tablename__ in available:
                counts[cls.__tablename__] = db.scalar(
                    select(func.count()).select_from(cls))
        return {"dialect": db.get_bind().dialect.name,
                "present_tables": [x for x in expected if x in available],
                "missing_tables": [x for x in expected if x not in available],
                "new_record_counts": counts,
                "old_tables_mutated": False,
                "live_database_connection": True}

    app.include_router(router)
