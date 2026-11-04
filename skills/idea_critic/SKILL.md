---
name: idea_critic
description: Attempt to falsify research novelty and feasibility before recommending research investment
---

# Idea Critic

For each candidate idea, conduct adversarial, evidence-backed review:

- Prior art: look for direct matches, close substitutes and comparable problem/method combinations. State the limits of your search.
- Assumptions: identify requirements about labels, temporal alignment, geospatial coverage, causal claims, computing and data access.
- Baselines: require at least a simple conventional baseline and an appropriate competitive baseline.
- Leakage: flag train/test leakage, spatial autocorrelation, temporal leakage and evaluation domain shift where relevant.
- Deliver a verdict as `值得小规模验证`, `需要补充证据` or `暂缓` with reasons; this is not publication acceptance prediction.

Never invent supporting references. Separate paper-specific evidence from your own hypothesis.


## Five mandatory feasibility gates (Codex/radar rubric)

Treat these as explicit fields, not an arbitrary weighted average.

1. **规划问题**: planning relevance, not simply exchanging one model for another.
2. **数据可得**: list exact datasets, real acquisition rights, spatial and temporal granularity, sample, preflight test and failure criteria. An item in a private data inventory is not proof of permission or actual access.
3. **构念有效**: never replace observed behavior with accessibility, individual health with spatial proxies, inundation resilience with elevation, or causal effects with correlations.
4. **文献增量**: targeted checks against closest prior art, including problem / method / outcome relevance. Zero retrieved papers does not demonstrate originality; mark novelty unverified.
5. **规模可控**: one-city / small-sample minimum viable experiment, baselines, metrics and stopping rules.

Optionally emit `minimum_data` and `stop_conditions` as JSON string arrays. Keep them as **unverified proposals**, not checked results. AI-only screening may recommend B/C/D, but must not grant A: A requires human verification of all gates. When source papers are abstract-only, distinguish "not in abstract" from "absent from full text". Merge overlapping candidate ideas rather than counting cosmetic reformulations separately.
