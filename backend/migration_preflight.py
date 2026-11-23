"""Read-only, admin-authenticated database migration target preflight.

Never logs or returns database URLs, usernames, credentials, hostnames,
database names or row values. Requires a distinct target PostgreSQL project.
No SQL writes or migrations are executed.
"""
from __future__ import annotations

import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool


def _parse(raw: str):
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Only PostgreSQL connections are supported")
    return url.set(drivername="postgresql+psycopg")


def _identity(url):
    return (str(url.host or "").lower(), int(url.port or 5432),
            str(url.database or ""))


def inspect_target(source_uri: str, target_uri: str) -> dict:
    """Verify identity and SELECT-only reachability of an empty target."""
    if not target_uri:
        raise ValueError("Migration target is not configured")
    if not source_uri:
        raise ValueError("Source database is not configured")
    try:
        source = _parse(source_uri)
        target = _parse(target_uri)
    except Exception as exc:
        raise ValueError("Invalid PostgreSQL connection configuration") from exc
    if _identity(source) == _identity(target):
        raise ValueError("The target is identical to the source; no migration allowed")
    engine = None
    try:
        engine = create_engine(target, poolclass=NullPool, connect_args={
            "connect_timeout": 7, "sslmode": "require"})
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                db_version = str(connection.execute(
                    text("SHOW server_version")).scalar_one())
                tables = connection.execute(text("""
                    SELECT count(*) FROM pg_catalog.pg_tables
                    WHERE schemaname = 'public'
                """)).scalar_one()
                # Source data is deliberately not read in this preflight.
        return {
            "connected": True, "source_and_target_distinct": True,
            "public_table_count": int(tables),
            "target_public_schema_empty": int(tables) == 0,
            "postgres_version": db_version,
            "safe_to_attempt_backup_restore": int(tables) == 0,
            "writes_performed": False,
            "backup_completed": False,
            "migration_completed": False,
        }
    except SQLAlchemyError as exc:
        # Never include the original DB exception in a log or API response:
        # many drivers include host/user and sometimes the connection URI.
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)
        if sqlstate == "28P01":
            category = "authentication_failed"
        elif sqlstate == "3D000":
            category = "database_not_found"
        elif sqlstate == "28000":
            category = "role_or_access_rejected"
        else:
            # Interpret common transport errors but never return their text.
            private_detail = str(orig or exc).lower()
            if "name or service not known" in private_detail or "could not translate host name" in private_detail or "nodename nor servname provided" in private_detail:
                category = "dns_resolution_failed"
            elif "timed out" in private_detail or "timeout" in private_detail:
                category = "network_timeout"
            elif "connection refused" in private_detail:
                category = "connection_refused"
            elif "password authentication failed" in private_detail:
                category = "authentication_failed"
            else:
                category = "other_connection_error"
        raise RuntimeError("migration_target_" + category) from None
    finally:
        if engine is not None:
            engine.dispose()



def source_inventory(db) -> dict:
    """Non-invasive source-size gate. Never returns any database values or secrets."""
    from sqlalchemy import text as sql_text
    if db.get_bind().dialect.name != "postgresql":
        raise ValueError("Expected a PostgreSQL source database")
    important = (
        "profiles", "team_profile_revisions", "team_achievements",
        "cusp_datasets", "papers", "ideas", "evidence", "events",
        "research_evolution_runs", "research_evolution_feedback",
        "research_tasks", "team_members",
    )
    # Only fixed, trusted identifiers appear in dynamic SQL.
    table_names = set(db.execute(sql_text(
        "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
    )).scalars().all())
    counts = {}
    for name in important:
        if name in table_names:
            counts[name] = int(db.execute(
                sql_text('SELECT count(*) FROM public."' + name + '"')
            ).scalar_one())
    total_bytes = int(db.execute(
        sql_text("SELECT pg_database_size(current_database())")
    ).scalar_one())
    source_is_expected_name = bool(db.execute(sql_text(
        "SELECT current_database() = :expected"
    ), {"expected":"research_atlas_test_db"}).scalar_one())
    return {
        "source_db_name_matches_expected": source_is_expected_name,
        "postgresql": True,
        "total_database_bytes": total_bytes,
        "total_database_megabytes": round(total_bytes / 1024 / 1024, 2),
        "public_table_count": len(table_names),
        "critical_table_counts": counts,
        "writes_performed": False,
        "backup_completed": False,
        "migration_completed": False,
    }


def mount(app, *, require_admin):
    router = APIRouter()

    @router.get("/api/admin/migration-target-preflight")
    def preflight(actor=Depends(require_admin)):
        if actor is None:
            # Legacy, shared-secret auth is insufficient for migration checks.
            raise HTTPException(status_code=403, detail="Team administrator login required")
        try:
            result = inspect_target(
                os.getenv("DATABASE_URL", ""),
                os.getenv("MIGRATION_TARGET_DATABASE_URL", ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return result

    app.include_router(router)
