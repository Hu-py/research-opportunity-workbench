"""Authenticated FastAPI service for the Research Opportunity Workbench."""
from __future__ import annotations

import hmac
import json
import os
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text as sql_text
from sqlalchemy.orm import Session

from research_workbench.core import (
    Paper, Idea, Evidence, Event, Profile, Base,
    get_profile, set_profile, feedback, weekly_report, validate_profile,
    session_factory,
)
from backend.tasks import ResearchTask, enqueue, as_dict
from backend.worker import run_task
from backend.bootstrap import bootstrap_admin_from_env
from backend.discovery_links import list_links, review_link
from backend.discovery import (
    SearchStrategy, DiscoveryRun, PaperCandidate, strategies,
    save_strategy, create_run, candidates, runs as discovery_runs,
    review_candidate,
)
from backend.discovery_runner import execute_discovery
from backend.model_vault import ModelCredential, status as model_status, save as save_model_config, remove_key as remove_model_key
from backend.profile_intelligence import (
    ResearchProfileDraft, ResearchProfileDraftRevision, ProfileSynthesisRun,
    initialize_database_draft,
    bootstrap_db_review,
    list_studio as list_research_portraits,
    start_generation as start_profile_synthesis,
    execute_generation as execute_profile_synthesis,
    update_draft as update_research_profile_draft,
    apply_draft as apply_research_profile_draft,
    discard_draft as discard_research_profile_draft,
)
from backend.ai_lab import (
    AIAnalysisRun, PaperUnderstanding, AIOpportunity,
    create_run as create_ai_run, create_scheduled_run as create_ai_scheduled,
    execute as execute_ai_analysis, list_runs as list_ai_runs,
    list_cards as list_ai_cards, review_card as review_ai_card,
    resume as resume_ai_run,
)
from backend.cusp import (
    CuspDataset, CuspDatasetRevision, CuspImportRun,
    import_records as import_cusp_records, update_one as update_cusp_one,
    as_dict as cusp_dict, summary as cusp_summary,
    parse_xlsx as cusp_parse_xlsx, bootstrap_from_env as cusp_bootstrap,
    propose_from_existing as cusp_proposals,
)
import base64
import binascii
from backend.repository import (
    TeamAchievement, ResearchDataAsset, ResearchRefreshRun,
    seed_verified, list_outputs, update_output_status, public_asset,
    import_directory_listing, inferred_opportunities, create_refresh,
    refresh_public_works,
)
from backend.team import (
    TeamMember, TeamProfileRevision, AuditEntry,
    SESSION_SECONDS, login as member_login, resolve_session, revoke_session,
    create_member, public_member, set_member_status, add_audit,
    current_profile_version, save_team_profile,
)

@lru_cache(maxsize=1)
def get_factory():
    # Importing ResearchTask above registers its metadata before create_all.
    return session_factory()

def get_db():
    with get_factory()() as db:
        yield db

def authenticate(request: Request):
    expected=os.getenv("API_BEARER_TOKEN","").strip()
    if not expected:
        if os.getenv("APP_ENV","development").lower() == "production":
            raise HTTPException(status_code=503,detail="API auth is not configured")
        return
    provided=request.headers.get("Authorization","")
    if not hmac.compare_digest(provided,"Bearer "+expected):
        raise HTTPException(status_code=401,detail="Authentication required")

def team_auth_enabled() -> bool:
    return os.getenv("TEAM_AUTH_ENABLED","").strip().lower() in ("true","1","yes")

def inline_worker_enabled() -> bool:
    # Explicit opt-in for short test tasks on a free Render web instance.
    # Production defaults to the separate-worker queue even when no worker exists.
    default = "queue" if os.getenv("APP_ENV", "development").lower()=="production" else "background"
    return os.getenv("WORKER_MODE",default).strip().lower()=="background"

def require_actor(request:Request,db:Session=Depends(get_db)):
    authenticate(request)
    if not team_auth_enabled():
        return None  # Legacy single-user mode, for transition only.
    member=resolve_session(db,request.headers.get("X-Research-Session"))
    if member is None:
        raise HTTPException(status_code=401,detail="Team session required or expired")
    return member

def require_editor(actor:TeamMember|None=Depends(require_actor)):
    if team_auth_enabled() and (actor is None or actor.role not in ("admin","researcher")):
        raise HTTPException(403,"Editor or admin role required")
    return actor

def require_admin(actor:TeamMember|None=Depends(require_actor)):
    if team_auth_enabled() and (actor is None or actor.role!="admin"):
        raise HTTPException(403,"Administrator role required")
    return actor

