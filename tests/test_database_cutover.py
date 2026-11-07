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
