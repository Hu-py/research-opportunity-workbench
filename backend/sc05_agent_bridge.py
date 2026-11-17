"""Owner-delegated, OAuth-protected SC05 MCP gateway.

No model calls happen during OAuth, discovery, listing or preflight.
MCP writes reuse the EXISTING SC05 Owner start handler, which enforces
checkpoint compatibility, frozen A/B evidence and provider budgets.
"""
from __future__ import annotations

from datetime import datetime
import base64
import hashlib
import html
import json
import os
import re
import secrets
import time
import uuid
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.team import AuditEntry, TeamMember, add_audit, login as member_login, revoke_session
from backend.sc05_eval_api import (SC05Case, SC05Run, SC05Rating, StartRequest, run_view, case_view, load, dump, now, pipeline_sha, check_fact_type_resume, check_literature_diagnosis_resume, EvidenceError)
from backend.sc05_paper_only import run_paper
from backend.model_gateway import ModelCallError, request_json
from backend.model_vault import status as model_config_status
from backend.research_budget import status as budget_status, reserve_session, record_usage_session
from backend.sc05_worker import (
    SC05DelegatedAuthorization, flag as worker_flag, worker_status
)

READ="experiments:read"
RUN="experiments:run"
SCOPES={READ,RUN}


def required_scopes() -> str:
    # First OAuth challenge previously forced READ even when RUN was offered.
    # OAuth does not upgrade already-issued grants without user re-consent.
    if worker_flag("SC05_MCP_RUN_SCOPE_ENABLED"):
        return READ + " " + RUN
    return READ


def required_scope_challenge() -> str:
    return ('Bearer resource_metadata="' + public_base() +
            '/.well-known/oauth-protected-resource", scope="' +
            required_scopes() + '"')


def step_up_result() -> dict:
    # Per-tool OAuth scope escalation contract required by ChatGPT.
    challenge = ('Bearer resource_metadata="' + public_base() +
                 '/.well-known/oauth-protected-resource", scope="' +
                 READ + " " + RUN +
                 '", error="insufficient_scope", error_description="Owner must approve experiment execution"')
    data = result({"error":"Owner must authorize experiments:run to create or start experiments"},
                  error=True)
    data["_meta"] = {"mcp/www_authenticate":[challenge]}
    return data
CLIENT="https://chatgpt.com/oauth/client.json"
REDIRECT="https://chatgpt.com/connector_platform_oauth_redirect"
MCP_VERSION="2025-06-18"


def now_seconds():
    return int(time.time())


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_base() -> str:
    base=os.getenv("SC05_MCP_PUBLIC_URL","").rstrip("/")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{2,5})?",base):
        raise HTTPException(503,"SC05 MCP public HTTPS origin is not configured")
    return base


def enabled():
    if os.getenv("SC05_MCP_ENABLED","").lower() not in {"true","1"}:
        raise HTTPException(404,"MCP integration is disabled")
    if os.getenv("TEAM_AUTH_ENABLED","").lower() not in {"true","1","yes"}:
        raise HTTPException(503,"Team authentication required")
    if os.getenv("SC05_MCP_PAID_ENABLED","").lower() not in {"true","1"}:
        # Read and OAuth flows remain available.
        return False
    return True


class OAuthCode(Base):
    __tablename__="sc05_mcp_auth_codes"
    code_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),index=True)
    challenge:Mapped[str]=mapped_column(String(64))
    client_id:Mapped[str]=mapped_column(Text)
    redirect_uri:Mapped[str]=mapped_column(Text)
    resource:Mapped[str]=mapped_column(Text)
    scopes:Mapped[str]=mapped_column(String(100))
    expires_at:Mapped[int]=mapped_column(Integer)


class OAuthGrant(Base):
    __tablename__="sc05_mcp_oauth_grants"
    access_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
    refresh_hash:Mapped[str]=mapped_column(String(64),unique=True)
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),index=True)
    client_id:Mapped[str]=mapped_column(Text)
    resource:Mapped[str]=mapped_column(Text)
    scopes:Mapped[str]=mapped_column(String(100))
    expires_at:Mapped[int]=mapped_column(Integer)
    refresh_expires_at:Mapped[int]=mapped_column(Integer)
    revoked:Mapped[int]=mapped_column(Integer,default=0)