@asynccontextmanager
async def lifespan(app:FastAPI):
    if os.getenv("APP_ENV","development").lower()=="production" and not os.getenv("API_BEARER_TOKEN"):
        raise RuntimeError("Set API_BEARER_TOKEN before production deployment")
    factory=get_factory()
    bootstrap_admin_from_env(factory)
    with factory() as db:
        imported=seed_verified(db)
        if imported:
            logging.getLogger("uvicorn.error").info(
                "Curated team research imported: %d records",imported
            )
    bootstrap=cusp_bootstrap(factory)
    if bootstrap:
        logging.getLogger("uvicorn.error").info(
            "CUSP metadata bootstrap: %d new, %d updated, %d unchanged",
            bootstrap["new"],bootstrap["updated"],bootstrap["unchanged"]
        )
    # Build the initial portrait from real rows after all database bootstraps.
    # Do NOT use the old chat-based bootstrap; it is invalidated in the DB.
    portrait=initialize_database_draft(factory)
    logging.getLogger("uvicorn.error").info(
        "Database-only portrait ready: created=%s discarded_chat_drafts=%d "
        "verified_outputs=%d registered_assets=%d approved_papers=%d official_lines=%d",
        portrait["new"],portrait["discarded_chat_drafts"],
        portrait["counts"]["achievements_verified"],
        portrait["counts"]["data_assets_total"],
        portrait["counts"]["approved_papers"],
        portrait["counts"]["official_lines"],
    )
    reviewed=bootstrap_db_review(factory)
    if reviewed:
        logging.getLogger("uvicorn.error").info(
            "DB analyst research portrait: imported=%s draft=%s lines=%s",
            reviewed["imported"],reviewed["id"],reviewed.get("lines","existing"),
        )
    with factory() as db:
        db.execute(sql_text("SELECT 1"))
        logging.getLogger("uvicorn.error").info(
            "Research database connection verified: dialect=%s",
            db.get_bind().dialect.name,
        )
        # Explicitly opted-in one-time diagnostic; safe schema only.
        # Never enabled by default or in recurring daily publication tasks.
        if os.getenv("PROFILE_AUDIT_ON_STARTUP","").strip()=="1":
            from backend.profile_audit import emit_log_report
            emit_log_report(db,logging.getLogger("uvicorn.error"))
    logging.getLogger("uvicorn.error").info(
        "OpenAlex API key configured: %s",
        "yes" if os.getenv("OPENALEX_API_KEY","").strip() else "no",
    )
    if inline_worker_enabled():
        logging.getLogger("uvicorn.error").warning(
            "Inline research jobs enabled: not durable across free-instance sleep or restarts"
        )
    yield

app=FastAPI(
    title="Research Opportunity Workbench API",
    description="Paper intelligence, rolling ideas and evidence-traceable agent jobs.",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("APP_ENV")!="production" else None,
    redoc_url=None,
)

class TaskRequest(BaseModel):
    kind:Literal["explore","sync","weekly"]="explore"
    query:str=Field(default="",max_length=2000)

class FeedbackRequest(BaseModel):
    status:Literal["candidate","watch","shortlist","experiment","rejected","archived"]
    note:str=Field(default="",max_length=1500)

class ProfileRequest(BaseModel):
    research_lines:list[dict]
    excluded_terms:list[str]=Field(default_factory=list)
    goals:str=""
    team:dict|None=None
    datasets:list[dict]|None=None
    methods:list[str]|None=None
    expected_version:int|None=None

class AchievementReviewRequest(BaseModel):
    status:Literal["verified","review","rejected"]

class DirectoryImportRequest(BaseModel):
    listing:str=Field(min_length=1,max_length=50000)

class DataAssetPatchRequest(BaseModel):
    description:str|None=Field(default=None,max_length=1600)
    spatial_scale:str|None=Field(default=None,max_length=250)
    time_range:str|None=Field(default=None,max_length=250)
    sensitivity:Literal["public","internal","restricted"]|None=None
    fields:list[str]|None=Field(default=None,max_length=80)

class CuspExcelImportRequest(BaseModel):
    filename:str=Field(default="CUSP数据登记.xlsx",max_length=120)
    file_b64:str=Field(min_length=50,max_length=3_000_000)

class CuspEditRequest(BaseModel):
    category:str|None=None
    format:str|None=None
    coverage:str|None=None
    period:str|None=None
    source:str|None=None
    description:str|None=None
    prior_research:str|None=None
    custodian:str|None=None
    f_drive:Literal["listed","not_listed","unknown"]|None=None
    backup:Literal["confirmed","not_confirmed","unknown"]|None=None
    sensitivity:Literal["public","internal","restricted"]|None=None
    note:str|None=None

class SearchStrategyRequest(BaseModel):
    direct_queries:list[str]=Field(default_factory=list,max_length=3)
    method_queries:list[str]=Field(default_factory=list,max_length=3)
    enabled:bool=False
    lookback_days:int=Field(default=30,ge=7,le=180)
    per_query:int=Field(default=8,ge=1,le=12)
    min_score:int=Field(default=60,ge=0,le=100)

class DiscoveryRunRequest(BaseModel):
    line_id:str|None=Field(default=None,max_length=110)

class RelationReviewRequest(BaseModel):
    status:Literal["confirmed","rejected","suggested"]

