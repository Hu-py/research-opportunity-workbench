"""Authenticated FastAPI service for the Research Opportunity Workbench."""
from __future__ import annotations

import hmac
import json
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_workbench.core import (
    Paper, Idea, Evidence, Event, Profile, Base,
    get_profile, set_profile, feedback, weekly_report, validate_profile,
    session_factory,
)
from backend.tasks import ResearchTask, enqueue, as_dict
from backend.worker import run_task

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

@asynccontextmanager
async def lifespan(app:FastAPI):
    if os.getenv("APP_ENV","development").lower()=="production" and not os.getenv("API_BEARER_TOKEN"):
        raise RuntimeError("Set API_BEARER_TOKEN before production deployment")
    get_factory()
    yield

app=FastAPI(
    title="Research Opportunity Workbench API",
    description="Paper intelligence, rolling ideas and evidence-traceable agent jobs.",
    version="0.2.0",
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

@app.get("/api/health")
def health():
    return {"ok":True,"service":"research-workbench","version":"0.2.0"}

@app.get("/api/overview",dependencies=[Depends(authenticate)])
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

@app.get("/api/papers",dependencies=[Depends(authenticate)])
def papers(search:str=Query(default="",max_length=180),
           limit:int=Query(default=100,ge=1,le=300),
           db:Session=Depends(get_db)):
    rows=db.scalars(select(Paper).order_by(Paper.published.desc()).limit(2000)).all()
    term=search.strip().lower()
    if term:rows=[p for p in rows if term in (p.title+" "+p.abstract+" "+p.venue).lower()]
    return {"total":len(rows),"items":[paper_dict(p) for p in rows[:limit]]}

@app.get("/api/ideas",dependencies=[Depends(authenticate)])
def ideas(status_filter:str|None=None,db:Session=Depends(get_db)):
    rows=db.scalars(select(Idea).order_by(Idea.score.desc()).limit(200)).all()
    if status_filter:rows=[i for i in rows if i.status==status_filter]
    return {"items":[idea_dict(i,db) for i in rows]}

@app.get("/api/ideas/{idea_id}/history",dependencies=[Depends(authenticate)])
def idea_history(idea_id:str,db:Session=Depends(get_db)):
    if not db.get(Idea,idea_id):raise HTTPException(404,"Idea not found")
    events=db.scalars(select(Event).where(Event.idea_id==idea_id)
                      .order_by(Event.version.desc())).all()
    return {"items":[{"version":e.version,"action":e.action,"detail":json.loads(e.detail or "{}"),
                      "created_at":e.created_at.isoformat() if e.created_at else None} for e in events]}

@app.post("/api/ideas/{idea_id}/feedback",dependencies=[Depends(authenticate)])
def idea_feedback(idea_id:str,data:FeedbackRequest,db:Session=Depends(get_db)):
    try:feedback(db,idea_id,data.status,data.note)
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc
    return idea_dict(db.get(Idea,idea_id),db)

@app.get("/api/profile",dependencies=[Depends(authenticate)])
def profile(db:Session=Depends(get_db)):
    return {"profile":get_profile(db)}

@app.put("/api/profile",dependencies=[Depends(authenticate)])
def profile_update(data:ProfileRequest,db:Session=Depends(get_db)):
    payload=data.model_dump()
    try:set_profile(db,payload)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    return {"profile":get_profile(db)}

@app.get("/api/tasks",dependencies=[Depends(authenticate)])
def tasks(db:Session=Depends(get_db)):
    rows=db.scalars(select(ResearchTask).order_by(ResearchTask.created_at.desc()).limit(40)).all()
    return {"items":[as_dict(t) for t in rows]}

@app.post("/api/tasks",status_code=status.HTTP_202_ACCEPTED,dependencies=[Depends(authenticate)])
def tasks_start(data:TaskRequest,background:BackgroundTasks,db:Session=Depends(get_db)):
    if data.kind=="explore" and len(data.query.strip())<6:
        raise HTTPException(422,"请输入更具体的研究问题（至少 6 个字符）")
    task=enqueue(db,data.kind,data.query)
    # BackgroundTasks is a local development convenience, NOT a durable worker.
    if os.getenv("APP_ENV","development")!="production" and os.getenv("WORKER_MODE","background")=="background":
        background.add_task(run_task,get_factory(),task.id)
    return as_dict(task)

@app.get("/api/tasks/{task_id}",dependencies=[Depends(authenticate)])
def task_detail(task_id:str,db:Session=Depends(get_db)):
    task=db.get(ResearchTask,task_id)
    if not task:raise HTTPException(404,"Task not found")
    return as_dict(task)

@app.get("/api/brief",dependencies=[Depends(authenticate)])
def brief(db:Session=Depends(get_db)):
    prof=get_profile(db)
    if not prof:return {"markdown":"","profile_ready":False}
    return {"markdown":weekly_report(db,prof),"profile_ready":True}
