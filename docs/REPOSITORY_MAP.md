# Repository map and maintenance policy

Last reviewed: 2026-11-16
Scope: `experiment/devstudio-postgres-e2e-20261114` (isolated staging branch)

This document is the navigation index for the repository. It distinguishes active product code, staging-only code, compatibility code and historical records. "Not currently in use" does not mean safe to delete: verify imports, deployment manifests, GitHub Actions and database dependencies first.

## 1. Active product code

| Area | Path | Role | Maintenance |
|---|---|---|---|
| Main API | `backend/api.py` | FastAPI application, authentication and route mounting | Active; changes require backend CI |
| Research agent | `backend/agent.py`, `backend/scientific_agent.py` | Research conversation and scientific reasoning services | Active capabilities; keep distinct from SC05 evaluation harness |
| Research tools | `backend/scientific_tools.py`, `backend/research_sources.py` | Source discovery and evidence retrieval | Active; preserve citations and provenance |
| Research evolution | `backend/sc04_evolution.py`, `backend/research_evolution*.py` | Research evolution workflows and validation | Active; see module-specific docs |
| Research Radar | `backend/radar_pipeline.py`, `backend/weekly_synthesis.py`, `scripts/openalex_weekly_radar.py` | Radar collection and weekly synthesis | Active when configured; schedule depends on GitHub Actions and persistent DB |
| Shared identity | `backend/team.py`, `backend/account_onboarding.py` | Roles, sessions, invitations and audit | Active; security-sensitive |
| Data layer | `research_workbench/` | SQLAlchemy models, OpenAlex and shared research persistence | Active; schema changes require migration review |
| Web application | `frontend/` | Next.js user interface | Active application frontend |
| Research instructions | `skills/` | Versioned agent skills | Active prompt assets; review with agent changes |
| CI | `.github/workflows/ci.yml` | Backend, frontend and tracker checks | Active required validation |
| Engineering tracker | `dev-tracker/` | Separate static engineering status board | Active independent Vercel project |

## 2. SC05: ChatGPT-managed experiment workflow

| Path | Role | Environment |
|---|---|---|
| `backend/sc05_agent_bridge.py` | OAuth-protected MCP tool gateway for ChatGPT | Staging-only until acceptance |
| `backend/sc05_eval_api.py` | Owner-authenticated paper intake, A/B run records, checkpoints, blind review and comparison | Staging-tested API |
| `backend/sc05_paper_only.py` | Paper-only research workflow and model stages | Shared SC05 execution code |
| `backend/sc05_worker.py` | Delegated queue consumer and isolated no-cost worker probe | Staging executor |
| `backend/sc05_r2_artifacts.py` | Private R2 archive mirror | Optional; not assumed enabled |
| `backend/sc05_quality.py`, `backend/sc05_science_gate.py`, `backend/sc05_research_diagnosis.py` | Quality, science gate and evidence validation | SC05 pipeline |
| `tests/test_sc05_*.py` | Offline security, workflow and pipeline tests | CI |
| `Dockerfile.devstudio-e2e`, `.render/devstudio-e2e.yaml` | Isolated staging service definition | Never point production at this service |

The MCP bridge now exposes pair-level preflight, sequential A/B start, blind result retrieval, blind review, unblinding/comparison and a durable experiment-round ledger. This is code-level capability, not yet proof that ChatGPT has refreshed its tool list or that a live paid experiment has completed.

## 3. Compatibility and legacy code

| Path | Current classification | Rule |
|---|---|---|
| `app.py` | Legacy Streamlit interface | Retain for compatibility and smoke tests; do not treat as the main Next.js UI |
| `backend/worker.py` | General durable task worker | Active for non-SC05 task queues; SC05 delegated worker is separate |
| `requirements.txt` | Legacy/minimal dependency list | Prefer `pyproject.toml` for canonical package/dependency management |
| `.streamlit/` | Legacy UI configuration | Keep until Streamlit compatibility is deliberately retired |
| `backend/sc05_operator_once.py` | Isolated one-shot staging operator | Diagnostic/recovery utility; not a normal ChatGPT execution path |

Do not delete compatibility code solely because the current product path does not use it.

## 4. Historical records and reference material

- `docs/`: specifications, runbooks, deployment audits and historical decisions. Prefer updating the current index/runbook rather than silently rewriting historical audit evidence.
- `dev-tracker/`: roadmap and issue-linked implementation status for engineering work.
- `examples/`: synthetic examples only.
- `data/`: runtime or research data; never commit confidential manuscripts, participant-level data, private PDFs, secrets or credentials.

Historical docs may describe an earlier deployment state. Check their date and the current deployment record before following operational instructions.

## 5. Not currently a default runtime path

The following are not the default user-facing application entry points: Streamlit `app.py`, the one-shot SC05 operator, and the isolated Render E2E Docker entrypoint. They remain in the repository because tests, compatibility and staging operations still depend on them.

No production code has been deleted or moved in this cleanup. A later retirement should require: (1) zero live imports/routes/workflows, (2) replacement tests, (3) deployment config updated, (4) explicit decision on historical reproducibility.

## 6. Change and release rules

1. Make changes on a feature or staging branch; do not use this isolated branch as the production branch.
2. Run `python -m compileall -q backend research_workbench` and the relevant pytest suite; full CI also checks frontend and tracker.
3. Keep credentials in Render/Vercel secret stores. Never put API keys, bearer tokens, Owner passwords or R2 credentials in Git.
4. Keep model execution separate from code deployment. A successful deploy is not a successful scientific experiment.
5. SC05 paid execution requires an active Owner OAuth grant with `experiments:run`, explicit per-run spending consent, configured provider credentials, an operating queue consumer and remaining server-side budget.
6. A worker restart must not automatically replay an ambiguous paid request. Preserve checkpoints and send ambiguous states to review.
7. Only call the full ChatGPT workflow accepted after the checklist in [SC05 ChatGPT end-to-end acceptance](SC05_CHATGPT_ACCEPTANCE.md) passes.