class PaperReviewRequest(BaseModel):
    status:Literal["relevant","method","rejected","pending"]
    note:str=Field(default="",max_length=500)

class ProfileSynthesisRequest(BaseModel):
    notes:str=Field(default="",max_length=2000)

class ResearchProfileDraftPatch(BaseModel):
    expected_revision:int=Field(ge=1)
    profile:dict

class ResearchProfileApplyRequest(BaseModel):
    expected_version:int=Field(ge=0)

class ModelConfigRequest(BaseModel):
    key:str|None=Field(default=None,min_length=12,max_length=320)
    fast_model:Literal["deepseek-flash"]|None=None
    reason_model:Literal["deepseek-v4-pro","deepseek-flash"]|None=None
    daily_enabled:bool|None=None

class AIAnalysisRequest(BaseModel):
    line_id:str=Field(min_length=1,max_length=110)

class AIReviewRequest(BaseModel):
    status:Literal["shortlist","rejected","draft"]

class LoginRequest(BaseModel):
    email:str=Field(min_length=3,max_length=255)
    password:str=Field(min_length=1,max_length=256)

class MemberRequest(BaseModel):
    email:str=Field(min_length=3,max_length=255)
    name:str=Field(min_length=2,max_length=140)
    temporary_password:str=Field(min_length=12,max_length=256)
    role:Literal["admin","researcher","viewer"]="researcher"

class MemberUpdateRequest(BaseModel):
    active:bool|None=None
    role:Literal["admin","researcher","viewer"]|None=None

@app.post("/api/auth/login",dependencies=[Depends(authenticate)])
def auth_login(data:LoginRequest,request:Request,db:Session=Depends(get_db)):
    if not team_auth_enabled():raise HTTPException(404,"Team authentication is disabled")
    address=request.client.host if request.client else "unknown"
    result=member_login(db,data.email,data.password,address)
    if result is None:raise HTTPException(401,"Invalid credentials")
    token,member=result
    return {"token":token,"expires_in":SESSION_SECONDS,"member":public_member(member)}

@app.get("/api/auth/me",dependencies=[Depends(authenticate)])
def auth_me(actor:TeamMember|None=Depends(require_actor)):
    if not team_auth_enabled():return {"enabled":False,"member":None}
    return {"enabled":True,"member":public_member(actor)}

@app.post("/api/auth/logout",dependencies=[Depends(authenticate)])
def auth_logout(request:Request,actor:TeamMember|None=Depends(require_actor),
                db:Session=Depends(get_db)):
    if team_auth_enabled():
        revoke_session(db,request.headers.get("X-Research-Session",""),actor.id)
    return {"ok":True}

@app.get("/api/team/members",dependencies=[Depends(require_admin)])
def team_members(db:Session=Depends(get_db)):
    if not team_auth_enabled():raise HTTPException(404,"Team member management is disabled")
    rows=db.scalars(select(TeamMember).order_by(TeamMember.created_at.asc())).all()
    return {"items":[public_member(x) for x in rows]}

@app.post("/api/team/members",dependencies=[Depends(require_admin)],status_code=201)
def team_add_member(data:MemberRequest,actor:TeamMember|None=Depends(require_admin),
                    db:Session=Depends(get_db)):
    if not team_auth_enabled():raise HTTPException(404,"Team member management is disabled")
    try:
        m=create_member(db,data.email,data.name,data.temporary_password,data.role,
                        actor_id=actor.id if actor else None)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return public_member(m)

@app.patch("/api/team/members/{member_id}",dependencies=[Depends(require_admin)])
def team_update_member(member_id:str,data:MemberUpdateRequest,
                       actor:TeamMember|None=Depends(require_admin),db:Session=Depends(get_db)):
    if not team_auth_enabled():raise HTTPException(404,"Team member management is disabled")
    m=db.get(TeamMember,member_id)
    if not m:raise HTTPException(404,"Member not found")
    try:set_member_status(db,m,active=data.active,role=data.role,actor_id=actor.id if actor else "")
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return public_member(m)

@app.get("/api/team/audit",dependencies=[Depends(require_admin)])
def team_audit(db:Session=Depends(get_db)):
    if not team_auth_enabled():raise HTTPException(404,"Team audit is disabled")
    rows=db.scalars(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(150)).all()
    return {"items":[{"id":x.id,"actor_id":x.actor_id,"action":x.action,"target":x.target,
                       "note":x.note,"created_at":x.created_at.isoformat() if x.created_at else None}
                      for x in rows]}

@app.get("/api/team/profile-history",dependencies=[Depends(require_actor)])
def team_profile_history(db:Session=Depends(get_db)):
    if not team_auth_enabled():raise HTTPException(404,"Team profile history is disabled")
    rows=db.scalars(select(TeamProfileRevision).order_by(TeamProfileRevision.version.desc()).limit(50)).all()
    return {"items":[{"version":r.version,"actor_id":r.actor_id,
                       "created_at":r.created_at.isoformat() if r.created_at else None} for r in rows]}


