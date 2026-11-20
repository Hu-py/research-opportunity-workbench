"""Auditable, conservative domain gate for SC05 academic near-neighbor evidence.

This is a cheap, deterministic *screen*, not a scientific novelty classifier.
Out-of-domain records can inform a separate human-reviewed method-transfer lane;
they must not be described as verified closest prior work.
"""
from __future__ import annotations

import re
from typing import Any

# Small versioned ontology. A previously unknown field is deliberately left
# unresolved (rather than automatically treated as having no prior art).
DOMAIN_PROFILES: dict[str, dict[str, Any]] = {
    "urban_transport": {
        "query_anchor": "urban rail transit transportation",
        "strong": (
            "urban rail", "rail transit", "subway", "metro", "railway",
            "transport network", "transportation", "public transit",
            "passenger flow", "traffic flow", "station-level",
            "origin destination", "transit disruption", "urban mobility",
            "轨道交通", "地铁", "公共交通", "城市交通", "客流",
        ),
        "weak": (
            "mobility", "transit", "passenger", "traffic", "station",
            "commuter", "transport", "rail", "road", "corridor",
            "交通", "出行", "道路", "线路",
        ),
    },
    "water_hydrology": {
        "query_anchor": "hydrology water resources watershed",
        "strong": (
            "hydrology", "hydrological", "watershed", "river basin",
            "water balance", "stormwater", "groundwater", "water resources",
            "reservoir operation", "flood risk", "ecological water",
            "水文", "生态补水", "水量平衡", "流域", "水资源", "洪涝",
        ),
        "weak": ("river", "reservoir", "water", "flooding", "runoff",
                 "rainfall", "discharge", "湖泊", "降雨", "河流", "径流"),
    },
    "health_epidemiology": {
        "query_anchor": "public health epidemiology",
        "strong": (
            "public health", "epidemiology", "child health",
            "child development", "health outcome", "disease burden",
            "health exposure", "maternal health", "儿 童 健 康",
            "儿童健康", "儿童发育", "流行病学",
        ),
        "weak": (
            "health", "clinical", "patient", "children",
            "epidemiological", "morbidity", "mortality", "健康", "疾病",
        ),
    },
    "housing_real_estate": {
        "query_anchor": "housing markets urban land prices",
        "strong": (
            "house price", "housing price", "housing market",
            "real estate", "hedonic pricing", "housing affordability",
            "rental market", "房价", "住宅市场", "享乐价格", "住房可负担",
        ),
        "weak": ("housing", "property", "rent", "land price",
                 "amenity", "住房", "租赁", "房地产", "地价"),
    },
    "urban_environment": {
        "query_anchor": "urban built environment city planning",
        "strong": (
            "built environment", "urban planning", "urbanization",
            "urbanisation", "urban morphology", "land use change",
            "urban spatial structure", "vertical urbanism",
            "建成环境", "城市规划", "城市形态", "城市化", "城市空间",
        ),
        "weak": ("cities", "urban", "city", "spatial",
                 "neighborhood", "街区", "用地", "城区"),
    },
}

POLICY_VERSION = "sc05-domain-nearest-v1"


def _matches(content: str, terms: tuple[str, ...]) -> list[str]:
    text = content.casefold()
    hits = []
    for term in terms:
        term = term.casefold()
        if re.search(r"[a-z]", term):
            # Never match 'station' inside 'manifestation', etc.
            pattern = r"(?<![a-z])" + re.escape(term) + r"(?![a-z])"
            if re.search(pattern, text):
                hits.append(term)
        elif term in text:
            hits.append(term)
    return hits


def infer_source_domain(pages: dict[str, str]) -> dict[str, Any]:
    """Infer a *candidate* domain from article body, not search results."""
    corpus = " ".join(str(text)[:4400] for text in list(pages.values())[:8])
    ranked = []
    for code, spec in DOMAIN_PROFILES.items():
        strong = _matches(corpus, spec["strong"])
        weak = _matches(corpus, spec["weak"])
        ranked.append((3 * len(strong) + len(weak), len(strong), code, strong, weak))
    ranked.sort(reverse=True)
    score, n_strong, code, strong, weak = ranked[0]
    if score < 3 or (n_strong == 0 and len(weak) < 3):
        return {
            "code": "unresolved", "confidence": "unresolved",
            "query_anchor": "", "source_signals": [],
            "policy": POLICY_VERSION,
        }
    # Do not overclaim precision from a small fixed terminology set.
    return {
        "code": code, "confidence": "heuristic",
        "query_anchor": DOMAIN_PROFILES[code]["query_anchor"],
        "source_signals": (strong + weak)[:16],
        "policy": POLICY_VERSION,
    }


