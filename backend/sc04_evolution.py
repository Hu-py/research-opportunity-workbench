"""SC04: Personal child-health research evolution; evidence is frozen per run.

This module owns the private baseline, approved-source paper snapshot, and
human review. Machine analysis is in sc04_evolution_runner, never triggered on GET.
No team profile, publication or health record is modified.
"""
from __future__ import annotations
import hashlib, json, re, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from research_workbench.core import Base
from backend.team import TeamMember, add_audit
from backend.model_vault import status as model_status
from backend.research_budget import status as budget_status
from backend.task_venue_radar import TASK_KEY, TaskVenuePaperRun

VERSION="sc04-v0.1.0"
MAX_PAPERS=5
BASELINE_DRAFT={
 "research_question":"如何验证从局部儿童发展调查训练的建成环境模型能跨城区或跨城市迁移？",
 "study_design":"局部区域调查数据关联至道路，训练后向未覆盖的城市空间外推；外部道路健康标签稀疏且受关联噪声影响。",
 "existing_methods":[
    "B1 建成环境特征 + XGBoost",
    "B2 邻域聚合特征 + XGBoost",
    "B3 GraphSAGE 表征 + XGBoost"],
 "observations":[
    "直接区域外推有域偏移与外部验证困难",
    "简单邻域均值聚合是强基线，不应假定复杂 GNN 一定更好",
    "AOA/DI 表明部分目标城区的环境表征与训练域不同"],
 "constraints":[
    "外部儿童标签较稀疏，空间软关联可能存在测量误差",
    "验证/测试结局不得进入训练与图聚合",
    "没有独立 SES 真值时不能声称 SES 预测已被验证"],
 "validation_goal":"优先检验真正独立空间留出及外部城市迁移，而不是随机混合验证",
 "provenance":"chat_context_researcher_review_required_not_validated_results"
}

def now():return datetime.now(timezone.utc)
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True)
def load(s,default=None):
    try:return json.loads(s) if s else default
    except (ValueError,TypeError):return default
def digest(v):return hashlib.sha256(dump(v).encode("utf-8")).hexdigest()

