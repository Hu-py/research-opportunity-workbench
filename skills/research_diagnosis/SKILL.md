---
name: research-diagnosis
description: Analyze one uploaded academic paper (PDF by default) to reconstruct its methods and data dependencies, independently diagnose scientific evidence gaps, search relevant theory and nearby research, and produce an auditable next-paper opportunity report with feasible tests and stop conditions. Use for paper-to-next-research, scientific idea discovery, or iterative research workbench evaluation; do not require raw datasets or source code.
---

# SC05 · Paper-only research diagnosis

## Interface
**Required input: one published or authorized paper.** The normal user uploads only a PDF; ask for no additional raw data or code at intake. Additional files are optional and may be proposed as future *feasibility requirements*, never prerequisites for generating the initial report. Support other publication topics without making the Zhengzhou or child-health projects implicit baselines.

**Output:** one readable Chinese research-diagnosis Markdown report, one source-and-model audit JSON, and a separated blind evidence snapshot. A published PDF may be analyzed for the requesting user; do not commit complete publisher text to GitHub. Explicitly distinguish model hypotheses from author findings, externally retrieved studies, and original numerical recomputation (not performed).

## Procedure (required order)
1. **Freeze the paper.** Read title, abstract, Introduction, Methods (including formulas/figures), Data, Results and *empirical* limitations. Preserve original pages and actual quoted excerpts, document and PDF hash. In first-pass blind tests withhold the author's Future Work/Discussion recommendations, previous assistant proposals and expected answer key, not meaningful negative results. Read PDF captions and diagram labels where extraction permits; mark unparsed equations/figures as unverified.
2. **Build a method/data dependency graph before proposing any method.** For each transformation record source data → observed/derived/simulated variable → formula, assumptions → evaluation → claim. Look explicitly for paths in which the proposed target is derived from candidate predictors, simulations are interpreted as observations, pre-event and post-event information are mixed, an outcome lacks independent evidence, or an intervention assumes fixed behavior. These are *diagnostic questions*, never automatic assertions of error.
3. **Independent diagnosis.** Use only verified source fact IDs. Provide competing mechanisms and falsifiable checks. Separate actual result, author interpretation, hypothesis and unknown. Do not force any number of findings; avoid suggesting an architecture before judging whether the current question is answerable.
4. **Plan targeted literature searches from diagnostic questions.** Seek theory, methods, independent empirical cases, negative findings and nearest competitors. Use OpenAlex or trustworthy primary publisher/preprint metadata with DOI/URL, date, abstract and clearly reported evidence level. Explore beyond the monitored journal directory, but do not silently approve a new permanent source. Do not say a method was evaluated in the source if the abstract does not say so.
5. **Compare near papers before generating research routes.** Record each candidate's actual task, known methodology, overlap, assumptions needed to transfer, limitations and whether it is a contradiction/counterexample. Ground each abstract-derived assertion in a literal excerpt. A short methods table is worth more than ten generic paper links.
6. **Redesign research, not just models.** Allow changes in the model, data, validation design and research question; compare routes without requiring one per type. For each route specify what *new* mechanism/question is added, what original evidence cannot answer, directly closest research, data feasibility, explicit baseline, minimum experiment, failure criterion and an alternative if data are missing. Zero good routes is a valid result.
7. **Independent scientific critic.** Try to invalidate each proposed path; label test / hold / reject. No research opportunity is called novel or publishable before fuller near-neighbor examination and, where necessary, new data.
8. **Deliver complete report and audit.** See `references/report-quality-gates.md`. Preserve snapshot SHA, source page IDs, citations, used external paper IDs, model stage/token usage, unresolved limitations and failed searches. If no real LLM call was made, label the output an offline workflow demonstration, not a SC05 blind experimental result.

## Explicitly prohibited shortcuts
- Do not ask for source code/OD/raw records merely to **understand** published formulas. Request minimal validation data only at the point of proposing a funded/reproducible experiment.
- Never put a previous human-authored research-direction report into the initial blind diagnosis prompt or pretend an assistant-generated draft was discovered autonomously.
- Do not give identical-looking methods as three different ideas, paste a generic "add GNN" recommendation, or claim that changing the study region alone is necessarily novel.
- Do not claim model performance, theoretical guarantees, deployment effectiveness, causal evidence or novelty beyond what the source and separately verified literature establish.
- Never reproduce full proprietary paper content in the report. Use short source excerpts and page anchors; do not print key values or server-only prompts to logs.
- A failed literature search is a validation gap, not proof that the topic is unexplored.

## Implementation
- Source + diagnosis validator: `backend/sc05_research_diagnosis.py`.
- Single-paper end-to-end pipeline: `backend/sc05_paper_only.py`.
- Explicitly authorized one-shot execution: `python -m scripts.sc05_paper_report --pdf paper.pdf --output ./reports --ack-model-spend`. Use the model key from the server environment, not chat.
- Read `references/research-state-schema.md` for structured evidence; `references/report-quality-gates.md` for report-level acceptance.
