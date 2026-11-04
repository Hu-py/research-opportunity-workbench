---
name: idea_discovery
description: Generate and merge evidence-grounded single-paper and cross-paper research hypotheses
---

# Idea Discovery — Research Radar

This skill implements an **inspiration/triage stage**, not verified novelty.

1. Ground each hypothesis in exact paper IDs, titles and stable URLs from the current evidence set. Label all abstract-only conclusions as tentative; absence from the abstract is **not** proof the full text lacks a method, dataset or limitation.
2. Explore five controlled transformations, selecting only where the evidence supports them:
   - **换方法**: transfer a computational method to a defined domain bottleneck; state assumptions, not just the model name.
   - **换研究主体**: change population, unit, or outcome while preserving construct validity.
   - **换研究环境**: test generalizability across cities, temporal contexts or institutions.
   - **换数据**: replace/add a dataset to improve identifiable constructs and coverage.
   - **补空白**: propose a falsifiable gap that must still be checked against recent prior art.
3. **跨论文组合**: combine genuinely complementary causal or methodological contributions from at least two referenced papers. Do not combine merely because both mention a similar city topic.
4. Merge overlapping hypotheses before scoring. Prefer one coherent idea with multiple supporting angles instead of several cosmetic title variations.
5. Every output idea must state: research question, why it matters, specific method, linked paper IDs, baselines, minimum viable experiment, missing data, key falsifier, and novelty status `unverified`.
6. Prefer 1–3 justified ideas to dozens of low-quality suggestions. Exclude confidential participant data and claims that registered datasets have already been accessed.
7. When importing old research-radar HTML and an external screening report, treat them as **historical model outputs**. Preserve provenance; do not silently elevate their claims to verified facts.

Default output is a structured JSON proposal, with no invented citations or venue acceptance claims.
