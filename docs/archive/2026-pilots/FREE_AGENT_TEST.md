# Research Agent: zero-additional-cost integration test (Render Free)

This guide is for the **existing** Research Atlas lab deployed on a Render Free
Web Service + Render Free PostgreSQL + Vercel. It **does not** provision a paid
Background Worker, cron job, model API, or additional Web Service.

## What works

With `WORKER_MODE=background`, an authenticated researcher or admin submits
an `explore`, `sync`, or `weekly` job via the Next.js web UI. FastAPI first
commits a `research_tasks` record to PostgreSQL, responds with HTTP 202, and
then schedules `run_task` with FastAPI/Starlette `BackgroundTasks`.
The job uses the **same** PostgreSQL database and writes logs, status, paper
evidence, and results back to that record. The existing web UI polls task
progress and displays the result.

An already **queued** task can be retried from the task card via
`POST /api/tasks/{id}/dispatch`. Only admins and researchers can trigger it,
and only `queued` tasks are eligible. Worker claims are atomic at the database
layer, so duplicate dispatch requests do not run a queued task twice.

Without `OPENAI_API_KEY`, `explore` produces **bibliographic_preview**:
search saved papers, optionally search OpenAlex for real paper metadata,
show titles/URLs/evidence, and explicitly **do not claim LLM method transfer**.
You can test this with zero LLM spend.

## Enable in your existing free environment

1. In the [existing API Environment](https://dashboard.render.com/web/srv-dbl9s03ncjis73d7i960),
   set `WORKER_MODE=background`. Keep `APP_ENV=production`,
   `TEAM_AUTH_ENABLED=true`, `API_BEARER_TOKEN`, and `DATABASE_URL`.
   **Do not** copy secrets into GitHub or chat.
2. Deploy the updated **main** (or the reviewed feature branch for a preview).
   Confirm the startup log:
   `Inline research jobs enabled: not durable across free-instance sleep or restarts`.
3. In the [Vercel team workspace](https://research-opportunity-workbench.vercel.app),
   sign in with a team member account as admin or researcher.
4. Open **Research Agent** and submit a short question like
   `城市空间功能识别中，少标签图学习有哪些值得验证的方法？`.
5. Look for job transition `queued -> running -> completed`. The results
   must explicitly say **无模型模式：文献证据预览** / `bibliographic_preview`
   if no LLM credentials have been added. The paper links should be manually
   checked before drawing scientific conclusions.
6. If a previously queued job remains queued, use
   **重新启动排队任务**. This cannot repair a task already stuck in `running`
   after the free instance is restarted; create a new task.

## What this test **does not** provide

- **No durable worker.** Render Free Web Services go idle; instance recycling,
  deploys and crashes can interrupt active tasks. `BackgroundTasks` is a
  per-process convenience, not persistent orchestration. Completed output is
  durable in PostgreSQL, but running jobs are **not** guaranteed to finish.
- **No unattended scheduled tasks.** The frontend or a user must submit a
  task; nothing runs on a clock or when the free service is asleep.
- **No per-team concurrency guarantees.** Do not start large collections of
  expensive or long-running queries on a 512 MB free container.
- **No automatic task recovery.** In-progress jobs interrupted by restarts
  may require a replacement task or manual status remediation.
- **No model-backed reasoning without a key.** Supplying `OPENAI_API_KEY`
  can incur model API charges and is not required for this test.
- **No guaranteed data retention.** The Render Free PostgreSQL database
  created November 4, 2026 expires on **December 4, 2026** without automatic
  backups. Do not import unique or confidential research assets.

For long-term use by ten people, migrate to a persistent managed PostgreSQL
instance with backups, a separate durable Worker, and controlled access to
model inference. Keep `WORKER_MODE=queue` on the API when the separate
worker is running; that is the default production configuration.

## Diagnostic checklist

| Symptom | What to check |
| --- | --- |
| Job stays queued | `WORKER_MODE=background` is set on Render API and a new deployment is `Live`; retry queued job from the UI |
| Job runs and fails | Open its task event trail; check relevant Render logs and OpenAlex connectivity |
| Result says bibliographic preview | Expected: no LLM model credentials were supplied |
| Job remains running after redeploy | Process was interrupted; create a new task (no automatic recovery in this prototype) |
| Unable to log in | Frontend and API `TEAM_AUTH_ENABLED=true`, member active, credentials correct |
| File/data concern | Do not use Render Free for important persistent research content |

The free test is an explicit opt-in; changing `APP_ENV` alone does not
enable inline execution in production.
