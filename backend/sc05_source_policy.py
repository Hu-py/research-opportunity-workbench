"""SC05 venue provenance policy: A/B planning discovery, C methods, D direct priors.

This is a conservative **source eligibility** check, not a relevance or
journal-quality score. Scientific mechanism alignment remains a separate gate.
The source catalog is reviewed/versioned in Git; never silently add a venue.
Unlisted OpenAlex results remain visible only in the audit, not model priors.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

POLICY_VERSION = "sc05-source-catalog-v1.0"


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


@lru_cache(maxsize=1)
def source_catalog() -> dict[str, Any]:
    path=Path(__file__).resolve().parent.parent/"config/sc05_source_catalog_v1.json"
    doc=json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema_version")!=POLICY_VERSION:
        raise ValueError("SC05 source catalog has unsupported version")
    return doc


def source_tier(venue: Any, source_domain: str) -> dict[str, str]:
    """Classify an *exact* venue/alias, never broad substring matches.

    An unknown journal is not a fraudulent paper and not evidence of no prior
    work. It simply cannot silently enter a curated scientific prior pool.
    """
    catalog=source_catalog()
    raw=str(venue or "").strip()
    key=_key(raw)
    if not key:
        return {"tier":"unverified", "canonical_venue":"",
                "venue_status":"missing"}
    canonical={
        _key(alias):actual
        for alias,actual in catalog.get("aliases",{}).items()
    }.get(key,raw)
    value=_key(canonical)
    for tier,definition in catalog["streams"].items():
        for registered in definition["venues"]:
            if value==_key(registered):
                return {"tier":tier,"canonical_venue":registered,
                        "venue_status":"curated"}
    for registered in catalog["direct_comparison_domain_pools"].get(source_domain,[]):
        if value==_key(registered):
            return {"tier":"D","canonical_venue":registered,
                    "venue_status":"domain_specialist"}
    return {"tier":"unlisted","canonical_venue":raw[:230],
            "venue_status":"manual_review_required"}


def apply_source_governance(
    retrieved: list[dict[str, Any]],
    domain_candidates: list[dict[str, Any]],
    *,
    source_domain: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Separate near work from approved technical sources without inventing gold.

    A/B/D candidates still need abstract and domain/mechanism checks.
    C is technical inspiration **even when the article concerns transport**.
    Unlisted venue is quarantined regardless of abstract semantic proximity;
    reviewers can nominate it for future catalog approval, not claim it was
    'not published'. Fully deterministic; no external API or model call.
    """
    annotated=[]
    for paper in retrieved:
        metadata=source_tier(paper.get("venue"),source_domain)
        annotated.append({**paper,"source_tier":metadata["tier"],
                          "canonical_venue":metadata["canonical_venue"],
                          "venue_status":metadata["venue_status"],
                          "catalog_version":POLICY_VERSION})
    by_id={p["id"]:p for p in annotated}
    in_scope=[p for p in annotated if p["source_tier"] in {"A","B","C","D"}]
    domain_ids={p["id"] for p in domain_candidates}
    direct=[{
        **by_id[pid],
        "eligible_for_nearest_prior":True,
    } for pid in domain_ids
        if pid in by_id and by_id[pid]["source_tier"] in {"A","B","D"}]
    # Keep the relative search order, not unordered set iteration.
    ordered_direct=[p for p in in_scope if p["id"] in {d["id"] for d in direct}]
    c_ids=[p["id"] for p in in_scope if p["source_tier"]=="C"]
    denied=[p for p in annotated if p["source_tier"] in {"unlisted","unverified"}]
    tally=Counter(p["source_tier"] for p in annotated)
    audit={
        "policy_version":POLICY_VERSION,
        "retrieved_total":len(retrieved),
        "metadata_classified":dict(sorted(tally.items())),
        "approved_source_candidates":len(in_scope),
        "eligible_direct_context":len(ordered_direct),
        "technical_C_count":len(c_ids),
        "unlisted_or_unverified_count":len(denied),
        "excluded_outside_catalog_ids":[p["id"] for p in denied],
        "candidates_missing_approved_venue":len(denied),
        "direct_tiers_with_candidates":sorted({
            p["source_tier"] for p in ordered_direct
        }),
        "uncovered_planning_streams":[tier for tier in ("A","B")
             if not any(p["source_tier"]==tier for p in ordered_direct)],
        "scientific_novelty_certified":False,
        "approved_catalog_expansion":0,
        "interpretation":(
            "Venue controls discovery provenance, never proves quality, "
            "mechanism alignment or novelty. A/B are planning sources, "
            "C offers methods only, D compares domain-specific prior art. "
            "Unlisted works require separate human approval."
        ),
    }
    return ordered_direct,in_scope,audit