class SC04Baseline(Base):
    __tablename__="sc04_personal_baselines"
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),primary_key=True)
    task_key:Mapped[str]=mapped_column(String(90),primary_key=True,default=TASK_KEY)
    payload_json:Mapped[str]=mapped_column(Text)
    revision:Mapped[int]=mapped_column(Integer,default=1)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class SC04Run(Base):
    __tablename__="sc04_personal_runs"
    id:Mapped[str]=mapped_column(String(50),primary_key=True)
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"),index=True)
    task_key:Mapped[str]=mapped_column(String(90),default=TASK_KEY)
    status:Mapped[str]=mapped_column(String(24),default="prepared")
    stage:Mapped[str]=mapped_column(String(24),default="reader")
    snapshot_json:Mapped[str]=mapped_column(Text)
    snapshot_sha:Mapped[str]=mapped_column(String(64))
    reader_json:Mapped[str]=mapped_column(Text,default="[]")
    matches_json:Mapped[str]=mapped_column(Text,default="[]")
    variants_json:Mapped[str]=mapped_column(Text,default="[]")
    critic_json:Mapped[str]=mapped_column(Text,default="[]")
    model_calls:Mapped[int]=mapped_column(Integer,default=0)
    input_tokens:Mapped[int]=mapped_column(Integer,default=0)
    output_tokens:Mapped[int]=mapped_column(Integer,default=0)
    error:Mapped[str]=mapped_column(String(280),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class SC04Review(Base):
    __tablename__="sc04_personal_reviews"
    id:Mapped[str]=mapped_column(String(50),primary_key=True)
    run_id:Mapped[str]=mapped_column(String(50),ForeignKey("sc04_personal_runs.id"))
    member_id:Mapped[str]=mapped_column(String(36),ForeignKey("team_members.id"))
    ratings_json:Mapped[str]=mapped_column(Text)
    target:Mapped[str]=mapped_column(String(24))
    decision:Mapped[str]=mapped_column(String(20))
    comment:Mapped[str]=mapped_column(String(950))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class BaselineRequest(BaseModel):
    research_question:str=Field(min_length=15,max_length=900)
    study_design:str=Field(min_length=15,max_length=1100)
    existing_methods:list[str]=Field(min_length=2,max_length=8)
    observations:list[str]=Field(min_length=1,max_length=8)
    constraints:list[str]=Field(min_length=2,max_length=8)
    validation_goal:str=Field(min_length=12,max_length=900)
    confirmed:bool=True

class ConsentRequest(BaseModel):
    acknowledge_external_model:bool

class ReviewRequest(BaseModel):
    paper_accuracy:int=Field(ge=1,le=5)
    method_fit:int=Field(ge=1,le=5)
    novelty_caution:int=Field(ge=1,le=5)
    experiment_feasibility:int=Field(ge=1,le=5)
    usefulness:int=Field(ge=1,le=5)
    target:str=Field(pattern="^(retrieval|reader|transfer|critic|experiment)$")
    decision:str=Field(pattern="^(keep|revise|reject)$")
    comment:str=Field(min_length=8,max_length=950)

def baseline(db,member_id):
    row=db.get(SC04Baseline,(member_id,TASK_KEY))
    return {"confirmed":bool(row),"revision":row.revision if row else None,
            "payload":load(row.payload_json,{}) if row else BASELINE_DRAFT,
            "notice":"初始研究基准来自对话草稿，需本人校对保存后才会用于模型调用。"}

def papers_from_strict_scan(db,member_id):
    """One recent, frozen, previously allowed source-ID scan; no paper mixing."""
    scan=db.scalars(select(TaskVenuePaperRun).where(
        TaskVenuePaperRun.member_id==member_id,TaskVenuePaperRun.task_key==TASK_KEY,
        TaskVenuePaperRun.status.in_(("completed","partial")))
        .order_by(TaskVenuePaperRun.created_at.desc()).limit(1)).first()
    if not scan:return None,[],{"total":0,"with_abstract":0,"groups":[]}
    groups={"A":[],"B":[],"C":[]}
    seen=set();total=0
    raw=load(scan.results_json,[])
    for p in raw[:100] if isinstance(raw,list) else []:
        if not isinstance(p,dict):continue
        pid=str(p.get("id") or "")
        group=p.get("probe_group")
        if not pid or pid in seen or group not in groups:continue
        seen.add(pid);total+=1
        abstract=re.sub(r"\s+"," ",str(p.get("abstract") or "")).strip()[:2600]
        url=str(p.get("url") or "")
        if len(abstract)<130 or not url.startswith("https://") or not p.get("title"):continue
        groups[group].append({"id":pid[:255],"title":str(p["title"])[:350],
             "abstract":abstract,"url":url[:1100],"group":group,
             "venue":str(p.get("venue") or "")[:200],
             "published":str(p.get("published") or "")[:30],
             "evidence_level":"OpenAlex abstract, no full-text audit"})
    selected=[]
    for i in range(2):
        for g in "ABC":
            if len(groups[g])>i:selected.append(groups[g][i])
    selected=selected[:MAX_PAPERS]
    return scan,selected,{"total":total,"with_abstract":sum(len(v) for v in groups.values()),
        "groups":[k for k,v in groups.items() if v],
        "selected":len(selected),
        "source_ids":load(scan.source_ids_json,{}),"scan_id":scan.id}

def evidence(db,member_id):
    scan,papers,stats=papers_from_strict_scan(db,member_id)
    return {"ready":len(papers)>=3 and len({x["group"] for x in papers})>=2,
        "scan_id":scan.id if scan else None,"stats":stats,
        "papers":[{"id":x["id"],"title":x["title"],"group":x["group"],
                   "venue":x["venue"],"url":x["url"]} for x in papers],
        "warning":"仅使用已批准来源扫描的 OpenAlex 摘要，尚未审阅原文全文。至少需3篇摘要、覆盖2个探针。"}

def run_view(row,detailed=False):
    result={"id":row.id,"status":row.status,"stage":row.stage,"engine_version":VERSION,
      "snapshot_sha":row.snapshot_sha,"paper_count":len((load(row.snapshot_json,{}) or {}).get("papers",[])),
      "model_calls":row.model_calls,"input_tokens":row.input_tokens,"output_tokens":row.output_tokens,
      "error":row.error,"created_at":row.created_at.isoformat(),
      "updated_at":row.updated_at.isoformat(),
      "novelty_verified":False,"science_experiment_executed":False}
    if detailed:
        result.update({"snapshot":load(row.snapshot_json,{}),
          "readings":load(row.reader_json,[]),"matches":load(row.matches_json,[]),
          "variants":load(row.variants_json,[]),"critic":load(row.critic_json,[])})
    return result

def owned_run(db,member_id,run_id):
    row=db.get(SC04Run,run_id)
    if not row or row.member_id!=member_id or row.task_key!=TASK_KEY:
        raise HTTPException(404,"不存在该用户的科研演化任务")
    return row

def prepare(db,member):
    row=db.get(SC04Baseline,(member.id,TASK_KEY))
    if not row:raise ValueError("请先校对并保存已有研究基准")
    scan,papers,stats=papers_from_strict_scan(db,member.id)
    if len(papers)<3 or len({x["group"] for x in papers})<2:
        raise ValueError("缺少3篇覆盖2个探针的真实摘要。请先到期刊目录执行严格来源检索")
    busy=db.scalars(select(SC04Run.id).where(
        SC04Run.member_id==member.id,
        SC04Run.status.in_(("queued","running"))).limit(1)).first()
    if busy:raise ValueError("当前账号已有运行中的实验")
    snap={"task":TASK_KEY,"baseline":load(row.payload_json,{}),"baseline_revision":row.revision,
          "papers":papers,"source_scan":scan.id,
          "source_ids":stats["source_ids"],"skill_version":VERSION,
          "evidence_level":"abstract_only", "novelty_status":"unverified"}
    result=SC04Run(id="sc04_"+uuid.uuid4().hex[:30],member_id=member.id,
                   snapshot_json=dump(snap),snapshot_sha=digest(snap))
    db.add(result)
    add_audit(db,"sc04.prepare",member.id,result.id,"strict_source_scan="+scan.id)
    db.commit()
    return run_view(result,True)

def mount(app,*,get_db,require_actor,team_auth_enabled,get_factory):
    from backend.sc04_evolution_runner import execute
    router=APIRouter(prefix="/api/personal-research/me/evolution",
                     tags=["SC04 Child Health Personal Research Evolution"])
    def member(actor:TeamMember|None=Depends(require_actor)):
        if not team_auth_enabled() or actor is None or not actor.active:
            raise HTTPException(401,"请登录本人科研账号")
        return actor

    @router.get("")
    def overview(db:Session=Depends(get_db),actor:TeamMember=Depends(member)):
        rows=db.scalars(select(SC04Run).where(
            SC04Run.member_id==actor.id,SC04Run.task_key==TASK_KEY)
            .order_by(SC04Run.created_at.desc()).limit(20)).all()
        return {"task":TASK_KEY,"version":VERSION,"baseline":baseline(db,actor.id),
                "evidence":evidence(db,actor.id),"model":model_status(db),
                "budget":budget_status(db),
                "runs":[run_view(x) for x in rows]}

    @router.put("/baseline")
    def save(data:BaselineRequest,db:Session=Depends(get_db),
             actor:TeamMember=Depends(member)):
        if not data.confirmed:raise HTTPException(422,"需要本人确认研究基准")
        for v in data.existing_methods+data.observations+data.constraints:
            if not 8<=len(v.strip())<=400:raise HTTPException(422,"条目需8至400字")
        value=data.model_dump(exclude={"confirmed"})
        value["provenance"]="researcher_confirmed"
        row=db.get(SC04Baseline,(actor.id,TASK_KEY))
        if row:
            row.payload_json=dump(value);row.revision+=1;row.updated_at=now()
        else:
            row=SC04Baseline(member_id=actor.id,task_key=TASK_KEY,payload_json=dump(value))
            db.add(row)
        add_audit(db,"sc04.baseline_saved",actor.id,TASK_KEY,"version="+str(row.revision))
        db.commit()
        return baseline(db,actor.id)

    @router.post("/prepare",status_code=201)
    def prep(db:Session=Depends(get_db),actor:TeamMember=Depends(member)):
        try:return prepare(db,actor)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc

    @router.get("/runs/{run_id}")
    def detail(run_id:str,db:Session=Depends(get_db),actor:TeamMember=Depends(member)):
        row=owned_run(db,actor.id,run_id)
        reviews=db.scalars(select(SC04Review).where(
            SC04Review.member_id==actor.id,SC04Review.run_id==run_id)
            .order_by(SC04Review.created_at.desc()).limit(20)).all()
        return {"run":run_view(row,True),"feedback":[{"id":x.id,
            "ratings":load(x.ratings_json,{}),"target":x.target,
            "decision":x.decision,"comment":x.comment,
            "created_at":x.created_at.isoformat()} for x in reviews]}

    def schedule(run_id,data,background,db,actor,resume=False):
        if not data.acknowledge_external_model:
            raise HTTPException(422,"请确认允许上传已核验研究基准和公开摘要给模型")
        row=owned_run(db,actor.id,run_id)
        required="failed" if resume else "prepared"
        if row.status!=required:raise HTTPException(409,"当前状态不能启动或恢复")
        cfg=model_status(db)
        if not cfg["configured"] or not cfg["vault_ready"]:
            raise HTTPException(409,"DeepSeek API Key/加密服务尚未配置，模型不会被调用")
        other=db.scalars(select(SC04Run.id).where(
            SC04Run.member_id==actor.id,SC04Run.status.in_(("queued","running"))).limit(1)).first()
        if other:raise HTTPException(409,"已有运行中的实验")
        row.status="queued";row.error="";row.updated_at=now()
        add_audit(db,"sc04.llm_requested",actor.id,row.id,"stage="+row.stage)
        db.commit()
        background.add_task(execute,get_factory(),run_id)
        return run_view(row)

    @router.post("/runs/{run_id}/start",status_code=202)
    def start(run_id:str,data:ConsentRequest,background:BackgroundTasks,
              db:Session=Depends(get_db),actor:TeamMember=Depends(member)):
        return schedule(run_id,data,background,db,actor)

    @router.post("/runs/{run_id}/resume",status_code=202)
    def resume(run_id:str,data:ConsentRequest,background:BackgroundTasks,
               db:Session=Depends(get_db),actor:TeamMember=Depends(member)):
        return schedule(run_id,data,background,db,actor,resume=True)

    @router.post("/runs/{run_id}/review",status_code=201)
    def review(run_id:str,data:ReviewRequest,db:Session=Depends(get_db),
               actor:TeamMember=Depends(member)):
        row=owned_run(db,actor.id,run_id)
        if row.status!="completed":raise HTTPException(409,"请先完成模型分析再评价")
        values=data.model_dump()
        ratings={k:values[k] for k in (
            "paper_accuracy","method_fit","novelty_caution","experiment_feasibility","usefulness")}
        item=SC04Review(id="review_"+uuid.uuid4().hex[:28],
          run_id=run_id,member_id=actor.id,ratings_json=dump(ratings),
          target=data.target,decision=data.decision,comment=data.comment)
        db.add(item)
        add_audit(db,"sc04.feedback",actor.id,run_id,
                  "focus="+data.target+";decision="+data.decision)
        db.commit()
        return {"id":item.id,"saved":True,"ratings":ratings}

    app.include_router(router)
