"""LLM-driven discovery: model plans queries and semantically assesses every result."""
from datetime import date, timedelta
import json, logging, os
from sqlalchemy import select
from backend.openalex_errors import safe_openalex_error
from research_workbench.core import get_profile, normalize_paper, query_openalex
from backend.discovery import DiscoveryRun, PaperCandidate, candidate_id, strategies, reads, dumps, now
from backend.preanalysis import execute_preanalysis
from backend.llm_discovery import plan_queries, assess_papers
from backend.model_vault import ModelCredential, load_key
from backend.cusp import CuspDataset
from backend.research_sources import ResearchSource, DIRECT_SOURCE_DOMAINS, METHOD_SOURCE_DOMAINS

def _assets(db):
    rows=db.scalars(select(CuspDataset).where(CuspDataset.sensitivity != "restricted").limit(40)).all()
    return [{
        "id":x.id,"name":x.name[:220],"category":x.category[:100],
        "format":x.format[:100],"coverage":x.coverage[:220],"period":x.period[:100],
        "description":x.description[:500],"prior_research":x.prior_research[:300],
    } for x in rows[:12]]

def _candidate_payload(paper, query, mode):
    return {"paper_id":paper["id"],"title":paper["title"][:900],
            "abstract":paper["abstract"][:3200],"venue":paper["venue"][:220],
            "published":paper["published"][:32],"doi":paper["doi"][:220],
            "url":paper["url"][:1000],"retrieval_query":query,"retrieval_mode":mode}

def _registered_source_ids(db):
    rows=db.scalars(select(ResearchSource).where(
        ResearchSource.enabled.is_(True),
        ResearchSource.resolution_status=="resolved",
        ResearchSource.openalex_source_id!="",
    )).all()
    direct=[x.openalex_source_id for x in rows if x.domain in DIRECT_SOURCE_DOMAINS]
    method=[x.openalex_source_id for x in rows if x.domain in METHOD_SOURCE_DOMAINS]
    return {"direct":list(dict.fromkeys(direct)),
            "method":list(dict.fromkeys(method)),
            "all":list(dict.fromkeys(direct+method))}
