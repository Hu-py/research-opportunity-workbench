# Autonomous Research Evolution Engine — first working implementation

Branch: `feat/autonomous-research-evolution-20261106`.
This is a **new isolated workflow** layered over the existing team workspace, DB,
OpenAlex/Crossref/Semantic Scholar tool registry, DeepSeek vault and daily budgets.

## What changes

**No manual paper screening at the beginning.** A researcher selects one of
the existing database research lines and launches an experiment. A machine
literature analyst and an *independent* paper referee choose relevant papers,
including potential contradicting evidence. The prior workflow requiring
`PaperCandidate.status` in `relevant|method` remains available only for
legacy A/B comparisons and historical cards.

## Bounded, checkpointed stages

| Order | Stage | Actor / artifact |
|---|---|---|
| 01 | plan | DeepSeek Literature Scout proposes 3 semantic OpenAlex queries |
| 02 | retrieve | Registry retrieves up to 14 real paper records, with IDs and URLs |
| 03 | screen | Paper Analyst independently assesses every paper |
| 04 | paper_referee | Independent Evidence Critic selects/counters the first assessment |
| 05–07 | seed_problem / seed_method / seed_data | 3 independent hypothesis perspectives |
| 08 | score_initial | Independent scientific judge scores each hypothesis |
| 09 | challenge | Prior-art Challenger raises objections and generates directed new queries |
| 10 | counter_search | Registry retrieves new evidence; results added to the same paper set |
| 11 | counter_referee | Second independent paper review assesses closest prior art and rebuttals |
| 12 | revise | Scientific Evolver revises/fuses/rejects hypotheses, preserving parent_ids |
| 13 | score_final | Independent second-round judge checks evidence and feasibility |
| 14 | package | Only qualified ideas are packaged with actual returned paper metadata |
| 15 | done | Status review_ready or held (no human review of rejected ideas) |

Call budget: **at most 12 DeepSeek calls**; conservatively reserved 6,500
tokens per call (**78,000 tokens** if all calls run) under existing atomic
per-UTC-day `ResearchDailyBudget` guards. At most **10 external academic API
calls**, up to **14 unique papers**. The code does not make DeepSeek calls on
import, startup, get/readiness, or final feedback. The max expected requests
is an *upper bound*; requests may fail and still consume provider quota.

A recommendation must simultaneously have an independent machine score
>=80/100, evidence, feasibility, falsifiability and directed prior-art search
flags, successful external counter-search, and a second literature referee
rating of `manageable` (not `fatal` or `unknown`). The final idea must
cite >=2 actual discovered papers, include non-invented registered dataset IDs,
an experiment, baseline, falsifiable prediction and >=2 research path steps.
Scores are **experimental gates**, NOT scientific truth; these thresholds
need calibration against real independent human reviews.

## Human feedback -> conservative policy learning

Human researchers can rate **only review_ready packages**. `adopt / revise /
defer / reject` and four 1–5 ratings produce a bounded numerical reward.
`EvolutionPolicy` uses UCB1 to balance 3 interpretable exploration
policies: balanced, novelty, feasibility. The next frozen snapshot also
includes up to six earlier final-review comments from the same research line.
No previous feedback silently edits official team portrait or paper records.
This is **online workflow policy adaptation, not fine-tuning, PPO, DPO or
DeepSeek model-weight training**. Early scores are too sparse to claim
learning improves scientific novelty or reliability.

## Storage and security

New tables: `research_evolution_runs`, `research_evolution_feedback`,
`research_evolution_policy`. Existing credentials, profiles and papers are
unchanged. SQLAlchemy registers new tables on API import; use a schema
migration/backup review for production rollouts rather than assuming the
startup `create_all` is a full migration.

All routes require team authentication and existing service bearer auth;
write endpoints require researcher/editor access. Full science trace is
available to authenticated team members, including ineligible hypotheses.
The system sends metadata/abstracts and *non-restricted dataset attributes*
to DeepSeek; it does not upload local research files.

## API / frontend

- `GET /api/research-evolution/readiness?line_id=...` — zero-cost readiness
- `POST /api/research-evolution` with `{"line_id":"..."}`
- `GET /api/research-evolution` and `GET /api/research-evolution/{id}`
- `POST /api/research-evolution/{id}/resume` — stale/failed stage recovery
- `POST /api/research-evolution/{id}/feedback` — final human review only
- `GET /api/research-evolution/policy` — auditable exploration policy stats

`ResearchEvolutionPanel` surfaces machine paper decisions, independent
review rounds, candidate lineage, machine quality gates, final evidence-linked
recommendations and a human feedback form.

## Important limitations before production

1. No live paid DeepSeek run has been verified. CI uses mock DeepSeek and
   mock bibliographic providers. Earlier academic tool smoke did reach real
   Crossref, OpenAlex and Semantic Scholar, but not this full autonomous loop.
2. These checks only validate metadata provenance, **not full-text content,
   author claims, plagiarism or exhaustive novelty**. Crossref DOI/retraction
   and venue checks can be extended before full automatic delivery.
3. The current runner uses FastAPI BackgroundTasks, checkpointing one stage
   at a time. It is not a durable queue; Render Free sleeping can interrupt
   a run. Manual resume supports 8-minute stale detection. A durable worker
   is needed before 5 themes / 80 papers per day at scale.
4. Automatic scheduling of 5 themes daily / weekly reports remains the
   separate existing workflow and is **not yet wired** to trigger this 12-call
   tournament. Given the existing default 30 model calls/day, doing 5 full
   evolution tournaments would exceed the cap; prioritize 1–2 themes.
5. UCB1 is a cold-start feedback mechanism, not a calibrated reward model.
   Blind expert evaluation and budget-matched controls remain essential.

Use reviewed results to compare evolution with the existing A/B baseline,
not to assert any improvement from self-assigned scores.
