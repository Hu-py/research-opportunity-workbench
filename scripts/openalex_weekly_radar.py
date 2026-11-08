"""OpenAlex public evidence feed. Topic selection and scientific judgments belong to the Agent.

Reads config/radar_source_pools.json; discovers topics *each run* from recent
papers published in broadly selected academic outlets. Never reads team data
or stores API keys in the public feed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.openalex.org"
CONFIG = Path("config/radar_source_pools.json")
OUTPUT = Path("data/radar/openalex_latest.json")
YEARS = (2023, 2024, 2025)  # Replaced at runtime by the last 3 complete years.


def api(endpoint, params):
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENALEX_API_KEY is missing")
    url = API + endpoint + "?" + urllib.parse.urlencode(dict(params, api_key=key))
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "CUSP-public-academic-radar/2.0"},
    )
    last = "unknown"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError("Non-object OpenAlex response")
            time.sleep(0.15)
            return payload
        except urllib.error.HTTPError as exc:
            last = "HTTP " + str(exc.code)
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except Exception as exc:
            last = type(exc).__name__
        if attempt < 2:
            time.sleep(1 + attempt * 2)
    # Deliberately do NOT print the key-containing request URL or response body.
    raise RuntimeError(last)


def normalized(value):
    return re.sub("[^a-z0-9]", "", (value or "").casefold())


def short_id(value):
    return (value or "").rsplit("/", 1)[-1]


def resolve_source(name):
    response = api("/sources", {"search": name, "per-page": 10})
    candidates = response.get("results") or []
    matches = [item for item in candidates
               if normalized(item.get("display_name")) == normalized(name)]
    if len(matches) != 1:
        return None, "No unique exact source-name match"
    return short_id(matches[0].get("id")), None


def public_work(work, source_name, stream):
    source = (work.get("primary_location") or {}).get("source") or {}
    authors = [
        (a.get("author") or {}).get("display_name")
        for a in (work.get("authorships") or [])[:6] if isinstance(a, dict)
    ]
    topic = work.get("primary_topic") or {}
    return {
        "openalex_id": work.get("id"),
        "doi": work.get("doi"),
        "title": str(work.get("title") or work.get("display_name") or "")[:700],
        "publication_date": work.get("publication_date"),
        "work_type": work.get("type"),
        "authors": [a for a in authors if a],
        "venue": source.get("display_name") or source_name,
        "primary_topic_id": short_id(topic.get("id")),
        "primary_topic": topic.get("display_name"),
        "stream": stream,
        "evidence_level": "metadata_only",
    }


def recent_from_source(source_id, source_name, stream, since):
    response = api("/works", {
        "filter": "primary_location.source.id:" + source_id + ",from_publication_date:" + since,
        "per-page": 30,
        "sort": "publication_date:desc",
        "select": "id,title,doi,publication_date,type,authorships,primary_topic,primary_location,is_retracted",
    })
    return [public_work(item, source_name, stream)
            for item in (response.get("results") or [])
            if isinstance(item, dict) and not item.get("is_retracted")]


def annual_counts(topic_id, years):
    response = api("/works", {
        "filter": "primary_topic.id:" + topic_id + ",publication_year:" + str(years[0]) + "-" + str(years[-1]),
        "group_by": "publication_year",
    })
    groups = response.get("group_by")
    if not isinstance(groups, list):
        raise ValueError("Missing group_by")
    counts = {str(year): 0 for year in years}
    for item in groups:
        year = str(item.get("key"))
        if year in counts:
            counts[year] = int(item["count"])
    return counts


def main():
    settings = json.loads(CONFIG.read_text(encoding="utf-8"))
    streams = settings["streams"]
    now = datetime.now(timezone.utc)
    since = (now.date() - timedelta(days=60)).isoformat()
    years = [now.year - 3, now.year - 2, now.year - 1]
    feed = {
        "schema_version": "2.0.0",
        "feed_kind": "public_scholarly_evidence_only",
        "retrieved_at_utc": now.isoformat(),
        "recent_window_start": since,
        "complete_publication_years": years,
        "source_pool_config": str(CONFIG),
        "discovery_protocol": "Select academic SOURCE pools; harvest latest source papers; observe their current PRIMARY topics; objectively count 3 recent complete years for dynamically observed topic IDs. Agent, not GitHub, selects scientifically worthwhile research themes.",
        "scientific_topic_selections": [],
        "caveats": [
            "Topic candidates change with the sampled recent papers; no permanent five-topic list.",
            "Source-name resolution is exact; unresolved sources and request failures appear in warnings.",
            "Per-source paper sampling is capped and may miss relevant papers or distort prevalence.",
            "Topic-wide annual counts cover all OpenAlex works assigned to that primary topic, not only curated source publications.",
            "OpenAlex indexing, topic assignments, publication dates and sample coverage may change.",
            "Metadata_only is not evidence that abstracts or full texts have been read.",
            "The Agent must independently validate method novelty and research gaps against primary sources.",
            "No team portrait, private papers, evaluation history or AI generated idea is in this public feed.",
        ],
        "source_coverage": {},
        "observed_topic_distributions": {},
        "topic_candidates": [],
        "recent_papers": [],
        "warnings": [],
    }

    known = {}
    for stream, group in streams.items():
        coverage = {"configured": len(group["source_names"]), "resolved": 0,
                    "sampled_papers": 0, "unresolved": []}
        all_works = {}
        for source_name in group["source_names"]:
            try:
                sid, why = resolve_source(source_name)
                if not sid:
                    coverage["unresolved"].append({"name": source_name, "reason": why})
                    continue
                coverage["resolved"] += 1
                works = recent_from_source(sid, source_name, stream, since)
                for item in works:
                    wid = item.get("openalex_id")
                    if wid:
                        all_works[wid] = item
                        # Paper may occur across outlets/streams; retain both categories.
                        if wid not in known:
                            known[wid] = dict(item, streams=[stream])
                        elif stream not in known[wid]["streams"]:
                            known[wid]["streams"].append(stream)
            except Exception as exc:
                coverage["unresolved"].append({"name": source_name, "reason": str(exc)})
        coverage["sampled_papers"] = len(all_works)
        feed["source_coverage"][stream] = coverage
        print("Source scan", stream, "resolved", coverage["resolved"],
              "out of", coverage["configured"], "sampled", len(all_works))

        occurrences = Counter()
        topic_names = {}
        topic_works = defaultdict(list)
        for item in all_works.values():
            topic_id = item["primary_topic_id"]
            if re.fullmatch(r"T\d+", topic_id or ""):
                occurrences[topic_id] += 1
                topic_names[topic_id] = item["primary_topic"]
                topic_works[topic_id].append(item["openalex_id"])

        feed["observed_topic_distributions"][stream] = [
            {"topic_id": tid, "name": topic_names.get(tid),
             "observed_recent_source_sample_count": frequency}
            for tid, frequency in occurrences.most_common(60)
        ]
        # A deterministic *coverage cap*, not an LLM topic recommendation.
        candidate_cap = int(group.get("established_topics", 5)) + int(group.get("rising_topics", 4))
        for topic_id, count in occurrences.most_common(max(0, min(candidate_cap, 30))):
            item = {
                "topic_id": topic_id,
                "name": topic_names.get(topic_id),
                "observed_stream": stream,
                "sampled_recent_papers": count,
                "sample_paper_ids": topic_works[topic_id][:5],
                "annual_counts": None,
                "latest_full_year_growth_pct": None,
                "evidence_status": "trend_unavailable",
                "selection_basis": "recent_primary_topic_frequency_in_curated_source_sample",
            }
            try:
                counts = annual_counts(topic_id, years)
                prev, latest = counts[str(years[-2])], counts[str(years[-1])]
                item["annual_counts"] = counts
                item["latest_full_year_growth_pct"] = (
                    round(100 * (latest - prev) / prev, 2) if prev else None
                )
                item["evidence_status"] = "measured"
            except Exception as exc:
                feed["warnings"].append("Annual count failed for " + topic_id + ": " + str(exc))
            feed["topic_candidates"].append(item)

    feed["recent_papers"] = sorted(
        known.values(), key=lambda row: (row.get("publication_date") or ""), reverse=True
    )[:240]
    if not feed["recent_papers"]:
        raise RuntimeError("No recent academic metadata retrieved. Refusing to publish an empty feed.")
    if not feed["topic_candidates"]:
        raise RuntimeError("No topic candidates discovered. Refusing to publish an empty feed.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote public feed:", OUTPUT, "recent papers", len(feed["recent_papers"]),
          "dynamic topic candidates", len(feed["topic_candidates"]),
          "warnings", len(feed["warnings"]))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("OpenAlex public radar collection failed:", str(exc), file=sys.stderr)
        sys.exit(1)
