# R6.7-B · Real-DOI development corpus, review protocol and evidence limits

Date: 2026-11-19. Category: ◇03 independent evidence-quality engineering.
This is **development** of the literature-evidence classifier, not an
independent holdout evaluation and **not** a paid research-report experiment.

| Problem | Method | Activity | Status | Preliminary result | Next | Audit |
|---|---|---|---|---|---|---|
| Need real papers beyond synthetic tests, while R6.6's 15 exposed DOI items can no longer act as unseen holdout | Collect newly source-verified publisher DOIs, freeze AI-assisted provisional labels, measure existing R6.7 code on live OpenAlex abstracts | 32 DOI cases: 9 direct domain neighbors, 5 domain reviews/context, 9 possible method transfers, 9 deceptive lexical negatives | One-shot CI/real metadata probe; no DeepSeek | Initial misclassification is diagnostic, not gold accuracy or scientific innovation | Human adjudication, then new unseen test and explicitly authorized A/B | benchmarks/sc05_r67_real_dev_v01.json, scripts/sc05_r67_real_dev_eval.py |

## 1. Corpora firewall

- Development manifest: benchmarks/sc05_r67_real_dev_v01.json.
- Historical exposed R6.6 set: benchmarks/sc05_r66_silver_set_v01.json, **strictly excluded** via exact DOI comparison in evaluation code.
- Development context: urban rail transit disruptions, passenger-flow redistribution, resilience and cascade mechanisms; this is not a new source-paper DeepSeek case and is not a fresh held-out scientific evaluation.
- All records have publisher-discoverable DOI/title links. No guessed DOI, raw abstract, or publisher PDF stored in GitHub.
- All labels are **AI-assisted provisional, not gold**: initial classifications are the assistant's screening interpretation of actual publisher pages. They do **not** represent a second independent human reviewer, consensus or verified transport-method equivalence.
- The method_transfer category expresses plausible algorithmic inspiration, not successful transfer. lexical_negative means no verified direct urban-rail mechanism or demonstrable actionable transfer in inspected evidence, not proof such transfer is impossible.
- Title/abstract screening can miss methods in full texts; unresolved cases are escalated for review.

## 2. What the run actually measures

A reproducible script fetches OpenAlex entries by exact DOI, reconstructs abstracts in memory and applies the **pre-existing R6.7 source-domain gate and separate method-lead selector**:

- domain_candidate: passed coarse transport-domain matching; **not automatically a scientific prior**;
- unapproved_method_lead: failed domain gate but contains a specific described computational method, still awaiting human check;
- quarantined: neither domain candidate nor supported method clue;
- provider_unresolved: OpenAlex DOI missing or abstract unavailable.

The script reports coverage, provisional domain precision/recall, method-lead recall, method incorrectly landing in domain, lexical-negative leakage and per-DOI review queues.

It does **not** measure full search coverage: inputs are curated DOI-addressed papers, not papers returned by a subject query. It does **not** test semantic closest-paper accuracy, feasibility of transfer, blind paper originality or quality of a new research agenda. Missing abstracts are unresolved, not negatives.

The manifest was assembled after R6.7 code was already implemented. This set is suitable for engineering diagnostics and tuning, **not** a clean unseen evaluation of that code's external validity.

## 3. Cost, privacy and provenance

- One-shot workflow: .github/workflows/sc05-r67-real-dev.yml, triggered only when the initial manifest is added or explicitly dispatched. Doc updates do not repeat external DOI calls.
- Hard cap: 38 public OpenAlex HTTP requests for 32 DOI items, including transient retries. No paid DeepSeek calls; no OpenAlex secret passed to GitHub.
- Results artifact only: DOI, paper title, year, URL, SHA256 of abstract, predicted lane, minimal error and provisional comparison metrics. No full paper or raw abstract.
- Public API throttling/incomplete metadata yields partial/blocked, not automatic acceptance.

## 4. Independent human adjudication protocol

**Reviewer A (initial AI-assisted labels)** and **Reviewer B (actual human, not yet assigned)** are different roles. The assistant must never self-identify as another independent reviewer or invent expert votes.

For each DOI, *before seeing algorithm predictions*, a human reviewer examines publisher abstract and, if necessary, methods. Record:
1. Research object and scope: same_domain=yes/no/uncertain.
2. Concrete transport mechanism: direct/indirect/counterexample/none/uncertain, with evidence.
3. Actual algorithm input/output, not just a general model name.
4. Target urban-transit input/output mapping, assumptions and falsification test if transfer is plausible.
5. Publication chronology and whether the paper predates the scientific question being compared.
6. Decision domain_near / domain_context / method_transfer / lexical_negative / ambiguous, or unresolved.
7. Evidence locator, review date and short reviewer-written rationale; no copyrighted long quotations.

The blank review sheet is benchmarks/sc05_r67_reviewer_B_blank_v01.json. Once a real human supplies annotations, preserve their authored responses in a *new* file. Only then adjudicate consensus/disagreements; never overwrite AI provisional labels.

## 5. Completion criteria

- [ ] Offline CI and safe metadata check complete.
- [ ] Exact coverage and item-level disagreements published, every rate marked provisional.
- [ ] Human second reviewer authored labels **or** unresolved/pending status shown; never simulated.
- [ ] Exposed R6.6 DOI set not reused and no model spending.
- [ ] If developers tune the classifier on this development set, freeze a fresh unseen holdout and new code/policy SHA before claiming improvements.
- [ ] Owner MCP read/write recovery separately required for PostgreSQL ledger sync (Issue #113); GitHub is audit fallback.

Final goal is to compare scientific-route quality on a genuinely new source paper, with separate fresh paid authorization after human review and clean experiment registration. DOI retrieval alone is never that goal.
