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
