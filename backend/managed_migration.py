"""One-shot, server-side migration from isolated Render PG17 to empty Supabase PG17.

Runs only when MANAGED_MIGRATION_PHASE=backup|restore; no publicly callable
routes, no secret URLs in logs. The original DATABASE_URL is never updated.
The archive is stored in a privately granted schema *on the destination*;
this is a migration checkpoint, not an independent off-site backup.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile

from sqlalchemy.engine import make_url


RUN_KEY = "render-research-atlas-20261108-snapshot-v1"
SCHEMA = "migration_private"
LIMIT_BYTES = 100 * 1024 * 1024
LOG = logging.getLogger("uvicorn.error")


class MigrationGateError(Exception):
    """A fixed safe error message without credentials or untrusted server output."""


def _cfg(raw: str):
    if not raw:
        raise MigrationGateError("missing_database_url")
    try:
        if raw.startswith("postgres://"):
            raw = "postgresql://" + raw[len("postgres://"):]
        url = make_url(raw)
        if url.get_backend_name() != "postgresql":
            raise ValueError("not postgres")
        if not url.host or not url.username or not url.database:
            raise ValueError("missing host/user/database")
        return url
    except Exception:
        raise MigrationGateError("invalid_database_url") from None


def _identity(url):
    return (url.host.lower(), int(url.port or 5432), url.database)


def _pg_config(url):
    # Never pass a password or a URL through a process argument.
    return {
        "host":url.host,
        "port":int(url.port or 5432),
        "dbname":url.database,
        "user":url.username,
        "password":url.password or "",
        "sslmode":"require",
        "connect_timeout":12,
    }


def _client_env(url):
    cfg=_pg_config(url)
    return {**os.environ, "PGHOST":str(cfg["host"]),
            "PGPORT":str(cfg["port"]), "PGDATABASE":str(cfg["dbname"]),
            "PGUSER":str(cfg["user"]), "PGPASSWORD":str(cfg["password"]),
            "PGSSLMODE":"require", "PGCONNECT_TIMEOUT":"12"}


def _conn(url):
    import psycopg
    try:
        return psycopg.connect(**_pg_config(url))
    except Exception:
        raise MigrationGateError("database_connection_failed") from None


def _run(argv, url, *, capture=False):
    try:
        p=subprocess.run(argv, env=_client_env(url), text=True,
                         stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                         stderr=subprocess.PIPE, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise MigrationGateError("postgresql_client_unavailable_or_timed_out") from None
    if p.returncode:
        # NEVER return raw stderr; pg tools can print connection hosts.
        raise MigrationGateError("postgresql_client_failed_" + str(p.returncode))
    return p.stdout if capture else None


def _table_counts(conn):
    from psycopg import sql
    with conn.cursor() as cur:
        cur.execute("""SELECT c.relname FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind IN ('r','p')
            ORDER BY c.relname""")
        names=[r[0] for r in cur.fetchall()]
        counts={}
        for name in names:
            cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier("public"),sql.Identifier(name)))
            counts[name]=int(cur.fetchone()[0])
        return counts


def _database_version(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('server_version_num')::integer")
        return int(cur.fetchone()[0])//10000


def _validate_source(url):
    if url.database != "research_atlas_test_db":
        raise MigrationGateError("unexpected_source_database_name")
    with _conn(url) as conn:
        conn.read_only=True
        counts=_table_counts(conn)
        version=_database_version(conn)
    if version!=17 or len(counts)<40:
        raise MigrationGateError("source_schema_or_postgres_version_unexpected")
    return counts


def _validate_target(source,target):
    if _identity(source)==_identity(target):
        raise MigrationGateError("source_and_target_are_same_database")
    if not target.host.endswith(".pooler.supabase.com"):
        raise MigrationGateError("target_must_be_supabase_pooler")
    if target.database!="postgres":
        raise MigrationGateError("target_database_name_unexpected")
    with _conn(target) as conn:
        conn.read_only=True
        if _database_version(conn)!=17:
            raise MigrationGateError("target_postgres_version_unexpected")
        counts=_table_counts(conn)
    if counts:
        raise MigrationGateError("target_public_schema_is_not_empty")


def _archive_sha(path):
    d=hashlib.sha256()
    with path.open("rb") as fh:
        for part in iter(lambda:fh.read(1024*1024),b""):
            d.update(part)
    return d.hexdigest()


def _verify_dump(path):
    if not path.exists() or not (1000 < path.stat().st_size < LIMIT_BYTES):
        raise MigrationGateError("invalid_backup_archive_size")
    try:
        x=subprocess.run(["pg_restore","--list",str(path)],
                         text=True,capture_output=True,timeout=30,check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise MigrationGateError("archive_validation_tool_unavailable") from None
    if x.returncode or "TABLE DATA public " not in x.stdout:
        raise MigrationGateError("invalid_archive_toc")
    return x.stdout


def _checkpoint_setup(conn):
    # This is inside a new isolated Supabase DB, never the Render source.
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS migration_private")
        cur.execute("""CREATE TABLE IF NOT EXISTS migration_private.archive (
          run_key TEXT PRIMARY KEY,
          source_tag TEXT NOT NULL,
          archive_sha256 CHAR(64) NOT NULL,
          archive_bytes INTEGER NOT NULL,
          table_counts JSONB NOT NULL,
          dump BYTEA NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          restored_at TIMESTAMPTZ
        )""")
        cur.execute("REVOKE ALL ON SCHEMA migration_private FROM PUBLIC")
        cur.execute("REVOKE ALL ON TABLE migration_private.archive FROM PUBLIC")
        # Supabase Data API roles must not access private checkpoints.
        cur.execute("""DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
              EXECUTE format('REVOKE ALL ON SCHEMA migration_private FROM %I',r);
              EXECUTE format('REVOKE ALL ON TABLE migration_private.archive FROM %I',r);
            END IF;
          END LOOP;
        END $$""")
    conn.commit()


def _read_checkpoint(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT archive_sha256, archive_bytes, table_counts, dump, restored_at
                       FROM migration_private.archive WHERE run_key=%s""",(RUN_KEY,))
        row=cur.fetchone()
    return row


