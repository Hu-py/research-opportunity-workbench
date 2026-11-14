"""Editable, versioned Development Studio experiment registry (V0.4).

New supplementary tables keep the existing experiment/run/evaluation schema intact.
Never infer scientific or CI success from an external URL or recorded score.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.team import TeamMember, add_audit

OBJECTIVES = ("quality", "performance", "generalization", "coverage", "reliability", "methods", "usability", "other")
SCENARIOS = ("radar_a", "radar_b", "sc01", "sc02", "sc03", "platform", "other")
OBJECTS = ("source", "workflow", "prompt", "model", "skill", "backend", "frontend", "data", "evaluation", "other")
STATUSES = ("planned", "running", "blocked", "review", "completed", "archived")
TRANSITIONS = {
    "planned": {"running", "blocked", "archived"},
    "running": {"blocked", "review", "archived"},
    "blocked": {"planned", "running", "archived"},
    "review": {"running", "completed", "blocked", "archived"},
    "completed": {"running", "archived"},
    "archived": {"planned"},
}


def now():
    return datetime.now(timezone.utc)


class ExperimentProfile(Base):
    __tablename__ = "devstudio_experiment_profiles"
    experiment_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("devstudio_experiments.id"), primary_key=True
    )
    objective: Mapped[str] = mapped_column(String(32), default="other", index=True)
    scenario: Mapped[str] = mapped_column(String(32), default="other", index=True)
    change_object: Mapped[str] = mapped_column(String(32), default="other", index=True)
    method: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(String(36), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentEvent(Base):
    __tablename__ = "devstudio_experiment_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(32), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    details_json: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentInput(BaseModel):
    module_id: str
    title: str = Field(min_length=3, max_length=200)
    hypothesis: str = Field(min_length=10, max_length=4000)
    baseline: str = Field(default="", max_length=1500)
    input_snapshot_ref: str = Field(default="", max_length=1600)
    metrics: list[str] = Field(default_factory=list, max_length=20)
    change_id: str = ""
    objective: Literal[*OBJECTIVES] = "other"
    scenario: Literal[*SCENARIOS] = "other"
    change_object: Literal[*OBJECTS] = "other"
    method: str = Field(default="", max_length=3000)
    expected_result: str = Field(default="", max_length=3000)
    conclusion: str = Field(default="", max_length=3000)
    next_action: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def check_metrics(self):
        if any(not name or len(name)>100 for name in self.metrics):
            raise ValueError("Metric names must be 1..100 characters")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("Duplicate metric names")
        return self


class ExperimentPatch(BaseModel):
    expected_revision: int = Field(ge=0)
    module_id: str | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    hypothesis: str | None = Field(default=None, min_length=10, max_length=4000)
    baseline: str | None = Field(default=None, max_length=1500)
    input_snapshot_ref: str | None = Field(default=None, max_length=1600)
    metrics: list[str] | None = Field(default=None, max_length=20)
    change_id: str | None = None
    objective: Literal[*OBJECTIVES] | None = None
    scenario: Literal[*SCENARIOS] | None = None
    change_object: Literal[*OBJECTS] | None = None
    method: str | None = Field(default=None, max_length=3000)
    expected_result: str | None = Field(default=None, max_length=3000)
    conclusion: str | None = Field(default=None, max_length=3000)
    next_action: str | None = Field(default=None, max_length=2000)
    status: Literal[*STATUSES] | None = None

    @model_validator(mode="after")
    def check_metrics(self):
        if self.metrics is not None:
            if any(not name or len(name)>100 for name in self.metrics):
                raise ValueError("Metric names must be 1..100 characters")
            if len(set(self.metrics)) != len(self.metrics):
                raise ValueError("Duplicate metric names")
        return self


EXTRA_FIELDS = {"objective", "scenario", "change_object", "method",
                "expected_result", "conclusion", "next_action"}
BASE_FIELDS = {"module_id", "title", "hypothesis", "baseline",
               "input_snapshot_ref", "metrics", "change_id"}


def summary(row, profile, to_dict):
    item = to_dict(row)
    item.update({
        "objective": profile.objective if profile else "other",
        "scenario": profile.scenario if profile else "other",
        "change_object": profile.change_object if profile else "other",
        "method": profile.method if profile else "",
        "expected_result": profile.expected_result if profile else "",
        "conclusion": profile.conclusion if profile else "",
        "next_action": profile.next_action if profile else "",
        "revision": profile.revision if profile else 0,
        "updated_by": profile.updated_by if profile else row.created_by,
        "updated_at": profile.updated_at.isoformat() if profile else item["created_at"],
    })
    return item


def mount(router, *, get_db, read, write, validate_module, to_dict, new_id,
          DevExperiment, DevChange, DevRunRef, DevEvaluation, encode):
    # Register these before /experiments/{id} to avoid catch-all route overlap.
    @router.get("/experiment-management")
    def list_managed(
        module_id: str = "",
        objective: str = "",
        scenario: str = "",
        change_object: str = "",
        status: str = "",
        query: str = Query(default="", max_length=200),
        include_archived: bool = False,
        db: Session = Depends(get_db),
        actor: TeamMember = Depends(read),
    ):
        for field, val, allowed in (
            ("module_id", module_id, None),
            ("objective", objective, OBJECTIVES),
            ("scenario", scenario, SCENARIOS),
            ("change_object", change_object, OBJECTS),
            ("status", status, STATUSES),
        ):
            if val and allowed and val not in allowed:
                raise HTTPException(422, "Invalid " + field)
        if module_id:
            validate_module(module_id)
        q = select(DevExperiment).order_by(DevExperiment.created_at.desc())
        if module_id:
            q = q.where(DevExperiment.module_id == module_id)
        if status:
            q = q.where(DevExperiment.status == status)
        elif not include_archived:
            q = q.where(DevExperiment.status != "archived")
        rows = db.scalars(q.limit(700)).all()
        ids = [r.id for r in rows]
        profiles = {p.experiment_id: p for p in db.scalars(
            select(ExperimentProfile).where(ExperimentProfile.experiment_id.in_(ids))
        ).all()} if ids else {}
        items = [summary(r, profiles.get(r.id), to_dict) for r in rows]
        if objective:
            items = [r for r in items if r["objective"] == objective]
        if scenario:
            items = [r for r in items if r["scenario"] == scenario]
        if change_object:
            items = [r for r in items if r["change_object"] == change_object]
        if query.strip():
            term = query.strip().casefold()
            items = [r for r in items if term in " ".join(
                str(r.get(k) or "") for k in
                ("title", "hypothesis", "baseline", "method", "conclusion", "next_action")
            ).casefold()]
        return {"items": items, "count": len(items), "truncated": len(rows) == 700}

    @router.get("/experiment-management/{experiment_id}")
    def managed_detail(experiment_id: str, db: Session = Depends(get_db),
                       actor: TeamMember = Depends(read)):
        row = db.get(DevExperiment, experiment_id)
        if row is None:
            raise HTTPException(404, "Experiment not found")
        profile = db.get(ExperimentProfile, experiment_id)
        return summary(row, profile, to_dict)

    @router.post("/experiment-management", status_code=201)
    def managed_create(data: ExperimentInput, db: Session = Depends(get_db),
                       actor: TeamMember = Depends(write)):
        validate_module(data.module_id)
        if data.change_id and db.get(DevChange, data.change_id) is None:
            raise HTTPException(422, "Linked change not found")
        row = DevExperiment(
            id=new_id("exp"), module_id=data.module_id, change_id=data.change_id,
            title=data.title, hypothesis=data.hypothesis, baseline=data.baseline,
            input_snapshot_ref=data.input_snapshot_ref, metrics_json=encode(data.metrics),
            status="planned", created_by=actor.id,
        )
        profile = ExperimentProfile(experiment_id=row.id, updated_by=actor.id,
                                    **data.model_dump(include=EXTRA_FIELDS))
        db.add_all([row, profile])
        db.flush()
        item = summary(row, profile, to_dict)
        db.add(ExperimentEvent(
            id=new_id("evt"), experiment_id=row.id, revision=1,
            action="created", details_json=encode({"after": item}), actor_id=actor.id,
        ))
        add_audit(db, "devstudio.experiment_created_v04", actor.id, row.id, data.title)
        db.commit()
        return summary(row, profile, to_dict)

    @router.patch("/experiment-management/{experiment_id}")
    def managed_patch(experiment_id: str, data: ExperimentPatch,
                      db: Session = Depends(get_db),
                      actor: TeamMember = Depends(write)):
        row = db.execute(select(DevExperiment).where(DevExperiment.id == experiment_id)
                         .with_for_update()).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "Experiment not found")
        profile = db.get(ExperimentProfile, experiment_id)
        revision = profile.revision if profile else 0
        if data.expected_revision != revision:
            raise HTTPException(409, "Experiment changed by another editor; refresh")
        changes = data.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if not changes:
            raise HTTPException(422, "No changes provided")
        if row.status == "archived" and changes.get("status") != "planned":
            raise HTTPException(409, "Archived experiment must be reopened before editing")
        if "module_id" in changes:
            validate_module(changes["module_id"])
        if changes.get("change_id") and db.get(DevChange, changes["change_id"]) is None:
            raise HTTPException(422, "Linked change not found")
        if "status" in changes and changes["status"] != row.status:
            if changes["status"] not in TRANSITIONS.get(row.status, set()):
                raise HTTPException(409, "Invalid experiment status transition")
        if "status" in changes and changes["status"] == "completed":
            has_evaluation = db.scalar(
                select(func.count()).select_from(DevEvaluation)
                .join(DevRunRef, DevEvaluation.run_id == DevRunRef.id)
                .where(DevRunRef.experiment_id == experiment_id)
            ) or 0
            if not has_evaluation:
                raise HTTPException(409, "Complete requires at least one recorded run evaluation")
        before = summary(row, profile, to_dict)
        if profile is None:
            profile = ExperimentProfile(experiment_id=experiment_id, revision=0,
                                        updated_by=actor.id)
            db.add(profile)
        for key, val in changes.items():
            if key in EXTRA_FIELDS:
                setattr(profile, key, val)
            elif key in BASE_FIELDS:
                if key == "metrics":
                    row.metrics_json = encode(val)
                else:
                    setattr(row, key, val)
            elif key == "status":
                row.status = val
        profile.revision = revision + 1
        profile.updated_by = actor.id
        profile.updated_at = now()
        db.flush()
        after = summary(row, profile, to_dict)
        changed = {key: {"before": before.get(key), "after": after.get(key)}
                   for key in changes if before.get(key) != after.get(key)}
        if not changed:
            raise HTTPException(422, "No actual changes")
        db.add(ExperimentEvent(
            id=new_id("evt"), experiment_id=experiment_id, revision=profile.revision,
            action="status_changed" if set(changes) == {"status"} else "updated",
            details_json=encode(changed), actor_id=actor.id,
        ))
        add_audit(db, "devstudio.experiment_updated_v04", actor.id, row.id,
                  "revision=" + str(profile.revision) + "; fields=" + ",".join(sorted(changed)))
        db.commit()
        return summary(row, profile, to_dict)

    @router.get("/experiment-management/{experiment_id}/history")
    def managed_history(experiment_id: str, db: Session = Depends(get_db),
                        actor: TeamMember = Depends(read)):
        if db.get(DevExperiment, experiment_id) is None:
            raise HTTPException(404, "Experiment not found")
        entries = db.scalars(
            select(ExperimentEvent).where(ExperimentEvent.experiment_id == experiment_id)
            .order_by(ExperimentEvent.created_at.desc(), ExperimentEvent.revision.desc())
            .limit(100)
        ).all()
        return {"items": [{
            "id": x.id, "experiment_id": x.experiment_id,
            "revision": x.revision, "action": x.action,
            "details": json.loads(x.details_json),
            "actor_id": x.actor_id, "created_at": x.created_at.isoformat(),
        } for x in entries]}
