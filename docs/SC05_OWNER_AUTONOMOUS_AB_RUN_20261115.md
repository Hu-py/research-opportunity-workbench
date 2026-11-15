# SC05 Owner-delegated cloud A/B execution audit — 2026-11-15

## Scope and security
- Isolated Render free Web Service: `research-atlas-devstudio-e2e-ejmh`, service `srv-dbs1tg6i0phs73bt8c1g`
- Database: existing `research_atlas_test_db`, isolated schema `atlas_devstudio_e2e_20261114`
- Published source PDF SHA256: `f8138694727ee27d4e399533311364eb137250d66b62d4b0f16d47d4c781a181`
- Pair: `sc05pair_c6a7665198a643e885e5f4fd699d`
- A: `sc05run_1380a7cde2354fc387d87ded2444` (science_gate_off)
- B: `sc05run_527287b83f3846b4b234f6a9512a` (science_gate_on)
- User delegated this run. No GitHub Owner session, browser cookie, or login password was used. No new paid Render Worker was created.
- Operator controlled through Render environment only, exact pair/source/schema allowlist, one-shot audit record, server-side daily model-call and token budgets.
- **Current operator configuration is INSPECT only and paid approval is disabled.**

## Actual completed checks
1. Exact-response preflight for baseline A originally failing on quotation mismatch: 4 source-verified facts; 2 invalid quotes excluded; initial 1 paid call reused.
2. A progressed to 15 checkpoints and failed on `Invalid diagnosis classification` (8 items lacked confidence; 3 `issue_class=inference`). Missing confidence is now marked `not_assessed`, not invented.
3. Exact-input offline replay of all 15 saved A model calls succeeded (0 additional calls). Next stage was `evidence_questions`.
4. A resumed and **COMPLETED**: 18 checkpoints, final report and manifest stored privately in R2.
5. B failed after 2 checkpoints on `Invalid diagnosis classification`. Private R2 metadata showed labels `causal_inference`, `inference_boundary`, `method_dependence`, `confounding`. Alias mapping preserves original labels, with canonical class.
6. B's exact original 2 checkpoints were validated without a new provider call; next stage `scientific_value_triage` matched.
7. B resumed to **4 saved checkpoints**, then stopped on `Missing/invalid search query`. There is **no completed B report** and **no A/B scientific quality delta**.
8. B was not blindly retried; the paid operator was switched back to `inspect` and its paid approval disabled.

## Confirmed results
| Variant | Server status | Checkpoint count | R2 report |
|---|---|---:|---|
| A baseline | completed | 18 | yes |
| B science gate | failed, missing/invalid search query | 4 | no |

Counts refer to persisted checkpointed model calls in this pair, **not** an exact billing statement. R2 snapshots and PostgreSQL checkpoint records preserve all paid outputs. Blinded human grading cannot be performed until B finishes.

## Engineering evidence
- GitHub PR #92: cached PDF quote provenance repair and isolated one-shot operator
- GitHub PR #93: diagnosis confidence normalization and A prefix SHA replay
- GitHub PR #94: gated diagnosis taxonomies and B prefix SHA replay
- R2 inventory Actions: `43712002957` (A snapshot10), `43712070522` (A14), `43712335507` (A15), `43712885918` (A16), `43712975292` (A complete/B0), `43713137384` (B2)
- Render latest read-only diagnosis logs at 2026-11-15 12:24 UTC: A completed/18; B failed/4; error `Missing/invalid search query`.

## Next technical issue
The strict structured output contract is brittle across LLM stages. Before any more paid attempts, inspect cached B `evidence_questions` output offline, report which required fields are missing/invalid and use a **bounded, auditable schema repair** only for structurally recoverable fields. Do not invent queries or citations. If a query was not supplied, request a single constrained stage retry under an explicit budget and preserve the original response. Add provider JSON Schema / structured-output enforcement and stage-specific tests; require exact prompt/checkpoint compatibility for any code version migration. Keep A report frozen and do not start B from scratch.

## Data governance
Do not publish source pages, raw paid model responses, R2 credentials, user sessions or private reports in GitHub logs. A report is accessible through the authenticated SC05 Owner dashboard.
