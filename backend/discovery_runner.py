"""Bounded OpenAlex candidate ingestion on the existing free FastAPI instance."""
from datetime import date,timedelta
import logging
import os
from backend.openalex_errors import safe_openalex_error
from research_workbench.core import get_profile,normalize_paper,query_openalex
from backend.discovery import (
    DiscoveryRun,PaperCandidate,candidate_id,strategies,reads,dumps,now,
)

def score_paper(line,paper,mode):
    title=(paper["title"] or "").lower()
    text=title+" "+(paper["abstract"] or "").lower()
    terms=[x.strip().lower() for x in line.get("keywords",[])
           if isinstance(x,str) and len(x.strip())>=3][:16]
    hits=[x for x in terms if x in title]
    context=[x for x in terms if x in text]
    score=min(100,40+10*min(3,len(hits))+5*min(4,len(context))+
              (8 if mode=="direct" else 4)+
              (5 if paper["doi"] else 0)+(2 if paper["abstract"] else 0))
    why=["问题检索" if mode=="direct" else "方法迁移检索"]
    if hits:why.append("标题命中："+", ".join(hits[:3]))
    if context:why.append("文本相关："+", ".join(context[:4]))
    if not paper["abstract"]:why.append("摘要缺失")
    why.append("分数仅表示检索匹配，不证明创新性与数据可行性")
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
        run.status="running";db.commit()
    errors=[]
    for line_id in selected:
        line=lines[line_id]
        config=settings[line_id]
        requests=[(x,"direct") for x in config["direct_queries"][:2]]
        requests +=[(x,"method") for x in config["method_queries"][:2]]
        for query,mode in requests:
            try:
                results=query_openalex(query,(date.today()-timedelta(
                    days=config["lookback_days"])).isoformat(),
                    limit=config["per_query"],client=client)
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
                        run.scanned+=1
                        rank,reason=score_paper(line,paper,mode)
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
