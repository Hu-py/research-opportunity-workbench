"""Task-scoped scholarly source lists. One global registry, separate A/B/C selections.

Configuration is stored independently for SC01, SC02 (per member), and SC03.
A run snapshots its effective list; later changes cannot rewrite historical runs.
An enforced list fails closed when unresolved, disabled, or empty, rather than
silently broadening a scholarly search.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from research_workbench.core import Base
from backend.research_sources import ResearchSource, _aliases, _norm

BANDS = ("A", "B", "C")
SCOPES = ("team_weekly", "personal_weekly", "directed_research")

# User-approved planning split. C is an editable *candidate* technical pool,
# not a claim all computer-science venues are equally authoritative.
INITIAL_NAMES = {
    "team_weekly": {
        "A": ["Cities", "Sustainable Cities and Society"],
        "B": ["Environment and Planning B", "Computers, Environment and Urban Systems"],
        "C": ["NeurIPS", "ICML", "ICLR"],
    },
    "personal_weekly": {"A": [], "B": [], "C": []},
    "directed_research": {
        "A": ["Cities", "Sustainable Cities and Society"],
        "B": ["Environment and Planning B", "Computers, Environment and Urban Systems"],
        "C": ["NeurIPS", "ICML", "ICLR"],
    },
}


class TaskSourceScope(Base):
    __tablename__ = "task_source_scopes"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    scene: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(48), default="")
    groups_json: Mapped[str] = mapped_column(Text, default="{}")
    enforced: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(String(48), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TaskSourceSnapshot(Base):
    __tablename__ = "task_source_snapshots"
    task_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scene: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(48), default="")
    groups_json: Mapped[str] = mapped_column(Text, default="{}")
    enforced: Mapped[bool] = mapped_column(Boolean, default=False)
    scope_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def _key(scene: str, owner_id: str = "") -> str:
    if scene not in SCOPES:
        raise ValueError("Unknown research source scope")
    if scene == "personal_weekly":
        if not owner_id:
            raise ValueError("Personal source scope requires a team member session")
        return "personal_weekly:" + owner_id
    return scene


def _decode(value: str) -> dict[str, list[str]]:
    parsed = json.loads(value or "{}")
    return {band: list(parsed.get(band) or []) for band in BANDS}


def _defaults(db, scene: str) -> dict[str, list[str]]:
    rows = db.scalars(select(ResearchSource)).all()
    by_name = {}
    for row in rows:
        for name in [row.name, row.abbreviation, *_aliases(row)]:
            by_name[_norm(name)] = row.id
    return {
        band: list(dict.fromkeys(
            by_name[_norm(name)] for name in INITIAL_NAMES[scene][band]
            if _norm(name) in by_name
        ))
        for band in BANDS
    }


def _validate_groups(db, groups: dict) -> dict[str, list[str]]:
    if not isinstance(groups, dict) or set(groups) != set(BANDS):
        raise ValueError("Source groups must include A, B and C")
    normalized = {}
    all_ids = []
    for band in BANDS:
        values = groups[band]
        if not isinstance(values, list) or len(values) > 80:
            raise ValueError("Each A/B/C group must contain at most 80 source IDs")
        if any(not isinstance(value, str) or len(value) > 60 for value in values):
            raise ValueError("Source IDs must be short strings")
        normalized[band] = list(dict.fromkeys(values))
        all_ids.extend(normalized[band])
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("A journal or conference can belong to only one task source group")
    if all_ids:
        rows = db.scalars(select(ResearchSource).where(ResearchSource.id.in_(all_ids))).all()
        found = {row.id for row in rows if row.enabled}
        if set(all_ids) != found:
            raise ValueError("Source list contains disabled or unknown registry entries")
    return normalized


def read_scope(db, scene: str, owner_id: str = "") -> dict:
    key = _key(scene, owner_id)
    row = db.get(TaskSourceScope, key)
    groups = _decode(row.groups_json) if row else _defaults(db, scene)
    ids = {item for group in groups.values() for item in group}
    sources = db.scalars(select(ResearchSource).where(ResearchSource.id.in_(ids))).all() if ids else []
    ready = sum(bool(x.enabled and x.resolution_status == "resolved" and x.openalex_source_id) for x in sources)
    return {
        "scene": scene,
        "groups": groups,
        "enforced": bool(row and row.enforced),
        "configured": bool(row),
        "version": row.version if row else 0,
        "selected_count": len(ids),
        "resolved_count": ready,
        "missing_or_unresolved": len(ids) - ready,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


def write_scope(db, scene: str, *, groups: dict, enforced: bool,
                expected_version: int, actor_id: str = "", owner_id: str = "") -> dict:
    key = _key(scene, owner_id)
    groups = _validate_groups(db, groups)
    if enforced and not any(groups.values()):
        raise ValueError("Strict source filtering requires at least one selected source")
    row = db.get(TaskSourceScope, key)
    current = row.version if row else 0
    if expected_version != current:
        raise ValueError("Source configuration was changed; refresh before saving")
    if row is None:
        row = TaskSourceScope(key=key, scene=scene, owner_id=owner_id)
        db.add(row)
    row.groups_json = json.dumps(groups, ensure_ascii=False)
    row.enforced = bool(enforced)
    row.version = current + 1
    row.updated_by = actor_id
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return read_scope(db, scene, owner_id)


def snapshot_task(db, task_id: str, *, kind: str, owner_id: str = "",
                  override: dict | None = None) -> dict:
    scene = "team_weekly" if kind == "weekly" else "directed_research"
    record = read_scope(db, scene)
    groups = _validate_groups(db, override) if override is not None else record["groups"]
    enforced = override is not None or record["enforced"]
    if enforced and not any(groups.values()):
        raise ValueError("Strict task source list cannot be empty")
    if db.get(TaskSourceSnapshot, task_id) is not None:
        raise ValueError("Task source snapshot already exists")
    snap = TaskSourceSnapshot(
        task_id=task_id, scene=scene, owner_id=owner_id,
        groups_json=json.dumps(groups, ensure_ascii=False),
        enforced=enforced, scope_version=record["version"],
    )
    db.add(snap)
    db.commit()
    return {
        "scene": scene, "groups": groups,
        "enforced": enforced, "scope_version": record["version"],
    }


def task_source_context(db, task_id: str) -> dict | None:
    snap = db.get(TaskSourceSnapshot, task_id)
    if snap is None or not snap.enforced:
        return None
    groups = _decode(snap.groups_json)
    ids = {source_id for group in groups.values() for source_id in group}
    if not ids:
        raise ValueError("Strict task source list is empty")
    rows = db.scalars(select(ResearchSource).where(ResearchSource.id.in_(ids))).all()
    by_id = {row.id: row for row in rows}
    missing = [
        source_id for source_id in ids
        if source_id not in by_id or not by_id[source_id].enabled
        or by_id[source_id].resolution_status != "resolved"
        or not by_id[source_id].openalex_source_id
    ]
    if missing:
        raise ValueError(
            f"任务专属来源中有 {len(missing)} 个未核验/已停用的期刊或会议。"
            "请先在「研究设置 → 来源总目录」完成 OpenAlex 核验，不会自动扩大到所有期刊。"
        )
    def openalex_ids(bands):
        return list(dict.fromkeys(
            by_id[source_id].openalex_source_id
            for band in bands for source_id in groups[band]
        ))
    allowed_names = {
        _norm(name) for row in rows for name in
        [row.name, row.abbreviation, *_aliases(row)] if name.strip()
    }
    return {
        "groups": groups,
        "direct_ids": openalex_ids(("A", "B")),
        "method_ids": openalex_ids(("C",)),
        "all_ids": openalex_ids(BANDS),
        "allowed_venues": allowed_names,
        "scope_version": snap.scope_version,
        "scene": snap.scene,
    }
