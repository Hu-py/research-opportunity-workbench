# Live evaluation

## Latest: general B0 smoke baseline

Protocol: B0_PROTOCOL.md; source/dependency review: OPEN_SOURCE_REVIEW.md; real outputs and costs: b0-v1-results.json. Two fixed ResearchBench development records (astronomy and biology), anonymized reference plus two negative variants; DeepSeek V4 Pro, one call per case. No private/team input. No hidden cases used. Ranking adaptation is not the official benchmark protocol.

Results: 2/2 provider requests and output schemas succeeded. Repeating the identical runner reused 2/2 completed checkpoints, adding **zero requests**. Deterministic regression checks cover provider failure, uncertain interruption and missing reviews; these simulated tests are not evidence of live service recovery under every failure.

Reference-label agreement: **0/2**. Astronomy preferred the model-generated negative over the reference; biology preferred the fabricated negative over the reference. This does not establish that the references are scientifically superior, but it exposes uncertainty in unsupported-mechanism discrimination. Scores were produced by B0 itself; no independent expert or blind judge evaluated these outputs.

Representative generated questions (translated): (1) Can supernova-formed refractory cores followed by molecular-cloud mantle accretion reproduce observed dust masses and isotope ratios at z>4? (2) Can WIBS-4+ fluorescence plus ensemble clustering achieve at least 90% precision and recall for airborne pollen/spores under controlled conditions? Engineering diagnosis: question 1 has testable observables but its mechanism/data sufficiency remain unsupported. Question 2 invents an unjustified 90% threshold and is framed mainly as predictive performance, not knowledge gain. Both require substantive evidence checking before recommendation.

Improvement established: reproducible config/input checkpoints and no repeated payment on completed-run resume. Scientific quality improvement over a baseline: **not established**; this is the new baseline, not a B0-vs-B1/B2 comparison. Avoid preference for detailed mechanisms simply because generic reference text is less specific. The next smallest informative experiment is B1 with a bounded, cited evidence packet addressing one of these concrete uncertainties. Do not add B2 until B1 has paired evidence of benefit.

This round: 2 new requests, 1,512 input / 928 output tokens, estimated CNY 0.038664 (peak, cache-miss rates). Cumulative: **22 attempted calls / CNY 0.867088** including prior unknown reservations. No retries; nine historic requests still have unknown complete usage. Codex usage cannot be read or constrained to an exact 5%; stopped at this small checkpoint.

Status: stopped after persistent provider failure. No valid comparative superiority conclusion.

Cases: heat/tree-canopy equity (development), transit reliability/job accessibility (test), flood resilience (held out, not called). Team facts and dataset availability are synthetic/unknown; five real OpenAlex records per executed case are frozen in local audit storage with IDs, DOI, title, abstract and evidence status.

A replays original AI-lab planner/reader/generator/critic prompts and validators. B makes one integrated call. C independently explores extension/transfer/frontier then critiques and revises. All use Flash; auxiliary blind reviews use Pro. Different request budgets and same-family reviewers limit causal interpretation.

Initial concrete failure examples: a proposed HOLC-stratified tree-canopy cooling threshold study and a Guangzhou/US cross-city replication study. The latter omitted a required justification field. Neither is a validated recommendation. Model text also risked conflating land-surface temperature with air temperature and interpreting missing abstract information as a literature gap. These defects motivate targeted review, not additional agents.

All attempts, failures and reservations remain in ignored local SQLite. Interrupted/failed requests retain worst-case charges; actual usage cannot be claimed for responses whose usage was not received. No private input or credentials are committed.

## Observed outcome

| Case | A: existing prompts | B: one advisor call | C: paths + critic + revision |
|---|---|---|---|
| Heat equity | Produced candidates, rejected missing mandatory field; rerun failed in a model stage | One complete validated candidate | Three path candidates generated; critic failed, no final recommendation |
| Transit accessibility | HTTP 503 | Total-deadline timeout | HTTP 503 |

Valid B title: **树冠覆盖对历史红线街区日间热暴露的尺度阈值效应**. It asks whether the canopy cooling threshold near 40% differs across historical HOLC grades at 60–90 metre scales. Its proposed baselines are linear OLS and an additive canopy/HOLC model. Inputs include DOI 10.1073/pnas.1817561116, 10.1038/s42949-021-00022-0 and 10.3390/cli8010012. These are retrieved metadata references, not proof that they support every generated statement.

Manual engineering assessment: worth inspecting as a hypothesis, not a recommendation to execute. Air temperature versus Landsat surface temperature is a construct mismatch; fine-scale buffer precision may exceed available thermal resolution; imperviousness is a confounder; no dataset access is verified; and the claimed gap is inferred from abstracts rather than established by systematic review. The generated claim that the team lacks a heat-equity topic is also unsupported by the synthetic capability description. Candidate novelty/publication value remains unknown.

A's rejected raw candidates included a HOLC-stratified canopy threshold study and a Guangzhou/US cross-city replication. C's raw extension candidate similarly proposed a threshold comparison. This overlap provides no evidence of improved opportunity diversity. Full successful result, public bibliographic snapshots and failure records are in `pilot-public-evidence.json`; unsuccessful intermediate model outputs remain in the local audit ledger.

The independent Pro reviewer timed out: **zero completed blind reviews**, no valid quality score or reviewer-disagreement statistic. Do not substitute engineering observations for completed independent review.

Improvement actually exercised: concise mandatory-field instructions yielded a schema-valid B result after the first missing-field failure. A/C did not complete after the change. Added targeted prior-art searches and stronger revision checks are implemented in revision 2 but **not live-validated**, because provider errors persisted. Flood holdout was not run or used for optimization.

## Cumulative usage

19 attempted model requests; 23,322 observed input tokens and 4,737 observed output tokens. Nine attempts lack complete usage, including interrupted calls; they retain full reservations. Conservative peak-price estimate including unknown reservations: **CNY 0.8201**, below the authorized CNY 10 / 60-request ceiling. This is not the provider invoice. Provider errors, not budget exhaustion, caused the stop.

Answer to the central question: **there is currently no evidence that the new system produces more valuable topics than either baseline**. Only B completed end to end in this pilot. A full paired experiment and independent assessment must succeed before making a stronger claim.

## Conservative follow-up: reader contract

Removed the global "every list at most three items" instruction, which contradicted the five-paper reader contract. Kept candidate-count restrictions at generation only. A now receives the original baseline prompts without transport-added modifications.

One real Flash call on the unchanged heat development bibliography returned all five expected IDs and passed the existing reader validator. The abstract-free paper remained metadata-only. This is a completeness check, not a paired scientific-quality experiment: no measured 60%-to-100% improvement is claimed, and no new topic or blind review was generated. The 3/5 figure is only the logical maximum if the old instruction were obeyed.

This call used 2,110 input / 513 output tokens, estimated CNY 0.008324. Updated cumulative totals: **20 requests, 25,432 observed input / 5,250 observed output tokens; CNY 0.828424 including full reservations for nine unknown-usage attempts**. Current publication task makes no additional paid calls.
