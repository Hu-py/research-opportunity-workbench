# SC05-R1 · Authenticated Real-Agent A/B Evaluation Runbook

**Objective:** Test whether the *Research Atlas agent*, not the human assistant, can autonomously reconstruct, criticize and extend a published study into a genuinely independent scientific question. Compare the current SC05 pipeline with vs without the Scientific Value Gate. This is an **ablation**, not a byte-for-byte replay of the old PR #83 revision.

## Status and safety

- The SC05 Owner API and ChatGPT MCP bridge are implemented in the isolated staging code line. Offline mocked-model CI validates API and tool behavior, not real DeepSeek research quality.
- **No real DeepSeek research-quality result exists until an Owner explicitly starts the paid runs and the provider responds.** Unit/integration CI does not replace this.
- Browser-facing Owner REST endpoints require the existing two-layer auth (API bearer and individual session), active Owner role and separate model-cost consent. The ChatGPT MCP bridge uses its own OAuth Authorization Code + PKCE grant, verifies the active Owner and scopes, and still requires explicit per-run paid consent. Case creation, pair creation and preflight do not call the model.
- The full PDF is not committed to the public repository. PDF upload holds bytes only in memory/temporary storage, extracts text using PyMuPDF, and saves source page text privately to PostgreSQL.
- A ChatGPT MCP workflow is now implemented in staging code; see [SC05 ChatGPT complete workflow guide](SC05_CHATGPT_OPERATING_GUIDE.md). It is not considered available until the exact staging commit is manually deployed to Render, ChatGPT completes Owner OAuth, and the current tools/list is verified. Do not paste Owner credentials, provider keys or bearer tokens into ChatGPT or GitHub.

## Experiment principles and iteration rules

These principles govern R6 / SC05 evaluation and take precedence over ad hoc module-level testing.

### 1. Evaluation target and scope boundary

- The object being evaluated is the Research Atlas agent's **complete scientific workflow**: from understanding a published paper and reconstructing its evidence, through critical diagnosis and independent question formation, to a defensible research direction and feasible next experiments.
- This is an evaluation of the agent's research capability and workflow quality. It is **not** an empirical study of the paper's subject, a dataset-extraction project, or a request to train/run an empirical model on the paper's underlying data.
- Paper text extraction and evidence-ledger construction are permitted only as controlled inputs to the agent evaluation. Do not describe them as empirical data analysis or as scientific findings produced by a new real-world experiment.
- Keep experimental-design rigor separate from scientific research value. A technically valid run does not automatically demonstrate useful scientific insight.

### 2. Complete the end-to-end workflow before local optimization

- First run the full workflow on the frozen benchmark paper. Do not prematurely narrow the evaluation to one stage, module, prompt, or isolated tool merely because an early weakness is visible.
- After the complete run, evaluate the overall output and workflow. Then diagnose the process stage by stage, identify the highest-impact failure, and jointly choose a targeted repair.
- The iteration order is: **complete workflow → overall evaluation → process diagnosis → targeted optimization → full regression**.
- A module-level test may be used to explain a diagnosed failure, but it must not replace the end-to-end evaluation or be reported as proof that the whole agent has improved.

### 3. Controlled A/B design

- Every A/B pair must start from one explicit, falsifiable evaluation question and a pre-declared hypothesis. State the treatment, control, expected effect, primary evaluation criteria, and any known confounders before execution.
- Use the same benchmark paper and immutable source snapshot for both arms. Record the paper/document ID, source SHA-256, extraction version, and shared evidence-ledger identity.
- For the current SC05 gate ablation, run the baseline arm first, freeze its common evidence ledger, and have the gated arm consume that same frozen evidence. Do not silently regenerate or replace shared facts between arms.
- Pin the repository commit, pipeline/source hash, prompt and Skill versions, model/provider and model parameters, tool configuration, and evaluation rubric. The arms may differ only in the declared treatment. If a treatment necessarily changes query planning or retrieval, preserve every query and result and record that as a treatment-mediated difference rather than pretending the retrieval traces are identical.
- Do not change the hypothesis, rubric, benchmark, or treatment after seeing results without opening a new, explicitly linked experiment.

