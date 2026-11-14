"""Offline unit tests for the independent Research Atlas A/B/C taxonomy and L1 drafts."""
import pytest

from backend.atlas_intelligence.sources import (
    SOURCE_GROUPS,
    assign_source_groups,
    load_source_plan,
    match_venue_groups,
)
from backend.atlas_intelligence.signals import (
    build_research_brief,
    render_research_brief,
)


def test_three_sources_are_independent_of_old_radar_a_b():
    plan = load_source_plan()
    assert set(plan["source_groups"]) == set(SOURCE_GROUPS)
    assert assign_source_groups({"name": "Cities", "abbreviation": "Cities", "domain": "urban_planning"}, plan=plan) == ("planning_application",)
    assert assign_source_groups({"name": "Computers, Environment and Urban Systems", "abbreviation": "CEUS", "domain": "urban_planning"}, plan=plan) == ("urban_science",)
    assert assign_source_groups({"name": "NeurIPS", "abbreviation": "NeurIPS", "domain": "ai_ml"}, plan=plan) == ("computational_methods",)


def test_author_watchlist_requires_stable_author_id_and_allows_overlap():
    plan = load_source_plan()
    plan["authors"] = [{"author_id": "A12345", "source_groups": ["urban_science", "computational_methods"]}]
    selected = assign_source_groups({"name": "Cities", "domain": "urban_planning"}, plan=plan, author_ids=["A12345"])
    assert selected == ("planning_application", "urban_science", "computational_methods")
    without_id = assign_source_groups({"name": "Cities", "domain": "urban_planning"}, plan=plan, author_ids=["Other Name"])
    assert without_id == ("planning_application",)


def test_unmatched_source_is_not_hallucinated():
    assert match_venue_groups("Unknown Source", [{"name": "Cities", "abbreviation": "Cities", "domain": "urban_planning"}]) == ()


PAPERS = [
    {"paper_id": "W1", "title": "Evidence on method transfer",
     "url": "https://example.org/p1", "source_groups": ["computational_methods"],
     "evidence_level": "abstract"},
    {"paper_id": "W2", "title": "A contrasting method study",
     "url": "https://example.org/p2", "source_groups": ["computational_methods"],
     "evidence_level": "abstract"},
    {"paper_id": "W3", "title": "A planning application",
     "url": "https://example.org/p3", "source_groups": ["planning_application"],
     "evidence_level": "metadata"},
]


def _proposal():
    return {"signals": [{
        "source_group": "computational_methods",
        "title": "Two approaches to transfer",
        "explanation": "These two papers describe different method assumptions.",
        "paper_ids": ["W1", "W2"],
        "gap_status": "author_claim_only",
        "trend_status": "multi_paper_observation",
        "team_relevance": "Possible use in the team's spatial models; not confirmed.",
        "action_suggestion": "Compare assumptions before transfer.",
        "claims": [{"kind": "cross_paper_synthesis",
                    "statement": "The two studies make distinct assumptions.",
                    "paper_ids": ["W1", "W2"]}],
    }]}


def test_l1_brief_is_traceable_and_no_forced_opportunities():
    report = build_research_brief(PAPERS, _proposal(), period="2026-W46")
    assert report["paper_count_unique"] == 3
    assert report["sources"]["computational_methods"]["distinct_papers"] == 2
    assert report["deep_reads"] == []
    assert report["research_opportunities"] == []
    assert report["signals"][0]["review_status"] == "needs_review"
    assert "https://example.org/p1" in render_research_brief(report)
    assert "研究缺口审查状态" in render_research_brief(report)


def test_reject_unknown_or_cross_source_references():
    fake = _proposal()
    fake["signals"][0]["claims"][0]["paper_ids"] = ["fake"]
    with pytest.raises(ValueError, match="traceable"):
        build_research_brief(PAPERS, fake)
    cross = _proposal()
    cross["signals"][0]["paper_ids"] = ["W1", "W3"]
    with pytest.raises(ValueError, match="outside"):
        build_research_brief(PAPERS, cross)


def test_single_paper_cannot_claim_multi_paper_trend():
    proposal = _proposal()
    proposal["signals"][0]["paper_ids"] = ["W1"]
    proposal["signals"][0]["claims"][0]["paper_ids"] = ["W1"]
    with pytest.raises(ValueError, match="one paper"):
        build_research_brief(PAPERS, proposal)


def test_zero_signals_is_a_valid_week():
    report = build_research_brief(PAPERS, {"signals": []}, period="2026-W46")
    markdown = render_research_brief(report)
    assert report["signals"] == []
    assert "本期暂无通过结构校验的重点研究信号" in markdown
    assert "研究选题为可选产物" in markdown
