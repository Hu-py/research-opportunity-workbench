"""Re-run public metadata-only Research Atlas method-transfer experiment without API calls.

Usage:
    python scripts/atlas_urban_health_trial.py --out /tmp/urban-health-atlas
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.atlas_intelligence.urban_health_case import replay_file, render_case

FIXTURE = ROOT / "experiments/urban_health_graph_2026_11_14/real_metadata_sample.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    case = replay_file(args.fixture)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "research_case.json").write_text(
        json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "research_case.md").write_text(render_case(case), encoding="utf-8")
    print("offline-replay", case["paper_count"], "papers",
          case["signal_count"], "L1 draft signals", args.out)


if __name__ == "__main__":
    main()