def backup_to_private_checkpoint(source,target):
    _validate_target(source,target)
    before=_validate_source(source)
    with _conn(target) as conn:
        _checkpoint_setup(conn)
        existing=_read_checkpoint(conn)
        if existing:
            return {"phase":"backup","result":"already_saved",
                    "sha256":existing[0],"bytes":existing[1],
                    "tables":len(existing[2]),"source_unchanged":True}
    # Reserve a directory with restrictive permissions. No dump in GitHub/logs.
    with tempfile.TemporaryDirectory(prefix="research-pg-dump-") as d:
        directory=Path(d)
        os.chmod(directory,0o700)
        path=directory/"research.dump"
        _run(["pg_dump","--format=custom","--schema=public","--no-owner",
              "--no-privileges","--file",str(path)],source)
        os.chmod(path,0o600)
        _verify_dump(path)
        after=_validate_source(source)
        if before!=after:
            raise MigrationGateError("source_counts_changed_during_backup")
        digest=_archive_sha(path)
        size=path.stat().st_size
        payload=path.read_bytes()
    # Archive only. Nothing in public target schema is created here.
    with _conn(target) as conn:
        if _table_counts(conn):
            raise MigrationGateError("target_public_schema_changed")
        _checkpoint_setup(conn)
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO migration_private.archive
                (run_key,source_tag,archive_sha256,archive_bytes,table_counts,dump)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (run_key) DO NOTHING""",
                (RUN_KEY,hashlib.sha256(repr(_identity(source)).encode()).hexdigest()[:24],
                 digest,size,json.dumps(before),payload))
            created=cur.rowcount==1
        conn.commit()
        row=_read_checkpoint(conn)
        if not row or row[0]!=digest or int(row[1])!=size:
            raise MigrationGateError("private_checkpoint_integrity_failure")
    return {"phase":"backup","result":"saved" if created else "already_saved",
            "sha256":digest,"bytes":size,"tables":len(before),
            "source_unchanged":True,"private_checkpoint":True,
            "independent_offsite_backup":False}


def _skip_public_schema_toc(toc: str):
    result=[]
    for line in toc.splitlines():
        if re.search(r";\s*\d+\s+\d+\s+SCHEMA\s+-\s+public(?:\s|$)",line):
            continue
        if re.search(r";\s*\d+\s+\d+\s+COMMENT\s+-\s+SCHEMA\s+public(?:\s|$)",line):
            continue
        result.append(line)
    return "\n".join(result)+"\n"


def _protect_target_schema(conn):
    with conn.cursor() as cur:
        # Remove schema access before restoration; no data is exposed to the
        # Supabase Data API between the restore commit and RLS lockdown.
        cur.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        cur.execute("""DO $$
        DECLARE r text;
        BEGIN
          FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
            IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
              EXECUTE format('REVOKE ALL ON SCHEMA public FROM %I',r);
            END IF;
          END LOOP;
        END $$""")
    conn.commit()


def _post_restore_lockdown(conn, expected: dict):
    from psycopg import sql
    actual=_table_counts(conn)
    if actual!=expected:
        raise MigrationGateError("restored_row_counts_do_not_match_snapshot")
    with conn.cursor() as cur:
        for name in actual:
            obj=sql.SQL("{}.{}").format(sql.Identifier("public"),sql.Identifier(name))
            cur.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(obj))
            cur.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM PUBLIC").format(obj))
            for role in ("anon","authenticated","service_role"):
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",(role,))
                if cur.fetchone():
                    cur.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM {}").format(
                        obj,sql.Identifier(role)))
        cur.execute("""SELECT c.relname FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='S'""")
        sequences=[r[0] for r in cur.fetchall()]
        for name in sequences:
            seq=sql.SQL("{}.{}").format(sql.Identifier("public"),sql.Identifier(name))
            cur.execute(sql.SQL("REVOKE ALL ON SEQUENCE {} FROM PUBLIC").format(seq))
            for role in ("anon","authenticated","service_role"):
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s",(role,))
                if cur.fetchone():
                    cur.execute(sql.SQL("REVOKE ALL ON SEQUENCE {} FROM {}").format(
                        seq,sql.Identifier(role)))
        cur.execute("""SELECT count(*) FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind IN ('r','p')
            AND NOT c.relrowsecurity""")
        if int(cur.fetchone()[0])!=0:
            raise MigrationGateError("rls_lockdown_not_complete")
    conn.commit()
    return len(sequences)


def restore_from_private_checkpoint(source,target):
    _validate_target(source,target)
    with _conn(target) as conn:
        try:
            checkpoint=_read_checkpoint(conn)
        except Exception:
            raise MigrationGateError("checkpoint_not_found") from None
        if not checkpoint:
            raise MigrationGateError("checkpoint_not_found")
        sha,size,counts,payload,restored_at=checkpoint
        if restored_at:
            raise MigrationGateError("restore_already_completed")
    # Verify bytes before touching the public target schema.
    with tempfile.TemporaryDirectory(prefix="research-pg-restore-") as d:
        directory=Path(d)
        os.chmod(directory,0o700)
        archive=directory/"research.dump"
        with archive.open("xb") as out:
            out.write(payload)
        os.chmod(archive,0o600)
        if archive.stat().st_size!=size or _archive_sha(archive)!=sha:
            raise MigrationGateError("checkpoint_checksum_mismatch")
        toc=_verify_dump(archive)
        list_file=directory/"toc.txt"
        with list_file.open("x") as out:
            out.write(_skip_public_schema_toc(toc))
        os.chmod(list_file,0o600)
        # Source is strictly read-only throughout; the target is empty.
        with _conn(target) as conn:
            _protect_target_schema(conn)
        _run(["pg_restore","--format=custom","--dbname",target.database,
              "--exit-on-error","--single-transaction","--no-owner",
              "--no-privileges","--use-list",str(list_file),str(archive)],target)
    with _conn(target) as conn:
        sequences=_post_restore_lockdown(conn,counts)
        with conn.cursor() as cur:
            cur.execute("""UPDATE migration_private.archive
                           SET restored_at=NOW()
                           WHERE run_key=%s AND restored_at IS NULL""",(RUN_KEY,))
        conn.commit()
    return {"phase":"restore","result":"restored",
            "tables":len(counts),"counts_match_snapshot":True,
            "rls_enabled":True,"sequences_protected":sequences,
            "source_unchanged":True,"production_database_switched":False,
            "independent_offsite_backup":False}


def execute_from_env():
    phase=os.getenv("MANAGED_MIGRATION_PHASE","").strip()
    if phase not in ("backup","restore"):
        return None
    try:
        source=_cfg(os.getenv("DATABASE_URL",""))
        target=_cfg(os.getenv("MIGRATION_TARGET_DATABASE_URL",""))
        result = (backup_to_private_checkpoint(source,target) if phase=="backup"
                  else restore_from_private_checkpoint(source,target))
        LOG.info("SERVER_SIDE_MIGRATION_RESULT %s",json.dumps(result,sort_keys=True))
        return result
    except MigrationGateError as exc:
        LOG.warning("SERVER_SIDE_MIGRATION_FAILED category=%s",str(exc))
        return {"phase":phase,"result":"failed","category":str(exc)}
    except Exception:
        LOG.warning("SERVER_SIDE_MIGRATION_FAILED category=unexpected_error")
        return {"phase":phase,"result":"failed","category":"unexpected_error"}
