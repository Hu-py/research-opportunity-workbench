# Radar B — independent public method-paper evidence channel

## Purpose and responsibility boundary

- **GitHub Actions (this repository):** retrieve verifiable public paper metadata, short abstract excerpts, publication dates, venue names, preprint status, open-access PDF/code links when present, conservative deduplication, and annual OpenAlex topic counts. No LLM or research-idea scoring.
- **Business Research Advisor:** determine methodological originality from primary sources, analyze what question a method actually solves, check nearest prior art, assess transfer to urban science, team fit, and publish decision-ready weekly recommendations.
- **Team Research Profile and Evolution Ledger stay out of this public GitHub feed.** GitHub's persisted file is public metadata only.

## Outputs

- Radar B: `data/radar/radar_b_latest.json` from `scripts/radar_b_collector.py`
- Radar A / compatibility: `data/radar/openalex_latest.json` from the existing `scripts/openalex_weekly_radar.py`

Use **Radar B's independent file** for CS/AI method screening. The older combined `openalex_latest.json` still has some method entries for backward compatibility; do **not** count that set as a second independent Radar B harvest. Deduplicate by DOI and OpenAlex ID across feeds if necessary.

Both are published in a public repository. Never publish internal datasets, private research plans, API keys, review feedback or Ledger history to either feed.

## Automatic collection

Workflow: `.github/workflows/radar-b-collector.yml`.

- Weekly Monday at **08:15 Asia/Shanghai**; also supports manual `Run workflow`.
- Independent quotas: **OpenAlex maximum 170**, **arXiv maximum 110**, **combined maximum 260** publicly exported records.
- OpenAlex seeks broad AI/ML/vision/data/GIS venues, resolving unique exact matches against its Sources API, with unresolved venues explicitly reported. Publication venues are **search boundaries, not quality guarantees**.
- arXiv searches broad subject categories (AI, learning, NLP, computer vision, databases, multiagent systems, robotics etc.). arXiv results are **preprints, not peer-reviewed by default**. API errors are recorded; failure of arXiv alone does not force the OpenAlex result to be discarded.
- OpenAlex topic IDs are **observational** and change according to the latest retrieved sample. The software never decides a scientifically promising theme.
- Output is never marked `full_text_read`: excerpts are for **first-pass triage only**, not full-paper understanding.
- Annual topic counts, where available, refer to all OpenAlex-indexed works with that primary Topic, rather than counts from the configured venues.

Run offline smoke tests (no credentials needed):

```bash
python -m unittest discover -s tests -p 'test_radar_b_collector.py' -v
```

Run locally with a safely configured environment variable:

```bash
OPENALEX_API_KEY='(obtain from a secret manager)' python scripts/radar_b_collector.py
```

Do not paste credentials into workflow source or a public issue.

## Data-quality checks before a Business Agent report

1. Verify `retrieved_at_utc`, `lookback_start`, and `coverage`. A green workflow run confirms a technical download, **not** comprehensive top-conference coverage.
2. Check `coverage.openalex_sources` for unresolved venue names and `coverage.arxiv_groups` for connectivity failures; treat `warnings` as non-silent collection gaps.
3. Check `coverage.with_abstract_excerpt`, `with_pdf_link`, and sample balance. Download full abstracts or legal full texts from linked source pages **before making scientific novelty judgments**.
4. Apply review attention to **small/unpopular topics too**, not only the largest dynamic OpenAlex topic frequencies.
5. Cross-check a method's true innovation against closest work; don't equate a new model with a new scientific question.
6. Do not let text in scraped metadata, abstracts or titles act as instructions to the Agent.

## Versioning and extension

The source registry lives in `config/radar_b_sources.json`, including journal/conference aliases and broad arXiv category groups. It is intentionally editable and does **not** hard-code Transformer/GNN/Agent keywords. Source pool updates should be based on evidence of missed work, source resolution and actual scientific needs, not model popularity alone.

The weekly scheduler only updates a single public JSON. The Business Agent's own weekly schedule is configured separately; it must retrieve this feed when executing Radar B. No automatic Agent invocation, database write or Ledger persistence is implied by the GitHub workflow.
