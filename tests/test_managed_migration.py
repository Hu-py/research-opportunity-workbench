"""Safety guards for server-side migration; never touches real PostgreSQL."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from backend import managed_migration as m


SRC="postgresql+psycopg://reader:pa%40ss@internal.render.com:5432/research_atlas_test_db"
DST="postgresql://postgres.sample:secret@aws-1-us-west-2.pooler.supabase.com:5432/postgres"


def test_credentials_are_not_put_into_process_arguments():
    cfg=m._cfg(SRC)
    env=m._client_env(cfg)
    assert cfg.password=="pa@ss"
    assert env["PGPASSWORD"]=="pa@ss"
    assert env["PGHOST"]=="internal.render.com"
    with patch("backend.managed_migration.subprocess.run") as run:
        run.return_value.returncode=0
        m._run(["pg_dump","--format=custom","--file","/tmp/test.dump"],cfg)
    assert all("pa@ss" not in str(x) for x in run.call_args.args[0])
    assert "PGPASSWORD" in run.call_args.kwargs["env"]


def test_reject_non_postgres_and_missing_uri():
    with pytest.raises(m.MigrationGateError,match="missing_database_url"):
        m._cfg("")
    with pytest.raises(m.MigrationGateError,match="invalid_database_url"):
        m._cfg("sqlite:///tmp/some.db")


def test_same_database_and_non_supabase_target_disallowed():
    source=m._cfg(SRC)
    with pytest.raises(m.MigrationGateError,match="same_database"):
        m._validate_target(source,source)
    with pytest.raises(m.MigrationGateError,match="target_must_be_supabase_pooler"):
        m._validate_target(source,m._cfg("postgresql://u:p@random.example.net/postgres"))
    with pytest.raises(m.MigrationGateError,match="target_database_name_unexpected"):
        m._validate_target(source,m._cfg(
            "postgresql://u:p@aws-1-us-west-2.pooler.supabase.com/not_postgres"))


def test_safe_restore_list_filters_schema_only():
    toc="""; comment
