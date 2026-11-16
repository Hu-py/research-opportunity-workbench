# Development Studio — Roadmap, run evidence, and weekly watchlist

## Purpose and locations

The `开发路线与兴趣雷达` tab in the existing Next.js workspace is a **delivery
dashboard**, not a replacement for the Research Atlas application. It gives
stakeholders a code-based feature inventory, implementation paths, explicit
acceptance criteria, and independently retrieved live database/run evidence.

- UI: `frontend/components/DevelopmentStudio.tsx` and `frontend/app/globals.css`
- Navigation: `frontend/components/Workbench.tsx`
- Independent interest model/search: `backend/interests.py`
- API: `GET/POST /api/research-interests`, `PATCH /api/research-interests/{id}`,
  `POST /api/research-interests/{id}/scan`
- Weekly: `research_workbench/cli.py`, `research_workbench/core.py`,
  `backend/worker.py`, `.github/workflows/weekly.yml`

## Status is not an assertion of successful production execution

- **已有实现**: code path present on the chosen branch; not automatically certified.
- **部分实现**: working components exist, but end-to-end research quality or
  production execution is not yet established.
- **规划中**: no usable production capability yet.
- **Live evidence**: when APIs are available, the UI fetches counts, latest
  discovery run, candidate bibliography, model analysis completion and saved
  research interests. Otherwise it explicitly shows missing data.

Feature statuses are currently **source-controlled**. To change them, modify the
`features` catalog in `DevelopmentStudio.tsx`, and make sure the file paths and
acceptance conditions still match the code. Do not infer completion simply from
a model-generated plan or mock result.

## Two separate knowledge layers

1. **Verified research basis**: PostgreSQL team achievements, research profile,
   nonrestricted CUSP metadata, reviewed paper candidates and confirmed links.
   These must preserve source IDs and human review.
2. **Research interest watchlist**: user-defined applied problems,
   cross-domain hypotheses and CS frontier learning topics, stored in
   `research_interests`. These are **not** official research lines and **not**
   verified team expertise. They can be paused without changing the profile.

The frontend includes an editable watchlist and starter **CS curricula** spanning
ML, NLP/agents, vision, graph/data mining, databases, robots, HCI, systems/SE,
and security. The venue labels are *watchlist suggestions* only; **the current
OpenAlex query does not filter/verify venues or rank scientific quality**.

## Weekly execution

1. In the authenticated site, add an interest with one or more public English
   search expressions. Avoid confidential text.
2. Click `试抓取` to test one branch. The backend processes it in a bounded
   FastAPI background task, and stores the resulting papers with
   `line_ids=["interest:<uuid>"]`. Existing papers are linked idempotently.
3. To enable the actual scheduled weekly workflow, configure the GitHub Actions
   repository variable `ENABLE_WEEKLY=true`, secret `DATABASE_URL`, and
   `OPENALEX_API_KEY` or other available OpenAlex credentials. Review its first
   successful run in Actions and the generated Markdown artifact.
4. The existing `research-wb weekly` CLI now ingests enabled interest topics
   (latest eight, first two queries each, up to six results per query), then
   appends a separate watchlist section to the existing brief.
5. If using the backend `weekly` research task instead, the worker now performs
   the same watchlist supplement. **The existing Vercel daily cron is not changed.**

GitHub Actions execution is gated and **is not enabled by the UI**. GitHub
Actions and Render can fail, sleep or run out of OpenAlex quota. The UI records
scan results but cannot guarantee continuous execution without a durable
worker, backups, and successful action history.

## Acceptance and next milestones

**Immediate acceptance (must be verified after deploy):**
- Login, open `开发路线与兴趣雷达`, see honest status and actual metrics.
- Add an interest, refresh and see it persist; pause and resume.
- Perform a real OpenAlex scan, check failures safely, and open a real paper URL.
- Run `research-wb weekly` against persistent PostgreSQL and verify the new
  interest subsection, without committing private data.
- Check CI typecheck/build and pytest. Mocked API tests do **not** certify
  live OpenAlex or LLM success.

**Next research-engine milestones:** metadata source/venue authority
verification, field-specific high-quality CS paper ranking, reading and
note-taking knowledge base, novelty/prior-art challenge workflow, explicit
cross-domain recommendations from team evidence, evaluator rubric with
baseline experiments, scheduled delivery history and alerting, backups.
