"""Run a local/offline Research Atlas L0/L1 scientific signal preview.

Input is an evidence snapshot JSON with 'papers' records and optional
'registered_sources' rows, not arbitrary scraped text. No database changes or
automatic publication. A --proposal file permits free deterministic validation.
Without it a real model call requires an explicit DeepSeek API key.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.atlas_intelligence.runner import (
    generate_signal_preview,
    prepare_paper_snapshot,
    SYSTEM_GUIDANCE,
)
from backend.atlas_intelligence.signals import build_research_brief, render_research_brief


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a review-only three-source science brief")
    parser.add_argument("--input", required=True, help="JSON with papers and registered_sources")
    parser.add_argument("--proposal", help="Existing model proposal JSON; does not call a provider")
    parser.add_argument("--period", default="", help="e.g. 2026-W46")
    parser.add_argument("--out", required=True, help="Output Markdown path (keep team data private)")
    parser.add_argument("--model", default="deepseek-chat", help="Model for explicitly requested paid run")
    args = parser.parse_args(argv)
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(source, dict) or not isinstance(source.get("papers"), list):
        raise SystemExit("input must contain a list named papers")
    papers = source["papers"]
    if source.get("registered_sources"):
        papers, coverage = prepare_paper_snapshot(
            papers, source["registered_sources"], per_group_limit=24
        )
    else:
        if any(not isinstance(p, dict) or not p.get("source_groups") for p in papers):
            raise SystemExit("papers need source_groups when registered_sources are omitted")
        coverage = {"candidate_count": len(papers), "input": "preclassified snapshot"}
    if args.proposal:
        proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))
        report = build_research_brief(papers, proposal, period=args.period, coverage=coverage)
    else:
        key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not key:
            raise SystemExit("DEEPSEEK_API_KEY required without --proposal (not committed or printed)")
        from backend.model_gateway import request_json

        def call(payload):
            output, usage = request_json(
                key, args.model, SYSTEM_GUIDANCE, payload, max_tokens=3500
            )
            print("Model usage:", json.dumps(usage, ensure_ascii=False))
            return output

        report = generate_signal_preview(
            papers, call, period=args.period, coverage=coverage
        )
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_research_brief(report), encoding="utf-8")
    destination.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Saved unreviewed draft:", destination, "signals:", len(report["signals"]))


if __name__ == "__main__":
    main()