1; 2615 2200 SCHEMA - public postgres
2; 0 0 COMMENT - SCHEMA public postgres
3; 1259 238 TABLE public profiles postgres
4; 0 238 TABLE DATA public profiles postgres
5; 1259 249 TABLE public team_achievements postgres
6; 0 249 TABLE DATA public team_achievements postgres
"""
    filtered=m._skip_public_schema_toc(toc)
    assert "SCHEMA - public " not in filtered
    assert "COMMENT - SCHEMA public" not in filtered
    assert "TABLE public profiles" in filtered
    assert "TABLE DATA public team_achievements" in filtered


def test_disabled_by_default_and_recovers_from_errors(monkeypatch):
    monkeypatch.delenv("MANAGED_MIGRATION_PHASE",raising=False)
    assert m.execute_from_env() is None
    monkeypatch.setenv("MANAGED_MIGRATION_PHASE","backup")
    monkeypatch.setenv("DATABASE_URL",SRC)
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",DST)
    with patch("backend.managed_migration.backup_to_private_checkpoint",
               side_effect=m.MigrationGateError("target_public_schema_is_not_empty")):
        response=m.execute_from_env()
    assert response=={
        "phase":"backup", "result":"failed",
        "category":"target_public_schema_is_not_empty"
    }


def test_duplicate_backup_is_noop(monkeypatch):
    # Once saved, re-running can NEVER overwrite the immutable checkpoint.
    monkeypatch.setattr(m,"_validate_target",lambda a,b:None)
    monkeypatch.setattr(m,"_validate_source",lambda a:{"profiles":1})
    from contextlib import contextmanager

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self,*args):return False
    conn=FakeConnection()

    monkeypatch.setattr(m,"_conn",lambda a:conn)
    monkeypatch.setattr(m,"_checkpoint_setup",lambda a:None)
    monkeypatch.setattr(m,"_read_checkpoint",lambda a:(
        "8"*64,1024,{"profiles":1},b"archive",None
    ))
    with patch("backend.managed_migration._run") as runner:
        result=m.backup_to_private_checkpoint(m._cfg(SRC),m._cfg(DST))
    assert result["result"]=="already_saved"
    assert runner.call_count==0


def test_no_public_restore_before_checkpoint_validated(monkeypatch):
    from contextlib import contextmanager
    class FakeConn:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def cursor(self):raise AssertionError("Should not use cursor when checkpoint is missing")
    monkeypatch.setattr(m,"_validate_target",lambda a,b:None)
    monkeypatch.setattr(m,"_conn",lambda a:FakeConn())
    monkeypatch.setattr(m,"_read_checkpoint",lambda a:None)
    with patch("backend.managed_migration._run") as runner:
        with pytest.raises(m.MigrationGateError,match="checkpoint_not_found"):
            m.restore_from_private_checkpoint(m._cfg(SRC),m._cfg(DST))
    runner.assert_not_called()


def test_explicit_verify_phase_uses_read_only_validation(monkeypatch):
    monkeypatch.setenv("MANAGED_MIGRATION_PHASE","verify")
    monkeypatch.setenv("DATABASE_URL",SRC)
    monkeypatch.setenv("MIGRATION_TARGET_DATABASE_URL",DST)
    result={"phase":"verify","result":"verified","tables":43}
    with patch("backend.managed_migration.verify_persisted_target",return_value=result) as call:
        assert m.execute_from_env()==result
    assert call.call_count==1


def test_verify_prevents_source_target_collision():
    src=m._cfg(SRC)
    with pytest.raises(m.MigrationGateError,match="same_database"):
        m.verify_persisted_target(src,src)


def test_precutover_detects_row_level_drift_even_when_counts_match():
    snapshot={"phase":"verify","result":"verified","source_counts_match_backup":True}
    with patch("backend.managed_migration.verify_persisted_target",return_value=snapshot), \
         patch("backend.managed_migration._data_fingerprints",side_effect=[
             {"papers":"a"*64},{"papers":"b"*64}
         ]), patch("backend.managed_migration._application_target_canary") as canary:
        with pytest.raises(m.MigrationGateError,match="row_content_mismatch"):
            m.precutover_verify(m._cfg(SRC),m._cfg(DST))
    canary.assert_not_called()


def test_precutover_validates_source_and_target_hashes_and_write_canary():
    snapshot={"phase":"verify","result":"verified","source_counts_match_backup":True}
    expected={"papers":"a"*64,"profiles":"b"*64}
    with patch("backend.managed_migration.verify_persisted_target",return_value=snapshot), \
         patch("backend.managed_migration._data_fingerprints",side_effect=[expected,expected]), \
         patch("backend.managed_migration._application_target_canary",
               return_value={"critical_tables_readable":True,
                             "transactional_write_rollback_passed":True}) as canary:
        report=m.precutover_verify(m._cfg(SRC),m._cfg(DST))
    assert report["result"]=="ready"
    assert report["tables"]==2
    assert report["all_table_content_hashes_match"] is True
    assert report["main_database_switched"] is False
    canary.assert_called_once()


def test_target_canary_rolls_back_uncommitted_write():
    from unittest.mock import MagicMock
    engine=MagicMock()
    con=engine.connect.return_value.__enter__.return_value
    con.execute.side_effect=[
        MagicMock(scalar_one=lambda:1),
        MagicMock(scalar_one=lambda:1),
        MagicMock(scalar_one=lambda:55),
        MagicMock(scalar_one=lambda:28),
        MagicMock(),
        MagicMock(scalar_one=lambda:1),
    ]
    with patch("sqlalchemy.create_engine",return_value=engine):
        report=m._application_target_canary(m._cfg(DST))
    assert report["transactional_write_rollback_passed"]
    con.begin.return_value.rollback.assert_called_once()
    engine.dispose.assert_called_once()
