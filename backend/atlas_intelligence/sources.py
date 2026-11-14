"""Three independent Research Atlas sources; never reuse legacy Radar A/B labels.

The source plan is a reviewable priority configuration. An OpenAlex venue
match is evidence of where a paper was found, not proof of its novelty,
quality, scientific topic, or fit with a team. Multiple groups are allowed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

SOURCE_GROUPS = (
    "planning_application",
    "urban_science",
    "computational_methods",
)

DEFAULT_PLAN = Path(__file__).resolve().parents[2] / "config" / "atlas_source_plan.json"

CS_DOMAINS = {
    "ai_ml", "data_mining", "cv_multimodal", "nlp", "agents_robotics",
    "hci", "graphics_visualization", "systems_software",
    "network_security", "computer_architecture", "theory_algorithms",
}
PLANNING_DOMAINS = {
    "urban_planning", "urban_environment", "transportation", "urban_health",
    "heritage", "water_disaster",
}
URBAN_SCIENCE_DOMAINS = {"gis_spatial"}


def _normal(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _fields(source: object) -> tuple[str, str, str, list[str]]:
    if isinstance(source, Mapping):
        raw = source
        aliases = raw.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        return (
            str(raw.get("name") or ""),
            str(raw.get("abbreviation") or ""),
            str(raw.get("domain") or ""),
            [str(x) for x in aliases],
        )
    aliases = getattr(source, "aliases", None)
    if aliases is None:
        try:
            aliases = json.loads(getattr(source, "aliases_json", "[]") or "[]")
        except (ValueError, TypeError):
            aliases = []
    if not isinstance(aliases, list):
        aliases = []
    return (
        str(getattr(source, "name", "") or ""),
        str(getattr(source, "abbreviation", "") or ""),
        str(getattr(source, "domain", "") or ""),
        [str(x) for x in aliases],
    )


def load_source_plan(path: str | Path | None = None) -> dict:
    """Load a versioned, explicit watchlist; fail on malformed configurations."""
    file = Path(path) if path else DEFAULT_PLAN
    payload = json.loads(file.read_text(encoding="utf-8"))
    groups = payload.get("source_groups")
    if not isinstance(groups, dict) or set(groups) != set(SOURCE_GROUPS):
        raise ValueError("source plan must define exactly the three Research Atlas groups")
    for group, data in groups.items():
        if not isinstance(data, dict) or not isinstance(data.get("venues"), list):
            raise ValueError("invalid venue list for source group " + group)
        if any(not isinstance(v, str) or not v.strip() for v in data["venues"]):
            raise ValueError("venue names must be nonempty strings")
    if not isinstance(payload.get("authors", []), list):
        raise ValueError("authors watchlist must be a list")
    for author in payload.get("authors", []):
        if not isinstance(author, dict) or not isinstance(author.get("author_id"), str):
            raise ValueError("author must have a stable identifier")
        if not set(author.get("source_groups", [])).issubset(SOURCE_GROUPS):
            raise ValueError("unknown group in author watchlist")
    return payload


def assign_source_groups(
    source: object,
    *,
    plan: dict | None = None,
    author_ids: list[str] | None = None,
) -> tuple[str, ...]:
    """Classify a venue or source row; explicit groups override domain fallback.

    Unknown venue and domain => no classification. Author watchlist may add
    groups but is never a substitute for verified author identifier matching.
    """
    plan = plan if plan is not None else load_source_plan()
    name, abbr, domain, aliases = _fields(source)
    identities = {_normal(x) for x in [name, abbr, *aliases] if x}
    groups = set()
    for group, setting in plan["source_groups"].items():
        if identities & {_normal(x) for x in setting["venues"]}:
            groups.add(group)
    if not groups:
        if domain in CS_DOMAINS:
            groups.add("computational_methods")
        elif domain in URBAN_SCIENCE_DOMAINS:
            groups.add("urban_science")
        elif domain in PLANNING_DOMAINS:
            groups.add("planning_application")
    author_keys = {_normal(x) for x in (author_ids or []) if x}
    for author in plan.get("authors", []):
        if _normal(author.get("author_id")) in author_keys:
            groups.update(author.get("source_groups", []))
    return tuple(group for group in SOURCE_GROUPS if group in groups)


def match_venue_groups(
    venue: str,
    registered_sources: list[object],
    *,
    plan: dict | None = None,
    author_ids: list[str] | None = None,
) -> tuple[str, ...]:
    """Match an actual indexed venue to a registered source, not by vague substring."""
    plan = plan if plan is not None else load_source_plan()
    key = _normal(venue)
    if not key:
        return ()
    matches = []
    for source in registered_sources:
        name, abbr, _domain, aliases = _fields(source)
        if key in {_normal(x) for x in [name, abbr, *aliases] if x}:
            matches.append(source)
    results = set()
    for match in matches:
        results.update(assign_source_groups(match, plan=plan, author_ids=author_ids))
    # An explicit watchlist item may not yet have a resolved registry row.
    if not matches:
        results.update(assign_source_groups({"name": venue}, plan=plan, author_ids=author_ids))
    return tuple(group for group in SOURCE_GROUPS if group in results)
