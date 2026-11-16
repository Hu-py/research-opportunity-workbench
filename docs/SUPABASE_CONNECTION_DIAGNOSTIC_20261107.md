# Supabase target connectivity diagnosis — 2026-11-07

**Source:** live Render `research-atlas-api-test` service logs, sanitized one-time checker.

- Operator added `MIGRATION_TARGET_DATABASE_URL` in the Render service; secrets were not read or pasted to GitHub.
- Read-only target preflight deployed using current service branch `feat/shared-team-workspace`.
- Source PostgreSQL remained reachable and the application started normally.
- First check: `MIGRATION_PREFLIGHT_FAILED category=connection_failed`.
- A more specific, privacy-preserving error classification at 2026-11-07 14:57 UTC returned:
  `MIGRATION_PREFLIGHT_FAILED category=dns_resolution_failed`.
- This is a hostname-resolution failure **before** PostgreSQL authentication.
  A mistaken/partial connection host or provider DNS/IPv4 configuration
  should be checked before retrying. Do not assume the database password is wrong.
- No table writes, migrations, backups or API database cutover occurred.
- One-time flag `MIGRATION_PREFLIGHT_ON_STARTUP` was reset to `0`, and
  the ordinary Render service deployment reached `live` at 14:58 UTC.

## Next operator check

In Supabase > new `research-team-memory` project > **Connect** >
**Session pooler** > **URI**, copy the complete connection string.
Validate privately: scheme `postgresql://`, username, complete host
ending `.pooler.supabase.com`, port `5432`, database `postgres`.
Replace any password placeholder privately and URL-encode reserved password
characters if necessary. The complete URI must stay exclusively in Render's
`MIGRATION_TARGET_DATABASE_URL` server environment variable. Never replace
the existing `DATABASE_URL` or place secrets in GitHub.

After the operator corrects the value, rerun a one-time preflight from the
admin-authenticated `/api/admin/migration-target-preflight` endpoint or
temporarily opt in to startup diagnostics and turn them off again. Confirm
`connected=true`, `source_and_target_distinct=true`, and
`target_public_schema_empty=true` before a backup/restore run.

**A successful connection preflight is not a successful migration.**
