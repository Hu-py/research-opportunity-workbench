# Research Radar: daily collection, five-gate review and private weekly archive

## Implemented flow

```text
GitHub daily.yml (opt-in)
    → OpenAlex searches for official profile + opt-in research interests
    → DOI-deduplicated Paper records, updated durable hypotheses
    → PostgreSQL

GitHub weekly.yml (opt-in)
    → same ingestion
    → optional paid DeepSeek AI review of one research line
       requires admin-saved encrypted model key and manually approved papers
       planner → paper reader → idea generation → critic
    → RadarTopic: conservative near-duplicate merging and evidence versions
    → five-gate feasibility pre-screen
    → RadarReport in PostgreSQL
    → /api/radar and /api/brief → Next.js "科研雷达 · 选题评审"
    → optional email; optional Git archive ONLY if repo private
```

The prior AI Lab keeps its safeguards: only papers manually reviewed as relevant/method and metadata of non-restricted datasets enter the LLM. The resulting model proposals remain unverified hypotheses. The radar does **not** automatically approve research, modify official research profiles, invent prior art or grant grade A.

The five gates were distilled from the two historical November 4 research-radar/Codex outputs provided by the user, without committing either private historical file into this public repository. See `skills/idea_discovery/SKILL.md`, `skills/paper_reader/SKILL.md` and `skills/idea_critic/SKILL.md`.

## Configuration for an existing private cloud deployment

### 1. Persistent database

Add GitHub Actions **secret** `DATABASE_URL` using a PostgreSQL URL with `postgresql+psycopg://`. Configure **the same** database in Render FastAPI and worker deployments. Configure separate least-privilege credentials and TLS/backup on the database provider.

Before switching on schedules, create schema by launching the current FastAPI service on the database; it registers the new radar tables via SQLAlchemy metadata. Production migrations should be introduced before heavily used releases.

### 2. Daily scanning

Set repository Actions **variable** `ENABLE_DAILY=true`. Its workflow runs at **07:13 Asia/Shanghai**. It requires a stored researcher profile; otherwise the task fails visibly instead of fabricating a profile. OpenAlex API key is optional depending on service limits; place it in `OPENALEX_API_KEY` Actions secret.

### 3. Weekly report

Set repository Actions **variable** `ENABLE_WEEKLY=true`. The weekly workflow runs at **09:17 Asia/Shanghai on Mondays**. It writes a markdown report to the database, including source links, data uncertainty and versioned Radar topics. The frontend reads the data from the backend API without redeployment.

**DeepSeek AI is opt-in:** set `ENABLE_WEEKLY_AI=true` and provide secret `MODEL_VAULT_KEY` matching the Render configuration. Configure the DeepSeek key through the authenticated AI lab; it remains encrypted in the database. The AI job can process **at most one** reviewed research line per weekly run, avoiding surprise multi-run charges. If no approved source papers or valid model key are configured, no new AI interpretation can be guaranteed. Without this flag, the scheduled process does **not** call DeepSeek.

The existing, separately controlled Vercel daily AI analysis switch has not been altered.

### 4. Private reports vs GitHub

This repository is currently **public**. Reports with personal research plans are saved to PostgreSQL and shown only via the authenticated site. **No reports are automatically pushed to public GitHub**. GitHub Actions report artifacts are also only uploaded for private repositories.

To archive weekly Markdown history into Git, first **make this repository private**, then set `ARCHIVE_REPORT_TO_GIT=true` in Actions variables. A second job verifies repository privacy again through GitHub's API and refuses to commit if it is public. It may need permission to write to the default branch.

To email a report, separately configure SMTP settings and recipient secrets. Email is off by default.

## Useful commands

```bash
pip install -e '.[postgres,test]'
research-wb daily                      # metadata and rule-based ideas, no LLM
research-wb weekly                     # report + latest completed AI cards, no LLM
research-wb weekly --ai                # optional ONE paid DeepSeek research line
research-wb weekly --email             # only if SMTP configured
pytest -q tests/test_radar_pipeline.py
```

## UI and API

- Next.js sidebar: **科研雷达 · 选题评审**
- GET `/api/radar`: Radar topics, review gates, report metadata, latest report
- POST `/api/radar/refresh`: editor/admin only; creates or merges topics from existing AI cards and generates a persisted report. **No LLM call.**
- PATCH `/api/radar/topics/{topic_id}`: editor/admin only; saves watch/shortlist/experiment/rejected/archived feedback, appends a versioned human-review event; AI sync does not overwrite it.
- GET `/api/brief`: existing Markdown brief plus latest available Radar report
- Research topics retain references to original Paper IDs, model card IDs and version events.

## Verification still needed after merge/deploy

- CI `pytest` + TypeScript build + Streamlit legacy smoke test.
- GitHub Secrets, database schema, OpenAlex real quota/latency, and user-configured research profile.
- DeepSeek paid analysis on actual *manually approved* paper candidates (explicit opt-in).
- Cross-week report retention, private Git archive and frontend access using deployed Render + Vercel.
- Check evidence quality and near-duplicate grouping with a researcher (current clustering is conservative, lexical; does not magically identify all conceptual synonyms).

The tool's grades are **only a triage mechanism**: B = promising but data preflight needed; C = blocked/uncertain; D = deferred. A is reserved for independent human verification of all five gates.

## First real retrieval sample (review before automatic ingestion)

The **科研雷达 · 选题评审** page has a **抓取一版真实论文** action. It
reads up to four **non-placeholder search queries from the actual PostgreSQL
database-evidence portrait**, falling back to officially registered queries
only if the evidence draft has no eligible query. It requests up to eight
OpenAlex works per query, limited to the previous 60 days.

- Data are stored in the separate `radar_trial_runs` table, NOT inserted into
  approved `papers`, `ideas` or official profiles.
- The live UI shows query provenance and for each work: title, date, DOI,
  source venue, abstract availability, and a weak lexical-overlap cue.
- Bibliographic completeness and keyword overlap are **not** relevance,
  peer-review quality, scientific novelty or legal data access. Do not equate
  an OpenAlex venue label with a verified top conference.
- Failed queries remain visible and do not silently count as zero results.
- Five-minute manual cooldown protects free API quota.
- No LLM is called. The separate AI Lab requires an admin-approved model
  configuration and manually reviewed candidate papers.

`POST /api/radar/scan-sample` queues a bounded run for editors and returns a
run ID. `GET /api/radar` includes the latest run as `sample`. The UI polls
while a run is active. On a service with no separate worker, FastAPI
BackgroundTasks does the small scan; do not use it for a massive crawl.

For **one explicitly approved** initial collection when the backend cannot be
called from the current client, the Render service also recognizes
`RADAR_TRIAL_ON_STARTUP=1`: it creates at most one database-wide trial on
startup. Repeated deploys/restarts do not rerun it once a record exists. The
server log prints the count and up to four **public OpenAlex** paper titles.
Leave this flag unset for routine operations. This initial run is independent
of the daily and weekly scheduled ingestion switches.

Recommended acceptance: compare 10–20 titles and abstracts against the
research questions, inspect source DOI links and dates, then classify
relevant / related but not transferable / irrelevant. Only after this
manual check should the official paper review and LLM reading proceed.
