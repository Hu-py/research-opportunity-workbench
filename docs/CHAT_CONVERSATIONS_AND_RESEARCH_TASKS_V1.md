# Research Atlas 对话与科研发现任务 V1

> Status: integrated feature branch for staging validation. Not production until the combined PR is reviewed, CI passes and backend/frontend E2E succeeds. Deployment must use a staging database first; do not point this branch at the production database.

## 1. Product behavior

### Private conversation
- Each private conversation has exactly one member: its creator.
- User and assistant messages are stored in Research Atlas PostgreSQL.
- Every private user message automatically triggers the configured chat model.
- Only the selected conversation's recent messages are sent to the model; other private conversations and team rooms are not included.
- The model provider can be OpenAI, a direct DeepSeek environment key, or the encrypted DeepSeek credential already stored in the model vault.

### Team conversation
- A team room is shared only with its ChatMember records.
- Creating a team room adds all currently active team members.
- Newly invited active members are added to existing team rooms; private rooms are never shared.
- Ordinary team messages are stored and do not call a model.
- A structured `@GPT` send or the explicit **AI 回复** action triggers a model call.
- Viewers can read conversations but cannot create rooms, send messages or trigger AI. Admins/researchers can write.

## 2. API

All chat endpoints require `TEAM_AUTH_ENABLED=true`, a valid team session and the normal API bearer check.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/chats?kind=private|team` | List only conversations the current member can access |
| POST | `/api/chats` | Create private or team room |
| GET | `/api/chats/{id}/messages?after_seq=0&limit=100` | Read ordered messages |
| POST | `/api/chats/{id}/messages` | Save a message; private auto-triggers AI, team only triggers when explicit |
| POST | `/api/chats/{id}/ai-replies` | Explicit team AI reply |
| POST | `/api/chats/{id}/members` | Admin adds an active member to a team room |

Messages use a client nonce and AI calls use an idempotency key. The conversation stores a monotonic sequence, a frozen input sequence for each model call, status, provider/model, token usage and sanitized failure. Concurrent AI calls in the same conversation are rejected rather than silently interleaved.

## 3. Research Opportunity task

The Research Desk exposes a dedicated Research Opportunity V1 task composer. It creates a durable `research_opportunity` task and selects one capability:

- `idea_review`: full paper-scale research discovery, cross-paper synthesis, method transfer and adversarial review;
- `paper_discovery`: discover and classify scholarly evidence;
- `evidence_review`: inspect source-supported claims and limitations;
- `method_transfer`: map computational capabilities to the target problem.

Every Research Opportunity task freezes the directed-research A/B/C source snapshot. It **fails closed** if the selected source list is empty, disabled or lacks a resolved OpenAlex source ID. It never silently falls back to unrestricted OpenAlex search. The runtime search tool accepts a lane (A/B/C/all), and the task snapshot provides distinct resolved source IDs per lane.

The full seed-paper PDF diagnostic remains a separate SC05 paper-only workflow. The Research Opportunity task uses the task question and registered scholarly sources; it must not claim to have extracted facts from a PDF unless a source PDF/evidence package was actually supplied to that workflow.

## 4. Model configuration

- Chat checks `OPENAI_API_KEY` first.
- If absent, chat checks `DEEPSEEK_API_KEY`, then the existing encrypted `ModelCredential` in the database.
- Research Opportunity Agent checks `OPENAI_API_KEY`, then direct `DEEPSEEK_API_KEY`, then the encrypted DeepSeek credential.
- DeepSeek credentials in the database require a stable server-side `MODEL_VAULT_KEY`; the API key itself is never returned to the browser or logged.
- The private chat UI informs the user that private messages are sent to the configured model provider. Private means isolated within Research Atlas access control, not that content is withheld from the provider.

## 5. Deployment requirements

Backend environment:
- `TEAM_AUTH_ENABLED=true`
- `RESEARCH_OPPORTUNITY_SKILL_ENABLED=true`
- existing `API_BEARER_TOKEN`
- existing `DATABASE_URL` (PostgreSQL recommended)
- one supported model credential path described above
- existing OpenAlex credentials and a populated/verified Academic Source Registry

Frontend environment:
- existing server-side backend URL and bearer token configuration;
- the same team session cookie flow as the current Research Atlas V1 UI.

## 6. Known limitations before production

- Model responses are synchronous with a 45-second provider timeout; this first release does not implement token streaming or durable background AI-call recovery.
- The UI refreshes conversation messages periodically; real-time WebSocket delivery is not included.
- Chat messages are retained in the database and follow the existing database backup/retention policy. Per-conversation deletion/export controls are not yet included.
- The model provider receives the messages in the selected conversation when AI is triggered.
- The team room member set is explicit. New members are auto-added to team rooms at invitation time; membership changes should remain auditable.
- Research Opportunity uses the current read-only ResearchAgent tool set. It does not run empirical experiments or access raw team datasets.
- CI and staging E2E are mandatory before production. Do not merge or deploy a preview to production if migrations, ACL tests, source-scope checks or model configuration fail.
