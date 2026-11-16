# SC05 · ChatGPT end-to-end acceptance

Last reviewed: 2026-11-16
Target: "Create, run, track and analyze a complete experiment entirely in ChatGPT."

## Acceptance definition

ChatGPT must be able to operate the complete Owner-authorized workflow without requiring the researcher to open Development Studio, run local scripts, or manually copy run IDs between tools. The user still explicitly authorizes paid DeepSeek calls; ChatGPT must not bypass that consent.

## Expected user journey

1. **Connect**: ChatGPT connects to the isolated Research Atlas MCP endpoint through Owner OAuth + PKCE. The grant includes `experiments:read` and `experiments:run`.
2. **Discover**: `list_experiments` retrieves the Owner's existing papers, runs, experiment-round ledger and budget.
3. **Create**: `create_ab_pair` creates a clean A/B pair (optionally cloning the exact paper snapshot while clearing the prior shared-evidence snapshot). This is a zero-model-call operation.
4. **Plan and preflight**: `prepare_ab_pair` checks source identity, pipeline hashes, baseline/gate status, frozen evidence, checkpoints, active runs and budget.
5. **Run baseline**: `start_ab_pair` starts only the gate-off baseline, after explicit paid consent. The cloud worker consumes the delegated queue record.
6. **Track**: `get_ab_pair_status` reads actual status, current stage, saved checkpoints, token use and the next safe action.
7. **Run gated arm**: after baseline completion and evidence freeze, call `start_ab_pair` again to start gate-on. Never start both arms concurrently.
8. **Analyze blindly**: `get_ab_pair_result` returns anonymized reports A/B. `record_blind_review` stores the scores without exposing the mapping.
9. **Compare**: `compare_ab_pair` reveals the mapping only after both blind reviews and returns score differences, quality warnings and token use.
10. **Record**: `record_experiment_round` / `list_experiment_rounds` persist the question, method, experiment content, category, status, brief result, next step and detailed run evidence in PostgreSQL.

## MCP tool inventory

| Tool | Type | Acceptance evidence |
|---|---|---|
| `list_experiments` | Read | Returns only the authenticated Owner's cases/runs/rounds/budget |
| `create_ab_pair` | Write, zero cost | Two prepared arms, same source, zero provider calls |
| `prepare_experiment` | Read | Per-arm source/checkpoint repair validation |
| `prepare_ab_pair` | Read | Pair-level consistency and next-action decision |
| `start_experiment` | Paid write | Starts one explicitly approved run |
| `start_ab_pair` | Paid write | Sequential, idempotent A/B orchestration |
| `get_ab_pair_status` | Read | Real status and next action |
| `get_ab_pair_result` | Read | Two completed reports with blinded labels |
| `record_blind_review` | Write | Immutable one-time score per anonymous arm |
| `compare_ab_pair` | Write/unblind | Requires both blind scores; returns paired comparison |
| `get_experiment_status` / `get_experiment_result` | Read | Detailed run state/report |
| `get_executor_status` | Read | Worker readiness, queue and probe state |
| `list_experiment_rounds` / `record_experiment_round` | Read/write | Durable experiment ledger |

## Current implementation status

| Layer | Status | Evidence / remaining work |
|---|---|---|
| SC05 Owner API | Implemented | Existing Owner routes and paper-only pipeline |
| OAuth + MCP gateway | Implemented in staging branch | ChatGPT must refresh/reconnect and show the current tool list |
| Pair-level workflow tools | Committed | New offline integration test added; full CI and deployed endpoint must pass |
| Durable experiment-round table | Committed | PostgreSQL table is created from registered SQLAlchemy metadata; verify on isolated schema |
| Isolated Render service | Existing, free plan, manual deploy | Latest deployment triggered for commit `262f3b053bb8a3910aed85bda1665073fcfad5f1`; confirm live/healthy |
| Worker queue | Partially implemented | Free Render web process can sleep/restart; probe is not proof of paid DeepSeek execution |
| R2 archive | Optional / unverified on this service | Verify secrets and private-bucket roundtrip separately; PostgreSQL remains source of truth |
| ChatGPT connector | Not yet accepted | Need actual OAuth connection, tool-list refresh and read-only call |
| Full paid A/B | Not yet accepted | Requires a limited-cost, explicit Owner-authorized real run through both arms |
| Blind evaluation and round record | Code committed | Verify on the actual ChatGPT MCP connection after both runs |

## Hard acceptance gates

### Gate A — software and security
- CI passes: Python compile, full pytest, frontend typecheck/build, tracker checks.
- MCP tool list exposes the complete inventory above.
- Read-only OAuth grant cannot create or run experiments.
- A non-Owner, inactive Owner or foreign run ID is rejected.
- Create-pair operation has zero provider calls and preserves source SHA.
- Pair runner cannot start gate-on before baseline and frozen evidence.
- Repeated start requests do not duplicate active/completed runs.
- Blind result retrieval does not reveal variant mapping; unblinding requires both scores.

### Gate B — cloud runtime
- Latest isolated Render deployment is `live` and `/api/health` is healthy.
- Worker probe completes in PostgreSQL with zero paid calls.
- Paid worker is genuinely consuming approved rows; a web-process probe alone does not establish this.
- Provider credentials, daily limits, checkpoint commits and ambiguous-run recovery are verified.
- R2 is only marked enabled after an actual private archive roundtrip.

### Gate C — ChatGPT
- Custom MCP connection completes Owner OAuth in ChatGPT.
- ChatGPT's current tool inventory includes pair creation, pair preflight, sequential start, pair status, blind results, blind review, comparison and round ledger.
- ChatGPT can create a clean pair and persist a round record.
- ChatGPT can run baseline, wait/poll, run gated arm and retrieve both reports without manual website interaction.
- ChatGPT can score anonymously, unblind only after both scores, and write the final result/next step to the ledger.

## Safety and cost

- A/B creation, preflight, status, result retrieval and ledger reads do not call the model.
- Every actual DeepSeek run is a paid external action and needs explicit user consent.
- Never infer success from a queued response; verify final database status and result.
- Never automatically retry a `claimed` or `running` request after a crash. Inspect its saved checkpoints and provider ambiguity first.
- Do not merge the staging branch to production until all three gates pass and a separate production release review is approved.

## Useful commands

```bash
python -m compileall -q backend research_workbench
python -m pytest -q tests/test_sc05_agent_bridge.py tests/test_sc05_eval_api.py tests/test_sc05_worker_delegated.py
python -m pytest -q
```

The complete ChatGPT workflow is accepted only when Gates A, B and C all pass. A green CI badge or a live Render deployment alone is insufficient.
