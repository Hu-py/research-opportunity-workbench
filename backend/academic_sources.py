"""Database-backed Academic Source Registry.

The JSON catalogue is a versioned bootstrap only. PostgreSQL is the runtime
source of truth; seed refreshes add missing rows but never overwrite edits.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import Boolean, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from research_workbench.core import Base


def now():
    return datetime.now(timezone.utc)


def _json(raw, default):
    try:
        value = json.loads(raw) if raw else default
        return value if isinstance(value, type(default)) else default
    except (TypeError, ValueError):
        return default


def _norm(value):
    return re.sub(r"[^\w]+", "", str(value or "").casefold(), flags=re.UNICODE)


def _source_id(value):
    raw = str(value or "").strip().rstrip("/")
    token = raw.rsplit("/", 1)[-1]
    return token if re.fullmatch(r"S\d+", token) else ""


def _list(values, *, limit=20, max_length=180, field="列表"):
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > limit:
        raise ValueError(field + "格式无效或数量超限")
    out = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(field + "不能包含空项")
        item = value.strip()[:max_length]
        if item not in out:
            out.append(item)
    return out


def _url(value):
    value = str(value or "").strip()
    if value and not value.startswith("https://"):
        raise ValueError("来源主页必须使用 HTTPS 地址")
    if len(value) > 1200:
        raise ValueError("来源主页过长")
    return value


class AcademicDomain(Base):
    __tablename__ = "academic_domains"
    slug: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_name: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    default_channels_json: Mapped[str] = mapped_column(Text, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AcademicSource(Base):
    __tablename__ = "academic_sources"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(260), nullable=False, index=True)
    abbreviation: Mapped[str] = mapped_column(String(80), default="")
    kind: Mapped[str] = mapped_column(String(20), default="journal", index=True)
    domains_json: Mapped[str] = mapped_column(Text, default="[]")
    rank_label: Mapped[str] = mapped_column(String(32), default="观察")
    ranking_system: Mapped[str] = mapped_column(String(180), default="")
    ranking_version: Mapped[str] = mapped_column(String(80), default="")
    ranking_source_url: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")
    notes: Mapped[str] = mapped_column(Text, default="")
    retrieval_channels_json: Mapped[str] = mapped_column(Text, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    openalex_source_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    resolution_status: Mapped[str] = mapped_column(String(24), default="unresolved", index=True)
    openalex_type: Mapped[str] = mapped_column(String(40), default="")
    resolution_note: Mapped[str] = mapped_column(String(300), default="")
    created_by: Mapped[str] = mapped_column(String(48), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AcademicSourceRevision(Base):
    __tablename__ = "academic_source_revisions"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(48), index=True)
    actor_id: Mapped[str] = mapped_column(String(48), default="")
    action: Mapped[str] = mapped_column(String(32), default="updated")
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AcademicRegistryState(Base):
    __tablename__ = "academic_registry_state"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    catalogue_version: Mapped[str] = mapped_column(String(80), default="")
    last_seeded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def domain_dict(row):
    return {
        "slug": row.slug, "name": row.name, "group_name": row.group_name,
        "description": row.description,
        "default_channels": _json(row.default_channels_json, []),
        "sort_order": row.sort_order, "enabled": row.enabled, "is_seed": row.is_seed,
    }


def source_dict(row):
    return {
        "id": row.id, "name": row.name, "abbreviation": row.abbreviation,
        "kind": row.kind, "domains": _json(row.domains_json, []),
        "rank_label": row.rank_label, "ranking_system": row.ranking_system,
        "ranking_version": row.ranking_version, "ranking_source_url": row.ranking_source_url,
        "source_url": row.source_url,
        "aliases": _json(row.aliases_json, []), "notes": row.notes,
        "retrieval_channels": _json(row.retrieval_channels_json, []),
        "enabled": row.enabled, "is_seed": row.is_seed,
        "openalex_source_id": row.openalex_source_id,
        "resolution_status": row.resolution_status, "openalex_type": row.openalex_type,
        "resolution_note": row.resolution_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _snapshot(row):
    return source_dict(row)


def _revision(db, row, action, actor, before=None):
    db.add(AcademicSourceRevision(
        id="asr_" + uuid.uuid4().hex[:28], source_id=row.id,
        actor_id=actor or "", action=action,
        before_json=json.dumps(before or {}, ensure_ascii=False),
        after_json=json.dumps(_snapshot(row), ensure_ascii=False),
    ))


def seed_registry(db):
    """Add new entries from the versioned JSON catalogue without overwriting edits."""
    path = Path(__file__).resolve().parent / "data" / "academic_sources_seed.json"
    if not path.exists():
        return {"domains_added": 0, "sources_added": 0, "catalogue_version": ""}
    payload = json.loads(path.read_text(encoding="utf-8"))
    domains_added = 0
    sources_added = 0
    for item in payload.get("domains", []):
        slug = str(item.get("slug", "")).strip()
        if not re.fullmatch(r"[a-z0-9_]{2,48}", slug):
            continue
        if db.get(AcademicDomain, slug):
            continue
        channels = [x for x in item.get("default_channels", []) if x in ("direct", "method")]
        db.add(AcademicDomain(
            slug=slug, name=str(item.get("name", slug))[:100],
            group_name=str(item.get("group_name", ""))[:100],
            description=str(item.get("description", ""))[:500],
            default_channels_json=json.dumps(channels, ensure_ascii=False),
            sort_order=int(item.get("sort_order", 100)), enabled=True, is_seed=True,
        ))
        domains_added += 1
    db.flush()
    known = db.scalars(select(AcademicSource)).all()
    by_name = {_norm(x.name): x for x in known}
    for item in payload.get("sources", []):
        name = str(item.get("name", "")).strip()
        kind = item.get("kind", "journal")
        if not name or kind not in ("journal", "conference") or _norm(name) in by_name:
            continue
        domains = [x for x in item.get("domains", []) if db.get(AcademicDomain, x)]
        channels = [x for x in item.get("retrieval_channels", []) if x in ("direct", "method")]
        ident = "asrc_" + hashlib.sha256((kind + "|" + name).encode()).hexdigest()[:28]
        row = AcademicSource(
            id=ident, name=name[:260], abbreviation=str(item.get("abbreviation", ""))[:80],
            kind=kind, domains_json=json.dumps(domains, ensure_ascii=False),
            rank_label=str(item.get("rank_label", "观察"))[:32],
            ranking_system=str(item.get("ranking_system", ""))[:180],
            ranking_version=str(item.get("ranking_version", ""))[:80],
            ranking_source_url=_url(item.get("ranking_source_url", "")),
            source_url=_url(item.get("source_url", "")),
            aliases_json=json.dumps(_list(item.get("aliases", []), limit=20), ensure_ascii=False),
            notes=str(item.get("notes", ""))[:1500],
            retrieval_channels_json=json.dumps(channels, ensure_ascii=False),
            enabled=bool(item.get("enabled", True)), is_seed=True,
        )
        db.add(row)
        by_name[_norm(name)] = row
        sources_added += 1
    version = str(payload.get("catalogue_version", ""))[:80]
    state = db.get(AcademicRegistryState, "default")
    if state is None:
        state = AcademicRegistryState(id="default")
        db.add(state)
    state.catalogue_version = version
    state.last_seeded_at = now()
    db.commit()
    return {"domains_added": domains_added, "sources_added": sources_added,
            "catalogue_version": version}


def list_domains(db, *, include_disabled=True):
    query = select(AcademicDomain)
    if not include_disabled:
        query = query.where(AcademicDomain.enabled.is_(True))
    rows = db.scalars(query.order_by(AcademicDomain.sort_order, AcademicDomain.name)).all()
    return [domain_dict(x) for x in rows]


def list_sources(db, *, q="", kind="", domain="", channel="", enabled=None, resolution_status=""):
    query = select(AcademicSource)
    if kind in ("journal", "conference"):
        query = query.where(AcademicSource.kind == kind)
    if enabled is not None:
        query = query.where(AcademicSource.enabled.is_(bool(enabled)))
    if resolution_status:
        query = query.where(AcademicSource.resolution_status == resolution_status)
    rows = db.scalars(query.order_by(AcademicSource.name.asc())).all()
    term = _norm(q)
    found = []
    for row in rows:
        domains = _json(row.domains_json, [])
        channels = _json(row.retrieval_channels_json, [])
        aliases = _json(row.aliases_json, [])
        if domain and domain not in domains:
            continue
        if channel and channel not in channels:
            continue
        haystack = " ".join([row.name, row.abbreviation, row.notes, row.rank_label] + aliases)
        if term and term not in _norm(haystack):
            continue
        found.append(source_dict(row))
    return found


def registry_summary(db):
    rows = db.scalars(select(AcademicSource)).all()
    domains = db.scalars(select(AcademicDomain).where(AcademicDomain.enabled.is_(True))).all()
    enabled = [x for x in rows if x.enabled]
    resolved = [x for x in enabled if x.resolution_status == "resolved" and x.openalex_source_id]
    return {
        "total": len(rows), "enabled": len(enabled), "disabled": len(rows) - len(enabled),
        "resolved": len(resolved),
        "unresolved": sum(x.resolution_status == "unresolved" for x in enabled),
        "ambiguous": sum(x.resolution_status == "ambiguous" for x in enabled),
        "not_found": sum(x.resolution_status == "not_found" for x in enabled),
        "errors": sum(x.resolution_status == "error" for x in enabled),
        "journals": sum(x.kind == "journal" for x in rows),
        "conferences": sum(x.kind == "conference" for x in rows),
        "domains": len(domains),
        "direct_enabled": sum(x.enabled and "direct" in _json(x.retrieval_channels_json, []) for x in rows),
        "method_enabled": sum(x.enabled and "method" in _json(x.retrieval_channels_json, []) for x in rows),
    }


def _validate_source_payload(db, payload, *, partial=False):
    values = {}
    if not partial or "name" in payload:
        name = str(payload.get("name", "")).strip()
        if not 3 <= len(name) <= 260:
            raise ValueError("来源名称需要 3–260 个字符")
        values["name"] = name
    if not partial or "kind" in payload:
        kind = payload.get("kind", "journal")
        if kind not in ("journal", "conference"):
            raise ValueError("来源类型只能是期刊或会议")
        values["kind"] = kind
    if not partial or "domains" in payload:
        domains = _list(payload.get("domains", []), limit=12, max_length=48, field="研究领域")
        if not domains:
            raise ValueError("至少选择一个研究领域")
        existing = {x.slug for x in db.scalars(select(AcademicDomain).where(AcademicDomain.enabled.is_(True))).all()}
        unknown = [x for x in domains if x not in existing]
        if unknown:
            raise ValueError("未知或已停用的领域：" + ", ".join(unknown))
        values["domains"] = domains
    if not partial or "retrieval_channels" in payload:
        channels = _list(payload.get("retrieval_channels", []), limit=2, max_length=16, field="检索通道")
        if any(x not in ("direct", "method") for x in channels):
            raise ValueError("检索通道只能是 direct 或 method")
        values["retrieval_channels"] = channels
    for key, max_len in (("abbreviation", 80), ("rank_label", 32),
                         ("ranking_system", 180), ("ranking_version", 80),
                         ("notes", 1500)):
        if not partial or key in payload:
            values[key] = str(payload.get(key, "") or "").strip()[:max_len]
    if not partial or "ranking_source_url" in payload:
        values["ranking_source_url"] = _url(payload.get("ranking_source_url", ""))
    if not partial or "source_url" in payload:
        values["source_url"] = _url(payload.get("source_url", ""))
    if not partial or "aliases" in payload:
        values["aliases"] = _list(payload.get("aliases", []), limit=20, max_length=180, field="别名")
    if not partial or "enabled" in payload:
        values["enabled"] = bool(payload.get("enabled", True))
    if "openalex_source_id" in payload:
        raw = str(payload.get("openalex_source_id", "") or "").strip()
        if raw:
            ident = _source_id(raw)
            if not ident:
                raise ValueError("OpenAlex Source ID 格式应为 S123456 或完整 Source URL")
            values["openalex_source_id"] = ident
        else:
            values["openalex_source_id"] = ""
    return values


def create_source(db, payload, actor=""):
    values = _validate_source_payload(db, payload)
    name_norm = _norm(values["name"])
    for row in db.scalars(select(AcademicSource)).all():
        if _norm(row.name) == name_norm:
            raise ValueError("该期刊/会议已存在")
    ident = "asrc_" + uuid.uuid4().hex[:28]
    row = AcademicSource(
        id=ident, name=values["name"], abbreviation=values["abbreviation"],
        kind=values["kind"], domains_json=json.dumps(values["domains"], ensure_ascii=False),
        rank_label=values["rank_label"] or "观察",
        ranking_system=values["ranking_system"], ranking_version=values["ranking_version"],
        ranking_source_url=values["ranking_source_url"], source_url=values["source_url"],
        aliases_json=json.dumps(values["aliases"], ensure_ascii=False), notes=values["notes"],
        retrieval_channels_json=json.dumps(values["retrieval_channels"], ensure_ascii=False),
        enabled=values["enabled"], created_by=actor,
    )
    if values.get("openalex_source_id"):
        row.openalex_source_id = values["openalex_source_id"]
        row.resolution_status = "resolved"
        row.resolution_note = "管理员手动指定 OpenAlex Source ID"
    db.add(row)
    db.flush()
    _revision(db, row, "created", actor)
    db.commit()
    return source_dict(row)


def update_source(db, ident, payload, actor=""):
    row = db.get(AcademicSource, ident)
    if row is None:
        raise ValueError("学术来源不存在")
    values = _validate_source_payload(db, payload, partial=True)
    if "name" in values:
        for other in db.scalars(select(AcademicSource).where(AcademicSource.id != ident)).all():
            if _norm(other.name) == _norm(values["name"]):
                raise ValueError("该期刊/会议名称已被其他来源使用")
    before = _snapshot(row)
    identity_changed = (
        ("name" in values and values["name"] != row.name) or
        ("abbreviation" in values and values["abbreviation"] != row.abbreviation) or
        ("aliases" in values and values["aliases"] != _json(row.aliases_json, []))
    )
    for key, value in values.items():
        if key in ("domains", "aliases", "retrieval_channels"):
            column = {"domains": "domains_json", "aliases": "aliases_json",
                      "retrieval_channels": "retrieval_channels_json"}[key]
            setattr(row, column, json.dumps(value, ensure_ascii=False))
        elif key == "openalex_source_id":
            row.openalex_source_id = value
            if value:
                row.resolution_status = "resolved"
                row.resolution_note = "管理员手动指定 OpenAlex Source ID"
                row.openalex_type = ""
            else:
                row.resolution_status = "unresolved"
                row.resolution_note = "管理员清空了来源 ID"
        else:
            setattr(row, key, value)
    manual_id_changed = ("openalex_source_id" in values and
                         values["openalex_source_id"] and
                         values["openalex_source_id"] != before.get("openalex_source_id"))
    if identity_changed and not manual_id_changed:
        row.openalex_source_id = ""
        row.openalex_type = ""
        row.resolution_status = "unresolved"
        row.resolution_note = "名称或别名已修改，等待重新核验"
    row.updated_at = now()
    _revision(db, row, "updated", actor, before)
    db.commit()
    return source_dict(row)


def create_domain(db, payload, actor=""):
    slug = str(payload.get("slug", "")).strip().lower()
    name = str(payload.get("name", "")).strip()
    if not re.fullmatch(r"[a-z0-9_]{2,48}", slug):
        raise ValueError("领域标识只能使用小写字母、数字和下划线")
    if not 2 <= len(name) <= 100:
        raise ValueError("领域名称需要 2–100 个字符")
    if db.get(AcademicDomain, slug):
        raise ValueError("领域标识已存在")
    channels = _list(payload.get("default_channels", []), limit=2, max_length=16, field="默认检索通道")
    if any(x not in ("direct", "method") for x in channels):
        raise ValueError("默认检索通道只能是 direct 或 method")
    row = AcademicDomain(
        slug=slug, name=name, group_name=str(payload.get("group_name", ""))[:100],
        description=str(payload.get("description", ""))[:500],
        default_channels_json=json.dumps(channels, ensure_ascii=False),
        sort_order=int(payload.get("sort_order", 500)), enabled=True, is_seed=False,
    )
    db.add(row)
    db.commit()
    return domain_dict(row)


def update_domain(db, slug, payload):
    row = db.get(AcademicDomain, slug)
    if row is None:
        raise ValueError("研究领域不存在")
    for key in ("name", "group_name", "description", "sort_order", "enabled"):
        if key in payload:
            value = payload[key]
            if key == "name" and (not isinstance(value, str) or not 2 <= len(value.strip()) <= 100):
                raise ValueError("领域名称需要 2–100 个字符")
            if key == "sort_order":
                value = max(0, min(9999, int(value)))
            setattr(row, key, value.strip() if isinstance(value, str) else value)
    if "default_channels" in payload:
        channels = _list(payload["default_channels"], limit=2, max_length=16, field="默认检索通道")
        if any(x not in ("direct", "method") for x in channels):
            raise ValueError("默认检索通道只能是 direct 或 method")
        row.default_channels_json = json.dumps(channels, ensure_ascii=False)
    row.updated_at = now()
    db.commit()
    return domain_dict(row)


def delete_domain(db, slug):
    row = db.get(AcademicDomain, slug)
    if row is None:
        raise ValueError("研究领域不存在")
    used = [x.name for x in db.scalars(select(AcademicSource)).all()
            if slug in _json(x.domains_json, [])]
    if used:
        raise ValueError("该领域仍被 " + str(len(used)) + " 个来源使用，请先调整来源领域或停用领域")
    db.delete(row)
    db.commit()
    return {"deleted": slug}


def source_history(db, ident, limit=40):
    rows = db.scalars(select(AcademicSourceRevision)
        .where(AcademicSourceRevision.source_id == ident)
        .order_by(AcademicSourceRevision.created_at.desc())
        .limit(max(1, min(limit, 100)))).all()
    return [{
        "id": x.id, "source_id": x.source_id, "actor_id": x.actor_id,
        "action": x.action, "before": _json(x.before_json, {}),
        "after": _json(x.after_json, {}),
        "created_at": x.created_at.isoformat() if x.created_at else None,
    } for x in rows]


def _openalex_candidates(row, client):
    terms = [x for x in (row.name, row.abbreviation) if x]
    exact_names = [row.name, row.abbreviation] + _json(row.aliases_json, [])
    wanted = {_norm(x) for x in exact_names if x}
    unique = {}
    for term in terms:
        params = {"search": term, "per-page": 25}
        if os.getenv("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        if os.getenv("OPENALEX_MAILTO"):
            params["mailto"] = os.environ["OPENALEX_MAILTO"]
        response = client.get("https://api.openalex.org/sources", params=params)
        response.raise_for_status()
        for item in response.json().get("results", []):
            names = [item.get("display_name", ""), item.get("abbreviated_title", "")]
            names.extend(item.get("alternate_titles") or [])
            if not wanted.intersection({_norm(x) for x in names if x}):
                continue
            source_type = str(item.get("type") or "").lower()
            if row.kind == "journal" and source_type != "journal":
                continue
            if row.kind == "conference" and source_type not in ("conference", "journal"):
                continue
            ident = _source_id(item.get("id"))
            if ident:
                unique[ident] = item
        if unique:
            break
    return [(item, ident) for ident, item in unique.items()]


def resolve_sources(db, source_ids=None, *, force=False, client=None, max_items=10, actor=""):
    """Resolve exact OpenAlex Source IDs; ambiguous matches are never guessed."""
    query = select(AcademicSource).where(AcademicSource.enabled.is_(True))
    if source_ids is not None:
        if not source_ids:
            return {"checked":0,"resolved":0,"ambiguous":0,"not_found":0,
                    "errors":0,"skipped":0,"items":[]}
        query = query.where(AcademicSource.id.in_(source_ids))
    elif force:
        query = query.where(AcademicSource.resolution_status!="resolved")
    else:
        query = query.where(AcademicSource.resolution_status=="unresolved")
    rows = db.scalars(query.order_by(AcademicSource.name.asc()).limit(max(1, min(max_items, 100)))).all()
    own = client is None
    http = client or httpx.Client(timeout=8, headers={
        "User-Agent": "research-opportunity-workbench/0.4"
    })
    summary = {"checked": 0, "resolved": 0, "ambiguous": 0, "not_found": 0,
               "errors": 0, "skipped": 0, "items": []}
    try:
        for row in rows:
            if row.resolution_status == "resolved" and row.openalex_source_id and not force:
                summary["skipped"] += 1
                continue
            if row.resolution_status in ("not_found", "ambiguous", "error") and not force:
                summary["skipped"] += 1
                continue
            summary["checked"] += 1
            before = _snapshot(row)
            try:
                matches = _openalex_candidates(row, http)
                if len(matches) == 1:
                    item, ident = matches[0]
                    row.openalex_source_id = ident
                    row.openalex_type = str(item.get("type") or "")
                    row.resolution_status = "resolved"
                    row.resolution_note = "名称/简称/别名与 OpenAlex 来源名称精确匹配"
                    summary["resolved"] += 1
                elif len(matches) > 1:
                    row.openalex_source_id = ""
                    row.openalex_type = ""
                    row.resolution_status = "ambiguous"
                    row.resolution_note = "存在多个精确匹配来源，需人工指定 OpenAlex Source ID"
                    summary["ambiguous"] += 1
                else:
                    row.openalex_source_id = ""
                    row.openalex_type = ""
                    row.resolution_status = "not_found"
                    row.resolution_note = "OpenAlex 未找到精确匹配；未采用模糊匹配"
                    summary["not_found"] += 1
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                row.resolution_status = "error"
                row.resolution_note = "OpenAlex 核验请求失败，请稍后重试"
                summary["errors"] += 1
            row.updated_at = now()
            _revision(db, row, "resolved", actor, before)
            db.commit()
            summary["items"].append({
                "id": row.id, "name": row.name, "status": row.resolution_status,
                "openalex_source_id": row.openalex_source_id,
                "note": row.resolution_note,
            })
    finally:
        if own:
            http.close()
    return summary


def resolved_source_ids_by_channel(db):
    result = {"direct": [], "method": []}
    rows = db.scalars(select(AcademicSource).where(
        AcademicSource.enabled.is_(True),
        AcademicSource.resolution_status == "resolved",
    ).order_by(AcademicSource.name.asc())).all()
    for row in rows:
        ident = _source_id(row.openalex_source_id)
        if not ident:
            continue
        for channel in _json(row.retrieval_channels_json, []):
            if channel in result and ident not in result[channel]:
                result[channel].append(ident)
    return result


def _csv_bool(value, default=True):
    if value is None or not str(value).strip():
        return default
    return str(value).strip().casefold() in ("1", "true", "yes", "y", "是", "启用", "enabled")


def import_sources_csv(db, csv_text, actor=""):
    if not isinstance(csv_text, str) or not csv_text.strip() or len(csv_text) > 300000:
        raise ValueError("CSV 内容为空或超过 300 KB")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames or "name" not in {x.strip().lower() for x in reader.fieldnames}:
        raise ValueError("CSV 必须包含 name 列")
    headers = {x.strip().lower(): x for x in reader.fieldnames}
    counts = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
    for line_no, raw in enumerate(reader, start=2):
        if line_no > 1002:
            counts["errors"].append({"row": line_no, "error": "单次最多导入 1000 条"})
            break
        row_data = {key: raw.get(column, "") for key, column in headers.items()}
        name = str(row_data.get("name", "")).strip()
        if not name:
            counts["skipped"] += 1
            continue
        domains = [x.strip() for x in re.split(r"[|;；,，]+", row_data.get("domains", "")) if x.strip()]
        channels = [x.strip().lower() for x in re.split(r"[|;；,，]+", row_data.get("retrieval_channels", "")) if x.strip()]
        aliases = [x.strip() for x in re.split(r"[|;；]+", row_data.get("aliases", "")) if x.strip()]
        if not domains:
            domains = ["urban_planning"]
        if not channels:
            channels = []
            for slug in domains:
                domain = db.get(AcademicDomain, slug)
                if domain:
                    channels.extend(_json(domain.default_channels_json, []))
            channels = list(dict.fromkeys(channels))
        payload = {
            "name": name, "abbreviation": row_data.get("abbreviation", ""),
            "kind": (row_data.get("kind", "journal") or "journal").strip().lower(),
            "domains": domains, "rank_label": row_data.get("rank_label", "观察") or "观察",
            "ranking_system": row_data.get("ranking_system", ""),
            "ranking_version": row_data.get("ranking_version", ""),
            "ranking_source_url": row_data.get("ranking_source_url", ""),
            "source_url": row_data.get("source_url", ""), "aliases": aliases,
            "notes": row_data.get("notes", ""),
            "retrieval_channels": channels,
            "enabled": _csv_bool(row_data.get("enabled"), True),
        }
        if str(row_data.get("openalex_source_id", "")).strip():
            payload["openalex_source_id"] = str(row_data["openalex_source_id"]).strip()
        existing = next((x for x in db.scalars(select(AcademicSource)).all()
                         if _norm(x.name) == _norm(name)), None)
        try:
            if existing:
                update_source(db, existing.id, payload, actor)
                counts["updated"] += 1
            else:
                create_source(db, payload, actor)
                counts["created"] += 1
        except ValueError as exc:
            counts["errors"].append({"row": line_no, "name": name[:120], "error": str(exc)})
    return counts


def export_sources_csv(db):
    fields = ["name", "abbreviation", "kind", "domains", "rank_label",
              "ranking_system", "ranking_version", "ranking_source_url", "source_url", "aliases",
              "notes", "retrieval_channels", "enabled", "openalex_source_id",
              "resolution_status"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in db.scalars(select(AcademicSource).order_by(AcademicSource.name.asc())).all():
        item = source_dict(row)
        writer.writerow({
            "name": item["name"], "abbreviation": item["abbreviation"],
            "kind": item["kind"], "domains": "|".join(item["domains"]),
            "rank_label": item["rank_label"], "ranking_system": item["ranking_system"],
            "ranking_version": item["ranking_version"], "ranking_source_url": item["ranking_source_url"],
            "source_url": item["source_url"],
            "aliases": "|".join(item["aliases"]), "notes": item["notes"],
            "retrieval_channels": "|".join(item["retrieval_channels"]),
            "enabled": str(item["enabled"]).lower(),
            "openalex_source_id": item["openalex_source_id"],
            "resolution_status": item["resolution_status"],
        })
    return out.getvalue()


def registry_state(db):
    row = db.get(AcademicRegistryState, "default")
    return {"catalogue_version": row.catalogue_version if row else "",
            "last_seeded_at": row.last_seeded_at.isoformat() if row and row.last_seeded_at else None}
