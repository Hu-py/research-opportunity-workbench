"""Bounded OpenAlex candidate ingestion on the existing free FastAPI instance."""
from datetime import date,timedelta
import logging
import os
from backend.openalex_errors import safe_openalex_error
from research_workbench.core import get_profile,normalize_paper,query_openalex
from backend.discovery import (
    DiscoveryRun,PaperCandidate,candidate_id,strategies,reads,dumps,now,
)
from backend.preanalysis import execute_preanalysis

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
    """Compatibility entrypoint; all discovery decisions are delegated to LLM."""
    from backend.llm_discovery import execute_discovery as execute_llm_discovery
    return execute_llm_discovery(factory,run_id,client=client)
