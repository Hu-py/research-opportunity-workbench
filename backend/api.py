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
    with factory() as db:
        db.execute(sql_text("SELECT 1"))
        logging.getLogger(__name__).info(
            "Research database connection verified: dialect=%s",
            db.get_bind().dialect.name,
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
    rows=db.scalars(select(TeamMember).order_by(TeamMember.created_at.asc())).all()
    return {"items":[public_member(x) for x in rows]}

@app.post("/api/team/members",dependencies=[Depends(require_admin)],status_code=201)
def team_add_member(data:MemberRequest,actor:TeamMember|None=Depends(require_admin),
                    db:Session=Depends(get_db)):
    try:
        m=create_member(db,data.email,data.name,data.temporary_password,data.role,
                        actor_id=actor.id if actor else None)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return public_member(m)

@app.patch("/api/team/members/{member_id}",dependencies=[Depends(require_admin)])
def team_update_member(member_id:str,data:MemberUpdateRequest,
                       actor:TeamMember|None=Depends(require_admin),db:Session=Depends(get_db)):
    m=db.get(TeamMember,member_id)
    if not m:raise HTTPException(404,"Member not found")
    try:set_member_status(db,m,active=data.active,role=data.role,actor_id=actor.id if actor else "")
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return public_member(m)

@app.get("/api/team/audit",dependencies=[Depends(require_admin)])
def team_audit(db:Session=Depends(get_db)):
    rows=db.scalars(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(150)).all()
    return {"items":[{"id":x.id,"actor_id":x.actor_id,"action":x.action,"target":x.target,
                       "note":x.note,"created_at":x.created_at.isoformat() if x.created_at else None}
                      for x in rows]}

@app.get("/api/team/profile-history",dependencies=[Depends(require_actor)])
def team_profile_history(db:Session=Depends(get_db)):
    rows=db.scalars(select(TeamProfileRevision).order_by(TeamProfileRevision.version.desc()).limit(50)).all()
    return {"items":[{"version":r.version,"actor_id":r.actor_id,
                       "created_at":r.created_at.isoformat() if r.created_at else None} for r in rows]}

@app.get("/api/health")
def health():
    return {"ok":True,"service":"research-workbench","version":"0.3.0"}

@app.get("/api/overview",dependencies=[Depends(require_actor)])
def overview(db:Session=Depends(get_db)):
    return {"papers":db.scalar(select(func.count()).select_from(Paper)) or 0,
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
    # BackgroundTasks is a local development convenience, NOT a durable worker.
    if os.getenv("APP_ENV","development")!="production" and os.getenv("WORKER_MODE","background")=="background":
        background.add_task(run_task,get_factory(),task.id)
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
