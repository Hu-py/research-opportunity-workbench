"""Tests for one-time Render-free admin bootstrap without shell access."""
from sqlalchemy import func, select
from research_workbench.core import session_factory
from backend.bootstrap import bootstrap_admin_from_env
from backend.team import TeamMember, AuditEntry, PASSWORD


def test_one_time_bootstrap_creates_only_one_admin(tmp_path,monkeypatch):
    factory=session_factory("sqlite:///"+str(tmp_path/"bootstrap.db"))
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","true")
    monkeypatch.setenv("TEAM_BOOTSTRAP_EMAIL","TestAdmin@Example.org")
    monkeypatch.setenv("TEAM_BOOTSTRAP_NAME","First Administrator")
    password="unit-test-only-long-password-374"
    monkeypatch.setenv("TEAM_BOOTSTRAP_PASSWORD",password)
    assert bootstrap_admin_from_env(factory)=="created"
    with factory() as db:
        members=db.scalars(select(TeamMember)).all()
        assert len(members)==1
        admin=members[0]
        assert admin.email=="testadmin@example.org"
        assert admin.role=="admin"
        assert admin.active is True
        assert password not in admin.password_hash
        assert PASSWORD.verify(admin.password_hash,password)
        assert db.scalar(select(func.count()).select_from(AuditEntry))==1
    assert bootstrap_admin_from_env(factory)=="already_initialized"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(TeamMember))==1
    monkeypatch.delenv("TEAM_BOOTSTRAP_PASSWORD")
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","false")
    assert bootstrap_admin_from_env(factory)=="disabled"


def test_bootstrap_requires_explicit_opt_in_and_credentials(tmp_path,monkeypatch):
    factory=session_factory("sqlite:///"+str(tmp_path/"bootstrap-guard.db"))
    monkeypatch.delenv("TEAM_BOOTSTRAP_ENABLED",raising=False)
    monkeypatch.setenv("TEAM_BOOTSTRAP_EMAIL","admin@example.org")
    monkeypatch.setenv("TEAM_BOOTSTRAP_PASSWORD","unit-test-only-long-password-374")
    assert bootstrap_admin_from_env(factory)=="disabled"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(TeamMember))==0
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","true")
    monkeypatch.delenv("TEAM_BOOTSTRAP_PASSWORD")
    try:
        bootstrap_admin_from_env(factory)
        assert False, "missing secret must fail closed"
    except RuntimeError as exc:
        assert "TEAM_BOOTSTRAP_PASSWORD" in str(exc)
