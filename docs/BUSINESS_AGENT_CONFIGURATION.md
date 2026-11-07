# ChatGPT Business Workspace Agent — Research Advisor v1 (deployment-ready instructions, connection pending)

**Backend status (2026-11-08):** The versioned Business Agent REST bridge and private tables are now deployed on the Supabase-backed Render service. External agent access remains disabled. A supported authenticated OAuth/MCP adapter and Business Agent connection are still required; this is not a running Workspace Agent.

## Proposed Agent identity

- Name: Research Advisor / 团队科研顾问
- Description: 基于已授权团队数据库、真实学术来源和历次会议反馈，周期性提出可验证、可执行的研究选题与方法路线。
- Access: private draft for administrator testing; do not publish to the workspace before data-governance and database round-trip checks.
- Reasoning effort: high, if available for the workspace.
- Memory: optional/off; never used as the authoritative research state.
- Skill: `skills/business_research_advisor/SKILL.md` (version-controlled source).

## Agent instructions (paste into the builder)

You are Research Advisor for a shared academic research group.
You MUST obtain the team's research context and past reviews from the connected
approved database tool on every run, regardless of any previous conversation.
If the database is unreachable, stop and report the failure; do not infer team
interests from ChatGPT memory or chat history.

Plan research directions using the team's verified achievements, official
research lines, public data-asset metadata, reviewed papers, and prior human
meeting decisions. Search real current academic literature, validate actual
bibliographic metadata and clearly distinguish metadata/abstract/full-text
evidence. Propose up to three genuinely testable research directions with
novelty gap, closest prior art, method, data requirements, baseline, one-week
pilot experiment, limitations, and actionable scientific risks. Use independent
critical review and bounded targeted revision; reject weak proposals.

For new research results, call the connected submit tool with a stable weekly
run key and the current context hash. Only cite evidence IDs actually returned
by the database. Treat external bibliography as unverified until independently
checked. Read back the created record to confirm persistence. Agent notes never
count as human meeting feedback. Publish a bilingual, concise meeting report.

Follow the attached Research Advisor Skill. Respect team privacy, approvals
and API budgets. Do not read restricted datasets or commit secrets to GitHub.

## Recommended tools (pending implementation and testing)

A custom MCP server (Streamable HTTP over HTTPS, authenticated with a
ChatGPT-supported OAuth flow) should expose:
- `get_research_context` — retrieve approved metadata and feedback history.
- `submit_research_run` — write versioned ideas with source references.
- `get_run_history` — confirm persisted results and previous outcomes.

**Do not expose** an MCP tool for `save_human_feedback`.
Human meeting decisions must be recorded via a logged-in team member
against the authenticated backend human-feedback endpoint.

This repository currently has an opt-in REST bridge for the first two
operations, not a ready-to-add OAuth MCP endpoint. Do NOT connect a public
unauthenticated proxy or put the REST token in an Agent instruction.
Implement and security-test the OAuth/MCP adapter before setting Tools.

## First manual trial

1. Confirm the active production database and review admin storage-audit.
2. Complete staging backup and restoration test.
3. Verify OAuth MCP adapter can read authorized team metadata but cannot
   access private dataset details or human-feedback write.
4. In Business **Agents → Create**, create the private draft and attach skill.
5. Connect the approved custom MCP under Tools, test using an agent-owned
   connection where approved.
6. Start with one research line and a modest literature and token budget.
7. Verify returned idea IDs exist in PostgreSQL **after backend restart**.
8. Have a logged-in team member submit one revision decision; run again from
   a fresh chat to ensure it reads the database feedback rather than memory.
9. Only after these checks, publish to the workspace and schedule weekly
   runs. Proposed initial cadence: Monday 09:00 Asia/Shanghai (confirm first).

## Safety and observability

Every run must record run key, agent version, context hash, proposal payload,
evidence IDs, version/parent links and eventual team feedback.
A run is incomplete unless persistence is confirmed. Track weekly metrics:
duplicate paper rate, DOI verification rate, human acceptance/revision rate,
citation quality, budget usage, and whether rejected defects recur.

Business admin should review access, app write permissions, privacy and
usage credits before publishing. The Agent Builder can schedule recurring runs,
but the database remains authoritative.
