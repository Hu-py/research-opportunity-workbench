# Business Research Advisor — durable memory foundation (draft)

## What is already there

This is an **additive** integration with the existing Research Opportunity Workbench:
- Existing authoritative records remain in `profiles`, `team_profile_revisions`,
  `team_achievements`, `cusp_datasets`, `papers`, `research_evolution_runs`,
  `research_evolution_feedback` and other original tables.
- Existing public-safe evidence exporter `backend/research_evidence_export.py`
  selects verified achievements, *public-only* dataset metadata, and manually
  approved external paper entries. It does not export private data files.
- This bridge introduces three distinct tables:
  `business_agent_runs`, `business_agent_ideas`,
  `business_meeting_feedback`.
- Agent proposal revisions are append-only and cite a previous idea ID.
  One run key cannot silently overwrite an earlier submission.
- The Business model must never treat its conversation as the durable state.

## What this does NOT yet do

- No migration or production deployment has been performed by this branch.
- No live Supabase or Render row count has been verified.
- This currently exposes a secure REST adapter, **not yet a ChatGPT custom MCP
  server**. Business Workspace Agent configuration/connection is a separate step.
- No weekly scheduled Agent has been created.
- `create_all` creates newly absent tables but does **not** migrate existing
  column changes or verify data backups. Do not use it as a migration strategy.

## Critical first check: where does production DATABASE_URL point?

The original repository documentation discusses both an expiring **Render Free
PostgreSQL** test database and a later **Supabase** deployment. These may be
different databases. Do not assume GitHub, Render, Vercel and Research Agent Lab
all use the same database.

An administrator must verify the active Render service's `DATABASE_URL` target
*privately*, without sending credentials to a chat or committing a connection
string. Before any schema application:
1. Record the selected provider and **project ID/hostname only** in an internal
   deployment register; never commit user/password/token.
2. Make a complete database backup and test restore to a separate database.
3. Inspect schema differences and identify any old data to preserve.
4. Apply the additive changes in staging and rerun tests.
5. Deploy the backend against the intended persistent database.

A read-only audit endpoint is included:
`GET /api/business-agent/storage-audit`
with the existing backend bearer token and an authenticated **admin**
`X-Research-Session`. It returns expected table presence and counts of
only the three new tables, not row content or connection strings.

## Opt-in REST bridge, disabled by default

Set **only on the FastAPI/Render server**:

```env
BUSINESS_AGENT_BRIDGE_ENABLED=true
BUSINESS_AGENT_SHARING_APPROVED=true
BUSINESS_AGENT_BRIDGE_TOKEN=<new independent cryptographically random 40+ character secret>
```

Do not use the same secret as `API_BEARER_TOKEN`, GitHub Actions, Vercel,
Supabase `service_role`, or a user password. Keep these values in server-side
secret storage. Rotate them after any suspected disclosure.

The key has two deliberately narrow privileges:
- `GET /api/business-agent/context`: bounded public-safe evidence,
  prior Business meeting decisions, and a SHA-256 `context_hash`.
- `POST /api/business-agent/runs`: create new immutable research submissions
  with a stable `run_key`, matching context hash, provenance references, and
  explicit `external_papers_unverified` labels.

Header for those two routes: `X-Research-Agent-Key: <secret>`.
No human accounts or unrestricted database access are exposed to the agent.

The endpoints use SQLAlchemy transactions; a duplicate run key with identical
payload is idempotent. A duplicate key with different payload or a stale context
hash produces HTTP 409. Unknown/unapproved evidence IDs are rejected with 422.
Existing profile and evidence tables remain unchanged.

## Human meeting feedback

Authenticated team researchers/admins may post to
`POST /api/business-agent/ideas/{idea_id}/feedback`
with the original backend bearer + X-Research-Session. Fields:
`decision` (adopt/revise/defer/reject), `novelty`, `feasibility`,
`scientific_value`, `testability` (1–5) and `comment`.

An agent's service key **cannot** forge feedback. Reviewers may review each
individual proposal version once. Review data enters the next context bundle;
the original proposal remains unchanged. Feedback does not automatically
change official team profile or train model weights.

## Data integrity and privacy

- Team documents in `internal` and `restricted` sensitivity are not exported.
  Only public-safe metadata is eligible. Explicit sharing approval remains
  mandatory even for those records.
- The bridge stores the exact bounded database context used for each submitted
  run as `snapshot_json`. Restoring a run does not require ChatGPT memory.
- External paper URLs are labeled **unverified** and are not inserted into
  `papers` as approved scholarly sources by the Agent bridge.
- New proposal input is untrusted. Never execute it as code or use it as SQL.
- Review the visibility and privacy of any Business Agent and its connected app
  before authorizing model access to real team metadata.
- Plan backups, key rotation, least-privilege DB accounts, RLS/access rules and
  a dedicated migration tool (Alembic) before relying on this system for
  irreplaceable data. The backend's existing owner API key must stay server-side.

## Testing and release gate

The new tests cover: disabled/unauthorized integration; restricted dataset
non-export; valid proposal storage and readback; idempotency; stale/fake
references; admin diagnostics; authenticated human feedback; feedback recall.
CI runs the full backend test suite via `pytest`.

Acceptance requires:
1. CI passes on the development branch.
2. Staging backup/restore completed.
3. Production database host selected and verified privately.
4. Admin storage-audit endpoint confirms new tables on that **live** target.
5. One end-to-end Business Agent or test MCP submission round-trip verified.
6. Read-after-write still works after the service restarts.

## Agent creation: subsequent step

After the storage foundation passes its release gate:
1. Add a small MCP adapter with precisely these functions:
   `get_research_context`, `submit_research_run`, `get_run_history`.
2. Test its authorization and confirm no human-feedback write tool is exposed
   to the Agent.
3. Workspace admin opens **Agents → Create** and creates
   `Research Advisor` in the Business workspace.
4. Attach a version-controlled research skill; add the approved MCP app
   with a dedicated service-account connection; first test manually.
5. Publish only after verifying agent writes a record and another team member
   can see it without relying on chat history.
6. Then configure a weekly schedule and cost/quality caps.

The MCP server must be publicly reachable over HTTPS and authenticated using
a Business-supported connection mechanism. Do not paste integration tokens into
agent instructions or the workspace-wide chat. Do not claim the REST endpoint
itself is an MCP tool.

## Rollback

If the new bridge misbehaves, set
`BUSINESS_AGENT_BRIDGE_ENABLED=false` and redeploy. This disables external
Agent access without deleting any historical table or row. Do not drop the
three new tables as an emergency response; preserve evidence for investigation.
