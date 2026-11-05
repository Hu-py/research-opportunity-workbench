"""LLM-generated, reviewable links between research lines and team evidence."""
from __future__ import annotations
import json
import logging
from sqlalchemy import select
from research_workbench.core import get_profile
from backend.cusp import CuspDataset, sensitive_level
from backend.repository import TeamAchievement
from backend.discovery_links import ResearchLineRelation, link_id, utcnow
from backend.model_vault import ModelCredential, load_key
from backend.model_gateway import request_json
from backend.skill_loader import load_skills

SYSTEM="""你是科研数据资产与研究问题匹配专家。判断必须基于研究构念、观测单位、字段、空间尺度、时间范围和方法验证需求，不能依赖关键词重合。数据登记不代表已获得、质量合格或允许使用。不要强行建立关联。所有关系只作为待人工确认建议。只输出 JSON。"""

def execute_llm_relations(factory, client=None):
    with factory() as db:
        profile=get_profile(db) or {}
        lines=profile.get("research_lines",[])
        cfg=db.get(ModelCredential,"deepseek")
        key=load_key(db) if cfg and cfg.encrypted_key else None
        if not key:
            return {"status":"skipped","reason":"DeepSeek API Key 未配置","created":0}
        datasets=db.scalars(select(CuspDataset).order_by(CuspDataset.name).limit(160)).all()
        datasets=[x for x in datasets if x.sensitivity in ("public","internal") and sensitive_level(x.name)!="restricted"]
        works=db.scalars(select(TeamAchievement).where(TeamAchievement.status=="verified").order_by(TeamAchievement.year.desc()).limit(80)).all()
        dataset_rows=[{"id":x.id,"name":x.name,"category":x.category,"format":x.format,
            "coverage":x.coverage[:160],"period":x.period[:120],"description":x.description[:300],
            "prior_research":x.prior_research[:180]} for x in datasets]
        work_rows=[{"id":x.id,"title":x.title,"year":x.year,"venue":x.venue,
            "tags":json.loads(x.tags_json or "[]")[:8]} for x in works]
        lines=[{"id":x.get("id"),"name":x.get("name"),"problem":x.get("problem"),
            "keywords":x.get("keywords",[])[:15],"methods":x.get("methods",[])[:12]} for x in lines]
        model=cfg.reason_model or "deepseek-v4-pro"
    created=0;updated=0;errors=[]
    for line in lines:
        payload={"research_line":line,"registered_nonrestricted_datasets":dataset_rows,
            "verified_team_achievements":work_rows,
            "task":"识别真正有研究价值的关系，最多返回12条。dataset和achievement均可不返回。优先说明字段/覆盖如何支撑问题，明确缺失信息。",
            "required_json":{"relations":[{"kind":"dataset|achievement","reference_id":"输入ID",
                "relevance_score":0,"relation_type":"direct_empirical|contextual|method_validation|weak",
                "reason":"具体的构念与证据联系","missing_checks":["需要核验的条件"]}]}}
        try:
            system=SYSTEM+"\\n\\n执行技能：\\n"+load_skills(("data_asset_mapping","research_profile"))
            result,_usage=request_json(key,model,system,payload,client=client,max_tokens=2400)
            relations=result.get("relations") if isinstance(result,dict) else None
            if not isinstance(relations,list):raise ValueError("LLM relation output invalid")
            allowed={"dataset":{x["id"] for x in dataset_rows},
                     "achievement":{x["id"] for x in work_rows}}
            with factory() as db:
                for item in relations[:12]:
                    if not isinstance(item,dict):continue
                    kind=item.get("kind");ref=item.get("reference_id")
                    score=item.get("relevance_score")
                    if kind not in allowed or ref not in allowed[kind]:continue
                    if isinstance(score,bool) or not isinstance(score,int) or not 0<=score<=100:continue
                    reason=item.get("reason")
                    if not isinstance(reason,str) or not reason.strip():continue
                    ident=link_id(line["id"],kind,ref)
                    row=db.get(ResearchLineRelation,ident)
                    if row and row.status in ("confirmed","rejected"):continue
                    if row is None:
                        label=next((x["name"] if kind=="dataset" else x["title"]
                            for x in (dataset_rows if kind=="dataset" else work_rows) if x["id"]==ref),"")
                        row=ResearchLineRelation(id=ident,line_id=line["id"],kind=kind,
                            reference_id=ref,label=label,score=score,reason=reason[:1800],status="suggested")
                        db.add(row);created+=1
                    else:
                        row.score=score;row.reason=reason[:1800];row.updated_at=utcnow();updated+=1
                db.commit()
        except Exception as exc:
            message=str(exc)[:180] if exc.__class__.__name__=="ModelCallError" else type(exc).__name__
            errors.append(line["id"]+": "+message)
            logging.getLogger("uvicorn.error").warning("LLM relation mapping failed: line=%s reason=%s",line["id"],message)
    return {"status":"partial" if errors else "completed","created":created,
            "updated":updated,"errors":errors[:5],"model":model}
