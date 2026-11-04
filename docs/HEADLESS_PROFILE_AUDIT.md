# 研究画像无前端验收 / Headless Research Portrait Audit

## Scope

Read **the live Research Atlas PostgreSQL database** rather than conversational memories. Source tables: `profiles` (existing registered goals), `team_achievements` (verified title/year/tags), `cusp_datasets` (non-restricted **metadata** only), manually reviewed papers, and confirmed research line relations.

CLI: `python -m backend.profile_audit` with authorized `DATABASE_URL` set to the backend database (prints JSON). The CLI never invokes an LLM or writes research files.

## Render without Vercel / without external PostgreSQL ingress

Because the free Render Postgres blocks external IP connections, running this script from a laptop requires network access. Instead, temporarily set `PROFILE_AUDIT_ON_STARTUP=1` **on the Render backend service**, and deploy/restart that backend. The already-authorized backend queries Postgres over its internal connection and logs named JSON records:

- `PROFILE_AUDIT_META`: live counts, dataset-category counts, research-tag frequencies and current registered line names
- `PROFILE_AUDIT_ACHIEVEMENT`: actual verified-title/year/type/tag/ID records
- `PROFILE_AUDIT_DATASET`: non-restricted data-attribute name, format, period, coverage and source ID only
- `PROFILE_AUDIT_LINE`: each generated draft line, evidence refs, matched works/metadata and evidence status
- `PROFILE_AUDIT_COMPLETE`: confirmation of an end-to-end read and source audit

Turn the variable **OFF immediately after examining the report** so ordinary restarts remain log-quiet. Do not copy protected logs to a public repo; no source files, custodians or protected descriptions are included. Keeping PostgreSQL's IP allowlist closed is recommended.

## What success means

1. Real database read and row counts verified.
2. Existing formal profile and verified-achievement tags clustered (without overriding official version).
3. Non-restricted asset metadata matched by cited record ID; unverified matching is labeled as such.
4. Structural and citation validation succeeds. Private dataset names excluded.
5. A reviewable draft exists in Postgres; **no automatic publication**.
6. No API keys or pay-per-token model calls are used.

## What this does NOT prove

- It is **rule-based evidence grouping**, not DeepSeek academic reasoning.
- Theme frequency is not evidence of theoretical novelty or method performance.
- Dataset metadata does not prove access, temporal alignment, fields, or data quality.
- A real paid-model integration requires an administrator-supplied DeepSeek Key; separate offline mock tests verify schema, draft approvals, no hallucinated refs and persistence.

After inspecting this dry run, the next scientific step is to selectively approve evidence links, review abstracts or full text where authorized, then run LLM research-profile synthesis via the existing admin API. Store that result as another review draft, not as a silent update to the official profile.
