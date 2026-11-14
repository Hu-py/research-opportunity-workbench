# Multi-agent Research Game Replay (V0.8 viewer)

The new sidebar route **研究执行 → 多智能体博弈回放** is an interactive
historical replay of actual persisted Research Agent Lab runs, not model chain
of thought and not a fabricated real-time agent animation.

## What the page displays

- Latest 25 runs from isolated `public.lab_frontier_runs`, selected by date/ID.
- A step-by-step **logical** event timeline: OpenAlex discovery, independent
  paper jurors, arbitration, seed hypotheses, reversed-order Elo debates,
  Supervisor decisions, hypothesis refinement/fusion/rollback and Scientific Gate.
- Pairwise debate cards with *both* actual LLM judging reasons and caveats,
  plus a position-disagreement indicator.
- Reconstructed Elo values **up to each replay step** using persisted
  `delta_left` updates from recorded matches (not final ratings pasted into
  earlier steps); Elo remains LLM preference, not external validation.
- Candidate cards with falsifiable predictions, methods, baselines, cited
  OpenAlex IDs, registered dataset IDs and stated limitations.
- Generation-by-generation lineage including parent candidate IDs.
- The recorded paper juror votes and third-agent adjudication.
- Whether data access or real experimental claims were verified.

Historical runs may have no per-node timestamps. In that case the page shows
**sequence numbers only**, not invented execution times.

## Secure connection

This view is served inside the existing Next.js workbench session, using
server-side route handlers in `frontend/app/api/research-lab/runs`. Team mode
requires both the session cookie and revalidation through the existing backend
`/api/auth/me` endpoint before any Supabase access.

Set these two **server-only** environment variables in the Vercel frontend
project, for production/preview as appropriate:

```env
RESEARCH_LAB_SUPABASE_URL=https://YOUR-ISOLATED-LAB.supabase.co
RESEARCH_LAB_SUPABASE_SECRET_KEY=sb_secret_...
```

Use the **isolated lab** Supabase project, not the workbench's main Postgres
database. The key must never be included in `NEXT_PUBLIC_*`, front-end source,
browser devtools, client fetches, or public GitHub logs. The server uses
`apikey` headers for modern `sb_secret_*` keys (without an invalid JWT
Bearer token). The protected API only exposes a strict allowlist of saved
scientific outputs; it does not serve raw CUSP files or original owner
registration documents. All responses use `no-store`.

The UI will show an explicit **not configured** message until these variables
are present; it does not silently substitute a fake demonstration.

## Instant local replay without connecting cloud credentials

The UI can also read an existing `lab_frontier_runs` JSON export or the
single-row SQL output file containing `execution_chain`, `hypotheses`,
`agent_debates`, `decisions`, `literature_review` and
`scientific_validation`. Click **导入本地结果** and select the JSON/TXT
file. The browser parses it locally; no upload request is sent.

## Limits / planned V0.9

This version can replay **completed stored runs** and refresh to see newly
saved finished runs. It is not yet an event stream from a running LangGraph.
The existing `lab_frontier_runs` table receives records only after each
run finishes. Real-time partial-stage monitoring requires a separate
persisted stage-event stream with server-side authorization, a migration and
explicit instrumentation in Research Agent Lab. The UI never pretends a
historical sequence number is a timestamp.

This view does not change the paid model workflow, GitHub public action
artifact policy, research data catalog permissions or the Supabase schemas.


## V0.9 — 实时节点监控

The same page now includes a **LIVE AGENT EXECUTION** panel above the
historical replay selector. It reads the isolated lab's private
`lab_frontier_events` table through the authenticated Next.js route
`GET /api/research-lab/live` every 6 seconds.

