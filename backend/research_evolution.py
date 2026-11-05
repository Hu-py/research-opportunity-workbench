"""Persistent autonomous research evolution, independent of the legacy human paper gate.

Research papers are vetted by competing LLM assessors BEFORE hypotheses.
Humans review only completed, evidence-linked recommendation packages.
"""
from __future__ import annotations
import json, math, os, uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base, get_profile
from backend.ai_lab import _dataset_context
from backend.model_vault import ModelCredential, load_key
from backend.research_budget import status as budget_status
from backend.repository import TeamAchievement
from backend.scientific_tournament import approved_learning
from backend.team import add_audit

STAGES=("plan","retrieve","screen","paper_referee",
        "seed_problem","seed_method","seed_data","score_initial",
        "challenge","counter_search","counter_referee","revise","score_final","package","done")
MODEL_STAGES=tuple(s for s in STAGES if s not in ("retrieve","counter_search","done"))
TOKEN_RESERVE=6500
MAX_PAPERS=14
MAX_TOOLS=10
THRESHOLD=80
STRATEGIES=("balanced","novelty","feasibility")

def now():return datetime.now(timezone.utc)
def dump(x):return json.dumps(x,ensure_ascii=False)
def load(x,default=None):
    try:return json.loads(x) if x else ({} if default is None else default)
    except (ValueError,TypeError):return {} if default is None else default
def text(x,name,n=900):
    if not isinstance(x,str) or not x.strip():raise ValueError("科研字段缺失："+name)
    return x.strip()[:n]
def string_list(x,name,n=8):
    if not isinstance(x,list) or any(not isinstance(v,str) for v in x):
        raise ValueError("科研列表无效："+name)
    return list(dict.fromkeys(v.strip()[:320] for v in x if v.strip()))[:n]

class EvolutionRun(Base):
    __tablename__="research_evolution_runs"
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    line_id:Mapped[str]=mapped_column(String(110),index=True)
    actor_id:Mapped[str]=mapped_column(String(64),default="")
    status:Mapped[str]=mapped_column(String(28),default="queued",index=True)
    stage:Mapped[str]=mapped_column(String(40),default="plan")
    strategy:Mapped[str]=mapped_column(String(24),default="balanced")
    snapshot_json:Mapped[str]=mapped_column(Text,default="{}")
    outputs_json:Mapped[str]=mapped_column(Text,default="{}")
    trace_json:Mapped[str]=mapped_column(Text,default="[]")
    model_calls:Mapped[int]=mapped_column(Integer,default=0)
    tool_calls:Mapped[int]=mapped_column(Integer,default=0)
    input_tokens:Mapped[int]=mapped_column(Integer,default=0)
    output_tokens:Mapped[int]=mapped_column(Integer,default=0)
    error:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class EvolutionFeedback(Base):
    __tablename__="research_evolution_feedback"
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    run_id:Mapped[str]=mapped_column(String(48),index=True)
    reviewer_id:Mapped[str]=mapped_column(String(64),index=True)
    decision:Mapped[str]=mapped_column(String(24))
    scientific_value:Mapped[int]=mapped_column(Integer)
    novelty:Mapped[int]=mapped_column(Integer)
    feasibility:Mapped[int]=mapped_column(Integer)
    testability:Mapped[int]=mapped_column(Integer)
    comment:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint("run_id","reviewer_id",
                                     name="uq_evolution_feedback_one_per_reviewer"),)

class EvolutionPolicy(Base):
    __tablename__="research_evolution_policy"
    strategy:Mapped[str]=mapped_column(String(24),primary_key=True)
    trials:Mapped[int]=mapped_column(Integer,default=0)
    total_reward:Mapped[float]=mapped_column(Float,default=0.0)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

