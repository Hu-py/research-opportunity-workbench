"""SC05 Owner-authenticated one-paper A/B experiments.

No frontend, no automatic model calls. PDF input is parsed into page text and
stored privately in PostgreSQL; only explicitly authorized background tasks
invoke the existing DeepSeek adapter. Raw model stage responses and usage are
checkpointed per attempt to make retries auditable and limit duplicate spend.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column
from research_workbench.core import Base, query_openalex
from backend.team import TeamMember, add_audit
from backend.model_gateway import ModelCallError, request_json
from backend.research_budget import reserve, record_usage, status as budget_status
from backend.sc05_paper_only import (
    run_paper, page_texts_from_pdf, FUTURE_HEADING,
    _chunks, extract_ledger, normalize_fact_kind,
    LITERATURE_SCHEMA_V1, LITERATURE_ASSESSMENT_SYSTEM_V1,
)
from backend.sc05_research_diagnosis import EvidenceError

MAX_TEXT=650000
MAX_PDF_BYTES=32000000
VERSION="sc05-eval-v0.2.0"


def pipeline_sha():
    """Pin source+prompts so a changed deploy cannot silently resume an old run."""
    folder=Path(__file__).resolve().parent
    h=hashlib.sha256()
    for name in ("sc05_eval_api.py","sc05_paper_only.py",
                 "sc05_science_gate.py","sc05_research_diagnosis.py",
                 "sc05_quality.py"):
        h.update((folder/name).read_bytes())
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc)


def archive_if_enabled(factory, run_id: str):
    """Best-effort R2 mirror after DB commit; never repeat a paid call for R2 errors."""
    if os.getenv("SC05_R2_ARCHIVE_ENABLED","false").strip().lower() not in ("1","true","yes"):
        return
    try:
        from backend.sc05_r2_artifacts import archive_run
        archive_run(factory, run_id)
    except Exception as exc:
        # No source text, account IDs, request metadata or credentials in logs.
        print("SC05 R2 archive warning: "+type(exc).__name__,flush=True)


def dump(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))


def load(text, default=None):
    try:return json.loads(text) if text else default
    except (TypeError,ValueError):return default


class SC05Case(Base):
    __tablename__="sc05_cases"
    id:Mapped[str]=mapped_column(String(55),primary_key=True)
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),index=True)
    title:Mapped[str]=mapped_column(String(300))
    pages_json:Mapped[str]=mapped_column(Text)
    source_sha:Mapped[str]=mapped_column(String(64))
    source_type:Mapped[str]=mapped_column(String(35))
    shared_evidence_json:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class SC05Run(Base):
    __tablename__="sc05_runs"
    id:Mapped[str]=mapped_column(String(55),primary_key=True)
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),index=True)
    case_id:Mapped[str]=mapped_column(String(55),ForeignKey("sc05_cases.id"))
    pair_id:Mapped[str]=mapped_column(String(55),index=True)
    variant:Mapped[str]=mapped_column(String(25))
    pipeline_sha:Mapped[str]=mapped_column(String(64))
    status:Mapped[str]=mapped_column(String(24),default="prepared")
    stage:Mapped[str]=mapped_column(String(40),default="prepare")
    checkpoints_json:Mapped[str]=mapped_column(Text,default="[]")
    report_md:Mapped[str]=mapped_column(Text,default="")
    result_json:Mapped[str]=mapped_column(Text,default="")
    calls:Mapped[int]=mapped_column(Integer,default=0)
    input_tokens:Mapped[int]=mapped_column(Integer,default=0)
    output_tokens:Mapped[int]=mapped_column(Integer,default=0)
    error:Mapped[str]=mapped_column(String(280),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class SC05Rating(Base):
    __tablename__="sc05_ratings"
    id:Mapped[str]=mapped_column(String(55),primary_key=True)
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),index=True)
    run_id:Mapped[str]=mapped_column(String(55),ForeignKey("sc05_runs.id"))
    accuracy:Mapped[int]=mapped_column(Integer)
    science_value:Mapped[int]=mapped_column(Integer)
    narrative:Mapped[int]=mapped_column(Integer)
    literature:Mapped[int]=mapped_column(Integer)
    feasibility:Mapped[int]=mapped_column(Integer)
    hard_failure:Mapped[bool]=mapped_column(default=False)
    feedback:Mapped[str]=mapped_column(Text,default="")
    failure_tags_json:Mapped[str]=mapped_column(Text,default="[]")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class ExtractedPaper(BaseModel):
    title:str=Field(min_length=8,max_length=300)
    pages:dict[str,str]
    source_sha:str|None=None


class StartRequest(BaseModel):
    acknowledge_external_model:bool=False


class RatingRequest(BaseModel):
    accuracy:int=Field(ge=0,le=5)
    science_value:int=Field(ge=0,le=5)
    narrative:int=Field(ge=0,le=5)
    literature:int=Field(ge=0,le=5)
    feasibility:int=Field(ge=0,le=5)
    hard_failure:bool=False
    feedback:str=Field(default="",max_length=3000)
    failure_tags:list[str]=Field(default_factory=list,max_length=6)


def safe_pages(pages):
    if not isinstance(pages,dict) or not 1<=len(pages)<=120:
        raise ValueError("Need 1-120 PDF pages")
    import re
    if any(not re.fullmatch(r"page_[0-9]{2,3}",k) for k in pages):
        raise ValueError("Invalid PDF page IDs")
    if sum(len(v) for v in pages.values())>MAX_TEXT:
        raise ValueError("PDF text exceeds 650k characters")
    if any(not isinstance(v,str) or not 40<=len(v)<=60000 for v in pages.values()):
        raise ValueError("Invalid PDF page text")
    # Same blind-setup rule as a full PDF: do not leak the original author's
    # Discussion/Future Work answer into the independent diagnostic prompt.
    cleaned={}
    for page,text in sorted(pages.items()):
        match=FUTURE_HEADING.search(text)
        if match:
            if len(text[:match.start()].strip())>=40:
                cleaned[page]=text[:match.start()]
            break
        cleaned[page]=text
    if not cleaned:raise ValueError("No blind-eligible Methods or Results pages")
    return cleaned


def case_view(x):
    return {"id":x.id,"title":x.title,"sha256":x.source_sha,
            "source_type":x.source_type,
            "pages":len(load(x.pages_json,{})),
            "shared_evidence_ready":bool(x.shared_evidence_json),
            "created_at":x.created_at.isoformat() if x.created_at else None}


def run_view(x,*,include_report=False):
    data={"id":x.id,"case_id":x.case_id,"pair_id":x.pair_id,
          "pipeline_sha":x.pipeline_sha,
          "variant":x.variant,
          "status":x.status,"stage":x.stage,
          "model_calls":x.calls,
          "input_tokens":x.input_tokens,"output_tokens":x.output_tokens,
          "error":x.error,"created_at":x.created_at.isoformat() if x.created_at else None}
    if include_report:
        data["report_md"]=x.report_md if x.status=="completed" else ""
        data["quality"]=load(x.result_json,{}).get("quality",{}) if x.status=="completed" else {}
        data["feedback_needed"]=x.status=="completed"
    return data


def owned(db:Session,actor:TeamMember,model,pk):
    row=db.get(model,pk)
    if row is None or row.member_id!=actor.id:
        raise HTTPException(404,"No such personal experiment")
    return row


def _model_key(factory):
    # Prefer the existing Render-only env variable, then the encrypted vault.
    direct=os.getenv("SC04_DEEPSEEK_API_KEY","").strip()
    if direct:return direct
    from backend.model_vault import load_key
    with factory() as db:
        return load_key(db)


def _checkpoint_call(factory,run_id):
    """Replay completed exact-input LLM stages; reserve before new paid stages."""
    def provider(api_key, model, system, payload, max_tokens=3000):
        stage=payload.get("sc05_stage","unknown")
        with factory() as db:
            row=db.get(SC05Run,run_id)
            if row is None or row.status!="running":
                raise RuntimeError("SC05 execution is not authorized or already canceled")
            index=len(load(row.checkpoints_json,[]))
        fingerprint=hashlib.sha256(dump({
            "model":model,"system":system,"payload":payload,
            "max_tokens":max_tokens,
        }).encode()).hexdigest()
        # Replays are consumed in order; the runner cursor is kept per invocation.
        if cursor[0]<index:
            with factory() as db:
                row=db.get(SC05Run,run_id)
                entry=load(row.checkpoints_json,[])[cursor[0]]
            if entry["prompt_sha256"]!=fingerprint:
                # One explicitly supported legacy prompt migration: the old
                # literature-assessment schema did not encode typed diagnosis links.
                legacy_match=False
                if stage=="literature_assessment":
                    legacy_payload=dict(payload)
                    legacy_payload["required_json_shape"]=LITERATURE_SCHEMA_V1
                    legacy_system=LITERATURE_ASSESSMENT_SYSTEM_V1+"\n输出一个 JSON 对象。"
                    legacy_fingerprint=hashlib.sha256(dump({
                        "model":model,"system":legacy_system,
                        "payload":legacy_payload,"max_tokens":max_tokens,
                    }).encode()).hexdigest()
                    legacy_match=entry["prompt_sha256"]==legacy_fingerprint
                if not legacy_match:
                    raise EvidenceError("Previously checkpointed prompt differs; cannot silently replay a changed model")
            cursor[0]+=1
            return entry["response"],entry["usage"]
        if not reserve(factory,calls=1,tokens=10000):
            raise RuntimeError("Daily LLM budget exhausted; no extra API call was made")
        try:
            response,usage=request_json(api_key,model,system,payload,max_tokens=max_tokens)
        except Exception:
            # The reserved call is never refunded, because provider billing is unknown.
            raise
        if not isinstance(response,dict):
            raise EvidenceError("Model returned non-object JSON")
        with factory() as db:
            row=db.get(SC05Run,run_id)
            existing=load(row.checkpoints_json,[])
            if len(existing)!=cursor[0]:
                raise RuntimeError("Concurrent stage checkpoint update detected")
            existing.append({"stage":stage,"prompt_sha256":fingerprint,
                             "response":response,"usage":usage,"model":model})
            row.checkpoints_json=dump(existing)
            row.stage=stage
            row.calls+=1
            row.input_tokens+=max(0,int(usage.get("input_tokens",0)))
            row.output_tokens+=max(0,int(usage.get("output_tokens",0)))
            row.updated_at=now()
            db.commit()
        record_usage(factory,usage)
        archive_if_enabled(factory,run_id)
        cursor[0]+=1
        return response,usage
    cursor=[0]
    return provider


def check_fact_type_resume(row: SC05Run, doc: SC05Case) -> dict:
    """No-cost, exact-prompt checkpoint check for the first live-run schema bug.

    This is the ONLY permitted legacy pipeline hash migration. It preserves
    the paid response, source hash, token counters and full audit trail.
    It does not repair fabricated quotations or alter prompts.
    """
    permitted_errors = (
        "Unsupported fact type",
        "PDF evidence quote is not an exact source fragment",
    )
    if row.status != "failed" or row.error not in permitted_errors:
        raise EvidenceError("Not an eligible cached first-stage evidence failure")
    if row.variant != "science_gate_off" or row.calls != 1:
        raise EvidenceError("Only the first baseline extraction is eligible")
    saved=load(row.checkpoints_json,[])
    if not isinstance(saved,list) or len(saved)!=1 or saved[0].get("stage")!="evidence_extraction":
        raise EvidenceError("Required first extraction checkpoint not found")
    entry=saved[0]
    response=entry.get("response")
    values=response.get("facts") if isinstance(response,dict) else None
    if not isinstance(values,list) or not 1<=len(values)<=6:
        raise EvidenceError("Saved facts have invalid shape")
    pages=load(doc.pages_json,{})
    chunks=_chunks(pages)
    if not chunks:
        raise EvidenceError("Source pages missing")
    first={part["page"]:part["text"] for part in chunks[0]}
    types=[{"raw_type":str(x.get("fact_type"))[:120],
            "normalized_type":normalize_fact_kind(x.get("fact_type"))[0]}
           for x in values if isinstance(x,dict)]
    if len(types)!=len(values):
        raise EvidenceError("Invalid saved fact object")
    if row.error == "Unsupported fact type" and all(
        x["raw_type"]==x["normalized_type"] for x in types
    ):
        raise EvidenceError("No fact taxonomy mismatch present")
    def saved_call(api_key,model,system,payload,max_tokens=2700):
        if payload.get("sc05_stage")!="evidence_extraction":
            raise EvidenceError("Unexpected legacy checkpoint stage")
        fp=hashlib.sha256(dump({
            "model":model,"system":system,"payload":payload,
            "max_tokens":max_tokens,
        }).encode()).hexdigest()
        if fp!=entry.get("prompt_sha256"):
            raise EvidenceError("Saved prompt differs; cannot replay without new paid call")
        return response,entry.get("usage",{})
    # Validate source provenance and type normalization with zero network calls.
    parsed=extract_ledger(first,"cached-response-only",saved_call,[],max_calls=8)
    rejected_quotes = sum(
        1 for note in parsed["source_note"]
        if note.get("rule") == "unverified_source_quote_rejected"
    )
    if row.error == "PDF evidence quote is not an exact source fragment" and not rejected_quotes:
        raise EvidenceError("No rejected quotation in cached evidence; cannot classify this repair")
    return {"facts":len(parsed["snapshot"]["observations"]),
            "rejected_quotes":rejected_quotes,
            "types":types,"replay_prompt_matches":True}


class _SearchPlanPrefixComplete(Exception):
    """Stop a no-cost replay immediately after validating the saved search plan."""


def check_search_query_resume(row: SC05Run, doc: SC05Case) -> dict:
    """Verify the four saved gated checkpoints under the relaxed query-length validator.

    Reconstructs the exact prompts from the source and frozen facts, consumes only
    saved responses, and stops before OpenAlex or any new model request.
    """
    if row.status != "failed" or row.error != "Missing/invalid search query":
        raise EvidenceError("Not the eligible saved search-query validation failure")
    if row.variant != "science_gate_on" or row.calls != 4:
        raise EvidenceError("Only the four-stage gated search-query failure is eligible")
    entries = load(row.checkpoints_json, [])
    expected = ["method_lineage", "diagnosis", "scientific_value_triage", "evidence_questions"]
    if not isinstance(entries, list) or len(entries) != 4:
        raise EvidenceError("Expected exactly four saved model checkpoints")
    if [x.get("stage") for x in entries if isinstance(x, dict)] != expected:
        raise EvidenceError("Saved checkpoint stages are incomplete or reordered")
    pages = load(doc.pages_json, {})
    frozen = load(doc.shared_evidence_json)
    if not frozen:
        raise EvidenceError("Gated search-query recovery requires frozen baseline facts")
    cursor = [0]
    captured = {}

    def cached_only(api_key, model, system, payload, max_tokens=3000):
        if cursor[0] >= len(entries):
            raise _SearchPlanPrefixComplete()
        entry = entries[cursor[0]]
        fingerprint = hashlib.sha256(dump({
            "model": model, "system": system, "payload": payload,
            "max_tokens": max_tokens,
        }).encode()).hexdigest()
        stage = payload.get("sc05_stage")
        if (entry.get("prompt_sha256") != fingerprint
            or entry.get("stage") != stage
            or entry.get("model") != model):
            raise EvidenceError("Saved prompt fingerprint mismatch at " + str(stage))
        if stage == "evidence_questions":
            captured["response"] = entry.get("response")
        cursor[0] += 1
        return entry.get("response"), entry.get("usage", {})

    def stop_before_openalex(*args, **kwargs):
        raise _SearchPlanPrefixComplete()

    try:
        run_paper(
            None, "cached-response-only", model_call=cached_only,
            search_provider=stop_before_openalex, source_title=doc.title,
            pages_override=pages, source_sha=doc.source_sha,
            frozen_snapshot=frozen, scientific_value_gate=True, max_calls=40,
            legacy_literature_checkpoint=True,
        )
    except _SearchPlanPrefixComplete:
        pass
    except EvidenceError as exc:
        raise EvidenceError(
            "Saved search-query response still fails validation: " + str(exc)[:120]
        ) from exc
    if cursor[0] != 4:
        raise EvidenceError("Cached replay did not verify all four saved stages")
    raw = captured.get("response")
    queries = raw.get("queries") if isinstance(raw, dict) else None
    if not isinstance(queries, list) or len(queries) > 7:
        raise EvidenceError("Saved search-query response has an invalid query list")
    lengths = [len(x.get("query", "")) for x in queries
               if isinstance(x, dict) and isinstance(x.get("query"), str)]
    return {
        "cached_stages": 4,
        "prompt_hashes_verified": True,
        "validated_queries": len(queries),
        "max_query_length": max(lengths, default=0),
        "paid_calls_on_check": 0,
        "network_searches_on_check": 0,
    }


class _LiteraturePrefixBoundary(Exception):
    """Stop after validating saved literature output, before new model calls."""


def check_literature_diagnosis_resume(
    row: SC05Run, doc: SC05Case, *, allow_queued: bool = False
) -> dict:
    """Verify the five saved gated prompts and conservatively parse unlinked literature.

    OpenAlex is queried again to reconstruct the literature-assessment prompt.
    If its results differ from the saved prompt fingerprint, recovery is refused.
    No DeepSeek request is made by this check. Queued recovery is allowed only
    for the MCP worker's already-authorized needs_review retry path.
    """
    failed_eligible=(
        row.status=="failed" and row.error=="Missing references: literature diagnosis"
    )
    queued_eligible=allow_queued and row.status=="queued" and not row.error
    if not (failed_eligible or queued_eligible):
        raise EvidenceError("Not the eligible missing literature-diagnosis reference failure")
    if row.variant != "science_gate_on" or row.calls != 5:
        raise EvidenceError("Only the five-stage gated literature-assessment failure is eligible")
    entries = load(row.checkpoints_json, [])
    expected = ["method_lineage", "diagnosis", "scientific_value_triage",
                "evidence_questions", "literature_assessment"]
    if not isinstance(entries, list) or len(entries) != 5:
        raise EvidenceError("Expected exactly five saved model checkpoints")
    if [x.get("stage") for x in entries if isinstance(x, dict)] != expected:
        raise EvidenceError("Saved literature checkpoints are incomplete or reordered")
    pages = load(doc.pages_json, {})
    frozen = load(doc.shared_evidence_json)
    if not frozen:
        raise EvidenceError("Literature recovery requires frozen baseline facts")
    cursor = [0]
    captured = {}
    openalex_queries = []

    def cached_only(api_key, model, system, payload, max_tokens=3000):
        if cursor[0] >= len(entries):
            raise _LiteraturePrefixBoundary()
        entry = entries[cursor[0]]
        fingerprint = hashlib.sha256(dump({
            "model": model, "system": system, "payload": payload,
            "max_tokens": max_tokens,
        }).encode()).hexdigest()
        stage = payload.get("sc05_stage")
        if (entry.get("prompt_sha256") != fingerprint
            or entry.get("stage") != stage
            or entry.get("model") != model):
            raise EvidenceError("Saved prompt fingerprint mismatch at " + str(stage))
        if stage == "literature_assessment":
            captured["response"] = entry.get("response")
        cursor[0] += 1
        return entry.get("response"), entry.get("usage", {})

    def openalex_provider(query, since, limit=7):
        openalex_queries.append(query)
        return query_openalex(query, since, limit=limit)

    try:
        run_paper(
            None, "cached-response-only", model_call=cached_only,
            search_provider=openalex_provider, source_title=doc.title,
            pages_override=pages, source_sha=doc.source_sha,
            frozen_snapshot=frozen, scientific_value_gate=True, max_calls=40,
            legacy_literature_checkpoint=True,
        )
    except _LiteraturePrefixBoundary:
        pass
    except EvidenceError as exc:
        raise EvidenceError(
            "Saved literature checkpoint is not safely recoverable: " + str(exc)[:120]
        ) from exc
    if cursor[0] != 5:
        raise EvidenceError("Cached replay did not verify all five saved stages")
    raw = captured.get("response")
    assessments = raw.get("assessments") if isinstance(raw, dict) else None
    if not isinstance(assessments, list):
        raise EvidenceError("Saved literature assessment response has invalid shape")
    unlinked = sum(
        1 for item in assessments
        if not isinstance(item, dict) or not (
            item.get("diagnosis_links") or item.get("diagnosis_ids")
        )
    )
    return {
        "cached_stages": 5,
        "prompt_hashes_verified": True,
        "assessment_count": len(assessments),
        "unlinked_assessments": unlinked,
        "openalex_queries_replayed": len(openalex_queries),
        "paid_calls_on_check": 0,
    }


def eligible_unstarted_gate_migration(db:Session,row:SC05Run,doc:SC05Case,
                                      current_sha:str)->bool:
    """Safely re-pin an unexecuted B run after recovering its original A.

    Never re-pin a paid or partially executed B run. The shared source facts
    must have been frozen by a completed baseline on the same current pipeline.
    """
    if (row.variant!="science_gate_on" or row.status!="prepared" or row.calls!=0
        or bool(load(row.checkpoints_json,[])) or not doc.shared_evidence_json):
        return False
    baseline=db.scalars(select(SC05Run).where(
        SC05Run.member_id==row.member_id,
        SC05Run.case_id==row.case_id,
        SC05Run.pair_id==row.pair_id,
        SC05Run.variant=="science_gate_off",
        SC05Run.status=="completed",
        SC05Run.pipeline_sha==current_sha,
    ).limit(1)).first()
    return baseline is not None


def execute(factory,run_id,*,claimed_by_worker=False):
    """Resumable job. Worker claims queued work before executing paid calls."""
    with factory() as db:
        row=db.get(SC05Run,run_id)
        if row is None or not (row.status=="queued" or
            (claimed_by_worker and row.status=="claimed")):return
        # Only one running experiment per Owner; A then B is deliberate.
        other=db.scalars(select(SC05Run.id).where(
            SC05Run.member_id==row.member_id,SC05Run.status=="running",
            SC05Run.id!=run_id).limit(1)).first()
        if other:
            row.status="failed";row.error="Another personal SC05 run is running"
            db.commit();return
        row.status="running";row.stage="starting";row.updated_at=now()
        doc=db.get(SC05Case,row.case_id)
        if row.pipeline_sha!=pipeline_sha():
            row.status="failed";row.error="Pipeline code changed; cannot resume this frozen experiment"
            db.commit();return
        pages=load(doc.pages_json,{})
        snapshot=load(doc.shared_evidence_json)
        title=doc.title
        sha=doc.source_sha
        variant=row.variant
        db.commit()
    archive_if_enabled(factory,run_id)
    try:
        key=_model_key(factory)
        if not key:raise RuntimeError("DeepSeek key is not configured")
        if variant=="science_gate_on" and not snapshot:
            raise RuntimeError("Run the baseline first to freeze an identical evidence snapshot")
        callback=_checkpoint_call(factory,run_id)
        report,result=run_paper(
            None,key,model_call=callback,source_title=title,
            pages_override=pages,source_sha=sha,frozen_snapshot=snapshot,
            scientific_value_gate=(variant=="science_gate_on"),
            max_calls=40,
        )
        # The first fully source-verified extraction freezes the common facts.
        with factory() as db:
            row=db.get(SC05Run,run_id)
            doc=db.get(SC05Case,row.case_id)
            if variant=="science_gate_off" and not doc.shared_evidence_json:
                doc.shared_evidence_json=dump(result["snapshot"])
            result["is_paid_model_output"]=True
            result["experiment_source"]="authenticated_owner_render_deepseek"
            row.report_md=report
            row.result_json=dump(result)
            row.status="completed";row.stage="complete";row.updated_at=now()
            add_audit(db,"sc05.completed",row.member_id,run_id,
                      "calls="+str(row.calls))
            db.commit()
        archive_if_enabled(factory,run_id)
    except Exception as exc:
        # Messages are whitelisted to avoid logging raw provider responses.
        # ModelCallError contains only adapter-whitelisted diagnostics
        # (HTTP status class, timeout, transport or response-shape category).
        # Preserve it so Owner can fix the actual provider problem; never log
        # raw HTTP bodies, credentials or prompt payloads.
        safe=(str(exc) if isinstance(exc,(EvidenceError,RuntimeError,ModelCallError)) else
              type(exc).__name__ + ": stage failed")
        with factory() as db:
            row=db.get(SC05Run,run_id)
            if row:
                row.status="failed";row.stage="failed"
                row.error=safe[:280];row.updated_at=now()
                db.commit()
        archive_if_enabled(factory,run_id)


def mount(app,*,get_db,require_actor,team_auth_enabled,get_factory):
    router=APIRouter(prefix="/api/personal-research/me/sc05",
                     tags=["SC05 Authenticated Research Agent Evaluation"])

    def owner(actor:TeamMember|None=Depends(require_actor)):
        if not team_auth_enabled() or actor is None or not actor.active:
            raise HTTPException(401,"Please log into Research Atlas")
        if actor.role!="owner":
            raise HTTPException(403,"SC05 experiment administration is Owner-only")
        return actor

    @router.get("")
    def overview(db:Session=Depends(get_db),actor=Depends(owner)):
        cases=db.scalars(select(SC05Case).where(SC05Case.member_id==actor.id)
            .order_by(SC05Case.created_at.desc()).limit(20)).all()
        runs=db.scalars(select(SC05Run).where(SC05Run.member_id==actor.id)
            .order_by(SC05Run.created_at.desc()).limit(40)).all()
        return {"version":VERSION,"cases":[case_view(c) for c in cases],
                "runs":[run_view(r) for r in runs],
                "budget":budget_status(db),
                "key_available":bool(os.getenv("SC04_DEEPSEEK_API_KEY","").strip())}

    @router.post("/cases",status_code=201)
    def create_case(data:ExtractedPaper,db:Session=Depends(get_db),
                    actor=Depends(owner)):
        try:pages=safe_pages(data.pages)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        sha=hashlib.sha256(dump(pages).encode()).hexdigest()
        if data.source_sha and data.source_sha!=sha:
            # For text intake hash the actual supplied content, never trust a
            # client claim that it already verified an unavailable PDF file.
            raise HTTPException(422,"Provided hash must match submitted page-text content")
        row=SC05Case(id="sc05case_"+uuid.uuid4().hex[:28],member_id=actor.id,
            title=data.title,pages_json=dump(pages),source_sha=sha,
            source_type="uploaded_extracted_pages")
        db.add(row)
        add_audit(db,"sc05.case_created",actor.id,row.id,
                  "source_sha="+sha[:16])
        db.commit()
        return case_view(row)

    @router.post("/cases/pdf",status_code=201)
    async def create_pdf_case(request:Request,db:Session=Depends(get_db),
                              actor=Depends(owner)):
        if request.headers.get("content-type","").split(";")[0].strip()!="application/pdf":
            raise HTTPException(415,"Content-Type must be application/pdf")
        size=request.headers.get("content-length")
        if size and size.isdigit() and int(size)>MAX_PDF_BYTES:
            raise HTTPException(413,"PDF exceeds the 32 MB upload limit")
        data=await request.body()
        if not data.startswith(b"%PDF") or not 100<=len(data)<=MAX_PDF_BYTES:
            raise HTTPException(422,"Invalid or oversized PDF")
        title=request.headers.get("x-research-paper-title","Published research paper")[:300]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"submitted.pdf"
            path.write_bytes(data)
            try: pages,original_sha=page_texts_from_pdf(path)
            except Exception:raise HTTPException(422,"Unable to extract PDF text")
        try:safe_pages(pages)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        row=SC05Case(id="sc05case_"+uuid.uuid4().hex[:28],
             member_id=actor.id,title=title,pages_json=dump(pages),
             source_sha=original_sha,source_type="uploaded_pdf")
        db.add(row)
        add_audit(db,"sc05.case_created",actor.id,row.id,"pdf_sha="+original_sha[:16])
        db.commit()
        return case_view(row)

    @router.post("/cases/{case_id}/ab",status_code=201)
    def create_ab(case_id:str,db:Session=Depends(get_db),actor=Depends(owner)):
        doc=owned(db,actor,SC05Case,case_id)
        pair_id="sc05pair_"+uuid.uuid4().hex[:28]
        # A and B differ in scientific gate; same model and frozen facts.
        runs=[]
        for variant in ("science_gate_off","science_gate_on"):
            item=SC05Run(id="sc05run_"+uuid.uuid4().hex[:28],
                member_id=actor.id,case_id=doc.id,pair_id=pair_id,
                variant=variant,pipeline_sha=pipeline_sha())
            db.add(item);runs.append(item)
        add_audit(db,"sc05.ab_created",actor.id,pair_id,doc.source_sha[:16])
        db.commit()
        return {"pair_id":pair_id,"runs":[run_view(r) for r in runs],
                "note":"Run the first baseline to freeze source evidence, then the gated variant. Paid calls require separate explicit Owner consent."}

    @router.post("/runs/{run_id}/start",status_code=202)
    def start(run_id:str,data:StartRequest,background:BackgroundTasks,
              db:Session=Depends(get_db),actor=Depends(owner)):
        if not data.acknowledge_external_model:
            raise HTTPException(422,"Explicit approval for paid model calls is required")
        mode=os.getenv("SC05_EXECUTION_MODE","background").strip().lower()
        if mode not in ("background","worker"):
            raise HTTPException(503,"Unknown SC05 execution mode")
        row=owned(db,actor,SC05Run,run_id)
        if row.status not in ("prepared","failed"):
            raise HTTPException(409,"Only prepared or failed runs can start")
        if row.variant=="science_gate_on" and not db.get(SC05Case,row.case_id).shared_evidence_json:
            raise HTTPException(409,"Finish the baseline first to lock shared source facts")
        if db.scalars(select(SC05Run.id).where(
            SC05Run.member_id==actor.id,
            SC05Run.status.in_(("queued","claimed","running")),
            SC05Run.id!=run_id).limit(1)).first():
            raise HTTPException(409,"An Owner SC05 experiment is already active")
        if not (os.getenv("SC04_DEEPSEEK_API_KEY","").strip()
                or os.getenv("MODEL_VAULT_KEY","").strip()):
            raise HTTPException(409,"No configured DeepSeek provider credential")
        # Resume only a vetted taxonomy parser fix. Never overwrite the pinned
        # pipeline SHA for other changes or for previously unverified evidence.
        current_sha=pipeline_sha()
        if row.pipeline_sha!=current_sha:
            document=db.get(SC05Case,row.case_id)
            old_sha=row.pipeline_sha
            if eligible_unstarted_gate_migration(db,row,document,current_sha):
                row.pipeline_sha=current_sha
                add_audit(db,"sc05.unstarted_gate_repin",actor.id,row.id,
                          "old_sha="+old_sha[:16]+";new_sha="+current_sha[:16]+
                          ";no_paid_stages=True;shared_facts=True")
            else:
                try:
                    if row.error=="Missing/invalid search query":
                        info=check_search_query_resume(row,document)
                        audit_action="sc05.verified_search_query_length_repair"
                        audit_detail=("old_sha="+old_sha[:16]+";new_sha="+current_sha[:16]+
                                      ";cached_stages="+str(info["cached_stages"])+
                                      ";validated_queries="+str(info["validated_queries"])+
                                      ";max_query_length="+str(info["max_query_length"])+
                                      ";no_paid_replay=True")
                    elif row.error=="Missing references: literature diagnosis":
                        info=check_literature_diagnosis_resume(row,document)
                        audit_action="sc05.verified_typed_literature_repair"
                        audit_detail=("old_sha="+old_sha[:16]+";new_sha="+current_sha[:16]+
                                      ";cached_stages="+str(info["cached_stages"])+
                                      ";unlinked_assessments="+str(info["unlinked_assessments"])+
                                      ";openalex_queries_replayed="+str(info["openalex_queries_replayed"])+
                                      ";no_paid_replay=True")
                    else:
                        info=check_fact_type_resume(row,document)
                        audit_action="sc05.verified_taxonomy_parser_repair"
                        audit_detail=("old_sha="+old_sha[:16]+";new_sha="+current_sha[:16]+
                                      ";replayed_facts="+str(info["facts"]))
                except (EvidenceError,ValueError,TypeError) as exc:
                    raise HTTPException(
                        409,"Saved run cannot be safely migrated: "+str(exc)[:180]
                    ) from None
                row.pipeline_sha=current_sha
                add_audit(db,audit_action,actor.id,row.id,audit_detail)
        row.status="queued";row.error="";row.updated_at=now()
        add_audit(db,"sc05.authorized_model_run",actor.id,row.id,
                  "variant="+row.variant)
        db.commit()
        if mode=="background":
            background.add_task(execute,get_factory(),row.id)
        return run_view(row)

    @router.get("/runs/{run_id}/repair-check")
    def repair_check(run_id:str,db:Session=Depends(get_db),actor=Depends(owner)):
        """Read-only; returns only type labels, not the source or model text."""
        row=owned(db,actor,SC05Run,run_id)
        if row.pipeline_sha==pipeline_sha():
            return {"ready":True,"requires_migration":False,
                    "saved_checkpoints":len(load(row.checkpoints_json,[]))}
        try:
            if row.error=="Missing/invalid search query":
                result=check_search_query_resume(row,db.get(SC05Case,row.case_id))
                return {"ready":True,"requires_migration":True,**result}
            if row.error=="Missing references: literature diagnosis":
                result=check_literature_diagnosis_resume(row,db.get(SC05Case,row.case_id))
                return {"ready":True,"requires_migration":True,**result}
            result=check_fact_type_resume(row,db.get(SC05Case,row.case_id))
        except (EvidenceError,ValueError,TypeError) as exc:
            return {"ready":False,"requires_migration":True,
                    "reason":str(exc)[:180]}
        return {"ready":True,"requires_migration":True,
                "replay_prompt_matches":result["replay_prompt_matches"],
                "saved_facts":result["facts"],
                "rejected_quotes":result["rejected_quotes"],
                "normalized_types":result["types"],
                "paid_calls_on_check":0}

    @router.get("/runs/{run_id}")
    def detail(run_id:str,db:Session=Depends(get_db),actor=Depends(owner)):
        return run_view(owned(db,actor,SC05Run,run_id),include_report=True)

    @router.get("/runs/{run_id}/audit")
    def audit(run_id:str,db:Session=Depends(get_db),actor=Depends(owner)):
        row=owned(db,actor,SC05Run,run_id)
        return {"id":row.id,"version":VERSION,
                "source_sha":db.get(SC05Case,row.case_id).source_sha,
                "variant":row.variant,
                "checkpoints":load(row.checkpoints_json,[]),
                "result":load(row.result_json,{}) if row.status=="completed" else None}

    @router.get("/pairs/{pair_id}/blind")
    def blind_pair(pair_id:str,db:Session=Depends(get_db),actor=Depends(owner)):
        rows=db.scalars(select(SC05Run).where(SC05Run.member_id==actor.id,
             SC05Run.pair_id==pair_id)).all()
        if len(rows)!=2:raise HTTPException(404,"No such A/B pair")
        if any(r.status!="completed" for r in rows):
            return {"pair_id":pair_id,"ready":False,
                    "statuses":[r.status for r in rows]}
        # Fixed opaque permutation: the evaluator receives no variant labels.
        ordered=sorted(rows,key=lambda r:hashlib.sha256(
            (pair_id+":"+r.id).encode()).hexdigest())
        return {"pair_id":pair_id,"ready":True,
                "blind_reports":[
                    {"label":chr(65+i),"run_id":r.id,"report_md":r.report_md}
                    for i,r in enumerate(ordered)]}

    @router.post("/runs/{run_id}/review",status_code=201)
    def review(run_id:str,data:RatingRequest,db:Session=Depends(get_db),
               actor=Depends(owner)):
        row=owned(db,actor,SC05Run,run_id)
        if row.status!="completed":
            raise HTTPException(409,"Only completed runs can be reviewed")
        existing=db.scalars(select(SC05Rating).where(
            SC05Rating.member_id==actor.id,SC05Rating.run_id==run_id).limit(1)).first()
        if existing:raise HTTPException(409,"Already rated; keep independent blind feedback immutable")
        v=data.model_dump()
        score=(v["accuracy"]*15+v["science_value"]*30+
               v["narrative"]*25+v["literature"]*20+
               v["feasibility"]*10)/5
        allowed={"paper_understanding","science_value","mechanism_narrative",
                 "literature_depth","feasibility","citation_error"}
        if any(t not in allowed for t in data.failure_tags):
            raise HTTPException(422,"Unknown failure tag")
        rating=SC05Rating(id="sc05rating_"+uuid.uuid4().hex[:28],
              member_id=actor.id,run_id=run_id,
              accuracy=v["accuracy"],science_value=v["science_value"],
              narrative=v["narrative"],literature=v["literature"],
              feasibility=v["feasibility"],hard_failure=v["hard_failure"],
              feedback=v["feedback"],failure_tags_json=dump(v["failure_tags"]))
        db.add(rating)
        add_audit(db,"sc05.blind_review",actor.id,row.id,
                 "score="+str(score)+";hard_failure="+str(v["hard_failure"]))
        db.commit()
        return {"saved":True,"score":0 if v["hard_failure"] else score,
                "hard_failure":v["hard_failure"]}

    @router.get("/pairs/{pair_id}/comparison")
    def comparison(pair_id:str,db:Session=Depends(get_db),actor=Depends(owner)):
        runs=db.scalars(select(SC05Run).where(
            SC05Run.member_id==actor.id,SC05Run.pair_id==pair_id)).all()
        if len(runs)!=2:raise HTTPException(404,"No such A/B pair")
        if any(r.status!="completed" for r in runs):
            raise HTTPException(409,"Finish both real runs first")
        assessed=[]
        for r in runs:
            rating=db.scalars(select(SC05Rating).where(
                SC05Rating.member_id==actor.id,
                SC05Rating.run_id==r.id).limit(1)).first()
            if not rating:raise HTTPException(409,"Both reports must be scored blindly before unblinding")
            subtotal=(rating.accuracy*15+rating.science_value*30+
                      rating.narrative*25+rating.literature*20+
                      rating.feasibility*10)/5
            result=load(r.result_json,{})
            assessed.append({
                "run_id":r.id,"variant":r.variant,
                "score":0 if rating.hard_failure else subtotal,
                "scientific_value":rating.science_value,
                "narrative":rating.narrative,
                "hard_failure":rating.hard_failure,
                "failure_tags":load(rating.failure_tags_json,[]),
                "feedback":rating.feedback,
                "model_calls":r.calls,
                "input_tokens":r.input_tokens,
                "output_tokens":r.output_tokens,
                "source_sha":db.get(SC05Case,r.case_id).source_sha,
                "pipeline_sha":r.pipeline_sha,
                "quality_warnings":result.get("quality",{}).get("warnings",[]),
            })
        baseline=next(x for x in assessed if x["variant"]=="science_gate_off")
        gated=next(x for x in assessed if x["variant"]=="science_gate_on")
        return {"pair_id":pair_id,"unblinded":True,
                "runs":assessed,
                "score_delta":gated["score"]-baseline["score"],
                "scientific_value_delta":gated["scientific_value"]-baseline["scientific_value"],
                "note":"These are researcher scores, not proof of scientific correctness. Test on held-out papers before claiming generality."}

    app.include_router(router)
