"""R6.7-B real-DOI evaluation harness: offline mocks only."""
import copy
import json
from pathlib import Path

import pytest

from scripts.sc05_r67_real_dev_eval import (
    evaluate_real_dev, load_dev
)


def synthetic_manifest():
    """These fake DOIs are ONLY unit fixtures; never enter the real corpus."""
    labels = ["domain_near","domain_context","method_transfer","lexical_negative"]
    return {
        "schema_version":"sc05-r67-real-development-v0.1",
        "label_status":"ai_assisted_provisional_not_gold",
        "source_domain":"urban_transport",
        "items":[{
            "doi":f"10.1000/unit-{i}",
            "title":f"Artificial unit test article number {i:02d}",
            "year":2025,"source_url":f"https://doi.org/10.1000/unit-{i}",
            "initial_label":labels[i // 5],
            "annotation_status":"ai_assisted_provisional",
        } for i in range(20)]
    }


def test_manifest_validation_does_not_allow_fabricated_human_review(tmp_path):
    manifest = synthetic_manifest()
    path = tmp_path / "dev.json"
    path.write_text(json.dumps(manifest))
    assert len(load_dev(path)["items"])==20
    manifest["items"][0]["annotation_status"] = "human_gold"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="human review"):
        load_dev(path)


def test_duplicate_doi_and_exposed_r66_are_blocked(tmp_path):
    manifest = synthetic_manifest()
    manifest["items"][0]["doi"] = manifest["items"][1]["doi"]
    manifest["items"][0]["source_url"] = manifest["items"][1]["source_url"]
    path = tmp_path / "dev.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="Repeated"):
        load_dev(path)
    manifest = synthetic_manifest()
    manifest["items"][0]["doi"] = "10.1038/s41598-026-67177-7"
    manifest["items"][0]["source_url"] = "https://doi.org/10.1038/s41598-026-67177-7"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match="R6.6"):
        load_dev(path)


def test_evaluator_distinguishes_domain_method_and_unrelated_without_approval():
    m = synthetic_manifest()
    items = [
      {"doi":"10.1000/unit-0","id":"fixture:domain",
       "title":"Metro passenger flow under urban rail disruption",
       "abstract":"Urban rail transit passengers reroute across metro stations during closure.",
       "url":"https://example.org/domain","year":"2025"},
      {"doi":"10.1000/unit-10","id":"fixture:method",
       "title":"Graph neural network wildfire risk estimation",
       "abstract":"A graph neural network forecasts wildfire hazards using ecological grid observations.",
       "url":"https://example.org/method","year":"2025"},
      {"doi":"10.1000/unit-15","id":"fixture:noise",
       "title":"Philosophy of social interaction",
       "abstract":"Linguistic philosophy considers metaphors of network connections.",
       "url":"https://example.org/noise","year":"2025"},
    ]
    result=evaluate_real_dev(m,{x["doi"]:x for x in items},requests=3)
    assert result["evaluation_status"] == "partial_provider_coverage"
    assert result["counts"]["resolved"] == 3
    by_doi={r["doi"]:r for r in result["per_doi"]}
    assert by_doi["10.1000/unit-0"]["predicted_lane"] == "domain_candidate"
    assert by_doi["10.1000/unit-10"]["predicted_lane"] == "unapproved_method_lead"
    assert by_doi["10.1000/unit-15"]["predicted_lane"] == "quarantined"
    m=result["metrics_provisional_not_gold"]
    assert m["human_approved_transfers"]==0
    assert m["actual_deepseek_calls"]==0
    assert m["scientific_novelty_certified"] is False
    assert m["openalex_requests"]==3
    assert "A graph neural network forecasts wildfire" not in json.dumps(result)


def test_unresolved_provider_error_is_not_a_false_negative():
    m=synthetic_manifest()
    result=evaluate_real_dev(m,{},{"10.1000/unit-0":"abstract_unavailable"})
    assert result["counts"]["resolved"]==0
    assert result["evaluation_status"]=="partial_provider_coverage"
    assert result["metrics_provisional_not_gold"]["same_domain_candidate_recall"] is None
    assert result["metrics_provisional_not_gold"]["method_lead_recall"] is None
    assert result["per_doi"][0]["provider_error"]=="abstract_unavailable"
    assert len(result["unresolved_dois"])==20


def test_method_with_domain_words_is_flagged_for_human_review_not_certified():
    m=synthetic_manifest()
    method=m["items"][10]
    doi=method["doi"]
    record={"id":"fixture:misclassified",
            "doi":doi,
            "title":"Graph neural network model for urban rail mobility",
            "abstract":"Urban rail stations and passenger flows appear in this cross-domain machine learning illustration.",
            "url":"https://example.org/combined",
            "published":"2025-01-01"}
    r=evaluate_real_dev(m,{doi:record})
    assert r["per_doi"][10]["predicted_lane"]=="domain_candidate"
    assert any(
        x["doi"]==doi and x["reason"]=="provisional_method_in_domain_lane"
        for x in r["needs_human_adjudication"]
    )
    assert r["metrics_provisional_not_gold"]["closest_prior_semantic_accuracy"] is None


def test_real_32_doi_manifest_is_valid_and_does_not_overlap_r66():
    m = load_dev(Path("benchmarks/sc05_r67_real_dev_v01.json"))
    assert len(m["items"]) == 32
    assert {x["initial_label"] for x in m["items"]} == {
        "domain_near", "domain_context", "method_transfer", "lexical_negative"}
    assert m["label_status"] == "ai_assisted_provisional_not_gold"
    assert any("2023WR" in x["doi"] for x in m["items"])
    assert all(x["human_reviewer_status"] == "not_assigned" for x in m["items"])
