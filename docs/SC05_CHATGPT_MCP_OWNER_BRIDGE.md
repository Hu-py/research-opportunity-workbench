# Research Atlas · ChatGPT Owner delegated SC05 tools

Status: **staging feature**. This is not a deployed/installed ChatGPT plugin, and it does not automatically cause paid DeepSeek calls. The current code is deliberately disabled until the isolated deployment is verified.

## Goals and boundaries

The ChatGPT assistant may prepare, enqueue and inspect **existing** SC05 Owner experiments, and store references in Development Studio. It may never impersonate a browser session, choose a new paper from a public repository, silently restart failed stages, or auto-approve its own scientific output.

The bridge is part of the existing FastAPI backend, at `https://<isolated-render-host>/mcp`. It is a minimal **stateless Streamable HTTP JSON-RPC** implementation with OAuth authorization code + PKCE S256, exact ChatGPT client identity and fixed redirect. Test protocol compatibility with ChatGPT itself before production release; no MCP SDK is used in this prototype.

Authorization endpoint is `/oauth/authorize`. On first authorization the Owner enters their Research Atlas email and password **on the Research Atlas backend page**, not in ChatGPT. Access tokens expire in 60 minutes; refresh tokens in 30 days. Token hashes are stored in PostgreSQL, rotated on refresh, and Owner revocation is available at the authenticated `/api/mcp/delegations` management endpoints. Disabling Owner status immediately removes access.

MCP operations:

| Tool | Scope | Side effect |
|---|---|---|
| `list_experiments` | `experiments:read` | None |
| `prepare_experiment` | `experiments:read` | None |
| `get_experiment_status` | `experiments:read` | Writes an idempotent Development Studio SC05 link/status |
| `get_experiment_result` | `experiments:read` | None |
| `start_experiment` | `experiments:read experiments:run` | Can enqueue **one prepared Owner run**; requires `confirm_paid=true` + positive paid flag |

All tools verify access token expiry, scopes, audience, active Owner membership and exact run ownership. A foreign run ID is always 404. `start_experiment` reuses the existing SC05 Owner route for all previous guards and source-hash protections, rather than duplicating LLM or billing logic. Global model-call/token ceilings remain enforced by `backend/research_budget.py`. This is **not** an exact USD billing limiter.

## Safe staging release procedure

1. Confirm intended Render workspace, exact isolated SC05 service and PostgreSQL schema, and complete a DB backup. Do not modify production, databases, secrets or OAuth settings in other projects.
2. Merge the tested PR into `experiment/devstudio-postgres-e2e-20261114` only. Render's isolated service `research-atlas-devstudio-e2e-ejmh` uses this branch, and auto-deploy is OFF. Trigger the explicit deploy after merge.
3. Configure these server-only env vars on that isolated service:

   - `SC05_MCP_ENABLED=true`
   - `SC05_MCP_PUBLIC_URL=https://research-atlas-devstudio-e2e-ejmh.onrender.com`
   - `SC05_MCP_PAID_ENABLED=false` (leave false until the executor is operating)
   - existing `API_BEARER_TOKEN`, `DATABASE_URL` and `TEAM_AUTH_ENABLED=true` must remain unchanged.

4. Check `GET /.well-known/oauth-protected-resource`, `GET /.well-known/oauth-authorization-server`, `GET /mcp` with no auth (expected 401 challenge), `GET /api/health`. Perform a single Owner OAuth connection in ChatGPT, followed by `tools/list` and `list_experiments`.
5. In ChatGPT web, Plugins → Add custom MCP server. Use `https://research-atlas-devstudio-e2e-ejmh.onrender.com/mcp`, OAuth authentication, then install the plugin. The Owner must perform this connection step personally; ChatGPT cannot grant its own access or directly install a custom MCP plugin. In the conversation, select the new plugin explicitly.
6. Verify a **read-only** SC05 inspection and existing A results. Do not initiate a new paid run to test discovery. Confirm DevStudio's linked experiment entry and record read-only status.
7. Only when an actual durable task consumer is working (or after consciously accepting the free Render background-worker interruption risk), decide how to enable paid starts. In normal operations, **do not enable** the paid switch if `SC05_EXECUTION_MODE=worker` has no independent running worker; a job would only stay queued. A Render Background Worker costs money; GitHub Actions needs a separately provisioned, protected cloud-running authentication mechanism.
8. Keep the SC05 B failed run frozen until the existing `Missing/invalid search query` model-response issue is repaired through an auditable stage-specific recovery. Paid retries must not discard the original four checkpoints.