### 4. Run integrity, checkpoints, and paid execution

- Create a clean pair for each new experimental iteration. Never overwrite a prior run, silently reuse a checkpoint generated by a different prompt/source version, or replay a completed arm just to make the pair look symmetrical.
- If a run fails, inspect its status, stage, error, source/pipeline hashes, and saved checkpoints first. Preserve all prior evidence. A changed prompt, code revision, or incompatible checkpoint requires a new run/pair ID; do not force-retry an incompatible run.
- Prepare and validate both arms before paid execution. Confirm source identity, declared treatment difference, budget availability, Owner authorization, and model-cost consent. Preparation and status reads must not be represented as model execution.
- Report model calls, input/output tokens, estimated or actual cost, timestamps, checkpoint stages, retries, and failures from recorded evidence only. Never infer a completed run from a prepared/queued state or claim a scientific result before the model outputs exist.

### 5. Blinded assessment and independent quality

- Score both reports before revealing which arm is gated or ungated. Use the same rubric and scoring scale for both arms; record the evaluator, scoring time, and any exposure to variant identity or audit traces.
- The current Owner-only prototype hides variant labels in the blind presentation but does not technically prevent the Owner from inspecting audit records first. Therefore, call the assessment fully blind only if the evaluator has not accessed variant-identifying audit information; otherwise disclose the limitation and mark blinding as compromised/partial.
- Keep technical execution, workflow completion, evidence quality, evidence-supported reasoning, scientific value, and generalization as separate evaluation dimensions.
- Technical pass, valid citations, successful persistence, or a complete report are necessary process checks, not sufficient evidence of scientific contribution.

### 6. Diagnose, repair, and test generalization

- After both arms are completed and scored, reveal the variants, compare outcomes, inspect stage traces and evidence, and identify the mechanism of failure or improvement.
- Make one targeted change per iteration wherever possible. Record why it was selected, which failure it is intended to fix, and what observable change would count as success.
- Re-run the same benchmark paper for controlled regression, then evaluate on at least one previously unseen held-out paper before accepting the change as a general improvement.
- A same-paper gain establishes only benchmark-specific improvement; it does not establish generalization. Report unseen-paper results separately and retain negative or mixed results.

### 7. Mandatory experiment record

Maintain a concise overview table and a detailed trace for every round. The overview row must include: experiment category and ID, problem to solve, method, experiment content, status, brief result, next step, and link/reference to the detailed record.

The detailed record must preserve, at minimum:

- experiment question, falsifiable hypothesis, control/treatment definition, pre-declared criteria, and decision rationale;
- benchmark paper/document identity, source SHA-256, shared evidence snapshot/ledger ID, and any holdout rules;
- repository commit, source/pipeline SHA, prompt/Skill/config versions, model/provider and parameters;
- each stage's input, output, evidence IDs/citations, tool calls, timestamps, status, and stage-level warnings/errors;
- run IDs and pair ID, checkpoint inventory, retries/recovery actions, model-call counts, tokens, cost, and archive locations;
- blind scores, evaluator and blinding limitations, variant comparison, overall conclusion, unresolved risks, and next-round owner/action.

Never delete or overwrite failed, superseded, or negative runs. Link follow-up rounds to their predecessors so that every change and conclusion remains traceable.

### 8. Status and claim discipline

- Distinguish at least: planned, prepared, queued, running, completed, failed, and needs-review. A pair is complete only when both arms have terminal results available; a partial pair remains partial.
- Distinguish platform/technical success from scientific-quality acceptance. Use needs-review until evidence, reasoning, and scientific value have been assessed.
- State explicitly what was executed, what was only prepared, what failed, what was not attempted, and which claims are supported by saved evidence.

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
