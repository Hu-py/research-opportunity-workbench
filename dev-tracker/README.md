# Research Atlas — Independent Development Tracker

This is a **standalone, read-only engineering progress website** hosted in a
separate Vercel project. It is deliberately not a page of the researcher-facing
workbench, and needs no Render/PostgreSQL, private login or LLM credentials.

## Source of truth and auto updates

The website reads these public GitHub REST resources directly (no token):
- `/issues?state=all` — feature targets, technical path, acceptance evidence
  and open/closed state. Pull requests are filtered out of this issue list.
- `/pulls?state=all` — open PRs and merged implementation examples.
- `/commits?sha=main` — latest development updates.
- `/actions/runs?branch=main` — latest CI result for the main branch.

Queries run when the page opens, every **10 minutes** while visible, and on
manual refresh. This makes statuses current without an additional workflow or
database, subject to the unauthenticated GitHub rate limit (normally 60 requests
per IP/hour) and network access. A request failure shows **unknown** data,
never a synthetic success. For a deployment that requires private repository
data, replace direct browser fetching with a server-side authenticated
integration and access control; do not embed a GitHub token in JavaScript.

This does not automatically infer scientific novelty, operational readiness or
actual deployed backend success. A closed Issue means **GitHub closed**, not that
its acceptance criteria were necessarily checked.

## Development workflow

1. Create a GitHub Issue with the **研发功能 / Development Task** issue form.
   Describe your goal, technical approach, checkable acceptance, and expected
   result. Keep public tickets free of unpublished research results, restricted
   data, secrets and participant information.
2. New Issues appear automatically in the dashboard. Existing milestones are
   categorized by `dev-tracker/roadmap.json`; other Issues still appear as
   **其他任务**. Priority is read from a title prefix such as `[P0]`.
3. Use GitHub labels `status:in-progress` / `status:blocked` (if configured)
   to distinguish active and blocked open issues. Otherwise status is **开放任务**.
4. Reference an issue from a PR body and merge with `Closes #18` (actual number).
   GitHub closes linked issues when PR merges into the repository default branch.
5. Post acceptance proof as GitHub Issue checkbox updates and comment links;
   code being merged, CI passing, or a background job being queued does not
   alone establish end-to-end research quality.
6. The GitHub site and CI reflect updates at the next refresh. Changes to the
   curated target tracks, static phase organization, or the tracker UI are
   deployed automatically when `main` changes, through the separate Vercel
   Git-connected project.

## Deployment

The source path is `dev-tracker/`; this folder has no build dependencies.

- Vercel project name: `research-atlas-dev-tracker`
- Git repository: `Hu-py/research-opportunity-workbench`
- Root Directory: `dev-tracker`
- Framework preset: `Other` (static site)
- No environment variables are required
- Any production push to `main` automatically redeploys the tracker. GitHub
  Issues and CI data update independently of code deployments.

This standalone site must not be confused with the research workbench Vercel
project, which still serves the actual researcher-facing application.

## Maintained artifacts

- `roadmap.json`: feature categories, issue references, past code milestones
- `index.html`: independent layout
- `app.js`: GitHub API reads, prioritization and status handling
- `style.css`: visual system
- `.github/ISSUE_TEMPLATE/development-task.yml`: create a structured Issue
- `.github/workflows/ci.yml`: validates tracker syntax and milestone schema

The tracker is intentionally **read-only** for development data; editing occurs
in GitHub Issues and Pull Requests with full history, ownership and auditability.
