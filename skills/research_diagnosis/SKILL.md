---
name: research-diagnosis
description: Diagnose the limits of an existing scientific study and redesign its research strategy from original goals, methods, data and experimental evidence. Use when an existing paper, project, experiments or unsuccessful transfer study needs an independent, non-leading diagnosis and evidence-driven alternative research plans. Preserve exact fact provenance, test competing explanations, and distinguish unverifiable claims from model failures.
---

# Research Diagnosis · SC05

## Outcome and scope
Build an auditable diagnosis of an ongoing scientific project before reading new algorithm papers or generating research variants. Do not assume continued optimization of the present architecture is the right objective. Treat a change in data, validation design, or research question as a legitimate alternative; do not force a new method or a fixed number of opportunities.

## Blind evidence intake
1. Read a provided manuscript and any available experiment files. Record each factual observation with an exact source anchor: document ID, section, quoted excerpt and claim type.
2. Keep original goals, data descriptions, methods and results in the **diagnosis input**. Hold future-work recommendations, planned next studies, desired model architecture and known answer keys in a separate **evaluation holdout**. Do not conceal genuine empirical results or caveats necessary to interpret results.
3. Where the study cannot share raw data, distinguish an author's reported statistic from a tool-recomputed statistic. Never claim to have recalculated it.
4. Keep individual-level personal or health data out of prompts. Require anonymized aggregates and explicit consent for model submission.
5. Freeze each input snapshot and its SHA256 before model invocation. Keep paper versions and file hashes; do not silently update an earlier run.

## Five-stage workflow
- **Stage 0 — Reconstruction:** Identify precise estimand/question, data-producing process, train/test unit, available labels, experimental comparisons, observed results and stronger claims needing support. Record missing information rather than filling gaps.
- **Stage 1 — Autonomous diagnosis:** Produce evidence-linked contradictions, non-identifiability or validation gaps and hypotheses for failure. For each, explicitly give rival explanations, falsifiable checks, decision relevance and epistemic status. It is acceptable to find no supported bottleneck.
- **Stage 2 — Evidence seeking:** Translate the diagnosis into narrowly scoped research questions, retrieve original theory/method/negative results, and report conditions under which each transfers. The approved task journal directory can constrain recurring monitoring, but exploratory literature search should be allowed outside it with transparent source provenance, not silent directory approval.
- **Stage 3 — Research redesign:** Compare *model change, data change, evaluation change and question change* on equal footing; do not mandate one option per category. For each candidate, list feasibility prerequisites, expected distinguishing evidence, minimum experiment, what would falsify it, and whether the original problem remains answerable.
- **Stage 4 — Independent critique:** Search for contradictions and prior work, challenge the feasibility of each plan and allow all proposals to be rejected or held. Never assert novel publication contribution without a separate systematic prior-art review.

## Critical constraints
- Do not insert the known next-paper idea, desired diagnosis, or previous assistant recommendations into the diagnostic prompt.
- Cite the evidence package's exact fact IDs. Missing or invented IDs invalidate the diagnosis.
- Separate [documented observation], [inference], [untested mechanism], [information missing], [independent external evidence] and [research proposal].
- Avoid interpreting missing target-domain labels as proof of either good or bad generalization.
- Review whether an algorithmic improvement can logically repair the observed evidence or validation failure; do not recommend architecture changes by default.
- The model may suggest collecting data, restricting scope or postponing a publication claim.

## Output
Return a decision-oriented diagnosis report:
1. Study reconstructed from facts (and scope of each fact).
2. Claims–evidence gaps, bottlenecks, rival explanations and required checks.
3. Source-traceable theory search and conditions for transfer.
4. Ranked or rejected alternative study paths, with feasibility and stop criteria.
5. The next minimum test that would most reduce uncertainty.
6. Open questions and limitations of the agent's own evidence.

## Evaluation discipline
Run the previous SC04 model and SC05 on the same **blinded primary evidence**, not on a prewritten summary of answers. Keep evaluators' hidden criteria separate, including anticipated redesigns. Evaluate diagnostic validity and recall, discrimination among rival mechanisms, citation precision, feasibility, and ability to reject unsupported claims. Compare costs and failure rates alongside quality scores.

Refer to `references/research-state-schema.md` when preparing an input snapshot or inspecting a structured report.
