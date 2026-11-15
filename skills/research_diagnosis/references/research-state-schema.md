# SC05 Research State and Diagnosis Schema v0.1

Each run is associated with an authenticated task owner and a versioned SHA256 input snapshot. Scientific documents may remain private; only safe, consented excerpts enter model prompts.

## Input: neutral research state

```json
{
  "research_question": "The study's actual research question, not a desired answer",
  "study_unit": "Road / person / neighborhood / city / other; distinguish observational and split units",
  "observations": [
    {
      "fact_id": "F001",
      "fact_type": "objective",
      "statement": "A plain claim transcribed from the original source",
      "source_id": "manuscript-v3",
      "section": "Methods",
      "verbatim_excerpt": "An exact, continuous excerpt from the source section",
      "evidence_origin": "author_reported"
    }
  ],
  "unknowns": ["Information not documented; no inference of values"]
}
```

Allowed fact_type: `objective`, `data`, `method`, `evaluation`, `result`, `limitation`. Allowed evidence_origin: `author_reported`, `independently_computed`. If a source section is unavailable, use `unknowns`; do not fabricate `verbatim_excerpt`. The source excerpt must be validated against the actual section text before accepting it.

## Withheld from initial diagnostic prompt

- The researcher's planned next paper, including its scope, study region or data design
- The expected "correct" bottleneck checklist
- The author's proposed future research direction or recommendations in the Discussion
- Earlier assistant suggestions, labels and coaching summaries

This information goes into a separate evaluator-only file and must never be interpolated into the diagnosis prompt. Do not withhold actual experimental negative results or methods merely to make a benchmark harder.

## Output: independent diagnosis

```json
{
  "study_reconstruction": {
    "question": "...",
    "evidence_fact_ids": ["F001"],
    "claimed_contribution": "...",
    "what_is_actually_tested": "..."
  },
  "diagnoses": [
    {
      "id": "D01",
      "issue_class": "validation",
      "problem": "...",
      "fact_ids": ["F001"],
      "epistemic_status": "hypothesis",
      "rival_explanations": ["..."],
      "verification_tests": ["..."],
      "research_consequence": "...",
      "confidence": "medium"
    }
  ],
  "open_questions": ["..."]
}
```

Allowed issue_class: `coverage`, `measurement`, `validation`, `method`, `interpretation`, `identifiability`, `resource`, `other`. Allowed epistemic_status: `observed`, `hypothesis`, `unknown`. Allowed confidence: `low`, `medium`, `high`. Confidence is an ordinal diagnostic self-assessment, **not** a calibrated probability.

Validation rules:
- Every cited fact_id must appear in the frozen input snapshot.
- Observed diagnoses require `fact_ids`; unknown diagnoses may cite none.
- Every hypothesis requires at least one rival explanation and one falsifiable verification test.
- A completed diagnosis never by itself proves novelty, model validity or causal claims.
- An empty diagnoses list is valid if the data do not support specific failure diagnoses.

## Stage-2 evidence requests

Each evidence question should specify:
- `diagnosis_ids` that motivated it;
- `theoretical_assumption` to check;
- `search_query` and source scope;
- `supporting_or_falsifying` evidence type;
- `paper_ids` and original DOI/OpenAlex IDs once retrieved;
- `transfer_status`: directly tested / conditional analogy / unsupported / conflicting;
- `what_would_change_decision`.

Journal exploration is **not** equivalent to silently expanding the formally approved journal directory.

## Stage-3 candidate study paths

Each plan should be `change_kind: model|data|evaluation|research_question` and specify:
- unresolved issue(s) with IDs,
- reason the change can address them,
- prerequisites and data availability,
- minimum test and metrics,
- failure/stop condition,
- prior-work evidence and scientific limitations,
- review verdict: `test|hold|reject`.

Zero candidates is acceptable; all candidates can be held or rejected.

## Generated report

Markdown report contains original source references, evidence/assumption labels, and the research route decision tree; no made-up numerical results and no claims of full-text review when only summaries are available.
