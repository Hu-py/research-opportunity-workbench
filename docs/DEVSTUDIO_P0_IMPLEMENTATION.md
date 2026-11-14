# Research Atlas Development Studio P0 Implementation

**Branch:** feature/devstudio-p0-governance. **Specification:** Development Studio V0.3, chapter 18. This is an experimental implementation; it has not been deployed or merged.

## Implemented

- Five views at /devstudio: R&D overview, source management proposals, documentation index, experiment/run management, change request and independent approval.
- FastAPI endpoints under /api/devstudio and SQLAlchemy tables for modules' issue, change, decision, document, experiment, run reference and append-only evaluation.
- A source proposal always remains separate from the existing legacy Radar academic source registry. The legacy sources are deliberately shown as not migrated to the new A/B/C taxonomy.
- The source change approval state is approved_pending_release. **This means approval of a proposal, not deployment of a new collector or updated production source plan.**
- External GitHub Actions URLs are merely linked, conservatively marked unverified, not asserted as successful.
- ChatGPT Page and GitHub docs are linked, not mirrored or automatically rewritten.
- A module can show explicitly linked issues, changes, experiments, runs and decisions. Time order alone is not treated as cause and effect.

## Access controls

- Server denies all Development Studio access unless TEAM_AUTH_ENABLED is true and the user has a valid team session.
- Viewer: read. Researcher and admin: create records. Administrator other than the change requester: approve, reject or request revision.
- Each write leaves a team audit event.
- Approval never mutates the actual ResearchSource table, GitHub branch, AI prompt, scheduled task, deployed system or private Page.
- The API bearer token continues to be handled by the Next.js server-side proxy rather than browser JavaScript.

## Verification

Backend: python -m pytest -q tests/test_devstudio_api.py

Frontend: cd frontend && npm run typecheck && npm run build

Review the branch's GitHub CI results for full regression status. CI does not prove production deployment or scientific validity of research claims.

## Suggested user trial

1. Log into the original workbench with a researcher account and open Development Studio.
2. Submit an A/B/C journal source change and provide a scientific reason.
3. Independently log in as an administrator to review it. Confirm the status is approved_pending_release and existing Radar scanning remains unchanged.
4. Register the actual technical design Page in the documents index and create a document-revision request.
5. Register the existing OpenAlex official-sentinel comparison as an experiment. Link the actual GitHub Actions Run and add a human evaluation.
6. Inspect module lineage to verify each record and that no unobserved result is displayed as verified.

## Deferred

- An actual immutable A/B/C watchlist release and production source switch; requires evaluating and merging the separate AI workflow PR #57 first.
- GitHub API synchronization, verified CI/Run status, official journal metadata monitoring, source configuration Diff and controlled release PR generation.
- Full Page synchronization, granular source/document reviewer roles, deployment or rollback automation, legacy Radar retirement.
- Back-end generated scientific conclusions; current evaluation is recorded human feedback, not automatic claim validation.

The existing SQLAlchemy database is reused; no database migration to another engine is needed for this prototype. In production, take a backup and review schema migration before deploying: creating missing tables does not safely alter existing columns. No live weekly reports are modified by this branch.


## Approved UI V0.2 implementation (2026-11-14)

**Visual source of truth:** the reviewed standalone Research Atlas Development Studio UI Prototype V0.2 HTML, not the earlier five-page P0 wireframe. The official Next.js route now uses DevelopmentStudioV02 through the stable DevelopmentStudio component import.

- Preserves the reviewed dark navy left rail, white top bar, purple accents, overview cards, module table with adjacent task list, document three-column layout, experiment tabs, change approval timeline, source catalogue and detail drawers.
- Seven functional navigation views: overview, sources, documents, experiments, changes, workflows, settings. Workflows and settings clearly distinguish approved design structure from real runtime settings.
- **Newly confirmed behavior:** all four overview KPI cards are clickable. Selecting pending changes, research review or open issues filters BOTH the module table and the right-side tasks; selecting the active card again resets to all modules. Counts are derived from authenticated backend data rather than hardcoded prototype samples.
- Backend GET /api/devstudio/overview now includes pending_review_experiment_ids, derived from runs with no appended manual evaluations. It is not an external GitHub verification or a claim of scientific validity.
- Global command palette opens via the search bar or Cmd/Ctrl+K; searches real registered modules, changes, documents and experiments plus separately labeled reference sources.
- The seven source reference rows from the approved HTML remain explicitly marked as **design recommendations, not production watchlist entries**. Source change proposals are real backend records and their approval does not activate the source.
- Research documents used in the prototype are shown as suggested **reference links** until a team member registers them. Registering a link does not alter its source Page or GitHub file.
- Experiment Run and human evaluation are persistent backend objects, not static browser demos. Run is labeled "unverified" until a future GitHub evidence sync is implemented.
- The UI review drawer can export Markdown design feedback; that particular review feedback remains **client-session only** and is not written to the research audit table.

**Release gate:** Frontend compile/build and backend tests must pass; an authorized member must also visually review all seven pages on the deployed preview and verify researcher/admin approval separation. The full seven-screen design is not evidence that the separate A/B/C source registry migration, live CI monitoring, real-time model configuration or production rollout has occurred.

