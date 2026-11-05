"""Provider integration smoke test, with public bibliographic data only.

Runs only in the opt-in scientific tool smoke GitHub Actions workflow.
No DeepSeek key, private data, or paid model requests are involved.
"""
from __future__ import annotations
from datetime import date
import json
from backend.scientific_tools import REGISTRY,ToolSession

def main():
    session=ToolSession(scopes=frozenset({"literature:read"}),max_calls=3)
    checks=[
        ("crossref.lookup_doi",{"doi":"10.1038/nature12373"}),
        ("openalex.search_papers",{"query":"graph neural networks urban research",
                                  "since":"2024-01-01","limit":2}),
        ("semantic_scholar.citation_neighbors",{"paper_id":"DOI:10.1038/nature12373",
                                                 "direction":"references","limit":1}),
    ]
    summary=[]
    for tool,args in checks:
        try:
            output=REGISTRY.invoke(tool,args,session=session)
            data=output["data"]
            if tool=="crossref.lookup_doi":
                count=int(bool(data.get("title") and data.get("doi")))
            else:
                count=len(data.get("papers") or [])
            summary.append({"tool":tool,"success":count>0,"item_count":count,
                            "provenance_present":bool(data.get("source_url"))})
        except Exception as exc:
            # Show sanitized error only; do not print response bodies or secrets.
            summary.append({"tool":tool,"success":False,
                            "error_type":type(exc).__name__,
                            "message":str(exc)[:140]})
    print(json.dumps({"type":"live_academic_provider_smoke",
                      "checks":summary},ensure_ascii=False))
    # Crossref & OpenAlex are required. Semantic Scholar may throttle unauthenticated tests.
    return 0 if all(x["success"] for x in summary[:2]) else 1

if __name__=="__main__":
    raise SystemExit(main())
