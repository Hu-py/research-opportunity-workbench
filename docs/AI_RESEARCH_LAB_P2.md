# P2: DeepSeek AI Research Lab

## In-app configuration

Open https://research-opportunity-workbench.vercel.app and sign in as a team **administrator**.
Choose **AI 选题实验台** in the sidebar. The **DeepSeek 模型连接** panel
contains a masked API Key field, model selection and an opt-in daily-analysis
switch. Keys are never displayed again.

### Encryption and scope

- The Render backend needs an independent `MODEL_VAULT_KEY` (a Fernet key).
- Create one with `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`
  in a trusted local shell and configure it in Render's Environment page;
  never paste or commit it into this repository.
- The browser sends the DeepSeek key only through the authenticated HTTPS
  API proxy to FastAPI. The backend encrypts it with Fernet and stores
  the ciphertext in the `model_credentials` PostgreSQL table. Do not
  overwrite or rotate the vault key without migrating stored ciphertext.
- Only the admin role can set, replace, remove the key or toggle daily use.
  Admins can remove keys to disable daily work. Neither retrieval responses
  nor audit logs include the key or ciphertext.
- `deepseek-flash` is used for paper reading; `deepseek-v4-pro` for planning,
  generation and criticism. Admins can choose `deepseek-flash` for all stages
  when they want a cheaper initial trial.

## Actual pipeline

1. Human-review candidate papers (relevant/method) in `科研关联与文献发现`.
2. Choose one existing team research line in `AI 选题实验台`.
3. Click `深度发现选题` to create a persisted run; the initial status is `queued`.
4. Four DeepSeek JSON stages run in a bounded background task:
   `planner` (bottleneck/data assumptions), `reader` (up to 5 abstracts),
   `generator` (1-3 evidence-linked research proposals), and `critic`
   (limitations, novel-work caveat and revised experiment).
5. Each validated stage is persisted in `ai_analysis_runs`; reusable paper
   analyses are cached in `paper_understandings` (metadata/abstract only).
6. When finished, `ai_opportunities` stores independent *drafts*, separate
   from the old template-driven `ideas` table. Researchers can shortlist
   or reject a draft. AI generated outputs are NOT auto-approved.

### Evidence and privacy enforcement

- Only human-reviewed `paper_discovery_candidates` are eligible.
- Data context contains names, formats, time/space coverage and abbreviated
  descriptions from `cusp_datasets`, not actual SHP/CSV files.
- Datasets marked `restricted` are excluded. Custodians, F-drive paths,
  backup locations and data-source contacts are never sent to models.
- Citation IDs are programmatically checked against the selected paper list,
  and dataset IDs against the non-restricted inventory. Invented IDs fail
  validation. Missing experimental baselines also fail.
- The Critic cannot certify originality: no comprehensive prior-art search
  is done in P2. Output always marks novelty as **not verified**.
- Model prompts explicitly mark scholarly abstracts as untrusted source text.

### Reliability and billing boundaries

- No paid DeepSeek request can run without a saved credential **and** a
  manual researcher click or administrator opt-in to daily analysis.
- New installations start with daily analysis OFF. The existing single Vercel
  daily cron optionally launches at most one P2 run per day, after existing
  research refresh and OpenAlex discovery background tasks.
- OpenAlex retrieval still requires its *own* key and is separate from DeepSeek.
- Backend tasks are checkpointed in Postgres, and a failed stage can be resumed
  by pressing the resume button without rerunning successful prior stages.
- The free Render instance can sleep/restart; a stale running task can be
  manually resumed after 8 minutes. This is not yet durable queue processing.
- Token counts are recorded, but no currency charge is estimated because
  model prices can change; check your DeepSeek platform billing dashboard.
- No live paid-model calls are performed as part of tests or deployment.

## Production validation checklist

- After deployment: database migrations/create_all successfully register
  `model_credentials`, `ai_analysis_runs`, `paper_understandings`,
  `ai_opportunities`.
- Log in as admin and verify `DeepSeek Key 已加密保存` status after saving.
- Log in as a researcher and verify no write access to model settings.
- Keep daily toggle OFF initially. Review one P1 paper and run one
  manual experiment with `deepseek-flash` to test JSON formatting.
- Inspect citations, data attributes, baselines, Critic caveats and token usage.
- Only enable daily analysis after validating results, budget and privacy.
- Plan PostgreSQL migration/backups before the Render Free DB expiration.
