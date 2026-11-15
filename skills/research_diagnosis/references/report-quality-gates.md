# SC05 report quality gates (paper-only)

## Required sections
1. **Source and scope**: publication title, DOI where known, scope of materials, whether claims are from authors, LLM or outside papers, PDF SHA and analysis date.
2. **Research reconstruction**: stated problem, actual empirical question/units, baseline, methods and observed contribution; specify what the paper does **not** test.
3. **Method & data chain**: a table: observed input → preprocessing → metric/formula → model/simulation → evaluation output → related scientific claim, with source page IDs. Distinguish observed, derived, simulated, assumed. Explicitly analyze critical mathematical or measurement dependencies.
4. **Two-track output**: a short quality/rigor review scoped to the original research question, and a separate scientific-frontier analysis from positive observations, emergent mechanisms and systemic contradictions. Only the frontier track is eligible for next-paper routes.
5. **Evidence-gap diagnosis**: evidence-linked candidate scientific gaps, alternative explanations, minimum checks/falsification, severity and scope; no claim that inferred bias or leakage is proven.
6. **Targeted literature review**: diagnosis-derived search queries and original papers (DOIs/links, years, method, task, evidence level, overlap, transfer assumptions). Seek negative results and close competitors. Include limitations of abstract-only reading.
7. **Research routes**: not interchangeable model names. Each candidate needs a distinct answerable question, scientific delta versus prior paper, credible existing literature comparison, minimum data and accessible fallback, baseline, design/evaluation scheme, possible negative outcome, stop criteria, and verdict.
8. **Practical decision**: rank or reject options conditionally; which single observation/experiment would most reduce uncertainty.
9. **Audit and limits**: input hash, fact IDs, citations, stages/tokens, search failures, human review status, no unsupported novelty guarantee.

## Hard validation gates (all required)
- Source references must point to a real page and quote verified in the uploaded PDF.
- Any asserted method or result must be attributed to a source fact; paper-only study may *propose* computations but cannot claim independent re-estimation.
- Do not infer that a metric constructed from another metric has independent forecasting value without independent outcomes and temporally valid tests.
- External paper IDs and URLs must be verified from actual search results. Abstract-derived details must match an exact abstract excerpt. No inventions to make a comparison seem comprehensive.
- Distinguish a publication's author-reported limitations from diagnosis independently inferred by the model; original discussion's future-work remarks cannot enter an initial blind evaluation.
- Negative evidence (method failure, adverse scenario, lack of independent tests) is as important as claimed positive result.
- A quality assurance check is not a publishable scientific opportunity. The review must not punish a paper merely because it did not answer an *additional* question that was outside its intended scope.
- The next-paper pool must contain an independently formulated new scientific question, an observable motivating phenomenon, an untested mechanism, a complete narrative and a discriminating experiment. Low-effort model tweaks or sensitivity-only experiments must not be recommended as stand-alone research stories.
- Output **test / hold / reject** instead of automatically filling a fixed list of "three innovations". Rejection is a valid scientific conclusion.
- If external literature access or data are insufficient, set an explicit limitation, not a pretend validated novelty score.
- The final report should be substantive: evidence-specific, method-aware and decision-useful. Do not inflate word count with generic filler.

## Quality rubric, 0–5 per category
| Category | 0 | 3 | 5 |
|---|---|---|---|
| Source faithfulness | Invented claims | Mostly source aligned | Every substantive empirical claim traceable |
| Method-data understanding | Algorithm-name list | Some formulas understood | Correct measurement/simulation/assumption chain |
| Independent bottleneck discovery | Repeats author Future Work | Several grounded issues | Discovers consequential overlooked evidence constraints |
| Theory/literature depth | No real external work | Real papers, surface links | Close methods, counterexamples and transfer conditions |
| Research redesign | Rename / extend old study | Distinct plausible problems | Independent, falsifiable and clearly differentiated advances |
| Feasibility and critique | Promises success | Basic data/risks | Strong baselines, stop tests, realistic missing-data alternatives |

Rater must never see the known "correct" routes before scoring blind Stage 1. This rubric is a quality standard, not a hard-coded answer key. Any <3 in provenance or fabricated citation is a hard failure regardless of overall score.

## Test-case control
Use the published Shen et al. To–Through metro case for integration testing but do not bake its conclusions, the four previously discussed next-paper candidates, or the human R0 report into prompts. Preserve those separately as *evaluator-only* materials. Passing a schema test is **not** passing a scientific-quality test. Model output still needs independent human review.
