/** Authorization policy for Supabase OAuth Business Research Advisor.
 *
 * This module does not trust client-provided scope claims or unverified JWT
 * payloads. Call its predicate ONLY AFTER Supabase middleware verifies the
 * JWT and supabase.auth.getUser(token) returns the same user ID.
 */
export interface VerifiedClaims {
  sub?: unknown;
  client_id?: unknown;
  role?: unknown;
  aud?: unknown;
  iss?: unknown;
}
export interface ResearchMcpPolicy {
  projectUrl: string;
  allowedUserIds: string;
  allowedClientIds: string;
  enabled: boolean;
}

export function parseAllowlist(value: string): ReadonlySet<string> {
  const entries = value.split(",").map((s) => s.trim()).filter(Boolean);
  if (!entries.length || entries.some((s) => s === "*" || s.length > 240)) {
    return new Set();
  }
  return new Set(entries);
}

export function isAuthorizedPrincipal(
  claims: VerifiedClaims,
  verifiedUserId: string,
  policy: ResearchMcpPolicy,
): boolean {
  if (!policy.enabled || !verifiedUserId || verifiedUserId.length > 240) return false;
  const userIds = parseAllowlist(policy.allowedUserIds);
  const clientIds = parseAllowlist(policy.allowedClientIds);
  const project = policy.projectUrl.replace(/\/$/, "");
  if (!/^https:\/\/[a-z0-9-]+\.supabase\.co$/.test(project)) return false;
  if (!userIds.size || !clientIds.size) return false;
  if (claims.sub !== verifiedUserId || claims.role !== "authenticated") return false;
  if (claims.iss !== project + "/auth/v1") return false;
  const audience = claims.aud;
  if (!(audience === "authenticated" ||
        (Array.isArray(audience) && audience.includes("authenticated")))) return false;
  if (typeof claims.client_id !== "string" || !clientIds.has(claims.client_id)) return false;
  return userIds.has(verifiedUserId);
}

export function bearerToken(header: string | null): string | null {
  if (!header) return null;
  const m = /^Bearer ([A-Za-z0-9._~-]+)$/.exec(header);
  return m?.[1] && m[1].length < 8192 ? m[1] : null;
}

/** Parse only after a separate signature/user-verification step. */
export function jwtClaimsFromVerifiedToken(jwt: string): VerifiedClaims | null {
  try {
    const parts = jwt.split(".");
    if (parts.length !== 3 || parts[1].length > 8192) return null;
    const padded = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const text = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
    const value = JSON.parse(text);
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}