class SC05ExperimentRound(Base):
    """Owner-scoped, durable round ledger for ChatGPT-managed SC05 work."""
    __tablename__="sc05_experiment_rounds"
    __table_args__=(UniqueConstraint("member_id","round_code",
                                     name="uq_sc05_round_member_code"),)
    id:Mapped[str]=mapped_column(String(55),primary_key=True)
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),index=True)
    round_code:Mapped[str]=mapped_column(String(32))
    category_code:Mapped[str]=mapped_column(String(16))
    category_label:Mapped[str]=mapped_column(String(80))
    problem:Mapped[str]=mapped_column(Text)
    method:Mapped[str]=mapped_column(Text)
    experiment_content:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(24),default="planned")
    brief_result:Mapped[str]=mapped_column(Text,default="")
    next_step:Mapped[str]=mapped_column(Text,default="")
    detailed_record_json:Mapped[str]=mapped_column(Text,default="{}")
    pair_id:Mapped[str|None]=mapped_column(String(55),nullable=True,index=True)
    source_sha:Mapped[str]=mapped_column(String(64),default="")
    pipeline_sha:Mapped[str]=mapped_column(String(64),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


def authorize_request(data):
    base=public_base()
    if data.get("response_type")!="code":
        raise HTTPException(400,"Authorization code flow required")
    if data.get("client_id")!=CLIENT or data.get("redirect_uri")!=REDIRECT:
        raise HTTPException(400,"Unregistered OAuth client or redirect URI")
    if data.get("resource")!=base+"/mcp":
        raise HTTPException(400,"Invalid protected resource")
    challenge=data.get("code_challenge","")
    if data.get("code_challenge_method")!="S256" or not re.fullmatch(r"[A-Za-z0-9_-]{43,64}",challenge):
        raise HTTPException(400,"PKCE S256 is mandatory")
    state=data.get("state","")
    if not state or len(state)>1000:
        raise HTTPException(400,"OAuth state required")
    scopes=set(data.get("scope",READ).split())
    if not scopes or not scopes.issubset(SCOPES):
        raise HTTPException(400,"Unsupported OAuth scopes")
    if RUN in scopes and not worker_flag("SC05_MCP_RUN_SCOPE_ENABLED"):
        raise HTTPException(403,"Run scope cannot be granted on this deployment")
    return base,scopes


def token_response(db:Session,owner:TeamMember,client_id:str,resource:str,scopes:str):
    raw_access=secrets.token_urlsafe(48)
    raw_refresh=secrets.token_urlsafe(48)
    row=OAuthGrant(access_hash=digest(raw_access),refresh_hash=digest(raw_refresh),
                   member_id=owner.id,client_id=client_id,resource=resource,
                   scopes=scopes,expires_at=now_seconds()+3600,
                   refresh_expires_at=now_seconds()+30*24*3600,revoked=0)
    db.add(row)
    db.commit()
    return {"access_token":raw_access,"refresh_token":raw_refresh,
            "token_type":"Bearer","expires_in":3600,"scope":scopes,
            "resource":resource}


def form_html(data):
    fields="".join(
        '<input type="hidden" name="'+html.escape(k,quote=True)+'" value="'+html.escape(str(v),quote=True)+'">'
        for k,v in data.items()
    )
    return """<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Research Atlas · Connect ChatGPT</title>
    <style>body{font:16px system-ui;margin:9vh auto;max-width:450px;padding:20px}
    label{display:block;margin:16px 0}input{box-sizing:border-box;width:100%;padding:12px}
    button{background:#111;color:white;border:0;padding:13px 20px;cursor:pointer}
    small{color:#555}h1{font-size:24px}</style>
    <h1>Research Atlas · ChatGPT integration</h1>
    <p>Sign in as the verified Owner to grant scoped access to your own SC05 experiments.</p>
    <p><strong>Requested scopes:</strong> """+html.escape(data.get("scope",READ))+"""</p>
    <form method="post" action="/oauth/authorize">"""+fields+"""
    <label>Email<input name="email" type="email" autocomplete="username" required></label>
    <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
    <button type="submit">Authorize ChatGPT</button></form>
    <p><small>Model spending still requires a separate explicit tool confirmation and server-side limits.
    This page never receives your DeepSeek credential.</small></p></html>"""


TOOLS=[
    {"name":"list_experiments","description":"List Owner SC05 papers, A/B runs, their actual status and remaining daily DeepSeek call budget. Read-only.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"create_ab_pair","description":"Owner write action with zero model calls: create a fresh science_gate_off/science_gate_on run pair for an existing Owner SC05 paper case. Does not start either run or spend DeepSeek budget. Run the gate-off baseline first; gate-on requires its frozen evidence snapshot.",
     "inputSchema":{"type":"object","properties":{
         "case_id":{"type":"string","description":"Existing Owner SC05 case ID returned by list_experiments"},
         "fresh_copy":{"type":"boolean","description":"Clone the exact source PDF page snapshot into a new case and clear its shared evidence so the baseline re-runs extraction; preserves the original source SHA"},
         "confirm_create":{"type":"boolean","description":"Confirm creating the case/pair records; this does not make model calls"}},
         "required":["case_id","confirm_create"],"additionalProperties":False}},
    {"name":"prepare_experiment","description":"Read-only preflight for an existing SC05 run: verify source hashes, frozen evidence, checkpoint counts, status, and budget before spending anything.",
     "inputSchema":{"type":"object","properties":{"run_id":{"type":"string","description":"Existing sc05run_ ID"}},
                    "required":["run_id"],"additionalProperties":False}},
    {"name":"start_experiment","description":"Paid action: start or resume ONE existing Owner SC05 run using existing API validation and daily budget controls. Never run without explicit paid consent; never restart completed runs. Prefer prepare_experiment first.",
     "inputSchema":{"type":"object","properties":{
         "run_id":{"type":"string","description":"Existing SC05 run ID"},
         "confirm_paid":{"type":"boolean","description":"Set true only after user explicitly authorized actual DeepSeek model spending in this conversation"}},
         "required":["run_id","confirm_paid"],"additionalProperties":False}},
    {"name":"get_executor_status","description":"Read-only worker and academic-retrieval status. Defaults to zero provider calls; pass probe_openalex=true to make one explicit, bounded OpenAlex metadata check using the configured free-tier key. Never calls DeepSeek.",
     "inputSchema":{"type":"object","properties":{
         "probe_openalex":{"type":"boolean","description":"Opt into one bounded OpenAlex search to verify actual connectivity; uses the account's OpenAlex quota but no DeepSeek tokens"}},
         "additionalProperties":False}},
    {"name":"get_model_config_status","description":"Read-only check of the DeepSeek credential source, encrypted-vault readiness, configured model names and execution flags. Never returns the key and makes no provider call.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"probe_model_connection","description":"Paid one-request DeepSeek connectivity test using the Owner's stored credential. Returns only sanitized provider status and token usage. Requires experiments:run and explicit per-call consent; reserves one call and 256 tokens.",
     "inputSchema":{"type":"object","properties":{"confirm_paid":{"type":"boolean","description":"Set true only after the user explicitly authorizes this small paid DeepSeek connectivity request"}},
                    "required":["confirm_paid"],"additionalProperties":False}},
    {"name":"get_experiment_status","description":"Check an existing Owner run without making model calls. Return stage, checkpoint count, tokens and errors; also sync Development Studio run status.",
     "inputSchema":{"type":"object","properties":{"run_id":{"type":"string"}},"required":["run_id"],"additionalProperties":False}},
    {"name":"get_experiment_result","description":"Read an existing completed Owner SC05 report (limited length), quality indicators and source/pipeline hashes. Read-only. No synthetic scientific scoring.",
     "inputSchema":{"type":"object","properties":{"run_id":{"type":"string"}},"required":["run_id"],"additionalProperties":False}},
    {"name":"prepare_ab_pair","description":"Read-only pair-level preflight. Verify the same source and current pipeline, check both arms, frozen evidence, checkpoints, active jobs and budget. No model calls.",
     "inputSchema":{"type":"object","properties":{"pair_id":{"type":"string"}},"required":["pair_id"],"additionalProperties":False}},
    {"name":"get_ab_pair_status","description":"Read the pair's current phase and next safe action. Use this to monitor the baseline and gated arm without exposing the blind mapping.",
     "inputSchema":{"type":"object","properties":{"pair_id":{"type":"string"}},"required":["pair_id"],"additionalProperties":False}},
    {"name":"start_ab_pair","description":"Paid, idempotent sequential runner. Starts only the next eligible arm: gate-off baseline first; call again after it completes to start gate-on. Never starts both concurrently or duplicates an active/completed arm. Requires explicit DeepSeek spending consent.",
     "inputSchema":{"type":"object","properties":{
         "pair_id":{"type":"string"},
         "confirm_paid":{"type":"boolean","description":"Set true only after the user explicitly authorizes actual DeepSeek model spending in this conversation"}},
         "required":["pair_id","confirm_paid"],"additionalProperties":False}},
    {"name":"get_ab_pair_result","description":"Read completed A/B reports under anonymized labels A/B, with quality warnings and token usage. Does not reveal which arm is which. No model calls.",
     "inputSchema":{"type":"object","properties":{"pair_id":{"type":"string"}},"required":["pair_id"],"additionalProperties":False}},
    {"name":"record_blind_review","description":"Save a human- or assistant-produced blind score for anonymized report A or B. Requires both reports complete; does not reveal the variant mapping.",
     "inputSchema":{"type":"object","properties":{
         "pair_id":{"type":"string"},"label":{"type":"string","enum":["A","B"]},
         "accuracy":{"type":"integer","minimum":0,"maximum":5},
         "science_value":{"type":"integer","minimum":0,"maximum":5},
         "narrative":{"type":"integer","minimum":0,"maximum":5},
         "literature":{"type":"integer","minimum":0,"maximum":5},
         "feasibility":{"type":"integer","minimum":0,"maximum":5},
         "hard_failure":{"type":"boolean"},"feedback":{"type":"string"},
         "failure_tags":{"type":"array","items":{"type":"string"}}},
         "required":["pair_id","label","accuracy","science_value","narrative","literature","feasibility"],
         "additionalProperties":False}},
    {"name":"compare_ab_pair","description":"Unblind and compare the A/B pair only after both anonymized reports have blind scores. Returns score deltas, quality warnings and usage.",
     "inputSchema":{"type":"object","properties":{"pair_id":{"type":"string"}},"required":["pair_id"],"additionalProperties":False}},
    {"name":"list_experiment_rounds","description":"List the persistent Owner experiment-round ledger, categories, brief results, next steps and detailed records. Read-only.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"record_experiment_round","description":"Create or update one durable experiment-round row. Link it to an A/B pair so status, source hash, pipeline hash and run details can be synchronized automatically.",
     "inputSchema":{"type":"object","properties":{
         "round_code":{"type":"string"},"category_code":{"type":"string"},"category_label":{"type":"string"},
         "problem":{"type":"string"},"method":{"type":"string"},"experiment_content":{"type":"string"},
         "status":{"type":"string","enum":["planned","running","completed","needs_review","blocked","cancelled"]},
         "brief_result":{"type":"string"},"next_step":{"type":"string"},
         "detailed_record":{"type":"object"},"pair_id":{"type":"string"}},
         "required":["round_code","category_code","category_label","problem","method","experiment_content"],
         "additionalProperties":False}}
]


# Publish per-tool OAuth requirements so ChatGPT can request the
# experiments:run grant and perform step-up after an earlier read-only link.
for _tool in TOOLS:
    _write = _tool["name"] in {
        "create_ab_pair","start_experiment","start_ab_pair",
        "probe_model_connection","record_blind_review","record_experiment_round"
    }
    _scopes = [READ, RUN] if _write else [READ]
    _tool["securitySchemes"] = [{"type":"oauth2","scopes":_scopes}]
    _tool["_meta"] = {"securitySchemes":[{"type":"oauth2","scopes":_scopes}]}
    _tool["annotations"] = {
        "readOnlyHint":not _write,
        "destructiveHint":False,
        "openWorldHint":bool(_write),
    }


def result(value, *, error=False):
    return {"content":[{"type":"text","text":json.dumps(value,ensure_ascii=False,default=str)}],
            "isError":bool(error)}


def own_run(db,owner,run_id):
    if not re.fullmatch(r"sc05run_[a-f0-9]{20,32}",run_id):
        raise HTTPException(400,"Invalid run ID")
    row=db.get(SC05Run,run_id)
    if row is None or row.member_id!=owner.id:
        raise HTTPException(404,"Run not found")
    return row


ROUND_CATEGORIES=[
    {"code":"◆01","label":"工作流完整性"},
    {"code":"●02","label":"科学质量"},
    {"code":"▲03","label":"证据与文献关联"},
    {"code":"■04","label":"创新性与研究路线"},
    {"code":"◇05","label":"执行稳定性与成本"},
]
ROUND_STATUSES={"planned","running","completed","needs_review","blocked","cancelled"}
FAILURE_TAGS={"paper_understanding","science_value","mechanism_narrative",
              "literature_depth","feasibility","citation_error"}


def round_view(row):
    return {
        "id":row.id,"round_code":row.round_code,
        "category_code":row.category_code,"category_label":row.category_label,
        "problem":row.problem,"method":row.method,
        "experiment_content":row.experiment_content,"status":row.status,
        "brief_result":row.brief_result,"next_step":row.next_step,
        "detailed_record":load(row.detailed_record_json,{}),
        "pair_id":row.pair_id,"source_sha256":row.source_sha,
        "pipeline_sha256":row.pipeline_sha,
        "created_at":row.created_at.isoformat() if row.created_at else None,
        "updated_at":row.updated_at.isoformat() if row.updated_at else None,
    }


def pair_rows(db,owner,pair_id):
    if not re.fullmatch(r"sc05pair_[a-f0-9]{20,32}",str(pair_id or "")):
        raise HTTPException(400,"Invalid SC05 pair ID")
    rows=db.scalars(select(SC05Run).where(
        SC05Run.member_id==owner.id,SC05Run.pair_id==pair_id
    ).order_by(SC05Run.created_at,SC05Run.id)).all()
    by_variant={row.variant:row for row in rows}
    if len(rows)!=2 or set(by_variant)!={"science_gate_off","science_gate_on"}:
        raise HTTPException(404,"A complete Owner A/B pair was not found")
    if len({row.case_id for row in rows})!=1:
        raise HTTPException(409,"A/B pair source case mismatch")
    paper=db.get(SC05Case,rows[0].case_id)
    if paper is None or paper.member_id!=owner.id:
        raise HTTPException(404,"A/B source paper not found")
    return by_variant,paper


def _arm_summary(row,check=None):
    return {
        "status":row.status,"stage":row.stage,
        "model_calls":row.calls,"input_tokens":row.input_tokens,
        "output_tokens":row.output_tokens,
        "saved_checkpoints":len(load(row.checkpoints_json,[])),
        "error":row.error,
        "safe_to_submit":bool(check and check.get("safe_to_submit")),
        "gate_ready":bool(check and check.get("gate_ready")),
        "repair_check":check.get("repair_check") if check else None,
    }


def pair_preflight(db,owner,pair_id):
    by,paper=pair_rows(db,owner,pair_id)
    baseline=by["science_gate_off"]
    gated=by["science_gate_on"]
    baseline_check=preflight(db,owner,baseline.id)
    gate_check=preflight(db,owner,gated.id)
    current_sha=pipeline_sha()
    pipeline_consistent=(baseline.pipeline_sha==gated.pipeline_sha)
    pipeline_current=(baseline.pipeline_sha==current_sha and gated.pipeline_sha==current_sha)
    active=any(row.status in ("queued","claimed","running") for row in (baseline,gated))
    if not pipeline_consistent or not pipeline_current:
        next_action="needs_review"
        reason="A/B source-pinned pipeline hashes differ or are not current; create a clean pair rather than silently migrating both arms."
    elif active:
        next_action="wait_for_completion"
        reason="One A/B arm is already queued or running; do not submit another arm concurrently."
    elif baseline.status!="completed":
        if baseline.status in ("prepared","failed") and baseline_check.get("safe_to_submit"):
            next_action="start_baseline"
            reason="The gate-off baseline is the next eligible arm."
        else:
            next_action="review_baseline"
            reason="The baseline is not safe to submit; inspect its saved checkpoints and error."
    elif not paper.shared_evidence_json:
        next_action="needs_review"
        reason="The baseline is marked complete but no frozen shared evidence snapshot exists."
    elif gated.status!="completed":
        if gated.status in ("prepared","failed") and gate_check.get("safe_to_submit"):
            next_action="start_gate"
            reason="The baseline has frozen shared evidence; the gate-on arm is the next eligible arm."
        else:
            next_action="review_gate"
            reason="The gate-on arm is not safe to submit; inspect its saved checkpoints and error."
    else:
        next_action="blind_review"
        reason="Both real A/B runs are complete. Retrieve anonymized reports, score them blindly, then unblind."
    if baseline.status=="completed" and gated.status=="completed":
        pair_status="completed"
    elif any(row.status=="failed" for row in (baseline,gated)):
        pair_status="needs_review"
    elif active or baseline.status=="completed":
        pair_status="running"
    else:
        pair_status="planned"
    return {
        "pair_id":pair_id,"pair_status":pair_status,
        "source_sha256":paper.source_sha,
        "pipeline_sha256":current_sha,
        "pipeline_hashes_consistent":pipeline_consistent,
        "pipeline_hashes_current":pipeline_current,
        "shared_evidence_frozen":bool(paper.shared_evidence_json),
        "baseline":_arm_summary(baseline,baseline_check),
        "gate":_arm_summary(gated,gate_check),
        "next_action":next_action,"reason":reason,
        "can_start_next":next_action in ("start_baseline","start_gate"),
        "budget":budget_status(db),
        "paid_execution_enabled":os.getenv("SC05_MCP_PAID_ENABLED","").lower() in ("true","1"),
    }


def blind_order(rows,pair_id):
    return sorted(rows,key=lambda row:hashlib.sha256(
        (pair_id+":"+row.id).encode()).hexdigest())


def sync_round_from_pair(db,owner,pair_id):
    row=db.scalars(select(SC05ExperimentRound).where(
        SC05ExperimentRound.member_id==owner.id,
        SC05ExperimentRound.pair_id==pair_id
    ).limit(1)).first()
    if row is None:
        return None
    state=pair_preflight(db,owner,pair_id)
    by,_=pair_rows(db,owner,pair_id)
    if state["pair_status"]=="completed":
        rating_ids=db.scalars(select(SC05Rating.run_id).where(
            SC05Rating.member_id==owner.id,
            SC05Rating.run_id.in_([r.id for r in by.values()])
        )).all()
        unblinded=db.scalar(select(AuditEntry.id).where(
            AuditEntry.actor_id==owner.id,
            AuditEntry.action=="sc05.ab_unblinded",
            AuditEntry.target==pair_id
        ).limit(1)) is not None
        if unblinded and len(set(rating_ids))==2:
            row.brief_result="A/B 两组运行、盲评、解盲比较均已完成；请查看评分差异及科学质量限制。"
            row.next_step="优先修复文献检索与近邻证据链，再评估选题新颖性和可执行性。"
        elif len(set(rating_ids))==2:
            row.brief_result="A/B 两组已完成并完成盲评，等待解盲比较。"
            row.next_step="执行 A/B 解盲比较，记录质量差异与下一轮修复点。"
        else:
            row.brief_result="A/B 两组真实运行均已完成；尚未完成盲评，暂不形成优劣结论。"
            row.next_step="读取匿名 A/B 报告，按统一评价标准盲评。"
    elif state["pair_status"]=="needs_review":
        row.brief_result="运行遇到需要人工复核的失败或版本不一致；未将失败视为实验结果。"
        row.next_step="检查失败检查点、提示词哈希和版本一致性，必要时新建干净配对。"
    elif state["pair_status"]=="running":
        row.brief_result="云端 A/B 工作流正在执行，或基线已完成、门控版本等待启动。"
        row.next_step="等待当前阶段完成，再预检并启动下一阶段。"
    else:
        row.brief_result="已创建 A/B 配对，尚未产生模型调用。"
        row.next_step="完成成对预检后，先启动 gate-off 基线。"
    row.status=state["pair_status"]
    row.source_sha=state["source_sha256"]
    row.pipeline_sha=state["pipeline_sha256"]
    row.detailed_record_json=dump({
        "pair_id":pair_id,"source_sha256":state["source_sha256"],
        "pipeline_sha256":state["pipeline_sha256"],
        "pipeline_hashes_consistent":state["pipeline_hashes_consistent"],
        "pipeline_hashes_current":state["pipeline_hashes_current"],
        "shared_evidence_frozen":state["shared_evidence_frozen"],
        "baseline":state["baseline"],"gate":state["gate"],
        "budget":state["budget"],"next_action":state["next_action"],
        "updated_at":now().isoformat(),
    })
    row.updated_at=now()
    return row


def upsert_round(db,owner,arguments,pair_id_override=None):
    round_code=str(arguments.get("round_code","")).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}",round_code):
        raise HTTPException(422,"round_code must be a short stable code such as R6.2")
    category_code=str(arguments.get("category_code","◆01")).strip()
    category_label=str(arguments.get("category_label","工作流完整性")).strip()
    problem=str(arguments.get("problem","")).strip()
    method=str(arguments.get("method","")).strip()
    experiment_content=str(arguments.get("experiment_content","")).strip()
    if not category_code or len(category_code)>16 or not category_label or len(category_label)>80:
        raise HTTPException(422,"Invalid experiment category")
    if not problem or len(problem)>4000 or not method or len(method)>4000 or not experiment_content or len(experiment_content)>4000:
        raise HTTPException(422,"Problem, method and experiment content are required (max 4000 characters each)")
    status=str(arguments.get("status","planned")).strip()
    if status not in ROUND_STATUSES:
        raise HTTPException(422,"Unknown experiment-round status")
    brief_result=str(arguments.get("brief_result","")).strip()
    next_step=str(arguments.get("next_step","等待成对预检")).strip()
    if len(brief_result)>3000 or len(next_step)>2000:
        raise HTTPException(422,"Round result or next step is too long")
    detailed=arguments.get("detailed_record",{})
    if not isinstance(detailed,(dict,list)):
        raise HTTPException(422,"detailed_record must be a JSON object or array")
    detailed_json=dump(detailed)
    if len(detailed_json)>25000:
        raise HTTPException(422,"detailed_record exceeds 25 KB")
    pair_id=pair_id_override or arguments.get("pair_id")
    paper=None
    if pair_id:
        _,paper=pair_rows(db,owner,pair_id)
    row=db.scalars(select(SC05ExperimentRound).where(
        SC05ExperimentRound.member_id==owner.id,
        SC05ExperimentRound.round_code==round_code
    ).limit(1)).first()
    if row is not None and row.pair_id and pair_id and row.pair_id!=pair_id:
        raise HTTPException(409,"This round code is already linked to another A/B pair")
    if pair_id:
        other=db.scalars(select(SC05ExperimentRound).where(
            SC05ExperimentRound.member_id==owner.id,
            SC05ExperimentRound.pair_id==pair_id
        ).limit(1)).first()
        if other is not None and other.round_code!=round_code:
            raise HTTPException(409,"This A/B pair is already linked to another round code")
    if row is None:
        row=SC05ExperimentRound(
            id="sc05round_"+uuid.uuid4().hex[:28],
            member_id=owner.id,round_code=round_code,
            category_code=category_code,category_label=category_label,
            problem=problem,method=method,experiment_content=experiment_content,
            status=status,brief_result=brief_result,next_step=next_step,
            detailed_record_json=detailed_json,pair_id=pair_id,
            source_sha=paper.source_sha if paper else "",
            pipeline_sha=pipeline_sha() if paper else "",
        )
        db.add(row)
    else:
        row.category_code=category_code
        row.category_label=category_label
        row.problem=problem
        row.method=method
        row.experiment_content=experiment_content
        row.status=status
        row.brief_result=brief_result
        row.next_step=next_step
        row.detailed_record_json=detailed_json
        if pair_id:
            row.pair_id=pair_id
            row.source_sha=paper.source_sha
            row.pipeline_sha=pipeline_sha()
        row.updated_at=now()
    db.flush()
    if pair_id:
        sync_round_from_pair(db,owner,pair_id)
    add_audit(db,"sc05.round_recorded",owner.id,row.id,
              "round="+round_code+";pair="+(pair_id or "none"))
    return row