def execute_discovery(factory, run_id, client=None):
    with factory() as db:
        run=db.get(DiscoveryRun,run_id)
        if not run or run.status!="queued":return
        run_source=run.source
        profile=get_profile(db)
        lines={x["id"]:x for x in (profile or {}).get("research_lines",[])}
        settings={x["line_id"]:x for x in strategies(db,profile)}
        selected=[i for i in reads(run.line_ids_json) if i in lines and i in settings]
        credential=db.get(ModelCredential,"deepseek")
        key=load_key(db) if credential and credential.encrypted_key else None
        if not key:
            run.status="failed";run.errors_json=dumps(["LLM 文献发现未执行：请先配置 DeepSeek API Key"])
            run.finished_at=now();db.commit();return
        if run_source=="scheduled" and not credential.daily_enabled:
            run.status="failed";run.errors_json=dumps(["管理员尚未开启每日 AI 分析"])
            run.finished_at=now();db.commit();return
        model=(credential.reason_model or "deepseek-v4-pro")
        fast=(credential.fast_model or "deepseek-flash")
        assets=_assets(db)
        registered_sources=_registered_source_ids(db)
        run.status="running";db.commit()
    errors=[];all_seen=0
    for line_id in selected:
        line=lines[line_id];config=settings[line_id]
        try:
            # LLM creates fresh, diverse queries from the research problem and data context.
            with factory() as db:
                previous=db.scalars(select(PaperCandidate).where(
                    PaperCandidate.line_id==line_id
                ).order_by(PaperCandidate.first_seen.desc()).limit(60)).all()
                prior=[q for row in previous for q in reads(row.matched_queries_json)]
            plan,plan_usage=plan_queries(
                key,model,line,assets,prior_queries=list(dict.fromkeys(prior)),
                search_preferences=config,client=client
            )
            query_results=[];seen=set()
            for item in plan["queries"]:
                with factory() as db:
                    run=db.get(DiscoveryRun,run_id);run.queries+=1;db.commit()
                source_mode=item["mode"]
                source_ids=(registered_sources["direct"] if source_mode=="direct"
                            else registered_sources["method"] if source_mode=="method"
                            else registered_sources["all"])
                if not source_ids:
                    errors.append(line_id+" | Academic Source Registry 缺少已解析的启用来源，已跳过该类检索；请先解析期刊/会议来源 ID。")
                    continue
                results=query_openalex(
                    item["query"],(date.today()-timedelta(days=config["lookback_days"])).isoformat(),
                    limit=min(12,max(1,config["per_query"])),client=client,
                    source_ids=source_ids or None
                )
                for work in results if isinstance(results,list) else []:
                    if not isinstance(work,dict):continue
                    paper=normalize_paper(work)
                    if not paper["title"] or not paper["url"].startswith("https://"):continue
                    if paper["id"] in seen:continue
                    seen.add(paper["id"])
                    query_results.append(_candidate_payload(paper,item["query"],item["mode"]))
            all_seen+=len(query_results)
            # LLM semantic evaluation replaces keyword overlap, hard-coded score and exclusion rules.
            assessments,usage=assess_papers(
                key,fast,line,assets,query_results[:30],client=client
            )
            by_id={x["paper_id"]:x for x in assessments}
            with factory() as db:
                run=db.get(DiscoveryRun,run_id)
                run.scanned+=len(query_results)
                eligible_results=[item for item in query_results[:30]
                                  if by_id[item["paper_id"]]["relevance_score"]>=config["min_score"]]
                for item in eligible_results:
                    assessment=by_id[item["paper_id"]]
                    ident=candidate_id(line_id,item["paper_id"])
                    existing=db.get(PaperCandidate,ident)
                    query=item["retrieval_query"]
                    score=assessment["relevance_score"]
                    reason=assessment["why_relevant"]+"；类型："+assessment["relevance_type"]+"；证据："+assessment["evidence_confidence"]
                    if existing is None:
                        db.add(PaperCandidate(
                            id=ident,line_id=line_id,paper_id=item["paper_id"],
                            title=item["title"],abstract=item["abstract"],doi=item["doi"],
                            url=item["url"],published=item["published"],venue=item["venue"],
                            score=score,score_reason=reason,
                            match_type="method" if assessment["relevance_type"]=="method_transfer" else "direct",
                            matched_queries_json=dumps([query]),status="pending"
                        ))
                        run.new_candidates+=1
                    else:
                        matched=reads(existing.matched_queries_json)
                        if query not in matched:matched.append(query)
                        existing.matched_queries_json=dumps(matched[:12])
                        existing.last_seen=now()
                        # Preserve human decisions; refresh only semantic metadata on unreviewed records.
                        if existing.status=="pending":
                            existing.score=score;existing.score_reason=reason
                            existing.match_type="method" if assessment["relevance_type"]=="method_transfer" else "direct"
                        run.updated_candidates+=1
                db.commit()
            # Store complete model judgement alongside preanalysis payload to keep the existing UI compatible.
            from backend.preanalysis import PaperPreanalysis
            with factory() as db:
                for item in eligible_results:
                    assessment=by_id[item["paper_id"]]
                    ident=candidate_id(line_id,item["paper_id"])
                    row=db.get(PaperPreanalysis,ident)
                    if row is None:
                        row=PaperPreanalysis(candidate_id=ident,paper_id=item["paper_id"],
                            abstract_hash="",model=fast)
                        db.add(row)
                    row.model=fast;row.status="completed"
                    row.fit_score=assessment["relevance_score"]
                    row.priority=assessment["priority"]
                    row.analysis_json=dumps(assessment)
                    row.error="";row.updated_at=now()
                db.commit()
        except Exception as exc:
            message=safe_openalex_error(exc,bool(os.getenv("OPENALEX_API_KEY")))
            errors.append(line_id+" | "+message)
            logging.getLogger("uvicorn.error").warning(
                "LLM literature discovery failed: run=%s line=%s reason=%s",run_id,line_id,message
            )
    with factory() as db:
        run=db.get(DiscoveryRun,run_id)
        run.errors_json=dumps(errors)
        run.status="failed" if errors and not run.scanned else ("partial" if errors else "completed")
        run.finished_at=now()
        db.commit()
    # LLM pre-analysis is now already included in the semantic assessment. Keep a bounded
    # fallback for legacy pending records only; this does not use keyword relevance.
    if all_seen==0:
        try: execute_preanalysis(factory,limit=3,require_daily_opt_in=(run_source=="scheduled"))
        except Exception: logging.getLogger("uvicorn.error").warning("Legacy preanalysis failed")
