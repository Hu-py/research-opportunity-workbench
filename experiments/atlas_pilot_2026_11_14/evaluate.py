"""Evaluate an OpenAlex collection against a *small official-site sentinel panel*.

This is NOT full-recall benchmarking. Official pages are independently curated;
an absent sentinel may reflect limited lookback, sampling cap, indexing lag,
mismatched source resolution, or a collection error. Do not infer novelty.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def normalize_doi(value):
    return str(value or "").strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")


def normalize_title(value):
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", "", "".join(x for x in text if not unicodedata.combining(x)))


def evaluate(benchmark, feed):
    records = feed.get("papers", [])
    groups = benchmark["source_groups"]
    summary = {}
    details = []
    for group, source_info in groups.items():
        sentinels = [x for x in benchmark["sentinels"] if x["group"] == group]
        matches = []
        for item in sentinels:
            desired_doi = normalize_doi(item.get("doi"))
            desired_title = normalize_title(item["title"])
            possible = [
                p for p in records
                if group in (p.get("source_groups") or [])
                and (
                    (desired_doi and normalize_doi(p.get("doi")) == desired_doi)
                    or normalize_title(p.get("title")) == desired_title
                )
            ]
            hit = possible[0] if possible else None
            matches.append(hit is not None)
            details.append({
                "group": group,
                "title": item["title"],
                "official_url": item["official_url"],
                "date_status": item["date_status"],
                "first_online_date": item["first_online_date"],
                "found_in_openalex_sample": bool(hit),
                "matched_paper_id": hit.get("paper_id") if hit else None,
                "matched_doi": hit.get("doi") if hit else None,
                "evidence_level": hit.get("evidence_level") if hit else None,
            })
        summary[group] = {
            "venue": source_info["venue"],
            "official_sentinels": len(sentinels),
            "found_in_capped_openalex_sample": sum(matches),
            "sentinel_sample_hit_fraction": f"{sum(matches)}/{len(sentinels)}",
            "coverage_note": "Sentinel panel only; not journal-wide recall",
        }
    return {
        "experiment_id": benchmark["experiment_id"],
        "feed_status": feed.get("status"),
        "feed_collection_coverage": feed.get("coverage"),
        "feed_retrieved_at_utc": feed.get("retrieved_at_utc"),
        "source_plan_sha256": feed.get("source_plan_sha256"),
        "source_group_sentinel_results": summary,
        "records": details,
        "interpretation_boundary": (
            "A missing sentinel is an observation in a capped API sample, not proof "
            "of absence from OpenAlex. JMLR sentinels lack exact first-online dates, "
            "so their 60-day temporal coverage is unknown."
        ),
        "official_reference_urls": sorted({x["official_url"] for x in benchmark["sentinels"]}),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    feed = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    result = evaluate(benchmark, feed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("EXPERIMENT_JSON_BEGIN")
    print(json.dumps({
        "experiment_id": result["experiment_id"],
        "status": result["feed_status"],
        "collected": result["feed_collection_coverage"]["global_unique_papers"],
        "group_counts": result["feed_collection_coverage"]["group_distinct_papers"],
        "per_group": result["source_group_sentinel_results"],
        "sentinel_rows": result["records"],
        "collection_warnings": feed.get("warnings", []),
        "source_failures": {
            name: entry["failed_sources"]
            for name, entry in feed["coverage"]["source_groups"].items()
        },
    }, ensure_ascii=False))
    print("EXPERIMENT_JSON_END")


if __name__ == "__main__":
    main()
