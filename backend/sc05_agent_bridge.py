"""Owner-delegated, OAuth-protected SC05 MCP gateway.

No model calls happen during OAuth, discovery, listing or preflight.
MCP writes reuse the EXISTING SC05 Owner start handler, which enforces
checkpoint compatibility, frozen A/B evidence and provider budgets.
"""
from __future__ import annotations

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
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.team import TeamMember, add_audit, login as member_login, revoke_session
from backend.sc05_eval_api import (SC05Case, SC05Run, StartRequest, run_view, case_view, load, dump, check_fact_type_resume, check_literature_diagnosis_resume, EvidenceError)
from backend.sc05_paper_only import run_paper
from backend.research_budget import status as budget_status
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
    data = result({"error":"Owner must authorize experiments:run to use this paid action"},
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
    {"name":"prepare_experiment","description":"Read-only preflight for an existing SC05 run: verify source hashes, frozen evidence, checkpoint counts, status, and budget before spending anything.",
     "inputSchema":{"type":"object","properties":{"run_id":{"type":"string","description":"Existing sc05run_ ID"}},
                    "required":["run_id"],"additionalProperties":False}},
    {"name":"start_experiment","description":"Paid action: start or resume ONE existing Owner SC05 run using existing API validation and daily budget controls. Never run without explicit paid consent; never restart completed runs. Prefer prepare_experiment first.",
     "inputSchema":{"type":"object","properties":{
         "run_id":{"type":"string","description":"Existing SC05 run ID"},
         "confirm_paid":{"type":"boolean","description":"Set true only after user explicitly authorized actual DeepSeek model spending in this conversation"}},
         "required":["run_id","confirm_paid"],"additionalProperties":False}},
    {"name":"get_executor_status","description":"Check zero-cost Render worker probe, paid executor enablement, queued dispatches and archive switch; no model calls.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"get_experiment_status","description":"Check an existing Owner run without making model calls. Return stage, checkpoint count, tokens and errors; also sync Development Studio run status.",
     "inputSchema":{"type":"object","properties":{"run_id":{"type":"string"}},"required":["run_id"],"additionalProperties":False}},
    {"name":"get_experiment_result","description":"Read an existing completed Owner SC05 report (limited length), quality indicators and source/pipeline hashes. Read-only. No synthetic scientific scoring.",
     "inputSchema":{"type":"object","properties":{"run_id":{"type":"string"}},"required":["run_id"],"additionalProperties":False}}
]


# Publish per-tool OAuth requirements so ChatGPT can request the
# experiments:run grant and perform step-up after an earlier read-only link.
for _tool in TOOLS:
    _write = _tool["name"] == "start_experiment"
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


def list_owned(db,owner):
    cases=db.scalars(select(SC05Case).where(SC05Case.member_id==owner.id)
                     .order_by(SC05Case.created_at.desc()).limit(30)).all()
    runs=db.scalars(select(SC05Run).where(SC05Run.member_id==owner.id)
                    .order_by(SC05Run.created_at.desc()).limit(70)).all()
    return {"cases":[case_view(x) for x in cases],
            "runs":[run_view(x) for x in runs],"budget":budget_status(db)}



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
    if row.status=="failed" and row.error=="Missing/invalid search query":
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
    safe_status=(row.status=="prepared" or (row.status=="failed" and repair_ready))
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
                    payload=result(worker_status(get_factory()))
                elif name=="prepare_experiment":
                    payload=result(preflight(db,owner,arguments.get("run_id","")))
                elif name=="get_experiment_status":
                    row=own_run(db,owner,arguments.get("run_id",""))
                    devstudio_id=register_devstudio(db,owner,row)
                    payload=result({"run":run_view(row),"saved_checkpoints":len(load(row.checkpoints_json,[])),
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
                    check=preflight(db,owner,row.id)
                    if not check["safe_to_submit"]:
                        raise HTTPException(409,"Run not safe to start; inspect checkpoint/preflight")
                    if budget_status(db)["used"]["model_calls"]>=budget_status(db)["limits"]["model_calls_per_day"]:
                        raise HTTPException(409,"Daily model budget exhausted")
                    # Reuse the EXACT existing SC05 Owner endpoint; no second
                    # implementation of checkpoint or cost authorization rules.
                    # FastAPI >=0.137 retains included routers lazily.
                    # Its supported iterator resolves the effective prefixed
                    # path (app.routes alone contains _IncludedRouter nodes).
                    from fastapi.routing import iter_route_contexts
                    endpoint=next((ctx.endpoint for ctx in iter_route_contexts(app.routes)
                      if ctx.path=="/api/personal-research/me/sc05/runs/{run_id}/start"
                      and "POST" in (ctx.methods or set())),None)
                    if endpoint is None:
                        raise HTTPException(503,"SC05 start route unavailable")
                    started=endpoint(row.id,StartRequest(acknowledge_external_model=True),
                                     background,db,owner)
                    db.refresh(row)
                    # This approved dispatch is independent of the historic
                    # SC05 queue. The free Render worker consumes ONLY rows
                    # with this exact per-run Owner authorization.
                    approval=db.get(SC05DelegatedAuthorization,row.id)
                    if approval:
                        raise HTTPException(409,"Delegated authorization already exists")
                    db.add(SC05DelegatedAuthorization(
                        run_id=row.id,member_id=owner.id,status="approved"
                    ))
                    add_audit(db,"sc05.mcp_paid_start",owner.id,row.id,
                              "OAuth run scope + per-call paid consent")
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
