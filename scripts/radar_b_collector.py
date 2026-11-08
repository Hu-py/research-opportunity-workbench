"""Radar B: independently collect public CS/AI method-paper evidence.

GitHub owns discovery, retrieval and provenance. Scientific novelty, paper
selection, method transfer and team matching are reserved for the Business Agent.
The exported feed contains no team profile, model scores, API key or private data.
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
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

CONFIG = Path("config/radar_b_sources.json")
OUTPUT = Path("data/radar/radar_b_latest.json")
OA_API = "https://api.openalex.org"
ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
RETRY_CODES = {429, 500, 502, 503, 504}


def http_payload(url, *, parse="json", attempts=3):
    """Fail without logging a URL (OpenAlex URLs contain an API key)."""
    request = Request(url, headers={
        "Accept": "application/json" if parse == "json" else "application/atom+xml",
        "User-Agent": "CUSP-Research-RadarB/1.0 (scholarly metadata collection)",
    })
    failure = "UnknownFailure"
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=40) as response:
                body = response.read()
            return json.loads(body) if parse == "json" else ET.fromstring(body)
        except HTTPError as error:
            failure = f"HTTP {error.code}"
            if error.code not in RETRY_CODES:
                break
        except Exception as error:
            failure = type(error).__name__
        if attempt + 1 < attempts:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(failure)


def openalex(endpoint, params):
    key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENALEX_API_KEY is missing")
    payload = http_payload(OA_API + endpoint + "?" + urlencode(dict(params, api_key=key)))
    if not isinstance(payload, dict):
        raise ValueError("Unexpected OpenAlex response")
    return payload


def canonical_name(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def short_id(value):
    return str(value or "").rsplit("/", 1)[-1]


def resolve_source(source_config):
    names = [source_config["name"]] + source_config.get("aliases", [])
    found = {}
    for candidate_name in names:
        results = openalex("/sources", {"search": candidate_name, "per-page": 10}).get("results") or []
        forms = {canonical_name(name) for name in names}
        for candidate in results:
            if canonical_name(candidate.get("display_name")) in forms:
                identifier = short_id(candidate.get("id"))
                if re.fullmatch(r"S\d+", identifier):
                    found[identifier] = candidate.get("display_name")
        if len(found) == 1:
            break
    if len(found) != 1:
        return None, "Ambiguous or unresolved exact source"
    return next(iter(found)), None


def extract_abstract(index, max_chars=650):
    """Short evidence excerpt, not a claim of full-text or full-abstract reading."""
    if not isinstance(index, dict):
        return None
    placements = []
    for word, locations in index.items():
        if not isinstance(locations, list):
            continue
        for location in locations:
            if isinstance(location, int) and 0 <= location < 10000:
                placements.append((location, str(word)))
    if not placements:
        return None
    excerpt = " ".join(word for _, word in sorted(placements))
    return excerpt[:max_chars].rstrip() + ("…" if len(excerpt) > max_chars else "")


def normalize_doi(value):
    raw = str(value or "").strip()
    return raw.lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def title_key(title):
    text = unicodedata.normalize("NFKC", str(title or "")).casefold()
    return re.sub(r"[^\w]+", "", text) if len(text) >= 30 else ""


def normalize_openalex(work, source_name, cutoff, excluded):
    if not isinstance(work, dict) or work.get("is_retracted"):
        return None
    if str(work.get("type") or "").lower() in excluded:
        return None
    date = str(work.get("publication_date") or "")[:10]
    if not date or date < cutoff:
        return None
    title = str(work.get("title") or "").strip()
    if not title:
        return None
    topic = work.get("primary_topic") or {}
    location = work.get("primary_location") or {}
    best_oa = work.get("best_oa_location") or {}
    authorships = work.get("authorships") or []
    authors = [(auth.get("author") or {}).get("display_name")
               for auth in authorships[:8] if isinstance(auth, dict)]
    abstract = extract_abstract(work.get("abstract_inverted_index"))
    return {
        "openalex_id": work.get("id"),
        "arxiv_id": None,
        "doi": work.get("doi"),
        "title": title[:750],
        "publication_date": date,
        "work_type": work.get("type"),
        "authors": [a for a in authors if a],
        "academic_source": source_name,
        "source_kind": "openalex_venue",
        "method_category": None,
        "primary_topic_id": short_id(topic.get("id")) if topic.get("id") else None,
        "primary_topic": topic.get("display_name"),
        "abstract_excerpt": abstract,
        "abstract_available": bool(abstract),
        "paper_url": (location.get("landing_page_url") or work.get("doi") or work.get("id")),
        "pdf_url": (best_oa.get("pdf_url") or location.get("pdf_url")),
        "code_url": None,
        "evidence_level": "metadata_with_abstract_excerpt" if abstract else "metadata_only",
        "publication_status": "OpenAlex indexed; venue metadata not independently publisher-verified",
        "provenance": ["openalex"],
    }


def openalex_recent(source_id, name, since, count, excluded):
    fields = ("id,title,doi,publication_date,type,authorships,primary_topic,"
              "primary_location,best_oa_location,is_retracted,abstract_inverted_index")
    response = openalex("/works", {
        "filter": f"primary_location.source.id:{source_id},from_publication_date:{since}",
        "sort": "publication_date:desc",
        "per-page": min(100, max(1, count)),
        "select": fields,
    })
    results = response.get("results")
    if not isinstance(results, list):
        raise ValueError("Missing OpenAlex results")
    return [record for record in
            (normalize_openalex(work, name, since, excluded) for work in results)
            if record is not None]


def arxiv_recent(group, since):
    categories = group["categories"]
    terms = " OR ".join("cat:" + category for category in categories)
    query = urlencode({
        "search_query": terms,
        "start": "0",
        "max_results": min(100, max(1, int(group.get("max_results", 40)))),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    root = http_payload(ARXIV_API + "?" + query, parse="xml", attempts=2)
    results = []
    for entry in root.findall(ATOM + "entry"):
        published = (entry.findtext(ATOM + "published") or "")[:10]
        if not published or published < since:
            continue
        url = (entry.findtext(ATOM + "id") or "").strip()
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", url)
        if not match:
            continue
        arxiv_id = match.group(1).removesuffix(".pdf")
        title = " ".join((entry.findtext(ATOM + "title") or "").split())
        if not title:
            continue
        abstract = " ".join((entry.findtext(ATOM + "summary") or "").split())
        excerpt = abstract[:650].rstrip() + ("…" if len(abstract) > 650 else "")
        authors = [e.findtext(ATOM + "name") for e in entry.findall(ATOM + "author")]
        primary_category = entry.find(ARXIV + "primary_category")
        code_match = re.search(r"https?://github\.com/[\w.\-]+/[\w.\-]+", abstract)
        pdf_url = None
        for link in entry.findall(ATOM + "link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break
        doi = entry.findtext(ARXIV + "doi")
        results.append({
            "openalex_id": None,
            "arxiv_id": arxiv_id,
            "doi": "https://doi.org/" + doi.strip() if doi else None,
            "title": title[:750],
            "publication_date": published,
            "work_type": "preprint",
            "authors": [a for a in authors if a],
            "academic_source": "arXiv",
            "source_kind": "arxiv_preprint",
            "method_category": primary_category.get("term") if primary_category is not None else None,
            "primary_topic_id": None,
            "primary_topic": None,
            "abstract_excerpt": excerpt or None,
            "abstract_available": bool(excerpt),
            "paper_url": "https://arxiv.org/abs/" + arxiv_id,
            "pdf_url": pdf_url or "https://arxiv.org/pdf/" + arxiv_id,
            "code_url": code_match.group(0) if code_match else None,
            "evidence_level": "metadata_with_abstract_excerpt" if excerpt else "metadata_only",
            "publication_status": "preprint; not peer review verified",
            "provenance": ["arxiv"],
        })
    return results


def merge_papers(openalex_papers, arxiv_papers, max_total):
    """Conservative DOI and exact-normalized-title dedup, no fuzzy deletions."""
    merged = []
    lookup = {}
    for paper in openalex_papers + arxiv_papers:
        identifiers = []
        doi = normalize_doi(paper.get("doi"))
        if doi:
            identifiers.append("doi:" + doi)
        if paper.get("arxiv_id"):
            identifiers.append("arxiv:" + paper["arxiv_id"].lower())
        if paper.get("openalex_id"):
            identifiers.append("oa:" + short_id(paper["openalex_id"]))
        tk = title_key(paper.get("title"))
        if tk:
            identifiers.append("title:" + tk)
        existing = next((lookup[key] for key in identifiers if key in lookup), None)
        if existing is not None:
            # Enrich records but avoid silently overwriting a substantive field.
            for field in ("openalex_id", "arxiv_id", "doi", "code_url", "pdf_url"):
                if not merged[existing].get(field) and paper.get(field):
                    merged[existing][field] = paper[field]
            if len(paper.get("abstract_excerpt") or "") > len(merged[existing].get("abstract_excerpt") or ""):
                merged[existing]["abstract_excerpt"] = paper["abstract_excerpt"]
                merged[existing]["abstract_available"] = True
                merged[existing]["evidence_level"] = "metadata_with_abstract_excerpt"
            merged[existing]["provenance"] = sorted(
                set(merged[existing]["provenance"] + paper["provenance"])
            )
        elif len(merged) < max_total:
            merged.append(dict(paper))
            existing = len(merged) - 1
        else:
            continue
        for key in identifiers:
            lookup[key] = existing
    return sorted(merged, key=lambda p: p.get("publication_date") or "", reverse=True)


def annual_counts(topic_id, years):
    result = openalex("/works", {
        "filter": f"primary_topic.id:{topic_id},publication_year:{years[0]}-{years[-1]}",
        "group_by": "publication_year",
    })
    groups = result.get("group_by")
    if not isinstance(groups, list):
        raise ValueError("Missing annual grouping")
    counts = {str(year): 0 for year in years}
    for group in groups:
        yr = str(group.get("key") or "")
        if yr in counts:
            counts[yr] = int(group["count"])
    return counts


def round_robin(lists, cap):
    out = []
    for i in range(max(map(len, lists), default=0)):
        for group in lists:
            if i < len(group):
                out.append(group[i])
                if len(out) >= cap:
                    return out
    return out


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    since = (now.date() - timedelta(days=int(config["lookback_days"]))).isoformat()
    years = [now.year - 3, now.year - 2, now.year - 1]
    excluded = set(config.get("non_research_work_types", []))
    warnings = []
    venue_results, arxiv_results = [], []
    venue_status, arxiv_status = [], []

    for source in config["openalex_sources"]:
        label = source["name"]
        try:
            sid, problem = resolve_source(source)
            if not sid:
                venue_status.append({"name": label, "status": "unresolved", "detail": problem})
                continue
            papers = openalex_recent(
                sid, label, since, int(config["per_source_sample"]), excluded
            )
            venue_results.append(papers)
            venue_status.append({"name": label, "status": "ok", "source_id": sid,
                                 "sample_count": len(papers)})
        except Exception as exc:
            venue_status.append({"name": label, "status": "error", "detail": str(exc)})
            warnings.append(f"OpenAlex source {label} failed: {exc}")
    print("OpenAlex venues", sum(v["status"] == "ok" for v in venue_status),
          "/", len(venue_status), "collected", sum(len(x) for x in venue_results))

    for group in config["arxiv_category_groups"]:
        try:
            papers = arxiv_recent(group, since)
            arxiv_results.append(papers)
            arxiv_status.append({"name": group["name"], "status": "ok",
                                 "sample_count": len(papers)})
        except Exception as exc:
            arxiv_status.append({"name": group["name"], "status": "error", "detail": str(exc)})
            warnings.append(f"arXiv group {group['name']} failed: {exc}")
        time.sleep(3.0)  # arXiv asks consumers not to send rapid consecutive requests.
    print("arXiv groups", sum(v["status"] == "ok" for v in arxiv_status),
          "/", len(arxiv_status), "collected", sum(len(x) for x in arxiv_results))

    oa = round_robin(venue_results, int(config["max_openalex_records"]))
    ax = round_robin(arxiv_results, int(config["max_arxiv_records"]))
    papers = merge_papers(oa, ax, int(config["max_public_records"]))
    if not papers:
        raise RuntimeError("No method-paper records; refuse to publish empty dataset")

    frequency = Counter(p["primary_topic_id"] for p in oa if p.get("primary_topic_id"))
    topic_names = {p["primary_topic_id"]: p.get("primary_topic")
                   for p in oa if p.get("primary_topic_id")}
    topics = []
    for topic_id, count in frequency.most_common(int(config["annual_topic_count_limit"])):
        row = {
            "topic_id": topic_id, "name": topic_names.get(topic_id),
            "observed_openalex_sample_count": count,
            "annual_counts": None, "growth_latest_complete_year_pct": None,
            "status": "not_verified",
        }
        try:
            counts = annual_counts(topic_id, years)
            previous, current = counts[str(years[-2])], counts[str(years[-1])]
            row.update(
                annual_counts=counts,
                growth_latest_complete_year_pct=round(100 * (current - previous) / previous, 2)
                if previous else None,
                status="measured",
            )
        except Exception as exc:
            warnings.append(f"Topic {topic_id} trend unavailable: {exc}")
        topics.append(row)

    feed = {
        "schema_version": "1.0.0",
        "feed_kind": "radar_b_public_method_evidence",
        "retrieved_at_utc": now.isoformat(),
        "lookback_start": since,
        "complete_publication_years": years,
        "source_config_path": str(CONFIG),
        "selection_policy": "Broad sources and categories, round-robin source coverage, separate OpenAlex/arXiv quotas, and no model-based quality/novelty ranking.",
        "agent_responsibility": "Agent must select methods, verify source content, challenge novelty, judge team fit and propose urban-science transfer.",
        "coverage": {
            "openalex_sources": venue_status, "arxiv_groups": arxiv_status,
            "openalex_sampled": len(oa), "arxiv_sampled": len(ax),
            "total_after_cross_source_dedup": len(papers),
            "with_abstract_excerpt": sum(bool(p.get("abstract_excerpt")) for p in papers),
            "with_pdf_link": sum(bool(p.get("pdf_url")) for p in papers),
            "with_code_link": sum(bool(p.get("code_url")) for p in papers),
        },
        "candidate_topic_statistics": topics,
        "recent_method_papers": papers,
        "warnings": warnings,
        "caveats": [
            "Sampled-source popularity is NOT scientific importance or a novelty score.",
            "OpenAlex publication date and source indexing may be incomplete or delayed.",
            "Only short abstract excerpts are included; full abstract/full text must be independently retrieved.",
            "arXiv entries are preprints, not peer-review-confirmed publications.",
            "Source resolution uses exact accepted names; unresolved venues remain visible.",
            "New/uncommon methods may fall outside source pools and category groups.",
            "No private team, ledger or research ideas are published to this public feed.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Radar B feed written:", OUTPUT, "papers", len(papers), "topics", len(topics),
          "warnings", len(warnings))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Radar B collection failed:", str(exc), file=sys.stderr)
        sys.exit(1)
