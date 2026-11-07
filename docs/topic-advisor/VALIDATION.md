# Independent review evidence

Latest backend revision: `.venv/bin/python -m pytest -q` — **104 passed**, one existing Starlette/httpx deprecation warning (2026-11-07).

Focused prompt/reader tests: `.venv/bin/python -m pytest -q tests/test_topic_prompt_contract.py tests/test_topic_advisor.py` — **6 passed**.

Frontend implementation in 9f7ec7d: `npm --prefix frontend run typecheck` and `python3 /workspace/.cloud-setup/build-frontend.py` — passed (the helper runs `npm run build` and preserves generated TypeScript configuration). Browser with system Chromium / Playwright verified the real pilot portfolio and feedback form using Next.js webpack mode. No frontend changes in the subsequent reader-contract fix.

Live original pilot and limitations: EVALUATION.md and pilot-public-evidence.json. Append-only public attempt/output export including the subsequent one-call reader probe: public-call-audit.json. Unknown usage is marked as reserved/failed, not silently charged zero. No calls were made for the publication task.

The committed JSON artifacts contain synthetic team contexts and public bibliography/results only. Keys, environment variables, database files and private prompts are excluded. Pre-existing untracked frontend/AGENTS.md and research_opportunity_workbench.egg-info/ are generated setup artifacts and deliberately not committed.
