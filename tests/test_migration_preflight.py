"""Preflight protects source and target without performing migration writes."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.api as api
from backend.team import create_member
from backend.migration_preflight import _parse, _identity, inspect_target
from research_workbench.core import session_factory


def test_target_probe_needs_two_distinct_postgres_urls():
    source="postgresql+psycopg://user:password@source.example.com/db?sslmode=require"
    with pytest.raises(ValueError, match="not configured"):
        inspect_target(source, "")
    with pytest.raises(ValueError, match="Source database"):
        inspect_target("", source)
    with pytest.raises(ValueError, match="identical"):
        inspect_target(source, source)
    with pytest.raises(ValueError, match="Invalid PostgreSQL"):
        inspect_target(source, "sqlite:///local.db")
    url=_parse("postgres://postgres.project:pa%40ss@host.pooler.supabase.com:5432/postgres")
    assert url.get_backend_name()=="postgresql"
    assert _identity(url)==("host.pooler.supabase.com",5432,"postgres")


def test_target_probe_only_reads_public_schema():
    engine=MagicMock()
    connection=engine.connect.return_value.__enter__.return_value
    connection.execute.side_effect=[
        MagicMock(), MagicMock(scalar_one=lambda:"17.5"),
        MagicMock(scalar_one=lambda:0),
    ]
    source="postgresql://user:password@source.example.com/research"
    target="postgresql://postgres:secret@target.example.com/postgres?sslmode=require"
    with patch("backend.migration_preflight.create_engine",return_value=engine):
        result=inspect_target(source,target)
    assert result["connected"] is True
    assert result["target_public_schema_empty"] is True
    assert result["writes_performed"] is False
    assert result["backup_completed"] is False
    assert result["migration_completed"] is False
    assert connection.execute.call_count==3
    queries=[str(c.args[0]) for c in connection.execute.call_args_list]
    assert queries[0]=="SET TRANSACTION READ ONLY"
    assert "SELECT count(*)" in queries[-1]
    assert not any("INSERT" in q or "UPDATE" in q or "DELETE" in q for q in queries)
    assert engine.dispose.called


@pytest.fixture
def api_client(tmp_path,monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("WORKER_MODE","queue")
    monkeypatch.setenv("API_BEARER_TOKEN","test-api-token")
    monkeypatch.delenv("MIGRATION_TARGET_DATABASE_URL",raising=False)
    monkeypatch.setenv("DATABASE_URL","postgresql://user:password@render.example.org/research")
    db=session_factory("sqlite:///"+str(tmp_path/"preflight.db"))
    monkeypatch.setattr(api,"get_factory",lambda:db)
    with db() as session:
        create_member(session,"admin@example.org","Admin",
                      "test-strong-password-2026",role="admin",initial=True)
    with TestClient(api.app) as client:
        response=client.post("/api/auth/login",
                             headers={"Authorization":"Bearer test-api-token"},
                             json={"email":"admin@example.org","password":"test-strong-password-2026"})
        assert response.status_code==200,response.text
        token=response.json()["token"]
        yield client,token


def test_admin_only_probe_and_no_credentials_leaked(api_client,monkeypatch):
    client,token=api_client
    path="/api/admin/migration-target-preflight"
    basic={"Authorization":"Bearer test-api-token"}
    assert client.get(path,headers=basic).status_code==401
    privileged={**basic,"X-Research-Session":token}
    missing=client.get(path,headers=privileged)
    assert missing.status_code==422
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",
                       "postgresql://user:password@render.example.org/research")
    same=client.get(path,headers=privileged)
    assert same.status_code==422
    assert "password" not in same.text
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",
                       "postgresql://postgres:secret@pooler.supabase.com/postgres")
    with patch("backend.migration_preflight.inspect_target",return_value={
        "connected":True,"target_public_schema_empty":True,
        "writes_performed":False
    }):
        response=client.get(path,headers=privileged)
    assert response.status_code==200,response.text
    assert "secret" not in response.text
