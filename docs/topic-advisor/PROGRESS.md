# Progress

Latest checkpoint: reader cardinality fix and one successful five-paper live probe. Cumulative 20 requests / conservative CNY 0.828424; see NEXT_ACTIONS.md for recovery and scope. Earlier figures below describe the original pilot. The current task is publication for independent review, with no new paid experiments.

Branch: feat/topic-advisor. Original tracked source clean at start; pre-existing generated frontend/AGENTS.md and editable egg-info preserved.

Implemented: cumulative audit ledger and exact cache, existing-prompt A/B/C runner, strict reference checks, explicit empty output, database context adapter, confirmed decision recording, authenticated portfolio API and independent `/topic-advisor` page.

Validated: existing 98 tests passed; three new citation/cache/budget tests passed; frontend TypeScript passed.

Live evaluation stopped after persistent DeepSeek 503/timeouts. 19 attempted calls; conservative CNY 0.8201 including unknown usage reservations. One complete B result; no complete A/C pair or blind review. No superiority claim is supported.

Final local checks: full suite **102 passed** (one existing Starlette deprecation warning), frontend TypeScript and production build passed. Browser loaded the real B portfolio and opened its reasoned-feedback form successfully using Next.js webpack mode. Turbopack dev exhibited repeated navigation/rebuilds in this workspace; use webpack for this preview.

Remaining: live validation of targeted nearest-prior-art retrieval; full UI launch flow and durable asynchronous production runner; held-out evaluation; meaningful portfolio version editing; human-memory integration into repeated live evaluation; completed blind reviews. The requested complete first-round acceptance criteria are NOT yet met.

To inspect this local public pilot: run `python -m scripts.topic_advisor_report --portfolio` with the project virtualenv. Start FastAPI with `DATABASE_URL=sqlite:///data/topic-advisor/portfolio.db`, and the frontend with BACKEND_URL pointing to that local API. This dedicated preview database is separate from existing team records and production. CLI generation remains the only paid execution path.