def _start_mcp_run(app,db,owner,row,background,paid_enabled,confirm_paid):
    if not confirm_paid:
        raise HTTPException(422,"Explicit consent for actual DeepSeek model spending is required")
    if not paid_enabled:
        raise HTTPException(503,"Owner delegated paid starts are disabled")
    if os.getenv("SC05_MCP_ENFORCE_WORKER_READINESS","true").lower() not in ("false","0") and not (
        worker_flag("SC05_INLINE_WORKER_ENABLED")
        and worker_flag("SC05_INLINE_WORKER_LIVE_ENABLED")
        and os.getenv("SC05_EXECUTION_MODE","").lower()=="worker"
    ):
        raise HTTPException(503,"Cloud worker not ready; paid jobs cannot be queued")
    approval_before=db.get(SC05DelegatedAuthorization,row.id)
    queued_retry=(row.status=="queued" and approval_before is not None
                  and approval_before.status=="needs_review")
    previous_status=row.status
    check=preflight(db,owner,row.id)
    if not check["safe_to_submit"]:
        raise HTTPException(409,"Run not safe to start; inspect checkpoint/preflight")
    budget=budget_status(db)
    if budget["used"]["model_calls"]>=budget["limits"]["model_calls_per_day"]:
        raise HTTPException(409,"Daily model budget exhausted")
    if queued_retry:
        previous_sha=row.pipeline_sha
        row.pipeline_sha=pipeline_sha()
        row.updated_at=now()
        approval_before.status="approved"
        approval_before.granted_at=now()
        approval_before.processed_at=None
        add_audit(db,"sc05.mcp_paid_resume",owner.id,row.id,
                  "Re-approved needs_review authorization after zero-paid checkpoint validation; old_sha="+
                  previous_sha[:16]+";new_sha="+row.pipeline_sha[:16])
        db.commit()
        started=run_view(row)
    else:
        from fastapi.routing import iter_route_contexts
        endpoint=next((ctx.endpoint for ctx in iter_route_contexts(app.routes)
          if ctx.path=="/api/personal-research/me/sc05/runs/{run_id}/start"
          and "POST" in (ctx.methods or set())),None)
        if endpoint is None:
            raise HTTPException(503,"SC05 start route unavailable")
        started=endpoint(row.id,StartRequest(acknowledge_external_model=True),
                         background,db,owner)
        db.refresh(row)
        approval=db.get(SC05DelegatedAuthorization,row.id)
        if approval:
            if previous_status=="failed" and approval.status=="needs_review":
                approval.status="approved"
                approval.granted_at=now()
                approval.processed_at=None
                audit_action="sc05.mcp_paid_resume"
                audit_detail="Re-approved needs_review authorization after zero-paid checkpoint validation"
            else:
                raise HTTPException(409,"Delegated authorization already exists")
        else:
            db.add(SC05DelegatedAuthorization(
                run_id=row.id,member_id=owner.id,status="approved"
            ))
            audit_action="sc05.mcp_paid_start"
            audit_detail="OAuth run scope + per-call paid consent"
        add_audit(db,audit_action,owner.id,row.id,audit_detail)
        db.commit()
    devstudio_id=register_devstudio(db,owner,row)
    return {"run":started,"devstudio_experiment_id":devstudio_id,
            "message":"Experiment enqueued; use get_ab_pair_status to follow progress."}


