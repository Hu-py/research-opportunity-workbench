# Research Atlas V0.5 · HTML-first website

Status: initial parity implementation, 2026-11-14.

The public root of the existing Next.js deployment points to the **exact approved V0.5 HTML design baseline**. This is a deliberate frontend reset, not a merging or re-display of previous Workbench features.

## Files

- `frontend/app/page.tsx`: redirects home to the approved V0.5 HTML asset.
- `frontend/public/research-atlas-v0.5.html`: verbatim copy of `docs/02-experience/prototypes/milestones/v0.5/index.html`.
- The historical V0.5 HTML remains unchanged and recoverable in `docs/02-experience/prototypes/milestones/v0.5/index.html`.

## New visible information architecture

- Primary icon rail: **对话** / **研究台**, with Chat as default.
- Chat: personal and team conversation **visual flows only**.
- Research Desk: **研究专题**, **科研发现**, **知识资产**, **管理与设置**.
- Specialized subviews match V0.5 HTML: topic details, A/B/C science scans, three-part weekly brief, evidence and method views, team/personal profiles, management.
- Black/white minimal style, no duplicate top navigation, no slogan, no architecture overview page.

## Current operational scope and disclosures

The static HTML uses sample topics, signals, papers and conversations. All chat messages are in-memory UI demonstration and are **not sent to an AI model or stored on the server**. Controls that would write persistent data display demo notices. **Do not treat the visible demo as a production collaborative research application.**

The old `Workbench.tsx` components and backend endpoints remain in the repo for rollback/data preservation, but they are **not shown from the homepage**. Existing API endpoints retain their independent authorization. No database schemas, secrets, backups, jobs, or GitHub workflows are modified. Do not expose private records in the static HTML.

## Production rollout

1. GitHub CI: TypeScript, Next.js production build, backend tests.
2. Vercel preview: verify exact asset, root redirect, menu, chat-to-research switching, topic/research/knowledge/settings subviews, desktop/mobile sizes.
3. Production deploy only after verifying that replacing the authenticated old Workbench with an explicitly public, **static design prototype** is intended.
4. Real features are implemented behind the new information architecture as separate tasks with authentication and authorization.

## Follow-on engineering

Implement native React/Next.js V0.5 components using the fixed approved layout, then connect private/team multi-turn conversation, account scope, research topics, A/B/C data, source provenance and personal profiles with actual backend services. Do not restore discarded legacy modules automatically.
