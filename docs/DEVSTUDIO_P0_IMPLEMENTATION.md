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
