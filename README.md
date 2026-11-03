# Research Atlas — 自动化科研选题工作台

A research intelligence workbench that continuously links **urban research questions**, **computer-science methods**, **scholarly evidence** and **versioned research opportunities**.

## What is implemented (v0.2)

- **Next.js 16 frontend** (\`frontend/\`): Chinese research dashboard, paper library, rolling ideas, profile editor, agent console, execution traces, evolution history and weekly brief.
- **FastAPI backend** (\`backend/api.py\`): profile, paper, ideas, feedback and durable task endpoints.
- **Research Agent** (\`backend/agent.py\`): bounded tool calls to OpenAlex, local paper library, research profile and existing ideas. Can run with OpenAI Responses API. With no API key, deliberately offers a **bibliographic preview only**.
- **Research Skills** (\`skills/\`): evidence-based paper reading, method transfer and idea criticism, loaded into model instructions.
- **Task worker** (\`backend/worker.py\`): database-backed tasks with progress steps, separate worker for cloud deployments.
- **Existing Python core** (\`research_workbench/\`): OpenAlex ingestion, DOI normalization, rolling ideas, versioned feedback, weekly Markdown and opt-in weekly schedule.
- **CI**: backend unit/integration tests, Streamlit legacy smoke test, TypeScript checks and Next.js build.

**Important:** This codebase is a tested development MVP, not an already-deployed website or verified multi-agent research service. Academic novelty must be evaluated by reading primary sources.

## Start the full stack locally

Requires Python 3.10+ and Node.js 22.

**Terminal 1 — FastAPI:**

\`\`\`bash
git clone https://github.com/Hu-py/research-opportunity-workbench.git
cd research-opportunity-workbench
# checkout feat/nextjs-fastapi-agent until PR is merged
git switch feat/nextjs-fastapi-agent
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
