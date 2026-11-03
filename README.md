# Research Opportunity Workbench 🔬

A cumulative, evidence-linked workbench for interdisciplinary research-topic discovery. The MVP searches scholarly metadata for urban-planning problems **and** transferable computer-science methods. It stores versioned hypotheses, supporting paper links and researcher feedback.

**MVP 0.1 (development):** OpenAlex retrieval, DOI deduplication, simple method taxonomy, research-profile onboarding, rolling idea pool, history, Markdown reports, Streamlit dashboard, mocked-API tests and opt-in GitHub Actions scheduling.

**Limits:** Method matching is a heuristic, *not* a novelty assessment, a comprehensive literature review or an autonomous multi-agent system.

## Run locally

Requires Python 3.10+:

```bash
git clone https://github.com/Hu-py/research-opportunity-workbench.git
cd research-opportunity-workbench
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cp examples/profile.example.json my-profile.json
# Edit your private profile; the filename is git-ignored
research-wb profile-import my-profile.json
research-wb ingest --days 30
research-wb ideate
research-wb weekly --days 14
streamlit run app.py
```

SQLite at `data/research.db` is the local default. The Research profile tab provides an alternative JSON editor. An imported profile must define `research_lines` with stable `id`, `name`, unresolved `problem`, `keywords`, `search_queries` and `method_queries`. Computational queries need not mention urban studies. Each idea corresponds to a stable research line × method, so new paper evidence updates the same idea instead of producing unrelated duplicates.

Run tests:

```bash
python -m pytest -q
```

## Weekly automation

`.github/workflows/weekly.yml` is scheduled on **Mondays 09:17 Asia/Shanghai** but **disabled by default**. For cumulative weekly runs, provide a persistent PostgreSQL database, not SQLite on an ephemeral GitHub runner.

1. Set Actions secret `DATABASE_URL` to a private PostgreSQL URI (`postgresql+psycopg://...`).
2. Import your profile into that database locally with `DATABASE_URL` set.
3. Set Actions variable `ENABLE_WEEKLY=true` to opt in.
4. Optionally set SMTP variables `SMTP_HOST`, `SMTP_PORT`, and secrets `SMTP_USER`, `SMTP_PASSWORD`, `REPORT_TO` for emailed digests.
5. Test the workflow manually and review the logs. Without email, the Markdown report is an Actions artifact only.

**Privacy:** This GitHub repository was observed to be **public**. Do not commit research materials, API keys, unpublished manuscripts or participant data. Make the repository private before enabling reports containing personal research topics. The database and email system need their own access controls.

## Source and inference safeguards

- [OpenAlex](https://openalex.org/) provides the first metadata feed. Searches use a publication-date filter and may miss papers newly indexed with old publication dates; periodic backfilling and additional sources are planned.
- Every hypothesis links to indexed paper records. This does **not** mean those papers conclusively support the target application. Always read original papers and check prior art.
- `score` is only a screening priority from evidence count and overlapping keywords; it is not a verified novelty or acceptance estimate.
- Status values: `candidate`, `watch`, `shortlist`, `experiment`, `rejected`, `archived`. Feedback creates a new historical version and excluded ideas are not automatically revived.

## Next development

Semantic Scholar recommendations, Zotero sync, arXiv/OpenReview/ACL venue verification, DOI/preprint identity reconciliation, hybrid search and RAG, critically sourced LLM reviews, researcher-document imports, refined opportunity evaluation, and eventual research-to-experiment handoffs.
