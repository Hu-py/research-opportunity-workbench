---
name: literature_discovery
description: LLM-led research discovery, adaptive scholarly search planning, semantic paper screening, and cross-domain opportunity mapping from the team's research profile and registered data assets.
---

# Literature Discovery Skill

## Mission
Discover research that is substantively useful to the team's research programme. Do not reduce discovery to keyword matching, title overlap, or a fixed list of search strings.

## Inputs
- Current team research profile and research-line problem statements.
- Registered, non-restricted dataset metadata only: names, fields, spatial/temporal coverage, format, description and access caveats.
- Verified team research outputs and previously reviewed papers.
- Enabled Academic Source Registry entries, including discipline, source type, rank label, aliases and OpenAlex source resolution status.
- Current user-supplied interests and frontier domains, when available.

Never send raw datasets, restricted records, credentials, private file paths, personal records, or confidential source material to a model.

## Stage 1 — Understand the research programme
Infer core scientific and planning problems; existing capabilities, methods and empirical contexts; usable and missing data; adjacent disciplines; and explicit unknowns. Do not infer access rights or data quality from a registry entry.

## Stage 2 — LLM search planning
Generate complementary problem-first, method-first, evidence-first, frontier-first, and contradiction/gap search strategies. For each provide a natural-language scholarly query, intent, target discipline, recency window, and rationale. Queries must use semantic formulations, related constructs and alternative terminology, not merely copy profile keywords.

Use the enabled source registry as a discovery prior. A source rank is provenance metadata, not proof an individual paper is relevant or high quality. Never invent rankings or claim a venue is indexed when unresolved.

## Stage 3 — Retrieve and expand
Use scholarly metadata APIs to retrieve candidates. Deduplicate by DOI, then stable provider ID, then normalized title. Keep provenance, query strategy, provider URL, DOI, venue, publication date and abstract. If results are weak or narrow, ask the LLM to diagnose coverage gaps and propose a second search round. Zero results do not establish novelty.

## Stage 4 — LLM semantic screening
Evaluate candidates against the complete research-line context, not keyword overlap. Assess conceptual relevance, methodological transferability and assumptions, empirical/data relevance, disciplinary contribution and source context, recency, and incremental value over reviewed work.

Return a 0–100 relevance score, priority, rationale, relation type (direct, method_transfer, frontier, contradictory, background), and full-text verification needs. A score is an LLM triage judgement, not a calibrated probability or quality metric.

## Stage 5 — Human review and evidence discipline
All retrieved papers remain pending until human review. The LLM cannot verify a paper, establish novelty, infer unavailable full-text details, or claim dataset access. Distinguish metadata-only, abstract-level and full-text evidence. Cite only exact retrieved paper IDs and URLs. Preserve model, prompt/skill version, search strategy and analysis provenance.

## Output
Return structured JSON with search plan and rationale; retrieved candidates; semantic relevance assessment and evidence level; missed-area and next-search recommendations; research-line and dataset relations; explicit uncertainties and human-review requirements. Prefer a small, well-justified set of high-value papers over large volumes of superficially similar records.