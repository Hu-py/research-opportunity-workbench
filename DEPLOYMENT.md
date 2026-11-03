# Cloud deployment — Next.js + FastAPI + PostgreSQL

The new frontend is in \`frontend/\`. The old Streamlit deployment guide has been superseded.

## Prerequisites

- GitHub repository at \`Hu-py/research-opportunity-workbench\`, new branch \`feat/nextjs-fastapi-agent\`.
- A private PostgreSQL database with backups (e.g. managed Postgres/Supabase).
- A cloud service able to run a continuously available Python API **and** a separate background worker (e.g. Render/Railway).
- Vercel/another Node-compatible host for the Next.js frontend.
- Your own long random strings for \`APP_PASSWORD\`, \`SESSION_SECRET\` (32+ chars) and \`API_BEARER_TOKEN\`; do not paste real values into Git.

## A. Provision private database

Create a dedicated database and least-privilege user. Prefer TLS and backups. Both FastAPI and Worker must use the **same** \`DATABASE_URL\` (SQLAlchemy form \`postgresql+psycopg://...\`). Existing SQLAlchemy tables are created at startup; production schema migrations have not yet been added.

## B. Deploy FastAPI service

Build from repository root with \`Dockerfile.api\`, port \`8000\`.

Set server-only environment variables:

\`\`\`text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:PASS@DBHOST:5432/DB?sslmode=require
API_BEARER_TOKEN=<a-long-independent-random-token>
OPENAI_API_KEY=<optional-model-secret>
OPENAI_MODEL=gpt-4.1-mini
OPENALEX_API_KEY=<optional-OpenAlex-key>
WORKER_MODE=queue
\`\`\`

Leave \`OPENAI_API_KEY\` empty if you want the paper-only prototype first. \`GET /api/health\` is publicly accessible, while research APIs require \`Authorization: Bearer …\` when configured.

**Never** set \`APP_ENV=development\` or leave \`API_BEARER_TOKEN\` blank on a publicly accessible API.

## C. Deploy the independent Worker

Build from repository root with \`Dockerfile.worker\`. Same \`DATABASE_URL\` as API, plus optional \`OPENAI_API_KEY\`, \`OPENAI_MODEL\`, \`OPENALEX_API_KEY\`. The worker polls durable queued tasks. Frontend displays task status until completion.

Do not assume Vercel serverless functions can host long-running Python agents. They only handle the Next.js UI and proxy.

## D. Deploy Next.js to Vercel

1. Import the same GitHub repository on https://vercel.com/new.
2. Set **Root Directory** to \`frontend\`.
3. Set Branch to \`feat/nextjs-fastapi-agent\` for a preview deployment, then use \`main\` after merging.
4. Set server-side environment variables in Vercel project settings:

\`\`\`text
BACKEND_URL=https://your-api-service.example
API_BEARER_TOKEN=<same-token-as-backend>
APP_PASSWORD=<long-private-login-password>
SESSION_SECRET=<random-string-with-at-least-32-characters>
\`\`\`

All four are server-side and must **not** be prefixed \`NEXT_PUBLIC_\`. Frontend calls \`/api/proxy/...\`; the Next.js server adds the backend bearer credential. Browser JavaScript never receives this secret. Cookies are signed, HttpOnly, SameSite=Strict, and Secure in production.

The authentication method is **single-user prototype password auth** without built-in account management or rate limiting. Enable hosting firewall/rate limiting and upgrade to proper managed auth before team/public access.

5. Deploy. Only the hosting platform can provide a live URL after successful build and runtime configuration.

## E. Scheduled weekly updates

The existing GitHub Actions workflow \`.github/workflows/weekly.yml\` is **opt-in** and must point to the *same* PostgreSQL \`DATABASE_URL\`. To enable it, set Actions variable \`ENABLE_WEEKLY=true\` and configure optional SMTP secrets (see \`.env.example\`). GitHub Actions runners are ephemeral; **never use SQLite on them to store cumulative research history**.

## Data protection and limitations

- The GitHub repository is currently public: keep personal research data and all secrets out of commits.
- Set cloud platform access controls, database backups and network restrictions before importing unpublished work.
- No multi-user isolation, abuse rate limiting, durable retries for crashed jobs, or migration framework yet.
- Agent citations are drawn from retrieved source records, but AI analysis still needs human verification.

## Local development

Start FastAPI from repository root:
\`\`\`bash
pip install -e '.[test,ai]'
uvicorn backend.api:app --reload --port 8000
\`\`\`

Start Next.js in \`frontend/\`:
\`\`\`bash
npm install
echo 'BACKEND_URL=http://127.0.0.1:8000' > .env.local
npm run dev
\`\`\`

In development, jobs are executed through FastAPI BackgroundTasks by default. In production, use the independent worker.
