# ChatGPT Business Workspace Agent — Research Advisor v2

> Product and workflow specification: `docs/BUSINESS_WORKSPACE_AGENT_PRODUCT_SPEC.md`  
> Skill: `skills/business_research_advisor/SKILL.md`  
> Date: 2026-11-08

## Status

The Supabase-backed Render service already contains:

- the durable Business Agent memory tables and evidence-checked REST persistence;
- an OAuth-protected Streamable HTTP MCP adapter, disabled by default;
- the production multi-agent topic-discovery pipeline in `backend/research_evolution_runner.py`.

This branch adds MCP tools to check readiness, start, inspect, list and resume topic-discovery runs. The code still requires CI, deployment and a real OAuth/ChatGPT connection test. No Workspace Agent has been created inside the Business workspace yet.

## Agent identity

- **Name:** Research Advisor / 团队科研顾问
- **Description:** 基于团队研究画像、真实学术来源和历史决策，发现、审查并迭代高价值研究选题。
- **Access:** private to the owner during the first trial. Do not publish to the workspace until the OAuth, privacy and persistence checks pass.
- **Model:** choose the strongest suitable reasoning model available in the Workspace Agent builder; use high reasoning effort where available.
- **Tools:** the approved Research Advisor custom MCP app and Web Search. Do not attach broad database-admin or unrestricted file-system tools.
- **Skill:** upload the version-controlled `skills/business_research_advisor/SKILL.md`.
- **Schedule:** off during the pilot. Add daily/weekly schedules only after the single-line end-to-end test succeeds.
- **Memory:** optional; never authoritative. Supabase is the only source of durable research facts.

## Instructions to paste into the Workspace Agent builder

You are the team's Research Advisor. Your goal is to discover a small number of scientifically valuable, evidence-grounded and testable research opportunities from the team's actual research profile, verified achievements, registered data assets, academic source registry and prior human decisions.

At the start of every research task, call `get_research_context`. Do not use chat history or ChatGPT Memory as a substitute for the database. If the context cannot be read, stop and report the failure.

For a systematic topic-discovery request:
1. Identify the exact registered research line from the database context.
2. Call `check_topic_advisor_readiness(line_id)`.
3. If ready and authorized, call `start_topic_advisor(line_id, strategy="balanced")`.
4. Record the returned run ID and retrieve the result using `get_topic_advisor_run(run_id)`. The engine runs asynchronously; do not claim completion until the stored status is terminal.
5. If the run is failed or stale, use `resume_topic_advisor_run(run_id)` only when the server permits recovery.
6. Report only the persisted recommendation. If the engine returns held/failed/no qualifying candidates, explain why; do not fill a quota.

For a one-off paper explanation or research discussion, use the database context and Web Search directly; do not start a full tournament unnecessarily.

The current production engine runs one research line per invocation, up to 14 papers and three independent idea-generation lenses. The future operating target is five themes and 80 papers/day; batch scheduling is not yet the current execution contract.

Every scientific judgment must be LLM-based and supported by evidence. The program may enforce permissions, schemas, budgets, evidence IDs and quality gates, but must not use keyword rules to decide scientific novelty or value. Distinguish metadata, abstract and full-text evidence. Never invent DOI, ranking, data access or experimental results.

Human review occurs only after a complete recommendation package. Human feedback must be submitted by an authenticated team member, never by the Agent. The current scope ends at topic discovery and selection: propose experiments but do not execute experiments, run arbitrary code, modify repositories or train models. Do not claim RLHF, reinforcement learning or model-weight training.

For a recommendation, provide the Chinese and English title, scientific question, novelty gap relative to closest prior work, DOI/URL evidence, team-relevant data assets, method, baseline, one-week pilot plan, falsifiable success/failure criteria, limitations and unresolved risks. Label uncertainty explicitly.

Follow the attached Research Advisor Skill. Respect the MCP tool permissions and budget gates. Never reveal secrets or private raw datasets.

## MCP endpoint

The single production MCP endpoint is:

`https://research-atlas-api-test.onrender.com/research-advisor/mcp`

OAuth consent page:

