# SC05 v0.2 — Paper-only autonomous research diagnosis

## What the user needs to supply
**One PDF paper.** Nothing else is required for source-grounded research reconstruction, conceptual gap detection, theory search and conditional future-study design. Additional raw data, code, maps or OD records are **not required** unless the user later chooses to implement a specific proposed experiment. The user can continue uploading a single article per analysis.

## What the operator runs
Install optional PDF support:

    pip install -e ".[paper]"

From an authorized runtime with the DeepSeek secret set as an environment variable (never commit the secret), run:

    python -m scripts.sc05_paper_report \
      --pdf "/private/papers/input.pdf" \
      --output "/private/reports" \
      --ack-model-spend

No frontend deployment or new database schema is needed. The CLI only runs when an authorized operator explicitly executes it. The CLI does NOT run automatically on container startup or expose an unauthenticated HTTP endpoint.

The server-side credential is read from `SC04_DEEPSEEK_API_KEY` or `DEEPSEEK_API_KEY`, but it cannot be read by the ChatGPT conversation itself. Merely having the credential stored in Render does **not** mean a paid SC05 experiment was run. This tool currently has no Render shell/task connector to invoke the CLI.

## Actual sequence
1. Local PDF extraction and section exclusion for blind evaluation (author Discussion/Future Work recommendations and references excluded from first pass; actual findings retained).
2. Multiple small model calls: source-fact extraction, each quote checked against the exact PDF page, with unique whitespace-only PDF line-break corrections allowed.
3. Freeze SHA256 evidence ledger; reconstruct method/data dependency chain, separating observed, derived and simulated values.
4. Independent source-grounded scientific diagnostic, with rivals and falsification tests. No predetermined future-paper ideas are injected.
5. Diagnose-driven OpenAlex search, verified DOI/URL and abstract capture, followed by a separate near-literature comparison with exact abstract excerpts.
6. Research route redesign, including baselines, design feasibility and stop tests; independent skeptical review may hold/reject all.
7. Markdown report + audit JSON with tokens, searched papers, source references, incomplete evidence and structural quality flags.

## Local outputs
`SC05_<hash>_report.md`: a decision-oriented report with eight scientific chapters plus structural QA.

`SC05_<hash>_audit.json`: private record of source evidence, actual model-stage outputs and token counts; **no key**. Protect and retain this file within the researcher's account/workspace.

## What is proven vs not proven
- **Covered by offline tests:** source excerpt matching and literal quote restoration, fake-reference rejection, per-stage JSON schema checks, no calls without key/cost consent, citation-anchored report structure and a complete mocked-model test.
- **Not yet proven:** the real model independently achieves the human-assisted R0 report's scientific quality. This requires an authorized DeepSeek run on the uploaded paper and a blind independent reviewer.
- **Not attempted:** re-estimating empirical effects, checking private operational records, optimizing network flows or proving novelty of research routes.
- **Current limitation:** if a model or external literature request fails partway through, a retry may repeat earlier paid steps; stage-level resumable checkpoints and persistent authenticated task execution are future production hardening work.

## Gold-standard benchmark
The first test source is the *published* 24-page Shen et al. To–Through metro paper, DOI: 10.1016/j.trd.2026.105654. The corrected neutral evidence snapshot has 19 verified facts; five initial excerpts had whitespace/line-break normalization and were revised to literal PDF spans. SHA256: `fb448d0c83b8b47bf92b97ebe4a11f46fa37ef0cfb898d2e0ad102c41a6821e5`.

For blind testing, keep the paper's future-work discussion and the prior human-assisted R0 opportunity report separate from stage 1. Do not score the agent merely on whether it guesses known next-paper options; review evidence integrity, method understanding, diagnostic novelty, literature depth and concrete feasibility.

The model is not allowed to assert that a 2024 expanded network under a reused 2021 hazard/OD profile was independently observed in 2024, or that time-lagged correlation with a constructed index proves prospective operational warning. These are **independent reviewer checks** that should not be inserted as stage-one model answer hints.
