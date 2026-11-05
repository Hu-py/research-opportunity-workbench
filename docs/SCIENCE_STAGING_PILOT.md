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

## Secure setup (user action; no keys in chat or GitHub)
1. In Render staging service Environment, configure
   `API_BEARER_TOKEN` (long random token), `APP_ENV=production`,
   `MODEL_VAULT_KEY` (Fernet-generated, keep stable),
   `TEAM_AUTH_ENABLED=true`, and
   `TEAM_BOOTSTRAP_ENABLED=true`, `TEAM_BOOTSTRAP_EMAIL`,
   `TEAM_BOOTSTRAP_PASSWORD` (a new strong staging-only password).
   Do not reuse production passwords. The bootstrap admin is created only
   if the test DB has zero members. Never log these values.
2. Reconfigure Vercel **preview branch-scoped** `API_BEARER_TOKEN` to
   match the staging API bearer, without changing its production target.
3. Rebuild only the isolated preview once its deployment cap permits.
   Verify its backend target and that it prompts for staging admin login.
4. Sign into that preview as staging admin. Go to AI 选题分析 and
   enter DeepSeek Key in the existing encrypted API key configuration UI.
   Keep daily automatic analysis **off**. Test a small manual run only.
5. To use **team-specific** literature instead of public demo papers,
   import a properly authorized metadata-only snapshot into an isolated
   **persistent staging database**. Do not point staging at the production
   DB without an explicit data-access and schema review.
6. Run `/api/scientific-tournaments/preflight?line_id=<line_id>`
   through the authenticated preview. It makes zero paid model calls.
   Require at least one manually approved paper, a configured model,
   a working vault and remaining 14 calls / 91,000 reserved tokens.
7. Start one manual A/B test. Neither arm may claim novelty verified.
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