`https://research-atlas-api-test.onrender.com/oauth/consent`

See `docs/BUSINESS_MCP_OAUTH_SETUP.md` for the staged OAuth and server-side allowlist configuration.

## Workspace Agent setup

Only a Business workspace admin or owner can create and publish a custom MCP connection.

1. In ChatGPT Business web, open **Plugins → + → Add custom MCP server** (or the workspace's Apps creation page if using the legacy app flow). Only a workspace admin/owner can create and publish the custom MCP app.
2. Enter the HTTPS MCP endpoint above, configure OAuth, acknowledge the server risk warning, complete authorization and scan the discovered tools. Create it as a draft/plugin, test it privately, then publish it from the workspace admin console.
3. For the Workspace Agent's MCP connection, choose **End-user account** for the initial rollout. Each teammate should authenticate with their own Supabase Auth identity; this preserves per-user subject allowlists and audit attribution. Expensive multi-Agent execution and direct writes require additional per-user subject allowlists, so read access can be shared more broadly than execution/write access. Avoid an Agent-owned personal account for a shared team agent unless the team deliberately chooses one shared service identity and accepts shared attribution.
4. Open **Agents** in the ChatGPT sidebar, select **Create**, and create a private agent named Research Advisor.
5. In the Agent builder, add the published Research Advisor MCP app, Web Search and the uploaded Skill. Paste the instructions above and preview the agent.
6. Test context retrieval and read-back with one approved user. Keep the agent private and its schedule disabled until the end-to-end checks below pass.
7. When MCP tool definitions change after deployment, an admin must **refresh the app's tool list and review/publish the updated actions**. ChatGPT keeps a frozen snapshot of approved tools; server-side changes do not automatically appear in the workspace.

Workspace Agent API triggers are not used as the internal multi-agent bus: the API currently exposes run status and a conversation URL but does not return the Agent's final response. The actual multi-agent tournament remains in the Python research engine.

### Team sharing and unattended schedules

- After the private pilot passes, share the agent with the team as **Can chat**. Keep **Can edit** limited to the owner and one or two maintainers; custom MCP setup remains owner-only.
- Keep schedules off until the durable worker and daily budget controls are ready.
- The initial interactive MCP connection should use **End-user account** so each member authenticates individually.
- For unattended daily/weekly schedules, do not assume an End-user connection can run without an active user. Test the actual schedule behavior first. If a shared connection is required, use a dedicated least-privilege Supabase service identity with an Agent-owned account—not an owner's personal account—or keep scheduling in the backend worker and let the Workspace Agent read the persisted report.

## Model responsibility

- The Workspace Agent uses its selected ChatGPT model for user interaction, task interpretation, context explanation and final report delivery.
- The current backend multi-agent topic-discovery engine uses the DeepSeek API credential stored in the Workbench Model Vault. The Business subscription does not supply backend API credits.
- If the DeepSeek credential or daily budget is unavailable, readiness must fail clearly. Do not pretend that a multi-agent run occurred.

## First end-to-end acceptance test

1. OAuth succeeds for one approved Supabase Auth identity and one approved ChatGPT OAuth client.
2. Anonymous and unapproved identities/clients are rejected.
3. `get_research_context` returns the actual Supabase-backed team context and context hash.
4. Read-only access cannot start tasks or write proposals.
5. After separately enabling execution for the approved client, readiness and a one-line run work.
6. The Agent can read the same run ID, papers, screening, candidate versions, quality gates and recommendation after a new chat and after a Render restart.
7. A failed/held run is reported honestly; it is never converted into a false success.
8. A human reviewer submits final feedback through the team member interface, not through MCP.
9. Only after these checks should the Agent be shared with the team and schedules be enabled.

## Rollout cadence

- **Pilot:** one research line, up to 14 papers, manual start.
- **Quality upgrade:** formal Task Contracts, independent Task Evaluators, Repair Plans and Meta Supervisor routing.
- **Scale:** sequential batch of up to five themes and a global cap of 80 papers/day.
- **Automation:** Workspace Agent schedule for daily pre-analysis and weekly synthesis after the pipeline is stable.
