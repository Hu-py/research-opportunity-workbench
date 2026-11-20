"""SC05 R7.1: evidence-linked synthesis of routes into a research agenda.

The generator is untrusted. This module validates identifiers and structural
claims, and keeps scientific merit, novelty and feasibility UNVERIFIED.
There is no implicit route invention, auto-citation, or extra model call.
"""
from __future__ import annotations

from typing import Any

VERSION = "sc05-research-agenda-v1"
AGENDA_ROLES = frozenset({"phenomenon", "mechanism", "boundary", "planning_decision"})
AGENDA_FIELDS = (
    "title",
    "central_question",
    "empirical_tension",
    "mechanism_synthesis",
    "integration_rationale",
    "why_independent_paper",
    "planning_decision",
    "boundary_conditions",
    "failure_condition",
)

AGENDA_SCHEMA = {"research_agendas": [{
    "id": "A01",
    "title": "A single scientific claim, not a list of unrelated gaps",
    "route_ids": ["R01", "R02"],
    "source_fact_ids": ["F001"],
    "central_question": "What broader mechanism is unknown?",
    "empirical_tension": "Source-paper observations that motivate competing explanations",
    "mechanism_synthesis": "At least two distinguishable rival mechanisms and their interactions",
    "integration_rationale": "Why the linked routes form one argument and cannot stand alone",
    "why_independent_paper": "New scope and contribution, not an appended robustness section",
    "planning_decision": "Who changes which planning decision if the claim holds",
    "boundary_conditions": "Contexts where the mechanism may fail, without presuming new data",
    "failure_condition": "Evidence that would refute the entire integrated claim",
    "study_sequence": [{
        "route_id": "R01",
        "role": "phenomenon|mechanism|boundary|planning_decision",
        "discriminating_test": "Independent test with an outcome and a competing explanation",
        "contributes_to_claim": "How this study supports or refutes the central question",
    }],
}]}

AGENDA_REVIEW_SCHEMA = {"agenda_reviews": [{
    "agenda_id": "A01",
    "verdict": "test|hold|reject",
    "strongest_objection": "Most serious threat to the entire independent paper claim",
    "nearest_prior_overlap": "Whether a specific prior work already addresses the central claim",
    "integration_risk": "What is disconnected or would remain a set of substudies",
    "minimum_discriminating_evidence": "Evidence that would change the verdict",
}]}


def _text(value: Any, minimum: int = 18, maximum: int = 1500) -> bool:
    return isinstance(value, str) and minimum <= len(value.strip()) <= maximum