def list_owned(db,owner):
    cases=db.scalars(select(SC05Case).where(SC05Case.member_id==owner.id)
                     .order_by(SC05Case.created_at.desc()).limit(30)).all()
    runs=db.scalars(select(SC05Run).where(SC05Run.member_id==owner.id)
                    .order_by(SC05Run.created_at.desc()).limit(70)).all()
    rounds=db.scalars(select(SC05ExperimentRound).where(
        SC05ExperimentRound.member_id==owner.id
    ).order_by(SC05ExperimentRound.created_at.desc()).limit(100)).all()
    run_views=[]
    for run in runs:
        view=run_view(run)
        rated=db.scalars(select(SC05Rating.id).where(
            SC05Rating.member_id==owner.id,SC05Rating.run_id==run.id
        ).limit(1)).first()
        if rated is None:
            # Keep the opaque run ID usable for preflight/recovery, but never
            # disclose whether it is the baseline or gated arm before blind review.
            view.pop("variant",None)
            view["arm"]="blind_pending"
        run_views.append(view)
    return {
        "cases":[case_view(x) for x in cases],
        "runs":run_views,
        "rounds":[round_view(x) for x in rounds],
        "round_categories":ROUND_CATEGORIES,
        "budget":budget_status(db),
    }



class _SC05PrefixBoundary(Exception):
    pass


def diagnose_search_query_checkpoint(row, paper):
    """Read-only replay of the four saved gated stages; never calls DeepSeek/OpenAlex."""
    if row.status != "failed" or row.error != "Missing/invalid search query":
        raise EvidenceError("Not a saved search-query validation failure")
    if row.variant != "science_gate_on" or row.calls != 4:
        raise EvidenceError("Only the four-stage gated search-query failure is supported")
    entries = load(row.checkpoints_json, [])
    expected = ["method_lineage", "diagnosis", "scientific_value_triage", "evidence_questions"]
    if not isinstance(entries, list) or len(entries) != 4:
        raise EvidenceError("Expected exactly four saved model checkpoints")
    if [x.get("stage") for x in entries if isinstance(x, dict)] != expected:
        raise EvidenceError("Saved checkpoint stages are incomplete or reordered")
    pages = load(paper.pages_json, {})
    frozen = load(paper.shared_evidence_json)
    cursor = [0]
    captured = {}

    def cached_only(api_key, model, system, payload, max_tokens=3000):
        if cursor[0] >= len(entries):
            raise _SC05PrefixBoundary()
        entry = entries[cursor[0]]
        fingerprint = hashlib.sha256(dump({
            "model": model, "system": system, "payload": payload,
            "max_tokens": max_tokens,
        }).encode()).hexdigest()
        if (entry.get("prompt_sha256") != fingerprint
            or entry.get("stage") != payload.get("sc05_stage")
            or entry.get("model") != model):
            raise EvidenceError("Saved prompt fingerprint mismatch at " + str(payload.get("sc05_stage")))
        if payload.get("sc05_stage") == "evidence_questions":
            captured["response"] = entry.get("response")
        cursor[0] += 1
        return entry.get("response"), entry.get("usage", {})

    def stop_before_search(*args, **kwargs):
        raise _SC05PrefixBoundary()

    outcome = "unknown"
    reason = ""
    try:
        run_paper(
            None, "cached-response-only", model_call=cached_only,
            search_provider=stop_before_search, source_title=paper.title,
            pages_override=pages, source_sha=paper.source_sha,
            frozen_snapshot=frozen, scientific_value_gate=True, max_calls=40,
        )
    except _SC05PrefixBoundary:
        outcome = "parser_passed"
    except EvidenceError as exc:
        reason = str(exc)[:180]
        if reason == "Missing/invalid search query":
            outcome = "query_validation_failed"
        else:
            raise
    raw = captured.get("response")
    if not isinstance(raw, dict):
        raise EvidenceError("Saved evidence_questions response is not an object")
    items = raw.get("queries")
    summaries = []
    if isinstance(items, list):
        for item in items[:7]:
            if not isinstance(item, dict):
                summaries.append({"item_type": type(item).__name__})
                continue
            value = item.get("query")
            aliases = [key for key in ("search_query", "question", "text")
                       if isinstance(item.get(key), str) and item.get(key).strip()]
            summaries.append({
                "keys": sorted(str(k) for k in item.keys()),
                "need": item.get("need"),
                "query_type": type(value).__name__,
                "query_length": len(value) if isinstance(value, str) else None,
                "query_blank": not value.strip() if isinstance(value, str) else None,
                "query_alias_fields": aliases,
                "assumption_length": (len(item.get("assumption_to_test"))
                    if isinstance(item.get("assumption_to_test"), str) else None),
            })
    return {
        "ready": outcome == "parser_passed",
        "outcome": outcome,
        "reason": reason,
        "cached_stages": cursor[0],
        "prompt_hashes_verified": cursor[0] == 4,
        "queries_type": type(items).__name__,
        "queries_count": len(items) if isinstance(items, list) else None,
        "query_items": summaries,
        "paid_calls_on_check": 0,
        "network_searches_on_check": 0,
    }


