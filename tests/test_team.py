"""Tests for team workspace data access and audit."""
from sqlalchemy import select, func
from research_workbench.core import session_factory, Profile
from backend.team import TeamMember, TeamProfileRevision, create_member, save_team_profile, current_profile_version, login, resolve_session

def test_shared_profile_and_individual_identity():
    Factory=session_factory("sqlite:///:memory:")
    with Factory() as db:
        member=create_member(db,"admin@example.org","Team Admin","test-only-long-credential-123",role="admin",initial=True)
        token,found=login(db,"admin@example.org","test-only-long-credential-123")
        assert found.id==member.id
        assert resolve_session(db,token).id==member.id
        payload={"team":{"name":"Research Lab"},"goals":"Shared research",
            "research_lines":[{"id":"city","name":"City","problem":"Missing labels",
                "keywords":[],"search_queries":["city graph"],"method_queries":[]}]}
        assert save_team_profile(db,payload,member.id,expected_version=0)==1
        assert current_profile_version(db)==1
        assert db.scalar(select(func.count()).select_from(Profile))==1
        assert db.scalar(select(func.count()).select_from(TeamProfileRevision))==1