Required additional setup:
1. Run [Research Agent Lab SQL 007](
   https://github.com/Hu-py/research-agent-lab/blob/main/sql/007_frontier_live_events.sql)
   inside the **separate research lab** Supabase SQL Editor.
2. Configure both server-only Vercel variables
   `RESEARCH_LAB_SUPABASE_URL` and `RESEARCH_LAB_SUPABASE_SECRET_KEY`.
   Redeploy after saving environment settings.
3. Run the Research Agent Lab's *free* connection verification workflow,
   with `check_frontier_live_events=true`.
4. In a **new** live frontier experiment, choose
   `stream_live_events=true` (default false) and `save_supabase=true`.

The browser shows genuine recorded node-completion timestamps and counters.
It cannot display private LLM chain-of-thought and will not claim a node
succeeded before the isolated backend writes its event. Completed runs
remain available in the same page's historical timeline. Do not copy
privileged Supabase API keys into repository source, public GitHub
variables, or `NEXT_PUBLIC_*` variables.

**Current limitation:** `run_started` is emitted only when LangGraph
execution starts, *after* the preceding team-portrait synchronization.
The live dashboard does not currently show portrait synthesis progress.


## V1.0 — Launch from the Workbench / 从网页发起科研实验

Team administrators can now open **研究执行 → 多智能体博弈回放** and
use the **启动新实验 / Launch experiment** panel, without opening
GitHub Actions directly.

The panel supports the current workflow's bounded controls:
- `evidence_source`: workbench_sync, public_demo, team_evidence, approved_secret
- `max_generations`: 0, 1, 2
- `max_papers`: 4, 6, 8; `max_pairs`: 1, 2, 3
- `stream_live_events`, `save_knowledge_graph`, `synthetic_pilot`
- `reuse_llm_cache`, `replay_namespace`, `bilingual_report`

**Existing SQL 002/003/004/007** and approved secrets are still required
for their respective operations. Team source permissions must be checked
before the admin confirms an experiment.

### One-time GitHub authorization (Vercel server only)

Create a **fine-grained personal access token** on GitHub restricted to the
single repository `Hu-py/research-agent-lab`, with **Actions: Read and write**
(and read-only Metadata, automatically granted by GitHub).

Save it as `RESEARCH_LAB_GITHUB_TOKEN` in the Vercel project's environment
variables. Use an encrypted/sensitive server-only value in Production and
Preview as needed; **never commit** it, send it in a screenshot or chat,
or prefix it with `NEXT_PUBLIC_`. Redeploy the Next.js site to load it.

The Next.js server API `GET/POST /api/research-lab/launch` uses this token
strictly server-side. Every request revalidates an active team **admin**
via the existing `/api/auth/me` endpoint. POST also enforces same-origin
JSON requests, strict enum/boolean validation, an explicit costs/permissions
checkbox, and checks GitHub for an existing active run before dispatch.
GitHub's workflow concurrency group provides an additional queue-level
guard. GitHub workflow dispatch accepted ≠ completed; the UI polls recent
Actions runs and shows their URLs, while the live event panel continues to
poll private `lab_frontier_events` every six seconds.

Because `workflow_dispatch` accepts no more than ten top-level inputs,
the live workflow now **always saves results to the isolated Lab Supabase**
instead of exposing a `save_supabase` toggle. The replacement input
`bilingual_report` adds at most **one** paid DeepSeek call to produce a
structured Chinese/English summary. The last scientific verification
remains unchanged if this translation fails; it must not declare claims
verified. Separate limits still apply to the research graph and team portrait
(up to nine calls).

Bilingual fields are `title`, `research_question`, `method`,
`competition_insight`, `scientific_assessment` and
`evidence_limitations`, with `zh` and `en` values. Original primary
language model output remains available beneath the bilingual report and
is the source of truth. Historical runs without the new field show a
transparent **not available** message rather than fabricated translations.

**Cost caution:** GitHub launch availability is gated on a repo-scoped
token. Frontend never calls DeepSeek directly. This does not implement
per-user billing, a dollar budget nor absolute race-free prevention of
simultaneous dispatch across geographically separate server instances.
Use GitHub spend monitoring for financial caps and grant admin role sparingly.