def preflight(db,owner,run_id):
    row=own_run(db,owner,run_id)
    paper=db.get(SC05Case,row.case_id)
    checks=load(row.checkpoints_json,[])
    budget=budget_status(db)
    active=db.scalars(select(SC05Run.id).where(
        SC05Run.member_id==owner.id,SC05Run.id!=row.id,
        SC05Run.status.in_(("queued","claimed","running"))).limit(1)).first()
    gate_ready=row.variant!="science_gate_on" or bool(paper.shared_evidence_json)
    # Failed runs are eligible only after the exact saved first-stage checkpoint
    # passes the existing Owner repair validator. This is read-only: it checks
    # source quotes, prompt fingerprint, model and saved usage without a provider call.
    repair_ready=False
    repair_summary=None
    delegated=db.get(SC05DelegatedAuthorization,row.id)
    if row.status=="queued" and delegated and delegated.status=="needs_review":
        try:
            literature_info=check_literature_diagnosis_resume(
                row,paper,allow_queued=True)
            repair_summary={"literature_diagnosis_repair":literature_info,
                            "queued_retry_authorization":"needs_review"}
            repair_ready=True
        except (EvidenceError,ValueError,TypeError) as exc:
            repair_summary={"ready":False,"reason":str(exc)[:180],"paid_calls_on_check":0}
    elif row.status=="failed" and row.error=="Missing/invalid search query":
        try:
            query_info=diagnose_search_query_checkpoint(row,paper)
            repair_summary={"search_query_repair":query_info}
            repair_ready=bool(query_info.get("ready"))
        except (EvidenceError,ValueError,TypeError) as exc:
            repair_summary={"ready":False,"reason":str(exc)[:180],"paid_calls_on_check":0}
    elif row.status=="failed" and row.error=="Missing references: literature diagnosis":
        try:
            literature_info=check_literature_diagnosis_resume(row,paper)
            repair_summary={"literature_diagnosis_repair":literature_info}
            repair_ready=True
        except (EvidenceError,ValueError,TypeError) as exc:
            repair_summary={"ready":False,"reason":str(exc)[:180],"paid_calls_on_check":0}
    elif row.status=="failed":
        try:
            info=check_fact_type_resume(row,paper)
            repair_ready=True
            repair_summary={
                "replay_prompt_matches":bool(info.get("replay_prompt_matches")),
                "saved_facts":int(info.get("facts",0)),
                "rejected_quotes":int(info.get("rejected_quotes",0)),
                "normalized_types":info.get("types",[]),
                "paid_calls_on_check":0,
            }
        except (EvidenceError,ValueError,TypeError) as exc:
            repair_summary={"ready":False,"reason":str(exc)[:180],"paid_calls_on_check":0}
    failed_needs_review=row.status=="failed" and not repair_ready
    safe_status=(
        row.status=="prepared"
        or (row.status=="failed" and repair_ready)
        or (row.status=="queued" and delegated and delegated.status=="needs_review" and repair_ready)
    )
    return {
        "run":run_view(row),"source_sha256":paper.source_sha,
        "saved_checkpoints":len(checks),
        "shared_facts_frozen":bool(paper.shared_evidence_json),
        "busy":bool(active),"gate_ready":gate_ready,
        "safe_to_submit":safe_status and gate_ready and not active,
        "failed_needs_review":failed_needs_review,
        "repair_check":repair_summary,
        "budget":budget,
        "paid_execution_enabled":os.getenv("SC05_MCP_PAID_ENABLED","").lower() in ("true","1"),
        "note":"Failed runs are released only after exact cached-checkpoint validation; the original Owner endpoint performs the same validation again before queueing."
    }


def register_devstudio(db,owner,row):
    # Link to the existing Development Studio without altering SC05's pinned
    # source files (which would invalidate historic checkpoint hashes).
    from backend.devstudio import DevExperiment, DevRunRef, new_id, encode
    marker="SC05:"+row.pair_id
    experiment=db.scalars(select(DevExperiment).where(
        DevExperiment.created_by==owner.id,DevExperiment.input_snapshot_ref==marker
    ).limit(1)).first()
    if experiment is None:
        experiment=DevExperiment(
            id=new_id("exp"),module_id="PLATFORM",
            title="SC05 Scientific Value Gate A/B · "+row.pair_id[-8:],
            hypothesis="Compare the frozen-evidence SC05 model with and without the Scientific Value Gate.",
            baseline="science_gate_off",input_snapshot_ref=marker,
            metrics_json=encode(["source_accuracy","science_value","narrative","literature","feasibility"]),
            status="running",created_by=owner.id)
        db.add(experiment)
        db.flush()
    target="/api/tasks/sc05/"+row.id
    link=db.scalars(select(DevRunRef).where(
        DevRunRef.experiment_id==experiment.id,DevRunRef.external_url==target
    ).limit(1)).first()
    if link is None:
        link=DevRunRef(id=new_id("run"),experiment_id=experiment.id,
                       kind="internal",external_url=target,
                       code_sha=row.pipeline_sha,input_hash=db.get(SC05Case,row.case_id).source_sha,
                       status=row.status,registered_by=owner.id,
                       note="Auto-synced SC05 "+row.variant)
        db.add(link)
    else:
        link.status=row.status
    statuses=db.scalars(select(SC05Run.status).where(
        SC05Run.pair_id==row.pair_id,SC05Run.member_id==owner.id)).all()
    if statuses and all(s=="completed" for s in statuses):
        experiment.status="completed"
    elif any(s=="failed" for s in statuses):
        experiment.status="needs_review"
    elif any(s in ("queued","claimed","running") for s in statuses):
        experiment.status="running"
    add_audit(db,"sc05.mcp_devstudio_sync",owner.id,row.id,experiment.id)
    db.commit()
    return experiment.id


