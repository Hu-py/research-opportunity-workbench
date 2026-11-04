# CUSP dataset register: private metadata only

The initial source is an **internal** spreadsheet, \`CUSP数据登记.xlsx\`,
containing a cross-domain research-data inventory. Its contents MUST NOT be
committed to this repository, its build logs, Vercel public routes or GitHub
Action artifacts. Only schemas and import logic belong in GitHub.

## Schema and refresh

\`cusp_datasets\` stores the 11 existing Excel columns plus sensitivity,
a curator note, version and update timestamp. \`cusp_dataset_revisions\`
retains each revision's structured metadata; \`cusp_import_runs\` records
the import count and source.

- Primary identifier is a normalized hash of each dataset NAME, not of its
  file bytes. Re-uploading identical Excel data is a no-op; changed rows
  update in place with an auditable revision. New names are new datasets.
- The raw XLSX binary is handled only in memory while the authenticated admin
  makes a request through Vercel's API proxy to FastAPI. It is NOT stored in
  PostgreSQL. The backend only records worksheet metadata.
- Existing non-CUSP user-entered directory metadata still lives in the
  separate \`team_data_assets\` table and remains available below the CUSP
  catalog on the Data Assets page.
- Registered in the F-drive column ≠ accessible on this cloud service.
  Empty backup column = unknown, **not** confirmed.
- Access to import/edit requires team admin credentials. Team viewers cannot
  read detailed metadata for records marked restricted.
- Once a person saves edits, other logged-in users see them on refresh
  (page refreshes every 30 seconds). This is NOT automatic watching of an
  F-drive, shared folder, or Dropbox/OneDrive/Drive spreadsheet.
- To enable true file-system-driven sync, set up a connector with permission
  to read the actual private inventory and implement pull changes, review,
  conflict handling and webhooks or periodic polling. Do not infer such access
  from a column's checkmark.

## Initial private environment bootstrap

A ONE-TIME startup migration enables initial data population without opening
PostgreSQL's external access or sharing an admin password.

1. Serialize the reviewed 28 rows to JSON using the exact 11 Chinese headers.
2. zlib-compress the JSON and URL-safe-base64 encode it; set that value as a
   temporary \`CUSP_DATA_BOOTSTRAP_ZB64\` in the Render API Environment.
3. Deployment starts, imports/updates rows by stable ID and logs *counts only*:
   \`CUSP metadata bootstrap: N new, N updated, N unchanged\`.
4. **Immediately delete** the temporary env variable (or set empty) and
   redeploy. Data stay in PostgreSQL with revision history.

The private payload must never be pasted into code, GitHub, CI, browser logs
or sent to a publicly accessible URL. Manual XLSX upload in the
authenticated dashboard is preferred for subsequent updates.

## Evidence-aware selection

\`/api/cusp/opportunities\` returns candidate research questions based on
explicit **existing dataset combinations**, with matched data IDs and
critical validation requirements. It uses no LLM key. The inference is
not a causal study, not proof of feasibility, not a novelty claim and
does not imply raw files have been read. Exact data permission, coordinate
systems, matching sampling periods, accuracy and privacy protections must
be verified before downstream agent analysis.

Some catalog entries describe trajectories, child-health data or identifiable
social-media activity. These are marked restricted by default. Do not ingest
row-level personal information into the current free database or a public
GitHub repo. Obtain appropriate authorization before accessing samples.

## Persistence

The test PostgreSQL plan expires December 4, 2026, has no managed backups
and must not be the only copy of the team's research inventory. Preserve
the source spreadsheet offline and migrate to durable backed-up storage
before relying on continuous operations.
