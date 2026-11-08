# Business Research Advisor — OAuth MCP connection and rollout

**Status (2026-11-08): MCP implementation prepared, disabled by default.**
The persistent team database and private REST bridge are deployed on the
Supabase-backed Render service. **This does NOT mean a Workspace Agent or
ChatGPT plugin has been created or connected.**

## Topology

ChatGPT Business Workspace Agent (approved tools)
→ HTTPS Streamable HTTP `/research-advisor/mcp`
→ issuer-verified OAuth 2.1 access token
→ approved-subject and tool-scope gates
→ existing versioned `business_agent_runs / business_agent_ideas` tables
in Supabase PostgreSQL.

Only the private team API's *public-safe evidence exporter* is accessible.
Private datasets, passwords, Research Agent Lab and human-feedback write
methods are not exposed.

## MCP tools

| Name | Required OAuth scope | Behavior |
|---|---|---|
| `get_research_context` | `research:read` | Approved metadata + real meeting reviews + context hash |
| `get_run_history` | `research:read` | Up to 20 recent persisted research runs |
| `get_research_run` | `research:read` | Fetch one run to confirm saved idea IDs |
| `submit_research_run` | `research:read research:write` | Evidence-checked, versioned, idempotent persistence |

**There is no `save_human_feedback` MCP tool.** Human meeting reviews are
accepted exclusively through the separate authenticated team member API.

## Hard security gates before enabling

The OAuth authorization server must support OAuth 2.1 authorization code,
PKCE S256, a resource/audience parameter, user consent and token
refresh/renewal. OpenAI recommends a trusted external provider (e.g. Auth0)
rather than writing a custom production authorization server.

The resource server is already implemented in `backend/business_mcp.py`,
using the official MCP Python SDK v2, JWT RS256 signature verification via
the provider's JWKS, exact issuer/audience matching, expiration checks,
explicit allowlisted subject IDs, tool-level scopes, and HTTPS host validation.

The backend **must not** enable its MCP endpoint until an administrator has
an established OAuth provider and explicitly approved which team identities
can connect. These settings are server-side Render secrets/configuration only:

```text
BUSINESS_MCP_ENABLED=false
BUSINESS_AGENT_SHARING_APPROVED=false
BUSINESS_MCP_RESOURCE_URL=https://research-atlas-api-test.onrender.com/research-advisor/mcp
BUSINESS_MCP_ISSUER_URL=<exact HTTPS OAuth issuer, including trailing slash if required>
BUSINESS_MCP_JWKS_URL=<provider's HTTPS JSON Web Key Set URL>
BUSINESS_MCP_ALLOWED_SUBJECTS=<approved OAuth user subject IDs, comma-separated>
```

The exact `resource` token audience must match
`BUSINESS_MCP_RESOURCE_URL`; required scopes are `research:read` and
`research:write`. ChatGPT uses an authorization-code/PKCE browser flow;
do NOT expose a static bearer secret, put tokens in an Agent prompt, or
connect a no-authentication MCP server.

Only after identity and connectivity tests pass:
```text
BUSINESS_AGENT_SHARING_APPROVED=true
BUSINESS_MCP_ENABLED=true
```

Do **not** modify the existing `DATABASE_URL`, 
`MIGRATION_TARGET_DATABASE_URL` or `RESEARCH_DATABASE_PROVIDER=supabase`.

## How an administrator connects the Business Plugin

After an OAuth-authorized endpoint has passed a private test:

1. In ChatGPT Business web, go to **Plugins** → **+** →
   **Add custom MCP server**. Only an owner/admin can publish to Business.
2. Enter `Team Research Advisor`, its HTTPS MCP URL
   `https://research-atlas-api-test.onrender.com/research-advisor/mcp`,
   and choose OAuth. Complete the actual authorization prompt.
3. Review the discovered four tools, especially the write tool.
   Keep the plugin restricted to the owner while testing.
4. Open **Agents** → **Create** → **Start blank**. Use the prompt at
   `docs/BUSINESS_AGENT_CONFIGURATION.md` and the versioned Skill in
   `skills/business_research_advisor/SKILL.md`.
5. Attach this plugin under the Agent's tools. For the first trial
   run it privately, with only one topic, modest scholarly query and token
   budgets. Verify the four read/write operations:
   context → submit → get run → new chat context/history.
6. Only after repeated privacy, identity and persistence checks,
   share with the team and add a weekly schedule. Proposed initial cadence
   is Monday 09:00 Asia/Shanghai, subject to owner approval.

## Self-checks and risk boundaries

- Verify **401** without OAuth and with forged/expired JWTs.
- Verify valid JWT with an unapproved `sub` cannot access metadata.
- Verify `research:read` token cannot submit runs.
- Verify private/internal dataset entries are absent from MCP context.
- Verify failed/duplicate/stale context submissions are rejected.
- Verify a saved idea remains readable after Render restart and a new chat.
- Verify an Agent token cannot impersonate a team reviewer or write feedback.
- Ensure external Agent access is disabled immediately if a provider or user
  credential is compromised.

**Operational limitations:** Workspace Agent creation and ChatGPT account
authorization require owner actions in the ChatGPT Business UI; GitHub code
commits alone cannot create the connected Agent. The independent offsite DB
backup still needs a provider-managed or encrypted remote copy. The old
Render Free PostgreSQL is not a permanent backup and expires 2026-12-04.

Sources:
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- https://help.openai.com/en/articles/20001143-chatgpt-workspace-agents-for-enterprise-and-business
- https://developers.openai.com/plugins/build/auth
- https://py.sdk.modelcontextprotocol.io/run/authorization/
