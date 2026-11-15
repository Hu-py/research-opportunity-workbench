# SC05 Owner -> Worker -> R2 deployment audit | 2026-11-15

## Verified actions
- User confirmed Render workspace Booooom, ID `tea-dbl9a3mgekts73fn0hgg`.
- Isolated SC05 test API `research-atlas-devstudio-e2e-ejmh` (`srv-dbs1tg6i0phs73bt8c1g`) uses branch `experiment/devstudio-postgres-e2e-20261114`, Dockerfile `Dockerfile.devstudio-e2e`, free plan in Singapore and `autoDeploy=no`.
- PR #91 for Owner-authenticated queue and R2 archival passed GitHub CI, merged to **isolated test branch only** with commit `384aaa6e40334e9b8f1ff158d911697a32f8d679`.
- Render deploy `dep-dbsopt3rjlhs739tngi0` triggered manually and reported **live**. No paid model call was initiated by the deploy.
- There is **no independent Render Background Worker** in the confirmed workspace: only three free Web Services.
- The only available Render PostgreSQL service is `research-atlas-test-db` (`dpg-dbl9idlg1s2s73e23bag-a`), plan free, reported available and set to expire 2026-12-04.
- A read-only Render Postgres query was refused due to SSL/TLS / external IP allowlist. We deliberately did not weaken the allowlist. Saved SC05 rows are not independently verified in this audit.
- Latest deploy retains default SC05 BackgroundTasks execution because `SC05_EXECUTION_MODE=worker` was **not enabled**, avoiding queued work without a consumer.
- R2 roundtrip from GitHub Actions was previously confirmed, but R2 credentials are **not yet confirmed on a Render Worker**. SC05 R2 backup is not yet enabled.
- Vercel front-end deployment is separate and not altered by this API-only deployment.

## Next steps requiring explicit billing/secret action
1. Choose whether to provision a paid 0.5 CPU / 512 MB Render Background Worker at approximately $7/month. Do not create or change billing without approval.
2. Create the Worker pointing to this exact isolated branch and `Dockerfile.worker`, same isolated staging `DATABASE_URL`, same model secret/vault key. Set `SC05_WORKER_ENABLED=true` and `SC05_R2_ARCHIVE_ENABLED=true`.
3. Set `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` in Worker Environment. Never transfer R2 secrets into GitHub code, chat, logs, or NEXT_PUBLIC vars.
4. Verify a running Worker and same pipeline/version and isolated database before setting `SC05_EXECUTION_MODE=worker` on the API.
5. Run a no-model task / isolated SC05 smoke and verify R2 checkpoints, then invoke the existing Owner-authenticated SC05 failed-run `repair-check` prior to any additional DeepSeek calls. The first paid stage must not be repeated.
6. Confirm published Vercel preview `BACKEND_URL` targets exactly this isolated test API; do not change production aliases.
