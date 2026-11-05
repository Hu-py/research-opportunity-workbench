"""Separately stored, user-curated research interests.

Interests are NOT verified team achievements or official research lines.
Weekly OpenAlex scans supplement the existing profile-based weekly workflow.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base, Paper, normalize_paper, query_openalex
from backend.openalex_errors import safe_openalex_error

def now():
    return datetime.now(timezone.utc)

def decode(value, default=None):
    try:
        return json.loads(value) if value else (default if default is not None else [])
    except (TypeError, ValueError):
        return default if default is not None else []

class ResearchInterest(Base):
    __tablename__ = "research_interests"
    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    focus: Mapped[str] = mapped_column(String(32), default="applied")
    problem: Mapped[str] = mapped_column(Text, default="")
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    queries_json: Mapped[str] = mapped_column(Text, default="[]")
    venues_json: Mapped[str] = mapped_column(Text, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(48), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(24), default="never")
    last_new: Mapped[int] = mapped_column(default=0)

def as_dict(row: ResearchInterest):
    return {
        "id": row.id, "title": row.title, "focus": row.focus, "problem": row.problem,
        "keywords": decode(row.keywords_json), "queries": decode(row.queries_json),
        "venues": decode(row.venues_json), "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "last_status": row.last_status, "last_new": row.last_new,
    }

def create_interest(db, payload: dict, actor: str = ""):
    # Queries are optional hints; the LLM derives the actual search plan.
    queries = [q.strip() for q in payload.get("queries", []) if q.strip()]
    row = ResearchInterest(
        id=str(uuid.uuid4()), title=payload["title"].strip(),
        focus=payload["focus"], problem=payload["problem"].strip(),
        keywords_json=json.dumps([s.strip() for s in payload["keywords"] if s.strip()], ensure_ascii=False),
        queries_json=json.dumps(list(dict.fromkeys(queries)), ensure_ascii=False),
        venues_json=json.dumps([s.strip() for s in payload["venues"] if s.strip()], ensure_ascii=False),
        enabled=payload["enabled"], created_by=actor,
    )
    db.add(row)
    db.commit()
    return as_dict(row)

def recent_papers(db, interest_id: str, limit: int = 4):
    # A bounded read of the existing bibliography; do not echo private metadata.
    tag = "interest:" + interest_id
    papers = db.scalars(select(Paper).where(Paper.line_ids.like('%"' + tag + '"%'))
                       .order_by(Paper.published.desc()).limit(limit)).all()
    found = []
    for p in papers:
        found.append({"id":p.id, "title":p.title, "url":p.url,
                      "published":p.published, "venue":p.venue})
        if len(found) >= limit:
            break
    return found

def ingest_interests(db, days=14, per_query=6, client=None, interest_ids=None, max_interests=8):
    """Bounded OpenAlex collection; literature is not marked human-reviewed.

    The weekly CLI processes at most eight enabled interests and two
    search queries per interest. Each batch is idempotent by normalized ID.
    """
    import httpx
    from datetime import date, timedelta
    if not 1 <= days <= 365 or not 1 <= per_query <= 12:
        raise ValueError("Invalid interest scan limits")
    q = select(ResearchInterest).where(ResearchInterest.enabled.is_(True))
    if interest_ids is not None:
        q = q.where(ResearchInterest.id.in_(interest_ids))
    rows = db.scalars(q.order_by(ResearchInterest.created_at.desc()).limit(max_interests)).all()
    since = (date.today() - timedelta(days=days)).isoformat()
    summary = {"interests":len(rows), "requests":0, "new_papers":0, "errors":0}
    for row in rows:
        errors = 0
        new = 0
        for search in decode(row.queries_json)[:2]:
            summary["requests"] += 1
            try:
                works = query_openalex(search, since, limit=per_query, client=client)
                for work in works:
                    paper = normalize_paper(work)
                    if not paper["title"] or not paper["url"].startswith("https://"):
                        continue
                    tag = "interest:" + row.id
                    old = db.get(Paper, paper["id"])
                    if old is None:
                        db.add(Paper(**paper, line_ids=json.dumps([tag])))
                        db.flush()  # prevent duplicate PK across search terms/interests
                        new += 1
                        summary["new_papers"] += 1
                    else:
                        existing = decode(old.line_ids)
                        if tag not in existing:
                            existing.append(tag)
                            old.line_ids = json.dumps(existing, ensure_ascii=False)
            except (httpx.HTTPError, ValueError) as exc:
                # Do not persist external URLs, API keys, or private query strings.
                _ = safe_openalex_error(exc, bool(os.getenv("OPENALEX_API_KEY")))
                errors += 1
                summary["errors"] += 1
        row.last_checked_at = now()
        row.last_status = "partial" if errors and errors < min(2,len(decode(row.queries_json))) else (
            "failed" if errors else "completed")
        row.last_new = new
        db.commit()
    return summary

def interest_brief_section(db, days=7):
    from datetime import date, timedelta
    cutoff=(date.today()-timedelta(days=days)).isoformat()
    rows=db.scalars(select(ResearchInterest).where(ResearchInterest.enabled.is_(True))
                    .order_by(ResearchInterest.created_at.desc()).limit(30)).all()
    lines=["", "## 手动关注的研究兴趣与计算机前沿", "",
           "> 兴趣分支由团队成员手动添加，与已核验团队成果和正式研究画像分开存储。顶会名称目前只是观察清单，尚未经过正式的 venue 验证。", ""]
    if not rows:
        lines.append("尚无已开启的兴趣分支。")
    for row in rows:
        lines.extend(["### " + row.title, "", "领域：" + row.focus +
                      " · 上次扫描：" + row.last_status, ""])
        found=[p for p in recent_papers(db,row.id,limit=6) if p["published"]>=cutoff]
        if not found:
            lines.append("本周尚无该分支已收录文献（可能尚未执行检索）。")
        for p in found:
            title=p["title"].replace("[","\\[").replace("]","\\]")
            lines.append("- ["+title+"]("+p["url"]+") · "+p["published"]+
                         " · "+(p["venue"] or "来源待核验"))
        lines.append("")
    return lines
