# Controlled PostgreSQL migration: Render Free -> isolated Supabase

**Status: preparation only. No production data has been copied.**

This runbook follows Render's official `pg_dump` guidance and Supabase's
Postgres migration guidance. It deliberately avoids creating public database
endpoints or placing source/target passwords in source code, GitHub, logs,
ChatGPT conversations or CI artifacts.

## Source verified so far

- Main API `research-atlas-api-test`: started successfully with
  PostgreSQL on 2026-11-07. Its last logged inventory reported 36 verified
  achievements, 28 registered dataset assets and one official research line.
- Render Free database `research-atlas-test-db` has name
  `research_atlas_test_db`, PostgreSQL 17, and expires **2026-12-04**.
- Exact current main API `DATABASE_URL` host has NOT been independently
  inspected. Confirm privately before migration, and do not send secrets here.
- Science staging API uses **SQLite** and must not become the source.
- Existing Vercel `RESEARCH_LAB_SUPABASE_*` settings correspond to the
  separate Agent Lab; do **not** reuse that existing project as an empty
  destination.

## Destination decision

Create a **separate** Supabase project for team research memory. On project
creation leave **Automatically expose new tables** OFF; disable the Data API
entirely if you only use the trusted FastAPI backend. This matters: after a
PostgreSQL dump is restored, project tables in the public schema might become
accessible via Supabase Data API grants unless RLS/grants are configured.

Supabase Free can be used for experiments, but is not an enterprise-grade
durability guarantee: **no automatic daily backups**, 500 MB free DB capacity,
and possible inactivity pauses. For an irreplaceable long-running team corpus,
prefer Pro or add encrypted, private, off-site backups plus a tested restore
process.

## Required environment

Run the migration tool in an operator-controlled shell that can reach BOTH
database hosts, has Python 3.11+, `psycopg[binary]`, `pg_dump`/ `pg_restore`
from PostgreSQL **17 or newer**, and sufficient encrypted disk space.

```bash
python -m pip install 'psycopg[binary]>=3.2,<4'
# Set each URI using your PRIVATE shell or secrets manager, not a pasted chat:
# DATABASE_URL=... (source Render Postgres)
# MIGRATION_TARGET_DATABASE_URL=... (new isolated Supabase Postgres)
```

**Network access to Render Free:** the source database currently has an empty
external IP allowlist. An external SQL tool cannot query it until an authorized
route exists. Two options (choose privately):

1. Temporarily allowlist only the operator machine's current public IP as a
   single `/32` entry in Render's database Networking settings, run the
   export over TLS, then immediately remove that entry. Do not use
   `0.0.0.0/0`. Never expose credentials in logs.
2. Upgrade Render Postgres to a paid plan and generate a Render logical
   backup in its Recovery page. This incurs costs, but avoids building your
   own backup service. Download the export to encrypted private storage.
   Render Free does NOT offer managed exports.

Do not run a backup against staging SQLite. The archive includes private
team research state, credentials hashes, potentially encrypted model
configuration, and must be treated as confidential. Store it outside
GitHub and any public bucket. The migration script creates a 0600 archive
and manifest in a 0700 directory, but **you** must secure the host/disk
and arrange private off-site retention.

## Guarded migration phases

**Phase 0: verify both hosts and target identity privately.**

```bash
python scripts/pg_migration_gate.py source-inventory
python scripts/pg_migration_gate.py target-inventory
```

- Source must show registered existing team tables, not an empty SQLite DB.
- Destination must be a different server/DB and should show **no application
  tables** in `public`. This tool refuses restore into a populated target.
- Compare source database size to the target's plan capacity; source Free Render
  can hold up to 1 GB, Supabase Free only 500 MB. Do not attempt an oversize
  restore.

**Phase 1: quiesce writes and produce a physical file backup.**

Pause scheduled writers (Vercel cron and any Agent jobs) and inform team
members of a read-only maintenance window before the final backup. If any
app writes continue, snapshot row counts may remain equal even when rows
change; count equality alone does NOT certify a consistent live cutover.

```bash
python scripts/pg_migration_gate.py backup \
    --archive private-backups/research-atlas-20261107.dump
python scripts/pg_migration_gate.py verify \
    --archive private-backups/research-atlas-20261107.dump
```

The tool refuses to overwrite an existing backup and saves a manifest
containing the file SHA-256 and exact counts of tables in `public`.
Check that a second securely stored copy exists, and ideally test a
restore to a separate throwaway private database **before** migration.

**Phase 2: restore to an EMPTY, non-exposed target.**

Keep Supabase Data API disabled or automatic exposure off during this step.

```bash
python scripts/pg_migration_gate.py restore \
    --archive private-backups/research-atlas-20261107.dump \
    --confirm-empty-target
```

The script checks the archive SHA, skips an already-existing `public`
schema creation entry, uses `pg_restore --single-transaction --exit-on-error`
and **never** passes `--clean`. It aborts on unexpected existing tables.
The tool compares destination table counts with the saved source manifest.
A failed restore is **not** a reason to delete or alter the source.

**Phase 3: protect the data before connecting any application.**

```bash
python scripts/pg_migration_gate.py secure-target \
    --archive private-backups/research-atlas-20261107.dump \
    --confirm-rls-lockdown
```

This explicitly enables RLS on the copied application tables and revokes
table grants from `anon`, `authenticated`, `service_role`, and `PUBLIC`.
The FastAPI backend must use a suitable private direct/session PostgreSQL
role that can still read/write the tables. Reconfirm with a real backend
read/write test after the RLS change.

**Important:** this is a table-level safety measure, not a complete security
audit. Review public functions, views, schema grants, default privileges,
legacy extensions, and enabled Data API settings as separate controls.
Prefer a closed Data API while the backend uses a private connection.

**Phase 4: validation BEFORE cutover.**

- Confirm every migrated app table and row count.
- Confirm identity sequences, FK constraints and important source links.
- Verify team login and profile read, paper list, curated achievements, data
  assets, prior Agent run and review history, and one disposable test record.
- Verify backend restart retains that test record.
- Verify Supabase object storage remains separate from database rows; if PDF
  attachments exist, migrate them through a separately authorized workflow.
- Check no `anon` Data API role can list team tables, and no production
  browser receives DB connection strings.

**Phase 5: cut over only with an accepted restore test.**

Change **only** the active main Render API `DATABASE_URL` to the isolated
validated Supabase connection in the Render secret store. Keep previous
configuration securely saved for rollback, and update other workers sharing
the same DB consistently. Do not switch Vercel
`RESEARCH_LAB_SUPABASE_*` variables; those belong to a different app.

Deploy, check authenticated health and read paths, then submit a new dummy
Business memory run and verify it after restart. If any verification fails,
revert the Render API/worker connection and do not accept writes on both
databases simultaneously.

## Rollback and non-goals

The source Render PostgreSQL remains untouched by the dump or restore steps.
Keep it as an emergency rollback until the target is verified and a separate
backup exists. Avoid split-brain writes after any switch.

No live database migration has been performed by writing this runbook.
No database secrets, backup archives or private table exports are committed
to GitHub.

References:
- https://render.com/docs/postgresql-backups
- https://supabase.com/kb/guides/migrate-from-postgres
- https://supabase.com/docs/guides/platform/backups
- https://supabase.com/docs/guides/api/securing-your-api