def policy_report(db):
    rows={x.strategy:x for x in db.scalars(select(EvolutionPolicy)).all()}
    return [{"strategy":s,"trials":rows[s].trials if s in rows else 0,
             "mean_reward":round(rows[s].total_reward/max(1,rows[s].trials),3)
             if s in rows else None} for s in STRATEGIES]

def policy_choice(db):
    rows={r.strategy:r for r in db.scalars(select(EvolutionPolicy)).all()}
    for s in STRATEGIES:
        if s not in rows or not rows[s].trials:return s
    total=sum(x.trials for x in rows.values())
    return max(STRATEGIES,key=lambda s:rows[s].total_reward/rows[s].trials+
               math.sqrt(2*math.log(total+1)/rows[s].trials))

def snapshot(db,line_id):
    profile=get_profile(db) or {}
    line=next((x for x in profile.get("research_lines",[]) if x.get("id")==line_id),None)
    if not line:raise ValueError("团队画像中不存在所选研究主线")
    achievements=db.scalars(select(TeamAchievement).where(
        TeamAchievement.status=="verified").order_by(
        TeamAchievement.year.desc()).limit(8)).all()
    previous=db.scalars(select(EvolutionFeedback).join(
        EvolutionRun,EvolutionFeedback.run_id==EvolutionRun.id
    ).where(EvolutionRun.line_id==line_id).order_by(
        EvolutionFeedback.created_at.desc()).limit(6)).all()
    return {"line":{"id":line_id,"name":text(line.get("name"),"name",180),
                    "problem":text(line.get("problem"),"problem",600),
                    "keywords":line.get("keywords",[])[:12]},
            "datasets":_dataset_context(db,line_id)[:10],
            "achievements":[{"title":a.title[:200],"year":a.year} for a in achievements],
            "approved_feedback":approved_learning(db,line_id,limit=5),
            "evolution_feedback":[{"decision":x.decision,"comment":x.comment[:550],
                "scores":{"scientific_value":x.scientific_value,
                          "novelty":x.novelty,"feasibility":x.feasibility,
                          "testability":x.testability}} for x in previous],
            "evidence_note":"仅有学术元数据与摘要；不等于全文或创新性核验"}

def readiness(db,line_id):
    reasons=[]
    try:snap=snapshot(db,line_id)
    except ValueError as e:snap=None;reasons.append(str(e))
    row=db.get(ModelCredential,"deepseek")
    if not row or not row.encrypted_key:reasons.append("请配置 DeepSeek API Key")
    if not os.getenv("MODEL_VAULT_KEY"):reasons.append("未配置模型密钥加密服务")
    budget=budget_status(db)
    used=budget["used"];lim=budget["limits"]
    if lim["model_calls_per_day"]-used["model_calls"]<len(MODEL_STAGES):
        reasons.append("今日模型调用额度不足")
    if (lim["token_reservation_per_day"]-used["token_reservation"] <
            len(MODEL_STAGES)*TOKEN_RESERVE):
        reasons.append("今日Token额度不足")
    if lim["papers_per_day"]-used["papers"]<MAX_PAPERS:
        reasons.append("今日论文数量额度不足")
    return {"ready":not reasons,"line":snap["line"] if snap else None,
            "reasons":reasons,"paper_human_approval_required":False,
            "max_model_calls":len(MODEL_STAGES),"minimum_quality_score":THRESHOLD}

def create_run(db,line_id,actor_id):
    if not actor_id:raise ValueError("需要已登录的团队研究人员")
    cfg=db.get(ModelCredential,"deepseek")
    if not cfg or not cfg.encrypted_key or not load_key(db):
        raise ValueError("DeepSeek Key 未配置或不可解密")
    if db.scalar(select(EvolutionRun.id).where(
        EvolutionRun.status.in_(("queued","running"))).limit(1)):
        raise ValueError("已有自主科研任务正在执行")
    snap=snapshot(db,line_id) # No human-paper-review gate.
    check=readiness(db,line_id)
    if not check["ready"]:raise ValueError("；".join(check["reasons"]))
    row=EvolutionRun(id=str(uuid.uuid4()),line_id=line_id,actor_id=actor_id,
                     strategy=policy_choice(db),snapshot_json=dump(snap))
    db.add(row);add_audit(db,"evolution.queued",actor_id,row.id);db.commit()
    return row

