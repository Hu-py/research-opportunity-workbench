# SC04 | Personal Child-Health Research Evolution V0.1

## Goal and distinct workflows
Current focus: improve an existing research project, rather than build a weekly paper digest. The two future modes share paper understanding and evidence protocol, not the same user prompt or output.

## Current source of truth
- Personal baseline: researcher-reviewed draft of Songjiang child-health external spatial extrapolation, XGBoost, mean-neighborhood baseline, GraphSAGE, target label sparsity and AOA. The draft is **not** verified data until the member saves and confirms it.
- Academic evidence: last completed or partial strict scan in the authenticated user's child-health task journal directory; source-ID snapshot is frozen. At least 3 suitable OpenAlex abstracts across 2 probes, max 5 papers.
- No automatic full-text claims, no fabricated R2 estimates, no invented data assets, no novel-method claim.

## Five steps
1. User edits and confirms research baseline in /research/personal/evolution. Every revision is stored per member_id. Earlier runs remain immutable.
2. User prepares a run: copy approved-source paper abstracts, URL, scan ID, baseline and source filters into a hashed SQL snapshot; no model request.
3. With encrypted DeepSeek credential and explicit consent, the user starts the three-stage runner. Its stage checkpoints are reader -> transfer (2-4 method matches + 1-3 variants) -> critic. Each call first reserves research budget and stores token usage.
4. The strict reader requires a literal excerpt that exists in the corresponding abstract. Transfers and variants must cite exact supplied paper IDs. Independent critic can hold or reject all variants; prior-art coverage is explicitly incomplete.
5. User submits per-run 1-5 quality ratings, which are appended to personal research history. Does not automatically change team profile, global journal whitelist, prompts or the old team evolution engine.

## Safety
- No private child-level health records leave the platform. Only reviewed study design and public abstracts are sent on explicit request.
- Without verified personal baseline, strict approved-source evidence, a model key or consent, no paid run occurs.
- The project remains isolated in Booooom Render E2E and Vercel Preview, never main/production.
- API uses the session's real TeamMember ID for every baseline, run and evaluation.

## Code and API
- Skill: skills/research_evolution/SKILL.md
- Backend persistence: backend/sc04_evolution.py; runner: backend/sc04_evolution_runner.py; shared model gateway: backend/model_gateway.py.
- Frontend: frontend/app/research/personal/evolution.
- Routes: GET/PUT /api/personal-research/me/evolution[/baseline]; POST /prepare; GET /runs/{id}; POST /runs/{id}/start, /resume, /review.

## Acceptance
- Python integration tests use mocked model responses and real SQLite session auth. Explicitly test no-key / no-consent, fake paper IDs or fake literal excerpts, source lineage, saved checkpoints, and user isolation.
- Frontend compiled with Next.js, linked from the child health personal study. Actual model execution remains gated by currently configured DeepSeek vault; CI tests do not imply the paid model really ran.


## SC04-only API Key configuration (isolated Render)

The first live experiment may use **one server-side environment secret** on the existing isolated Render web service; no GitHub Secret or frontend Vercel variable is required.

1. Open Render Dashboard -> isolated service `research-atlas-devstudio-e2e` -> Environment.
2. Add environment variable **`SC04_DEEPSEEK_API_KEY`** containing the actual DeepSeek API credential, not an OpenAlex token and not a GitHub token. Mark it secret if the hosting UI permits. Do not paste the key into chat, a GitHub issue, PR, markdown, frontend source, or `NEXT_PUBLIC_*` variables.
3. Let the Render service redeploy and check `GET /api/personal-research/me/evolution` while authenticated. Expected model response: `configured=true`, `vault_ready=true`, `key_storage=render-environment-sc04-only`, `daily_enabled=false`. The response does **not** include the key.
4. SC04 still requires a researcher-confirmed baseline, ≥3 abstracts from an approved-source scan spanning ≥2 A/B/C probes, and an explicit opt-in per run before any provider call. No scheduled job uses this scoped variable.
5. To revoke, delete `SC04_DEEPSEEK_API_KEY` on Render and redeploy. Other platform features remain unchanged. To transition to the original encrypted database vault later, the administrator can configure `MODEL_VAULT_KEY` and use `PUT /api/ai-lab/config`.

The fallback intentionally uses the already whitelisted `deepseek-flash` model in all three SC04 stages for a bounded first real run. The backend's existing model gateway validates provider responses and records token use; costs depend on provider billing. This key is scoped to the isolated TEST service only.