@app.get("/api/team-repository",dependencies=[Depends(require_actor)])
def achievement_catalog(status_filter:str|None=None,kind:str|None=None,
                        db:Session=Depends(get_db)):
    items=list_outputs(db,status_filter,kind,limit=300)
    return {"items":items,"count":len(items),
            "source":"同济大学师资页面、期刊出版页与 OpenAlex ORCID",
            "orcid":"0000-0002-7261-4234",
            "review_note":"自动发现的论文仅进入待核验区；人工通过后才成为正式团队成果。"}

@app.patch("/api/team-repository/{output_id}",dependencies=[Depends(require_actor)])
def review_achievement(output_id:str,data:AchievementReviewRequest,
                       db:Session=Depends(get_db),
                       actor:TeamMember|None=Depends(require_admin)):
    try:return update_output_status(db,output_id,data.status,actor.id if actor else "")
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc

@app.get("/api/team-repository/refresh-runs",dependencies=[Depends(require_actor)])
def achievement_refresh_runs(db:Session=Depends(get_db)):
    rows=db.scalars(select(ResearchRefreshRun).order_by(
        ResearchRefreshRun.created_at.desc()).limit(20)).all()
    return {"items":[{"id":x.id,"source":x.source,"status":x.status,
        "scanned":x.scanned,"inserted":x.inserted,"error":x.error,
        "created_at":x.created_at.isoformat() if x.created_at else None}
        for x in rows]}

@app.post("/api/team-repository/refresh",status_code=202,
          dependencies=[Depends(require_actor)])
def manual_refresh_achievements(background:BackgroundTasks,
             db:Session=Depends(get_db),
             actor:TeamMember|None=Depends(require_admin)):
    run=create_refresh(db,"manual")
    background.add_task(refresh_public_works,get_factory(),run.id)
    add_audit(db,"achievement.refresh",actor.id if actor else None,run.id)
    db.commit()
    return {"id":run.id,"status":"queued"}

@app.post("/api/team-repository/refresh-scheduled",status_code=202,
          dependencies=[Depends(authenticate)])
def scheduled_refresh_achievements(request:Request,background:BackgroundTasks,
                                  db:Session=Depends(get_db)):
    # Service-only endpoint: never rely on browser sessions or public User-Agent.
    expected=os.getenv("ATLAS_SYNC_SECRET","").strip()
    supplied=request.headers.get("X-Atlas-Sync-Secret","")
    if len(expected)<24 or not hmac.compare_digest(supplied,expected):
        raise HTTPException(403,"Scheduled refresh is not authorized")
    run=create_refresh(db,"scheduled")
    background.add_task(refresh_public_works,get_factory(),run.id)
    # Share the existing free Vercel daily cron. Discovery is explicitly
    # opt-in per research line; defaults to OFF and never auto-approves papers.
    discovered=create_run(db,get_profile(db),source="scheduled")
    if discovered:
        background.add_task(execute_discovery,get_factory(),discovered.id)
    # Paid analysis is exclusively opt-in. This path does nothing while
    # the admin's daily_enabled switch is false (initial default).
    ai_run=create_ai_scheduled(db)
    if ai_run:
        background.add_task(execute_ai_analysis,get_factory(),ai_run.id)
    return {"id":run.id,"status":"queued",
            "paper_discovery_id":discovered.id if discovered else None,
            "ai_analysis_id":ai_run.id if ai_run else None}

@app.get("/api/data-assets",dependencies=[Depends(require_actor)])
def data_assets(db:Session=Depends(get_db)):
    rows=db.scalars(select(ResearchDataAsset).order_by(ResearchDataAsset.name)).all()
    return {"items":[public_asset(x) for x in rows],
            "note":"仅保存目录、格式和手工填写的数据字典，不存储原始研究数据文件。"}

@app.post("/api/data-assets/import-directory",dependencies=[Depends(require_actor)])
def import_data_directory(data:DirectoryImportRequest,
             db:Session=Depends(get_db),
             actor:TeamMember|None=Depends(require_admin)):
    try:return import_directory_listing(db,data.listing,actor.id if actor else "")
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.patch("/api/data-assets/{asset_id}",dependencies=[Depends(require_actor)])
def update_data_asset(asset_id:str,data:DataAssetPatchRequest,
            db:Session=Depends(get_db),
            actor:TeamMember|None=Depends(require_admin)):
    item=db.get(ResearchDataAsset,asset_id)
    if not item:raise HTTPException(404,"Data asset not found")
    values=data.model_dump(exclude_unset=True)
    if "fields" in values:
        fields=values.pop("fields")
        if fields is not None:
            item.fields_json=json.dumps([x.strip()[:160] for x in fields],ensure_ascii=False)
    for key,value in values.items():
        if value is not None:setattr(item,key,value)
    add_audit(db,"data_assets.updated",actor.id if actor else None,item.id)
    db.commit()
    return public_asset(item)

