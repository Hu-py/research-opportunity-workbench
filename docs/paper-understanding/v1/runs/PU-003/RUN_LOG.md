# Execution log — 2026-11-07

1. Fast-forwarded feat/topic-advisor from cc175ea to upstream 1d9599d (five user-provided exemplar files). Original ledger reconciled: 33 calls / CNY 1.073446.
2. Nineteen public-source HTTP attempts logged separately; accepted Crossref/OpenAlex metadata only. User supplied 18,303,003-byte, 11-page original PDF. pdftotext yielded only form feeds. pdftoppm at 170 dpi + Tesseract eng produced all 11 OCR pages. Initial unrestricted OCR threading was slow and terminated; bounded two-process/one-thread OCR completed. No cloud OCR service or OCR API fee.
3. `python -m scripts.paper_understanding_experiment freeze`: saved prompt and evidence/case hashes before model runs.
4. `... R0`: one real Flash request, completed reader schema; `... R1`: one real Flash request, completed reader schema.
5. `... R2`: one real Flash request; API succeeded, validation failed: `Eight nonempty modules required`. Raw extra module and wrong-page references retained.
6. Recorded REPAIR_HYPOTHESIS.md, added optional attribution prompt revision; `... R2 --revision 2`: one real Flash request; API succeeded, validation failed: `Quote absent from source`. No schema relaxation or silent correction.
7. `python -m scripts.review_paper_understanding`: one fresh Pro request, completed review. Review mistakes documented, not used as proof of success.
8. Offline citation audit exported all mismatches without altering original results. Re-ran R0, R1 and R2 revision 2 commands: each printed `Existing checkpoint; no new call`; cumulative attempts remained 38.
9. `.venv/bin/python -m pytest -q`: **120 passed**, one existing Starlette deprecation warning, 30.64 seconds. Focused reading/registry/advisor tests: **19 passed**, same warning. `git diff --check`: passed. `git diff --exit-code HEAD -- backend/topic_advisor.py`: passed (S1 source unchanged from starting branch).
10. Stopped paid work: 5 requests this round, 86,470 input / 6,122 output tokens, estimated CNY 0.360685. Original cumulative ledger: 38 requests / conservative CNY 1.434131, including nine historical unknown-usage reservations. No merge/deployment/production migration.

Exact request timestamps and call IDs are in usage.json; exact full-text inputs are in the original local SQLite ledger, not this public log. Failed R2 orchestration is distinct from API service failure. Neither raw R2 result is an approved knowledge record or recommendation input.
