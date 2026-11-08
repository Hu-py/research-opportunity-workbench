"""Collect public OpenAlex topic trends and recent-work metadata for the weekly Research Advisor.

No team data or credentials are written to the output. No paid-model calls.
Run: OPENALEX_API_KEY=... python scripts/openalex_weekly_radar.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.openalex.org/works"
OUT = pathlib.Path("data/radar/openalex_latest.json")
TOPICS = [
    ("T10766", "Urban Heat Island Mitigation", "城市热岛缓解"),
    ("T10298", "Urban Transport and Accessibility", "城市交通与可达性"),
    ("T12325", "Urban Design and Spatial Analysis", "城市设计与空间分析"),
    ("T11980", "Human Mobility and Location-Based Analysis", "人类移动与位置分析"),
    ("T11479", "Smart Cities and Technologies", "智慧城市与技术"),
]


def request_json(parameters: dict) -> dict:
    """Use the configured key; never expose a key-bearing URL in logs or files."""
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENALEX_API_KEY is not configured")
    params = dict(parameters, api_key=key)
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "research-opportunity-workbench/weekly-radar-1.0", "Accept": "application/json"},
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError("Unexpected API payload")
            return payload
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except Exception as exc:
            last_error = type(exc).__name__
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise RuntimeError("OpenAlex request failed: " + str(last_error))


def get_counts(topic: str, years: list[int]) -> dict[str, int]:
    result = request_json({
        "filter": f"primary_topic.id:{topic},publication_year:{years[0]}-{years[-1]}",
        "group_by": "publication_year",
    })
    groups = result.get("group_by")
    if not isinstance(groups, list):
        raise ValueError("OpenAlex returned no annual grouping")
    counts = {str(y): 0 for y in years}
    for row in groups:
        year = str(row.get("key", ""))
        if year in counts:
            counts[year] = int(row["count"])
    return counts


def recent_works(topic: str, since: str, max_records: int = 20) -> list[dict]:
    response = request_json({
        "filter": f"primary_topic.id:{topic},from_publication_date:{since}",
        "sort": "publication_date:desc",
        "per-page": str(max_records),
    })
    works = response.get("results")
    if not isinstance(works, list):
        raise ValueError("OpenAlex returned no works results")
    items = []
    for work in works:
        if not isinstance(work, dict) or work.get("is_retracted"):
            continue
        source = (work.get("primary_location") or {}).get("source") or {}
        people = work.get("authorships") or []
        authors = [
            str((person.get("author") or {}).get("display_name") or "")
            for person in people[:8] if isinstance(person, dict)
        ]
        items.append({
            "openalex_id": work.get("id"),
            "title": str(work.get("title") or work.get("display_name") or "")[:600],
            "doi": work.get("doi"),
            "publication_date": work.get("publication_date"),
            "type": work.get("type"),
            "venue": source.get("display_name"),
            "authors": [name for name in authors if name],
            "source_topic_id": topic,
            "evidence_level": "metadata_only",
        })
    return items


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    since = (now.date() - dt.timedelta(days=60)).isoformat()
    years = list(range(now.year - 3, now.year))
    data = {
        "schema_version": "1.0.0",
        "purpose": "public_scholarly_metadata_only",
        "retrieved_at_utc": now.isoformat(),
        "retrieval_window_start": since,
        "complete_publication_years": years,
        "dataset": "OpenAlex Works API",
        "query_basis": "primary_topic.id; publication_year counts; recent works sorted by publication_date descending",
        "caveats": [
            "OpenAlex may reclassify works and backfill citations; results are a point-in-time snapshot.",
            "These topics are broad. Publication volume is not evidence of novelty.",
            "Recent papers are API samples, not an exhaustive all-papers download.",
            "Titles, authors, DOI and venues are OpenAlex metadata, not publisher-verified abstracts or full texts.",
            "Radar B computer-science method surveillance is NOT covered by this dataset.",
        ],
        "topic_trends": [],
        "recent_papers": [],
    }
    by_id = {}
    for topic_id, en, zh in TOPICS:
        counts = get_counts(topic_id, years)
        before = counts[str(years[-2])]
        after = counts[str(years[-1])]
        growth = round((after - before) / before * 100, 2) if before else None
        papers = recent_works(topic_id, since)
        for paper in papers:
            unique = paper.get("doi") or paper.get("openalex_id")
            if unique and unique not in by_id:
                by_id[unique] = paper
        data["topic_trends"].append({
            "topic_id": topic_id,
            "name_en": en,
            "name_zh": zh,
            "annual_counts": counts,
            "growth_rate_latest_complete_year_pct": growth,
            "recent_sample_count": len(papers),
            "query_filter": f"primary_topic.id:{topic_id}",
        })
        print(f"OK {topic_id}: annual counts {counts}; recent sample {len(papers)}")
        time.sleep(0.35)
    data["recent_papers"] = sorted(
        by_id.values(), key=lambda row: row.get("publication_date") or "", reverse=True
    )
    data["recent_unique_paper_count"] = len(data["recent_papers"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Exported {len(TOPICS)} topics and {len(data['recent_papers'])} distinct recent paper metadata records")
    print(f"Public-only export: {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("OpenAlex weekly data collection failed:", str(error), file=sys.stderr)
        sys.exit(1)