def view(run,detailed=False):
    result={"id":run.id,"line_id":run.line_id,"status":run.status,
            "stage":run.stage,"strategy":run.strategy,
            "model_calls":run.model_calls,"tool_calls":run.tool_calls,
            "input_tokens":run.input_tokens,"output_tokens":run.output_tokens,
            "error":run.error,"novelty_verified":False,
            "created_at":run.created_at.isoformat() if run.created_at else None}
    if detailed:
        outputs=load(run.outputs_json)
        result.update({"papers":outputs.get("papers",[]),
                       "paper_assessments":outputs.get("screen",[]),
                       "paper_referee":outputs.get("paper_referee",{}),
                       "versions":[{"stage":s,"value":outputs[s]} for s in
                         ("seed_problem","seed_method","seed_data","score_initial",
                          "challenge","counter_referee","revise","score_final") if s in outputs],
                       "recommendation":outputs.get("package")
                           if run.status=="review_ready" else None,
                       "trace":load(run.trace_json,[]),
                       "quality":outputs.get("score_final",{})})
    return result

def resume(db,run_id,actor):
    row=db.get(EvolutionRun,run_id)
    if not row or row.status not in ("failed","queued","running") or row.stage=="done":
        raise ValueError("任务无法恢复")
    if row.status!="failed":
        age=row.updated_at or now()
        if age.tzinfo is None:age=age.replace(tzinfo=timezone.utc)
        if now()-age<timedelta(minutes=8):
            raise ValueError("任务可能仍在执行，8分钟无更新后才可恢复")
    row.status="queued";row.error="";row.updated_at=now()
    add_audit(db,"evolution.resumed",actor,row.id);db.commit()
    return row

def feedback(db,run_id,reviewer,decision,scores,comment=""):
    row=db.get(EvolutionRun,run_id)
    if not row or row.status!="review_ready":
        raise ValueError("只有机器完成的科研推荐包允许人工批阅")
    if decision not in ("adopt","revise","defer","reject"):
        raise ValueError("无效的研究评价")
    fields=("scientific_value","novelty","feasibility","testability")
    if any(type(scores.get(k)) is not int or not 1<=scores[k]<=5 for k in fields):
        raise ValueError("评分必须是1到5的整数")
    if db.scalar(select(EvolutionFeedback.id).where(
        EvolutionFeedback.run_id==run_id,EvolutionFeedback.reviewer_id==reviewer).limit(1)):
        raise ValueError("该研究人员已经评价过这份推荐")
    db.add(EvolutionFeedback(id=str(uuid.uuid4()),run_id=run_id,reviewer_id=reviewer,
        decision=decision,comment=str(comment)[:1200],**{k:scores[k] for k in fields}))
    reward=0.7*{"adopt":1.,"revise":0.4,"defer":-0.2,"reject":-1.}[decision]+(
        0.3*(sum(scores[k] for k in fields)/10-1))
    policy=db.scalar(select(EvolutionPolicy).where(
        EvolutionPolicy.strategy==row.strategy).with_for_update())
    if policy is None:
        policy=EvolutionPolicy(strategy=row.strategy,trials=0,total_reward=0.0)
        db.add(policy)
    policy.trials+=1;policy.total_reward+=reward;policy.updated_at=now()
    add_audit(db,"evolution.feedback",reviewer,run_id,"decision="+decision)
    try:db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("该研究人员已经评价过这份推荐") from exc
    return {"run_id":run_id,"policy":row.strategy,"reward":round(reward,3),
            "model_weight_training":False,"human_review_stage":"final_only"}
