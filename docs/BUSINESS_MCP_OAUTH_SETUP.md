# Business Research Advisor — OAuth MCP connection and rollout

## Supabase OAuth onboarding (2026-11-08, verified)

The team owner has **enabled and saved** the Supabase OAuth Server. The
Vercel consent UI `frontend/app/oauth/consent/page.tsx` is implemented.
The authorized **Site URL still needs to be changed away from localhost**.

Supabase OAuth tokens use `aud=authenticated`, issuer
`https://<project-ref>.supabase.co/auth/v1` and a signed `client_id`.
Supabase OAuth currently supports only standard `openid/email/profile/phone`
scopes; it does **not** issue custom `research:read`/`research:write`
scopes. The MCP backend therefore validates the exact issuer/signature,
audience, Supabase Auth user subject and OAuth client ID. **Independent server
configuration alone** grants research read/write capabilities.

Consent page configuration (Vercel environment variables, publicly
publishable values; never use the service-role key):

```text
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<Supabase Settings → API Keys → Publishable key>
```

Supabase dashboard → Authentication → URL Configuration → Site URL:
`https://research-opportunity-workbench.vercel.app`
when that domain is serving the actual consent route.
Supabase dashboard → Authentication → OAuth Server → Authorization Path:
`/oauth/consent`.

**The original Research Atlas team login and Supabase Auth login are distinct.**
The consent page accepts a previously registered Supabase Auth user's
email/password or email-login link; creating an account in the normal team
workspace does not create a Supabase Auth identity. Only explicitly allowed
Supabase user UUIDs can receive MCP data access. Do not put admin user
credentials or keys in GitHub or ChatGPT prompts.

Until a stable consent route is deployed, leave Supabase's dynamic OAuth app
registration off. Do not expose the MCP service or trust scope names alone.


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
| `get_research_context` | Approved user + client (server-side read capability) | Approved metadata + real meeting reviews + context hash |
| `get_run_history` | Approved user + client | Up to 20 recent persisted research runs |
| `get_research_run` | Approved user + client | Fetch one run to confirm saved idea IDs |
| `submit_research_run` | Explicit write-client allowlist + write enabled | Evidence-checked, versioned, idempotent persistence |

**There is no `save_human_feedback` MCP tool.** Human meeting reviews are
accepted exclusively through the separate authenticated team member API.

## Hard security gates before enabling

Use the **existing Supabase OAuth 2.1 Server** as issuer. It supports
authorization code with PKCE and refresh token rotation; its resource JWT
audience is `authenticated` rather than the MCP URL. For this reason the
resource server enforces exact OAuth client ID and user identity allowlists,
and limits writes separately from the identity-provider scope claim. Confirm
the ChatGPT OAuth handshake and resource discovery with real browser sign-in
before enabling external access.

The resource server is implemented in `backend/business_mcp.py`, using
the official MCP Python SDK v2 and RS256/ES256 signature validation via
Supabase JWKS, exact issuer/audience matching, expiration checks, explicit
approved Supabase subject and client IDs, and HTTPS host validation.
The independent `BUSINESS_MCP_WRITE_ENABLED` toggle defaults off.

The backend **must not** enable its MCP endpoint until an administrator has
an established OAuth provider and explicitly approved which team identities
can connect. These settings are server-side Render secrets/configuration only:

```text
BUSINESS_MCP_ENABLED=false
BUSINESS_AGENT_SHARING_APPROVED=false
BUSINESS_MCP_RESOURCE_URL=https://research-atlas-api-test.onrender.com/research-advisor/mcp
BUSINESS_MCP_ISSUER_URL=https://<project-ref>.supabase.co/auth/v1
BUSINESS_MCP_JWKS_URL=https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
BUSINESS_MCP_ALLOWED_SUBJECTS=<approved Supabase Auth user UUIDs, comma-separated>
BUSINESS_MCP_ALLOWED_CLIENT_IDS=<approved OAuth client IDs from Supabase OAuth Apps>
BUSINESS_MCP_ALLOWED_WRITE_CLIENT_IDS=
BUSINESS_MCP_WRITE_ENABLED=false
```

The signed Supabase JWT has `aud=authenticated`, and the backend grants
internal `research:read` only to a validated user+client combination.
Research writes remain disabled until the administrator explicitly
allowlists a client for writing and enables the separate write switch.
ChatGPT uses an authorization-code/PKCE browser flow;
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


## Actual deploy checkpoint (2026-11-08)

- Team owner confirmed Supabase OAuth Server is switched on and saved.
- `/oauth/consent` route and Supabase Auth sign-in+approve/deny logic were
  added **only** to the Vercel production branch `main` in commit
  `8d206212b5af2286a3e7896599ce5a138750b363`.
  All three GitHub CI jobs passed, but a Vercel deployment API attempt was
  rejected with HTTP 402 `api-deployments-free-per-day` (daily quota of 100).
  **Do not describe the page as live until a new production deployment is
  independently confirmed.** The existing website is unaffected.
- Vercel public env `NEXT_PUBLIC_SUPABASE_URL` is configured for the team
  Supabase project; `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` is **still
  missing**. Must be set to the project's *publishable* key, NEVER service-role
  or secret API key. The page is programmed to refuse use when it is absent.
- Supabase OAuth standard scopes **do not include** research read/write.
  MCP verifier was hardened to JWT issuer + `aud=authenticated` +
  approved `sub` + approved `client_id`. An independent write switch is
  disabled by default. The OAuth client ID and Supabase Auth user ID are not
  yet registered on the backend.
- Do **not** update Supabase Authentication → URL Configuration → Site URL to
  the Vercel domain before the route actually deploys. After it is live, set
  Site URL to `https://research-opportunity-workbench.vercel.app` while
  keeping Authorization Path `/oauth/consent`.
- A complete end-to-end OAuth PKCE sign-in / ChatGPT connection test has not
  been run. BUSINESS_MCP_ENABLED and BUSINESS_MCP_WRITE_ENABLED remain false.
