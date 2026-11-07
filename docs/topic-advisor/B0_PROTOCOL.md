# B0 v1 — general scientific judgment smoke evaluation

Frozen before model calls: `scripts/research_b0.py` PROMPT, METRICS, source revision, row indices 0–1, first fake/model negative, alternating candidate order, Pro model and 2000-output-token cap. No prompt changes after observing results. Ten other rows remain unused; do not read their content during optimization. This is a two-case development pilot, not a generalization estimate.

Source: ResearchBench Authors, *ResearchBench: Benchmarking LLMs in Scientific Discovery via Inspiration-Based Task Decomposition*, https://arxiv.org/abs/2503.21248. Snapshot commit `03873e075c8f33544adeac37745fdc14f0c16c50`; ranking.jsonl SHA256 `e67270dfabd020e19ea358c87d56eac3ebd1a54eee8b7853aa2f8943f18d9615`. Derived local adaptation is non-commercial research under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/); original publisher restrictions still apply. Source texts stay in ignored storage. Public outputs retain attribution and DOI references; this grant does not imply unrestricted commercial use or rights to source publications.

Inputs: research question and three anonymously labelled candidate hypotheses. No gold label, DOI, publication venue, team profile or personal context is sent. A positive benchmark reference and two benchmark negative variants are supplied; these labels are reference judgments, not verified scientific truth. Negative cases may be plausible, and published-reference text can be generic.

Output: candidate-specific reasons and five 0–2 rubric dimensions (importance, problem origin, knowledge increment, evidence reliability, avoidance of unmotivated technique stacking), one preference or abstention, one proposed falsifiable question, and missing verification. Scores are model assessments, not independent value measurements. No citations may be invented and unsupported is not synonymous with false.

Objective checks: exactly one review per label; scores are bounded integers; nonempty reasons/question; explicit missing-verification list. Missing/duplicate labels or invalid JSON are schema failures, never a default winning candidate. Report reference agreement separately from critical reading. This adapts official two-way/both-order ranking to three-way single-call B0; it is **not an official ResearchBench score or reproduction**. Two samples and one ordering per sample cannot establish order robustness or model superiority. Pretraining contamination is unknown.

Version comparison: retain identical source bytes, row selection, label order and inputs; changing prompt/model changes the checkpoint hash. Never replace prior outputs. Pair by sample ID and source checksum. Original urban A/B/C experiments are not directly comparable with this new general-task protocol.

Recovery: model ledger reservation precedes HTTP. B0 stores input, config and `started` before execution, then completed/error records. Re-running completed cases makes zero calls. Failed or uncertain `started` cases are skipped by default; explicit `--retry-failed` is required. If model output was durably cached before interruption, explicit retry can reuse that exact response. If remote completion is unknown, retain full old reservation and count any retry as new. Process interruption cannot guarantee exactly-once remote billing.

Errors: acquisition/checksum (stop before inference); missing/mismatched historical ledger (stop); provider/budget errors (record sanitized class, stop current round); JSON/schema errors (retain response, no fabricated score); interruption (`started`, outcome unknown); scientific defects (record separately even when schema passes). Existing caller enforces 90-second deadline, one concurrent request, finite output and CNY 10 / 60 cumulative attempted-call caps. This round: at most two new calls, no retries.

Reproduce from repository root with the existing reconciled ledger:
```
.venv/bin/python -m scripts.research_b0
.venv/bin/python -m pytest -q tests/test_research_b0.py tests/test_topic_advisor.py tests/test_topic_prompt_contract.py
```
First command is resumable and may call the API only for unseen cases; it refuses a missing or undercounted historical ledger. Do not create a fresh ledger to rerun this task. `b0-v1-results.json` is the public result/usage record; full inputs/configuration remain in local `b0_attempt` records and pinned source.
