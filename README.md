# Research Atlas — 团队共享科研智能工作台

A research intelligence workbench that continuously links **urban research questions**, **computer-science methods**, **scholarly evidence** and **versioned research opportunities**.

## ChatGPT Business Workspace Agent

The primary user-facing research interface is being built as a **ChatGPT Business Workspace Agent**. It connects to the single OAuth-protected Render MCP endpoint, reads the shared Supabase research context, and can launch the existing multi-agent topic-discovery pipeline. Supabase remains the only durable research database; Render is the Python/MCP execution layer; Vercel remains an optional visualization frontend.

- Product requirements and target architecture: [Business Workspace Agent specification](docs/BUSINESS_WORKSPACE_AGENT_PRODUCT_SPEC.md)
- Agent instructions and setup: [Business Agent configuration](docs/BUSINESS_AGENT_CONFIGURATION.md)
- OAuth and permission gates: [Business MCP OAuth setup](docs/BUSINESS_MCP_OAUTH_SETUP.md)
- Versioned Agent Skill: [Research Advisor Skill](skills/business_research_advisor/SKILL.md)

The MCP server, execution permission and write permission remain disabled by default until the OAuth client, approved user identities and end-to-end tests are verified.

## Development studio & research interest watchlist

Development progress tracking now lives in the **standalone development console**
(`dev-tracker/`), deployed as a **separate Vercel project**. It tracks GitHub
Issues, Pull Requests, commits, and CI directly, refreshing every ten minutes
while visible. It does not require backend credentials or the research workspace
login. Each milestone's goals, implementation notes, acceptance conditions,
evidence and status are connected to a GitHub Issue. To update status, close a
tracked Issue or merge a PR with `Closes #NN`; CI and commit activity reflect
automatically. See [tracker guide](dev-tracker/README.md).

The business-facing **研究兴趣监测** tab remains inside the research workbench,
where it belongs. The engineering status board is no longer embedded in the
workbench UI.

Research interests are stored **independently** of the official team profile
and verified achievements. Editors can add/pause topics or test an OpenAlex
scan. The existing weekly CLI / GitHub Actions workflow now includes enabled
interests, grouped separately in Markdown reports. To actually schedule weekly
runs, the GitHub Action must be enabled and a persistent database configured.
See [development studio and acceptance checklist](docs/DEVELOPMENT_STUDIO.md).

## What is implemented (v0.3 team development)

- **Next.js 16 frontend** (\`frontend/\`): Chinese research dashboard, paper library, rolling ideas, profile editor, agent console, execution traces, evolution history and weekly brief.
- **FastAPI backend** (\`backend/api.py\`): profile, paper, ideas, feedback and durable task endpoints.
- **Research Agent** (\`backend/agent.py\`): bounded tool calls to OpenAlex, local paper library, research profile and existing ideas. Can run with OpenAI Responses API. With no API key, deliberately offers a **bibliographic preview only**.
- **Research Skills** (\`skills/\`): evidence-based paper reading, method transfer and idea criticism, loaded into model instructions.
- **Task worker** (\`backend/worker.py\`): database-backed tasks with progress steps, separate worker for cloud deployments.
- **Existing Python core** (\`research_workbench/\`): OpenAlex ingestion, DOI normalization, rolling ideas, versioned feedback, weekly Markdown and opt-in weekly schedule.
- **CI**: backend unit/integration tests, Streamlit legacy smoke test, TypeScript checks and Next.js build.

**Important:** This codebase is a tested development MVP, not an already-deployed website or verified multi-agent research service. Academic novelty must be evaluated by reading primary sources.

## Shared 10-member laboratory mode

**One research profile + one shared paper/idea corpus for the entire lab.** The team edition adds separate member accounts (admin, researcher and viewer), Argon2 password hashing, revocable sessions, role-checked APIs, profile revision history, member audit logs and team admin UI. Inactive members lose access immediately.

This feature is **opt-in** with \`TEAM_AUTH_ENABLED=true\` on both Vercel and FastAPI; the existing personal prototype remains the compatibility default until a database and first administrator are configured. Do **not** enable team mode on Vercel before the persistent PostgreSQL backend is ready.

Read [Team setup / migration / roles](docs/TEAM_SETUP.md) and use [Example team profile JSON](examples/team-profile.example.json). Existing papers/ideas and profile JSON are preserved; never commit actual confidential research data or passwords.

## Start the full stack locally

Requires Python 3.10+ and Node.js 22.

**Terminal 1 — FastAPI:**

\`\`\`bash
git clone https://github.com/Hu-py/research-opportunity-workbench.git
cd research-opportunity-workbench
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test,ai]'
uvicorn backend.api:app --reload --port 8000
\`\`\`

**Terminal 2 — Next.js:**

\`\`\`bash
cd research-opportunity-workbench/frontend
npm install
printf 'BACKEND_URL=http://127.0.0.1:8000\n' > .env.local
npm run dev
\`\`\`

Open **http://localhost:3000**. In local development, no login is required if \`APP_PASSWORD\` is unset, and backend auth is disabled if \`API_BEARER_TOKEN\` is unset. **Do not use this unsecured configuration on public networks.**

1. Go to **研究者画像** and save your own research lines. The built-in profile is illustrative only.
2. Go to **科研总览** and click **更新论文情报**.
3. Go to **Research Agent**, enter a research question, and inspect tool traces/results.
4. Provide \`OPENAI_API_KEY\` only in the backend environment to enable true model reasoning; without it, Agent exploration is deliberately labeled “无模型模式”.
5. Review evidence and update idea status, then check version history and the weekly brief.

The local database defaults to \`data/research.db\` (git-ignored); it persists between restarts. The legacy Streamlit prototype remains at \`app.py\` and is **not** the new frontend.

## Production / Cloud deployment

Refer to [DEPLOYMENT.md](DEPLOYMENT.md) for Vercel frontend, Docker-based FastAPI/Worker and private PostgreSQL configuration, security boundaries and secrets. The repository is public as of development; **never commit API keys, researcher CVs, unpublished manuscripts, participant data or private PDFs.**

## Architecture and tests

- [Architecture, API and data/agent boundaries](docs/ARCHITECTURE.md)
- \`python -m pytest -q\`
- \`cd frontend && npm run typecheck && npm run build\`
- API docs in local development: \`http://localhost:8000/docs\`

### Follow-up milestones

Full-text Zotero/RAG ingestion, Semantic Scholar and venue verification, method embeddings, true novelty search against prior art, profile document upload, per-task cost logging, job recovery and secure team accounts are **not yet implemented**.
