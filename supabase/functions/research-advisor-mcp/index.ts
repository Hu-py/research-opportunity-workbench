/**
 * Research Advisor — native Supabase MCP (read-only pilot).
 * Verified JWT + exact OAuth user/client allowlist before ANY database call.
 * Fixed, read-only SQL. No raw data/files/custodian/secret access or writes.
 *
 * The legacy app revoked authenticated grants on its public tables, so the
 * scoped Supabase client cannot read them. Only this trusted Edge Function
 * uses the built-in SUPABASE_DB_URL for parameterized read-only queries.
 */
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createMcpHandler, McpServer } from "npm:@modelcontextprotocol/server@^2.0.0";
import { pipeline } from "npm:@supabase/middleware@1";
import { withOAuthProtectedResource, withSupabase } from "npm:@supabase/server@1";
import postgres from "npm:postgres@3.4.7";
import { z } from "npm:zod@^4.3.6";
import {
  bearerToken, isAuthorizedPrincipal, jwtClaimsFromVerifiedToken,
} from "./auth_policy.ts";

const PROJECT_URL = Deno.env.get("SUPABASE_URL") || "";
const MAX_BUNDLE_BYTES = 44_000;
const SENSITIVE_NAME = /儿童健康|手机信令|微博签到|通勤od|病例轨迹|疫情数据|个人轨迹|隐私轨迹|个人隐私|个体健康|身份证|患者信息/i;

let pool: ReturnType<typeof postgres> | undefined;
function db() {
  const uri = Deno.env.get("SUPABASE_DB_URL");
  if (!uri) throw new Error("Database configuration unavailable");
  if (!pool) {
    pool = postgres(uri, { max: 1, prepare: false, ssl: "require",
      idle_timeout: 8, connect_timeout: 10 });
  }
  return pool;
}

function toolResult(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(data) }] };
}
function safeToolError() {
  return { isError: true, content: [{ type: "text" as const,
    text: "Research MCP operation failed. Review the private function logs." }] };
}

async function snapshotContext() {
  return await db().begin(async (tx) => {
    await tx.unsafe("SET TRANSACTION READ ONLY");
    const achievements = await tx.unsafe(
      "SELECT id, title, year, kind, doi, venue, tags_json FROM public.team_achievements " +
      "WHERE status='verified' AND length(trim(title))>0 ORDER BY year DESC, title, id LIMIT 80");
    const assets = await tx.unsafe(
      "SELECT id, name, category, coverage, period FROM public.cusp_datasets " +
      "WHERE sensitivity='public' ORDER BY category, name, id LIMIT 100");
    const publicAssets = assets.filter((r) => !SENSITIVE_NAME.test(String(r.name || "")))
      .slice(0, 25).map((r) => ({
        id: "cusp_datasets:" + r.id,
        name: String(r.name || "").slice(0, 200),
        category: String(r.category || "").slice(0, 120),
        coverage: String(r.coverage || "").slice(0, 200),
        period: String(r.period || "").slice(0, 150),
        sensitivity: "public", access_verified: false,
      }));
    const verifiedWorks = achievements.map((r) => {
      let tags: string[] = [];
      try {
        const raw = JSON.parse(String(r.tags_json || "[]"));
        if (Array.isArray(raw)) {
          tags = raw.slice(0, 16).filter((v) => typeof v === "string")
            .map((v) => v.slice(0, 100));
        }
      } catch { /* Reject invalid tags without exposing the value. */ }
      return {
        id: "team_achievements:" + r.id,
        title: String(r.title || "").slice(0, 400),
        year: Number(r.year) || 0, kind: String(r.kind || "").slice(0, 40),
        venue: String(r.venue || "").slice(0, 200),
        doi: String(r.doi || "").slice(0, 200),
        tags, evidence_level: "title_only", ownership: "verified_team_output",
      };
    });
    if (!verifiedWorks.length) throw new Error("Verified catalogue empty");
    const bundle = {
      bundle_id: "research-team",
      source: "supabase_authorized_database_snapshot",
      memory_schema: "research_mcp_readonly_v1",
      achievements: verifiedWorks, datasets: publicAssets,
      limitations: [
        "Dataset metadata does not grant access to underlying private data.",
        "Titles alone are not a full-text literature review.",
        "Research proposals are not human-approved without explicit review.",
      ],
    };
    const serialized = JSON.stringify(bundle);
    if (new TextEncoder().encode(serialized).byteLength > MAX_BUNDLE_BYTES) {
      throw new Error("Bounded context too large");
    }
    const hash = await crypto.subtle.digest(
      "SHA-256", new TextEncoder().encode(serialized));
    const contextHash = Array.from(new Uint8Array(hash))
      .map((b) => b.toString(16).padStart(2, "0")).join("");
    return { context_hash: contextHash, context: bundle };
  });
}

