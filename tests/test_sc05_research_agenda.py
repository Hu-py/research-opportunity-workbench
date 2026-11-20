"""R7.1 offline agenda contract: no paid calls or network required."""
from backend.sc05_research_agenda import (
    validate_agenda_proposals, validate_agenda_reviews, audit_agendas,
)

FACTS = [{"fact_id": "F001"}, {"fact_id": "F002"}]
ROUTES = [
    {"id": "R01", "closest_paper_ids": ["doi:10.1000/precedent"],
     "research_program": {"contribution_level": "independent_study"}},
    {"id": "R02", "closest_paper_ids": []},
]
STUDIES = [
    {
        "route_id": "R01",
        "role": "phenomenon",
        "discriminating_test": "Compare independent network event trajectories",
        "contributes_to_claim": "Tests whether disruptions propagate through network structure",
    },
    {
        "route_id": "R02",
        "role": "mechanism",
        "discriminating_test": "Compare capacity and behavior mechanisms using disjoint outcomes",
        "contributes_to_claim": "Discriminates rival explanations of cascading failure",
    },
]
AGENDA = {
    "id": "A01",
    "title": "Network overload and failure propagation mechanisms",
    "route_ids": ["R01", "R02"],
    "source_fact_ids": ["F001"],
    "central_question": "When does disruption buffering become systemic propagation?",
    "empirical_tension": "The source reports localized responses but competing processes remain unseparated",
    "mechanism_synthesis": "Capacity thresholds and behavioral rerouting predict different propagation outcomes",
    "integration_rationale": "The first study locates the response, the second explains the response",
    "why_independent_paper": "A new system mechanism is tested, not only the original metric sensitivity",
    "planning_decision": "Transport agencies can compare infrastructure buffers with operating interventions",
    "boundary_conditions": "The claim may differ for disconnected, redundant, or strongly congested networks",
    "failure_condition": "Neither rival mechanism predicts held-out event propagation better than a baseline",
    "study_sequence": STUDIES,
}
REVIEW = {
    "agenda_id": "A01",
    "verdict": "test",
    "strongest_objection": "Observed mobility choices are only indirectly measured in available records",
    "nearest_prior_overlap": "Direct previous works may already assess cascading network mechanisms",
    "integration_risk": "Network simulations might fail to distinguish capacity from behavior",
    "minimum_discriminating_evidence": "Measure independent held-out disruptions under rival model predictions",
}


def test_agenda_accepts_grounded_integrated_studies_without_novelty_certificate():
    rows, audit = validate_agenda_proposals([AGENDA], ROUTES, FACTS)
    assert audit["accepted"] == 1
    assert rows[0]["source_fact_ids"] == ["F001"]
    assert rows[0]["scientific_novelty_verified"] is False
    reviews, review_audit = validate_agenda_reviews([REVIEW], rows)
    assert review_audit["unreviewed_agenda_ids"] == []
    result = audit_agendas(
        rows, reviews, ROUTES,
        [{"route_id": "R01", "verdict": "test"},
         {"route_id": "R02", "verdict": "test"}],
        {"direct_tiers_with_candidates": ["A", "B", "D"]},
    )
    assert result["provisional_for_human_review"] == 1
    assert result["scientific_novelty_verified"] is False
    assert result["real_world_feasibility_verified"] is False


def test_invalid_fact_reference_is_quarantined_not_repaired():
    bad = {**AGENDA, "source_fact_ids": ["F999"]}
    rows, audit = validate_agenda_proposals([bad], ROUTES, FACTS)
    assert rows == []
    assert audit["rejected"][0]["code"] == "AGENDA_SOURCE_FACT_INVALID"


def test_invented_route_is_quarantined():
    bad = {**AGENDA, "route_ids": ["R01", "R99"]}
    rows, audit = validate_agenda_proposals([bad], ROUTES, FACTS)
    assert not rows
    assert audit["rejected"][0]["code"] == "AGENDA_ROUTE_REFERENCE_INVALID"


def test_unrelated_study_sequence_cannot_pass():
    bad = {**AGENDA, "study_sequence": [
        {**STUDIES[0], "role": "phenomenon"},
        {**STUDIES[1], "role": "boundary"},
    ]}
    rows, audit = validate_agenda_proposals([bad], ROUTES, FACTS)
    assert rows == []
    assert audit["rejected"][0]["code"] == "AGENDA_STUDY_CHAIN_INVALID"


def test_incomplete_independent_critic_means_hold_not_promote():
    rows, _ = validate_agenda_proposals([AGENDA], ROUTES, FACTS)
    reviews, review_audit = validate_agenda_reviews([], rows)
    assert review_audit["unreviewed_agenda_ids"] == ["A01"]
    result = audit_agendas(
        rows, reviews, ROUTES, [{"route_id": "R01", "verdict": "test"},
                                {"route_id": "R02", "verdict": "test"}],
        {"direct_tiers_with_candidates": ["A", "B"]},
    )
    assert result["provisional_for_human_review"] == 0
    assert "AGENDA_INDEPENDENT_CRITIC_NOT_APPROVED" in result["agendas"][0]["blocking_codes"]


def test_missing_planning_evidence_cannot_promote_even_with_model_test():
    rows, _ = validate_agenda_proposals([AGENDA], ROUTES, FACTS)
    reviews, _ = validate_agenda_reviews([REVIEW], rows)
    result = audit_agendas(
        rows, reviews, ROUTES, [{"route_id": "R01", "verdict": "test"},
                                {"route_id": "R02", "verdict": "test"}],
        {"direct_tiers_with_candidates": ["D"]},
    )
    assert result["provisional_for_human_review"] == 0
    assert "PLANNING_A_B_EVIDENCE_INCOMPLETE" in result["agendas"][0]["blocking_codes"]


def test_no_route_or_no_agenda_does_not_force_a_generated_paper():
    rows, audit = validate_agenda_proposals(None, [], FACTS)
    assert rows == [] and audit["accepted"] == 0
    result = audit_agendas([], [], [], [], {})
    assert result["no_compulsory_agenda"] is True
    assert result["provisional_for_human_review"] == 0


def test_extra_and_duplicate_agendas_rejected():
    bad = [{**AGENDA, "id": "A01"}, {**AGENDA, "id": "A01"}]
    rows, audit = validate_agenda_proposals(bad, ROUTES, FACTS)
    assert len(rows) == 1
    assert audit["rejected"][0]["code"] == "AGENDA_ID_INVALID_OR_DUPLICATE"


def test_a_quality_only_bundle_cannot_become_full_paper():
    only_quality = [
        {"id": "R01", "closest_paper_ids": ["doi:10.1000/precedent"],
         "research_program": {"contribution_level": "robustness_fix"}},
        {"id": "R02", "closest_paper_ids": [],
         "research_program": {"contribution_level": "mechanism_substudy"}},
    ]
    rows, audit = validate_agenda_proposals([AGENDA], only_quality, FACTS)
    assert rows == []
    assert audit["rejected"][0]["code"] == "AGENDA_ONLY_QUALITY_OR_SUBSTUDIES"