def validate_agenda_proposals(
    raw: Any, routes: list[dict[str, Any]], facts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Quarantine hallucinated or non-integrated drafts; do not repair model IDs.

    A single route may anchor a paper if it contains multiple complementary
    studies. Two linked routes alone do not establish a coherent paper.
    """
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        return [], {"version": VERSION, "proposed": 0, "accepted": 0,
                    "rejected": [{"position": 0, "code": "AGENDA_NOT_LIST"}]}
    known_routes = {r["id"] for r in routes}
    known_facts = {f["fact_id"] for f in facts}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used = set()
    for pos, item in enumerate(raw[:2], 1):
        if not isinstance(item, dict):
            rejected.append({"position": pos, "code": "AGENDA_NOT_OBJECT"})
            continue
        aid = item.get("id")
        if aid not in ("A01", "A02") or aid in used:
            rejected.append({"position": pos, "code": "AGENDA_ID_INVALID_OR_DUPLICATE"})
            continue
        used.add(aid)
        route_ids = item.get("route_ids")
        fact_ids = item.get("source_fact_ids")
        if (not isinstance(route_ids, list) or not route_ids or len(route_ids) > 4
                or not all(isinstance(x, str) for x in route_ids)
                or len(set(route_ids)) != len(route_ids)
                or not set(route_ids) <= known_routes):
            rejected.append({"position": pos, "code": "AGENDA_ROUTE_REFERENCE_INVALID"})
            continue
        if (not isinstance(fact_ids, list) or not fact_ids or len(fact_ids) > 12
                or not all(isinstance(x, str) for x in fact_ids)
                or len(set(fact_ids)) != len(fact_ids)
                or not set(fact_ids) <= known_facts):
            rejected.append({"position": pos, "code": "AGENDA_SOURCE_FACT_INVALID"})
            continue
        if any(not _text(item.get(key)) for key in AGENDA_FIELDS):
            rejected.append({"position": pos, "code": "AGENDA_STORY_INCOMPLETE"})
            continue
        studies = item.get("study_sequence")
        if not isinstance(studies, list) or not 2 <= len(studies) <= 4:
            rejected.append({"position": pos, "code": "AGENDA_NEEDS_COMPLEMENTARY_STUDIES"})
            continue
        normalized = []
        pairs = set()
        valid = True
        for study in studies:
            if not isinstance(study, dict):
                valid = False
                break
            rid, role = study.get("route_id"), study.get("role")
            if (rid not in route_ids or role not in AGENDA_ROLES
                    or (rid, role) in pairs
                    or not _text(study.get("discriminating_test"))
                    or not _text(study.get("contributes_to_claim"))):
                valid = False
                break
            pairs.add((rid, role))
            normalized.append({
                "route_id": rid,
                "role": role,
                "discriminating_test": study["discriminating_test"].strip(),
                "contributes_to_claim": study["contributes_to_claim"].strip(),
            })
        roles = {s["role"] for s in normalized}
        if (not valid or not set(route_ids) <= {s["route_id"] for s in normalized}
                or "mechanism" not in roles or len(roles) < 2):
            rejected.append({"position": pos, "code": "AGENDA_STUDY_CHAIN_INVALID"})
            continue
        accepted.append({
            "id": aid,
            **{key: item[key].strip() for key in AGENDA_FIELDS},
            "route_ids": list(route_ids),
            "source_fact_ids": list(fact_ids),
            "study_sequence": normalized,
            "scientific_novelty_verified": False,
            "human_review_required": True,
        })
    if len(raw) > 2:
        rejected.append({"position": 3, "code": "AGENDA_OVER_TWO_LIMIT",
                         "count": len(raw) - 2})
    return accepted, {
        "version": VERSION, "proposed": len(raw), "accepted": len(accepted),
        "rejected": rejected,
        "note": "An agenda is a structured hypothesis, never a certified paper.",
    }


def validate_agenda_reviews(
    raw: Any, agendas: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Independent reviewer must explicitly assess every agenda to promote it."""
    if raw is None:
        raw = []
    allowed = {a["id"] for a in agendas}
    reviews: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen = set()
    if not isinstance(raw, list):
        return [], {"rejected": [{"code": "AGENDA_REVIEWS_NOT_LIST"}],
                    "unreviewed_agenda_ids": sorted(allowed)}
    for pos, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            rejected.append({"position": pos, "code": "AGENDA_REVIEW_NOT_OBJECT"})
            continue
        aid = item.get("agenda_id")
        if aid not in allowed or aid in seen:
            rejected.append({"position": pos, "code": "AGENDA_REVIEW_REFERENCE_INVALID"})
            continue
        seen.add(aid)
        if (item.get("verdict") not in ("test", "hold", "reject")
                or any(not _text(item.get(k), 12, 1200) for k in (
                    "strongest_objection", "nearest_prior_overlap",
                    "integration_risk", "minimum_discriminating_evidence"))):
            rejected.append({"position": pos, "code": "AGENDA_REVIEW_INCOMPLETE"})
            continue
        reviews.append({
            "agenda_id": aid, "verdict": item["verdict"],
            **{k: item[k].strip() for k in (
                "strongest_objection", "nearest_prior_overlap",
                "integration_risk", "minimum_discriminating_evidence")},
        })
    return reviews, {
        "reviewed": len(reviews),
        "unreviewed_agenda_ids": sorted(allowed - {x["agenda_id"] for x in reviews}),
        "rejected": rejected,
    }


def audit_agendas(
    agendas: list[dict[str, Any]],
    agenda_reviews: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    route_reviews: list[dict[str, Any]],
    source_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """No model or automatic scores. Evidence and review are separate gates."""
    source_audit = source_audit or {}
    route_map = {r["id"]: r for r in routes}
    route_verdicts = {r["route_id"]: r["verdict"] for r in route_reviews}
    reviewer = {r["agenda_id"]: r for r in agenda_reviews}
    tiers = set(source_audit.get("direct_tiers_with_candidates", []))
    planning_coverage = {"A", "B"} <= tiers
    results = []
    for agenda in agendas:
        rids = agenda["route_ids"]
        row = reviewer.get(agenda["id"], {})
        verdict = row.get("verdict", "unreviewed")
        blocking = []
        if not planning_coverage:
            blocking.append("PLANNING_A_B_EVIDENCE_INCOMPLETE")
        if not any(route_map[x].get("closest_paper_ids") for x in rids):
            blocking.append("DIRECT_PRIOR_NOT_SUPPORTED")
        if verdict != "test":
            blocking.append("AGENDA_INDEPENDENT_CRITIC_NOT_APPROVED")
        if any(route_verdicts.get(x) != "test" for x in rids):
            blocking.append("COMPONENT_ROUTE_NOT_TEST_READY")
        # These are only necessary checks, not a claim of scientific novelty.
        results.append({
            "agenda_id": agenda["id"],
            "reviewer_verdict": verdict,
            "linked_route_count": len(rids),
            "evidence_source_fact_count": len(agenda["source_fact_ids"]),
            "editorial_status": (
                "provisional_for_human_review" if not blocking
                else "held_for_evidence_or_revision"
            ),
            "blocking_codes": blocking,
            "scientific_novelty_verified": False,
            "field_validity_not_scientific_merit": True,
        })
    return {
        "version": VERSION,
        "proposed_agendas": len(agendas),
        "reviewed_agendas": len(agenda_reviews),
        "provisional_for_human_review": sum(
            x["editorial_status"] == "provisional_for_human_review" for x in results
        ),
        "agendas": results,
        "no_compulsory_agenda": len(agendas) == 0,
        "scientific_novelty_verified": False,
        "real_world_feasibility_verified": False,
        "note": "Even a provisionally reviewed agenda requires independent expert comparison to real prior work.",
    }