async function recentRuns(limit: number) {
  return await db().begin(async (tx) => {
    await tx.unsafe("SET TRANSACTION READ ONLY");
    const rows = await tx.unsafe(
      "SELECT r.id, r.run_key, r.topic, r.agent_version, r.status, r.created_at, " +
      "count(i.id)::integer AS idea_count FROM public.business_agent_runs AS r " +
      "LEFT JOIN public.business_agent_ideas AS i ON i.run_id=r.id " +
      "GROUP BY r.id ORDER BY r.created_at DESC, r.id DESC LIMIT $1",
      [limit],
    );
    return { items: rows.map((r) => ({
      run_id: r.id, run_key: r.run_key, topic: r.topic,
      agent_version: r.agent_version, status: r.status,
      created_at: r.created_at, idea_count: Number(r.idea_count) || 0,
    })) };
  });
}

async function getRun(id: string) {
  return await db().begin(async (tx) => {
    await tx.unsafe("SET TRANSACTION READ ONLY");
    const rows = await tx.unsafe(
      "SELECT id, run_key, topic, agent_version, status, context_hash, created_at " +
      "FROM public.business_agent_runs WHERE id=$1 LIMIT 1", [id]);
    if (!rows.length) return { found: false };
    const ideas = await tx.unsafe(
      "SELECT id, parent_id, version, title, payload_json, created_at " +
      "FROM public.business_agent_ideas WHERE run_id=$1 " +
      "ORDER BY created_at, id LIMIT 20", [id]);
    return {
      found: true, run: {
        run_id: rows[0].id, run_key: rows[0].run_key,
        topic: rows[0].topic, status: rows[0].status,
        agent_version: rows[0].agent_version,
        context_hash: rows[0].context_hash, created_at: rows[0].created_at,
        ideas: ideas.map((i) => {
          let content: Record<string, unknown> = {};
          try {
            const parsed = JSON.parse(String(i.payload_json || "{}"));
            if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
              content = parsed;
            }
          } catch { /* Bad historical proposal JSON must not crash the tool. */ }
          return {
            ...content, id: i.id, parent_id: i.parent_id,
            version: i.version, title: String(i.title || "").slice(0, 240),
          };
        }),
      },
    };
  });
}

const enabled = () =>
  Deno.env.get("RESEARCH_MCP_ENABLED")?.trim().toLowerCase() === "true";

const handler = pipeline(
  [withOAuthProtectedResource(), withSupabase({ auth: "user" })],
  async (request, { supabase }) => {
    const token = bearerToken(request.headers.get("Authorization"));
    if (!token) return new Response("Unauthorized", { status: 401 });
    // The middleware authenticates JWT via Supabase JWKS. GetUser adds an
    // independent server-side identity check before signed claims are parsed.
    const { data, error } = await supabase.auth.getUser(token);
    const claims = jwtClaimsFromVerifiedToken(token);
    if (error || !data.user || !claims || !isAuthorizedPrincipal(
      claims, data.user.id, {
        projectUrl: PROJECT_URL, enabled: enabled(),
        allowedUserIds: Deno.env.get("RESEARCH_MCP_ALLOWED_USER_IDS") || "",
        allowedClientIds: Deno.env.get("RESEARCH_MCP_ALLOWED_CLIENT_IDS") || "",
      },
    )) {
      return new Response("Forbidden", {
        status: 403, headers: { "Cache-Control": "no-store" },
      });
    }
    const mcpHandler = createMcpHandler(() => {
      const server = new McpServer({
        name: "Research Advisor — Supabase", version: "0.1.0",
      });
      server.registerTool("get_research_context", {
        title: "Get research context",
        description: "Read approved team publication titles and public dataset metadata, plus source limitations and snapshot hash.",
        inputSchema: z.object({}),
        annotations: { readOnlyHint: true },
      }, async () => {
        try { return toolResult(await snapshotContext()); }
        catch { return safeToolError(); }
      });
      server.registerTool("list_research_runs", {
        title: "List saved research runs",
        description: "Read persistent run IDs and idea counts from the PostgreSQL team memory, not the conversation.",
        inputSchema: z.object({ limit: z.number().int().min(1).max(20).default(10) }),
        annotations: { readOnlyHint: true },
      }, async ({ limit }) => {
        try { return toolResult(await recentRuns(limit)); }
        catch { return safeToolError(); }
      });
      server.registerTool("get_research_run", {
        title: "Recall one research run",
        description: "Retrieve the saved versioned proposals and persistent idea IDs by research run ID.",
        inputSchema: z.object({ run_id: z.string().uuid() }),
        annotations: { readOnlyHint: true },
      }, async ({ run_id }) => {
        try { return toolResult(await getRun(run_id)); }
        catch { return safeToolError(); }
      });
      // Write tools must be added only after live auth and read-back testing.
      return server;
    });
    return mcpHandler.fetch(request);
  },
);

Deno.serve((request) => {
  if (!enabled()) {
    return new Response("Research MCP is not enabled", {
      status: 503, headers: { "Cache-Control": "no-store" },
    });
  }
  return handler(request);
});
