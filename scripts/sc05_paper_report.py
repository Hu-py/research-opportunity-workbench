"""Explicitly paid, one-PDF -> full SC05 research report CLI.

Example (from a trusted machine, without exposing API key in shell history):
  python -m scripts.sc05_paper_report --pdf ./paper.pdf --output ./sc05_results --ack-model-spend

Uses SC04_DEEPSEEK_API_KEY from environment (or DEEPSEEK_API_KEY).
Never logs or serializes the credential. No app login bypass or Render startup
trigger; the operator must run the CLI and consent to its charged requests.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from backend.sc05_paper_only import run_paper


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="Research Atlas SC05: one-paper research diagnosis report")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-calls",type=int,default=18)
    parser.add_argument("--ack-model-spend",action="store_true",
                        help="Explicitly consent to paid DeepSeek requests")
    args=parser.parse_args(argv)
    if not args.ack_model_spend:
        parser.error("Real model execution requires --ack-model-spend")
    if not 6<=args.max_calls<=40:
        parser.error("--max-calls must be in 6..40")
    if not args.pdf.is_file() or args.pdf.suffix.lower()!=".pdf":
        parser.error("--pdf must point to a local PDF file")
    api_key=(os.getenv("SC04_DEEPSEEK_API_KEY") or
             os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        parser.error("Set SC04_DEEPSEEK_API_KEY or DEEPSEEK_API_KEY in the host environment")
    out=args.output
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    report,record=run_paper(args.pdf,api_key,max_calls=args.max_calls)
    rid=record["source"]["sha256"][:12]
    md=out/("SC05_"+rid+"_report.md")
    audit=out/("SC05_"+rid+"_audit.json")
    md.write_text(report,encoding="utf-8")
    audit.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    try:
        md.chmod(0o600);audit.chmod(0o600)
    except OSError:
        pass
    print(json.dumps({
        "status":"completed","report":str(md),"audit":str(audit),
        "model_calls":len(record["usage"]),
        "input_tokens":sum(x["input_tokens"] for x in record["usage"]),
        "output_tokens":sum(x["output_tokens"] for x in record["usage"]),
        "fact_count":len(record["snapshot"]["observations"]),
        "diagnosis_count":len(record["diagnosis"]["diagnoses"]),
        "literature_count":len(record["external_papers"]),
        "candidate_count":len(record["routes"]),
        "scientific_status":"model_draft_not_independently_validated",
    },ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
