"""Diagnostic OpenAlex queries for the four misses in the first pilot.

Only public bibliographic data; never prints API keys. Uses the same
OpenAlex authenticated transport as the collector, but looks up exact DOI
or title irrespective of the 60-day venue-limited sample.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.atlas_intelligence.collector import openalex_api, _resolve_openalex_source, _official_catalog
from backend.atlas_intelligence.sources import load_source_plan


def simplify(paper):
    if not isinstance(paper, dict):
        return {}
    source = ((paper.get("primary_location") or {}).get("source") or {})
    return {
        "openalex_id": paper.get("id"),
        "title": paper.get("title"),
        "doi": paper.get("doi"),
        "publication_date": paper.get("publication_date"),
        "indexed_source_name": source.get("display_name"),
        "indexed_source_id": source.get("id"),
        "updated_date": paper.get("updated_date"),
    }


def run():
    benchmark = json.loads(Path(
        "experiments/atlas_pilot_2026_11_14/official_sentinels.json"
    ).read_text(encoding="utf-8"))
    plan = load_source_plan(
        "experiments/atlas_pilot_2026_11_14/source_plan.json"
    )
    catalog = _official_catalog()
    original = {
        "SCS": "Sustainable Cities and Society",
        "JMLR": "Journal of Machine Learning Research",
    }
    counts = {}
    for abbreviation, name in original.items():
        row = next((x for x in catalog if x["name"] == name), None)
        if row is None:
            counts[abbreviation] = {"error": "No registered source"}
            continue
        sid = _resolve_openalex_source(row, openalex_api)
        query = {
            "filter": "primary_location.source.id:" + sid +
                      ",from_publication_date:2026-09-15",
            "per-page": 1,
        }
        resp = openalex_api("/works", query)
        counts[abbreviation] = {
            "resolved_source_id": sid,
            "indexed_60day_total_count": (resp.get("meta") or {}).get("count"),
        }

    misses = [
        p for p in benchmark["sentinels"]
        if p["group"] == "computational_methods"
        or p["doi"] == "10.1016/j.scs.2026.107957"
    ]
    diagnostics = []
    for sentinel in misses:
        record = {
            "group": sentinel["group"],
            "official_title": sentinel["title"],
            "official_doi": sentinel.get("doi"),
            "found_by_exact_doi": None,
            "search_title_top_matches": [],
            "lookup_error": None,
        }
        try:
            doi = sentinel.get("doi")
            if doi:
                payload = openalex_api("/works", {
                    "filter": "doi:https://doi.org/" + doi,
                    "per-page": 3,
                })
                record["found_by_exact_doi"] = [
                    simplify(x) for x in payload.get("results", [])
                ]
            response = openalex_api("/works", {
                "search": sentinel["title"],
                "per-page": 5,
                "select": "id,title,doi,publication_date,primary_location,updated_date",
            })
            record["search_title_top_matches"] = [
                simplify(x) for x in response.get("results", [])[:5]
            ]
        except (ValueError, RuntimeError) as error:
            record["lookup_error"] = str(error)[:120]
        diagnostics.append(record)

    result = {
        "experiment_id": benchmark["experiment_id"],
        "diagnostic_type": "OpenAlex_direct_DOI_and_title_lookup",
        "source_count_probe": counts,
        "misses": diagnostics,
        "limitations": (
            "Search results are ranked candidates; exact DOI/title and source "
            "must be checked. Failure in a bounded query does not establish "
            "global database absence."
        ),
    }
    out = Path("scratch/atlas_pilot_missing_probes.json")
    out.parent.mkdir(exist_ok=True, parents=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("DIAGNOSTIC_JSON_BEGIN")
    print(json.dumps(result, ensure_ascii=False))
    print("DIAGNOSTIC_JSON_END")


if __name__ == "__main__":
    run()
