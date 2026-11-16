"""The first Research Atlas workflow slice runs with no network or model key."""

from backend.atlas_intelligence.runner import (
    generate_signal_preview,
    prepare_paper_snapshot,
)
from backend.atlas_intelligence.signals import render_research_brief


def test_balanced_three_source_snapshot_and_unclassified_coverage():
    registry = [
        {"name": "Cities", "abbreviation": "Cities", "domain": "urban_planning"},
        {"name": "Environment and Planning B: Urban Analytics and City Science", "abbreviation": "EPB", "domain": "urban_planning"},
        {"name": "Conference on Neural Information Processing Systems", "abbreviation": "NeurIPS", "domain": "ai_ml"},
    ]
    candidates = [
        {"paper_id": "W1", "title": "Planning challenge", "venue": "Cities", "url": "https://example.org/a"},
        {"paper_id": "W2", "title": "Measuring cities", "venue": "EPB", "url": "https://example.org/b", "abstract": "A new urban indicator."},
        {"paper_id": "W3", "title": "Learning methods", "venue": "NeurIPS", "url": "https://example.org/c"},
        {"paper_id": "W4", "title": "Unresolved", "venue": "Unknown Venue", "url": "https://example.org/d"},
    ]
    papers, coverage = prepare_paper_snapshot(candidates, registry, per_group_limit=1)
    assert [p["paper_id"] for p in papers] == ["W1", "W2", "W3"]
    assert coverage["unclassified_candidate_count"] == 1
    assert [p["source_groups"][0] for p in papers] == [
        "planning_application", "urban_science", "computational_methods"
    ]


def test_llm_preview_requires_actual_paper_claims_and_can_be_empty():
    records = [
        {"paper_id": "W1", "title": "Some evidence",
         "url": "https://example.org/1", "source_groups": ["urban_science"],
         "evidence_level": "abstract"},
    ]
    def fake_model(payload):
        assert payload["papers"][0]["paper_id"] == "W1"
        assert "source_group" in payload["required_json"]["signals"][0]
        return {"signals": [{
            "source_group": "urban_science",
            "title": "A bounded single-study observation",
            "explanation": "One study discusses a measurement challenge.",
            "paper_ids": ["W1"],
            "trend_status": "single_paper",
            "claims": [{"kind": "author_claim",
                        "statement": "The study claims a measurement gap.",
                        "paper_ids": ["W1"]}],
        }]}
    report = generate_signal_preview(records, fake_model)
    assert report["signals"][0]["gap_status"] == "not_assessed"
    assert report["signals"][0]["review_status"] == "needs_review"
    assert "B 城市科学视角" in render_research_brief(report)


def test_no_papers_does_not_pay_for_fake_findings():
    called = []
    report = generate_signal_preview([], lambda x: called.append(x))
    assert not called
    assert report["signals"] == []
