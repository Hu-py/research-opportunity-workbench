"""A real-public-metadata but fully offline test; no user data, internet or AI API."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.atlas_intelligence.urban_health_case import (
    CASE_ID, build_case, render_case, replay_file,
)

FIXTURE = Path(__file__).resolve().parents[1] / "experiments/urban_health_graph_2026_11_14/real_metadata_sample.json"


def test_real_bibliography_three_source_replay_and_traceability():
    case = replay_file(FIXTURE)
    report = case["research_signal_review"]
    assert case["case_id"] == CASE_ID
    assert case["paper_count"] == 10
    assert case["signal_count"] == 3
    assert case["run_mode"] == "offline_replay_real_public_metadata"
    assert not case["has_paid_model_calls"]
    assert not case["has_empirical_health_model_run"]
    assert case["scientific_review_status"] == "needs_review"
    assert report["paper_count_unique"] == 10
    assert len(report["signals"]) == 3
    assert {s["source_group"] for s in report["signals"]} == {
        "planning_application", "urban_science", "computational_methods"
    }
    assert report["research_opportunities"] == []
    ids = {p["paper_id"] for p in report["papers"]}
    assert ids == {p["paper_id"] for p in json.loads(FIXTURE.read_text())["papers"]}
    for signal in report["signals"]:
        assert len(signal["paper_ids"]) >= 2
        assert signal["gap_status"] == "not_assessed"
        assert signal["trend_status"] == "multi_paper_observation"
        assert signal["review_status"] == "needs_review"
        assert all(claim["kind"] == "hypothesis" for claim in signal["claims"])
        assert set(signal["paper_ids"]) <= ids
    assert "GraphSAGE" in render_case(case)
    assert "空间" in render_case(case)


def test_case_is_deterministic():
    assert replay_file(FIXTURE) == replay_file(FIXTURE)


def test_reject_unverified_abstract_level_and_missing_evidence():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data = deepcopy(fixture)
    data["papers"][0]["evidence_level"] = "abstract"
    with pytest.raises(ValueError, match="Metadata-only"):
        build_case(data)
    data = deepcopy(fixture)
    data["papers"][0]["abstract"] = "unverified abstract inserted"
    with pytest.raises(ValueError, match="must not silently add"):
        build_case(data)
    data = deepcopy(fixture)
    data["papers"][0]["url"] = "https://example.org/not-a-doi"
    with pytest.raises(ValueError, match="DOI URL"):
        build_case(data)
    data = deepcopy(fixture)
    data["papers"].pop()
    with pytest.raises(ValueError, match="Missing or unclassified|unknown paper"):
        build_case(data)


def test_closes_with_a_no_idea_default_and_anti_leakage_baselines():
    case = replay_file(FIXTURE)
    transfer = case["method_transfer"]
    assert transfer["status"] == "hypothesis_not_empirically_tested"
    assert len(transfer["minimum_baselines"]) >= 3
    assert any("标签" in item for item in transfer["validation_protocol"])
    assert any("独立" in item for item in transfer["validation_protocol"])
    assert set(transfer["evidence_paper_ids"]) <= {
        p["paper_id"] for p in case["research_signal_review"]["papers"]
    }
