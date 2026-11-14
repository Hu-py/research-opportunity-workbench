"""Manually collect a public Research Atlas A/B/C evidence snapshot from OpenAlex.

Run from repository root after 'pip install -e .'. The result is a *sample*,
not a field census or a scientific intelligence report. Nothing is published.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from backend.atlas_intelligence.collector import collect_three_sources
from backend.atlas_intelligence.sources import load_source_plan


def main(argv=None):
    p = argparse.ArgumentParser(description="Fetch independent A/B/C Research Atlas source evidence")
    p.add_argument("--source-plan", default=None)
    p.add_argument("--lookback-days", type=int, default=30)
    p.add_argument("--max-per-source", type=int, default=15)
    p.add_argument("--max-sources-per-group", type=int, default=None,
                   help="Optional trial cap; omitted scans all configured venues")
    p.add_argument("--today", default=None, help="ISO date for a reproducible window")
    p.add_argument("--out", required=True, help="Local output JSON; do not publish private watchlists")
    args = p.parse_args(argv)
    run_date = date.fromisoformat(args.today) if args.today else None
    plan = load_source_plan(args.source_plan)
    feed = collect_three_sources(
        plan=plan,
        today=run_date,
        lookback_days=args.lookback_days,
        max_per_source=args.max_per_source,
        max_sources_per_group=args.max_sources_per_group,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": feed["status"],
        "global_unique_papers": feed["coverage"]["global_unique_papers"],
        "per_group": feed["coverage"]["group_distinct_papers"],
        "failed_venue_counts": {
            group: len(entry["failed_sources"])
            for group, entry in feed["coverage"]["source_groups"].items()
        },
        "author_failures": len(feed["coverage"]["authors"]["failed"]),
        "output": str(out),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
