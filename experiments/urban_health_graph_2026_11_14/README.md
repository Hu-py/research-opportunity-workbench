# Urban health × spatial graph learning: first Research Atlas scientific trial

**Status:** Experimental, offline and fully reproducible *public metadata* end-to-end test.
Nothing in this experiment validates urban-child-health prediction scientifically.

## What is real and what is not

- **Real archived public source data:** Ten specifically identified OpenAlex records from the repository's `data/radar/openalex_latest.json` feed (retrieved 2026-11-09), with unchanged titles, DOIs, published dates and venue names. `real_metadata_sample.json` pins the exact records used, with provenance and source limitations.
- **Real code:** The L0/L1 classification, reference checking and draft rendering logic imported unchanged from three-source draft PR #57, combined with the first migrated Skill adapter in draft PR #69. Group A/B/C is **Research Atlas's new taxonomy**, not old ROR A/B. Original feed's 'planning/methods' pools are different; paper groups are reclassified by indexed venue.
- **Deterministic authored experiment:** The three L1 research topics and method-transfer questions are explicitly authored *title-level hypotheses*. They have source-linked paper IDs but are **not model-generated findings** and do not establish a gap or a trend over time.
- **Not run:** No OpenAlex API live request for this case; no GPT/DeepSeek API; no personal or child data; no trained XGBoost/GraphSAGE; no accepted scientific novelty claim.
- **No automatic side effects:** The runner does not write to production database, send paid API requests, publish a report or merge PRs.

## Reproduce

```bash
python scripts/atlas_urban_health_trial.py --out /tmp/research-atlas-urban-health
python -m pytest -q tests/test_atlas_urban_health_case.py tests/test_research_opportunity_skill.py
```

Outputs `research_case.json` and `research_case.md`, including input fingerprint, all paper evidence links, three categorized L1 draft signals, method transfer protocol and failure criteria. Outputs are not committed to production.

## Test's concrete scientific question

Can spatial graph context outperform non-graph and simple neighborhood aggregation baselines on a **strictly spatially held-out, out-of-domain urban health endpoint**, without target-label leakage? Test spatial blocking, spatially disjoint cities, risk of noisy sparse linked child outcomes, AOA, distinct target label variance, and uncertainty. Compare plain XGBoost, neighborhood mean/distance weighted XGBoost, GraphSAGE embeddings plus XGBoost, and direct supervised GraphSAGE. These are *planned comparisons*, not demonstrated wins.

## Next requirements before actual scientific acceptance

1. Acquire relevant source abstracts and verify the key full papers (especially closest graph health prior art); determine whether title-level examples actually support the proposed mechanism.
2. Run genuine query-based OpenAlex collection for this topic. The archived ten-paper sample is illustrative and is **not** evidence of exhaustive search or representative literature coverage.
3. Build cross-source L1 evidence synthesis using explicitly approved model calls and cite statement-to-excerpt provenance. Stop if support fails.
4. Bring isolated external-city evaluation records and spatially blocked baselines; do not publish raw personal health observations. Include data use permissions and aggregation checks.
5. Store run manifests and expert review approvals under Development Studio prior to shared publication.
