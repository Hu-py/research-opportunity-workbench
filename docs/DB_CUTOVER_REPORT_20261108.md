# Research Atlas database cutover and Business Agent bridge — 2026-11-08

## Status

**The main Render FastAPI service successfully switched from expiring Render
PostgreSQL to the isolated Supabase PostgreSQL project.** The original
Render DB and its connection string remain preserved for rollback.
The separate Research Agent Lab Supabase project was not used or modified.

## Verified live milestones

| Step | Live evidence (UTC) | Result |
|---|---|---|
| Source inventory | 2026-11-07 15:10 | 43 tables; 9.76 MB |
| Target readiness | 2026-11-07 15:06 | Supabase PG17.11, empty, distinct |
| Snapshot backup | 2026-11-07 16:27 | 170,170-byte logical archive |
| Target restore | 2026-11-07 16:31 | All 43 tables, row counts verified, RLS on |
| Persistent restore verification | 2026-11-07 16:35 | Tables, FKs, RLS, Data API roles all verified |
| Content integrity gate | 2026-11-07 17:02 | All 43 table content hashes identical; write/rollback test passed |
| Successful primary cutover | 2026-11-07 17:05 | Render deployment live with Supabase selected |
| Normal service restart | 2026-11-07 17:07 | Startup normal; 36 verified outputs, 28 assets, one official line |
| Business memory adapter deployment | 2026-11-07 17:12 | Private bridge code deployed with opt-in external access disabled |

The content comparison initially reported one mismatch in `team_audit`;
it arose from database-dependent sorting while hashing rows. Recomputing
hashes with PostgreSQL `COLLATE "C"` produced **43/43 identical table
content hashes**. No data values, authentication credentials or row IDs
were printed.

## Database selection and rollback

The running Render web service chooses its database through:

- `RESEARCH_DATABASE_PROVIDER=supabase` — active project selected.
- `MIGRATION_TARGET_DATABASE_URL` — private target PostgreSQL URL on Render.
- `DATABASE_URL` — **unchanged original Render PostgreSQL URL**, retained for rollback.
- `MIGRATION_CUTOVER_GUARD=0` — one-time guard disabled after verified switch.
- `MIGRATION_FREEZE_WRITES=0` — normal write operations re-enabled.
- `MANAGED_MIGRATION_PHASE=0` — backup/restore/check jobs disabled.

Rollback is a controlled Render environment update to
`RESEARCH_DATABASE_PROVIDER=render`, followed by an app restart. A
rollback after new Supabase writes needs **data reconciliation first**;
blindly reverting would lose those new writes. Do not delete old DB,
reveal secrets, or reset database credentials merely to switch providers.

## Private Business Research Advisor data model

The live service now includes three versioned research memory tables:
`business_agent_runs`, `business_agent_ideas`,
`business_meeting_feedback`. Its startup code enables RLS and revokes
public/API-role table privileges. Existing team research records remain
authoritative. Business Agent external access is **disabled by default**;
the REST bridge is not a production OAuth MCP server and is not yet
attached to a ChatGPT Business Workspace Agent.

To activate later requires a separately generated service credential,
an explicit team data-sharing approval, HTTPS authentication/authorization
review, and a compatible remote MCP adapter / supported Workspace Agent
connection. Never store provider secrets in GitHub.

## Important unresolved safeguards

1. The logical dump lives in the destination's protected
   `migration_private.archive` schema; it is a recoverable **checkpoint**,
   **not independent off-site storage**. The old Render PostgreSQL is a
   temporary independent source but expires **2026-12-04**.
   Configure separate, tested encrypted backups before that deadline.
2. Supabase target is in the United States West region; the Render API is
   in Singapore. Cross-region latency can affect performance. SQLAlchemy
   session-factory caching and bounded pooling are staged to reduce
   repeated schema introspection; monitor slow queries and use a regional
   alignment plan if latency becomes material.
3. Temporary Render PostgreSQL Networking allowlist
   ("Temporary Mac backup") was still present at
   the last provider check. Remove it from Render's **PostgreSQL Inbound
   IP Rules** once external Mac backup is no longer needed.
4. Only PostgreSQL `public` schema was migrated; independent object-storage
   files and the separate Research Agent Lab DB were intentionally excluded.
5. Long-term research source sync, backup verification, Business Agent
   connection and scheduled weekly runs are separate follow-up tasks.

## Links

- Main Render service:
  https://dashboard.render.com/web/srv-dbl9s03ncjis73d7i960
- Original Render PostgreSQL:
  https://dashboard.render.com/d/dpg-dbl9idlg1s2s73e23bag-a
- Detailed backup/restore history:
  `docs/SERVER_SIDE_MIGRATION_20261108.md`
- Business Agent Skill:
  `skills/business_research_advisor/SKILL.md`
