"""R6.6 reproducible, read-only OpenAlex relevance evaluation.

The CLI never calls DeepSeek, writes to Research Atlas databases, or stores
third-party full text/abstracts. It evaluates a *provisional silver* DOI set;
a second review is required before any conclusions about scientific quality.

Examples:
  python -m scripts.sc05_r66_eval --manifest benchmarks/sc05_r66_silver_set_v01.json --live --output r66-metrics.json
  python -m scripts.sc05_r66_eval --manifest benchmarks/sc05_r66_silver_set_v01.json --fixture fixtures.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any

import httpx

from backend.sc05_relevance import screen_candidate_papers
from research_workbench.core import normalize_paper

LABELS = {"direct_near", "domain_context", "method_transfer", "unrelated", "source_self"}
DOMAIN_POSITIVES = {"direct_near", "domain_context"}
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
MAX_MANIFEST_ITEMS = 25


def normalize_doi(value: str) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    return text.removeprefix("doi:")


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "sc05-r66-benchmark-v0.1":
        raise ValueError("Unsupported R6.6 benchmark schema")
    if data.get("snapshot_status") != "provisional_silver_not_gold":
        raise ValueError("Do not pass a silver set off as adjudicated gold")
    source = data.get("heldout_source") or {}
    source_doi = normalize_doi(source.get("doi"))
    if not DOI_RE.fullmatch(source_doi):
        raise ValueError("Missing valid held-out source DOI")
    items = data.get("items")
    if not isinstance(items, list) or not 2 <= len(items) <= MAX_MANIFEST_ITEMS:
        raise ValueError("Benchmark must contain 2-25 frozen DOI records")
    seen = set()
    for item in items:
        doi = normalize_doi(item.get("doi"))
        if not DOI_RE.fullmatch(doi) or doi in seen:
            raise ValueError("Invalid or duplicate benchmark DOI")
        seen.add(doi)
        if item.get("label") not in LABELS:
            raise ValueError("Unsupported benchmark class")
        if (doi == source_doi) != (item["label"] == "source_self"):
            raise ValueError("Held-out source may only be labeled source_self")
        if not isinstance(item.get("title"), str) or len(item["title"]) < 12:
            raise ValueError("Missing publisher-verified title")
        if not isinstance(item.get("year"), int) or item["year"] < 1900:
            raise ValueError("Missing publication year")
    if not any(x["label"] == "source_self" for x in items):
        raise ValueError("Source-self exclusion case is required")
    return data


def _paper_from_work(work: dict[str, Any], expected_doi: str) -> dict[str, Any]:
    actual_doi = normalize_doi(work.get("doi"))
    if actual_doi != expected_doi:
        raise ValueError("Provider DOI mismatch")
    paper = normalize_paper(work)
    if not paper.get("title") or not paper.get("abstract"):
        raise ValueError("OpenAlex record missing title or abstract")
    return {
        "id": str(paper["id"]),
        "doi": expected_doi,
        "title": str(paper["title"])[:300],
        "abstract": str(paper["abstract"])[:10000],
        "published": str(paper.get("published") or "")[:10],
        "url": str(paper["url"]),
        "venue": str(paper.get("venue") or "")[:250],
    }


def fetch_openalex_metadata(
    manifest: dict[str, Any], *,
    client: httpx.Client,
    max_requests: int = 16,
    delay_seconds: float = 1.05,
) -> tuple[dict[str, dict[str, Any]], dict[str, str], int]:
    """DOI-addressed public metadata lookups; no search, no LLM, hard request cap.

    Retry 429 / temporary 5xx only within max_requests. Never log the complete
    URL, request headers, secret key, response body, or provider exception text.
    """
    if max_requests < len(manifest["items"]):
        raise ValueError("Request cap lower than required DOI count")
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    found: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    count = 0
    for item in manifest["items"]:
        doi = normalize_doi(item["doi"])
        for attempt in range(2):
            if count >= max_requests:
                errors[doi] = "request_cap_exhausted"
                break
            if delay_seconds:
                time.sleep(delay_seconds)
            count += 1
            try:
                params = {
                    "filter": "doi:https://doi.org/" + doi,
                    "per-page": 1,
                }
                if key:
                    params["api_key"] = key
                response = client.get("https://api.openalex.org/works", params=params)
                if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    continue
                if response.status_code >= 400:
                    errors[doi] = "openalex_http_" + str(response.status_code)
                    break
                results = response.json().get("results")
                if not isinstance(results, list) or not results:
                    errors[doi] = "not_indexed_or_no_result"
                    break
                try:
                    found[doi] = _paper_from_work(results[0], doi)
                except ValueError as error:
                    # Fixed public error category; do not emit unsafe provider data.
                    errors[doi] = (
                        "abstract_unavailable" if "abstract" in str(error)
                        else "metadata_mismatch"
                    )
                break
            except (httpx.TimeoutException, httpx.TransportError):
                errors[doi] = "openalex_network_or_timeout"
                if attempt == 0:
                    continue
            except (ValueError, TypeError, KeyError):
                errors[doi] = "malformed_provider_response"
                break
    return found, errors, count


def evaluate(
    manifest: dict[str, Any],
    works_by_doi: dict[str, dict[str, Any]],
    errors: dict[str, str] | None = None,
    *,
    api_calls: int = 0,
) -> dict[str, Any]:
    """Evaluate the domain screen, not pretend to grade scientific novelty."""
    source = manifest["heldout_source"]
    profile = {"code": source["source_field"], "confidence": "curator_declared"}
    candidates = [
        works_by_doi[normalize_doi(item["doi"])]
        for item in manifest["items"]
        if normalize_doi(item["doi"]) in works_by_doi
    ]
    accepted, audit = screen_candidate_papers(candidates, profile, source_doi=source["doi"])
    kept = {p["id"] for p in accepted}
    removed = {p["paper_id"]: p["reason"] for p in audit["quarantined_records"]}
    records = []
    for item in manifest["items"]:
        doi = normalize_doi(item["doi"])
        paper = works_by_doi.get(doi)
        if not paper:
            records.append({
                "doi": doi, "label": item["label"], "prediction": "unresolved",
                "error_code": (errors or {}).get(doi, "metadata_not_provided"),
            })
            continue
        predicted = "domain_candidate" if paper["id"] in kept else "quarantined"
        records.append({
            "doi": doi,
            "publisher_title": item["title"],
            "year": item["year"],
            "label": item["label"],
            "prediction": predicted,
            "quarantine_reason": removed.get(paper["id"], ""),
            "provider_title": paper["title"][:250],
            "provider_publication_date": paper.get("published", ""),
            "abstract_sha256": hashlib.sha256(paper["abstract"].encode()).hexdigest(),
            "source_url": item["publisher_url"],
        })
    resolved = [r for r in records if r["prediction"] != "unresolved"]
    positives = [r for r in resolved if r["label"] in DOMAIN_POSITIVES]
    negatives = [r for r in resolved if r["label"] not in DOMAIN_POSITIVES]
    kept_rows = [r for r in resolved if r["prediction"] == "domain_candidate"]
    true_kept = [r for r in kept_rows if r["label"] in DOMAIN_POSITIVES]
    near = [r for r in resolved if r["label"] == "direct_near"]
    irrelevant = [r for r in resolved if r["label"] == "unrelated"]
    transfer = [r for r in resolved if r["label"] == "method_transfer"]
    source_self = [r for r in resolved if r["label"] == "source_self"]
    ratio = lambda numerator, denominator: (
        round(numerator / denominator, 4) if denominator else None
    )
    metrics = {
        "metadata_coverage": ratio(len(resolved), len(records)),
        "domain_precision_provisional": ratio(len(true_kept), len(kept_rows)),
        "domain_recall_provisional": ratio(
            sum(r["prediction"] == "domain_candidate" for r in positives),
            len(positives),
        ),
        "direct_near_candidate_recall": ratio(
            sum(r["prediction"] == "domain_candidate" for r in near), len(near),
        ),
        "unrelated_admission_rate": ratio(
            sum(r["prediction"] == "domain_candidate" for r in irrelevant),
            len(irrelevant),
        ),
        "method_transfer_quarantine_rate": ratio(
            sum(r["prediction"] == "quarantined" for r in transfer),
            len(transfer),
        ),
        "source_self_excluded": (
            all(r["prediction"] == "quarantined" for r in source_self)
            if source_self else None
        ),
        "frozen_source_papers": 1,
        "model_calls": 0,
        "api_requests": api_calls,
        "nearest_prior_semantic_accuracy": None,
        "scientific_novelty_certified": False,
    }
    missing = [r["doi"] for r in records if r["prediction"] == "unresolved"]
    return {
        "benchmark_version": manifest["schema_version"],
        "source_doi": normalize_doi(source["doi"]),
        "source_selected_after_fix": source["selection"],
        "evaluation_status": (
            "complete_silver_not_gold" if not missing
            else "partial_provider_coverage_not_comparable"
        ),
        "judgment_status": manifest["snapshot_status"],
        "total_items": len(records),
        "resolved_items": len(resolved),
        "positive_resolved": len(positives),
        "non_domain_resolved": len(negatives),
        "metrics": metrics,
        "rejected_ids_for_review": [
            {"doi": row["doi"], "label": row["label"],
             "reason": row.get("quarantine_reason", "")}
            for row in records if row["prediction"] == "quarantined"
        ],
        "unresolved_dois": missing,
        "per_paper": records,
        "interpretation_limit": (
            "Single-reviewer title/abstract provisional labels only. "
            "Domain-screen accuracy is not equivalent to closest-prior "
            "semantic validity, scientific innovation or A/B performance. "
            "Unresolved provider records are excluded from precision/recall."
        ),
        "source_material_policy": "No full text or reconstructed abstracts stored.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-requests", type=int, default=16)
    parser.add_argument("--delay-seconds", type=float, default=1.05)
    parser.add_argument("--strict-coverage", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if bool(args.live) == bool(args.fixture):
        parser.error("Select exactly one of --live or --fixture")
    if args.max_requests > 25 or args.max_requests < 1:
        parser.error("max-requests must be between 1 and 25")
    if not 0 <= args.delay_seconds <= 15:
        parser.error("delay-seconds must be between 0 and 15")
    if args.fixture:
        raw = json.loads(args.fixture.read_text(encoding="utf-8"))
        works = {normalize_doi(k): v for k, v in raw["works_by_doi"].items()}
        errors = raw.get("errors", {})
        calls = 0
    else:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            works, errors, calls = fetch_openalex_metadata(
                manifest, client=client,
                max_requests=args.max_requests,
                delay_seconds=args.delay_seconds,
            )
    report = evaluate(manifest, works, errors, api_calls=calls)
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    if args.strict_coverage and report["unresolved_dois"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