@app.get("/api/data-assets/opportunities",dependencies=[Depends(require_actor)])
def data_asset_opportunities(db:Session=Depends(get_db)):
    return {"items":inferred_opportunities(db),
        "disclaimer":"仅基于目录和格式的研究假设；未查看数据内容、质量、权限和真实可用性。"}

@app.get("/api/opportunity-engine",dependencies=[Depends(require_actor)])
def opportunity_engine(db:Session=Depends(get_db)):
    profile=get_profile(db)
    return {
        "profile_ready":bool(profile),
        "openalex_key_configured":bool(os.getenv("OPENALEX_API_KEY","").strip()),
        "strategies":strategies(db,profile),
        "relations":list_links(db,profile),
        "candidates":candidates(db,limit=160),
        "runs":discovery_runs(db),
        "note":"论文相关性是规则排序，不表示学术创新性；团队数据仅使用登记元数据，未读取任何原始文件。",
    }

@app.patch("/api/opportunity-engine/relations/{relation_id}",
           dependencies=[Depends(require_actor)])
def review_research_relation(relation_id:str,data:RelationReviewRequest,
        db:Session=Depends(get_db),actor:TeamMember|None=Depends(require_admin)):
    try:
        return review_link(db,get_profile(db),relation_id,data.status,
                           actor.id if actor else "")
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc

@app.put("/api/opportunity-engine/strategies/{line_id}",
         dependencies=[Depends(require_actor)])
def update_search_strategy(line_id:str,data:SearchStrategyRequest,
        db:Session=Depends(get_db),actor:TeamMember|None=Depends(require_admin)):
    try:
        return save_strategy(db,get_profile(db),line_id,data.model_dump(),
                             actor.id if actor else "")
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.post("/api/opportunity-engine/run",status_code=202,
          dependencies=[Depends(require_actor)])
def start_discovery(data:DiscoveryRunRequest,background:BackgroundTasks,
         db:Session=Depends(get_db),actor:TeamMember|None=Depends(require_editor)):
    if not get_profile(db):raise HTTPException(409,"请先保存团队研究画像")
    try:
        run=create_run(db,get_profile(db),source="manual",line_id=data.line_id)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    if not run:raise HTTPException(409,"没有可用的研究主线")
    add_audit(db,"paper_discovery.started",actor.id if actor else None,run.id)
    db.commit()
    background.add_task(execute_discovery,get_factory(),run.id)
    return {"id":run.id,"status":run.status,
            "note":"任务在 Render 免费实例上运行；休眠或重启可能使任务中断。"}

@app.patch("/api/opportunity-engine/candidates/{candidate_id}",
           dependencies=[Depends(require_actor)])
def review_discovered_paper(candidate_id:str,data:PaperReviewRequest,
        db:Session=Depends(get_db),actor:TeamMember|None=Depends(require_editor)):
    try:
        return review_candidate(db,candidate_id,data.status,data.note,
                                actor.id if actor else "")
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc

@app.get("/api/profile-intelligence",dependencies=[Depends(require_actor)])
def research_profile_studio(db:Session=Depends(get_db)):
    return list_research_portraits(db)

@app.post("/api/profile-intelligence/generate",status_code=202,
          dependencies=[Depends(require_actor)])
def generate_research_profile(data:ProfileSynthesisRequest,
                              background:BackgroundTasks,
                              db:Session=Depends(get_db),
                              actor:TeamMember|None=Depends(require_admin)):
    if not team_auth_enabled():
        raise HTTPException(403,"Admin team access required for model-based team profile changes")
    try:
        run=start_profile_synthesis(db,data.notes,actor.id if actor else "")
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    background.add_task(execute_profile_synthesis,get_factory(),run.id)
    return {"id":run.id,"status":run.status,
            "note":"从非受限资产元信息、已有研究画像与审核成果提取新画像草稿；不会直接改写正式团队画像。"}

@app.put("/api/profile-intelligence/drafts/{draft_id}",
         dependencies=[Depends(require_actor)])
def edit_research_profile_draft(draft_id:str,
             data:ResearchProfileDraftPatch,
             db:Session=Depends(get_db),
             actor:TeamMember|None=Depends(require_admin)):
    try:
        return update_research_profile_draft(db,draft_id,
            data.profile,data.expected_revision,actor.id if actor else "")
    except ValueError as exc:raise HTTPException(409 if "刷新" in str(exc) else 422,str(exc)) from exc

@app.post("/api/profile-intelligence/drafts/{draft_id}/apply",
          dependencies=[Depends(require_actor)])
def publish_research_profile_draft(draft_id:str,
             data:ResearchProfileApplyRequest,
             db:Session=Depends(get_db),
             actor:TeamMember|None=Depends(require_admin)):
    if not team_auth_enabled():raise HTTPException(403,"Admin team access required")
    try:
        return apply_research_profile_draft(db,draft_id,data.expected_version,
                                           actor.id if actor else "")
    except ValueError as exc:
        raise HTTPException(409 if "变化" in str(exc) else 422,str(exc)) from exc

