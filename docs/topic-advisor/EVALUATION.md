# Live evaluation

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
