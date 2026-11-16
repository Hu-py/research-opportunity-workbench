# Research Atlas · ChatGPT Owner SC05 MCP Bridge

**Status as of 2026-11-16:** The bridge and A/B orchestration are implemented in the SC05 staging code line. The repository's isolated Render service has automatic deployment disabled, so a GitHub commit alone does not deploy the new tools. ChatGPT tool discovery and a real paid A/B run remain separate acceptance steps. See the [SC05 ChatGPT operating guide](SC05_CHATGPT_OPERATING_GUIDE.md).

## Purpose

Allow ChatGPT to manage an Owner's complete SC05 experiment workflow without copying Owner credentials into the conversation or requiring a local terminal for normal operations.

The bridge can create private paper cases from extracted text, create and preflight A/B pairs, start the next safe arm, inspect status, return blind reports, save blind scores, unblind and compare, and maintain a durable experiment-round ledger.

It does not silently start paid models, automatically retry an ambiguous provider request, or declare scientific success based on a completed API run.

## Endpoints and OAuth

- MCP resource: `/mcp`
- Resource metadata: `/.well-known/oauth-protected-resource`
- Authorization server metadata: `/.well-known/oauth-authorization-server`
- Owner authorization: `/oauth/authorize`
- Token exchange / refresh: `/oauth/token`
- Token revocation: `/oauth/revoke`
- Owner delegation management: `/api/mcp/delegations`

The implementation uses the exact ChatGPT client identity and redirect URI, OAuth Authorization Code + PKCE S256, a fixed HTTPS resource origin, hashed access/refresh tokens in PostgreSQL, one-hour access tokens and rotating refresh tokens. The Owner signs in on the Research Atlas backend authorization page; ChatGPT never receives the Owner password or DeepSeek credential.

Every MCP request validates token expiry, audience, scopes, active Owner status and ownership of the requested paper/run/pair.

## Current tool registry

| Tool | Scope | Side effect |
|---|---|---|
| `list_experiments` | `experiments:read` | Read Owner cases, pairs, rounds and budget; blind run IDs/variants remain hidden until unblinding |
| `prepare_experiment` | `experiments:read` | Read-only single-run checkpoint/budget preflight |
| `get_executor_status` | `experiments:read` | Read worker probe and queue readiness |
| `get_experiment_status` | `experiments:read` | Read-only single-run status |
| `get_experiment_result` | `experiments:read` | Read completed report and quality metadata |
| `prepare_ab_pair` | `experiments:read` | Read-only pair-level preflight |
| `get_ab_pair_result` | `experiments:read` | Read anonymized A/B reports |
| `list_experiment_rounds` | `experiments:read` | Read persistent experiment-round ledger |
| `create_paper_case` | `experiments:read experiments:run` | Save a private extracted-paper snapshot; zero model calls |
| `create_ab_pair` | `experiments:read experiments:run` | Create the two prepared run records; zero model calls |
| `get_ab_pair_status` | `experiments:read experiments:run` | Read pair status and synchronize the round ledger |
| `start_ab_pair` | `experiments:read experiments:run` | Enqueue only the next safe arm; may make paid model calls |
| `start_experiment` | `experiments:read experiments:run` | Compatibility single-run start/resume; may make paid model calls |
| `record_blind_review` | `experiments:read experiments:run` | Save a score for anonymous A or B |
| `compare_ab_pair` | `experiments:read experiments:run` | Write an audit record and reveal the mapping after both blind scores exist |
| `record_experiment_round` | `experiments:read experiments:run` | Create/update the durable round ledger |

All mutating tools publish write annotations and require the run scope. `get_ab_pair_status` is treated as a write because it synchronizes the persistent round ledger. `compare_ab_pair` is an explicit unblinding action and cannot be repeated after a pair has been unblinded.

## Scientific workflow rules

1. Create or select one Owner paper case.
2. Create a clean A/B pair using the same source snapshot.
3. Preflight the pair and verify source/pipeline hashes.
4. Start gate-off baseline first.
5. Freeze the shared evidence snapshot.
6. Start gate-on only after baseline completion.
7. Retrieve anonymized reports and save both blind reviews.
8. Unblind only after both reviews exist.
9. Persist comparison and next-step notes in the round ledger.

The baseline and gate-on arms must not run concurrently. A pipeline hash mismatch requires a new clean pair or a separately validated recovery; the MCP bridge must not silently rewrite old checkpoints.

## Paper intake limits

`create_paper_case` accepts extracted page text from ChatGPT and is limited to a 48,000-byte UTF-8 JSON payload per MCP request. It uses the same page validation and blind-eligibility filtering as the authenticated PDF endpoint. Larger PDFs should be uploaded through the authenticated Research Atlas PDF page. Original PDFs and private source pages must not be committed to GitHub.

## Paid execution and worker readiness

A paid start requires all of the following:

- OAuth grant includes `experiments:run`.
- The user explicitly authorizes actual DeepSeek model spending in the current conversation and the tool receives `confirm_paid=true`.
- Server-side `SC05_MCP_PAID_ENABLED=true`.
- Worker readiness checks pass (unless an Owner has explicitly disabled the readiness guard for a controlled test).
- Daily call/token budget is available.
- The target run passes the source, checkpoint and frozen-evidence preflight.

The isolated Render workspace has no separately confirmed independent SC05 Background Worker resource. Render logs on 2026-11-16 show the inline worker started with `live_deepseek_enabled=True`, so the currently deployed service is technically capable of paid DeepSeek execution. This is not user consent. The optional inline worker on a free Web Service may sleep or restart. Do not enable paid starts merely because the MCP endpoint is reachable. Interrupted `claimed` / `running` requests remain frozen for review; they are not automatically stolen or replayed because a provider may already have billed them.

R2 archiving is optional. PostgreSQL remains authoritative. R2 failure must never trigger a second paid model request.

## Staging release checklist

1. Confirm the Render workspace, exact isolated service and isolated PostgreSQL schema.
2. Merge the reviewed PR into the branch bound to the isolated service.
3. Trigger a manual Render deploy because `autoDeploy=no`.
4. Verify the live deploy commit equals the intended GitHub commit.
5. Verify `/api/health`, OAuth discovery endpoints, and the unauthenticated MCP challenge.
6. Connect ChatGPT using the exact `/mcp` URL and Owner authorization. Grant both `experiments:read` and `experiments:run`.
7. Verify `tools/list` includes the current tool registry and run read-only / zero-cost operations first.
8. Verify the synthetic PostgreSQL worker probe before considering paid execution.
9. Only after the actual queue consumer is ready, separately authorize a bounded real DeepSeek test.
10. Review the saved source SHA, pipeline SHA, checkpoints, token usage, A/B blind scores, unblinded comparison and round ledger.

## Owner revocation

- `GET /api/mcp/delegations` lists grant fingerprints, scopes and expiry; it does not expose raw tokens.
- `POST /api/mcp/delegations/{grant_id}/revoke` revokes one Owner grant.
- `POST /oauth/revoke` supports OAuth-client token revocation.
- Disabling the MCP feature flag or deactivating/changing the Owner role also blocks access.

## Security limitations

This is a staging integration, not an externally audited OAuth provider. Before public production use, complete rate-limit/WAF protection for Owner login, CSRF and OAuth threat review, schema migration/backup validation, worker lease/heartbeat design, exact cost controls, and a formal incident/revocation procedure. Never put Owner passwords, provider keys, database URLs, bearer tokens or R2 credentials in ChatGPT, source code, GitHub Actions logs or public frontend variables.
