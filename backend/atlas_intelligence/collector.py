"""Independent, source-constrained OpenAlex collector for Research Atlas.

Unlike legacy Radar A/B, this retrieves each of the three configurable source
groups independently. The output is *bibliographic evidence*, not an AI review.
No team profile, credentials, or unpublished research enters the public output.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .sources import SOURCE_GROUPS, load_source_plan

API_ROOT = "https://api.openalex.org"
WORK_FIELDS = (
    "id,title,doi,publication_date,type,authorships,primary_location,"
    "abstract_inverted_index,is_retracted,primary_topic"
)
RETRYABLE = {429, 500, 502, 503, 504}
OA_SOURCE = re.compile(r"^S\d+$")
OA_AUTHOR = re.compile(r"^(?:https://openalex\.org/)?(A\d+)$", re.I)
ORCID = re.compile(r"^(?:https://orcid\.org/)?(\d{4}-\d{4}-\d{4}-[\dX]{4})$", re.I)


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _short(value: object) -> str:
    return str(value or "").strip().rsplit("/", 1)[-1]


def openalex_api(endpoint: str, params: dict[str, Any]) -> dict:
    """Send an API request; never reveal credential-bearing URLs on errors."""
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENALEX_API_KEY is required for the live collector")
    query = urlencode({**params, "api_key": key})
    request = Request(API_ROOT + endpoint + "?" + query, headers={
        "User-Agent": "ResearchAtlas/0.1 (public bibliographic metadata)",
        "Accept": "application/json",
    })
    last = "request failed"
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError("non-object OpenAlex result")
            time.sleep(0.12)
            return payload
        except HTTPError as exc:
            last = "OpenAlex HTTP " + str(exc.code)
            if exc.code not in RETRYABLE:
                break
        except (URLError, TimeoutError, ValueError):
            last = "OpenAlex network or response error"
        if attempt < 2:
            time.sleep(1 + 2 * attempt)
    raise RuntimeError(last)


def _official_catalog() -> list[dict[str, Any]]:
    """Reuse *source identities* from the registry; do not reuse Radar A/B."""
    from backend.research_sources import DEFAULT_SOURCES

    return [
        {"name": name, "abbreviation": abbreviation, "kind": kind,
         "aliases": aliases, "domain": domain}
        for name, abbreviation, kind, domain, *_rest, aliases, _notes in DEFAULT_SOURCES
    ]


def _catalog_match(watch: str, catalog: list[dict]) -> dict | None:
    key = _norm(watch)
    matches = [
        source for source in catalog
        if key in {_norm(x) for x in [
            source.get("name"), source.get("abbreviation"),
            *(source.get("aliases") or [])
        ]}
    ]
    return matches[0] if len(matches) == 1 else None


def _resolve_openalex_source(source: dict, api: Callable) -> str:
    names = [source["name"], *(source.get("aliases") or [])]
    forms = {_norm(name) for name in names if name}
    found = set()
    for candidate_name in names:
        response = api("/sources", {"search": candidate_name, "per-page": 10})
        for item in response.get("results", []):
            if not isinstance(item, dict):
                continue
            ident = _short(item.get("id"))
            if _norm(item.get("display_name")) in forms and OA_SOURCE.fullmatch(ident):
                found.add(ident)
        if len(found) == 1:
            break
    if len(found) != 1:
        raise ValueError("source ID unresolved or ambiguous (exact matching required)")
    return next(iter(found))


def _abstract(inverted: object, limit: int = 3600) -> tuple[str, str]:
    """Reconstruct available OpenAlex abstract and mark truncation accurately."""
    if not isinstance(inverted, dict):
        return "", "metadata"
    positions: dict[int, str] = {}
    for word, values in inverted.items():
        if not isinstance(values, list):
            continue
        for pos in values:
            if isinstance(pos, int) and not isinstance(pos, bool) and 0 <= pos < 10000:
                positions[pos] = str(word)
    if not positions:
        return "", "metadata"
    words = [positions[pos] for pos in sorted(positions)]
    full = " ".join(words)
    if len(full) > limit:
        return full[:limit].rstrip() + "…", "abstract_excerpt"
    return full, "abstract"


def _normalize_work(work: object, today: date, since: str) -> dict | None:
    if not isinstance(work, dict) or work.get("is_retracted"):
        return None
    wid = _short(work.get("id"))
    if not re.fullmatch(r"W\d+", wid):
        return None
    pub = str(work.get("publication_date") or "")[:10]
    if not pub or pub < since or pub > today.isoformat():
        return None
    title = str(work.get("title") or "").strip()
    if not title:
        return None
    abstract, level = _abstract(work.get("abstract_inverted_index"))
    loc = work.get("primary_location") or {}
    venue = (loc.get("source") or {}).get("display_name") or ""
    authors, author_ids = [], []
    for authorship in work.get("authorships") or []:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author") or {}
        if not isinstance(author, dict):
            continue
        if author.get("display_name"):
            authors.append(str(author["display_name"]))
        if author.get("id"):
            author_ids.append(_short(author["id"]))
    doi = str(work.get("doi") or "").strip()
    doi = doi if doi.lower().startswith("https://doi.org/") else ""
    return {
        "paper_id": wid,
        "openalex_ids": [wid],
        "doi": doi,
        "title": title[:600],
        "venue": str(venue)[:240],
        "published": pub,
        "work_type": str(work.get("type") or "")[:70],
        "authors": authors[:20],
        "author_ids": author_ids[:50],
        "url": doi or "https://openalex.org/" + wid,
        "abstract": abstract,
        "evidence_level": level,
        "source_groups": [],
        "source_provenance": [],
        "publication_status": "OpenAlex indexed; publisher acceptance not verified",
    }


def _join_record(
    records: dict[str, dict], doi_index: dict[str, str],
    record: dict, group: str, reason: dict,
) -> None:
    key = doi_index.get(record["doi"].casefold()) if record["doi"] else None
    key = key or record["paper_id"]
    if key not in records:
        records[key] = record
    else:
        current = records[key]
        current["openalex_ids"] = list(dict.fromkeys(
            current["openalex_ids"] + record["openalex_ids"]
        ))
        if len(record["abstract"]) > len(current["abstract"]):
            current["abstract"] = record["abstract"]
            current["evidence_level"] = record["evidence_level"]
        if not current.get("doi") and record.get("doi"):
            current["doi"] = record["doi"]
    item = records[key]
    if record["doi"]:
        doi_index[record["doi"].casefold()] = key
    if group not in item["source_groups"]:
        item["source_groups"].append(group)
    if reason not in item["source_provenance"]:
        item["source_provenance"].append(reason)


def _recent_works(
    api: Callable, filter_value: str, limit: int,
) -> list[dict]:
    response = api("/works", {
        "filter": filter_value,
        "sort": "publication_date:desc",
        "per-page": min(100, max(1, limit)),
        "select": WORK_FIELDS,
    })
    if not isinstance(response.get("results"), list):
        raise ValueError("OpenAlex works response missing results")
    return response["results"]


def _author_filter(value: str) -> tuple[str, str]:
    match = OA_AUTHOR.fullmatch(value.strip())
    if match:
        return "authorships.author.id", match.group(1).upper()
    match = ORCID.fullmatch(value.strip())
    if match:
        return "authorships.author.orcid", match.group(1).upper()
    raise ValueError("author_id must be an OpenAlex author ID or ORCID")


def collect_three_sources(
    *,
    api: Callable = openalex_api,
    plan: dict | None = None,
    catalog: list[dict] | None = None,
    today: date | None = None,
    lookback_days: int = 30,
    max_per_source: int = 15,
    max_sources_per_group: int | None = None,
) -> dict[str, Any]:
    """Retrieve genuinely independent A/B/C venue/author evidence.

    Counts describe the capped collected sample, not entire journal output.
    Partial failure stays visible. No LLM call, team portrait or DB write.
    """
    if not 1 <= lookback_days <= 365 or not 1 <= max_per_source <= 100:
        raise ValueError("lookback_days must be 1..365 and max_per_source 1..100")
    if max_sources_per_group is not None and max_sources_per_group < 1:
        raise ValueError("max_sources_per_group must be positive")
    plan = plan if plan is not None else load_source_plan()
    catalog = catalog if catalog is not None else _official_catalog()
    today = today or datetime.now(timezone.utc).date()
    since = (today - timedelta(days=lookback_days)).isoformat()
    records: dict[str, dict] = {}
    doi_index: dict[str, str] = {}
    warnings = []
    coverage: dict[str, dict] = {}
    for group in SOURCE_GROUPS:
        names = plan["source_groups"][group]["venues"]
        sampled_names = names[:max_sources_per_group] if max_sources_per_group else names
        state = {
            "configured_venues": len(names),
            "attempted_venues": len(sampled_names),
            "resolved_venues": 0,
            "successful_venues": 0,
            "failed_sources": [],
            "sampled_records_before_dedup": 0,
        }
        for watch in sampled_names:
            entry = _catalog_match(watch, catalog)
            if entry is None:
                state["failed_sources"].append({"venue": watch, "reason": "registry match missing or ambiguous"})
                continue
            try:
                source_id = _resolve_openalex_source(entry, api)
                state["resolved_venues"] += 1
                results = _recent_works(
                    api, "primary_location.source.id:" + source_id +
                    ",from_publication_date:" + since, max_per_source
                )
                state["successful_venues"] += 1
                for work in results:
                    record = _normalize_work(work, today, since)
                    if record is None:
                        continue
                    work_source = _short(
                        ((work.get("primary_location") or {}).get("source") or {}).get("id")
                    )
                    if work_source != source_id:
                        warnings.append("OpenAlex record source mismatch: " + record["paper_id"])
                        continue
                    state["sampled_records_before_dedup"] += 1
                    _join_record(records, doi_index, record, group, {
                        "kind": "venue", "source_id": source_id,
                        "watch": watch, "group": group,
                    })
            except (ValueError, RuntimeError) as exc:
                state["failed_sources"].append({"venue": watch, "reason": str(exc)[:180]})
        coverage[group] = state

    authors = plan.get("authors") or []
    author_coverage = {"configured": len(authors), "successful": 0, "failed": []}
    for entry in authors:
        identifier = str(entry.get("author_id") or "")
        try:
            key, ident = _author_filter(identifier)
            results = _recent_works(
                api, key + ":" + ident + ",from_publication_date:" + since, max_per_source
            )
            author_coverage["successful"] += 1
            for work in results:
                record = _normalize_work(work, today, since)
                if record is None:
                    continue
                # Verify author linkage in actual returned metadata; no name-based matches.
                if key.endswith(".id"):
                    linked = ident in record["author_ids"]
                else:
                    linked = any(
                        str((a.get("author") or {}).get("orcid") or "").upper().endswith(ident)
                        for a in work.get("authorships") or [] if isinstance(a, dict)
                    )
                if not linked:
                    warnings.append("Author identity not verifiable in returned metadata: " + record["paper_id"])
                    continue
                for group in entry.get("source_groups", []):
                    if group not in SOURCE_GROUPS:
                        raise ValueError("invalid author source group")
                    _join_record(records, doi_index, record, group, {
                        "kind": "author", "author_id": ident, "group": group,
                    })
        except (ValueError, RuntimeError) as exc:
            author_coverage["failed"].append({"author_id": identifier, "reason": str(exc)[:180]})
    counts = {group: sum(group in p["source_groups"] for p in records.values())
              for group in SOURCE_GROUPS}
    sampled = list(records.values())
    status = "complete" if (
        all(not c["failed_sources"] for c in coverage.values()) and
        not author_coverage["failed"] and
        all(c["attempted_venues"] == c["configured_venues"] for c in coverage.values())
        and not warnings
    ) else "partial"
    fingerprint = hashlib.sha256(
        json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "0.2.0",
        "feed_kind": "atlas_three_source_public_evidence",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "lookback_start": since,
        "lookback_end": today.isoformat(),
        "source_plan_sha256": fingerprint,
        "status": status,
        "coverage": {"source_groups": coverage, "authors": author_coverage,
                     "group_distinct_papers": counts,
                     "global_unique_papers": len(sampled),
                     "sampled_not_full_population": True},
        "papers": sampled,
        "warnings": warnings,
        "caveats": [
            "Venue and author priorities are not a complete field census.",
            "Sampling caps and OpenAlex indexing may omit important papers.",
            "Abstract records may be truncated or absent; full text is not downloaded.",
            "Publication venue metadata and scientific novelty are not independently verified.",
            "AI synthesis and human review are separate steps.",
        ],
    }
