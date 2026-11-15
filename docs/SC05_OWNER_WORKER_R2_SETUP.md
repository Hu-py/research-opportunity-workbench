# SC05 Owner → PostgreSQL queue → Render Worker → R2

**Status:** implementation branch only; not deployed. Review/tests before any production rollout.

## Why GitHub SC05 secrets are not necessary

The existing Next.js site already has an HttpOnly Owner session cookie. Its
server-side proxy attaches `Authorization: Bearer <API_BEARER_TOKEN>` and the
temporary `X-Research-Session` header when calling the private FastAPI backend.
The SC05 `POST /runs/{run_id}/start` endpoint checks active Owner membership
and explicit paid-model consent before adding an SC05Run row to PostgreSQL.

The browser never contacts R2, Render Worker, PostgreSQL or DeepSeek directly.
Neither `SC05_OWNER_SESSION` nor `SC05_API_BASE_URL` is required in GitHub
Actions for normal Owner-initiated experiments.

## Deploy targets

Only use the **isolated SC05 staging** infrastructure for the first paid trial.
Never reuse the production database or swap a Vercel production backend URL
without a separate deployment review.

1. Vercel preview: existing Research Atlas Next.js project.
2. Render API: existing FastAPI service connected to **isolated staging PostgreSQL**.
3. Render Background Worker: reuse an already-running, authorized Worker
   process or create one from the same repository/branch and `Dockerfile.worker`.
4. Cloudflare R2: existing **private** `research-atlas-assets` bucket.

The API and Worker MUST use the same source branch/commit and the same isolated
PostgreSQL `DATABASE_URL`. The worker runs continuously and consumes queued
SC05 jobs. R2 is a private backup of the durable PostgreSQL state.

## Exact environment variables

| Location | Variable | Value / security note |
|---|---|---|
| Vercel preview (server) | `BACKEND_URL` | HTTPS URL of the isolated SC05 Render API |
| Vercel preview (server) | `API_BEARER_TOKEN` | Existing API bearer token; match Render API |
| Vercel preview (server) | `TEAM_AUTH_ENABLED` | `true` |
| Vercel preview (server) | `SESSION_SECRET` | Existing strong secret; do not change during active sessions |
| Render API | `DATABASE_URL` | Existing **isolated** PostgreSQL URL |
| Render API | `API_BEARER_TOKEN` | Existing API bearer token |
| Render API | `TEAM_AUTH_ENABLED` | `true` |
| Render API | `APP_ENV` | `production` |
| Render API | `SC05_EXECUTION_MODE` | `worker` (switch only after Worker is LIVE) |
| Render API | `MODEL_VAULT_KEY` | Existing vault key, if encrypted model credentials are used |
| Render Worker | `DATABASE_URL` | The same staging database URL as API |
| Render Worker | `SC05_WORKER_ENABLED` | `true` |
| Render Worker | `SC05_R2_ARCHIVE_ENABLED` | `true` |
| Render Worker | `R2_BUCKET` | `research-atlas-assets` |
| Render Worker | `R2_ENDPOINT` | Private R2 S3 endpoint |
| Render Worker | `R2_ACCESS_KEY_ID` | R2 Object Read & Write key (bucket-scoped) |
| Render Worker | `R2_SECRET_ACCESS_KEY` | Corresponding R2 secret |
| Render Worker | `MODEL_VAULT_KEY` | **Same** key as API when using encrypted vault |
| Render Worker | `SC04_DEEPSEEK_API_KEY` | Alternative to encrypted vault: direct server-only provider key |

If direct `SC04_DEEPSEEK_API_KEY` is used instead of the vault, the API also
needs a provider-availability configuration because it checks credentials before
accepting a paid run. Easiest setup is an existing stable `MODEL_VAULT_KEY`
shared by API/Worker, with DeepSeek key configured in the Owner vault UI.
Do not generate a new `MODEL_VAULT_KEY` if existing encrypted records depend on
the previous one.

`R2_*` credentials should be present **only on the Worker** in this design.
The Worker needs no GitHub token, browser session, Owner email or password.
Do not set any of these secrets as `NEXT_PUBLIC_*` in Vercel.

## Deployment order

1. Verify isolated staging database backup, Owner membership, the existing
   paper's SHA and source-pinned SC05 pair. Take a private audit export.
2. Deploy the branch to the **existing staging** API while SC05 execution mode
   remains `background`, then deploy/redeploy the Background Worker using the
   identical commit and credentials. Check worker logs and PostgreSQL connection.
3. Set `SC05_WORKER_ENABLED=true` and `SC05_R2_ARCHIVE_ENABLED=true` only
   on Worker. Check no other unintended SC05 consumer is running.
4. Set `SC05_EXECUTION_MODE=worker` on the staging API. Verify its Vercel
   preview still proxies to exactly that service.
5. Log in as Owner at `/devstudio/sc05`. Create a cheap test case/pair first,
   confirm consent=false does not create a job and consent=true creates exactly
   one queued run. Check queued → claimed → running → complete/failed.
6. Verify R2 has `sc05/<source_sha>/<run_id>/source_pages.json`,
   `checkpoints/stage-XXX.json`, `manifest.json`, and after completion,
   `report.md` and `result.json`.
7. Only then resume the first real failed SC05 A via its `repair-check`; do not
   begin B until A finishes and shared evidence is frozen. Verify preserved
   first paid stage before authorizing additional DeepSeek usage.

## Important limitations

- Existing SC05 `pipeline_sha` includes `sc05_eval_api.py`: deployment
  changes its hash. A legacy run can be migrated **only** by the validated
  safe parser repair or the verified unstarted B-arm migration already in the
  server, and never by silently overwriting old checkpoints.
- PostgreSQL commit is authoritative. If R2 fails, log a nonfatal archive
  warning; do **not** replay paid model calls to fix a storage error. Replay
  archival from PostgreSQL once R2 is restored.
- A worker terminated while status is `claimed`/`running` leaves an
  incomplete run that needs operator inspection. Automatic stale-job stealing
  is intentionally disabled to avoid duplicate DeepSeek charges. Add
  heartbeat/lease and manual recovery only after first end-to-end validation.
- R2 stores **extracted source page text**, not the original PDF binary. The
  current PDF endpoint stores extracted pages in PostgreSQL; a separate
  presigned upload scheme is needed to persist original PDFs without giving
  R2 keys to the browser.
- SC05 test results remain unverified until real A/B model reports exist,
  audit is reviewed, and blinded grading is completed.
- Render continuously-running Background Workers are not included in its
  free-service types; verify pricing before creating a new paid service.
  Free Render PostgreSQL may expire; use a durable backed-up database for
  long-term research records.