def mount(app,*,get_db,get_factory):
    router=APIRouter()
    @router.get("/.well-known/oauth-protected-resource")
    def resource_metadata():
        enabled()
        base=public_base()
        return {"resource":base+"/mcp","authorization_servers":[base],
                "scopes_supported":[READ,RUN],"bearer_methods_supported":["header"]}

    @router.get("/.well-known/oauth-authorization-server")
    def authorization_metadata():
        enabled()
        base=public_base()
        return {"issuer":base,"authorization_endpoint":base+"/oauth/authorize",
                "token_endpoint":base+"/oauth/token",
                "response_types_supported":["code"],
                "grant_types_supported":["authorization_code","refresh_token"],
                "token_endpoint_auth_methods_supported":["none"],
                "code_challenge_methods_supported":["S256"],
                "authorization_response_iss_parameter_supported":True,
                "revocation_endpoint":base+"/oauth/revoke",
                "scopes_supported":[READ,RUN],
                "client_id_metadata_document_supported":True}

    @router.get("/oauth/authorize",response_class=HTMLResponse)
    def authorize_page(request:Request):
        enabled()
        data=dict(request.query_params)
        authorize_request(data)
        return HTMLResponse(form_html(data),headers={"Cache-Control":"no-store",
                  # Chromium/WebKit enforce form-action across the full
                  # POST -> 303 redirect chain. 'self' alone blocked our
                  # validated ChatGPT OAuth callback while the form appeared
                  # unresponsive. Allow only the fixed callback origin.
                  "Content-Security-Policy":"default-src 'none';style-src 'unsafe-inline';form-action 'self' https://chatgpt.com;base-uri 'none';frame-ancestors 'none'",
                  "Referrer-Policy":"no-referrer"})

    @router.post("/oauth/authorize")
    async def authorize_submit(request:Request,db:Session=Depends(get_db)):
        enabled()
        if len(await request.body())>8192:
            raise HTTPException(413,"OAuth form too large")
        data={k:v[0] for k,v in parse_qs((await request.body()).decode("utf-8"),keep_blank_values=True).items()}
        base,scopes=authorize_request(data)
        email=data.get("email","")
        password=data.get("password","")
        if not email or not password:
            raise HTTPException(400,"Owner sign-in required")
        logged=member_login(db,email,password,request.client.host if request.client else "unknown")
        if logged is None:
            raise HTTPException(401,"Invalid Owner credentials")
        session,member=logged
        revoke_session(db,session,member.id)
        if member.role!="owner" or not member.active:
            raise HTTPException(403,"Verified active Owner required")
        code=secrets.token_urlsafe(40)
        db.add(OAuthCode(code_hash=digest(code),member_id=member.id,
            challenge=data["code_challenge"],client_id=CLIENT,redirect_uri=REDIRECT,
            resource=base+"/mcp",scopes=" ".join(sorted(scopes)),
            expires_at=now_seconds()+300))
        add_audit(db,"sc05.mcp_authorized",member.id,"chatgpt",",".join(sorted(scopes)))
        db.commit()
        return RedirectResponse(REDIRECT+"?"+urlencode({"code":code,
            "state":data["state"],"iss":base}),status_code=303)

    @router.post("/oauth/token")
    async def exchange_token(request:Request,db:Session=Depends(get_db)):
        enabled()
        body=await request.body()
        if len(body)>8192:raise HTTPException(413,"OAuth token request too large")
        fields={k:v[0] for k,v in parse_qs(body.decode("utf-8"),keep_blank_values=True).items()}
        grant=fields.get("grant_type")
        if fields.get("client_id")!=CLIENT or fields.get("resource")!=public_base()+"/mcp":
            raise HTTPException(400,"invalid_client_or_resource")
        if grant=="authorization_code":
            row=db.get(OAuthCode,digest(fields.get("code","")))
            if row is None or row.expires_at<now_seconds():
                raise HTTPException(400,"invalid_grant")
            verifier=fields.get("code_verifier","")
            expected=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}",verifier) or expected!=row.challenge:
                raise HTTPException(400,"invalid_grant")
            if row.client_id!=CLIENT or row.redirect_uri!=fields.get("redirect_uri") or row.resource!=fields["resource"]:
                raise HTTPException(400,"invalid_grant")
            owner=db.get(TeamMember,row.member_id)
            if owner is None or not owner.active or owner.role!="owner":
                raise HTTPException(403,"Owner no longer active")
            member_id,scope=row.member_id,row.scopes
            db.delete(row)
            db.flush()
            response=token_response(db,owner,CLIENT,fields["resource"],scope)
            add_audit(db,"sc05.mcp_token_issued",member_id,"chatgpt")
            db.commit()
            return JSONResponse(response,headers={"Cache-Control":"no-store","Pragma":"no-cache"})
        if grant=="refresh_token":
            old=db.scalars(select(OAuthGrant).where(
                OAuthGrant.refresh_hash==digest(fields.get("refresh_token",""))
            ).with_for_update()).first()
            if (old is None or old.revoked or old.refresh_expires_at<now_seconds()
                or old.client_id!=CLIENT or old.resource!=fields["resource"]):
                raise HTTPException(400,"invalid_grant")
            owner=db.get(TeamMember,old.member_id)
            if owner is None or not owner.active or owner.role!="owner":
                raise HTTPException(403,"Owner no longer active")
            old.revoked=1
            db.flush()
            response=token_response(db,owner,old.client_id,old.resource,old.scopes)
            add_audit(db,"sc05.mcp_token_refreshed",owner.id,"chatgpt")
            db.commit()
            return JSONResponse(response,headers={"Cache-Control":"no-store","Pragma":"no-cache"})
        raise HTTPException(400,"unsupported_grant_type")

    @router.post("/oauth/revoke")
    async def revoke_oauth(request:Request,db:Session=Depends(get_db)):
        enabled()
        body=await request.body()
        if len(body)>4096:raise HTTPException(413,"OAuth revocation payload too large")
        fields={k:v[0] for k,v in parse_qs(body.decode("utf-8")).items()}
        if fields.get("client_id")!=CLIENT:
            raise HTTPException(400,"Unknown OAuth client")
        provided=fields.get("token","")
        for column in (OAuthGrant.access_hash,OAuthGrant.refresh_hash):
            row=db.scalars(select(OAuthGrant).where(column==digest(provided)).limit(1)).first()
            if row:
                row.revoked=1
                add_audit(db,"sc05.mcp_token_revoked",row.member_id,"chatgpt")
                db.commit()
                break
        return {"revoked":True}

    @router.get("/api/mcp/delegations")
    def list_delegations(request:Request,db:Session=Depends(get_db)):
        enabled()
        # This management route uses regular Owner session authentication,
        # *not* the delegated token itself, so a stolen MCP token cannot
        # inspect or revoke other grants.
        from backend.team import resolve_session
        expected=os.getenv("API_BEARER_TOKEN","")
        if not expected or not secrets.compare_digest(
            request.headers.get("Authorization",""),"Bearer "+expected):
            raise HTTPException(401,"Backend authorization required")
        owner=resolve_session(db,request.headers.get("X-Research-Session"))
        if owner is None or owner.role!="owner" or not owner.active:
            raise HTTPException(403,"Owner login required")
        rows=db.scalars(select(OAuthGrant).where(
            OAuthGrant.member_id==owner.id).order_by(OAuthGrant.expires_at.desc()).limit(50)).all()
        return {"items":[{"grant_id":r.access_hash,"scopes":r.scopes,
                          "access_expires_at":r.expires_at,
                          "refresh_expires_at":r.refresh_expires_at,
                          "revoked":bool(r.revoked)} for r in rows]}

    @router.post("/api/mcp/delegations/{grant_id}/revoke")
    def revoke_delegation(grant_id:str,request:Request,db:Session=Depends(get_db)):
        enabled()
        from backend.team import resolve_session
        expected=os.getenv("API_BEARER_TOKEN","")
        if not expected or not secrets.compare_digest(
            request.headers.get("Authorization",""),"Bearer "+expected):
            raise HTTPException(401,"Backend authorization required")
        owner=resolve_session(db,request.headers.get("X-Research-Session"))
        if owner is None or owner.role!="owner" or not owner.active:
            raise HTTPException(403,"Owner login required")
        if not re.fullmatch(r"[a-f0-9]{64}",grant_id):
            raise HTTPException(400,"Invalid grant ID")
        row=db.get(OAuthGrant,grant_id)
        if row is None or row.member_id!=owner.id:
            raise HTTPException(404,"No such delegated access")
        row.revoked=1
        add_audit(db,"sc05.mcp_token_revoked",owner.id,grant_id[:16],
                  "Owner revoked delegated ChatGPT access")
        db.commit()
        return {"revoked":True}

    @router.api_route("/mcp",methods=["GET","POST","DELETE"])
    async def mcp_endpoint(request:Request,background:BackgroundTasks,
                           db:Session=Depends(get_db)):
        paid_enabled=enabled()
        base=public_base()
        origin=request.headers.get("origin","")
        if origin and origin not in {"https://chatgpt.com","https://chat.openai.com",base}:
            raise HTTPException(403,"Origin not allowed")
        raw=request.headers.get("authorization","")
        auth=raw.removeprefix("Bearer ") if raw.startswith("Bearer ") else ""
        grant=db.get(OAuthGrant,digest(auth)) if auth else None
        if grant is None or grant.revoked or grant.expires_at<now_seconds() or grant.resource!=base+"/mcp":
            return JSONResponse({"error":"Authorization required"},status_code=401,
                    headers={"WWW-Authenticate":required_scope_challenge(),
                             "Cache-Control":"no-store"})
        owner=db.get(TeamMember,grant.member_id)
        if owner is None or not owner.active or owner.role!="owner":
            raise HTTPException(403,"Owner authorization revoked")
        if request.method!="POST":
            return JSONResponse({"error":"Use POST for stateless MCP"},status_code=405)
        if len(await request.body())>65536:
            raise HTTPException(413,"Request too large")
        try:
            message=json.loads(await request.body())
        except (ValueError,UnicodeError):
            raise HTTPException(400,"Invalid JSON-RPC request")
        if not isinstance(message,dict) or message.get("jsonrpc")!="2.0":
            raise HTTPException(400,"Invalid JSON-RPC envelope")
        method=message.get("method")
        identifier=message.get("id")
        if method=="notifications/initialized" or identifier is None:
            return JSONResponse({},status_code=202)
        try:
            if method=="initialize":
                payload={"protocolVersion":MCP_VERSION,
                         "capabilities":{"tools":{"listChanged":False}},
                         "serverInfo":{"name":"research-atlas-sc05","version":"0.1.0"},
                         "instructions":"Prepare and inspect before paid calls. Only start an existing Owner SC05 experiment with explicit consent. Never claim scientific success without completed A/B reports and blind grading."}
            elif method=="ping":
                payload={}
            elif method=="tools/list":
                payload={"tools":TOOLS}
            elif method=="tools/call":
                params=message.get("params") or {}
                name=params.get("name")
                arguments=params.get("arguments") or {}
                if not isinstance(arguments,dict):
                    raise HTTPException(400,"Tool arguments must be an object")
                scopes=set(grant.scopes.split())
                if READ not in scopes:
                    raise HTTPException(403,"Missing read scope")
                if name=="list_experiments":
                    payload=result(list_owned(db,owner))
                elif name=="get_executor_status":
                    state=worker_status(get_factory())
                    config=model_config_status(db)
                    direct_available=bool(os.getenv("SC04_DEEPSEEK_API_KEY","").strip())
                    state["model_config"]={
                        "configured":bool(config.get("configured")),
                        "vault_ready":bool(config.get("vault_ready")),
                        "fast_model":config.get("fast_model"),
                        "reason_model":config.get("reason_model"),
                        "direct_env_key_available":direct_available,
                        "credential_source":("environment" if direct_available else
                            "encrypted_vault" if config.get("configured") else "missing"),
                    }
                    # This checks configuration only: do not mistake a present
                    # credential for a successful external literature search.
                    retrieval_key_present=bool(os.getenv("OPENALEX_API_KEY","").strip())
                    state["academic_retrieval"]={
                        "provider":"OpenAlex",
                        "api_key_configured":retrieval_key_present,
                        "connection_tested":False,
                        "status":("configured_unverified" if retrieval_key_present
                                  else "missing_api_key"),
                        "note":("Key presence does not establish query success."
                                if retrieval_key_present else
                                "Set a free OPENALEX_API_KEY on the Render service "
                                "before using A/B reports to assess novelty."),
                        "provider_calls_on_check":0,
                    }
                    if arguments.get("probe_openalex") is True:
                        if RUN not in scopes:
                            payload=step_up_result()
                            return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                                headers={"Cache-Control":"no-store"})
                        if not retrieval_key_present:
                            state["academic_retrieval"]["status"]="missing_api_key"
                            state["academic_retrieval"]["note"]="No OpenAlex API key in the running container."
                        else:
                            # Fixed, low-volume query; never return credentials, raw
                            # provider exception text or the URL containing api_key.
                            from research_workbench.core import query_openalex
                            from backend.openalex_errors import safe_openalex_error
                            try:
                                works=query_openalex("urban transit resilience", "2020-01-01", limit=2)
                                if not isinstance(works,list):
                                    raise ValueError("Invalid OpenAlex results")
                                state["academic_retrieval"].update({
                                    "connection_tested":True,
                                    "status":"query_succeeded",
                                    "works_returned":len(works),
                                    "sample_titles":[str(x.get("title") or x.get("display_name") or "")[:180]
                                                     for x in works[:2] if isinstance(x,dict)],
                                    "provider_calls_on_check":"1-3",  # core query_openalex has bounded retries
                                    "note":"API responded; relevance and abstract grounding still require a separate audit.",
                                })
                            except Exception as exc:
                                state["academic_retrieval"].update({
                                    "connection_tested":True,
                                    "status":"query_failed",
                                    "provider_calls_on_check":"1-3",
                                    "error":safe_openalex_error(exc),
                                    "note":"A configured API key does not guarantee a successful search.",
                                })
                    payload=result(state)
                elif name=="get_model_config_status":
                    config=model_config_status(db)
                    direct_available=bool(os.getenv("SC04_DEEPSEEK_API_KEY","").strip())
                    config["direct_env_key_available"]=direct_available
                    config["credential_source"]=(
                        "environment" if direct_available else
                        "encrypted_vault" if config.get("configured") else "missing"
                    )
                    config["provider_calls"]=0
                    payload=result(config)
                elif name=="probe_model_connection":
                    if RUN not in scopes:
                        payload=step_up_result()
                        return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                            headers={"Cache-Control":"no-store"})
                    if not paid_enabled:
                        raise HTTPException(503,"Owner delegated paid starts are disabled")
                    if arguments.get("confirm_paid") is not True:
                        raise HTTPException(422,"Explicit consent required for this paid connectivity probe")
                    try:
                        key=os.getenv("SC04_DEEPSEEK_API_KEY","").strip()
                        if not key:
                            from backend.model_vault import load_key
                            key=load_key(db)
                    except Exception as exc:
                        safe=str(exc) if isinstance(exc,ValueError) else type(exc).__name__+": credential lookup failed"
                        payload=result({"ok":False,"error":safe,"provider_calls":0},error=True)
                    else:
                        if not key:
                            payload=result({"ok":False,"error":"No DeepSeek credential is configured in the environment or encrypted vault.","provider_calls":0},error=True)
                        elif not reserve_session(db,calls=1,tokens=256):
                            payload=result({"ok":False,"error":"Daily model-call or token reservation limit reached; no provider request was sent.","provider_calls":0,"budget":budget_status(db)},error=True)
                        else:
                            try:
                                response,usage=request_json(
                                    key,"deepseek-flash",
                                    "你正在执行一个最小 API 连通性测试。请只返回有效 JSON。",
                                    {"sc05_stage":"connection_probe",
                                     "instruction":"Return exactly one JSON object with ok set to true.",
                                     "required_json_shape":{"ok":True}},
                                    max_tokens=96,
                                )
                                record_usage_session(db,usage)
                                ok=response.get("ok") is True
                                add_audit(db,"sc05.model_connection_probe",owner.id,
                                          "deepseek-flash","success="+str(ok))
                                db.commit()
                                payload=result({"ok":ok,"model":"deepseek-flash",
                                    "usage":usage,"provider_calls":1,
                                    "response_valid":isinstance(response,dict),
                                    "budget":budget_status(db)},
                                    error=not ok)
                            except ModelCallError as exc:
                                add_audit(db,"sc05.model_connection_probe",owner.id,
                                          "deepseek-flash","failure="+str(exc)[:180])
                                db.commit()
                                payload=result({"ok":False,"model":"deepseek-flash",
                                    "error":str(exc),"provider_calls":1,
                                    "budget":budget_status(db)},error=True)
                            except Exception as exc:
                                safe=type(exc).__name__+": connectivity probe failed"
                                add_audit(db,"sc05.model_connection_probe",owner.id,
                                          "deepseek-flash","failure="+safe)
                                db.commit()
                                payload=result({"ok":False,"model":"deepseek-flash",
                                    "error":safe,"provider_calls":1,
                                    "budget":budget_status(db)},error=True)
                elif name=="create_ab_pair":
                    if RUN not in scopes:
                        payload=step_up_result()
                        return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                            headers={"Cache-Control":"no-store"})
                    if arguments.get("confirm_create") is not True:
                        raise HTTPException(422,"Explicit confirmation required to create an A/B run pair")
                    case_id=arguments.get("case_id","")
                    if not re.fullmatch(r"sc05case_[a-f0-9]{20,32}",case_id):
                        raise HTTPException(400,"Invalid SC05 case ID")
                    source_paper=db.get(SC05Case,case_id)
                    if source_paper is None or source_paper.member_id!=owner.id:
                        raise HTTPException(404,"Paper case not found")
                    fresh_copy=arguments.get("fresh_copy") is True
                    paper=source_paper
                    if fresh_copy:
                        # Preserve the exact already-uploaded PDF-derived page
                        # snapshot and original PDF SHA, but clear the shared
                        # facts snapshot so the new baseline re-runs extraction.
                        paper=SC05Case(
                            id="sc05case_"+uuid.uuid4().hex[:28],
                            member_id=owner.id,title=source_paper.title,
                            pages_json=source_paper.pages_json,
                            source_sha=source_paper.source_sha,
                            source_type=source_paper.source_type,
                            shared_evidence_json=None,
                        )
                        db.add(paper)
                        db.flush()
                        add_audit(db,"sc05.case_cloned_for_fresh_pipeline",
                                  owner.id,paper.id,
                                  "source_case="+source_paper.id+
                                  ";source_sha="+paper.source_sha[:16])
                    pair_id="sc05pair_"+uuid.uuid4().hex[:28]
                    created=[]
                    for variant in ("science_gate_off","science_gate_on"):
                        item=SC05Run(
                            id="sc05run_"+uuid.uuid4().hex[:28],
                            member_id=owner.id,case_id=paper.id,pair_id=pair_id,
                            variant=variant,pipeline_sha=pipeline_sha(),
                        )
                        db.add(item)
                        created.append(item)
                    add_audit(db,"sc05.mcp_ab_pair_created",owner.id,pair_id,
                              "source_case="+source_paper.id+
                              ";case="+paper.id+
                              ";source_sha="+paper.source_sha[:16]+
                              ";fresh_copy="+str(fresh_copy)+
                              ";model_calls=0")
                    db.commit()
                    for item in created:
                        db.refresh(item)
                    payload=result({
                        "pair_id":pair_id,
                        "source_case":case_view(source_paper),
                        "case":case_view(paper),
                        "fresh_copy":fresh_copy,
                        "runs":[run_view(item) for item in created],
                        "model_calls":0,
                        "message":"A/B pair created as prepared records. No DeepSeek calls or model spending occurred. The gate-off baseline must run first and freeze the evidence snapshot before gate-on can start."
                    })
                elif name=="prepare_experiment":
                    payload=result(preflight(db,owner,arguments.get("run_id","")))
                elif name=="get_experiment_status":
                    row=own_run(db,owner,arguments.get("run_id",""))
                    devstudio_id=register_devstudio(db,owner,row)
                    checkpoints=load(row.checkpoints_json,[])
                    checkpoint_summary=[]
                    for item in checkpoints:
                        response=item.get("response",{}) if isinstance(item,dict) else {}
                        diagnosis=response.get("diagnoses",[]) if isinstance(response,dict) else []
                        raw_classes=sorted({str(d.get("issue_class")) for d in diagnosis
                                             if isinstance(d,dict) and d.get("issue_class") is not None})
                        routes=response.get("routes") if isinstance(response,dict) else None
                        checkpoint_summary.append({
                            "stage":item.get("stage"),
                            "model":item.get("model"),
                            "input_tokens":(item.get("usage") or {}).get("input_tokens",0),
                            "output_tokens":(item.get("usage") or {}).get("output_tokens",0),
                            "diagnosis_issue_classes":raw_classes,
                            "response_keys":sorted(response.keys()) if isinstance(response,dict) else [],
                            "routes_type":type(routes).__name__ if routes is not None else "missing",
                            "routes_count":len(routes) if isinstance(routes,list) else None,
                        })
                    payload=result({"run":run_view(row),"saved_checkpoints":len(checkpoints),
                                    "checkpoint_summary":checkpoint_summary,
                                    "devstudio_experiment_id":devstudio_id})
                elif name=="get_experiment_result":
                    row=own_run(db,owner,arguments.get("run_id",""))
                    paper=db.get(SC05Case,row.case_id)
                    data={"run":run_view(row,include_report=True),
                          "source_sha256":paper.source_sha,
                          "saved_checkpoints":len(load(row.checkpoints_json,[])),
                          "quality":load(row.result_json,{}).get("quality",{}) if row.status=="completed" else None}
                    if "report_md" in data["run"]:
                        data["run"]["report_md"]=data["run"]["report_md"][:50000]
                    payload=result(data)
                elif name=="prepare_ab_pair":
                    payload=result(pair_preflight(db,owner,arguments.get("pair_id","")))
                elif name=="get_ab_pair_status":
                    state=pair_preflight(db,owner,arguments.get("pair_id",""))
                    sync_round_from_pair(db,owner,arguments.get("pair_id",""))
                    db.commit()
                    payload=result(state)
                elif name=="start_ab_pair":
                    if RUN not in scopes:
                        payload=step_up_result()
                        return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                            headers={"Cache-Control":"no-store"})
                    pair_id=arguments.get("pair_id","")
                    by,paper=pair_rows(db,owner,pair_id)
                    state=pair_preflight(db,owner,pair_id)
                    if not state["can_start_next"]:
                        raise HTTPException(409,"A/B pair cannot start the next arm: "+state["reason"])
                    target=by["science_gate_off"] if state["next_action"]=="start_baseline" else by["science_gate_on"]
                    started=_start_mcp_run(app,db,owner,target,background,paid_enabled,
                                           arguments.get("confirm_paid") is True)
                    sync_round_from_pair(db,owner,pair_id)
                    db.commit()
                    payload=result({"pair_id":pair_id,"started_arm":target.variant,
                                    "run":started["run"],"next_action":"wait_for_completion",
                                    "message":"Only the next sequential arm was queued. Re-check pair status after completion."})
                elif name=="get_ab_pair_result":
                    pair_id=arguments.get("pair_id","")
                    by,paper=pair_rows(db,owner,pair_id)
                    if any(x.status!="completed" for x in by.values()):
                        raise HTTPException(409,"Both A/B arms must complete before blind review")
                    ordered=blind_order(list(by.values()),pair_id)
                    payload=result({"pair_id":pair_id,"ready":True,"source_sha256":paper.source_sha,
                        "reports":[{"label":chr(65+i),"report_md":row.report_md[:50000],
                                    "quality":load(row.result_json,{}).get("quality",{}),
                                    "model_calls":row.calls,"input_tokens":row.input_tokens,
                                    "output_tokens":row.output_tokens}
                                   for i,row in enumerate(ordered)],
                        "note":"A/B labels are anonymized. Do not infer the variant from report order; use blind scoring before unblinding."})
                elif name=="record_blind_review":
                    if RUN not in scopes:
                        payload=step_up_result()
                        return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                            headers={"Cache-Control":"no-store"})
                    pair_id=arguments.get("pair_id","")
                    by,paper=pair_rows(db,owner,pair_id)
                    if any(x.status!="completed" for x in by.values()):
                        raise HTTPException(409,"Both reports must complete before scoring")
                    label=arguments.get("label")
                    if label not in ("A","B"):
                        raise HTTPException(422,"Blind label must be A or B")
                    ordered=blind_order(list(by.values()),pair_id)
                    target=ordered[ord(label)-65]
                    if db.scalars(select(SC05Rating).where(
                        SC05Rating.member_id==owner.id,SC05Rating.run_id==target.id
                    ).limit(1)).first():
                        raise HTTPException(409,"This blind report has already been scored")
                    values={}
                    for key in ("accuracy","science_value","narrative","literature","feasibility"):
                        value=arguments.get(key)
                        if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=5:
                            raise HTTPException(422,"All blind scores must be integers from 0 to 5")
                        values[key]=value
                    tags=arguments.get("failure_tags",[])
                    if not isinstance(tags,list) or len(tags)>6 or any(x not in FAILURE_TAGS for x in tags):
                        raise HTTPException(422,"Invalid blind-review failure tags")
                    feedback=str(arguments.get("feedback",""))[:3000]
                    hard_failure=arguments.get("hard_failure",False) is True
                    rating=SC05Rating(
                        id="sc05rating_"+uuid.uuid4().hex[:28],member_id=owner.id,
                        run_id=target.id,accuracy=values["accuracy"],
                        science_value=values["science_value"],narrative=values["narrative"],
                        literature=values["literature"],feasibility=values["feasibility"],
                        hard_failure=hard_failure,feedback=feedback,
                        failure_tags_json=dump(tags))
                    db.add(rating)
                    score=(values["accuracy"]*15+values["science_value"]*30+
                           values["narrative"]*25+values["literature"]*20+
                           values["feasibility"]*10)/5
                    add_audit(db,"sc05.mcp_blind_review",owner.id,target.id,
                              "label="+label+";score="+str(score)+";hard_failure="+str(hard_failure))
                    db.commit()
                    payload=result({"saved":True,"pair_id":pair_id,"label":label,
                                    "score":0 if hard_failure else score,
                                    "variant_revealed":False})
                elif name=="compare_ab_pair":
                    if RUN not in scopes:
                        payload=step_up_result()
                        return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                            headers={"Cache-Control":"no-store"})
                    pair_id=arguments.get("pair_id","")
                    by,paper=pair_rows(db,owner,pair_id)
                    if any(x.status!="completed" for x in by.values()):
                        raise HTTPException(409,"Both A/B arms must complete")
                    ratings={x.run_id:x for x in db.scalars(select(SC05Rating).where(
                        SC05Rating.member_id==owner.id,
                        SC05Rating.run_id.in_([r.id for r in by.values()])
                    )).all()}
                    if set(ratings)!=set(x.id for x in by.values()):
                        raise HTTPException(409,"Both anonymized reports must be blindly scored before unblinding")
                    details=[]
                    for variant,row in by.items():
                        rating=ratings[row.id]
                        score=(rating.accuracy*15+rating.science_value*30+
                               rating.narrative*25+rating.literature*20+
                               rating.feasibility*10)/5
                        details.append({"variant":variant,"run_id":row.id,
                            "blind_score":0 if rating.hard_failure else score,
                            "science_value":rating.science_value,"hard_failure":rating.hard_failure,
                            "failure_tags":load(rating.failure_tags_json,[]),
                            "feedback":rating.feedback,"model_calls":row.calls,
                            "input_tokens":row.input_tokens,"output_tokens":row.output_tokens,
                            "quality":load(row.result_json,{}).get("quality",{})})
                    base=next(x for x in details if x["variant"]=="science_gate_off")
                    gate=next(x for x in details if x["variant"]=="science_gate_on")
                    add_audit(db,"sc05.ab_unblinded",owner.id,pair_id,
                              "score_delta="+str(gate["blind_score"]-base["blind_score"]))
                    db.flush()
                    sync_round_from_pair(db,owner,pair_id)
                    db.commit()
                    payload=result({"pair_id":pair_id,"unblinded":True,"runs":details,
                        "score_delta":gate["blind_score"]-base["blind_score"],
                        "scientific_value_delta":gate["science_value"]-base["science_value"],
                        "note":"Researcher scores are evaluation evidence, not proof of scientific correctness."})
                elif name=="list_experiment_rounds":
                    rounds=db.scalars(select(SC05ExperimentRound).where(
                        SC05ExperimentRound.member_id==owner.id
                    ).order_by(SC05ExperimentRound.created_at.desc()).limit(100)).all()
                    payload=result({"categories":ROUND_CATEGORIES,
                                    "rounds":[round_view(x) for x in rounds]})
                elif name=="record_experiment_round":
                    row=upsert_round(db,owner,arguments)
                    db.commit()
                    payload=result(round_view(row))
                elif name=="start_experiment":
                    if RUN not in scopes:
                        payload=step_up_result()
                        return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                            headers={"Cache-Control":"no-store"})
                    if not paid_enabled:
                        raise HTTPException(503,"Owner delegated paid starts are disabled")
                    if os.getenv("SC05_MCP_ENFORCE_WORKER_READINESS","true").lower() not in ("false","0") and not (
                        worker_flag("SC05_INLINE_WORKER_ENABLED")
                        and worker_flag("SC05_INLINE_WORKER_LIVE_ENABLED")
                        and os.getenv("SC05_EXECUTION_MODE","").lower()=="worker"
                    ):
                        raise HTTPException(503,"Cloud worker not ready; paid jobs cannot be queued")
                    if arguments.get("confirm_paid") is not True:
                        raise HTTPException(422,"Explicit consent required for this paid call")
                    row=own_run(db,owner,arguments.get("run_id",""))
                    approval_before=db.get(SC05DelegatedAuthorization,row.id)
                    queued_retry=(
                        row.status=="queued" and approval_before is not None
                        and approval_before.status=="needs_review"
                    )
                    previous_status=row.status
                    check=preflight(db,owner,row.id)
                    if not check["safe_to_submit"]:
                        raise HTTPException(409,"Run not safe to start; inspect checkpoint/preflight")
                    if budget_status(db)["used"]["model_calls"]>=budget_status(db)["limits"]["model_calls_per_day"]:
                        raise HTTPException(409,"Daily model budget exhausted")

                    if queued_retry:
                        # A previous start committed the SC05 queue before its
                        # delegated authorization was re-approved. Revalidate
                        # the exact cached checkpoints, repin the verified code,
                        # then re-arm this same authorization row; never create
                        # a second grant or replay an already-paid stage.
                        previous_sha=row.pipeline_sha
                        row.pipeline_sha=pipeline_sha()
                        row.updated_at=now()
                        approval_before.status="approved"
                        approval_before.granted_at=now()
                        approval_before.processed_at=None
                        add_audit(db,"sc05.mcp_paid_resume",owner.id,row.id,
                                  "Re-approved needs_review authorization after zero-paid checkpoint validation; old_sha="+
                                  previous_sha[:16]+";new_sha="+row.pipeline_sha[:16])
                        db.commit()
                        started=run_view(row)
                    else:
                        # Reuse the EXACT existing SC05 Owner endpoint; no second
                        # implementation of checkpoint or cost authorization rules.
                        from fastapi.routing import iter_route_contexts
                        endpoint=next((ctx.endpoint for ctx in iter_route_contexts(app.routes)
                          if ctx.path=="/api/personal-research/me/sc05/runs/{run_id}/start"
                          and "POST" in (ctx.methods or set())),None)
                        if endpoint is None:
                            raise HTTPException(503,"SC05 start route unavailable")
                        started=endpoint(row.id,StartRequest(acknowledge_external_model=True),
                                         background,db,owner)
                        db.refresh(row)
                        approval=db.get(SC05DelegatedAuthorization,row.id)
                        if approval:
                            if previous_status=="failed" and approval.status=="needs_review":
                                approval.status="approved"
                                approval.granted_at=now()
                                approval.processed_at=None
                                audit_action="sc05.mcp_paid_resume"
                                audit_detail="Re-approved needs_review authorization after zero-paid checkpoint validation"
                            else:
                                raise HTTPException(409,"Delegated authorization already exists")
                        else:
                            db.add(SC05DelegatedAuthorization(
                                run_id=row.id,member_id=owner.id,status="approved"
                            ))
                            audit_action="sc05.mcp_paid_start"
                            audit_detail="OAuth run scope + per-call paid consent"
                        add_audit(db,audit_action,owner.id,row.id,audit_detail)
                        db.commit()
                    devstudio_id=register_devstudio(db,owner,row)
                    payload=result({"run":started,"devstudio_experiment_id":devstudio_id,
                                    "message":"Experiment enqueued; use get_experiment_status to follow progress."})
                else:
                    raise HTTPException(404,"Unknown MCP tool")
            else:
                return JSONResponse({"jsonrpc":"2.0","id":identifier,
                    "error":{"code":-32601,"message":"Unknown method"}},
                    headers={"Cache-Control":"no-store"})
            return JSONResponse({"jsonrpc":"2.0","id":identifier,"result":payload},
                                headers={"Cache-Control":"no-store"})
        except HTTPException as exc:
            return JSONResponse({"jsonrpc":"2.0","id":identifier,
                "result":result({"error":str(exc.detail),"http_status":exc.status_code},error=True)},
                headers={"Cache-Control":"no-store"})

    app.include_router(router)
