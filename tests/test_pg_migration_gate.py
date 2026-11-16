"""Offline guard checks: never connect to a live database in CI."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from scripts.pg_migration_gate import (
    PgTarget, filter_supabase_toc, guarded_backup, guarded_restore,
    parse_postgres_url, pg_env, secure_target, verify_archive,
)


def test_parse_postgres_url_no_insecure_scheme():
    value=parse_postgres_url(
        "postgresql+psycopg://postgres.project:pa%40ss%3A123@pooler.supabase.com:5432/postgres?sslmode=require"
    )
    assert value.host=="pooler.supabase.com"
    assert value.password=="pa@ss:123"
    assert value.user=="postgres.project"
    assert value.sslmode=="require"
    assert "pa@ss" not in value.fingerprint
    env=pg_env(value)
    assert env["PGPASSWORD"]=="pa@ss:123"
    assert env["PGHOST"]=="pooler.supabase.com"
    with pytest.raises(ValueError):
        parse_postgres_url("sqlite:///tmp/data.db")
    with pytest.raises(ValueError):
        parse_postgres_url("postgresql://user:password@host/db?sslmode=disable")


def test_reject_restore_and_lockdown_without_confirm(tmp_path):
    target=PgTarget("db.example.com",5432,"postgres","secret","postgres")
    archive=tmp_path/"backup.dump"
    with pytest.raises(ValueError,match="confirm-empty-target"):
        guarded_restore(target,archive,False)
    with pytest.raises(ValueError,match="confirm-rls-lockdown"):
        secure_target(target,archive,False)


def test_backup_never_overwrites_existing_data(tmp_path):
    target=PgTarget("db.example.com",5432,"postgres","secret","research")
    archive=tmp_path/"research.dump"
    archive.write_bytes(b"do not overwrite")
    with pytest.raises(ValueError,match="already exists"):
        guarded_backup(target,archive)
    assert archive.read_bytes()==b"do not overwrite"


def test_supabase_toc_preserves_data_and_other_schemas():
    toc="""; Archive created at 2026-11-07
6; 2615 2200 SCHEMA - public pg_database_owner
7; 0 0 COMMENT - SCHEMA public pg_database_owner
8; 1259 8812 TABLE public papers postgres
9; 0 8812 TABLE DATA public papers postgres
10; 2615 9011 SCHEMA - other postgres
"""
    result=filter_supabase_toc(toc)
    assert "SCHEMA - public " not in result
    assert "COMMENT - SCHEMA public " not in result
    assert "TABLE DATA public papers" in result
    assert "SCHEMA - other" in result


def test_archive_check_rejects_corruption(tmp_path):
    archive=tmp_path/"research.dump"
    archive.write_bytes(b"incomplete-archive")
    manifest=archive.with_suffix(archive.suffix+".manifest.json")
    manifest.write_text(json.dumps({
        "archive_sha256":hashlib.sha256(b"original-archive").hexdigest()
    }))
    with pytest.raises(ValueError,match="checksum mismatch"):
        verify_archive(archive)


def test_reject_nonempty_target_even_with_explicit_confirm(tmp_path):
    archive=tmp_path/"research.dump"
    target=PgTarget("target.example.com",5432,"postgres","secret","postgres")
    with patch("scripts.pg_migration_gate.verify_archive",return_value=(
        {"source":{"fingerprint":"otherdb","table_counts":{"papers":1}}},"mocktoc"
    )), patch("scripts.pg_migration_gate.read_inventory",return_value={
        "table_counts":{"existing_team_data":1},"fingerprint":target.fingerprint
    }):
        with pytest.raises(ValueError,match="existing tables"):
            guarded_restore(target,archive,True)


def test_restore_targets_a_database_and_verifies_counts(tmp_path):
    archive=tmp_path/"research.dump"
    target=PgTarget("target.example.com",5432,"postgres","secret","postgres")
    toc="8; 1259 8812 TABLE public papers postgres\n9; 0 8812 TABLE DATA public papers postgres\n"
    snapshots=[
        {"table_counts":{},"fingerprint":target.fingerprint},
        {"table_counts":{"papers":2},"rls_enabled":{"papers":False}}
    ]
    with patch("scripts.pg_migration_gate.verify_archive",return_value=(
        {"source":{"fingerprint":"not-target","table_counts":{"papers":2}}},toc
    )),patch("scripts.pg_migration_gate.read_inventory",side_effect=snapshots),patch(
        "scripts.pg_migration_gate.run_command"
    ) as run:
        outcome=guarded_restore(target,archive,True)
    assert outcome["restored"] is True
    assert outcome["rls_unprotected_tables"]==["papers"]
    command=run.call_args.args[0]
    assert command[0]=="pg_restore"
    assert command[command.index("--dbname")+1]=="postgres"
    assert "--clean" not in command
    assert "--single-transaction" in command


def test_security_lockdown_refuses_source_database(tmp_path):
    target=PgTarget("same.example.com",5432,"postgres","secret","research")
    archive=tmp_path/"backup.dump"
    with patch("scripts.pg_migration_gate.verify_archive",return_value=(
        {"source":{"fingerprint":target.fingerprint,"table_counts":{"papers":1}}},"mocktoc"
    )):
        with pytest.raises(ValueError,match="source database"):
            secure_target(target,archive,True)
