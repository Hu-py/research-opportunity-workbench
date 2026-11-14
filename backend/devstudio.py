"""Research Atlas Development Studio P0: auditable development governance.

A proposal's approval is NOT a production configuration change. The existing
academic source registry and AI workflows are deliberately read-only here.
All write operations require TEAM_AUTH_ENABLED and a real member session.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.team import TeamMember, add_audit
from backend.research_sources import list_sources


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex[:20]


def encode(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def decode(payload: str | None) -> Any:
    return json.loads(payload or "{}")


MODULES = [
    {"id": "DISCOVERY", "name": "文献发现与来源核验", "scope": "共用核心能力"},
    {"id": "PAPER_KNOWLEDGE", "name": "论文知识与证据抽取", "scope": "共用核心能力"},
    {"id": "SIGNAL_L1", "name": "跨论文科研信号综合", "scope": "共用核心能力"},
    {"id": "DEEP_READ_L2", "name": "代表论文深读", "scope": "SC01 / SC03"},
    {"id": "IDEA_L3", "name": "方法迁移与研究机会", "scope": "SC03 / 可选 L3"},
    {"id": "TEAM_FIT", "name": "团队能力与数据匹配", "scope": "共用核心能力"},
    {"id": "DELIVERY", "name": "SC01–SC03 交付与反馈", "scope": "使用场景"},
    {"id": "PLATFORM", "name": "平台、权限、模型与任务", "scope": "系统基础"},
]
MODULE_IDS = {item["id"] for item in MODULES}
SOURCE_GROUPS = {"planning_application", "urban_science", "computational_methods"}
GITHUB_ACTION_RE = re.compile(
    r"^https://github\.com/Hu-py/research-opportunity-workbench/actions/runs/\d+/?$"
)


class DevIssue(Base):
    __tablename__ = "devstudio_issues"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    module_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="open")
    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DevChange(Base):
    __tablename__ = "devstudio_changes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    module_id: Mapped[str] = mapped_column(String(40), index=True)
    issue_id: Mapped[str] = mapped_column(String(32), default="")
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    proposed_json: Mapped[str] = mapped_column(Text, default="{}")
    risk: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(32), default="submitted", index=True)
    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DevDecision(Base):
    __tablename__ = "devstudio_decisions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    change_id: Mapped[str] = mapped_column(String(32), index=True)
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    reviewer_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DevDocument(Base):
    __tablename__ = "devstudio_documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    module_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40))
    authoritative_url: Mapped[str] = mapped_column(Text)
    revision_ref: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(30), default="indexed_draft")
    owner_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DevExperiment(Base):
    __tablename__ = "devstudio_experiments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    module_id: Mapped[str] = mapped_column(String(40), index=True)
    change_id: Mapped[str] = mapped_column(String(32), default="")
    title: Mapped[str] = mapped_column(String(200))
    hypothesis: Mapped[str] = mapped_column(Text)
    baseline: Mapped[str] = mapped_column(Text, default="")
    input_snapshot_ref: Mapped[str] = mapped_column(Text, default="")
    metrics_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(30), default="planned")
    created_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DevRunRef(Base):
    __tablename__ = "devstudio_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    external_url: Mapped[str] = mapped_column(Text)
    code_sha: Mapped[str] = mapped_column(String(64), default="")
    input_hash: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(30), default="unverified")
    note: Mapped[str] = mapped_column(Text, default="")
    registered_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DevEvaluation(Base):
    __tablename__ = "devstudio_evaluations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    rubric_version: Mapped[str] = mapped_column(String(80))
    scores_json: Mapped[str] = mapped_column(Text, default="{}")
    limitations: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class IssueRequest(BaseModel):
    module_id: str
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=8, max_length=6000)
    severity: Literal["low", "medium", "high"] = "medium"


class ChangeRequest(BaseModel):
    module_id: str
    kind: Literal["source", "document", "workflow", "code", "other"]
    title: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=10, max_length=4000)
    issue_id: str = ""
    proposed: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    reason: str = Field(min_length=8, max_length=3000)


class DocumentRequest(BaseModel):
    module_id: str
    title: str = Field(min_length=3, max_length=200)
    category: Literal["product", "architecture", "data", "evaluation", "decision", "operations"]
    authoritative_url: str = Field(min_length=12, max_length=1600)
    revision_ref: str = Field(default="", max_length=120)


class ExperimentRequest(BaseModel):
    module_id: str
    title: str = Field(min_length=3, max_length=200)
    hypothesis: str = Field(min_length=10, max_length=4000)
    baseline: str = Field(default="", max_length=1500)
    input_snapshot_ref: str = Field(default="", max_length=1600)
    metrics: list[str] = Field(default_factory=list, max_length=20)
    change_id: str = ""


class RunRequest(BaseModel):
    kind: Literal["github_actions", "internal"]
    external_url: str = Field(min_length=10, max_length=1600)
    code_sha: str = Field(default="", max_length=64)
    input_hash: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=1200)


class EvaluationRequest(BaseModel):
    rubric_version: str = Field(min_length=1, max_length=80)
    scores: dict[str, float] = Field(default_factory=dict)
    limitations: str = Field(default="", max_length=2000)


def to_dict(row) -> dict[str, Any]:
    output = {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
    }
    for k, v in list(output.items()):
        if isinstance(v, datetime):
            output[k] = v.isoformat()
        elif k in {"proposed_json", "metrics_json", "scores_json"}:
            output[k.removesuffix("_json")] = decode(v)
            del output[k]
    return output


def validate_module(module: str) -> None:
    if module not in MODULE_IDS:
        raise HTTPException(422, "Unknown research module")


def validate_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, "A normal HTTPS Page or GitHub link is required")
    if parsed.hostname not in {"chatgpt.com", "github.com"}:
        raise HTTPException(422, "Document links must use ChatGPT Page or GitHub")
    return value.strip()


def validate_proposal(data: ChangeRequest) -> None:
    if len(encode(data.proposed)) > 12000:
        raise HTTPException(422, "Proposed changes must be smaller than 12 KB")
    if data.kind == "source":
        if data.module_id != "DISCOVERY":
            raise HTTPException(422, "Source changes belong to DISCOVERY")
        if data.proposed.get("operation") not in {"add", "pause", "reclassify", "update"}:
            raise HTTPException(422, "Source proposals require an operation")
        if not str(data.proposed.get("name") or "").strip():
            raise HTTPException(422, "Source proposals require a source name")
        groups = data.proposed.get("source_groups")
        if not isinstance(groups, list) or not groups or not set(groups) <= SOURCE_GROUPS:
            raise HTTPException(422, "Source proposals require valid A/B/C groups")
    if data.kind == "workflow" and not data.proposed:
        raise HTTPException(422, "Workflow changes require a description of the proposed configuration")


def mount(app, *, get_db, require_actor, require_editor, require_admin, team_auth_enabled):
    router = APIRouter(prefix="/api/devstudio", tags=["Development Studio"])

    def verified_actor(actor: TeamMember | None) -> TeamMember:
        if not team_auth_enabled() or actor is None:
            raise HTTPException(403, "Development Studio requires a team login")
        return actor

    def read(actor: TeamMember | None = Depends(require_actor)) -> TeamMember:
        return verified_actor(actor)

    def write(actor: TeamMember | None = Depends(require_editor)) -> TeamMember:
        return verified_actor(actor)

    def approve(actor: TeamMember | None = Depends(require_admin)) -> TeamMember:
        return verified_actor(actor)

    @router.get("/overview")
    def overview(db: Session = Depends(get_db), actor: TeamMember = Depends(read)):
        return {
            "modules": MODULES,
            "counts": {
                "open_issues": db.scalar(select(func.count()).select_from(DevIssue).where(DevIssue.status == "open")) or 0,
                "pending_changes": db.scalar(select(func.count()).select_from(DevChange).where(DevChange.status == "submitted")) or 0,
                "experiments": db.scalar(select(func.count()).select_from(DevExperiment)) or 0,
                "indexed_documents": db.scalar(select(func.count()).select_from(DevDocument)) or 0,
            },
            "deployment_status": "not_verified",
            "note": "Counts reflect Development Studio records only. CI, science review and production deployment are different evidence states.",
        }

    @router.get("/sources")
    def sources(db: Session = Depends(get_db), actor: TeamMember = Depends(read)):
        entries = list_sources(db)
        proposals = db.scalars(select(DevChange).where(DevChange.kind == "source")
                               .order_by(DevChange.created_at.desc()).limit(150)).all()
        return {
            "legacy_registry": [
                {**row, "atlas_source_groups": [], "atlas_classification_status": "not_migrated"}
                for row in entries
            ],
            "source_proposals": [to_dict(row) for row in proposals],
            "warning": "Legacy direct/method registry is not the new A/B/C source plan. Approved proposals do not change production scanning.",
        }

    @router.get("/issues")
    def issues(db: Session = Depends(get_db), actor: TeamMember = Depends(read)):
        rows = db.scalars(select(DevIssue).order_by(DevIssue.created_at.desc()).limit(250)).all()
        return {"items": [to_dict(row) for row in rows]}

    @router.post("/issues", status_code=201)
    def create_issue(data: IssueRequest, db: Session = Depends(get_db), actor: TeamMember = Depends(write)):
        validate_module(data.module_id)
        row = DevIssue(id=new_id("issue"), module_id=data.module_id, title=data.title,
                       description=data.description, severity=data.severity, created_by=actor.id)
        db.add(row)
        add_audit(db, "devstudio.issue_created", actor.id, row.id, data.title)
        db.commit()
        return to_dict(row)

    @router.get("/changes")
    def changes(db: Session = Depends(get_db), actor: TeamMember = Depends(read)):
        rows = db.scalars(select(DevChange).order_by(DevChange.created_at.desc()).limit(250)).all()
        return {"items": [to_dict(row) for row in rows]}

    @router.post("/changes", status_code=201)
    def create_change(data: ChangeRequest, db: Session = Depends(get_db), actor: TeamMember = Depends(write)):
        validate_module(data.module_id)
        validate_proposal(data)
        if data.issue_id and not db.get(DevIssue, data.issue_id):
            raise HTTPException(422, "Linked issue not found")
        risk = "high" if data.kind in {"workflow", "code"} else "medium" if data.kind == "source" else "low"
        row = DevChange(id=new_id("change"), module_id=data.module_id, issue_id=data.issue_id,
                        kind=data.kind, title=data.title, reason=data.reason,
                        proposed_json=encode(data.proposed), risk=risk, created_by=actor.id)
        db.add(row)
        add_audit(db, "devstudio.change_submitted", actor.id, row.id, data.reason[:180])
        db.commit()
        return to_dict(row)

    @router.get("/changes/{change_id}/decisions")
    def decisions(change_id: str, db: Session = Depends(get_db), actor: TeamMember = Depends(read)):
        if not db.get(DevChange, change_id):
            raise HTTPException(404, "Change not found")
        rows = db.scalars(select(DevDecision).where(DevDecision.change_id == change_id)
                          .order_by(DevDecision.created_at.desc())).all()
        return {"items": [to_dict(row) for row in rows]}

    @router.post("/changes/{change_id}/decisions", status_code=201)
    def decide(change_id: str, data: DecisionRequest, db: Session = Depends(get_db),
               actor: TeamMember = Depends(approve)):
        change = db.get(DevChange, change_id)
        if not change:
            raise HTTPException(404, "Change not found")
        if change.status != "submitted":
            raise HTTPException(409, "Change has already received a decision")
        if change.created_by == actor.id:
            raise HTTPException(403, "The requester cannot approve or decide their own change")
        state = {"approve": "approved_pending_release", "reject": "rejected",
                 "request_changes": "needs_revision"}[data.decision]
        decision = DevDecision(id=new_id("decision"), change_id=change.id,
                               decision=data.decision, reason=data.reason, reviewer_id=actor.id)
        change.status = state
        db.add(decision)
        add_audit(db, "devstudio.change_reviewed", actor.id, change.id,
                  data.decision + ": " + data.reason[:160])
        db.commit()
        return {"change": to_dict(change), "decision": to_dict(decision),
                "applied_to_production": False}

    @router.get("/documents")
    def documents(db: Session = Depends(get_db), actor: TeamMember = Depends(read)):
        rows = db.scalars(select(DevDocument).order_by(DevDocument.created_at.desc()).limit(250)).all()
        return {"items": [to_dict(row) for row in rows]}

    @router.post("/documents", status_code=201)
    def create_document(data: DocumentRequest, db: Session = Depends(get_db),
                        actor: TeamMember = Depends(write)):
        validate_module(data.module_id)
        url = validate_url(data.authoritative_url)
        row = DevDocument(id=new_id("doc"), module_id=data.module_id, title=data.title,
                          category=data.category, authoritative_url=url,
                          revision_ref=data.revision_ref, owner_id=actor.id)
        db.add(row)
        add_audit(db, "devstudio.document_indexed", actor.id, row.id, data.title)
        db.commit()
        return to_dict(row)

    @router.get("/experiments")
    def experiments(db: Session = Depends(get_db), actor: TeamMember = Depends(read)):
        rows = db.scalars(select(DevExperiment)
                          .order_by(DevExperiment.created_at.desc()).limit(250)).all()
        return {"items": [to_dict(row) for row in rows]}

    @router.post("/experiments", status_code=201)
    def create_experiment(data: ExperimentRequest, db: Session = Depends(get_db),
                          actor: TeamMember = Depends(write)):
        validate_module(data.module_id)
        if data.change_id and not db.get(DevChange, data.change_id):
            raise HTTPException(422, "Linked change not found")
        row = DevExperiment(id=new_id("exp"), module_id=data.module_id, title=data.title,
                            hypothesis=data.hypothesis, baseline=data.baseline,
                            change_id=data.change_id, input_snapshot_ref=data.input_snapshot_ref,
                            metrics_json=encode(data.metrics), created_by=actor.id)
        db.add(row)
        add_audit(db, "devstudio.experiment_registered", actor.id, row.id, data.title)
        db.commit()
        return to_dict(row)

    @router.get("/experiments/{experiment_id}/runs")
    def runs(experiment_id: str, db: Session = Depends(get_db),
             actor: TeamMember = Depends(read)):
        if not db.get(DevExperiment, experiment_id):
            raise HTTPException(404, "Experiment not found")
        rows = db.scalars(select(DevRunRef).where(DevRunRef.experiment_id == experiment_id)
                          .order_by(DevRunRef.created_at.desc())).all()
        return {"items": [to_dict(row) for row in rows]}

    @router.post("/experiments/{experiment_id}/runs", status_code=201)
    def create_run(experiment_id: str, data: RunRequest, db: Session = Depends(get_db),
                   actor: TeamMember = Depends(write)):
        if not db.get(DevExperiment, experiment_id):
            raise HTTPException(404, "Experiment not found")
        if data.kind == "github_actions" and not GITHUB_ACTION_RE.fullmatch(data.external_url):
            raise HTTPException(422, "Use a verified-format GitHub Actions Run URL from this repository")
        if data.kind == "internal" and not data.external_url.startswith("/api/tasks/"):
            raise HTTPException(422, "Internal runs must refer to a task resource")
        row = DevRunRef(id=new_id("run"), experiment_id=experiment_id, kind=data.kind,
                        external_url=data.external_url, code_sha=data.code_sha,
                        input_hash=data.input_hash, note=data.note, registered_by=actor.id,
                        status="unverified")
        db.add(row)
        add_audit(db, "devstudio.run_linked", actor.id, row.id, data.external_url[:170])
        db.commit()
        return to_dict(row)

    @router.get("/runs/{run_id}/evaluations")
    def evaluations(run_id: str, db: Session = Depends(get_db),
                    actor: TeamMember = Depends(read)):
        if not db.get(DevRunRef, run_id):
            raise HTTPException(404, "Run not found")
        rows = db.scalars(select(DevEvaluation).where(DevEvaluation.run_id == run_id)
                          .order_by(DevEvaluation.created_at.desc())).all()
        return {"items": [to_dict(row) for row in rows]}

    @router.post("/runs/{run_id}/evaluations", status_code=201)
    def create_evaluation(run_id: str, data: EvaluationRequest, db: Session = Depends(get_db),
                          actor: TeamMember = Depends(write)):
        if not db.get(DevRunRef, run_id):
            raise HTTPException(404, "Run not found")
        if len(data.scores) > 30 or any(len(name) > 100 or not 0 <= score <= 5
                                        for name, score in data.scores.items()):
            raise HTTPException(422, "Scores must contain at most 30 metrics in the range 0..5")
        row = DevEvaluation(id=new_id("eval"), run_id=run_id,
                            rubric_version=data.rubric_version,
                            scores_json=encode(data.scores), limitations=data.limitations,
                            reviewer_id=actor.id)
        db.add(row)
        add_audit(db, "devstudio.evaluation_added", actor.id, row.id, run_id)
        db.commit()
        return to_dict(row)

    @router.get("/lineage/{module_id}")
    def lineage(module_id: str, db: Session = Depends(get_db),
                actor: TeamMember = Depends(read)):
        validate_module(module_id)
        issues = db.scalars(select(DevIssue).where(DevIssue.module_id == module_id)).all()
        changes = db.scalars(select(DevChange).where(DevChange.module_id == module_id)).all()
        experiments = db.scalars(select(DevExperiment)
                                 .where(DevExperiment.module_id == module_id)).all()
        change_ids = [x.id for x in changes]
        exp_ids = [x.id for x in experiments]
        decision_rows = db.scalars(select(DevDecision).where(DevDecision.change_id.in_(change_ids))).all() if change_ids else []
        runs_rows = db.scalars(select(DevRunRef).where(DevRunRef.experiment_id.in_(exp_ids))).all() if exp_ids else []
        return {
            "module_id": module_id,
            "issues": [to_dict(x) for x in issues],
            "changes": [to_dict(x) for x in changes],
            "experiments": [to_dict(x) for x in experiments],
            "runs": [to_dict(x) for x in runs_rows],
            "decisions": [to_dict(x) for x in decision_rows],
            "note": "Links are explicitly recorded. Time order alone does not prove causation or deployment.",
        }

    app.include_router(router)