@app.post("/api/profile-intelligence/drafts/{draft_id}/discard",
          dependencies=[Depends(require_actor)])
def reject_research_profile_draft(draft_id:str,
             db:Session=Depends(get_db),
             actor:TeamMember|None=Depends(require_admin)):
    try:return discard_research_profile_draft(db,draft_id,actor.id if actor else "")
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.get("/api/ai-lab",dependencies=[Depends(require_actor)])
def ai_lab_overview(db:Session=Depends(get_db)):
    return {"config":model_status(db),"runs":list_ai_runs(db),
            "cards":list_ai_cards(db),
            "note":"模型仅分析已审核论文的标题与摘要以及非受限数据属性。草稿不代表已验证的创新性。"}

@app.put("/api/ai-lab/config",dependencies=[Depends(require_actor)])
def ai_lab_model_save(data:ModelConfigRequest,db:Session=Depends(get_db),
                      actor:TeamMember|None=Depends(require_admin)):
    if not team_auth_enabled():
        raise HTTPException(403,"Only an authenticated team administrator may save API keys")
    try:
        return save_model_config(db,actor.id if actor else "",key=data.key,
            fast_model=data.fast_model,reason_model=data.reason_model,
            daily_enabled=data.daily_enabled)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.delete("/api/ai-lab/key",dependencies=[Depends(require_actor)])
def ai_lab_model_remove(db:Session=Depends(get_db),
                        actor:TeamMember|None=Depends(require_admin)):
    if not team_auth_enabled():
        raise HTTPException(403,"Only an authenticated team administrator may delete API keys")
    return remove_model_key(db,actor.id if actor else "")

@app.post("/api/ai-lab/run",status_code=202,dependencies=[Depends(require_actor)])
def ai_lab_start(data:AIAnalysisRequest,background:BackgroundTasks,
                 db:Session=Depends(get_db),
                 actor:TeamMember|None=Depends(require_editor)):
    try:
        task=create_ai_run(db,data.line_id,source="manual",
                           actor_id=actor.id if actor else None)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    background.add_task(execute_ai_analysis,get_factory(),task.id)
    return {"id":task.id,"status":"queued",
            "note":"逐阶段保存，失败后可恢复；只有实际模型调用会产生 DeepSeek 费用。"}

@app.post("/api/ai-lab/runs/{run_id}/resume",status_code=202,
          dependencies=[Depends(require_actor)])
def ai_lab_resume(run_id:str,background:BackgroundTasks,
                  db:Session=Depends(get_db),
                  actor:TeamMember|None=Depends(require_editor)):
    try:
        result=resume_ai_run(db,run_id)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    add_audit(db,"ai_analysis.resumed",actor.id if actor else None,run_id)
    db.commit()
    background.add_task(execute_ai_analysis,get_factory(),run_id)
    return result

@app.patch("/api/ai-lab/cards/{card_id}",dependencies=[Depends(require_actor)])
def ai_lab_review(card_id:str,data:AIReviewRequest,
                  db:Session=Depends(get_db),
                  actor:TeamMember|None=Depends(require_editor)):
    try:return review_ai_card(db,card_id,data.status,actor.id if actor else "")
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc

@app.get("/api/cusp/summary",dependencies=[Depends(require_actor)])
def cusp_summary_api(db:Session=Depends(get_db)):
    return cusp_summary(db)

@app.get("/api/cusp/datasets",dependencies=[Depends(require_actor)])
def cusp_datasets_api(search:str=Query(default="",max_length=120),
             category:str=Query(default="",max_length=80),
             db:Session=Depends(get_db),
             actor:TeamMember|None=Depends(require_actor)):
    rows=db.scalars(select(CuspDataset).order_by(CuspDataset.category,
                    CuspDataset.name)).all()
    if category:rows=[r for r in rows if r.category==category]
    if search:
        q=search.casefold()
        rows=[r for r in rows if q in (r.name+" "+r.category+" "+
                r.description+" "+r.prior_research+" "+r.coverage).casefold()]
    redact=bool(actor is not None and actor.role=="viewer")
    return {"items":[cusp_dict(r,redact=redact) for r in rows[:1000]],
            "total":len(rows),"source_note":"仅登记表元数据，未存储原始研究样本或数据文件"}

@app.get("/api/cusp/import-runs",dependencies=[Depends(require_actor)])
def cusp_import_history(db:Session=Depends(get_db)):
    runs=db.scalars(select(CuspImportRun).order_by(
        CuspImportRun.created_at.desc()).limit(20)).all()
    return {"items":[{"id":x.id,"origin":x.origin,"new":x.imported,
       "updated":x.updated,"unchanged":x.unchanged,
       "created_at":x.created_at.isoformat() if x.created_at else None}
       for x in runs]}

