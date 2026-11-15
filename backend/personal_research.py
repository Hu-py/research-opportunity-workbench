"""Research Atlas SC02 personal portrait and two evidence-bounded research runs.

Public bibliographic evidence is imported into a neutral TEST snapshot store.
Only the authenticated member can read their private portrait/results. The
named Owner seed is scoped by a deployment-only email environment variable,
not hardcoded in this public repository or assigned to a synthetic test Owner.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.team import TeamMember, add_audit
from backend.profile_database import evidence_inventory, safe_overview

PILOT_FILE = Path(__file__).parent / "fixtures/research_atlas_two_domain_probe_review_20261114.json"
PROFILE_VERSION = "0.1.0"
SEED_EMAIL_ENV = "PERSONAL_RESEARCH_OWNER_EMAIL"
REQUIRED_KEYS = ("child_health_extrapolation", "vertical_urbanization_3d")
EVIDENCE_LEVEL = "publisher_abstract_or_conference_abstract_checked"
SOURCE_VENUES = {
    "A": {"Cities", "Sustainable Cities and Society"},
    "B": {"Computers, Environment and Urban Systems",
          "Environment and Planning B: Urban Analytics and City Science"},
    "C": {"NeurIPS", "AAAI", "KDD", "ICML", "ICLR", "IJCAI"},
}


def now():
    return datetime.now(timezone.utc)


def read_json(raw):
    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}


class PersonalResearchProfile(Base):
    __tablename__ = "personal_research_profiles"
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("team_members.id"), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="user_confirmed")
    revision: Mapped[str] = mapped_column(String(32), default=PROFILE_VERSION)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PublicPilotEvidence(Base):
    __tablename__ = "research_pilot_public_evidence"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    result_json: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(30), default="needs_scientific_review")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PersonalResearchResult(Base):
    __tablename__ = "personal_research_results"
    id: Mapped[str] = mapped_column(String(70), primary_key=True)
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("team_members.id"), index=True)
    topic_key: Mapped[str] = mapped_column(String(80), index=True)
    result_json: Mapped[str] = mapped_column(Text)
    source_digest: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(30), default="needs_scientific_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProfileUpdate(BaseModel):
    interests: list[str] = Field(min_length=1, max_length=8)
    note: str = Field(default="", max_length=700)


def source_file() -> dict:
    data = json.loads(PILOT_FILE.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0":
        raise ValueError("Unknown pilot source version")
    if data.get("llm_api_executed") is not False or data.get("openalex_api_executed") is not False:
        raise ValueError("Unverified API execution claims")
    if {x.get("key") for x in data.get("topics", [])} != set(REQUIRED_KEYS):
        raise ValueError("Missing two research subjects")
    for topic in data["topics"]:
        probes = topic.get("probes", [])
        if [x.get("id") for x in probes] != ["A", "B", "C"]:
            raise ValueError("Three distinct source probes required")
        for probe in probes:
            if len(probe.get("papers", [])) < 2:
                raise ValueError("Probe evidence too thin")
            for paper in probe["papers"]:
                if paper.get("venue") not in SOURCE_VENUES[probe["id"]]:
                    raise ValueError("Source venue is outside the configured A/B/C probe")
                if not str(paper.get("url", "")).startswith("https://"):
                    raise ValueError("Original paper URL missing")
    return data


def seed_public_pilots(db: Session) -> dict:
    """Only used by the isolated test service with its verified PostgreSQL schema."""
    data = source_file()
    added = 0
    for entry in data["topics"]:
        key = entry["key"]
        record = {
            "topic": entry,
            "created_on": data["created_on"],
            "retrieval_provenance": data["execution_mode"],
            "llm_api_executed": data["llm_api_executed"],
            "openalex_api_executed": data["openalex_api_executed"],
            "full_text_audited": False,
            "review_status": "needs_scientific_review",
            "candidate_status": "hypothesis_not_accepted",
            "disclosure": "按出版来源检索后人工辅助选取的证据快照，不是平台自动执行的 AI 模型分析，也不是儿童健康或三维城市实验结果。",
        }
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        existing = db.get(PublicPilotEvidence, key)
        if existing is None:
            db.add(PublicPilotEvidence(key=key, result_json=payload, digest=digest))
            added += 1
        elif existing.digest != digest:
            # The source pack changed; do not silently mutate the historical
            # run to give a user a new result that was not reviewed.
            raise ValueError("Pilot source changed; require versioned migration")
    db.commit()
    return {"seeded": added, "available": len(data["topics"]),
            "source_kind": data["execution_mode"]}


def _default_profile() -> dict:
    return {
        "version": PROFILE_VERSION,
        "scope": "personal",
        "explicitly_declared_interests": ["儿童健康空间外推", "三维竖向城市化"],
        "research_questions": {
            "child_health_extrapolation": "局部训练到跨城区或跨城市的预测可靠性、空间验证和标签测量误差",
            "vertical_urbanization_3d": "建筑楼层功能、竖向可达性、3D 城市测量与 POI 楼层恢复",
        },
        "analysis_preferences": [
            "三探针 A 应用、B 城市科学、C 计算方法独立分析",
            "原始论文来源可追溯；显式区分作者结论、证据不足与模型假设",
            "重视方法迁移边界、反证及最小验证实验",
        ],
        "claim": "user_declared_interest_only_not_verified_team_capability",
    }


def _verified_owner_seed(actor: TeamMember) -> bool:
    expected = os.getenv(SEED_EMAIL_ENV, "").strip().casefold()
    return bool(expected and actor.role == "owner"
                and actor.active and actor.email.casefold() == expected)


def _private_id(member_id: str, key: str) -> str:
    return "pr_" + hashlib.sha256((member_id + ":" + key).encode()).hexdigest()[:38]


def ensure_personal(db: Session, actor: TeamMember, *, explicit: bool = False) -> bool:
    """Only seed for real authenticated owner with explicit target email."""
    if not explicit and not _verified_owner_seed(actor):
        return False
    profile = db.get(PersonalResearchProfile, actor.id)
    created = profile is None
    if profile is None:
        db.add(PersonalResearchProfile(
            member_id=actor.id, payload_json=json.dumps(_default_profile(), ensure_ascii=False),
            status="user_declared_initial"))
    # Source rows are neutral, but private copies are attached to the verified
    # member_id and will never be returned in other members' personal queries.
    for key in REQUIRED_KEYS:
        evidence = db.get(PublicPilotEvidence, key)
        if evidence is None:
            continue
        item_id = _private_id(actor.id, key)
        if db.get(PersonalResearchResult, item_id) is None:
            db.add(PersonalResearchResult(
                id=item_id, member_id=actor.id, topic_key=key,
                result_json=evidence.result_json,
                source_digest=evidence.digest,
            ))
            created = True
    if created:
        add_audit(db, "personal_research.owner_seeded", actor.id, actor.id,
                  "Private profile and two user-requested bibliographic previews")
        db.commit()
    return created


def private_profile(db, actor) -> dict:
    row = db.get(PersonalResearchProfile, actor.id)
    return {
        "profile": read_json(row.payload_json) if row else None,
        "status": row.status if row else "not_created",
        "revision": row.revision if row else None,
        "scope": "personal",
        "team_portrait": safe_overview(evidence_inventory(db)),
        "note": "团队画像依据团队数据库成果；个人画像只从本人明确表达的兴趣建立，不推断个人成果或数据授权。",
    }


def private_result(db, actor, key: str):
    row = db.get(PersonalResearchResult, _private_id(actor.id, key))
    if row is None or row.member_id != actor.id:
        return None
    return {
        "id": row.id, "topic_key": row.topic_key,
        "run": read_json(row.result_json),
        "review_status": row.review_status,
        "source_digest": row.source_digest,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "visibility": "personal",
    }


def mount(app, *, get_db, require_actor, team_auth_enabled):
    router = APIRouter(prefix="/api/personal-research", tags=["Personal Research"])

    def member(actor: TeamMember | None = Depends(require_actor)):
        if not team_auth_enabled() or actor is None or not actor.active:
            raise HTTPException(401, "Team member session required")
        return actor

    @router.get("/me")
    def me(db: Session = Depends(get_db), actor: TeamMember = Depends(member)):
        ensure_personal(db, actor)
        return private_profile(db, actor)

    @router.post("/me/initialize")
    def initialize(db: Session = Depends(get_db),
                   actor: TeamMember = Depends(member)):
        # A profile can already exist even when its run copies have not yet
        # been associated with this member. Keep edits intact; attach only
        # missing public-preview results to this authenticated account.
        public_keys = set(db.scalars(select(PublicPilotEvidence.key).where(
            PublicPilotEvidence.key.in_(REQUIRED_KEYS))).all())
        if not set(REQUIRED_KEYS).issubset(public_keys):
            raise HTTPException(503, "两份公开文献快照尚未导入测试数据库")
        ensure_personal(db, actor, explicit=True)
        linked = [private_result(db, actor, key) for key in REQUIRED_KEYS]
        if any(value is None for value in linked):
            raise HTTPException(503, "个人结果关联尚未完成，请稍后重试")
        return {"profile": private_profile(db, actor),
                "results": linked, "linked_count": len(linked)}

    @router.put("/me")
    def update(data: ProfileUpdate, db: Session = Depends(get_db),
               actor: TeamMember = Depends(member)):
        values = [x.strip() for x in data.interests]
        if any(not 2 <= len(x) <= 100 for x in values) or len(set(values)) != len(values):
            raise HTTPException(422, "Interests must be distinct and 2..100 characters")
        row = db.get(PersonalResearchProfile, actor.id)
        if row is None:
            row = PersonalResearchProfile(member_id=actor.id)
            db.add(row)
        payload = read_json(row.payload_json)
        payload.update({"version": PROFILE_VERSION, "scope": "personal",
                        "explicitly_declared_interests": values, "note": data.note,
                        "claim": "user_edited_private_profile"})
        row.payload_json = json.dumps(payload, ensure_ascii=False)
        row.status = "user_confirmed"
        row.updated_at = now()
        add_audit(db, "personal_research.updated", actor.id, actor.id,
                  "Owner of personal profile updated interests")
        db.commit()
        return private_profile(db, actor)

    @router.get("/me/results")
    def results(db: Session = Depends(get_db),
                actor: TeamMember = Depends(member)):
        ensure_personal(db, actor)
        rows = db.scalars(select(PersonalResearchResult).where(
            PersonalResearchResult.member_id == actor.id
        ).order_by(PersonalResearchResult.created_at.desc()).limit(20)).all()
        public = db.scalars(select(PublicPilotEvidence.key).where(
            PublicPilotEvidence.key.in_(REQUIRED_KEYS))).all()
        linked = {row.topic_key for row in rows}
        return {"items": [private_result(db, actor, row.topic_key) for row in rows],
                "scope": "personal", "count": len(rows),
                "expected_count": len(REQUIRED_KEYS),
                "available_public_count": len(public),
                "missing_topic_keys": [key for key in REQUIRED_KEYS if key not in linked],
                "requires_explicit_import": bool(set(REQUIRED_KEYS) - linked),
                "note": "两个真实出版页检索样本由研究者辅助整理，尚非 Agent 自主推理或 SCI 原始科研实验结果。"}

    @router.get("/me/results/{result_id}")
    def detail(result_id: str, db: Session = Depends(get_db),
               actor: TeamMember = Depends(member)):
        row = db.get(PersonalResearchResult, result_id)
        if row is None or row.member_id != actor.id:
            raise HTTPException(404, "Personal research result not found")
        return private_result(db, actor, row.topic_key)

    app.include_router(router)
