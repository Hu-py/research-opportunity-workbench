# Research Atlas AI workflow migration

Status: **incremental experimental refactor** (branch only). Product authority:
[Research Atlas technical design Page](https://chatgpt.com/space/page_4f5d2daf5684819181b1756930835fde).
Existing team and production interfaces remain on the old implementations until
the new pipeline is evaluated and explicitly switched over.

## Terminology

The new three source groups are **not** the old Radar A/B collector names:

- `planning_application`: practical planning problems, scenarios, data needs.
- `urban_science`: measurement, urban-science framing, theory and conceptual changes.
- `computational_methods`: reusable CS models, tools, evaluation and method changes.

This is the **source axis**. `L0-L3` is the **analysis depth axis**.
`SC01-SC03` is the **user/workflow axis**. Legacy A/B/C/D research-idea
grades remain separate, with no new group inferred from an old letter.

A venue may belong to more than one group. For now, explicit venue priorities
take precedence over broad `domain` fallback. The JSON plan can be reviewed and
edited without source code changes. A watched author uses a stable ID, never
name-only fuzzy matching. Classification says where to look; it is *not* a paper
quality score or proof of author identity.

## Design goal and first implementation slice

```text
Configurable tri-source watchlist
    -> source tagging on an existing paper snapshot
    -> L0 unique record and group counts
    -> optional model-assisted L1 synthesis
    -> structural check of cited paper IDs, source membership and trend claims
    -> human-review-only draft with paper references
```

Current new code:

- `config/atlas_source_plan.json`: named A/B/C watchlists.
- `backend/atlas_intelligence/sources.py`: exact registry-based venue matching,
  stable-author-ID addition and explicit group mapping.
- `backend/atlas_intelligence/runner.py`: balanced evidence snapshot and one
  injectable model synthesis call; does **not** publish or mutate a database.
- `backend/atlas_intelligence/signals.py`: reference validation, evidence
  status, L0/L1 draft and Markdown renderer.
- `scripts/atlas_signal_trial.py`: manual trial entry point; accepts a JSON
  evidence snapshot; can validate a saved JSON proposal with no paid call.

A model-cited ID **must exist** in the evidence snapshot, but this mechanical
check does not establish the truth of a specific scientific claim. Every signal
is marked `needs_review`; the frontend must not interpret it as published
or as verified novelty. The single-paper guard prevents a one-paper result
from being silently labeled a multi-paper trend. Historical comparison claims
must identify their comparison window, and still require human review.

The signal content is deliberately flexible. Gap, method features, paper
differences, limitations and team fit are **analysis concerns**, not mandatory
user-visible headings. No target number of signals, deep reads or research
proposals is imposed. L2/L3 may be empty.

## Usage for the first local experiment

Make an **authorized** JSON evidence snapshot (only public abstracts or
research materials you may process):

```json
{
  "papers": [
    {
      "paper_id": "W-example",
      "title": "Example study",
      "venue": "Cities",
      "url": "https://example.org/paper",
      "abstract": "Example abstract..."
    }
  ],
  "registered_sources": [
    {"name": "Cities", "abbreviation": "Cities", "domain": "urban_planning"}
  ]
}
```

For a no-cost offline check, supply a model proposal with
`{"signals":[]}` or valid L1 `signals` using only the supplied paper IDs:

```bash
python scripts/atlas_signal_trial.py --input input.json --proposal proposal.json --period 2026-W46 --out scratch/atlas-preview.md
```

For an explicitly paid DeepSeek run, set `DEEPSEEK_API_KEY` as a private
environment variable and omit `--proposal`. This is a trial, not a scheduled
workflow, not an approved report, and not a live database integration.
Do not commit sensitive input/output JSON, model credentials, unpublished
manuscripts, or private team records to a public repository. Prefer local
ignore-listed scratch paths and remove sensitive material after testing.

## Modules: retain, refactor, retire (provisional)

| Existing module | Decision now | Exit conditions |
| --- | --- | --- |
| `backend/research_sources.py` | Keep registry/API and stable source IDs; new A/B/C labels are a separate layer | Merge after A/B/C registry regression tests |
| `backend/discovery_runner.py` | Keep old direct/method discovery for compatibility | Switch only after new three-group recall and duplication tests |
| `backend/preanalysis.py` | Keep, augment later with evidence and `PaperKnowledge` | Validate abstract-only limitations and extraction accuracy |
| `backend/weekly_synthesis.py` | Keep old DB report until SC01 new L1 path is tested | Compare source coverage, evidence errors, user utility and costs |
| `backend/radar_pipeline.py` | Keep reviewed proposal/idea history as optional L3 | Decouple from default weekly path before retiring any old endpoints |
| `backend/agent.py`, `scientific_agent.py` | Keep as SC03 candidates | Evaluate tool differences and remove redundant code only with tests |
| `scripts/openalex_weekly_radar.py`, `scripts/radar_b_collector.py` | **Legacy public feeds**; retain temporarily | Remove only after consumers, actions, dashboards and backfills audited |
| `skills/idea_discovery`, `skills/idea_critic` | Keep for targeted hypothesis/novelty tasks | Do not run as obligatory steps for every L1 signal |
| `frontend/`, `backend/api.py` | No UI/API removal in this slice | Introduce new run API when new drafts/permission model proven |

**Deprecation policy:** Mark obsolete entry points, identify all consumers,
build replacement and regression coverage, provide an output/data migration,
disable old schedules, then remove code in a distinct PR. Do not erase
old evidence, reviewed ideas or audit history merely to declutter code.

## T1.1: independent OpenAlex source collection (second iteration)

The new collector **queries OpenAlex directly** using each of the three configured
source lists. It is not a renamed import of either legacy Radar A or Radar B.

- `backend/atlas_intelligence/collector.py`: resolves registered venue names
  to OpenAlex Source IDs by exact names/aliases, fetches recent paper metadata
  for each group, optionally retrieves works by *verified* author OpenAlex ID
  or ORCID, deduplicates DOI/Work IDs and retains group-level provenance.
- `scripts/atlas_collect.py`: manual collection entry point. Records the
  configured and attempted source counts, unresolved sources, request failures,
  distinct paper counts, abstract availability, exact source-plan hash and
  the complete/partial **attempt status**. Sampling is **never** a complete
  scholarly population estimate.
- `scripts/atlas_signal_trial.py`: accepts this new feed for an optional,
  explicitly authorized L1 synthesis trial; limits papers per source group
  before sending material to a model. It does not quietly force a research idea.
- `tests/test_atlas_collector.py`: no-network fixtures for three-source
  collection, DOI/author deduplication, abstract truncation, coverage and
  the model-input handoff.
- `.github/workflows/atlas-three-source-trial.yml`: **manual-only** real API
  smoke test. Uses an existing `OPENALEX_API_KEY` secret and uploads a
  review-only **public metadata** artifact for seven days. It does not
  publish a report, use a private team profile, or update a database.

This iteration broadens the **C methods** watchlist to include method journals
(e.g., JAIR, TPAMI, IJCV, TNNLS, TKDE), not just seasonal CS conference
proceedings. OpenAlex records may have no abstract; reconstructed abstracts
may be truncated; evidence levels stay distinct. Accepted conference status,
research gaps and method breakthroughs are **not** verified by the collector.

To run on your own machine with a configured environment and the checked-out
experimental branch:

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_atlas_intelligence.py tests/test_atlas_runner.py tests/test_atlas_collector.py
export OPENALEX_API_KEY="<set your private key in your shell>"
python scripts/atlas_collect.py --lookback-days 30 --max-per-source 8 --max-sources-per-group 2 --out scratch/atlas_public_sample.json
python scripts/atlas_signal_trial.py --input scratch/atlas_public_sample.json --proposal scratch/review_proposal.json --period 2026-W46 --out scratch/atlas_preview.md
```

The `--proposal` JSON file contains a researcher/model proposal such as
`{"signals":[]}` for an offline smoke test; without that flag, the trial
requires an explicit `DEEPSEEK_API_KEY` and makes a paid model request.
All proposals still require scholarly review. Local `scratch/` files must
not be committed to a public repository if they contain personal choices
or private team assets.

### Historical audit, not a new tri-source feed

The public artifacts dated **2026-11-09** are useful only as migration
baselines: the older public OpenAlex feed includes `recent_papers` without
abstract texts, while the old Radar B technical feed includes many arXiv
preprints and selected technical journals. Directly relabelling old
`planning/methods` streams as A/B/C would therefore misrepresent collection
coverage. An independent sampling trial against the new source plan is
required before replacing any automated source ingestion.

## Next technical increments

1. Compare tri-source recall against the existing public OpenAlex feeds and
   add a versioned **author directory** backed by verified OpenAlex/ORCID IDs.
2. Introduce persistent `PaperKnowledge`, `Evidence`, `ResearchSignal`
   and run checkpoints while reusing existing `Paper` and candidate tables.
3. Make claim-level evidence checks stronger (original passages, contradiction
   evidence, closest prior work); then human-evaluate six fixed cases.
4. Integrate the L0/L1 pipeline into a permission-checked SC01 task, with
   team source configuration, draft/approval states and repeatable snapshots.
5. Enable SC02 private reranking and SC03 ad hoc deep-dive paths using the
   same knowledge and evidence API.

## Verification

`pytest -q tests/test_atlas_intelligence.py` should pass in the normal
repository test environment. Existing CI should continue testing legacy
API/radar behavior. Do not claim production readiness until CI, a real
metadata feed trial, a paid model trial (when authorized), and human research
review have each been verified.
