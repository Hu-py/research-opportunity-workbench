"""Deterministic SC05 domain-neighbor regression corpus; no network or DeepSeek."""
import httpx

from backend.sc05_relevance import (
    anchored_query, infer_source_domain, screen_candidate_papers,
    screen_route_prior_claims,
)
from research_workbench.core import query_openalex


TRANSPORT_PAGES = {
    "page_01": ("Urban rail transit disruptions show metro station passenger flow "
                "redistribution and network resilience during extreme rainfall."),
    "page_02": ("An origin destination matrix of subway passengers measures "
                "station-level mobility under partial closures."),
}
RELEVANT = {
    "id": "doi:10.1000/metro",
    "doi": "10.1000/metro",
    "title": "Passenger flow redistribution after urban rail disruptions",
    "abstract": ("This study estimates how metro station demand shifts after "
                 "network closure and examines passenger rerouting."),
    "url": "https://doi.org/10.1000/metro",
}
PHILOSOPHY = {
    "id": "doi:10.1000/philosophy",
    "doi": "10.1000/philosophy",
    "title": "Existence, Consciousness and the Philosophy of Networks",
    "abstract": "The paper studies linguistic philosophy, consciousness and metaphysics.",
    "url": "https://doi.org/10.1000/philosophy",
}
LINGUISTICS = {
    "id": "doi:10.1000/linguistics",
    "doi": "10.1000/linguistics",
    "title": "The Dynamics of Metaphor Formation in Mandarin",
    "abstract": "We study the evolution of linguistic pragmatics and metaphorical cognition.",
    "url": "https://doi.org/10.1000/linguistics",
}
CROSS_METHOD = {
    "id": "doi:10.1000/psychology",
    "doi": "10.1000/psychology",
    "title": "A neural model for psychological questionnaires",
    "abstract": "Reliability analysis and sensitivity analysis of psychological scores.",
    "url": "https://doi.org/10.1000/psychology",
}


def test_transport_domain_quarantines_philosophy_language_and_method_analogy():
    profile = infer_source_domain(TRANSPORT_PAGES)
    assert profile["code"] == "urban_transport"
    assert "urban rail" in anchored_query("capacity thresholds in cascades", profile)
    accepted, audit = screen_candidate_papers(
        [RELEVANT, PHILOSOPHY, LINGUISTICS, CROSS_METHOD],
        profile,
    )
    assert [p["id"] for p in accepted] == [RELEVANT["id"]]
    assert accepted[0]["domain_screen_status"] == "domain_match"
    assert accepted[0]["eligible_for_nearest_prior"] is True
    assert audit["retrieved"] == 4
    assert audit["accepted"] == 1
    assert audit["quarantined"] == 3
    assert {x["reason"] for x in audit["quarantined_records"]} == {
        "out_of_domain_or_unsupported_transfer",
    }
    # Original candidates are untouched, and may be manually examined later.
    assert "domain_screen_status" not in RELEVANT
    assert all("paper_id" in row for row in audit["quarantined_records"])


def test_self_citation_and_missing_abstract_cannot_be_claimed_as_prior():
    profile = infer_source_domain(TRANSPORT_PAGES)
    self_paper = {**RELEVANT, "doi": "https://doi.org/10.1016/j.trd.2026.105654"}
    missing = {**RELEVANT, "id": "doi:missing", "abstract": ""}
    papers, audit = screen_candidate_papers(
        [self_paper, missing, RELEVANT], profile,
        source_doi="10.1016/j.trd.2026.105654",
    )
    assert len(papers) == 1
    assert [row["reason"] for row in audit["quarantined_records"]] == [
        "source_paper_not_independent_prior",
        "abstract_absent_cannot_verify",
    ]


def test_unknown_source_domain_does_not_silently_certify_nearest_prior():
    profile = infer_source_domain({
        "page_01": "Mathematical implications for modal logic and truth claims."})
    assert profile["code"] == "unresolved"
    papers, audit = screen_candidate_papers([RELEVANT], profile)
    assert len(papers) == 1
    assert papers[0]["domain_screen_status"] == "domain_unresolved"
    assert papers[0]["eligible_for_nearest_prior"] is False
    assert audit["source_domain"] == "unresolved"


def test_water_and_child_health_profiles_are_not_forced_into_transport():
    assert infer_source_domain({
        "page_01": "A river basin water balance in watershed hydrology and ecological water replenishment."
    })["code"] == "water_hydrology"
    assert infer_source_domain({
        "page_01": "Child health and child development outcomes in a public health epidemiology study."
    })["code"] == "health_epidemiology"


def test_prior_requires_domain_close_verified_abstract_and_direct_explanation():
    profile = infer_source_domain(TRANSPORT_PAGES)
    accepted, _ = screen_candidate_papers([RELEVANT], profile)
    pid = RELEVANT["id"]
    base = {
        "paper_id": pid,
        "relevance": "close",
        "evidence_status": "abstract_quote_verified",
        "diagnosis_links": [{
            "diagnosis_id": "D01",
            "relation_type": "direct",
            "relation_explanation": "Both studies test transport network resilience to disruptions.",
        }],
    }
    raw = {"routes": [{"id": "R01", "closest_paper_ids":
                       [pid, PHILOSOPHY["id"], LINGUISTICS["id"]]}]}
    screened, audit = screen_route_prior_claims(raw, accepted, [base])
    assert screened["routes"][0]["closest_paper_ids"] == [pid]
    assert audit["removed_reference_count"] == 2
    assert raw["routes"][0]["closest_paper_ids"] == [
        pid, PHILOSOPHY["id"], LINGUISTICS["id"]]
    assert set(audit["minimum_evidence_eligible_paper_ids"]) == {pid}
    for change in [
        {"relevance": "partial"},
        {"evidence_status": "quote_unverified"},
        {"diagnosis_links": [{
            "diagnosis_id": "D01", "relation_type": "indirect",
            "relation_explanation": "The paper offers only a method analogy.",
        }]},
        {"diagnosis_links": []},
    ]:
        p, a = screen_route_prior_claims(raw, accepted, [{**base, **change}])
        assert p["routes"][0]["closest_paper_ids"] == []
        assert a["removed_reference_count"] == 3


def test_openalex_sc05_relevance_opt_in_preserves_default_weekly_sort():
    observed = []
    def responder(request):
        observed.append(request)
        return httpx.Response(200, json={"results": []})
    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        query_openalex("rail resilience", "2020-01-01", 7, client=client)
        query_openalex("rail resilience", "2020-01-01", 7, client=client,
                       sort_by_relevance=True, require_abstract=True)
    assert observed[0].url.params["sort"] == "publication_date:desc"
    assert observed[1].url.params["sort"] == "relevance_score:desc"
    assert "has_abstract:true" not in observed[0].url.params["filter"]
    assert "has_abstract:true" in observed[1].url.params["filter"]
