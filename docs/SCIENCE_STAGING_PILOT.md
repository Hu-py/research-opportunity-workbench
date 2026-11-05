# Scientific A/B pilot — isolated staging checklist (2026-11-05)

**Status:** Dedicated Render Free service deployed and reported LIVE. CI green.
Three public academic provider smoke calls succeeded with real network responses.
**No DeepSeek model calls have been made. No team database has been connected.**

## Staging resources
- Backend service (free): https://research-atlas-science-staging.onrender.com
- Render dashboard: https://dashboard.render.com/web/srv-dbm9j45bedkc73bkidog
- Backend branch: `feat/scientific-tool-registry-20261105`, `autoDeploy=no`.
- Data store: `sqlite:////tmp/science_staging.db` (ephemeral; **not backed up**).
- Vercel preview: branch-scoped encrypted `BACKEND_URL` has been added
  for the scientific tool branch, pointing to isolated staging.
  The Vercel preview build has **not** been refreshed: provider reported
  `402 api-deployments-free-per-day` limit. Older preview links may still
  point to the existing live backend. Do **not** enter staging API keys into
  an unverified preview URL.
- Existing Vercel production backend points to **research-atlas-api-test**.
  No change was made to that backend and it still serves the existing site.

## Persistence blocker verified 2026-11-05

The Render account already owns one active Free Postgres database. Creating
`research-science-staging-db` on the free tier was rejected by Render with
"cannot have more than one active free tier database". No paid database was
created and the existing team database was not modified.

The isolated staging service's current `/tmp` SQLite is an **ephemeral smoke
environment only**. We have a server-side guard
`SCIENTIFIC_PILOT_REQUIRE_POSTGRES=true` which rejects any paid A/B start
unless the database dialect is PostgreSQL. The zero-cost
`GET /api/scientific-tournaments/preflight?line_id=...` endpoint surfaces
`persistent_database`, model key/vault status, reviewed-paper counts and
remaining per-day model budget. The frontend also checks this before enabling
the A/B button.

**Recommended $0 trial database** (if an unused free slot is available):
an independent Supabase Free project named, e.g.,
`research-science-staging`. It must not be the project used by the live site.
Supabase allows up to two active Free projects across owner/admin
organizations; if no free slot remains, request the owner's decision instead
of silently provisioning paid storage.

From Supabase project **Connect**, select **Session pooler** if the backend
network requires IPv4. Copy its real host/user/port rather than reconstructing
it. In Render staging service **Environment**, set
`DATABASE_URL` to the corresponding **`postgresql+psycopg://`** driver URL,
with any reserved password characters percent-encoded and SSL required where
indicated. Never share connection strings in chats, issues, PRs or logs.

Configuring a new `DATABASE_URL` triggers a deployment and creates tables on
the **staging database**, so verify the Supabase project identity first. Do
not reuse production's `DATABASE_URL`. A free project can pause for
inactivity and does not provide automatic backups: export the sanitized
trial output after completion. No automatic task will start on first boot.

## Secure setup (user action; no keys in chat or GitHub)
1. First connect a **separate persistent PostgreSQL database** as described
   above; confirm the staging service's new deployment is LIVE and uses
   PostgreSQL. Keep `SCIENTIFIC_PILOT_REQUIRE_POSTGRES=true`.
2. In Render staging service Environment, configure
   `API_BEARER_TOKEN` (long random token), `APP_ENV=production`,
   `MODEL_VAULT_KEY` (Fernet-generated, keep stable),
   `TEAM_AUTH_ENABLED=true`, and
   `TEAM_BOOTSTRAP_ENABLED=true`, `TEAM_BOOTSTRAP_EMAIL`,
   `TEAM_BOOTSTRAP_PASSWORD` (a new strong staging-only password).
   Do not reuse production passwords. The bootstrap admin is created only
   if the test DB has zero members. Never log these values.
3. Reconfigure Vercel **preview branch-scoped** `API_BEARER_TOKEN` to
   match the staging API bearer, without changing its production target.
4. Rebuild only the isolated preview once its deployment cap permits.
   Verify its backend target and that it prompts for staging admin login.
5. Sign into that preview as staging admin. Go to AI 选题分析 and
   enter DeepSeek Key in the existing encrypted API key configuration UI.
   Keep daily automatic analysis **off**. Test a small manual run only.
6. To use **team-specific** literature instead of public demo papers,
   import a properly authorized metadata-only snapshot into an isolated
   **persistent staging database**. Do not point staging at the production
   DB without an explicit data-access and schema review.
7. Run `/api/scientific-tournaments/preflight?line_id=<line_id>`
   through the authenticated preview. It makes zero paid model calls.
   Require at least one manually approved paper, a configured model,
   a working vault and remaining 14 calls / 91,000 reserved tokens.
8. Start one manual A/B test. Neither arm may claim novelty verified.
   Obtain independently blinded reviews before opening the arm identity.
   Do not automatically transfer drafts into official research profiles.

## Important limitations
- SQLite in `/tmp` is container-ephemeral and can lose accounts, encrypted
  key, intermediate runs and results on a restart. Use a separate persistent
  PostgreSQL database before relying on trial results.
- Render Free may sleep and interrupt FastAPI background tasks; resume
  from durable checkpoints requires persistent storage.
- A/B shares snapshot evidence but does **not** match compute (4 versus up
  to 10 model requests); compare cost and add compute-matched control C
  before making a causal claim about multi-agent quality.
- The DeepSeek Key has not been provided, accessed, or charged.
- API provider tool smoke and CI mocks are not a live scientific-quality trial.
