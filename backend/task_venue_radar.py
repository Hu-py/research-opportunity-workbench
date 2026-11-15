"""Task-scoped journal discovery for ONE child-health extrapolation pilot.

This module proposes new journals from real OpenAlex work-source metadata,
keeps a durable source/evidence snapshot, and requires authenticated human
review before adding a venue to this member's task-only directory.

The global research_sources registry, Team Profile and other research tasks are
never modified. Search/quality judgements are not made by an LLM in V0.1.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base, normalize_paper, query_openalex
from backend.research_sources import ResearchSource
from backend.team import TeamMember, add_audit

TASK_KEY = "child_health_extrapolation"
TASK_TITLE = "儿童健康空间外推"
QUERY_VERSION = "2026-11-15.v1"
# Configured for this first pilot. Other topics do NOT inherit this directory.
BASELINE = {
    "A": ("Cities", "Sustainable Cities and Society", "Landscape and Urban Planning"),
    "B": ("Computers, Environment and Urban Systems",
          "Environment and Planning B: Urban Analytics and City Science",
          "International Journal of Geographical Information Science"),
    "C": ("Journal of Machine Learning Research",
          "IEEE Transactions on Neural Networks and Learning Systems",
          "IEEE Transactions on Knowledge and Data Engineering"),
}
QUERIES = {
    "A": ("child health built environment urban neighborhood",
          "early childhood development green space urban"),
    "B": ("spatial generalization urban health prediction",
          "geographical transfer learning environmental health"),
    "C": ("graph out of distribution generalization spatial",
          "domain adaptation geospatial prediction machine learning"),
}
MAX_QUERIES = 6
PER_QUERY = 40
MAX_CANDIDATES_PER_GROUP = 8
API_URL = "https://api.openalex.org/works"
SOURCE_ID = re.compile(r"^https://openalex\.org/(S\d+)$")
NO_SCORE = "未评定质量；仅依据该检索计划返回的论文相关性线索排序"
KEYWORDS = ("child", "health", "urban", "environment", "spatial", "graph", "geospatial")


def utcnow():
    return datetime.now(timezone.utc)


def dump(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def load(data):
    try:
        return json.loads(data or "{}")
    except (TypeError, ValueError):
        return {}


def label(value, limit=240):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def stable_id(member_id, source_id):
    return "jv_" + hashlib.sha256((member_id + "\x00" + TASK_KEY + "\x00" + source_id).encode()).hexdigest()[:40]


def directory_id(member_id, source_id):
    return "jd_" + hashlib.sha256((member_id + "\x00" + TASK_KEY + "\x00" + source_id).encode()).hexdigest()[:40]


class TaskVenueRun(Base):
    __tablename__ = "task_venue_discovery_runs"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("team_members.id"), index=True)
    task_key: Mapped[str] = mapped_column(String(90), default=TASK_KEY)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    plan_version: Mapped[str] = mapped_column(String(50), default=QUERY_VERSION)
    queries_json: Mapped[str] = mapped_column(Text, default="{}")
    requests_made: Mapped[int] = mapped_column(Integer, default=0)
    works_seen: Mapped[int] = mapped_column(Integer, default=0)
    proposals_created: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskVenueCandidate(Base):
    __tablename__ = "task_venue_candidates"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("team_members.id"), index=True)
    task_key: Mapped[str] = mapped_column(String(90), default=TASK_KEY)
    openalex_source_id: Mapped[str] = mapped_column(String(30))
    display_name: Mapped[str] = mapped_column(String(260))
    probe_group: Mapped[str] = mapped_column(String(1))
    issn_l: Mapped[str] = mapped_column(String(25), default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    discovered_run_id: Mapped[str] = mapped_column(String(60), default="")
    proposer: Mapped[str] = mapped_column(String(20), default="openalex_search")
    reviewer_id: Mapped[str] = mapped_column(String(36), default="")
    review_reason: Mapped[str] = mapped_column(String(700), default="")
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskVenueDirectory(Base):
    __tablename__ = "task_venue_directory"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("team_members.id"), index=True)
    task_key: Mapped[str] = mapped_column(String(90), default=TASK_KEY)
    openalex_source_id: Mapped[str] = mapped_column(String(30))
    display_name: Mapped[str] = mapped_column(String(260))
    probe_group: Mapped[str] = mapped_column(String(1))
    candidate_id: Mapped[str] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(default=True)
    approved_by: Mapped[str] = mapped_column(String(36))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status_note: Mapped[str] = mapped_column(String(500), default="")


class TaskVenuePaperRun(Base):
    __tablename__ = "task_venue_paper_runs"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(36), ForeignKey("team_members.id"), index=True)
    task_key: Mapped[str] = mapped_column(String(90), default=TASK_KEY)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    source_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    results_json: Mapped[str] = mapped_column(Text, default="[]")
    error_summary: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VenueReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    reason: str = Field(min_length=5, max_length=500)


class DirectoryStatusRequest(BaseModel):
    action: str = Field(pattern="^(pause|resume)$")
    reason: str = Field(min_length=5, max_length=300)


def run_dict(row: TaskVenueRun) -> dict:
    return {"id": row.id, "status": row.status, "plan_version": row.plan_version,
            "queries": load(row.queries_json), "requests_made": row.requests_made,
            "works_seen": row.works_seen, "proposals_created": row.proposals_created,
            "error_summary": row.error_summary, "created_at": row.created_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else None}


def candidate_dict(row: TaskVenueCandidate) -> dict:
    evidence = load(row.evidence_json)
    return {"id": row.id, "name": row.display_name, "openalex_source_id": row.openalex_source_id,
            "source_url": "https://openalex.org/" + row.openalex_source_id,
            "issn_l": row.issn_l, "probe_group": row.probe_group,
            "status": row.status, "proposer": row.proposer,
            "evidence": evidence, "review_reason": row.review_reason,
            "discovered_run_id": row.discovered_run_id,
            "discovered_at": row.discovered_at.isoformat(),
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "quality_label": NO_SCORE}


def directory_dict(row: TaskVenueDirectory) -> dict:
    return {"id": row.id, "name": row.display_name,
            "openalex_source_id": row.openalex_source_id,
            "url": "https://openalex.org/" + row.openalex_source_id,
            "probe_group": row.probe_group, "candidate_id": row.candidate_id,
            "active": row.active, "approved_at": row.approved_at.isoformat(),
            "status_note": row.status_note}


def baseline_sources(db):
    rows = db.scalars(select(ResearchSource).where(ResearchSource.enabled.is_(True))).all()
    known = {re.sub(r"[^a-z0-9]+", "", x.name.lower()): x for x in rows if x.kind == "journal"}
    result = []
    for group, names in BASELINE.items():
        for name in names:
            key = re.sub(r"[^a-z0-9]+", "", name.lower())
            row = known.get(key)
            result.append({
                "name": name, "probe_group": group,
                "registry_id": row.id if row else None,
                "openalex_source_id": row.openalex_source_id if row and row.resolution_status == "resolved" else None,
                "resolution_status": row.resolution_status if row else "not_in_global_registry",
                "origin": "existing_curated_baseline",
            })
    return result


def enabled_source_ids(db, member_id):
    approved = db.scalars(select(TaskVenueDirectory).where(
        TaskVenueDirectory.member_id == member_id, TaskVenueDirectory.task_key == TASK_KEY,
        TaskVenueDirectory.active.is_(True))).all()
    base = baseline_sources(db)
    groups = {}
    for key in BASELINE:
        entries = [x["openalex_source_id"] for x in base
                   if x["probe_group"] == key and x["openalex_source_id"]]
        entries += [x.openalex_source_id for x in approved if x.probe_group == key]
        groups[key] = list(dict.fromkeys(entries))[:30]
    return groups


def create_discovery_run(db, member):
    recent = db.scalars(select(TaskVenueRun).where(
        TaskVenueRun.member_id == member.id,
        TaskVenueRun.task_key == TASK_KEY
    ).order_by(TaskVenueRun.created_at.desc()).limit(1)).all()
    if recent:
        row = recent[0]
        if row.status in ("queued", "running"):
            raise ValueError("已有尚未结束的探索任务")
        prev = row.created_at
        if prev.tzinfo is None:
            prev = prev.replace(tzinfo=timezone.utc)
        if (utcnow() - prev).total_seconds() < 300:
            raise ValueError("为保护 OpenAlex 请求额度，请至少间隔五分钟重新探索")
    row = TaskVenueRun(id="jrun_" + uuid.uuid4().hex[:28], member_id=member.id,
                       queries_json=dump(QUERIES))
    db.add(row)
    add_audit(db, "task_venues.discovery_requested", member.id, row.id,
              "task=child_health_extrapolation; max_queries=6; model_calls=0")
    db.commit()
    return row


def _api_works(group, query, http):
    params = {
        "search": query,
        "filter": "from_publication_date:2022-01-01,primary_location.source.type:journal",
        "per-page": PER_QUERY,
        "select": "id,display_name,doi,publication_year,primary_location,cited_by_count",
    }
    if os.getenv("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    if os.getenv("OPENALEX_MAILTO"):
        params["mailto"] = os.environ["OPENALEX_MAILTO"]
    response = http.get(API_URL, params=params)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError("OpenAlex result format invalid")
    return data["results"][:PER_QUERY]


def build_candidates(works_by_query):
    """Candidates are only source-backed discovery leads, never rankings."""
    collected = {}
    for group, query, works in works_by_query:
        for work in works:
            if not isinstance(work, dict):
                continue
            source = ((work.get("primary_location") or {}).get("source") or {})
            matched = SOURCE_ID.fullmatch(str(source.get("id") or ""))
            if not matched or source.get("type") != "journal":
                continue
            sid = matched.group(1)
            name = label(source.get("display_name"), 260)
            if not name:
                continue
            url = str(work.get("doi") or work.get("id") or "")
            if not url.startswith("https://"):
                continue
            title = label(work.get("display_name"), 230)
            if not title:
                continue
            key = (group, sid)
            e = collected.setdefault(key, {"probe_group": group,
                "source_id": sid, "name": name,
                "issn_l": label(source.get("issn_l"), 25),
                "queries": set(), "papers": {}})
            e["queries"].add(query)
            wid = str(work.get("id") or url)
            e["papers"][wid] = {
                "title": title, "url": url,
                "year": work.get("publication_year"),
                "work_id": wid, "query": query,
            }
    observed = []
    for (group, sid), item in collected.items():
        count = len(item["papers"])
        if count < 2:
            continue
        evidence = {
            "found_in_queries": sorted(item["queries"]),
            "observed_paper_count": count,
            "distinct_query_count": len(item["queries"]),
            "sample_papers": list(item["papers"].values())[:4],
            "search_plan": QUERY_VERSION,
            "source_type": "journal",
            "source_provider": "OpenAlex",
            "basis": "以六条有界检索的相关论文出现频次推荐阅读，不代表期刊质量或正式收录排名",
        }
        observed.append({
            "source_id": sid, "name": item["name"],
            "issn_l": item["issn_l"], "group": group,
            "evidence": evidence,
        })
    # One candidate per canonical OpenAlex source, even if relevant to
    # multiple probes. Keep the strongest probe as its primary slot and
    # preserve the other probe memberships as evidence, not separate votes.
    strongest = {}
    memberships = defaultdict(set)
    for value in observed:
        sid = value["source_id"]
        memberships[sid].add(value["group"])
        old = strongest.get(sid)
        signal = (value["evidence"]["distinct_query_count"],
                  value["evidence"]["observed_paper_count"])
        old_signal = ((old["evidence"]["distinct_query_count"],
                       old["evidence"]["observed_paper_count"])
                      if old else (-1, -1))
        if signal > old_signal:
            strongest[sid] = value
    by_group = defaultdict(list)
    for source_id, value in strongest.items():
        value["evidence"]["associated_probe_groups"] = sorted(memberships[source_id])
        by_group[value["group"]].append(value)
    result = []
    for group in BASELINE:
        options = sorted(by_group[group], key=lambda v: (
            -v["evidence"]["distinct_query_count"],
            -v["evidence"]["observed_paper_count"], v["name"]))
        result.extend(options[:MAX_CANDIDATES_PER_GROUP])
    return result

def execute_discovery(factory, run_id, client=None):
    with factory() as db:
        run = db.get(TaskVenueRun, run_id)
        if run is None or run.status != "queued":
            return
        run.status = "running"
        member_id = run.member_id
        db.commit()
    observed = []
    errors = []
    requested = 0
    own = client is None
    http = client or httpx.Client(timeout=12, headers={
        "User-Agent": "ResearchAtlas/TaskVenueRadar-0.1"})
    try:
        for group, queries in QUERIES.items():
            for query in queries:
                requested += 1
                try:
                    works = _api_works(group, query, http)
                    observed.append((group, query, works))
                except (httpx.HTTPError, ValueError, TypeError):
                    errors.append(group + ":OpenAlex 查询暂不可用或格式不匹配")
        # Never claim success if every API request failed.
        prepared = build_candidates(observed)
        created = 0
        with factory() as db:
            run = db.get(TaskVenueRun, run_id)
            global_baseline = {re.sub(r"[^a-z0-9]+", "", x["name"].lower())
                               for x in baseline_sources(db)}
            approved_sources = {
                x.openalex_source_id for x in db.scalars(
                    select(TaskVenueDirectory).where(
                        TaskVenueDirectory.member_id == member_id,
                        TaskVenueDirectory.task_key == TASK_KEY)
                ).all()
            }
            for item in prepared:
                normalized = re.sub(r"[^a-z0-9]+", "", item["name"].lower())
                if normalized in global_baseline or item["source_id"] in approved_sources:
                    continue
                key = stable_id(member_id, item["source_id"])
                candidate = db.get(TaskVenueCandidate, key)
                if candidate is not None and candidate.status != "pending":
                    continue
                if candidate is None:
                    candidate = TaskVenueCandidate(
                        id=key, member_id=member_id, openalex_source_id=item["source_id"],
                        task_key=TASK_KEY, display_name=item["name"],
                        probe_group=item["group"], issn_l=item["issn_l"],
                        evidence_json=dump(item["evidence"]), discovered_run_id=run_id,
                    )
                    db.add(candidate)
                    created += 1
                else:
                    candidate.evidence_json = dump(item["evidence"])
                    candidate.discovered_run_id = run_id
            run.requests_made = requested
            run.works_seen = sum(len(w) for _, _, w in observed)
            run.proposals_created = created
            run.error_summary = "; ".join(errors)[:200]
            run.status = "failed" if len(errors) == requested else "partial" if errors else "completed"
            run.finished_at = utcnow()
            add_audit(db, "task_venues.discovery_finished", member_id, run_id,
                      "status=" + run.status + ";new=" + str(created))
            db.commit()
    finally:
        if own:
            http.close()


def review(db, member, candidate_id, decision, reason):
    row = db.get(TaskVenueCandidate, candidate_id)
    if row is None or row.member_id != member.id or row.task_key != TASK_KEY:
        raise KeyError("候选期刊不存在")
    if row.status != "pending":
        raise ValueError("期刊已经完成审批；不可重复审批或隐式覆盖历史")
    row.status = "approved" if decision == "approve" else "rejected"
    row.reviewer_id = member.id
    row.review_reason = reason
    row.reviewed_at = utcnow()
    if decision == "approve":
        key = directory_id(member.id, row.openalex_source_id)
        if db.get(TaskVenueDirectory, key):
            raise ValueError("期刊已经加入这个研究任务")
        db.add(TaskVenueDirectory(
            id=key, member_id=member.id, task_key=TASK_KEY,
            openalex_source_id=row.openalex_source_id, display_name=row.display_name,
            probe_group=row.probe_group, candidate_id=row.id,
            approved_by=member.id, status_note=reason,
        ))
    add_audit(db, "task_venues.human_review", member.id, row.id,
              "task=" + TASK_KEY + ";decision=" + decision + ";reason=" + label(reason, 180))
    db.commit()
    return candidate_dict(row)


def create_paper_run(db, member):
    groups = enabled_source_ids(db, member.id)
    if not any(groups.values()):
        raise ValueError("尚无已解析或获批的期刊来源 ID，不能执行严格目录内检索")
    row = TaskVenuePaperRun(
        id="jpaper_" + uuid.uuid4().hex[:26], member_id=member.id,
        source_ids_json=dump(groups))
    db.add(row)
    add_audit(db, "task_venues.strict_scan_requested", member.id, row.id,
              "task=" + TASK_KEY + ";approved_or_resolved_source_count=" +
              str(sum(map(len, groups.values()))))
    db.commit()
    return row


def execute_paper_scan(factory, run_id, client=None):
    with factory() as db:
        row = db.get(TaskVenuePaperRun, run_id)
        if row is None or row.status != "queued":
            return
        row.status = "running"
        source_ids = load(row.source_ids_json)
        db.commit()
    items = []
    errors = []
    seen = set()
    for group, ids in source_ids.items():
        if not ids:
            continue
        for query in QUERIES[group][:2]:
            try:
                results = query_openalex(query, "2023-01-01", limit=15, client=client, source_ids=ids)
                for work in results:
                    pid = str(work.get("id") or "")
                    if not pid or pid in seen:
                        continue
                    seen.add(pid)
                    paper = normalize_paper(work)
                    if paper["title"] and paper["url"].startswith("https://"):
                        items.append({**paper, "probe_group": group, "query": query})
            except (httpx.HTTPError, ValueError, TypeError):
                errors.append(group + " 目录内检索失败")
    with factory() as db:
        row = db.get(TaskVenuePaperRun, run_id)
        row.results_json = dump(items[:100])
        row.error_summary = "; ".join(errors)[:200]
        row.status = "partial" if items and errors else "failed" if errors else "completed"
        row.finished_at = utcnow()
        db.commit()


def mount(app, *, get_db, require_actor, team_auth_enabled, get_factory):
    router = APIRouter(prefix="/api/personal-research/me/journal-radar",
                       tags=["SC02 Child Health Task Journal Radar"])

    def member(actor: TeamMember | None = Depends(require_actor)):
        if not team_auth_enabled() or actor is None or not actor.active:
            raise HTTPException(401, "团队登录后才能管理个人科研任务期刊")
        return actor

    @router.get("")
    def overview(db: Session = Depends(get_db), actor: TeamMember = Depends(member)):
        candidates = db.scalars(select(TaskVenueCandidate).where(
            TaskVenueCandidate.member_id == actor.id,
            TaskVenueCandidate.task_key == TASK_KEY).order_by(
            TaskVenueCandidate.discovered_at.desc()).limit(100)).all()
        approved = db.scalars(select(TaskVenueDirectory).where(
            TaskVenueDirectory.member_id == actor.id,
            TaskVenueDirectory.task_key == TASK_KEY).order_by(
            TaskVenueDirectory.approved_at.desc()).limit(100)).all()
        runs = db.scalars(select(TaskVenueRun).where(
            TaskVenueRun.member_id == actor.id,
            TaskVenueRun.task_key == TASK_KEY).order_by(
            TaskVenueRun.created_at.desc()).limit(12)).all()
        scans = db.scalars(select(TaskVenuePaperRun).where(
            TaskVenuePaperRun.member_id == actor.id,
            TaskVenuePaperRun.task_key == TASK_KEY).order_by(
            TaskVenuePaperRun.created_at.desc()).limit(5)).all()
        return {
            "task_key": TASK_KEY, "title": TASK_TITLE,
            "baseline": baseline_sources(db),
            "candidates": [candidate_dict(x) for x in candidates],
            "directory": [directory_dict(x) for x in approved],
            "active_source_ids": enabled_source_ids(db, actor.id),
            "runs": [run_dict(x) for x in runs],
            "paper_runs": [{
                "id": x.id, "status": x.status, "source_ids": load(x.source_ids_json),
                "papers": load(x.results_json), "error_summary": x.error_summary,
                "created_at": x.created_at.isoformat()} for x in scans],
            "search_plan": {key: list(queries) for key, queries in QUERIES.items()},
            "limits": {"queries_per_discovery": MAX_QUERIES,
                       "results_per_query": PER_QUERY,
                       "llm_calls": 0, "automated_approval": False},
            "note": "只对儿童健康空间外推个人任务生效。OpenAlex 来源归类是待审证据；人工审批才进入任务目录，不修改全局期刊库。",
        }

    @router.post("/discover", status_code=202)
    def discover(background: BackgroundTasks, db: Session = Depends(get_db),
                 actor: TeamMember = Depends(member)):
        try:
            run = create_discovery_run(db, actor)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        background.add_task(execute_discovery, get_factory(), run.id)
        return run_dict(run)

    @router.post("/candidates/{candidate_id}/review")
    def decide(candidate_id: str, data: VenueReviewRequest,
               db: Session = Depends(get_db), actor: TeamMember = Depends(member)):
        try:
            return review(db, actor, candidate_id, data.decision, data.reason.strip())
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc

    @router.post("/directory/{entry_id}/status")
    def status(entry_id: str, data: DirectoryStatusRequest,
               db: Session = Depends(get_db), actor: TeamMember = Depends(member)):
        row = db.get(TaskVenueDirectory, entry_id)
        if not row or row.member_id != actor.id or row.task_key != TASK_KEY:
            raise HTTPException(404, "研究任务期刊不存在")
        row.active = (data.action == "resume")
        row.status_note = data.reason.strip()
        add_audit(db, "task_venues.directory_status", actor.id, row.id,
                  data.action + ": " + label(data.reason, 200))
        db.commit()
        return directory_dict(row)

    @router.post("/scan-approved", status_code=202)
    def scan_approved(background: BackgroundTasks, db: Session = Depends(get_db),
                      actor: TeamMember = Depends(member)):
        try:
            run = create_paper_run(db, actor)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        background.add_task(execute_paper_scan, get_factory(), run.id)
        return {"id": run.id, "status": run.status, "source_ids": load(run.source_ids_json),
                "note": "冻结已获批目录的来源 ID 快照，仅在该目录内检索；不执行 LLM 分析"}

    app.include_router(router)
