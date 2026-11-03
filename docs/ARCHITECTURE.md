# Research Atlas architecture (v0.2)

```
[Next.js 16 browser UI]
  |
  | HTTPS, signed HttpOnly session cookie
  v
[Next.js same-origin /api/proxy] -- Bearer API_BEARER_TOKEN (server only) -->
  |
  v
[FastAPI API, authenticated] ---> [PostgreSQL / SQLite]
                                     |
                                     v
                              [persistent tasks]
                                     |
                                [worker process]
                                     |
                  +------------------+-----------------+
                  |                  |                 |
         [Research Agent]    [OpenAlex API]      [Existing ideas]
                  |
      [read-only tools and Skills]
                  |
       [OpenAI Responses API]
                  |
        [answer and raw sources]
```

## Separation of concerns

- `frontend/`: Next.js 16 + React TypeScript user interface. No provider keys or database connection in browser.
- `backend/api.py`: authentication, CRUD endpoints and durable task enqueue.
- `backend/tasks.py`: SQLAlchemy task record, statuses, steps and result JSON.
- `backend/worker.py`: independent worker with atomic task claiming; local development may instead use FastAPI BackgroundTasks.
- `backend/agent.py`: whitelisted search tools, bounded model turns, source preservation and explicit no-key fallback.
- `skills/`: version-controlled instructions loaded into the Agent prompt, not executable arbitrary code.
- `research_workbench/core.py`: inherited paper and versioned-idea persistence, unchanged across Streamlit and Next.js.

## API endpoints

| Method | Path | What it does |
|--------|------|--------------|
| GET | `/api/health` | Public service health |
| GET | `/api/overview` | Counts and latest research ideas |
| GET | `/api/papers` | List/search stored papers |
| GET | `/api/ideas` | List rolling ideas and paper evidence |
| GET | `/api/ideas/{id}/history` | Evidence/feedback version history |
| POST | `/api/ideas/{id}/feedback` | Researcher changes idea state |
| GET, PUT | `/api/profile` | Manage research profile in private DB |
| POST | `/api/tasks` | Enqueue explore, sync or weekly task |
| GET | `/api/tasks` | Most recent task logs and results |
| GET | `/api/tasks/{id}` | Poll task status and steps |
| GET | `/api/brief` | Current Markdown brief |

All endpoints except health require backend Bearer authentication when `API_BEARER_TOKEN` is set. Production refuses to start without it.

## Models / Agent

When `OPENAI_API_KEY` is present, the Agent calls OpenAI Responses function tools. Tool calls are whitelisted: local paper search, OpenAlex live paper search, profile, and existing ideas. The skill loader attaches `paper_reader`, `method_transfer`, and `idea_critic` instructions. Each run is capped at four model rounds and nine tool calls. Sources are collected from actual returned records; model claims still require academic review. No model-generated conclusion is automatically committed to the versioned idea pool.

Without the model key, exploration produces an explicitly marked **bibliographic preview**, never a fabricated “AI-generated opportunity”.

## Limitations and follow-up

This is a **single-user experimental system**. Server-side session login is password-based and has no built-in rate limiting or organization-level permissions. Use a reverse proxy/WAF and stronger authentication before public/team deployment. SQLite is for local use; long-term production requires PostgreSQL, backups, access controls and explicit migration procedures.

The worker is separate from FastAPI to keep long-running jobs out of HTTP requests. Jobs are durable while queued, but automatic recovery of a worker that crashes mid-task, concurrent quotas, cancel/resume, metering and retry/backoff are **not yet implemented**. Add heartbeat/retry/dead-letter management before high-reliability scheduling.

Research recommendations are hypothesis-generation aids, not validated novelty conclusions or legal/academic guarantees.
