# Live infrastructure audit — 2026-11-07 (metadata only)

This audit documents **verified** provider-level observations. It intentionally
omits all database credentials, connection URIs, session tokens, private
dataset descriptions and internal user details. It must not be confused with a
fresh table-level audit.

## Render workspace

Confirmed Render workspace: `Booooom`,
`tea-dbl9a3mgekts73fn0hgg`.

Services:

| Render resource | ID | Branch / database evidence |
|---|---|---|
| Main `research-atlas-api-test` | `srv-dbl9s03ncjis73d7i960` | branch `feat/shared-team-workspace`; 2026-11-07 06:26 UTC startup: `dialect=postgresql` |
| Experimental `research-atlas-science-staging` | `srv-dbm9j45bedkc73bkidog` | branch `feat/scientific-tool-registry-20261105`; 2026-11-06 latest audited startup: `dialect=sqlite` |
| Managed `research-atlas-test-db` | `dpg-dbl9idlg1s2s73e23bag-a` | Render PostgreSQL 17, Free plan, status available, expiry **2026-12-04 02:32 UTC**, external IP allowlist empty |

**Important:** the Postgres dialect log proves that the main API reached some
PostgreSQL server. It does *not* reveal whether the live `DATABASE_URL`
currently points to the Render instance above or a Supabase database.
The empty IP allowlist blocked Render MCP's read-only external SQL connector.
We deliberately **did not open public network access** to the database.

## Production run evidence

From the main API's **2026-11-07 06:26 UTC startup logs**:
- Verified team achievements: **36**
- Registered dataset assets: **28**
- Manually approved external papers: **0**
- Official research lines: **1**
- Startup succeeded, database dialect `postgresql`

An earlier **2026-11-04 11:15 UTC** read-only profile audit logged:
- Eligible metadata assets: **19**
- Restricted or unclassified assets: **9**
- Confirmed research-line links: **1**
- Evidence reference checks: pass
- Official profile was not changed by the audit
- Review draft exists; this is not a certified adopted profile

These are **historical log observations**, not live SQL row counts.
Do not extrapolate how many papers, feedback records or Agent runs exist today.

The staging service reported sqlite and zero registered assets in the
observed startup logs; this is **not** the team's authoritative corpus.

## Vercel configuration (variable names only)

The project `research-opportunity-workbench` has separate server-side
variables `RESEARCH_LAB_SUPABASE_URL` and
`RESEARCH_LAB_SUPABASE_SECRET_KEY` in the production environment.
These are associated with the **independent Research Agent Lab** routes.
Their existence does **not** establish that the main Render FastAPI
`DATABASE_URL` points to Supabase.

Other observed configuration **names only** include `BACKEND_URL`,
`API_BEARER_TOKEN`, `TEAM_AUTH_ENABLED`. No secret values were fetched.

## Critical decisions before deploying Business Agent memory

1. An administrator must confirm the **main Render API's current**
   `DATABASE_URL` provider/project by inspecting **host name only** in
   Render Environment (no screenshot showing credentials).
2. Select a **persistent**, backed-up PostgreSQL database as the authority for
   the main team corpus. Do not accidentally point the API at the staging
   SQLite DB or the separate Research Agent Lab Supabase project.
3. Perform a backup of the original database and verify restore to isolated
   staging. Do not wait until the Render Free database expires.
4. Inspect source/target schema and row counts in private infrastructure.
   Reconcile sequences, identity references, project-specific schemas and
   permissions before any data copy; preserve all historical rows.
5. Run the additive, reviewed migration
   `db/migrations/20261107_business_agent_memory.sql` on a restored
   staging database, followed by `tests/test_business_memory.py`.
6. If staging passes, migrate or attach the primary API to the selected
   persistent PostgreSQL database in a controlled deployment window; verify
   read-after-write and backup recovery.
7. Only then merge and deploy the Business Agent bridge, enable its **scoped**
   integration key, and test real persistent writes.
8. Implement a standards-compliant, authenticated custom MCP endpoint for
   Business; OpenAI documentation confirms Workspace Agent can attach custom
   MCPs. The REST bridge alone is not directly installable as an MCP app.
9. A Business workspace admin must create and connect the private Research
   Advisor Workspace Agent before scheduling weekly runs.

## Verification status

- GitHub PR #49: additive data model, REST endpoints and tests prepared.
- CI run 42378830694: all backend/frontend/tracker jobs **passed**.
- No production migration, data copy, backup verification or Workspace Agent
  installation has been executed through this audit.
- Render external SQL connector blocked by private allowlist; leave it private.

This document is a factual infrastructure snapshot, not an operations success
certificate.
