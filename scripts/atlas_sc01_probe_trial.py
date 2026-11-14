"""SC01 team-research three-probe bibliographic trial (offline replay).

This replays live-search evidence archived by a researcher and validates
journal-level A/B/C scope. It does NOT autonomously search, invoke GPT,
save a shared team chat or create scientific synthesis claims.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "experiments/urban_health_graph_2026_11_14/sc01_team_probe_evidence.json"
GROUPS = ("planning_application", "urban_science", "computational_methods")
DEFAULT_PLAN = ROOT / "config/atlas_source_plan.json"


def normalized(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


# Use exact venue-to-watchlist alias identities. Venue inference from domain
# or keywords is disallowed; supplementary literature stays separate.
VENUE_ALIASES = {
    "Cities": "Cities",
    "Computers, Environment and Urban Systems": "CEUS",
    "Environment and Planning B: Urban Analytics and City Science": "EPB",
    "International Journal of Computer Vision": "IJCV",
    "NeurIPS": "NeurIPS",
    "AAAI": "AAAI",
    "KDD": "KDD",
}


def evaluate(manifest: dict, plan: dict) -> dict:
    if manifest.get("scenario_id") != "SC01":
        raise ValueError("Not a team research scenario")
    if manifest.get("status") != "researcher_assisted_probe_draft":
        raise ValueError("Unexpected trial maturity/status")
    if manifest.get("access_control_tested") is not False:
        raise ValueError("This offline test cannot claim team access was tested")
    papers = manifest.get("papers")
    if not isinstance(papers, list) or not papers:
        raise ValueError("No bibliographic evidence")
    source_groups = plan["source_groups"]
    if set(source_groups) != set(GROUPS):
        raise ValueError("Source plan taxonomy changed")
    counts = Counter()
    seen_paper = set()
    evidence_ids = {}
    for paper in papers:
        ident = paper.get("paper_id")
        if not isinstance(ident, str) or ident in seen_paper:
            raise ValueError("Duplicate or invalid paper identifier")
        seen_paper.add(ident)
        group = paper.get("source_group")
        if group not in (*GROUPS, "supplementary_out_of_watchlist"):
            raise ValueError("Invalid source group")
        if not paper.get("title") or not paper.get("url"):
            raise ValueError("Missing bibliographic identifier")
        if str(paper.get("url")).startswith("https://example.org"):
            raise ValueError("Placeholder sources forbidden")
        if int(paper.get("year")) > date.fromisoformat(manifest["trial_date"]).year:
            # On-line 2026 preprint records may be in a 2027 volume, but must
            # be encoded as year=2026 for the retrieval record.
            raise ValueError("Future unobserved publication year")
        if group in GROUPS:
            venue = paper["venue"]
            watch = VENUE_ALIASES.get(venue, venue)
            configured = {normalized(item) for item in source_groups[group]["venues"]}
            if normalized(watch) not in configured:
                raise ValueError("Primary paper lacks its exact venue in source plan: " + ident)
            counts[group] += 1
        else:
            counts[group] += 1
        evidence_ids[ident] = group
    selected_per_probe = manifest["sampling"].get("selected_primary_per_probe")
    if any(counts[g] != selected_per_probe for g in GROUPS):
        raise ValueError("Missing/uneven source probe")
    if counts["supplementary_out_of_watchlist"] != manifest["sampling"]["out_of_watchlist_context_count"]:
        raise ValueError("Supplementary evidence mismatch")
    return {
        "trial_id": manifest["trial_id"],
        "scenario_id": "SC01",
        "kind": "team_research_public_bibliography_preview",
        "status": "needs_scientific_review",
        "live_search_performed_by": "assistant_outside_backend",
        "autonomous_agent_run": False,
        "team_acl_verified": False,
        "gpt_api_used": False,
        "scientific_claims_verified_from_full_text": False,
        "probe_counts": {g: counts[g] for g in GROUPS},
        "supplementary_count": counts["supplementary_out_of_watchlist"],
        "unique_papers": len(seen_paper),
        "paper_ids": {g: sorted(k for k, v in evidence_ids.items() if v == g)
                      for g in (*GROUPS, "supplementary_out_of_watchlist")},
        "source_plan": manifest["source_config"],
        "missing_gates": [
            "Authenticated team run with member ACL, status, review and shared result",
            "Repeatable topic query against source-constrained OpenAlex/official sites",
            "LLM-generated evidence-anchored L1 synthesis rather than authored interpretation",
            "Representative coverage/recall assessment and close-prior-art deep reading",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    manifest = json.loads(args.input.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = evaluate(manifest, plan)
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
