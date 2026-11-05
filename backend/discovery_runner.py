"""Bounded OpenAlex candidate ingestion on the existing free FastAPI instance."""
from datetime import date,timedelta
import logging
import os
from sqlalchemy import select
from backend.openalex_errors import safe_openalex_error
from backend.academic_sources import AcademicSource,resolved_source_ids_by_channel
from research_workbench.core import get_profile,normalize_paper,query_openalex
from backend.discovery import (
    DiscoveryRun,PaperCandidate,candidate_id,strategies,reads,dumps,now,
)

def score_paper(line,paper,mode,source=None):
    title=(paper["title"] or "").casefold()
    text=title+" "+(paper["abstract"] or "").casefold()
    terms=[x.strip().casefold() for x in line.get("keywords",[])
           if isinstance(x,str) and len(x.strip())>=3][:16]
    hits=[x for x in terms if x in title]
    context=[x for x in terms if x in text]
    label=(source.rank_label or "").upper() if source else ""
    source_boost={"A":10,"B":8,"C":5,"核心":9,"重点":6,"补充":3,"观察":1}.get(label,2)
    if source and source.kind=="conference":
        # CCF conference grades cover Full/Regular papers, not every format.
        source_boost=min(source_boost,7)
    score=min(100,36+10*min(3,len(hits))+5*min(4,len(context))+
              (8 if mode=="direct" else 4)+source_boost+
              (5 if paper["doi"] else 0)+(2 if paper["abstract"] else 0))
    why=["问题检索" if mode=="direct" else "方法迁移检索"]
    if source:why.append("白名单来源："+source.name+"（"+source.rank_label+"）")
    if source and source.kind=="conference" and "CCF" in (source.ranking_system or ""):
        why.append("会议等级需按 Full/Regular 论文范围核验；单篇论文类型仍待人工确认")
    if hits:why.append("标题命中："+", ".join(hits[:3]))
    if context:why.append("文本相关："+", ".join(context[:4]))
    if not paper["abstract"]:why.append("摘要缺失")
    why.append("来源等级仅作检索先验；匹配分数不证明单篇论文质量、创新性或数据可行性")
    return score,"；".join(why)

def execute_discovery(factory,run_id,client=None):
    with factory() as db:
        run=db.get(DiscoveryRun,run_id)
        if not run or run.status!="queued":return
        profile=get_profile(db)
        lines={x["id"]:x for x in (profile or {}).get("research_lines",[])}
        settings={x["line_id"]:x for x in strategies(db,profile)}
        selected=[i for i in reads(run.line_ids_json) if i in lines and i in settings]
        if not selected:
            run.status="failed";run.errors_json=dumps(["研究主线已不存在或画像缺失"])
            run.finished_at=now();db.commit();return
        channel_ids=resolved_source_ids_by_channel(db)
        source_rows=db.scalars(select(AcademicSource).where(
            AcademicSource.enabled.is_(True),
            AcademicSource.resolution_status=="resolved")).all()
        source_by_id={x.openalex_source_id.rstrip("/").rsplit("/",1)[-1]:x
                      for x in source_rows if x.openalex_source_id}
        if not channel_ids["direct"] and not channel_ids["method"]:
            run.status="failed"
            run.errors_json=dumps(["学术来源管理中尚无已启用且已核验的 OpenAlex 来源。请先在 Academic Source Registry 执行批量核验；未退回全库检索。"])
            run.finished_at=now();db.commit();return
        run.status="running";db.commit()
    logging.getLogger("uvicorn.error").info(
        "Academic source filter: direct=%d method=%d",
        len(channel_ids["direct"]),len(channel_ids["method"]))
    errors=[]
    for line_id in selected:
        line=lines[line_id]
        config=settings[line_id]
        requests=[(x,"direct") for x in config["direct_queries"][:2]]
        requests +=[(x,"method") for x in config["method_queries"][:2]]
        for query,mode in requests:
            query_source_ids=channel_ids.get(mode,[])
            if not query_source_ids:
                errors.append(line_id+" | "+mode+" | No enabled and verified sources")
                with factory() as db:
                    run=db.get(DiscoveryRun,run_id)
                    run.queries+=1;run.errors_json=dumps(errors);db.commit()
                continue
            try:
                results=query_openalex(query,(date.today()-timedelta(
                    days=config["lookback_days"])).isoformat(),
                    limit=config["per_query"],client=client,source_ids=query_source_ids)
                if not isinstance(results,list):raise ValueError("Unexpected paper search response")
                with factory() as db:
                    run=db.get(DiscoveryRun,run_id)
                    run.queries+=1
                    excluded=[x.lower() for x in (profile or {}).get("excluded_terms",[])
                              if isinstance(x,str) and x.strip()]
                    for work in results[:config["per_query"]]:
                        if not isinstance(work,dict):continue
                        paper=normalize_paper(work)
                        if not paper["title"] or not paper["url"].startswith("https://"):
                            continue
                        if any(x in (paper["title"]+" "+paper["abstract"]).lower()
                               for x in excluded):continue
                        raw_source=(work.get("primary_location") or {}).get("source") or {}
                        source_ident=str(raw_source.get("id") or "").rstrip("/").rsplit("/",1)[-1]
                        source=source_by_id.get(source_ident)
                        if source is None:continue
                        run.scanned+=1
                        rank,reason=score_paper(line,paper,mode,source)
                        ident=candidate_id(line_id,paper["id"])
                        existing=db.get(PaperCandidate,ident)
                        if not existing:
                            db.add(PaperCandidate(id=ident,line_id=line_id,
                                paper_id=paper["id"],title=paper["title"][:1500],
                                abstract=paper["abstract"][:6000],doi=paper["doi"],
                                url=paper["url"][:1600],published=paper["published"],
                                venue=paper["venue"][:300],
                                score=rank,score_reason=reason,match_type=mode,
                                matched_queries_json=dumps([query]),status="pending"))
                            run.new_candidates+=1
                        else:
                            matched=reads(existing.matched_queries_json)
                            if query not in matched:matched.append(query)
                            existing.matched_queries_json=dumps(matched[:12])
                            existing.last_seen=now()
                            if rank>existing.score:
                                existing.score=rank;existing.score_reason=reason
                                existing.match_type=mode
                            run.updated_candidates+=1
                            # Do not reset manual decisions on repeated search.
                    db.commit()
            except Exception as exc:
                # httpx.HTTPStatusError's string representation contains the
                # full request URL, potentially including OPENALEX_API_KEY.
                # Never persist or log str(exc), the URL, or private query text.
                message=safe_openalex_error(exc,bool(os.getenv("OPENALEX_API_KEY")))
                errors.append((line_id+" | "+mode+" | "+message)[:260])
                logging.getLogger("uvicorn.error").warning(
                    "Paper discovery failed: run=%s line=%s mode=%s reason=%s",
                    run_id,line_id,mode,message,
                )
                with factory() as db:
                    run=db.get(DiscoveryRun,run_id)
                    run.queries+=1;run.errors_json=dumps(errors);db.commit()
    with factory() as db:
        run=db.get(DiscoveryRun,run_id)
        run.errors_json=dumps(errors)
        run.status="failed" if errors and not run.scanned else (
            "partial" if errors else "completed")
        run.finished_at=now()
        logging.getLogger("uvicorn.error").info(
            "Paper discovery finished: run=%s status=%s queries=%d scanned=%d new=%d errors=%d",
            run.id,run.status,run.queries,run.scanned,run.new_candidates,len(errors),
        )
        db.commit()
