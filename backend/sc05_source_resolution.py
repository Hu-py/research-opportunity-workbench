"""R7.2: auditably resolve owner-approved venues to real OpenAlex source IDs.

The source catalog controls which names MAY be queried. The OpenAlex /sources
response controls which IDs actually exist. No model-invented source IDs, broad
venue auto-approval, or best-effort guessing are allowed.

One-time per new baseline run; freeze the exact IDs and audit with source facts
for the other arm. A retrieval failure MUST NOT be treated as no prior art.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable

import httpx

from backend.sc05_source_policy import (
    source_catalog, source_tier, resolved_openalex_source_ids,
)

VERSION = "sc05-openalex-exact-source-resolution-v1"
LIMIT_BY_TIER = {"A": 2, "B": 2, "D": 10, "C": 4}
TIERS = ("A", "B", "D", "C")
SOURCE_ID = re.compile(r"^S[0-9]+$")


def _source_id(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.startswith("https://openalex.org/"):
        raw = raw.rsplit("/", 1)[-1]
    return raw if SOURCE_ID.fullmatch(raw) else ""


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _real_openalex_lookup(name: str) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"search": name, "per-page": 15}
    if os.getenv("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    if os.getenv("OPENALEX_MAILTO"):
        params["mailto"] = os.environ["OPENALEX_MAILTO"]
    with httpx.Client(timeout=12, headers={
        "User-Agent": "research-opportunity-workbench/0.1"
    }) as http:
        response = http.get("https://api.openalex.org/sources", params=params)
        response.raise_for_status()
        body = response.json()
    return body.get("results", []) if isinstance(body, dict) else []


def resolve_sources(
    registry: list[dict[str, Any]] | None,
    domain: str,
    *,
    search_sources: Callable[[str], list[dict[str, Any]]] | None = None,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    """Resolve exact catalog names only; keep failures nonfatal and visible.

    An enabled owner source with a real-looking OpenAlex ID is treated as
    already verified by the owner source catalog, consistent with R7.0.
    Remaining names must match OpenAlex source display_name exactly after
    punctuation/case normalization. Ambiguous exact matches are not promoted.
    """
    catalog = source_catalog()
    source_names = {}
    for tier in ("A", "B", "C"):
        source_names[tier] = catalog["streams"][tier]["venues"][:LIMIT_BY_TIER[tier]]
    source_names["D"] = catalog.get("direct_comparison_domain_pools", {}).get(
        domain, [])[:LIMIT_BY_TIER["D"]]
    ids = resolved_openalex_source_ids(registry, domain)
    owner_by_name = {}
    for row in registry or []:
        if not isinstance(row, dict) or row.get("enabled") is False:
            continue
        sid = _source_id(row.get("openalex_source_id"))
        if not sid:
            continue
        metadata = source_tier(row.get("name"), domain)
        canonical = metadata.get("canonical_venue")
        if canonical and metadata.get("tier") in TIERS:
            owner_by_name[_key(canonical)] = sid

    lookup = search_sources or _real_openalex_lookup
    found = []
    unresolved = []
    errors = []
    registry_count = 0
    lookup_count = 0
    for tier in TIERS:
        for venue in source_names[tier]:
            owner_id = owner_by_name.get(_key(venue), "")
            if owner_id:
                registry_count += 1
                if owner_id not in ids[tier]:
                    ids[tier].append(owner_id)
                found.append({"tier": tier, "venue": venue,
                              "id": owner_id, "provenance": "owner_registry"})
                continue
            try:
                candidates = lookup(venue)
            except (httpx.HTTPError, TimeoutError, ValueError, TypeError) as exc:
                # Deliberately no raw exception: it can include API keys in URLs.
                errors.append({"tier": tier, "venue": venue,
                               "error_type": type(exc).__name__})
                continue
            if not isinstance(candidates, list):
                errors.append({"tier": tier, "venue": venue,
                               "error_type": "INVALID_SOURCE_RESPONSE"})
                continue
            exact = {}
            for cand in candidates:
                if not isinstance(cand, dict):
                    continue
                sid = _source_id(cand.get("id"))
                if (sid and _key(cand.get("display_name")) == _key(venue)):
                    exact[sid] = cand
            if len(exact) == 1:
                sid = next(iter(exact))
                lookup_count += 1
                if sid not in ids[tier]:
                    ids[tier].append(sid)
                found.append({"tier": tier, "venue": venue,
                              "id": sid, "provenance": "OpenAlex_exact_display_name"})
            else:
                unresolved.append({"tier": tier, "venue": venue,
                                   "reason": "ambiguous_exact_ids" if exact else "no_exact_match"})
    return {tier: sorted(set(ids[tier])) for tier in ("A","B","C","D")}, {
        "version": VERSION,
        "owner_registered_exact_sources": registry_count,
        "openalex_exact_name_sources": lookup_count,
        "resolved": found,
        "unresolved": unresolved,
        "provider_errors": errors,
        "strict_exact_name": True,
        "source_id_claim_certified_by_human": False,
        "note": "Query source IDs come only from approved owner rows or an exact OpenAlex source-name match; missing A/B is a retrieval gap, never proof of a gap in science.",
    }
