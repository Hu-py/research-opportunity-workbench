# Research Advisor: Supabase-native MCP v0.1

## Why this exists

The team wants ChatGPT Business Research Advisor to read its own durable team
research knowledge without depending on Render or the eventual Vercel UI.
This **separate Supabase Edge Function** implements the first read-only stage.
It does not replace the existing Research Atlas website or its API.

**Project**: existing `research-team-memory` Supabase project.
**Function**: `research-advisor-mcp`.
**Endpoint after deployment**:
`https://tfyfupxabojddixwjkat.supabase.co/functions/v1/research-advisor-mcp`.

### Actual status as of 2026-11-08

- Code in branch `feat/supabase-native-mcp`.
- Deno type checking, default-deny policy unit tests, and safe-code checks pass.
- No authenticated live user/client session or ChatGPT Business Agent connection
  has occurred.
- No Supabase Edge deployment has occurred through this conversation yet.
- The existing Render Postgres→Supabase **database migration is already done**.
  The new function reads the same Supabase PostgreSQL; there is no new data
  import, backup or secondary database.
- The existing Render service remains the primary web backend and is not deleted.

## Tools (all read-only)

1. `get_research_context()`: 80 most recent verified publication records,
   only fields id/title/year/kind/venue/DOI/tags; up to 25 public-labelled
   dataset catalogue entries, fields id/name/category/coverage/period.
   Restricted-name patterns are excluded and raw datasets, file paths,
   custodians, authors' private details, passwords and secrets are never read.
   Returns an explicit title-only evidence warning and SHA-256 context hash.
2. `list_research_runs(limit=10)`: up to 20 persistent Business Agent run IDs,
   topics, timestamps and proposal counts.
3. `get_research_run(run_id)`: a persisted run and its versioned idea records.
   No internal research data files are exposed.

**There is no write-capable MCP tool in v0.1.** After successful live OAuth
authorization and cross-session read-back, implement a transactional,
evidence-referenced, auditable `submit_research_run` that preserves the
existing Python-side rules and refuses duplicate run keys.

## Security model

The Supabase Auth OAuth Server signs and verifies user JWTs. Per the official
Supabase MCP guide the function uses
`withOAuthProtectedResource()` and `withSupabase({ auth: "user" })`
before calling any tool. It additionally fetches the user using
`supabase.auth.getUser(token)` and verifies that the signed claims match:

- JWT issuer points **exactly** to this team's Supabase Auth project.
- JWT role/audience is authenticated.
- The signed JWT's `sub` equals the actual verified Supabase Auth user ID.
- The signed `client_id` belongs to the owner-approved OAuth client allowlist.
- Both user and client must be explicitly allowed; blank or wildcard lists
  refuse access.

The existing PostgreSQL `public` app tables deliberately have no direct
`authenticated` access (a protection added during the source migration).
To avoid loosening those database grants, fixed, bounded, read-only queries
run inside the Edge Function with the Supabase-injected `SUPABASE_DB_URL`.
The function uses a maximum of one PostgreSQL connection per Edge instance,
disables prepared statements, requires TLS and sets each transaction read-only.

**Important trust boundary**: The database connection is privileged.
A bug in the Edge Function could expose information, so the function must be
audited before enabling it. There is no generic SQL interface, no raw
dataset endpoint, and no user-supplied table names. Longer term, provision a
dedicated least-privilege DB role.

The gateway setting `verify_jwt=false` is **required for OAuth discovery**
and does *not* mean tools are public: requests must pass the separate Supabase
OAuth middleware and user/client gates. All MCP requests are rejected with
HTTP 503 when `RESEARCH_MCP_ENABLED` is not `true`.

## Deployment

The function is **not deployed automatically**. Before connecting users:

1. Create a dedicated Supabase personal access token via
   Supabase Dashboard → Account → Access Tokens, for deployment management.
   Never paste it into chat, a repository file or an Agent instruction.
   Store it as the GitHub **Actions repository secret**
   `SUPABASE_ACCESS_TOKEN` for `Hu-py/research-opportunity-workbench`.
2. Use the manually triggered GitHub Actions workflow
   `Deploy native Supabase Research MCP` (defined on the default
   branch), which checks out a **tested, pinned commit** and invokes
   `supabase functions deploy research-advisor-mcp --project-ref
   tfyfupxabojddixwjkat --no-verify-jwt --use-api`.
   It deploys no other functions or SQL migrations.
3. After the endpoint exists it remains HTTP 503 until the owner configures
   Edge Function Secrets:
   ```text
   RESEARCH_MCP_ENABLED=false
   RESEARCH_MCP_ALLOWED_USER_IDS=<explicit approved Supabase Auth user UUIDs>
   RESEARCH_MCP_ALLOWED_CLIENT_IDS=<explicit trusted Supabase OAuth client IDs>
   ```
   Only then intentionally set `RESEARCH_MCP_ENABLED=true`.
   Do NOT put the API publishable key or a service-role key in these lists.
   A business workspace seat is not itself a Supabase Auth user identity.
4. Supabase OAuth is already enabled. It still needs a working sign-in and
   consent page: today `/oauth/consent` is available through the existing
   Render service, while the complete Research Atlas dashboard remains on
   Vercel. This consent page is an **authentication dependency only**; it
   is not an MCP server and may be moved to another static host later.
5. For a client that requires dynamic OAuth registration, use the Supabase
   OAuth Server setting only after the consent page and origin have been
   verified. Approve each client; don't create wildcard grants.
6. Validate HTTP 503 when disabled, 401 without a user JWT, 403 with an
   unauthorized OAuth subject/client, valid discovery metadata, and the
   three actual read tools. Then create/connect ChatGPT Business plugin.
7. For a durable-memory acceptance test: read context, inspect an existing
   run, restart the session and confirm the same database record can be
   retrieved independently of conversation history.

## Read-only test commands

From the checked-out branch, GitHub CI already runs:

```
deno check supabase/functions/research-advisor-mcp/index.ts
deno test supabase/functions/research-advisor-mcp/auth_policy.test.ts
```

## Out of scope

- User-approved Agent write operations.
- Daily paper crawling, 80-paper batch analysis and multi-Agent debates.
- Human-review recording and feedback reinforcement.
- Full Next.js/Vercel research visualizations.
- Long-running scheduler/workers.
- Independent off-site database backup (still required; do not delete the
  old Render PostgreSQL until an independently verified backup exists).

## Official references

- https://supabase.com/docs/guides/ai-tools/byo-mcp
- https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication
- https://supabase.com/docs/guides/functions/deploy
- https://supabase.com/docs/guides/functions/secrets
