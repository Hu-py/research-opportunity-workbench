# SC05-R1 · Authenticated Real-Agent A/B Evaluation Runbook

**Objective:** Test whether the *Research Atlas agent*, not the human assistant, can autonomously reconstruct, criticize and extend a published study into a genuinely independent scientific question. Compare the current SC05 pipeline with vs without the Scientific Value Gate. This is an **ablation**, not a byte-for-byte replay of the old PR #83 revision.

## Status and safety

- The isolated GitHub PR implements a callable experiment platform and offline mocked-model tests.
- **No real DeepSeek research-quality result exists until an Owner explicitly starts the paid runs and the provider responds.** Unit/integration CI does not replace this.
- All Owner API endpoints require the existing two-layer auth (API bearer and individual session), active Owner role and separate model-cost consent. No deploy, GET request or case creation calls the model.
- The full PDF is not committed to the public repository. PDF upload holds bytes only in memory/temporary storage, extracts text using PyMuPDF, and saves source page text privately to PostgreSQL.
- No direct shell/HTTP invocation from this ChatGPT conversation into the Owner-authenticated Render instance is currently available. An operator with a signed-in Owner session must use the trusted CLI; **do not paste credentials into ChatGPT or GitHub**.

## First benchmark

Shen et al., *How metro networks respond to extreme rainfall: a coupled To–Through resilience perspective* (DOI 10.1016/j.trd.2026.105654). Its uploaded 24-page PDF yields approximately 21 blind-eligible pages and ~13 extraction batches under current chunking. Estimated paid calls: extraction+no-gate A ~19, gated B ~7 (depending on whether relevant OpenAlex papers are returned); the existing 30-call daily ceiling may therefore accommodate both, **but existing same-day usage can prevent a full pair**. Token budgets are hard reservations, not exact billing amounts.

Hold the author Future Work/Discussion recommendations and earlier assistant R0 ideas out of the initial diagnostic prompts. Original methods/results and negative outcomes remain visible. The model discovers its own failure modes and scientific frontiers.

## Workflow

1. Owner securely uploads *one* PDF via `POST /api/personal-research/me/sc05/cases/pdf` with Content-Type `application/pdf` and `X-Research-Paper-Title`. Alternatively upload verified PDF page text to `POST /cases`, with future-work holdout applied automatically. Return document ID and SHA.
2. `POST /cases/{id}/ab` creates an A/B pair with no model spending. The server pins the pipeline source hash.
3. With explicit Owner model consent, `POST /runs/{A}/start` executes **science_gate_off** first. It produces a model-derived evidence ledger, saves it as immutable shared case evidence and records all LLM stage responses, usage and total tokens.
4. `POST /runs/{B}/start` executes **science_gate_on** against the **same frozen facts**. The difference is the scientific-value classification stage and route constraints. OpenAlex searches may differ because query planning is part of the treatment; all queries and results are preserved.
5. `GET /pairs/{pair_id}/blind` displays the reports as neutral A/B presentation labels, without model variants. The Owner assigns source-accuracy (15%), independent science value (30%), complete mechanism narrative (25%), prior-work depth (20%) and feasible experiments (10%), each 0–5. Imaginary sources/claims set `hard_failure=true`. Scope-checks or "add sensitivity tests" are not standalone scientific advances.
6. Only after **both reports are scored**, `GET /pairs/{pair_id}/comparison` reveals which variant was on and off, their ratings, deltas, costs, structural warnings and failure tags.
7. Inspect `GET /runs/{id}/audit` for actual raw stage responses and grounded source IDs. Treat blind presentation as a reviewer protocol: this initial Owner-only prototype does not technically prevent the Owner from inspecting audited model versions before rating; a separate reviewer role can be added later.
8. Make one targeted prompt, Skill, or retrieval change, pin a new pipeline SHA, and repeat on the same paper. Confirm generalization on a *new*, held-out published paper before accepting the improvement.

## Operator CLI (no new frontend)

Runs only from a machine where the Owner/service tokens are provisioned in protected environment variables:

```bash
export SC05_API_BASE_URL="https://<isolated-render-service>.onrender.com"
# SC05_API_BEARER_TOKEN and SC05_OWNER_SESSION are supplied securely
python -m scripts.sc05_eval_client --pdf "./paper.pdf" --out "./private/sc05"
# Creates case/pair, no paid API calls.

python -m scripts.sc05_eval_client --pair-id "sc05pair_..." \
  --out "./private/sc05" --authorize-paid --wait
# Writes original model reports, owner audit JSON and blinded report files.
```

Do not rely on free Render BackgroundTasks for production-grade long-running jobs. This test setup checkpoints provider replies, supports failed-stage replay, and reserves the daily call/token budget before each attempt. Crashes *between the paid provider response and its checkpoint commit* can still cause duplicate charges when retried. If the job remains in 'running' after service interruption, investigate worker status rather than blindly re-submit.

## Scientific acceptance (human assessment)

A passing technical test asserts permissions, output shape, citations, DB persistence, bounded calls and no secret leakage. It does **not** establish research insight.

The actual scientific test should require:
- a nontrivial scientific phenomenon extracted independently from paper findings;
- a competing explanatory mechanism, not only a model or evaluation weakness;
- a narrative spanning observed tension -> new mechanism -> observable implication;
- specific nearby papers and transparent novelty boundaries;
- a minimum experiment capable of distinguishing mechanisms;
- evidence-linked statements, no false empirical computations or full-text review claims;
- blind improvement versus baseline plus repeat performance on an unrelated paper.

At the end, the developer platform should register the pair ID, source SHA, pipeline SHA, human scores, failure tags and next iteration owner. This PR stores Owner audit entries and SC05-specific tables. A unified DevStudio experiment dashboard linkage remains a separate integration.
