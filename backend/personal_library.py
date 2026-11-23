"""Member-private research library for publications, reports and experiment records.

The library stores small metadata snapshots and references to source records/files.
It does not duplicate full PDFs or shared team research records.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select, or_
from sqlalchemy.orm import Mapped, mapped_column, Session

from research_workbench.core import Base
from backend.team import PersonalResearchProfile


KINDS = {"publication", "agent_report", "experiment_result", "project", "dataset", "note"}
SOURCE_TYPES = {
    "doi", "openalex_work", "chatgpt_space_page", "research_task",
    "sc05_run", "library_file", "external_url", "manual",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PersonalResearchAsset(Base):
    __tablename__ = "personal_research_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), index=True
    )
    client_key: Mapped[str] = mapped_column(String(80), default="")
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(260), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(40), default="manual")
    source_id: Mapped[str] = mapped_column(String(255), default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("member_id", "client_key", name="uq_personal_asset_member_client_key"),
    )


class PersonalResearchAssetLine(Base):
    __tablename__ = "personal_research_asset_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("personal_research_assets.id", ondelete="CASCADE"), index=True
    )
    line_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("member_id", "asset_id", "line_id", name="uq_personal_asset_line"),
    )


def profile_line_ids(db: Session, member_id: str) -> set[str]:
    profile = db.get(PersonalResearchProfile, member_id)
    if profile is None:
        return set()
    try:
        payload = json.loads(profile.profile_json or "{}")
    except (TypeError, ValueError):
        return set()
    return {
        line.get("id")
        for line in payload.get("research_lines", [])
        if isinstance(line, dict) and isinstance(line.get("id"), str)
    }


def validate_asset_payload(payload: dict, allowed_line_ids: set[str]) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("科研资料必须是对象")
    kind = payload.get("kind")
    if kind not in KINDS:
        raise ValueError("不支持的科研资料类型")
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 260:
        raise ValueError("资料标题不能为空且不超过 260 字")
    summary = payload.get("summary", payload.get("note", ""))
    url = payload.get("url", "")
    source_type = payload.get("source_type", "manual")
    source_id = payload.get("source_id", "")
    client_key = payload.get("client_key", "")
    metadata = payload.get("metadata", {})
    line_ids = payload.get("line_ids", [])

    if not isinstance(summary, str) or len(summary) > 12000:
        raise ValueError("资料摘要不超过 12000 字")
    if not isinstance(url, str) or len(url) > 1200 or (
        url and not url.startswith(("https://", "http://"))
    ):
        raise ValueError("资料链接必须为有效 HTTP(S) 地址")
    if source_type not in SOURCE_TYPES:
        raise ValueError("资料来源类型无效")
    if not isinstance(source_id, str) or len(source_id) > 255:
        raise ValueError("来源记录 ID 不超过 255 字")
    if source_type in {"doi", "openalex_work", "chatgpt_space_page", "research_task", "sc05_run", "library_file"} and not source_id:
        raise ValueError("引用已有论文、报告或实验时必须提供来源记录 ID")
    if not isinstance(client_key, str) or len(client_key) > 80:
        raise ValueError("资料客户端标识不超过 80 字")
    if not isinstance(metadata, dict) or len(json.dumps(metadata, ensure_ascii=False)) > 30000:
        raise ValueError("资料元数据格式无效或过大")
    if not isinstance(line_ids, list) or len(line_ids) > 8 or any(
        not isinstance(line_id, str) or line_id not in allowed_line_ids
        for line_id in line_ids
    ):
        raise ValueError("资料只能关联当前账号已有的个人研究主线")
    return {
        "kind": kind,
        "title": title.strip(),
        "summary": summary,
        "url": url,
        "source_type": source_type,
        "source_id": source_id,
        "client_key": client_key,
        "metadata": metadata,
        "line_ids": list(dict.fromkeys(line_ids)),
    }


def serialize_asset(db: Session, asset: PersonalResearchAsset) -> dict:
    links = db.scalars(
        select(PersonalResearchAssetLine.line_id).where(
            PersonalResearchAssetLine.member_id == asset.member_id,
            PersonalResearchAssetLine.asset_id == asset.id,
        )
    ).all()
    try:
        metadata = json.loads(asset.metadata_json or "{}")
    except (TypeError, ValueError):
        metadata = {}
    return {
        "id": asset.id,
        "client_key": asset.client_key,
        "kind": asset.kind,
        "title": asset.title,
        "summary": asset.summary,
        "url": asset.url,
        "source_type": asset.source_type,
        "source_id": asset.source_id,
        "metadata": metadata,
        "line_ids": list(links),
        "status": asset.status,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }


def upsert_personal_asset(db: Session, member_id: str, raw: dict) -> dict:
    allowed = profile_line_ids(db, member_id)
    if not allowed:
        raise ValueError("请先保存个人研究画像，再录入关联科研资料")
    payload = validate_asset_payload(raw, allowed)

    asset = None
    if payload["client_key"]:
        asset = db.scalar(select(PersonalResearchAsset).where(
            PersonalResearchAsset.member_id == member_id,
            PersonalResearchAsset.client_key == payload["client_key"],
        ))
    if asset is None and payload["source_id"]:
        asset = db.scalar(select(PersonalResearchAsset).where(
            PersonalResearchAsset.member_id == member_id,
            PersonalResearchAsset.source_type == payload["source_type"],
            PersonalResearchAsset.source_id == payload["source_id"],
            PersonalResearchAsset.status == "active",
        ))
    if asset is None:
        client_key = payload["client_key"] or "manual_" + uuid.uuid4().hex
        asset = PersonalResearchAsset(
            id=str(uuid.uuid4()),
            member_id=member_id,
            client_key=client_key,
            kind=payload["kind"],
            title=payload["title"],
        )
        db.add(asset)

    asset.kind = payload["kind"]
    asset.title = payload["title"]
    asset.summary = payload["summary"]
    asset.url = payload["url"]
    asset.source_type = payload["source_type"]
    asset.source_id = payload["source_id"]
    asset.metadata_json = json.dumps(payload["metadata"], ensure_ascii=False)
    asset.status = "active"
    asset.archived_at = None
    asset.updated_at = utc_now()
    db.flush()

    db.query(PersonalResearchAssetLine).filter_by(
        member_id=member_id, asset_id=asset.id
    ).delete(synchronize_session=False)
    for line_id in payload["line_ids"]:
        db.add(PersonalResearchAssetLine(
            member_id=member_id, asset_id=asset.id, line_id=line_id
        ))
    db.flush()
    return serialize_asset(db, asset)


def list_personal_assets(
    db: Session,
    member_id: str,
    *,
    kind: str | None = None,
    line_id: str | None = None,
    query: str | None = None,
    include_archived: bool = False,
) -> list[dict]:
    stmt = select(PersonalResearchAsset).where(
        PersonalResearchAsset.member_id == member_id
    )
    if not include_archived:
        stmt = stmt.where(PersonalResearchAsset.status == "active")
    if kind:
        if kind not in KINDS:
            raise ValueError("不支持的科研资料类型")
        stmt = stmt.where(PersonalResearchAsset.kind == kind)
    if line_id:
        stmt = stmt.where(PersonalResearchAsset.id.in_(
            select(PersonalResearchAssetLine.asset_id).where(
                PersonalResearchAssetLine.member_id == member_id,
                PersonalResearchAssetLine.line_id == line_id,
            )
        ))
    if query:
        needle = "%" + query.strip()[:120] + "%"
        stmt = stmt.where(or_(
            PersonalResearchAsset.title.ilike(needle),
            PersonalResearchAsset.summary.ilike(needle),
            PersonalResearchAsset.source_id.ilike(needle),
        ))
    rows = db.scalars(stmt.order_by(PersonalResearchAsset.updated_at.desc()).limit(200)).all()
    return [serialize_asset(db, row) for row in rows]


def archive_personal_asset(db: Session, member_id: str, asset_id: str) -> bool:
    asset = db.scalar(select(PersonalResearchAsset).where(
        PersonalResearchAsset.id == asset_id,
        PersonalResearchAsset.member_id == member_id,
    ))
    if asset is None:
        return False
    asset.status = "archived"
    asset.archived_at = utc_now()
    asset.updated_at = utc_now()
    db.flush()
    return True


def prune_personal_asset_line_links(db: Session, member_id: str, valid_line_ids: set[str]) -> int:
    """Unlink assets from removed research lines without deleting the assets."""
    query = db.query(PersonalResearchAssetLine).filter(
        PersonalResearchAssetLine.member_id == member_id
    )
    if valid_line_ids:
        query = query.filter(~PersonalResearchAssetLine.line_id.in_(valid_line_ids))
    return query.delete(synchronize_session=False)
