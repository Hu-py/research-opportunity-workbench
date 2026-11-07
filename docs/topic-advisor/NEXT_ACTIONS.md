# Recovery checkpoint — 2026-11-07

Conservative Codex policy: account quota cannot be measured here; one bottleneck and one bounded validation per round, then stop. Do not claim enforcement of a precise 5% limit.

Latest bottleneck: transport injected a three-item limit into every list, conflicting with the reader's five-paper completeness requirement. Removed that global instruction and restricted generation limits to topic generation. Original A prompts are now passed unchanged. No claim that this caused previous HTTP 503/timeouts.

One live development-case probe completed: 5/5 original paper IDs returned, missing abstract correctly labelled metadata-only. The old constraint's maximum coverage if obeyed was 3/5, a logical bound, NOT a measured paired baseline. This verifies completeness, not scientific quality or improved A/B/C performance. No holdout accessed.

Budget after this probe: 20 cumulative attempted requests; conservative CNY 0.828424 including unknown reservations. Probe usage: 2,110 input + 513 output tokens; CNY 0.008324 peak-price estimate. Nine earlier requests still lack full usage. No new paid calls authorized in the current publication/review task.

Next best research task after independent review: compare a single advisor followed by one evidence-grounded critic against the existing B candidate, focusing on air-temperature versus land-surface-temperature construct validity. Freeze evidence, predefine failure criteria and cap calls before starting. Do not rerun all agents merely because API access recovered.

Before further calls, re-read the actual `data/topic-advisor/experiments.db` ledger and confirm it has at least the recorded 20 attempts. If the ledger is absent or cannot reconcile with committed records, make no paid calls until accounting is recovered. Never initialize a new ledger to bypass cumulative limits.