def anchored_query(query: str, profile: dict[str, Any]) -> str:
    """Keep the model's evidence question but anchor broad searches to its field."""
    raw = str(query).strip()[:350]
    if profile.get("code") not in DOMAIN_PROFILES or not raw:
        return raw
    spec = DOMAIN_PROFILES[profile["code"]]
    if _matches(raw, spec["strong"]):
        return raw
    return (spec["query_anchor"] + " " + raw)[:400]


def _doi(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    raw = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", raw)
    return raw.removeprefix("doi:")


def screen_candidate_papers(
    papers: list[dict], profile: dict[str, Any], *,
    source_doi: str = "",
) -> tuple[list[dict], dict[str, Any]]:
    """Exclude unrelated work from direct-comparison context, but audit loss.

    Domain detection can have false negatives. Quarantined records can be
    inspected by a researcher; they are never silently labeled 'prior work'.
    """
    domain = profile.get("code", "unresolved")
    spec = DOMAIN_PROFILES.get(domain)
    accepted = []
    rejected = []
    for row in papers:
        reason = ""
        if source_doi and _doi(row.get("doi")) == _doi(source_doi):
            reason = "source_paper_not_independent_prior"
        elif not str(row.get("abstract") or "").strip():
            reason = "abstract_absent_cannot_verify"
        elif spec:
            content = (
                str(row.get("title") or "") + " " +
                str(row.get("abstract") or "")
            )
            strong = _matches(content, spec["strong"])
            weak = _matches(content, spec["weak"])
            if not strong and len(weak) < 2:
                reason = "out_of_domain_or_unsupported_transfer"
        if reason:
            rejected.append({
                "paper_id": str(row.get("id") or "")[:255],
                "title": str(row.get("title") or "")[:180],
                "reason": reason,
            })
            continue
        # An unknown field is not evidence that every hit is relevant.
        # Retain for assessment but disallow nearest-prior certification.
        status = "domain_match" if spec else "domain_unresolved"
        accepted.append({
            **row,
            "domain_screen_status": status,
            "eligible_for_nearest_prior": bool(spec),
        })
    audit = {
        "policy_version": POLICY_VERSION,
        "source_domain": domain,
        "source_domain_confidence": profile.get("confidence", "unresolved"),
        "retrieved": len(papers),
        "accepted": len(accepted),
        "quarantined": len(rejected),
        "quarantined_records": rejected[:35],
        "note": (
            "Domain matching is only a conservative text screen; "
            "it never certifies novelty, temporality or method equivalence. "
            "Out-of-domain hits require a separate explicit method-transfer review."
        ),
    }
    return accepted, audit


def screen_route_prior_claims(
    raw_routes: dict, accepted_papers: list[dict],
    literature_assessments: list[dict],
) -> tuple[dict, dict[str, Any]]:
    """Only close + verified + directly explained papers can be cited as near.

    Indirect cross-domain method inspirations are *not* automatically true
    closest scientific precedents. This is a minimum check, not proof of overlap.
    """
    if not isinstance(raw_routes, dict) or not isinstance(raw_routes.get("routes"), list):
        return raw_routes, {"removed_reference_count": 0, "removed": []}
    paper_map = {p["id"]: p for p in accepted_papers}
    eligible = set()
    for item in literature_assessments:
        pid = item.get("paper_id")
        p = paper_map.get(pid)
        if not p or not p.get("eligible_for_nearest_prior"):
            continue
        if item.get("evidence_status") != "abstract_quote_verified":
            continue
        if item.get("relevance") != "close":
            continue
        if any(
            link.get("relation_type") in ("direct", "counterexample") and
            isinstance(link.get("relation_explanation"), str) and
            len(link["relation_explanation"].strip()) >= 12 and
            not link["relation_explanation"].startswith("旧版输出")
            for link in item.get("diagnosis_links", [])
        ):
            eligible.add(pid)

    removed = []
    routes = []
    for pos, route in enumerate(raw_routes["routes"], 1):
        if not isinstance(route, dict) or not isinstance(route.get("closest_paper_ids"), list):
            routes.append(route)  # Preserve structural errors for existing validator.
            continue
        original = route["closest_paper_ids"]
        retained = [pid for pid in original if pid in eligible]
        disallowed = [pid for pid in original if pid not in eligible]
        if disallowed:
            removed.append({
                "route_position": pos,
                "route_id": str(route.get("id") or "")[:30],
                "removed_paper_ids": disallowed[:12],
                "reason": "no_close_abstract_verified_domain_matched_direct_or_counterexample_link",
            })
        routes.append({**route, "closest_paper_ids": retained})
    audit = {
        "policy_version": POLICY_VERSION,
        "minimum_evidence_eligible_paper_ids": sorted(eligible),
        "removed_reference_count": sum(len(x["removed_paper_ids"]) for x in removed),
        "removed": removed,
        "note": "Retained references remain provisional; source-date order and scientific novelty are not certified.",
    }
    return {**raw_routes, "routes": routes}, audit
