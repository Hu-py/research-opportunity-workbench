# SC05 — Research Diagnosis: pilot intake and blind evaluation plan

This branch creates a **reusable diagnostic component**, not a completed live DeepSeek experiment. It is intentionally not mounted to the live personal Research Atlas API or scheduled to run. This prevents accidental paid execution and avoids mixing source material from different research projects. **The first real pilot is now the publicly published Shen et al. (2026) metro-resilience paper**, documented in `SC05_TRD_FIRST_PUBLISHED_CASE.md`; the unpublished child-health project is out of scope.

## Researcher's first upload

**Required:** One research document (published article or unpublished draft, in DOCX / PDF / MD). Use it for the research question, study units, data, methods, experimental claims and limitations. The current study is an uploaded published PDF. Do not commit publisher full-text PDFs or any confidential unpublished work to a public GitHub branch.

**Highly recommended:** Small aggregate CSV/XLSX files with the paper's metrics, comparisons and validation outcomes; for a transport study, useful files include OD summaries, station/segment time-series aggregates, simulation intervention outputs and reliability diagnostics. Do not upload identifiable mobility trajectories or sensitive personal records.

**Optional:** Reproducible notebooks or scripts for network construction, assignment assumptions, time-lag analyses, scenario interventions and independent validation. Restrict to code and synthetic or aggregated input until repository access permissions are reviewed.

Paper-only work can establish claims–evidence relationships and propose diagnostics; it cannot honestly claim to validate operational failures, re-estimate network flow, recalibrate simulation predictions or rerun scenarios without their corresponding datasets and code.

## Blind scientific evaluation

Any researcher-proposed next study and previous assistant advice are placed in an **evaluator-only holdout**, not passed into the diagnostic prompt. For the first published metro case, the original paper's Discussion §6.2 future-work recommendations are also withheld from the Stage-1 diagnostic prompt. The original manuscript's study objective, methods and results must remain intact. Author discussion that explicitly proposes the future solution may be held out, but empirical limitations and caveats needed to interpret data remain visible.

A neutral evidence ledger is prepared with fact IDs F001..., actual source section name, literal excerpt and status as author-reported or independently computed. The ledger is manually checked before making an LLM call. The blind snapshot is immutable and content-hashed.

SC05 is required to reconstruct what the study intended and what its evidence actually supports, to diagnose problems using evidence fact IDs, to offer competing explanations and falsifying tests, and to allow an empty list when no problem is supported. Only then should later rounds search literature and redesign the project. It must *not* be required to propose any specific number of variants or any particular method, transport mode, study region, or architecture.

## Implemented in current PR

- A stable Skill: skills/research_diagnosis/SKILL.md
- Versioned evidence/diagnostic schema: skills/research_diagnosis/references/research-state-schema.md
- Stage-0/Stage-1 input and output validation: backend/sc05_research_diagnosis.py
- Offline tests: tests/test_sc05_research_diagnosis.py

## Status and next development steps

- **Completed for first published case:** the 24-page PDF has been read and 19 neutral facts have been checked against exact PDF pages and frozen into a SHA256-identified source-input snapshot. The original full-text file stays in the conversation, not on GitHub.
- **Completed:** excluded the paper's Discussion §6.2 future directions and prior assistant ideas from the initial diagnosis input.
- running SC04 and SC05 with the **same** input and budget (not the old five-paper model prompt);
- actual DeepSeek calls and token/cost ledger;
- iterative search of computing methods and negative evidence driven by diagnosed uncertainties;
- independently reviewing and scoring generated study designs;
- writing and delivering a sourced SC05 Markdown research report.

Run-quality checks must report whether a finding comes from a source document, a recomputed diagnostic, an LLM hypothesis, or external theory. A user’s suggestion must not be re-labeled as an autonomous model finding.

## Pilot output

1. Research state evidence ledger with source references and missing-data flags.
2. Claims-versus-evidence table and 0–12 candidate diagnoses (no forced list).
3. For each diagnosis: source fact IDs, at least one rival explanation and a check that could falsify it.
4. Diagnoses prioritized by decision impact and verification cost.
5. Conditional research pathways (methods / data / validation / changed research question) and their feasibility requirements.
6. Blind A/B results (SC04 vs SC05), plus provenance, cost, critiques and next recommended minimum experiments.

The first published-paper intake is complete. Run the diagnosis only after a truthful, permissioned model-execution path is available; do not build a new frontend for each research experiment.
