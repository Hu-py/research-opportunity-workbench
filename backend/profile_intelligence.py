"""Research portrait studio: reviewed drafts, repeatable LLM synthesis and safe team promotion.

The initial user-context example is privately bootstrapped into PostgreSQL,
never checked into a public repository, and never silently replaces a team's
official profile. LLM invocation is manually gated behind an API key.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime,timezone
from sqlalchemy import DateTime,Integer,String,Text,select,update
from sqlalchemy.orm import Mapped,mapped_column
from research_workbench.core import Base,get_profile,validate_profile
from backend.cusp import CuspDataset,sensitive_level
from backend.repository import TeamAchievement
from backend.model_vault import ModelCredential,load_key
from backend.model_gateway import request_json,ModelCallError
from backend.skill_loader import load_skills
from backend.team import add_audit,current_profile_version,save_team_profile
from backend.profile_database import evidence_inventory,database_draft,safe_overview

def now():return datetime.now(timezone.utc)
def pack(x):return json.dumps(x,ensure_ascii=False)
def unpack(s,default=None):
    try:return json.loads(s) if s else default
    except (ValueError,TypeError):return default

class ResearchProfileDraft(Base):
    __tablename__="research_profile_drafts"
    id:Mapped[str]=mapped_column(String(55),primary_key=True)
    source:Mapped[str]=mapped_column(String(26),default="curated_example")
    scope:Mapped[str]=mapped_column(String(24),default="personal_collaborative")
    status:Mapped[str]=mapped_column(String(20),default="draft")
    base_version:Mapped[int]=mapped_column(Integer,default=0)
    revision:Mapped[int]=mapped_column(Integer,default=1)
    profile_json:Mapped[str]=mapped_column(Text)
    analysis_json:Mapped[str]=mapped_column(Text)
    provenance_json:Mapped[str]=mapped_column(Text,default="[]")
    note:Mapped[str]=mapped_column(Text,default="")
    model:Mapped[str]=mapped_column(String(80),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    applied_version:Mapped[int|None]=mapped_column(Integer,nullable=True)

class ProfileSynthesisRun(Base):
    __tablename__="research_profile_synthesis_runs"
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    status:Mapped[str]=mapped_column(String(20),default="queued")
    snapshot_json:Mapped[str]=mapped_column(Text,default="{}")
    model:Mapped[str]=mapped_column(String(80),default="")
    draft_id:Mapped[str]=mapped_column(String(55),default="")
    error:Mapped[str]=mapped_column(Text,default="")
    input_tokens:Mapped[int]=mapped_column(Integer,default=0)
    output_tokens:Mapped[int]=mapped_column(Integer,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ResearchProfileDraftRevision(Base):
    __tablename__="research_profile_draft_revisions"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    draft_id:Mapped[str]=mapped_column(String(55),index=True)
    revision:Mapped[int]=mapped_column(Integer)
    profile_json:Mapped[str]=mapped_column(Text)
    actor_id:Mapped[str]=mapped_column(String(60),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

def _texts(values,name,maxcount=12,limit=300):
    if not isinstance(values,list):raise ValueError(name+" 必须是列表")
    if len(values)>maxcount:raise ValueError(name+" 数量过多")
    if any(not isinstance(v,str) or not v.strip() for v in values):
        raise ValueError(name+" 包含无效文字")
    return [v.strip()[:limit] for v in values]

def _profile(value):
    """Validate and strip non-canonical keys, avoiding accidental raw data."""
    if not isinstance(value,dict):raise ValueError("画像必须为 JSON 对象")
    raw=value.get("research_lines")
    if not isinstance(raw,list) or not 1<=len(raw)<=8:
        raise ValueError("研究主线需要 1–8 条")
    lines=[];ids=set()
    for x in raw:
        if not isinstance(x,dict):raise ValueError("研究主线必须为对象")
        ident=x.get("id")
        if not isinstance(ident,str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,54}",ident):
            raise ValueError("研究主线 id 须为英文小写及下划线")
        if ident in ids:raise ValueError("研究主线 id 重复")
        ids.add(ident)
        name=x.get("name");problem=x.get("problem")
        if not isinstance(name,str) or not name.strip() or len(name)>140:
            raise ValueError("研究主线缺少名称")
        if not isinstance(problem,str) or not problem.strip() or len(problem)>1000:
            raise ValueError("研究主线缺少具体问题")
        lines.append({"id":ident,"name":name.strip(),"problem":problem.strip(),
            "keywords":_texts(x.get("keywords",[]),"keywords",16,100),
            "search_queries":_texts(x.get("search_queries",[]),"search_queries",5,160),
            "method_queries":_texts(x.get("method_queries",[]),"method_queries",5,160)})
    team=value.get("team") or {}
    if not isinstance(team,dict):raise ValueError("team 结构无效")
    priorities=_texts(team.get("priorities",[]),"team.priorities",12,150)
    goals=value.get("goals","")
    if not isinstance(goals,str):raise ValueError("goals 结构无效")
    result={"research_lines":lines,"goals":goals[:1000],
        "team":{"name":str(team.get("name",""))[:140],
                "mission":str(team.get("mission",""))[:1000],
                "priorities":priorities},
        "methods":_texts(value.get("methods",[]),"methods",30,120),
        "excluded_terms":_texts(value.get("excluded_terms",[]),"excluded_terms",30,120),
        # CUSP metadata remain in cusp_datasets; do not duplicate raw assets.
        "datasets":[]}
    validate_profile(result)
    return result

def _analysis(value,profile):
    if not isinstance(value,dict):raise ValueError("画像分析必须为 JSON 对象")
    insights=value.get("line_insights",[])
    if not isinstance(insights,list) or len(insights)>10:
        raise ValueError("line_insights 结构无效")
    if not insights:raise ValueError("需要为每条研究主线提供瓶颈与验证方案")
    ids={x["id"] for x in profile["research_lines"]}
    findings=[]
    for x in insights:
        if not isinstance(x,dict) or x.get("line_id") not in ids:
            raise ValueError("分析引用了不存在的研究主线")
        findings.append({"line_id":x["line_id"],
            "bottleneck":str(x.get("bottleneck",""))[:950],
            "next_experiment":str(x.get("next_experiment",""))[:1200],
            "data_requirements":_texts(x.get("data_requirements",[]),"data_requirements",8),
            "evidence_status":x.get("evidence_status","inferred")
              if x.get("evidence_status") in ("verified","described","inferred","planned") else "inferred",
            "evidence_refs":_texts(x.get("evidence_refs",[]),"evidence_refs",24,330)})
    if {x["line_id"] for x in findings}!={x["id"] for x in profile["research_lines"]}:
        raise ValueError("画像分析没有覆盖全部研究主线")
    return {"positioning":str(value.get("positioning",""))[:1300],
        "method_capabilities":_texts(value.get("method_capabilities",[]),"method_capabilities",25),
        "line_insights":findings,
        "cross_line_opportunities":_texts(value.get("cross_line_opportunities",[]),"cross_line_opportunities",12,500),
        "evidence_gaps":_texts(value.get("evidence_gaps",[]),"evidence_gaps",12,550),
        "scope_cautions":_texts(value.get("scope_cautions",[]),"scope_cautions",10,550)}

def _validated(raw,allowed_refs=None):
    if not isinstance(raw,dict):raise ValueError("画像内容格式不正确")
    profile=_profile(raw.get("profile"))
    analysis=_analysis(raw.get("analysis"),profile)
    if allowed_refs is not None:
        for item in analysis["line_insights"]:
            if any(ref not in allowed_refs for ref in item["evidence_refs"]):
                raise ValueError("模型引用了数据库中不存在或受限的证据 ID")
            if item["evidence_status"]=="verified":
                # Titles alone do not verify method or experimental conclusions.
                item["evidence_status"]="described"
    return profile,analysis

def draft_view(row):
    return {"id":row.id,"source":row.source,"scope":row.scope,
        "status":row.status,"base_version":row.base_version,
        "revision":row.revision,"profile":unpack(row.profile_json,{}),
        "analysis":unpack(row.analysis_json,{}),
        "provenance":unpack(row.provenance_json,[]),
        "note":row.note,"model":row.model,
        "applied_version":row.applied_version,
        "created_at":row.created_at.isoformat() if row.created_at else None}

def run_view(x):
    return {"id":x.id,"status":x.status,"error":x.error,
        "model":x.model,"draft_id":x.draft_id,
        "input_tokens":x.input_tokens,"output_tokens":x.output_tokens,
        "created_at":x.created_at.isoformat() if x.created_at else None}

def list_studio(db):
    return {"profile_version":current_profile_version(db),
        "evidence":safe_overview(evidence_inventory(db)),
        "drafts":[draft_view(x) for x in db.scalars(
            select(ResearchProfileDraft).order_by(
                ResearchProfileDraft.created_at.desc()).limit(25)).all()],
        "runs":[run_view(x) for x in db.scalars(select(ProfileSynthesisRun).order_by(
            ProfileSynthesisRun.created_at.desc()).limit(20)).all()],
        "model_configured":bool(db.get(ModelCredential,"deepseek") and
           db.get(ModelCredential,"deepseek").encrypted_key),
        "note":"示例基于对话整理，个人与合作课题不能自动认定为团队核验成果。发布画像需管理员确认。"}

def new_draft(db,raw,source="curated_example",scope="personal_collaborative",
              provenance=None,note="",model="",base_version=None,draft_id=None):
    profile,analysis=_validated(raw)
    if scope not in ("personal_collaborative","team"):raise ValueError("画像范围无效")
    row=ResearchProfileDraft(
        id=draft_id or "prof_"+uuid.uuid4().hex,
        source=source,scope=scope,
        base_version=current_profile_version(db) if base_version is None else base_version,
        profile_json=pack(profile),analysis_json=pack(analysis),
        provenance_json=pack(provenance or []),
        note=note[:1000],model=model,status="draft")
    db.add(row)
    db.flush()
    db.add(ResearchProfileDraftRevision(draft_id=row.id,revision=1,
        profile_json=row.profile_json,actor_id="system"))
    db.commit()
    return row

def initialize_database_draft(factory):
    """Disavow the chat-derived seed and install DB-only, evidence-bound draft.

    Idempotent on every restart, no alteration of the official team profile.
    This is explicitly an evidence-linked deterministic prototype, not LLM.
    """
    with factory() as db:
        removed=0
        old=db.scalars(select(ResearchProfileDraft).where(
            ResearchProfileDraft.source=="curated_example",
            ResearchProfileDraft.status=="draft")).all()
        for row in old:
            row.status="discarded"
            row.note=("已作废：此前草稿从聊天记录生成，不符合仅依据现有数据库的要求。"
                      "禁止作为LLM画像证据；仅保留内部审计。")
            row.updated_at=now()
            removed+=1
        db.flush()
        inventory=evidence_inventory(db)
        # A stable ID prevents duplicate drafts when free Render restarts.
        material=pack({
            "official_profile":inventory["profile"],
            "achievement_ids":[x["ref"] for x in inventory["team_achievements"]],
            "data_ids":[x["ref"] for x in inventory["datasets"]],
            "paper_ids":[x["ref"] for x in inventory["approved_papers"]],
            "verified_relations":inventory["confirmed_relations"]
        })
        ident="prof_db_"+hashlib.sha256(material.encode()).hexdigest()[:28]
        existed=db.get(ResearchProfileDraft,ident)
        if not existed:
            draft,refs=database_draft(inventory)
            existing_refs=["profiles:1"] if inventory["profile"] else []
            new_draft(db,draft,source="database_snapshot",scope="team",
                      provenance=existing_refs+refs,
                      note=("本草稿仅由现有 PostgreSQL 表构造，未使用聊天记录或LLM。"
                            "技术瓶颈源于已有正式画像，关联为可解释初筛，不代表成果验证。"),
                      model="",draft_id=ident)
        else:
            db.commit()
        return {"new":not bool(existed),"discarded_chat_drafts":removed,
            "id":ident,"counts":inventory["counts"]}


def bootstrap_from_env(factory):
    text=os.getenv("RESEARCH_PROFILE_BOOTSTRAP_B64","").strip()
    if not text:return None
    try:
        raw=base64.b64decode(text.encode(),validate=True)
        if len(raw)>35000:raise ValueError("Profile bootstrap exceeds metadata limit")
        data=json.loads(raw.decode("utf-8"))
        fingerprint="prof_seed_"+hashlib.sha256(raw).hexdigest()[:24]
        with factory() as db:
            existing=db.get(ResearchProfileDraft,fingerprint)
            if existing:return {"imported":False,"id":fingerprint}
            row=new_draft(db,data,source="curated_example",
               scope="personal_collaborative",draft_id=fingerprint,
               note="基于既往研究讨论的初始结构化示例，尚未确认是否代表团队正式研究主线。",
               provenance=["既往对话中陈述或讨论的研究项目（未经独立成果核验）",
                           "CUSP 数据资产仅单独登记元信息，没有自动认定为个人已获得数据"])
            return {"imported":True,"id":row.id}
    except (ValueError,UnicodeError,TypeError) as exc:
        raise ValueError("Initial research portrait bootstrap invalid") from exc

def _snapshot(db,note):
    """Strictly live PostgreSQL records. Never include historical chat drafts."""
    inventory=evidence_inventory(db)
    # Explicit, stable IDs allow the model and backend to prove provenance.
    return {
        "source_policy":"strict_postgresql_only",
        "existing_official_profile":inventory["profile"],
        "verified_team_outputs":inventory["team_achievements"],
        "non_restricted_data_metadata":inventory["datasets"],
        "human_approved_papers":inventory["approved_papers"],
        "confirmed_line_relations":inventory["confirmed_relations"],
        "inventory_counts":inventory["counts"],
        "dataset_categories":inventory["dataset_categories"],
        # Admin review notes are optional requirements, NOT independent evidence.
        "reviewer_instructions_not_evidence":note[:1000],
        "evidence_note":"只允许以上现有数据库记录。禁止使用聊天记录、被撤回的初始化草稿、或臆造的数据字段和团队成果。",
        "output_scope":"team_draft_needs_admin_review"
    }


def start_generation(db,note="",actor_id=""):
    if not load_key(db):
        raise ValueError("请先在 AI 选题实验台配置 DeepSeek Key")
    if db.scalar(select(ProfileSynthesisRun.id).where(
        ProfileSynthesisRun.status.in_(["queued","running"])).limit(1)):
        raise ValueError("已有画像生成任务在运行")
    cfg=db.get(ModelCredential,"deepseek")
    snapshot=_snapshot(db,note)
    item=ProfileSynthesisRun(id=str(uuid.uuid4()),status="queued",
        snapshot_json=pack(snapshot),model=cfg.reason_model)
    db.add(item)
    add_audit(db,"profile_synthesis.queued",actor_id,item.id)
    db.commit()
    return item

def execute_generation(factory,run_id,client=None):
    with factory() as db:
        result=db.execute(update(ProfileSynthesisRun).where(
            ProfileSynthesisRun.id==run_id,ProfileSynthesisRun.status=="queued"
        ).values(status="running",updated_at=now()))
        db.commit()
        if not result.rowcount:return False
    try:
        with factory() as db:
            row=db.get(ProfileSynthesisRun,run_id)
            context=unpack(row.snapshot_json,{})
            key=load_key(db)
            if not key:raise ValueError("DeepSeek Key 已移除，请重新配置")
            model=row.model
            base_version=current_profile_version(db)
        system=("你是数据库证据驱动的科研画像分析助手。所有事实必须来自本次提供的"
                "PostgreSQL记录。不得使用任何历史聊天、先前个人案例或工作台之外的项目记忆。"
                "团队成果为工作台已核验条目，但文献标题不等于已证明具体方法结论。"
                "主线必须给出 evidence_refs（输入提供的 ref ID），并明确证据不足之处。"
                "只能根据现有元信息提出假设，不能推断原始数据实际可用。"
                "必须返回 JSON object，字段必须遵守以下可复用 Skill：\n"+
                load_skills(("research_profile",)))
        result,usage=request_json(key,model,system,context,client=client,max_tokens=4200)
        allowed_refs={x["ref"] for block in ("verified_team_outputs",
                     "non_restricted_data_metadata","human_approved_papers")
                     for x in context.get(block,[])}
        profile,analysis=_validated(result,allowed_refs=allowed_refs)
        with factory() as db:
            run=db.get(ProfileSynthesisRun,run_id)
            if run.status!="running":return False
            draft=new_draft(db,{"profile":profile,"analysis":analysis},
                source="llm",scope="team",base_version=base_version,model=model,
                note="严格基于 PostgreSQL 中的团队成果、正式画像、CUSP 属性目录和人工审核论文生成；需核查方法推断与研究归属。",
                provenance=["profiles:1"]+[ref for item in analysis["line_insights"]
                            for ref in item["evidence_refs"]],
                )
            run.draft_id=draft.id;run.status="completed";run.error=""
            run.input_tokens=usage["input_tokens"]
            run.output_tokens=usage["output_tokens"];run.updated_at=now()
            db.commit()
        return True
    except (ModelCallError,ValueError,TypeError,KeyError) as exc:
        # Error class names and guarded messages only; not prompts or secrets.
        with factory() as db:
            run=db.get(ProfileSynthesisRun,run_id)
            if run and run.status=="running":
                run.status="failed";run.error=str(exc)[:250];run.updated_at=now()
                db.commit()
        return False
    except Exception as exc:
        with factory() as db:
            run=db.get(ProfileSynthesisRun,run_id)
            if run and run.status=="running":
                run.status="failed"
                run.error="画像生成内部故障："+type(exc).__name__
                run.updated_at=now();db.commit()
        return False

def update_draft(db,ident,profile,expected_revision,actor):
    row=db.get(ResearchProfileDraft,ident)
    if not row or row.status not in ("draft","applied"):
        raise ValueError("只有有效画像草稿可以修改")
    if row.revision!=expected_revision:raise ValueError("草稿已被其他成员修改，请刷新")
    validated=_profile(profile)
    row.profile_json=pack(validated)
    row.revision+=1;row.updated_at=now()
    row.status="draft";row.applied_version=None
    db.add(ResearchProfileDraftRevision(draft_id=ident,
        revision=row.revision,profile_json=row.profile_json,
        actor_id=actor or ""))
    add_audit(db,"research_profile.draft_updated",actor,ident,
              "revision="+str(row.revision))
    db.commit()
    return draft_view(row)

def apply_draft(db,ident,expected_version,actor):
    row=db.get(ResearchProfileDraft,ident)
    if not row or row.status!="draft":raise ValueError("草稿不存在或已处理")
    actual=current_profile_version(db)
    if expected_version!=actual or row.base_version!=actual:
        raise ValueError("正式画像已经变化；请基于最新版本重新生成或检查后再应用")
    profile=_profile(unpack(row.profile_json))
    version=save_team_profile(db,profile,actor,expected_version=expected_version)
    row.status="applied";row.applied_version=version;row.updated_at=now()
    add_audit(db,"research_profile.draft_applied",actor,ident,
              "profile_version="+str(version))
    db.commit()
    return {"id":ident,"profile_version":version,"status":"applied"}

def discard_draft(db,ident,actor):
    row=db.get(ResearchProfileDraft,ident)
    if not row or row.status!="draft":raise ValueError("草稿不存在或已处理")
    row.status="discarded";row.updated_at=now()
    add_audit(db,"research_profile.draft_discarded",actor,ident)
    db.commit()
    return {"id":ident,"status":"discarded"}
