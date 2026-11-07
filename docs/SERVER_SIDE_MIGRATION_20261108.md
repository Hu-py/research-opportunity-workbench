# Render → Supabase server-side migration report

**Status: BACKUP + RESTORE + INDEPENDENT READ-ONLY VERIFICATION SUCCEEDED. PRODUCTION CUTOVER NOT PERFORMED.**

Date: 2026-11-07 UTC / 2026-11-08 China time.

## Source and destination

- Source: Render PostgreSQL 17 `research_atlas_test_db`, currently still the main
  service's `DATABASE_URL`. Free Render source expires 2026-12-04.
- Destination: separately provisioned Supabase PostgreSQL 17.11, accessible
  only via the existing private server-side secret
  `MIGRATION_TARGET_DATABASE_URL`. The destination is not the separate
  Research Agent Lab Supabase database.
- Render web backend: `research-atlas-api-test` (Singapore); deployment branch
  `feat/shared-team-workspace`.
- The owner was NOT asked to paste any credentials in chat or GitHub.
- An old temporary Render database allowlist rule for the Mac was present on
  inspection; it should be removed in Render > PostgreSQL > Networking now
  that the Mac backup route is no longer needed. This repository cannot
  directly revoke the rule through the available connector actions.

## Verifiable execution evidence

1. **Before migration**: source database 43 public tables, 9.76 MB.
   Source includes 55 team-achievement rows (36 previously described as
   verified), 28 registered dataset assets, one profile and one team member.
   The destination had zero public tables.
2. **Backup**: Render application startup created a PostgreSQL 17 custom-format
   `pg_dump` with source `public` schema and 43 tables, checked its
   `pg_restore --list` table of contents and SHA-256, and stored the archive
   in a restricted `migration_private.archive` table in the destination.
   Log at 2026-11-07 16:27:52 UTC:
   `SERVER_SIDE_MIGRATION_RESULT ... "phase":"backup","result":"saved","bytes":170170,"tables":43`.
3. **Restore**: The program loaded the checkpoint and verified its checksum,
   disabled Supabase Data API-role schema access, and ran a
   `pg_restore --single-transaction --exit-on-error` into the previously
   empty `public` schema. Post-restore, it checked **every table's count**
   against the snapshot, enabled RLS on all 43 app tables, and revoked
   access to the copied tables and seven sequences from public API roles.
   Log at 2026-11-07 16:31:21 UTC:
   `SERVER_SIDE_MIGRATION_RESULT ... "phase":"restore","result":"restored",
   "tables":43,"counts_match_snapshot":true,"rls_enabled":true,
   "sequences_protected":7`.
4. **Independent recheck after restart**: A new read-only connection queried
   the persisted target and original source. The 43 target table row counts
   match the archive and current source; all restored foreign keys are
   validated; all target app tables have RLS; and Supabase Data API
   `anon`, `authenticated`, and `service_role` lack access to the public
   schema. Log at 2026-11-07 16:35:36 UTC:
   `SERVER_SIDE_MIGRATION_RESULT ... "phase":"verify","result":"verified",
   "row_counts_match_backup":true,"source_counts_match_backup":true,
   "rls_enabled_for_all_tables":true,"all_foreign_keys_validated":true,
   "public_schema_closed_to_data_api":true`.

Archive: **170,170 bytes**.
SHA-256: `1cda9182051c6461ddb6396d30ae28c60553f309c4a31b818c104ca9e4feed13`.

The archive is privately accessible within the destination database, not a
public URL, repository attachment, or temporary local file.

## Important remaining limits

- **No cutover**: The running Render FastAPI still reads/writes the old
  Render PostgreSQL `DATABASE_URL`, which was never changed.
- **Not an independent off-site backup**: The archive is in a private schema
  of the **same Supabase project** as the restored data; loss of that whole
  project could destroy both. The separate original Render PostgreSQL remains
  an independent source until expiration but must not be treated as permanent
  backup.
- **Possible post-snapshot changes**: Source row counts matched at the
  read-only verify stage. Counts alone cannot exclude modifications to
  existing rows made after the snapshot.
- **No actual Business Workspace Agent connected or deployed**: the
  versioned Business Agent bridge and Skill remain in draft PR #49.
- **No object-storage files were copied**; this covers only the source
  PostgreSQL `public` schema.

## Final cutover gates (not yet performed)

1. Create/test a genuinely independent private offsite backup or a paid
   provider backup, and verify its restore.
2. Freeze or queue all source application writers before the final catchup.
   Audit row integrity (prefer canonical row hashes as well as counts) and
   handle any source updates since the checkpoint.
3. Verify team login, member permissions, profile, data metadata and
   historical Agent records with a separately initialized target test.
4. Switch the backend's active database using secrets stored on Render,
   without revealing credentials. Update any separate writer consistently.
   Monitor errors, read-after-write and service restarts.
5. Keep old Render PostgreSQL intact for rollback and remove temporary
   external network allowlist entries. Schedule ongoing verified backups.

## One-time execution safeguards

The server-side migration is enabled ONLY by the Render environment
`MANAGED_MIGRATION_PHASE=backup|restore|verify`; normal mode is `0`.
The process prints only fixed safe status and hashes (no URI/user/password/
row values). Backup is idempotent by an immutable checkpoint run key.
Restoration requires the target schema to be empty, so a repeat cannot
silently overwrite the copy. The source is never written by migration code.
