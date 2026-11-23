---
name: cross_paper_synthesis
description: Synthesize multiple distinct papers into evidence-linked L1 research signals without forcing trends or topic combinations.
version: 1.0.0
---

# Cross-Paper Synthesis Skill

## Purpose

Produce research signals, not annotated bibliographies. The unit of analysis is a research development supported by multiple distinct works. A list of paper summaries is not a synthesis.

## Input requirements

Use only the supplied, provenance-preserving paper snapshot and source coverage. Each paper must have a stable paper ID, title, venue, publication date, URL, source group and evidence level. Do not invent missing fields. If fewer than two substantively related distinct works exist, return a single-paper observation or no L1 signal.

## Synthesis procedure

1. Group papers by a substantive research question, construct, mechanism, measurement, evaluation problem or technical capability—not by shared keywords alone.
2. For each group, state what changed or remains unresolved and why the development matters.
3. Compare at least two distinct works. Identify what is shared, what differs, which methods or evidence are complementary, and where results conflict.
4. Separate paper facts, author claims, cross-paper synthesis and new hypotheses.
5. Identify direct evidence, indirect mechanism links, counterexamples and unlinked records. Do not force all papers into one narrative.
6. Assess the research gap. Use author_claim_only when the gap comes from an author's discussion; use compared_to_prior_art only when actual nearest neighbors were examined. Otherwise use not_assessed.
7. Assess trend strength: single_paper, multi_paper_observation or historically_compared. Historical claims require comparable snapshots, a fixed time window and denominator.
8. Explain conditional team relevance using only authorized profile and dataset metadata. A listed dataset does not prove access, quality or suitability.
9. Recommend an action only when evidence supports one: monitor, deep-read, compare, reproduce, adapt or reject.
10. State contrary evidence, missing full text, source coverage limits and the next decisive check.

## Quality rules

- No fixed quota of topics. Zero strong signals is a valid result.
- Do not force a cross-disciplinary combination. A/B/C may each yield independent signals.
- Do not call a single paper a trend, a method release a scientific breakthrough, or an author claim a verified gap.
- Do not claim novelty from sparse retrieval.
- Do not infer a causal mechanism from correlation, prediction importance or a model explanation alone.
- Cite only paper IDs present in the supplied snapshot. Every key claim must carry one or more supporting IDs; contested claims should also identify counterexample IDs.

## Required output

Return one JSON object with:
- signals: source_group, title, explanation, paper_ids;
- claims: kind, statement, paper_ids;
- gap_status: not_assessed | author_claim_only | compared_to_prior_art;
- trend_status: single_paper | multi_paper_observation | historically_compared;
- comparison_window when historically_compared;
- team_relevance and team_fit_status;
- action_suggestion;
- limitations and missing_evidence.

The rendered L1 report should use the report_templates Skill. L2 deep reads and L3 opportunities are optional and may remain empty.