## Owner revocation

Send requests via the existing authenticated Research Atlas backend proxy:

- `GET /api/mcp/delegations` lists grant fingerprints, scopes and expiry (no raw tokens).
- `POST /api/mcp/delegations/{grant_id}/revoke` revokes a selected link.
- OAuth clients may call `POST /oauth/revoke` with their own refresh/access token.

Owner inactivity, role change and expiry also make the link unusable. To disable the integration immediately, set `SC05_MCP_ENABLED=false` on the isolated service.

## Security requirements before production

This is a staging prototype, not an externally audited OAuth server. Require remote protocol compatibility tests, secure cookie/CSRF review, rate-limit/WAF for login and OAuth, OAuth client metadata verification or trusted IdP, safe database migrations, token revocation audit, budget policy review, and a hardened execution queue before public release. The existing Owner email and provider keys must not be embedded in ChatGPT or source code.

### Tests

`pytest -q tests/test_sc05_agent_bridge.py tests/test_sc05_eval_api.py`

CI tests must not make real model calls. Successful CI establishes only software function and security checks, not new-paper scientific merit.


## 2026-11-16: Owner-delegated run scope and zero-fixed-cost executor

This deployment deliberately reuses the **existing isolated Render web service**, not a new paid Render Background Worker. `experiments:run` is not enabled for an existing read-only token automatically.

**OAuth / ChatGPT scope upgrade**

The first unauthenticated MCP 401 advertises `scope="experiments:read experiments:run"` when `SC05_MCP_RUN_SCOPE_ENABLED=true`. Per-tool OAuth `securitySchemes` declare read-only scopes for inspection and both scopes for `start_experiment`. If an old read-only grant invokes `start_experiment`, the MCP result advertises an `insufficient_scope` reauthorization challenge. The Owner must re-consent. Both OAuth scope and paid-model consent are checked server-side.

**Isolated Render rollout (stage 1; no model calls)**

```env
SC05_MCP_RUN_SCOPE_ENABLED=true
SC05_INLINE_WORKER_ENABLED=true
SC05_WORKER_SMOKE_ON_STARTUP=true
SC05_WORKER_SMOKE_ID=sc05probe_isolated_staging_20261116
SC05_EXECUTION_MODE=worker
SC05_INLINE_WORKER_LIVE_ENABLED=false
SC05_MCP_PAID_ENABLED=false
SC05_MCP_ENFORCE_WORKER_READINESS=true
```

At startup a synthetic probe is inserted at most once in `sc05_worker_probes`, committed, claimed by the actual Render worker loop, and marked completed. A `SC05 WORKER PROBE: completed` log line and a `get_executor_status` response with status `completed` confirm the PostgreSQL writer/reader cycle **without** DeepSeek or R2. If it fails, do not enable paid work.

**Isolated Render rollout (stage 2; availability only, not a paid test)**

After verifying the zero-cost probe and confirming no unexpected in-flight SC05 rows:

```env
SC05_INLINE_WORKER_LIVE_ENABLED=true
SC05_MCP_PAID_ENABLED=true
```

All other variables above stay unchanged. The worker only consumes rows in `sc05_delegated_worker_authorizations` marked `approved` following a new ChatGPT OAuth Owner tool invocation with `confirm_paid=true`; historical `queued`, `claimed` and `failed` SC05 runs cannot be silently restarted. Each stage still reserves from the existing global daily call/token budget, checkpoints in PostgreSQL, and optionally mirrors to R2 if the bucket credentials and `SC05_R2_ARCHIVE_ENABLED=true` are actually configured.

**Important limitations**

- This is not a continuously available independent Worker: Render's free web process may suspend or restart. Paid runs in `claimed` or `running` states remain frozen for human inspection after crashes; they are not automatically replayed.
- Live DeepSeek execution is **not** proven by the synthetic zero-cost probe. Real provider and R2 integration require a separately authorized limited-cost test and successful immutable checkpoint/manifest audit.
- Postgres is the primary persistent record. The database snapshot/backup plan must be completed before its free-instance expiration.
- The Owner may need to disconnect/reconnect the custom ChatGPT MCP plugin to request the upgraded scopes, depending on the client.
