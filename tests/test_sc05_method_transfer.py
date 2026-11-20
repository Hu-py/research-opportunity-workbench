"""Offline R6.7 two-lane invariants against a *synthetic development* set.

No real R6.6 holdout DOI or abstract may be used for threshold tuning here.
No network, no DeepSeek, no human-gold or novelty claims.
"""
import copy
import json
from pathlib import Path

from backend.sc05_method_transfer import (
    collect_transfer_leads, method_leads_for_model, screen_transfer_bridges,
)
from backend.sc05_relevance import screen_candidate_papers


DEV = Path("benchmarks/sc05_r67_synthetic_dev_v01.json")


def fixture():
    data = json.loads(DEV.read_text(encoding="utf-8"))
    assert data["schema"] == "sc05-r67-synthetic-dev-v0.1"
    assert data["firewall"]["r66_holdout_dois_permitted"] is False
    assert data["firewall"]["real_doi_count"] == 0
    papers = [
        {**r, "url": "https://example.org/synthetic/"+r["id"].split(":")[-1],
         "year": "2025", "venue": "Synthetic teaching fixture"}
        for r in data["cases"]
    ]
    return data, papers


def test_synthetic_dev_is_different_from_openalex_r66_holdout():
    data, papers = fixture()
    assert len(papers) == 8
    assert all(x["id"].startswith("fixture:") for x in papers)
    assert not any("10.1038" in str(x) or "10.1016" in str(x)
                   for x in papers)
    assert all(x["expected_lane"] in {
        "domain_candidate","method_transfer_candidate","quarantined"
    } for x in papers)


def test_domain_and_method_lanes_are_separate_without_deleting_candidates():
    data, papers = fixture()
    domain, audit = screen_candidate_papers(
        papers, data["source_profile"], source_doi=data["source_doi"])
    leads, method_audit = collect_transfer_leads(
        papers, domain, audit, max_leads=4)
    assert {x["id"] for x in domain} == {
        "fixture:urban-rail","fixture:domain-traffic"}
    assert {x["id"] for x in leads} == {
        "fixture:forestry-method","fixture:clinical-method"}
    assert method_audit["method_leads_emitted"] == 2
    assert method_audit["auto_approved_transfers"] == 0
    assert all(x["eligible_for_nearest_prior"] is False for x in leads)
    assert all(x["review_status"] == "unreviewed_method_candidate" for x in leads)
    assert all(x["id"] not in {d["id"] for d in domain} for x in leads)
    assert all(x["expected_lane"] == "method_transfer_candidate"
               for x in papers if x["id"] in {p["id"] for p in leads})
    assert "fixture:source" not in {p["id"] for p in leads}
    assert "fixture:missing-abstract" not in {p["id"] for p in leads}
    assert not any("domain_screen_status" in x for x in papers)
    assert len(papers) == 8


def test_bounded_method_lead_context_is_not_full_source_dump():
    data, papers = fixture()
    domain, audit = screen_candidate_papers(
        papers, data["source_profile"], source_doi=data["source_doi"])
    leads, _ = collect_transfer_leads(papers,domain,audit)
    context = method_leads_for_model(leads, max_leads=1, abstract_chars=52)
    assert len(context) == 1
    assert len(context[0]["abstract"]) <= 52
    assert "review_status" in context[0]
    assert "eligible_for_nearest_prior" not in context[0]


def valid_bridge(pid,quote):
    return {
        "route_id": "R01",
        "paper_id": pid,
        "method_name": "Graph neural network prediction for structured systems",
        "source_input": "Observed environmental features recorded on wildfire grid cells",
        "target_input": "Measured transit station demand and topology with timestamps",
        "source_output": "Spatial wildfire hazard predictions for target locations",
        "target_output": "Prediction of operational transit disruption risk by station",
        "invariance_assumption": "Neighborhood dependence must transfer between different network dynamics",
        "discriminating_test": "Compare against a simple spatial-mean baseline on held-out incidents",
        "failure_condition": "Reject if held-out calibration deteriorates or flow constraints break",
        "abstract_excerpt":quote,
    }


def test_valid_proposal_is_unapproved_and_has_quote_grounding_only():
    data, papers = fixture()
    direct, audit = screen_candidate_papers(
        papers, data["source_profile"], source_doi=data["source_doi"])
    leads, _ = collect_transfer_leads(papers,direct,audit)
    target = next(p for p in leads if p["id"]=="fixture:forestry-method")
    quote = "A graph neural network maps ecological observations"
    accepted, bridge_audit = screen_transfer_bridges(
        [valid_bridge(target["id"],quote)], leads, {"R01"})
    assert len(accepted) == 1
    assert accepted[0]["abstract_quote_status"] == "verified"
    assert accepted[0]["review_status"] == "needs_human_review"
    assert accepted[0]["approved"] is False
    assert accepted[0]["eligible_for_nearest_prior"] is False
    assert bridge_audit["human_approved"] == 0
    assert bridge_audit["scientific_novelty_certified"] is False


def test_fabricated_route_quote_or_method_reference_is_excluded_without_relinking():
    data, papers = fixture()
    direct, audit = screen_candidate_papers(
        papers, data["source_profile"], source_doi=data["source_doi"])
    leads, _ = collect_transfer_leads(papers,direct,audit)
    pid = "fixture:forestry-method"
    good = valid_bridge(
        pid, "A graph neural network maps ecological observations")
    invalids = [
        {**good, "paper_id": "fixture:not-a-paper"},
        {**good, "route_id": "R99"},
        {**good, "abstract_excerpt": "A fabricated quote absent from the real abstract"},
        {**good, "target_output": "too short"},
    ]
    accepted, report = screen_transfer_bridges(invalids, leads, {"R01"})
    assert accepted == []
    assert [x["reason"] for x in report["rejected"]] == [
        "unrecognized_method_paper","unrecognized_route",
        "abstract_quote_not_verified","incomplete_input_output_or_falsification",
    ]
    assert report["accepted_provisional_bridges"] == 0
    assert report["human_approved"] == 0


def test_non_list_approval_and_excess_are_conservatively_handled():
    good = valid_bridge("fixture:forestry-method",
                        "A graph neural network maps ecological observations")
    lead = {"id":"fixture:forestry-method",
            "abstract":"A graph neural network maps ecological observations to predicted risk."}
    assert screen_transfer_bridges({"fabricated":good},[lead],{"R01"})[0] == []
    proposals = [
        {**copy.deepcopy(good), "route_id": f"R{i:02d}"}
        for i in range(1,5)
    ]
    accepted, audit = screen_transfer_bridges(
        proposals,[lead],{"R01","R02","R03","R04"},limit=2)
    assert len(accepted) == 2
    assert audit["excess_candidates"] == 2
    assert all(x["approved"] is False for x in accepted)
