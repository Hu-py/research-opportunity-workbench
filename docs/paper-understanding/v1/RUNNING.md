# Running and audit recovery

Use the existing repository virtualenv and original ledger. No new database or credential configuration is needed. Requires system pdftotext, pdftoppm and tesseract (eng). The PDF is user supplied; it is not committed.

```bash
.venv/bin/python -m scripts.prepare_paper_evidence /path/to/authorized.pdf --doi 10.1016/j.cities.2022.103597
# Review page OCR, metadata and source rights before freezing a NEW experiment.
.venv/bin/python -m scripts.paper_understanding_experiment freeze
.venv/bin/python -m scripts.paper_understanding_experiment R0
.venv/bin/python -m scripts.paper_understanding_experiment R1
.venv/bin/python -m scripts.paper_understanding_experiment R2
.venv/bin/python -m scripts.paper_understanding_experiment R2 --revision 2
.venv/bin/python -m scripts.review_paper_understanding
.venv/bin/python -m scripts.paper_understanding_experiment export
```

The committed freeze must not be overwritten. The preparation utility creates a NEW evidence version (acquisition timestamps differ): it is not an exact replay of the existing hash. For replay use preserved `data/paper-understanding/PU-003/evidence.json`; otherwise retain existing results and establish a separately named, explicitly versioned experiment before paid work. Never delete ledger entries or old outputs to enable a replay. Missing/unreconciled original ledger means no paid calls.

Completed and failed stages are skipped by default. `--retry-failed` explicitly retries an unchanged failed stage; successful raw model responses are exact cached, so a validation-only failure need not incur another request. Original started requests are durable before HTTP, and failures retain budget reservations. This script has a 40-total-attempt stop in addition to the original ledger's 60-request / CNY 10 limit. Current checkpoint is 38 attempts / conservative CNY 1.434131; do not assume a historical lower floor establishes the remaining balance.

R0/R1 use the old reader contract; R2 default revision 1 is retained. Revision 2 is an experimental failed repair and is not promoted. Failures are saved and do not feed S1 recommendations. The optional authenticated GET `/api/topic-advisor/paper-understanding/examples?target_doi=...` exposes versioned development cards and excludes the target's own example; it performs no paid call. CLI uses existing ExperimentModel/model gateway and TopicArtifact storage. PDF preparation uses the existing scientific tool registry for DOI verification.

## Public outputs

- [Frozen baseline prompt, evidence/case hashes](runs/PU-003/freeze.json)
- [R0 full output](runs/PU-003/R0-eadfd727b7ce.json)
- [R1 full output](runs/PU-003/R1-1d8fb97ddecb.json)
- [R2 v1 full failed output and quote audit](runs/PU-003/R2-9eb9abbbc9ba.json)
- [R2 v2 full failed output and quote audit](runs/PU-003/R2-a8fc686bcb96.json)
- [Independent review, including errors](runs/PU-003/independent-review.json)
- [Usage, call IDs/timestamps and raw model results](runs/PU-003/usage.json)

Exact original inputs are local in `data/topic-advisor/experiments.db`, kinds `paper_reading_request`, `paper_reading`, and `paper_review_request`. PDFs/OCR/pages are local under the user attachment path and ignored `data/paper-understanding/PU-003/`. Public output exports omit full-text payloads. Model prompts, source hash, module hash, generation model, token cap, timestamp and request identity are preserved. API credential values are never recorded.

## Verification

`.venv/bin/python -m pytest -q` runs the existing regression suite plus new case/status/citation checks. Quote checks enforce whitespace-normalized literal source matching, not entailment or originality. `git diff --check` checks patch formatting. Byte comparison of backend/topic_advisor.py against the baseline confirms S1 recommendation logic was not modified.
