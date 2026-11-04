# Verified team research and data-assets workflow

## Scope and identity

**Tracked researcher:** 同济大学建筑与城市规划学院 沈尧 / Yao Shen, ORCID
`0000-0002-7261-4234`. This is **not** the unrelated authors with the
same English name in medicine, materials, etc.

- Official faculty publication and project list: https://caupzs.tongji.edu.cn/e3/c0/c19001a189376/page.htm
- University English profile: https://caup.tongji.edu.cn/caupen/e6/7e/c33465a321150/page.htm
- Publisher independently confirming ORCID and affiliation: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0212004
- More recent articles verified via publisher/journal pages and their DOI/URL; see
  `backend/data/shen_yao_verified.json`.

The first curated import contains **30 public publications/articles plus
6 public grants/projects**. Not all historical works may be listed. This is a
public academic bibliography, **not** a claim that the entire university's
research data has been collected.

## Data model

- `team_achievements` (separate from external `papers`) stores curated work
  with source URL, DOI, year, authors, theme tags, verification status.
  A title-normalized stable primary key makes startup seeding idempotent.
- `team_research_refresh_runs` stores each manual or scheduled OpenAlex scan
  and its scanned/inserted counts, status and error.
- `team_data_assets` stores directory **metadata only**, not actual files.
  Field dictionary, spatial/time coverage, data sensitivity and notes can be
  filled in later.

The LLM Research Agent has a read-only `get_team_research_history` tool;
it can see verified prior achievements when developing method-transfer ideas.

## Scheduled automatic update

Vercel Hobby Cron is configured in `frontend/vercel.json` for
`0 1 * * *`, nominally **09:00 Beijing time daily** (01:00 UTC).
Hobby scheduling is approximate within an hour; Vercel cron functions
are included in Hobby subject to function usage limits.

To enable it securely, both projects must contain the specified secret:

Vercel production environment:
- `CRON_SECRET`: a new independent random string; Vercel automatically
  sends it in the Cron request Authorization header
- `ATLAS_SYNC_SECRET`: second independent random string
- `BACKEND_URL` and `API_BEARER_TOKEN` as already deployed

Render FastAPI:
- `ATLAS_SYNC_SECRET`: **same value as Vercel**
- `API_BEARER_TOKEN` as already deployed

The public `/api/cron/team-research` endpoint verifies `CRON_SECRET`.
It then POSTs to the server-to-server Render endpoint
`/api/team-repository/refresh-scheduled`, which separately verifies both
the service bearer token and `ATLAS_SYNC_SECRET`. The Render endpoint
returns 202 and runs OpenAlex collection asynchronously in the same free API
process, so restarts and sleep can interrupt the scan. The team research
page shows last-run outcome and a manual refresh button.

### Publication identity and review gate

OpenAlex query is **scoped by the publisher-verified ORCID** and further
checks each returned authorship for the exact ORCID.
DOI/title upsert prevents duplicate imports. Only metadata from OpenAlex is
stored; no paywalled article content is downloaded.

**All automatically discovered works are inserted as status `review`**;
only a team admin can mark them `verified` or `rejected`.
A repeated scan does not flip a manual decision or overwrite a curated item.
This deliberately favors disambiguation and source quality over recall.

OpenAlex free API does not provide the exact paid `from_updated_date`
incremental filter. The script instead scans works published from 2022 onward
each day and deduplicates locally. This may miss older late-indexed papers
before 2022 or works without the verified ORCID and is not an exhaustive
publication sync. Admins can add these to the curated seed file through
reviewed GitHub changes.

## Metadata-only datasets and opportunity hypotheses

In the **研究数据资产** page, an admin pastes a **relative** folder/file listing.
Recognized extensions include CSV/Excel/GeoPackage/Shapefile/GeoJSON/Parquet/
GeoTIFF/NetCDF/HDF5/JSON. Unsupported, absolute and traversal paths are
ignored. No disk access and no raw file upload are performed.

Admins can expand each item with fields, spatial/temporal coverage, notes,
and sensitivity; the opportunity panel returns conservative, explainable
hypotheses grounded in directory name matching, with links to verified prior
research. These are *not* LLM-verified proposals and are *not* an assessment
of dataset quality, completeness, or scientific novelty.

For future expansion: check data licenses, sensitivity, schema validity,
sample values, join keys, coverage and sampling bias before claiming research
feasibility. Uploads or external data-storage integrations must be protected
and require data-governance approval.

## Free-tier limitations / persistence

Render Free PostgreSQL database created **2026-11-04** expires
**2026-12-04** and lacks automatic backups. The team should migrate to a
persistent database with backup/recovery and appropriate privacy controls
**before** loading irreplaceable internal data. Publishing on GitHub or
storing paths in a public git repository is not the same as a private
research data platform. Vercel Cron is not a durable job runner; it does
not guarantee retries or precise schedule times.
