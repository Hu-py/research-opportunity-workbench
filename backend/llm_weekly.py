"""LLM-synthesized weekly research intelligence brief from persisted evidence."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from research_workbench.core import get_profile
from backend.discovery import PaperCandidate, DiscoveryRun
from backend.preanalysis import PaperPreanalysis
from backend.ai_lab import AIOpportunity
from backend.discovery_links import ResearchLineRelation
from backend.interests import ResearchInterest, decode as decode_interest
from backend.model_vault import ModelCredential, load_key
from backend.model_gateway import request_json
from backend.skill_loader import load_skills

SYSTEM="""你是跨学科科研团队的首席研究情报分析师。根据提供的本周数据库记录撰写中文科研周报。
必须区分已发表论文事实、摘要级理解、LLM提出的假设和人工确认关系。不得把待审核候选写成团队已采用成果。
不得虚构论文、DOI、来源等级、实验结果、数据可用性或创新性。指出本周证据不足和下周最值得推进的动作。
规划学与计算机前沿应同时覆盖；计算机论文可以通过方法机制迁移关联规划问题。
仅输出 JSON。"""

def generate_weekly_brief(factory, days=7, client=None):
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,min(int(days),30)))
    with factory() as db:
        cfg=db.get(ModelCredential,"deepseek")
        key=load_key(db) if cfg and cfg.encrypted_key else None
        if not key: return {"status":"skipped","reason":"DeepSeek Key 或 MODEL_VAULT_KEY 未配置","markdown":""}
        profile=get_profile(db) or {}
        papers=db.scalars(select(PaperCandidate).where(PaperCandidate.last_seen>=cutoff).order_by(PaperCandidate.score.desc()).limit(50)).all()
        ids=[x.id for x in papers]
        analyses={x.candidate_id:x for x in db.scalars(select(PaperPreanalysis).where(PaperPreanalysis.candidate_id.in_(ids))).all()} if ids else {}
        cards=db.scalars(select(AIOpportunity).order_by(AIOpportunity.created_at.desc()).limit(15)).all()
        relations=db.scalars(select(ResearchLineRelation).order_by(ResearchLineRelation.updated_at.desc()).limit(40)).all()
        interests=db.scalars(select(ResearchInterest).where(ResearchInterest.enabled.is_(True)).order_by(ResearchInterest.created_at.desc()).limit(20)).all()
        line_names={x.get("id"):x.get("name") for x in profile.get("research_lines",[]) if isinstance(x,dict)}
        paper_rows=[]
        for p in papers:
            analysis=analyses.get(p.id)
            try: detail=json.loads(analysis.analysis_json or "{}") if analysis else {}
            except (ValueError,TypeError): detail={}
            paper_rows.append({"id":p.paper_id,"title":p.title,"abstract":(p.abstract or "")[:1200],
                "venue":p.venue,"published":p.published,"doi":p.doi,"url":p.url,
                "research_line":line_names.get(p.line_id,p.line_id),"llm_relevance_score":analysis.fit_score if analysis else None,
                "llm_preanalysis":detail,"human_review_status":p.status})
        card_rows=[{"title":x.title,"question":x.question,"method":x.method,
            "why_now":x.why_now,"status":x.status,"critic":json.loads(x.critic_json or "{}")} for x in cards]
        relation_rows=[{"line":line_names.get(x.line_id,x.line_id),"kind":x.kind,
            "label":x.label,"status":x.status,"reason":x.reason} for x in relations]
        interest_rows=[{"title":x.title,"focus":x.focus,"problem":x.problem,
            "keywords":decode_interest(x.keywords_json),"venues":decode_interest(x.venues_json),
            "last_status":x.last_status,"last_new":x.last_new} for x in interests]
        model=cfg.reason_model or "deepseek-v4-pro"
    payload={"reporting_window_days":days,"team_goals":profile.get("goals",""),
        "research_lines":profile.get("research_lines",[]),"papers":paper_rows,
        "ai_opportunities":card_rows,"research_data_relations":relation_rows,
        "manual_interests":interest_rows,
        "task":"写一份有判断、有证据、有优先级的周报。分为本周重要论文（规划/城市研究与计算机前沿）、方法迁移启发、与团队数据的潜在结合、候选选题进展、证据缺口、下周行动。只挑重要内容，不要机械罗列全部论文。每个论文引用必须使用输入中的 URL 和标题。",
        "required_json":{"executive_summary":"","planning_research_highlights":[""],
            "computer_science_frontier":[""],"method_transfer_opportunities":[""],
            "team_data_connections":[""],"topic_progress":[""],
            "evidence_gaps":[""],"next_week_actions":[""],
            "sources":[{"paper_id":"","title":"","url":"","why_included":""}]}}
    system=SYSTEM+"\\n\\n执行技能：\\n"+load_skills(("literature_discovery","paper_reader","idea_discovery","idea_critic"))
    result,usage=request_json(key,model,system,payload,client=client,max_tokens=4200)
    sections=[("# 科研机会周报",""),("## 执行摘要",result.get("executive_summary","")),
        ("## 规划学与城市研究进展","\n".join("- "+str(x) for x in result.get("planning_research_highlights",[]))),
        ("## 计算机前沿","\n".join("- "+str(x) for x in result.get("computer_science_frontier",[]))),
        ("## 方法迁移机会","\n".join("- "+str(x) for x in result.get("method_transfer_opportunities",[]))),
        ("## 与团队数据的潜在结合","\n".join("- "+str(x) for x in result.get("team_data_connections",[]))),
        ("## 选题进展","\n".join("- "+str(x) for x in result.get("topic_progress",[]))),
        ("## 证据缺口","\n".join("- "+str(x) for x in result.get("evidence_gaps",[]))),
        ("## 下周行动","\n".join("- "+str(x) for x in result.get("next_week_actions",[])))]
    markdown="\n\n".join(title+"\n"+body for title,body in sections if body)
    sources=result.get("sources",[])
    if sources:
        markdown+="\n\n## 参考文献\n"+ "\n".join("- ["+str(x.get("title",""))+"]("+str(x.get("url",""))+") — "+str(x.get("why_included","")) for x in sources if isinstance(x,dict) and str(x.get("url","")).startswith("https://"))
    markdown+="\n\n> 本报告由 LLM 基于工作台已存储的文献元数据、摘要级预分析、团队画像和非受限数据属性生成。未读取论文全文或原始数据；所有新选题均为待核验假设。"
    return {"status":"completed","markdown":markdown,"model":model,
        "input_tokens":usage["input_tokens"],"output_tokens":usage["output_tokens"],
        "papers_considered":len(paper_rows),"ideas_considered":len(card_rows)}