@app.get("/api/cusp/datasets/{dataset_id}/history",dependencies=[Depends(require_actor)])
def cusp_dataset_history(dataset_id:str,db:Session=Depends(get_db),
                         actor:TeamMember|None=Depends(require_actor)):
    rows=db.scalars(select(CuspDatasetRevision).where(
        CuspDatasetRevision.dataset_id==dataset_id
    ).order_by(CuspDatasetRevision.revision.desc()).limit(30)).all()
    return {"items":[{"revision":x.revision,"origin":x.origin,
       "created_at":x.recorded_at.isoformat() if x.recorded_at else None,
       "snapshot":({k:v for k,v in json.loads(x.snapshot_json).items()
                    if k not in ("description","custodian","source","note")}
                   if actor is not None and actor.role=="viewer"
                   and db.get(CuspDataset,dataset_id)
                   and db.get(CuspDataset,dataset_id).sensitivity=="restricted"
                   else json.loads(x.snapshot_json))
       } for x in rows]}

@app.post("/api/cusp/import-xlsx",dependencies=[Depends(require_actor)])
def cusp_import_xlsx(data:CuspExcelImportRequest,db:Session=Depends(get_db),
                     actor:TeamMember|None=Depends(require_admin)):
    try:
        if not data.filename.lower().endswith(".xlsx"):
            raise ValueError("Only .xlsx files are accepted")
        content=base64.b64decode(data.file_b64,validate=True)
        rows=cusp_parse_xlsx(content)
        result=import_cusp_records(db,rows,actor.id if actor else "",
                                   "CUSP数据登记.xlsx · web_import")
        add_audit(db,"cusp.import",actor.id if actor else None,result["import_id"],
                  "new=%d updated=%d unchanged=%d"%
                  (result["new"],result["updated"],result["unchanged"]))
        db.commit()
        return result
    except (ValueError,binascii.Error) as exc:
        db.rollback()
        raise HTTPException(422,str(exc)[:250]) from exc

@app.patch("/api/cusp/datasets/{dataset_id}",dependencies=[Depends(require_actor)])
def cusp_edit_dataset(dataset_id:str,data:CuspEditRequest,db:Session=Depends(get_db),
                      actor:TeamMember|None=Depends(require_admin)):
    fields=data.model_dump(exclude_unset=True,exclude_none=True)
    if any(len(str(v))>2100 for v in fields.values()):
        raise HTTPException(422,"A field is too long")
    try:
        result=update_cusp_one(db,dataset_id,fields,actor.id if actor else "")
        add_audit(db,"cusp.edited",actor.id if actor else None,dataset_id)
        db.commit()
        return result
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.get("/api/cusp/opportunities",dependencies=[Depends(require_actor)])
def cusp_opportunities_api(db:Session=Depends(get_db)):
    return {"items":cusp_proposals(db),
            "note":"规则推断的研究问题，不是 LLM 验证的创新性或数据可行性结论"}

@app.get("/api/health")
def health():
    return {"ok":True,"service":"research-workbench","version":"0.3.0"}

@app.get("/api/overview",dependencies=[Depends(require_actor)])
def overview(db:Session=Depends(get_db)):
    return {"cusp_datasets":db.scalar(select(func.count()).select_from(CuspDataset)) or 0,
            "extra_data_assets":db.scalar(select(func.count()).select_from(ResearchDataAsset)) or 0,
            "papers":db.scalar(select(func.count()).select_from(Paper)) or 0,
            "ideas":db.scalar(select(func.count()).select_from(Idea)) or 0,
            "revisions":db.scalar(select(func.count()).select_from(Event)) or 0,
            "research_lines":len((get_profile(db) or {}).get("research_lines",[])),
            "recent_ideas":[idea_dict(i,db) for i in db.scalars(
                select(Idea).order_by(Idea.updated_at.desc()).limit(5)).all()]}

def paper_dict(p:Paper):
    return {"id":p.id,"title":p.title,"abstract":p.abstract,"doi":p.doi,
            "url":p.url,"published":p.published,"venue":p.venue,
            "line_ids":json.loads(p.line_ids or "[]")}

def idea_dict(i:Idea,db:Session):
    ids=db.scalars(select(Evidence.paper_id).where(Evidence.idea_id==i.id).limit(12)).all()
    return {"id":i.id,"line_id":i.line_id,"method":i.method,"title":i.title,
            "hypothesis":i.hypothesis,"caveat":i.caveat,"status":i.status,
            "score":i.score,"version":i.version,
            "updated_at":i.updated_at.isoformat() if i.updated_at else None,
            "papers":[paper_dict(p) for pid in ids if (p:=db.get(Paper,pid)) is not None]}

@app.get("/api/papers",dependencies=[Depends(require_actor)])
def papers(search:str=Query(default="",max_length=180),
           limit:int=Query(default=100,ge=1,le=300),
           db:Session=Depends(get_db)):
    rows=db.scalars(select(Paper).order_by(Paper.published.desc()).limit(2000)).all()
    term=search.strip().lower()
    if term:rows=[p for p in rows if term in (p.title+" "+p.abstract+" "+p.venue).lower()]
    return {"total":len(rows),"items":[paper_dict(p) for p in rows[:limit]]}

