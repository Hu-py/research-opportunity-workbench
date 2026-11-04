"""Bounded, evidence-labeled first retrieval sample for human quality review.

This never promotes unreviewed literature into the team's verified paper
corpus or calls a paid LLM. It samples actual PostgreSQL profile/draft queries,
persists public bibliographic metadata only, and retains explicit errors.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from research_workbench.core import Base, get_profile, normalize_paper, query_openalex
from backend.profile_intelligence import ResearchProfileDraft

LOG = logging.getLogger("uvicorn.error")
_GENERIC = {"urban spatial research methods", "urban research methods"}
_SKIP = {"a", "an", "the", "for", "with", "and", "on", "in", "of",
         "using", "based", "study", "research", "methods", "method", "model"}


def utcnow():
    return datetime.now(timezone.utc)


class RadarTrialRun(Base):
    __tablename__ = "radar_trial_runs"
    id: Mapped[str] = mapped_column(String(45), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def trial_dict(row):
    if row is None:
        return None
    try:
        report = json.loads(row.result_json or "{}")
    except ValueError:
        report = {}
    return {"id": row.id, "status": row.status, "report": report,
            "error": row.error,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None}


def latest_trial(db):
    row = db.scalar(select(RadarTrialRun).order_by(
        RadarTrialRun.created_at.desc()).limit(1))
    return trial_dict(row)


def create_trial(db, *, startup=False):
    """A separate trial store; do not contaminate the approved paper library."""
    row = db.scalar(select(RadarTrialRun).order_by(
        RadarTrialRun.created_at.desc()).limit(1))
    if row is not None and row.status in ("queued", "running"):
        raise ValueError("已有试抓取任务运行中，请先查看结果")
    # Startup opt-in is strictly once per database, including after failure.
    if startup and row is not None:
        return None
    if row is not None and not startup and row.created_at:
        age = (utcnow() - row.created_at.replace(tzinfo=timezone.utc)
               if row.created_at.tzinfo is None
               else utcnow() - row.created_at)
        if age.total_seconds() < 300:
            raise ValueError("五分钟内已提交试抓取，避免重复占用检索额度")
    row = RadarTrialRun(id="trial_" + uuid.uuid4().hex[:24])
    db.add(row)
    db.commit()
    return row.id


def choose_queries(db, *, limit=4):
    """Prefer database-evidence drafts, with explicit provenance labels."""
    candidates = db.scalars(select(ResearchProfileDraft).where(
        ResearchProfileDraft.source.in_(["database_snapshot", "database_analyst"]),
        ResearchProfileDraft.status.in_(["draft", "applied"])
    ).order_by(ResearchProfileDraft.created_at.desc()).limit(20)).all()
    portrait = None
    source = "official_postgresql_profile"
    # Prefer the rule-based, evidence-linked database snapshot to any old
    # manually supplied profile or an unpublished analyst hypothesis.
    for item in candidates:
        if item.source == "database_snapshot":
            try:
                portrait = json.loads(item.profile_json)
            except (ValueError, TypeError):
                continue
            source = "database_evidence_draft:" + item.id
            break
    if not portrait:
        portrait = get_profile(db)
    if not portrait:
        return [], source
    all_queries = []
    for line in portrait.get("research_lines", []):
        if not isinstance(line, dict):
            continue
        ident = str(line.get("id", ""))[:100]
        title = str(line.get("name", ""))[:140]
        for key in ("search_queries", "method_queries"):
            for value in line.get(key, []):
                if not isinstance(value, str):
                    continue
                query = value.strip()
                if 5 <= len(query) <= 160 and query.casefold() not in _GENERIC:
                    all_queries.append({"query": query, "line_id": ident,
                                        "line_name": title, "type": key})
    if not all_queries and source.startswith("database_evidence"):
        # If a source-grounded draft has only generic placeholder queries,
        # try configured official queries without promoting its hypotheses.
        official = get_profile(db) or {}
        for line in official.get("research_lines", []):
            for value in (line.get("search_queries", []) +
                          line.get("method_queries", [])):
                if isinstance(value, str) and 5 <= len(value.strip()) <= 160:
                    if value.strip().casefold() not in _GENERIC:
                        all_queries.append({"query": value.strip(),
                                            "line_id": str(line.get("id", "")),
                                            "line_name": str(line.get("name", "")),
                                            "type": "official_fallback"})
        if all_queries:
            source += " + official_query_fallback"
    unique = []
    seen = set()
    for q in all_queries:
        if q["query"].casefold() in seen:
            continue
        seen.add(q["query"].casefold())
        unique.append(q)
        if len(unique) >= limit:
            break
    return unique, source


def _lexical_signal(query, paper):
    words = {t for t in re.findall(r"[a-z]{3,}", query.lower()) if t not in _SKIP}
    if not words:
        return "未评估"
    content = (paper["title"] + " " + paper["abstract"]).lower()
    hits = sum(bool(re.search(r"\\b" + re.escape(word) + r"\\b", content)) for word in words)
    return "字面相关候选" if hits >= max(1, (len(words) + 2)//3) else "需人工核对"


def execute_trial(factory, trial_id, *, client=None, days=60):
    with factory() as db:
        row = db.get(RadarTrialRun, trial_id)
        if row is None or row.status not in ("queued", "running"):
            return False
        row.status = "running"
        row.updated_at = utcnow()
        db.commit()
        try:
            queries, source = choose_queries(db)
            if not queries:
                raise ValueError("数据库画像没有具体的非占位检索表达式，请先在初步画像中核对并保存研究主线")
            since = (date.today() - timedelta(days=days)).isoformat()
            errors = []
            found = {}
            matched = 0
            for entry in queries:
                try:
                    works = query_openalex(entry["query"], since, 8, client=client)
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    # Log type, never a possibly secret-bearing request URL.
                    errors.append({"query_index": queries.index(entry) + 1,
                                   "error_type": type(exc).__name__})
                    continue
                for work in works:
                    paper = normalize_paper(work)
                    if not paper["title"] or not paper["url"].startswith("https://"):
                        continue
                    matched += 1
                    key = paper["id"]
                    signal = _lexical_signal(entry["query"], paper)
                    item = found.get(key)
                    if item is None:
                        found[key] = {
                            "id": paper["id"], "title": paper["title"][:300],
                            "url": paper["url"][:500], "doi": paper["doi"][:180],
                            "published": paper["published"],
                            "venue": paper["venue"][:230],
                            "has_abstract": bool(paper["abstract"]),
                            "signal": signal, "query_indices": [
                                queries.index(entry) + 1],
                        }
                    else:
                        idx = queries.index(entry) + 1
                        if idx not in item["query_indices"]:
                            item["query_indices"].append(idx)
                        if signal == "字面相关候选":
                            item["signal"] = signal
            items = sorted(found.values(),
                           key=lambda p: p["published"], reverse=True)
            report = {
                "source": source,
                "since": since,
                "queries": [{"index": i + 1, **q}
                            for i, q in enumerate(queries)],
                "query_count": len(queries),
                "matched": matched,
                "unique_papers": len(items),
                "with_doi": sum(bool(p["doi"]) for p in items),
                "with_abstract": sum(p["has_abstract"] for p in items),
                "with_venue": sum(bool(p["venue"]) for p in items),
                "lexically_relevant": sum(
                    p["signal"] == "字面相关候选" for p in items),
                "failed_queries": errors,
                "papers": items[:24],
                "method": "OpenAlex 最近 60 天；最多 4 条数据库画像检索式，每条 8 条；"
                          "只检查元数据完整性和词面相关性；"
                          "未进行人工相关性、会议等级、创新性或全文质量认证。",
                "next_step": "人工审核 DOI/摘要/研究问题后，才能把论文纳入正式选题和 LLM 阅读。",
            }
            row.result_json = json.dumps(report, ensure_ascii=False)
            row.status = "completed" if not errors else ("partial" if items else "failed")
            row.error = (str(len(errors)) + " 条 OpenAlex 检索失败（仅记录错误类型）") if errors else ""
            row.updated_at = utcnow()
            db.commit()
            LOG.info("RADAR_FIRST_SCAN status=%s queries=%d unique=%d doi=%d abstracts=%d lexical=%d failed=%d",
                     row.status, len(queries), len(items),
                     report["with_doi"], report["with_abstract"],
                     report["lexically_relevant"], len(errors))
            # Paper titles are public OpenAlex metadata, not private team data.
            for item in items[:4]:
                LOG.info("RADAR_FIRST_SCAN_PAPER title=%s doi=%s published=%s",
                         item["title"][:160], item["doi"], item["published"])
            return row.status in ("completed", "partial")
        except Exception as exc:
            db.rollback()
            row = db.get(RadarTrialRun, trial_id)
            row.status = "failed"
            row.error = (str(exc)[:240] if isinstance(exc, ValueError)
                         else "试抓取执行失败：" + type(exc).__name__)
            row.updated_at = utcnow()
            db.commit()
            LOG.warning("RADAR_FIRST_SCAN failed: %s", row.error)
            return False
