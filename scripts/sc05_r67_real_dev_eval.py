"""R6.7-B real-publisher-DOI *development*, not independent holdout evaluation.

No model calls. Public OpenAlex DOI abstracts live in memory only; reports store
metadata, abstract SHA256, provisional lane decisions and disagreement queues.
This program does not approve any cross-field transfer or certify originality.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import httpx

from backend.sc05_method_transfer import collect_transfer_leads
from backend.sc05_relevance import screen_candidate_papers
from scripts.sc05_r66_eval import fetch_openalex_metadata, normalize_doi

SCHEMA = "sc05-r67-real-development-v0.1"
ALLOWED = {"domain_near", "domain_context", "method_transfer", "lexical_negative"}
NEAR = {"domain_near", "domain_context"}


def load_dev(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA:
        raise ValueError("Unrecognized real-development manifest schema")
    if manifest.get("label_status") != "ai_assisted_provisional_not_gold":
        raise ValueError("Only provisional, non-adjudicated labels are allowed")
    items = manifest.get("items")
    if not isinstance(items, list) or len(items) < 20 or len(items) > 38:
        raise ValueError("Expected 20-38 publisher-verified development records")
    seen = set()
    for row in items:
        doi = normalize_doi(row.get("doi"))
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            raise ValueError("Invalid DOI")
        if doi in seen:
            raise ValueError("Repeated development DOI")
        seen.add(doi)
        if row.get("initial_label") not in ALLOWED:
            raise ValueError("Unrecognized provisional category")
        if not row.get("title") or len(row["title"]) < 14:
            raise ValueError("Missing complete publisher title")
        source_url = str(row.get("source_url") or "")
        if (not source_url.casefold().startswith("https://doi.org/")
                or normalize_doi(source_url) != doi):
            raise ValueError("Canonical DOI source link required")
        if row.get("annotation_status") != "ai_assisted_provisional":
            raise ValueError("Never invent independent human review")
        if not 2020 <= row.get("year", 0) <= 2026:
            raise ValueError("Unexpected publication year")
    counts = Counter(r["initial_label"] for r in items)
    if any(counts.get(name, 0) < 5 for name in ALLOWED):
        raise ValueError("Development categories insufficient for diagnostics")
    # Hard anti-leak boundary: fail if any R6.6 record is accidentally re-used.
    r66 = Path("benchmarks/sc05_r66_silver_set_v01.json")
    if r66.is_file():
        old = json.loads(r66.read_text(encoding="utf-8"))
        old_dois = {normalize_doi(r["doi"]) for r in old["items"]}
        source_doi = normalize_doi(old["heldout_source"]["doi"])
        if old_dois.intersection(seen) or source_doi in seen:
            raise ValueError("R6.6 exposed DOI cannot enter R6.7 development corpus")
    return manifest


def _round(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def evaluate_real_dev(
    manifest: dict[str, Any],
    available: dict[str, dict[str, Any]],
    errors: dict[str, str] | None = None,
    *,
    requests: int = 0,
) -> dict[str, Any]:
    """Evaluate first-stage lane triage, not transfer-bridge correctness.

    A single machine-generated label is useful for prioritizing manual review,
    but is not a gold-standard accuracy estimate. Provider gaps are abstentions.
    """
    domain = manifest["source_domain"]
    lookup: dict[str, dict[str, Any]] = {}
    for item in manifest["items"]:
        doi = normalize_doi(item["doi"])
        if doi in available:
            lookup[doi] = available[doi]
    papers = list(lookup.values())
    domain_papers, domain_audit = screen_candidate_papers(
        papers, {"code": domain, "confidence": "research_context_declared"}
    )
    method_leads, method_audit = collect_transfer_leads(
        papers, domain_papers, domain_audit, max_leads=12
    )
    domain_ids = {p["id"] for p in domain_papers}
    method_ids = {p["id"] for p in method_leads}
    reasons = {p["paper_id"]: p["reason"]
               for p in domain_audit["quarantined_records"]}
    records = []
    for item in manifest["items"]:
        doi = normalize_doi(item["doi"])
        paper = lookup.get(doi)
        if paper is None:
            records.append({
                "doi": doi, "provisional_label": item["initial_label"],
                "predicted_lane": "provider_unresolved",
                "provider_error": (errors or {}).get(doi, "not_returned"),
            })
            continue
        if paper["id"] in domain_ids:
            lane = "domain_candidate"
        elif paper["id"] in method_ids:
            lane = "unapproved_method_lead"
        else:
            lane = "quarantined"
        records.append({
            "doi": doi,
            "publisher_title": item["title"],
            "openalex_title": paper["title"][:240],
            "publication_year": item["year"],
            "provisional_label": item["initial_label"],
            "predicted_lane": lane,
            "screen_reason": reasons.get(paper["id"], ""),
            "abstract_sha256": hashlib.sha256(
                paper["abstract"].encode("utf-8")).hexdigest(),
            "metadata_url": item["source_url"],
            "human_review_status": "not_adjudicated",
        })
    resolved = [r for r in records
                if r["predicted_lane"] != "provider_unresolved"]
    near = [r for r in resolved if r["provisional_label"] in NEAR]
    method = [r for r in resolved
              if r["provisional_label"] == "method_transfer"]
    neg = [r for r in resolved
           if r["provisional_label"] == "lexical_negative"]
    kept = [r for r in resolved if r["predicted_lane"] == "domain_candidate"]
    correct_near = [r for r in kept if r["provisional_label"] in NEAR]
    promoted_methods = [r for r in method
                        if r["predicted_lane"] == "unapproved_method_lead"]
    # Review cases include both "method incorrectly in domain" and
    # "method unknown" and wrong-domain admissions. Nothing is auto-approved.
    disputes = [{
        "doi": r["doi"], "provisional_label": r["provisional_label"],
        "predicted_lane": r["predicted_lane"],
        "reason": (
            "provisional_method_in_domain_lane"
            if r["provisional_label"] == "method_transfer" and
               r["predicted_lane"] == "domain_candidate"
            else "domain_article_not_kept"
            if r["provisional_label"] in NEAR and
               r["predicted_lane"] != "domain_candidate"
            else "irrelevant_article_admitted"
            if r["provisional_label"] == "lexical_negative" and
               r["predicted_lane"] != "quarantined"
            else "method_not_recovered"
        )
    } for r in resolved if (
        (r["provisional_label"] in NEAR and r["predicted_lane"] != "domain_candidate") or
        (r["provisional_label"] == "lexical_negative" and r["predicted_lane"] != "quarantined") or
        (r["provisional_label"] == "method_transfer" and
         r["predicted_lane"] != "unapproved_method_lead")
    )]
    confusion = {}
    for label in sorted(ALLOWED):
        confusion[label] = dict(Counter(
            r["predicted_lane"] for r in resolved
            if r["provisional_label"] == label))
    missing = [r["doi"] for r in records
               if r["predicted_lane"] == "provider_unresolved"]
    outcome = {
        "schema_version": "sc05-r67-real-dev-result-v0.1",
        "manifest_sha256": hashlib.sha256(json.dumps(
            manifest,ensure_ascii=False,sort_keys=True
        ).encode("utf-8")).hexdigest(),
        "evaluation_status": (
            "complete_provisional_development"
            if not missing else "partial_provider_coverage"
        ),
        "label_status": "ai_assisted_provisional_not_gold",
        "source_domain": domain,
        "counts": {"manifest":len(records), "resolved":len(resolved),
                   "unresolved":len(missing)},
        "metrics_provisional_not_gold": {
            "openalex_coverage":_round(len(resolved),len(records)),
            "same_domain_candidate_recall":_round(
                len(correct_near),len(near)),
            "same_domain_candidate_precision":_round(
                len(correct_near),len(kept)),
            "method_lead_recall":_round(
                len(promoted_methods),len(method)),
            "method_in_domain_leakage":_round(
                sum(r["predicted_lane"]=="domain_candidate" for r in method),
                len(method)),
            "unrelated_admission_rate":_round(
                sum(r["predicted_lane"] != "quarantined" for r in neg),
                len(neg)),
            "human_approved_transfers":0,
            "actual_deepseek_calls":0,
            "openalex_requests":requests,
            "scientific_novelty_certified":False,
            "closest_prior_semantic_accuracy":None,
        },
        "confusion_matrix_provisional":confusion,
        "method_lane_audit":{
            "leads_emitted":method_audit["method_leads_emitted"],
            "weak_only_unpromoted":method_audit["weak_only_unpromoted"],
            "auto_approved":0,
        },
        "needs_human_adjudication":disputes,
        "unresolved_dois":missing,
        "per_doi":records,
        "limitations":[
            "Labels are AI-assisted title/abstract provisional labels, not independent human gold.",
            "A selected development corpus is not a live search recall benchmark.",
            "No novel held-out paper or true transfer feasibility has been tested.",
            "An exact abstract quote is not proof of method compatibility.",
            "Missing OpenAlex abstracts are unresolved, not false negatives.",
        ],
        "copyright_policy":"No full article text or third-party abstracts saved.",
    }
    return outcome


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--fixture", type=Path)
    p.add_argument("--max-requests", type=int, default=38)
    p.add_argument("--delay-seconds", type=float, default=1.05)
    p.add_argument("--output", type=Path)
    p.add_argument("--strict-coverage", action="store_true")
    args = p.parse_args()
    manifest = load_dev(args.manifest)
    if bool(args.live) == bool(args.fixture):
        p.error("Select exactly one of --live and --fixture")
    if not len(manifest["items"]) <= args.max_requests <= 48:
        p.error("max-requests must cover all DOI records and not exceed 48")
    if not 0 <= args.delay_seconds <= 8:
        p.error("delay-seconds must be between 0 and 8")
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        available = payload["works_by_doi"]
        errors = payload.get("errors", {})
        n = 0
    else:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            available, errors, n = fetch_openalex_metadata(
                manifest, client=client,
                max_requests=args.max_requests,
                delay_seconds=args.delay_seconds,
            )
    result = evaluate_real_dev(manifest,available,errors,requests=n)
    text = json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding="utf-8")
    print(text)
    return 2 if args.strict_coverage and result["unresolved_dois"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
