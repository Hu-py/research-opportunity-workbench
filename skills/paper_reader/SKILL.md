---
name: paper_reader
description: Structured, evidence-level-aware reading of scholarly papers for research continuity and method comparison.
version: 1.1.0
---

# Paper Reader Skill

## Purpose

Read a paper to establish what it actually studied, what it demonstrated, what it only claimed and what remains unanswered. Do not turn a paper summary into a novelty judgment.

## Required extraction

1. Bibliographic identity: exact title, authors, year, venue, DOI/URL, publication type and version status.
2. Research purpose: field problem, specific research question and why it matters.
3. Conceptual framing: key constructs, definitions, theoretical assumptions and causal/predictive target.
4. Study design: geography/system, population, spatial and temporal scale, unit of analysis and sampling.
5. Data: sources, coverage, period, variables, labels, sample size and known restrictions.
6. Method: model or analytical strategy, inputs, outputs, mechanism, assumptions, training/evaluation split and baselines.
7. Results: only results explicitly supported by the supplied evidence; distinguish quantitative findings from qualitative interpretation.
8. Contribution: what the authors claim, what the evidence demonstrates and what is not independently verified.
9. Limitations: author-stated limitations, limitations visible from the design, and unknowns that require full-text inspection.
10. Research continuity: which question this paper answers, which it leaves open, and which next questions are plausible but still hypotheses.

## Evidence rules

- Mark each extracted item as metadata, abstract or full_text evidence.
- A missing abstract is not evidence that the paper is irrelevant; it is a reason to lower confidence and seek another source.
- Never infer sample size, model architecture, metrics, statistical significance, causal identification or data access if not present in the supplied source.
- Keep author_claim separate from paper_fact and agent interpretation.
- Preserve the exact source URL and DOI. Do not invent page numbers or quotations.

## Output

Return:
- a concise paper identity block;
- a structured table of question, construct, data, unit, method, inputs/outputs, baselines, findings and limitations;
- author claims versus evidence-supported findings;
- the paper's role in the current research line;
- open questions and missing full-text checks;
- a recommendation: deep_read, use_as_direct_neighbor, use_as_method_source, background_only or reject, with reasons.

A paper's venue or citation count is not a substitute for reading its research contribution.