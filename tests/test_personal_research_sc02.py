"""Offline SC02 evidence replay and privacy ownership checks."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

import backend.api as api
from backend.personal_research import (
    PersonalResearchProfile, PersonalResearchResult, PublicPilotEvidence,
    _default_profile, _private_id, ensure_personal, private_result, seed_public_pilots,
    source_file,
)
from backend.team import create_member, TeamMember
from research_workbench.core import session_factory


def test_fixture_has_two_independent_real_source_topics():
    data = source_file()
    assert len(data["topics"]) == 2
    assert {t["key"] for t in data["topics"]} == {
        "child_health_extrapolation", "vertical_urbanization_3d"
    }
    assert all([p["id"] for p in t["probes"]] == ["A", "B", "C"] for t in data["topics"])
    assert all(len(p["papers"]) >= 2 for t in data["topics"] for p in t["probes"])
    assert data["llm_api_executed"] is False
    assert data["openalex_api_executed"] is False
    assert data["papers_full_text_audited"] == 0


def test_personal_persistence_is_distinct_from_public_snapshot(tmp_path, monkeypatch):
    factory = session_factory("sqlite:///" + str(tmp_path / "sc02.db"))
    monkeypatch.setenv("PERSONAL_RESEARCH_OWNER_EMAIL", "seed@example.invalid")
    with factory() as db:
        owner = create_member(db, "seed@example.invalid", "Owner",
                              "offline-test-only-placeholder", role="owner", initial=True)
        other = create_member(db, "other@example.invalid", "Member",
                              "offline-test-only-placeholder2", role="researcher")
        first = seed_public_pilots(db)
        assert first["seeded"] == 2
        assert seed_public_pilots(db)["seeded"] == 0
        assert db.scalar(select(PersonalResearchProfile.member_id)) is None
        assert ensure_personal(db, owner)
        assert not ensure_personal(db, owner)
        assert db.get(PersonalResearchProfile, owner.id) is not None
        assert db.get(PersonalResearchProfile, other.id) is None
        assert len(db.scalars(select(PersonalResearchResult)).all()) == 2
        for key in ("child_health_extrapolation", "vertical_urbanization_3d"):
            item = private_result(db, owner, key)
            assert item["visibility"] == "personal"
            assert item["run"]["openalex_api_executed"] is False
            assert item["review_status"] == "needs_scientific_review"
            assert len(item["run"]["topic"]["probes"]) == 3
            assert private_result(db, other, key) is None
            assert db.get(PersonalResearchResult, _private_id(other.id, key)) is None
        assert ensure_personal(db, other, explicit=True)
        assert len(db.scalars(select(PersonalResearchResult)).all()) == 4
        assert private_result(db, other, "child_health_extrapolation")["visibility"] == "personal"


def test_profile_no_inferred_team_capability():
    p = _default_profile()
    assert p["scope"] == "personal"
    assert p["explicitly_declared_interests"] == [
        "儿童健康空间外推", "三维竖向城市化"
    ]
    assert p["claim"] == "user_declared_interest_only_not_verified_team_capability"