@app.get("/api/ideas",dependencies=[Depends(require_actor)])
def ideas(status_filter:str|None=None,db:Session=Depends(get_db)):
    rows=db.scalars(select(Idea).order_by(Idea.score.desc()).limit(200)).all()
    if status_filter:rows=[i for i in rows if i.status==status_filter]
    return {"items":[idea_dict(i,db) for i in rows]}

@app.get("/api/ideas/{idea_id}/history",dependencies=[Depends(require_actor)])
def idea_history(idea_id:str,db:Session=Depends(get_db)):
    if not db.get(Idea,idea_id):raise HTTPException(404,"Idea not found")
    events=db.scalars(select(Event).where(Event.idea_id==idea_id)
                      .order_by(Event.version.desc())).all()
    return {"items":[{"version":e.version,"action":e.action,"detail":json.loads(e.detail or "{}"),
                      "created_at":e.created_at.isoformat() if e.created_at else None} for e in events]}

@app.post("/api/ideas/{idea_id}/feedback",dependencies=[Depends(require_actor)])
def idea_feedback(idea_id:str,data:FeedbackRequest,db:Session=Depends(get_db),
                  actor:TeamMember|None=Depends(require_editor)):
    try:feedback(db,idea_id,data.status,data.note)
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc
    add_audit(db,"idea.feedback",actor.id if actor else None,idea_id,
              "status="+data.status+"; "+data.note[:200])
    db.commit()
    return idea_dict(db.get(Idea,idea_id),db)

@app.get("/api/profile",dependencies=[Depends(require_actor)])
def profile(db:Session=Depends(get_db)):
    return {"profile":get_profile(db),"version":current_profile_version(db)}

@app.put("/api/profile",dependencies=[Depends(require_actor)])
def profile_update(data:ProfileRequest,db:Session=Depends(get_db),
                   actor:TeamMember|None=Depends(require_admin)):
    payload=data.model_dump(exclude={"expected_version"},exclude_none=True)
    try:
        if team_auth_enabled():
            version=save_team_profile(db,payload,actor.id,data.expected_version)
        else:
            set_profile(db,payload)
            version=current_profile_version(db)
    except ValueError as exc:raise HTTPException(409 if "changed by another" in str(exc) else 422,str(exc)) from exc
    return {"profile":get_profile(db),"version":version}

@app.get("/api/tasks",dependencies=[Depends(require_actor)])
def tasks(db:Session=Depends(get_db)):
    rows=db.scalars(select(ResearchTask).order_by(ResearchTask.created_at.desc()).limit(40)).all()
    return {"items":[as_dict(t) for t in rows]}

@app.post("/api/tasks",status_code=status.HTTP_202_ACCEPTED,dependencies=[Depends(require_actor)])
def tasks_start(data:TaskRequest,background:BackgroundTasks,db:Session=Depends(get_db),
                actor:TeamMember|None=Depends(require_editor)):
    if data.kind=="explore" and len(data.query.strip())<6:
        raise HTTPException(422,"请输入更具体的研究问题（至少 6 个字符）")
    task=enqueue(db,data.kind,data.query)
    add_audit(db,"task.created",actor.id if actor else None,task.id,"kind="+data.kind)
    db.commit()
    # Opt-in fallback for free-host evaluation, NOT a durable worker.
    # An interrupted process may leave a task queued/running. Never claim
    # production-grade reliability without a separate worker.
    if inline_worker_enabled():
        background.add_task(run_task,get_factory(),task.id)
    return as_dict(task)

@app.post("/api/tasks/{task_id}/dispatch",dependencies=[Depends(require_actor)])
def dispatch_queued_task(task_id:str,background:BackgroundTasks,
                         db:Session=Depends(get_db),
                         actor:TeamMember|None=Depends(require_editor)):
    if not inline_worker_enabled():
        raise HTTPException(409,"Inline execution is disabled; use the dedicated worker")
    task=db.get(ResearchTask,task_id)
    if task is None:raise HTTPException(404,"Task not found")
    if task.status!="queued":
        raise HTTPException(409,"Only queued tasks can be dispatched again")
    background.add_task(run_task,get_factory(),task.id)
    add_audit(db,"task.dispatched",actor.id if actor else None,task.id)
    db.commit()
    return as_dict(task)

@app.get("/api/tasks/{task_id}",dependencies=[Depends(require_actor)])
def task_detail(task_id:str,db:Session=Depends(get_db)):
    task=db.get(ResearchTask,task_id)
    if not task:raise HTTPException(404,"Task not found")
    return as_dict(task)

@app.get("/api/brief",dependencies=[Depends(require_actor)])
def brief(db:Session=Depends(get_db)):
    prof=get_profile(db)
    if not prof:return {"markdown":"","profile_ready":False}
    return {"markdown":weekly_report(db,prof),"profile_ready":True}
