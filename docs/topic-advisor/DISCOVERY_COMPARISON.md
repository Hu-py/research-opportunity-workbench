# Actual advisor discovery comparison — 2026-11-07

## Finding and hypothesis
S0's three lenses converged on variations of a 40% canopy / historical redlining interaction. Its critic requested evidence or deferred candidates, yet final synthesis recommended a similar topic. A transfer-path candidate invented prior team work despite an empty achievements input. The main actionable defect was that evidence-grounded problem formulation and critic decisions did not constrain recommendation.

Hypothesis fixed before S1: replacing three parallel lenses and unconstrained final rewriting with source-linked problem discovery, competing explanations, candidate generation and a binding critic gate will reduce unsupported recommendations and potentially improve knowledge increment. Failure criterion: independent review does not prefer S1, or source/causal errors persist. This criterion was met: scientific-quality superiority was NOT demonstrated.

## Frozen conditions
S0 source and prompts: commit 5032872eaeec2e370bb9d2b18ad813430addea4e, C revision 1 (five calls). This is the existing no-extra-retrieval workflow; revision 2 targeted retrieval was not evaluated. Source SHA and exact context in discovery-comparison.json.
Context SHA256: 0ec89be342ac6f7e8e4c3b98503349d7507da6522cbc02a2bc249fdd8d550ae7.
One public urban-heat development case; five existing OpenAlex records, no team achievements, no verified dataset access. No hidden cases opened. No new search requests: all arms received identical frozen evidence. This tests reasoning on supplied abstracts, not full-literature novelty or active retrieval. Papers include DOI 10.1073/pnas.1817561116 (air temperature), 10.3390/cli8010012 (surface temperature), and 10.1038/s42949-021-00022-0 (HOLC/tree canopy). One of five records has no abstract.
B0 and S0 were run before editing the advisor. All generation used deepseek-flash. Here B0 means the existing one-call advisor, not the prior ResearchBench ranking baseline or a Pro-quality upper bound. Call budgets differ and are reported; this is not a cost-matched efficacy trial.

## Real outputs
| Arm | Candidate / decision | Calls | Estimated CNY |
|---|---|---:|---:|
| B0 | 树冠覆盖与城市热暴露不平等的尺度依赖阈值检验; recommended | 1 | 0.007090 |
| S0 | 树冠降温阈值的HOLC等级交互：阈值公平假说; recommended despite unresolved review | 5 | 0.044746 |
| S1 | 树冠独立降温效应与不透水面通道的配对分解; withheld, no final recommendation | 3 | 0.028936 |
| Two independent reviewer calls | fresh Pro contexts, concealed arm names | 2 | 0.125586 |

B0/S0 ask whether the canopy threshold moderates historical heat inequality, transferring a single-city air-temperature observation into surface-temperature comparisons. S1 instead asks whether canopy or co-varying impervious surfaces/building form explains the disparity. Its problem record has literal source quotations, explicit inferred-gap status, rival predictions and a distinguishing observation. However, it still says prior work did not separate contributions when the supplied abstract says it examined them. Partial R² cannot establish intervention mechanisms. S1's critic identified outcome/time-window ambiguity, confounding and unavailable matching data, and the deterministic gate withheld the candidate.

## Independent evidence and limitations
Two fresh deepseek-v4-pro reviews, concealed order X0=S1, X1=B0, X2=S0, saw the same sources and final candidates (including S1's explicitly un-recommended candidate). They preferred “tie” and “none”; neither marked any candidate worth human review. Their ratings were identical across arms within each review, but differed between reviewers. First reviewer gave S1 clearer importance/increment; second challenged its unsupported novelty claim.

These are independent calls, not independent human or model-family validation. S1's richer nested problem record may reveal its format. The first review scored anti-stitching highly while describing S0 as stitching; both sometimes demanded evidence for the proposed hypothesis itself, rather than evidence that the uncertainty is worth resolving. Do not treat these ratings as reliable scientific-value measurements. Quote-level checks confirm source provenance, not entailment. The original abstract supports the confounding concern, but does not establish that the proposed question is new. No high-quality accepted recommendation was produced by S1; its false-negative rate is unknown.

Conclusion: retain the source/provenance contract and binding critic gate as workflow integrity improvements. There is no demonstrated improvement in valuable problem discovery over S0 or B0. Three paths were redundant in this case, which supports a simpler provisional implementation, not universal removal of exploration diversity.

## Implementation, failure and recovery
Existing backend/topic_advisor.py now routes default C revision 3 and explicit S1 through three stages. C revisions 1/2 remain available. Candidates must link to validated problems and preserve their source IDs. Only an explicit recommend with no unresolved concerns passes. No free-form final generation can override rejection.
The first S1 attempt failed after two successful API calls: the model placed problem_id at the response envelope. The adapter now accepts that only for exactly one candidate and an explicit known ID. Failure retained; retry reused two exact cached responses and made only the critic call. No repeated paid generation or judge-driven tuning occurred.
Run from repository root using .venv/bin/python -m scripts.topic_discovery_compare s1 or judge; completed stages are skipped. --retry-failed is explicit. Baseline refuses changed source; replay S0 only at its frozen commit with the same frozen context and reconciled existing ledger. Never create a new ledger to rerun.

## Accounting and checks
This round: 11 actual API requests, 31,762 input / 6,198 output tokens, estimated CNY 0.206358. All completed at API level; one orchestration attempt failed schema linkage and is retained.
Cumulative: 33/60 requests, conservative CNY 1.073446/10. Historical nine unknown-usage calls retain reservations; cumulative known tokens 58,706 input / 12,376 output are incomplete. Estimates use conservative configured peak rates, not a billing statement.
No new public API retrieval calls this round; evidence acquisition costs belong to earlier records. Codex quota cannot be read or capped at precisely 5%; one bounded cycle performed and paid work stopped.
Tests: .venv/bin/python -m pytest -q => 114 passed, one existing Starlette deprecation warning (29.31s). Targeted discovery/advisor/prompt tests: 12 passed. git diff --check passed.
Public audit: discovery-comparison.json includes evidence, frozen version, raw outputs, failed attempt, both reviews, model IDs, max token limits, request hashes and usage. No private inputs or credentials included.

## Next decision
Do not add agents. Next narrow hypothesis: requiring a claim-by-claim “prior work already explains / genuinely unresolved / not knowable from abstract” distinction may prevent fabricated gaps. First check accessible source text and have an independent human assess this failure and the gate's strictness. A later bounded paired run should use a fresh public development case and preserve an untouched test case; do not repeatedly tune this heat case. No automated source-code self-modification loop or background paid work was started.
