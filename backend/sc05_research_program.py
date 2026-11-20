"""SC05 publication-scale research-program audit, separate from correctness.

A complete field is an auditable *proposal*, not proof that a study is novel,
feasible, causally identified or of publication quality. Do not increase an
automatic numerical science score merely because the model writes more words.
"""
from __future__ import annotations

from typing import Any

VERSION="sc05-program-architecture-v1"
PROGRAM_FIELDS=(
    "planning_problem", "system_mechanism", "planning_contribution",
    "decision_stakeholders", "generalization_boundary",
    "paper_architecture", "why_not_a_subexperiment",
)
LEVELS={"robustness_fix","mechanism_substudy","independent_study","system_program"}
PROGRAM_TEMPLATE={
    "contribution_level":"robustness_fix|mechanism_substudy|independent_study|system_program",
    "planning_problem":"What city or social planning problem matters beyond the original author's case",
    "system_mechanism":"Causal/behavioral/structural interaction across components, scales or actors",
    "planning_contribution":"What transferable city system finding or policy decision changes",
    "decision_stakeholders":"Which planning/operation actors must decide, and which outcomes matter",
    "generalization_boundary":"What variation in cities/events/network types defines the claim's scope",
    "paper_architecture":"Coherent empirical chapters: mechanism, contrasting explanations, validation, decision relevance",
    "why_not_a_subexperiment":"Why this merits an independent paper rather than a sensitivity analysis of the source",
}

def _valid_field(value: Any) -> bool:
    return isinstance(value,str) and len(value.strip())>=24 and len(value)<=1500

def audit_research_program(
    routes: list[dict[str,Any]],
    reviews: list[dict[str,Any]],
    source_audit: dict[str,Any] | None=None,
) -> dict[str,Any]:
    source_audit=source_audit or {}
    review_map={r["route_id"]:r for r in reviews}
    route_results=[]
    planning_tiers=set(source_audit.get("direct_tiers_with_candidates",[]))
    planning_evidence_ready={"A","B"}.issubset(planning_tiers)
    for route in routes:
        prog=route.get("research_program")
        if not isinstance(prog,dict):
            prog={}
        level=prog.get("contribution_level")
        missing=[k for k in PROGRAM_FIELDS if not _valid_field(prog.get(k))]
        if level not in LEVELS:
            missing.append("contribution_level")
        verdict=review_map.get(route["id"],{}).get("verdict","unreviewed")
        scale_ready=(level in {"independent_study","system_program"} and not missing)
        near_papers=route.get("closest_paper_ids") or []
        # A route without actual comparable prior work is still a *hypothesis*.
        evidence_ready=bool(near_papers) and planning_evidence_ready
        flagged=[]
        if not scale_ready:
            flagged.append("not_yet_independent_paper_scale")
        if not near_papers:
            flagged.append("closest_scientific_prior_not_verified")
        if not planning_evidence_ready:
            flagged.append("planning_A_B_evidence_coverage_incomplete")
        if verdict=="reject":
            flagged.append("independent_critic_rejected")
        elif verdict=="hold":
            flagged.append("independent_critic_held")
        route_results.append({
            "route_id":route["id"],
            "model_declared_level":level if level in LEVELS else "unclassified",
            "program_fields_complete":len(missing)==0,
            "missing_program_dimensions":missing,
            "model_critic_verdict":verdict,
            "paper_scale_claim_supported_by_structure":scale_ready,
            "nearest_prior_present":bool(near_papers),
            "planning_A_B_coverage_sufficient":planning_evidence_ready,
            "editorial_status":(
                "provisional_independent_study_for_human_review"
                if scale_ready and evidence_ready and verdict=="test" else
                "not_ready_to_recommend_as_independent_paper"
            ),
            "cautions":flagged,
        })
    tier_coverage=source_audit.get("direct_tiers_with_candidates",[])
    uncovered=source_audit.get("uncovered_planning_streams",[])
    return {
        "version":VERSION,
        "routes":route_results,
        "possible_independent_study_proposals":sum(
            r["paper_scale_claim_supported_by_structure"] for r in route_results),
        "recommended_for_human_independent_study_review":sum(
            r["editorial_status"]=="provisional_independent_study_for_human_review"
            for r in route_results
        ),
        "review_required":True,
        "planning_venue_coverage":[t for t in tier_coverage if t in {"A","B"}],
        "planning_venue_gaps":uncovered,
        "novelty_certified":False,
        "publisher_acceptance_certified":False,
        "note":(
            "Research-problem scale, planning contribution, transferable "
            "mechanisms and venue-matched prior work need human verification. "
            "The model's declared level does not establish originality."
        ),
    }
