# SC05 — Research Diagnosis: pilot intake and blind evaluation plan

This branch creates the **first reusable diagnostic component**, not a completed live DeepSeek experiment. It is intentionally not mounted to the live personal Research Atlas API or scheduled to run. This avoids moving unpublished manuscript content to a cloud provider or initiating a paid model request before the research owner reviews the evidence snapshot.

## Researcher's first upload

**Required:** Latest manuscript draft (DOCX / PDF / MD), even if unfinished. The paper is used for the research question, study units, data, methods, experimental claims and limitations. Do not publish its contents to a public GitHub branch unless the researcher separately approves.

**Highly recommended:** A small, anonymized spreadsheet or CSV of aggregated experiment outcomes, split definitions and data density by region (R2/RMSE/MAE, number of labeled roads, children per road, AOA coverage, distribution diagnostics). Do not upload individual children’s outcomes, IDs, addresses or identifiable records.

**Optional:** Reproducible notebooks or scripts for label linkage, train/test splitting, AOA calculations, environment-shift metrics, and external validation. Restrict to code and synthetic or aggregated input until repository access permissions are reviewed.

Manuscript-only work can establish claims-evidence relationships and suggest diagnostics; it cannot honestly claim to recompute spatial coverage, verify leakage or estimate label reliability from the raw samples.

## Blind scientific evaluation

The researcher already proposed a possible multi-city next study. That proposed solution and previous assistant advice are placed in an **evaluator-only holdout**, not passed into the diagnostic prompt. The original manuscript's study objective, methods and results must remain intact. Author discussion that explicitly proposes the future solution may be held out, but empirical limitations and caveats needed to interpret data remain visible.

A neutral evidence ledger is prepared with fact IDs F001..., actual source section name, literal excerpt and status as author-reported or independently computed. The ledger is manually checked before making an LLM call. The blind snapshot is immutable and content-hashed.

SC05 is required to reconstruct what the study intended and what its evidence actually supports, to diagnose problems using evidence fact IDs, to offer competing explanations and falsifying tests, and to allow an empty list when no problem is supported. Only then should later rounds search literature and redesign the project. It must *not* be required to propose another city or any one particular architecture.

## Implemented in current PR

- A stable Skill: skills/research_diagnosis/SKILL.md
- Versioned evidence/diagnostic schema: skills/research_diagnosis/references/research-state-schema.md
- Stage-0/Stage-1 input and output validation: backend/sc05_research_diagnosis.py
- Offline tests: tests/test_sc05_research_diagnosis.py

## Not yet done (requires the manuscript)

- Parsing the actual manuscript into a factual neutral evidence ledger and validating every claim’s excerpt;
- selecting a no-answer-leakage initial view of manuscript sections;
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

The first response to the researcher should request the manuscript, not another web interface or a new deployment.
