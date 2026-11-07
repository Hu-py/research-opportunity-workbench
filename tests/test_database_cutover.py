"""Supabase cutover chooses an explicit, reversible provider and rejects bad URLs."""
import pytest
from sqlalchemy.engine import URL
from research_workbench.core import resolve_database_url


def test_render_default_not_changed(monkeypatch):
    monkeypatch.delenv("RESEARCH_DATABASE_PROVIDER",raising=False)
    monkeypatch.setenv("DATABASE_URL","sqlite:////tmp/render-legacy-test.sqlite")
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",
        "postgresql://p:secret@aws-1-us-west-2.pooler.supabase.com:5432/postgres")
    assert resolve_database_url()=="sqlite:////tmp/render-legacy-test.sqlite"


def test_supabase_switch_preserves_private_credentials_and_uses_psycopg(monkeypatch):
    monkeypatch.setenv("RESEARCH_DATABASE_PROVIDER","supabase")
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",
        "postgresql://postgres.project:pa%40ss@aws-1-us-west-2.pooler.supabase.com:5432/postgres")
    url=resolve_database_url()
    assert isinstance(url,URL)
    assert url.drivername=="postgresql+psycopg"
    assert url.password=="pa@ss"
    assert url.host=="aws-1-us-west-2.pooler.supabase.com"
    assert url.database=="postgres"
    # Existing source DB remains separately configured and untouched.


def test_explicit_fixture_database_ignores_provider(monkeypatch):
    monkeypatch.setenv("RESEARCH_DATABASE_PROVIDER","supabase")
    monkeypatch.delenv("MIGRATION_TARGET_DATABASE_URL",raising=False)
    assert resolve_database_url("sqlite:///:memory:")=="sqlite:///:memory:"


def test_unset_target_and_invalid_db_are_blocked(monkeypatch):
    monkeypatch.setenv("RESEARCH_DATABASE_PROVIDER","supabase")
    monkeypatch.delenv("MIGRATION_TARGET_DATABASE_URL",raising=False)
    with pytest.raises(RuntimeError,match="not configured"):
        resolve_database_url()
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL","sqlite:///bad.db")
    with pytest.raises(RuntimeError,match="Invalid private"):
        resolve_database_url()
    monkeypatch.setenv("RESEARCH_DATABASE_PROVIDER","unknown")
    with pytest.raises(RuntimeError,match="Unknown"):
        resolve_database_url()


def test_source_connection_not_mutated_during_selection(monkeypatch):
    original="postgresql+psycopg://reader:pass@render.example.com/research_atlas_test_db"
    monkeypatch.setenv("DATABASE_URL",original)
    monkeypatch.setenv("RESEARCH_DATABASE_PROVIDER","supabase")
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",
        "postgresql://u:p@aws-1-us-west-2.pooler.supabase.com/postgres")
    resolve_database_url()
    assert __import__("os").environ["DATABASE_URL"]==original


def test_supabase_factory_is_reused_and_respects_connection_change(monkeypatch):
    import research_workbench.core as core
    core._supabase_cached_factory.cache_clear()
    monkeypatch.setenv("RESEARCH_DATABASE_PROVIDER","supabase")
    first_url="postgresql://u:p@aws-1-us-west-2.pooler.supabase.com/postgres"
    second_url="postgresql://u:p2@aws-1-us-west-2.pooler.supabase.com/postgres"
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",first_url)
    calls=[]
    def fake_build(url):
        calls.append(url)
        return object()
    monkeypatch.setattr(core,"_build_session_factory",fake_build)
    try:
        first=core.session_factory()
        assert first is core.session_factory()
        assert len(calls)==1
        monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",second_url)
        assert core.session_factory() is not first
        assert len(calls)==2
        assert calls[0].password=="p"
        assert calls[1].password=="p2"
    finally:
        core._supabase_cached_factory.cache_clear()


def test_explicit_session_factory_never_reuses_cached_target(monkeypatch):
    import research_workbench.core as core
    monkeypatch.setenv("RESEARCH_DATABASE_PROVIDER","supabase")
    calls=[]
    def fake_build(url):
        calls.append(url)
        return object()
    monkeypatch.setattr(core,"_build_session_factory",fake_build)
    core.session_factory("sqlite:///:memory:")
    core.session_factory("sqlite:///:memory:")
    assert calls==["sqlite:///:memory:","sqlite:///:memory:"]
