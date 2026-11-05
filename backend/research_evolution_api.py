"""Authenticated API endpoints for autonomous research without a new FastAPI application."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.research_evolution import (
    EvolutionRun, readiness, create_run, view, resume, feedback, policy_report)
from backend.research_evolution_runner import execute

class EvolutionStartRequest(BaseModel):
    line_id: str = Field(min_length=1,max_length=110)

class EvolutionFeedbackRequest(BaseModel):
    decision: str = Field(pattern="^(adopt|revise|defer|reject)$")
    scientific_value: int = Field(ge=1,le=5)
    novelty: int = Field(ge=1,le=5)
    feasibility: int = Field(ge=1,le=5)
    testability: int = Field(ge=1,le=5)
    comment: str = Field(default="",max_length=1200)

def mount(app, *, get_db, get_factory, require_actor, require_editor,
          team_auth_enabled):
    router=APIRouter(prefix="/api/research-evolution")

    @router.get("/readiness",dependencies=[Depends(require_actor)])
    def check(line_id:str=Query(min_length=1,max_length=110),
              db:Session=Depends(get_db)):
        return readiness(db,line_id)

    @router.get("/policy",dependencies=[Depends(require_actor)])
    def policy(db:Session=Depends(get_db)):
        return {"policies":policy_report(db),"model_weight_training":False,
                "method":"UCB1 based on final human ratings, not RLHF"}

    @router.post("",status_code=202,dependencies=[Depends(require_editor)])
    def start(data:EvolutionStartRequest,background:BackgroundTasks,
              actor=Depends(require_editor),db:Session=Depends(get_db)):
        if not team_auth_enabled() or actor is None:
            raise HTTPException(403,"需要已登录的团队研究人员身份")
        try:run=create_run(db,data.line_id,actor.id)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        background.add_task(execute,get_factory(),run.id)
        return {"id":run.id,"status":"queued",
                "requires_manual_paper_approval":False,
                "human_review_stage":"final_package_only"}

    @router.get("",dependencies=[Depends(require_actor)])
    def list_runs(db:Session=Depends(get_db)):
        runs=db.scalars(select(EvolutionRun).order_by(
            EvolutionRun.created_at.desc()).limit(25)).all()
        return {"items":[view(run) for run in runs]}

    @router.get("/{run_id}",dependencies=[Depends(require_actor)])
    def details(run_id:str,db:Session=Depends(get_db)):
        run=db.get(EvolutionRun,run_id)
        if not run:raise HTTPException(404,"科研演化任务不存在")
        return view(run,True)

    @router.post("/{run_id}/resume",status_code=202,
                 dependencies=[Depends(require_editor)])
    def resume_run(run_id:str,background:BackgroundTasks,
                   actor=Depends(require_editor),db:Session=Depends(get_db)):
        if not team_auth_enabled() or actor is None:
            raise HTTPException(403,"需要已登录的团队研究人员身份")
        try:run=resume(db,run_id,actor.id)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        background.add_task(execute,get_factory(),run.id)
        return {"id":run.id,"status":"queued"}

    @router.post("/{run_id}/feedback",dependencies=[Depends(require_editor)])
    def rate(run_id:str,data:EvolutionFeedbackRequest,
             actor=Depends(require_editor),db:Session=Depends(get_db)):
        if not team_auth_enabled() or actor is None:
            raise HTTPException(403,"需要已登录的团队研究人员身份")
        scores=data.model_dump(include={
            "scientific_value","novelty","feasibility","testability"})
        try:return feedback(db,run_id,actor.id,data.decision,scores,data.comment)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    app.include_router(router)
