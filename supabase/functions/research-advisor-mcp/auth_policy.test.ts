import { assertEquals, assert } from "jsr:@std/assert@1";
import {
  bearerToken, isAuthorizedPrincipal, jwtClaimsFromVerifiedToken, parseAllowlist,
} from "./auth_policy.ts";

const policy = {
  enabled: true,
  projectUrl: "https://sample-project.supabase.co",
  allowedUserIds: "11111111-1111-4111-8111-111111111111",
  allowedClientIds: "approved-oauth-client",
};
const user = "11111111-1111-4111-8111-111111111111";
const claims = {
  sub: user, client_id: "approved-oauth-client", role: "authenticated",
  aud: "authenticated", iss: "https://sample-project.supabase.co/auth/v1",
};

Deno.test("only the precise approved OAuth client and Supabase user can read", () => {
  assert(isAuthorizedPrincipal(claims, user, policy));
  assertEquals(isAuthorizedPrincipal({...claims, sub:"attacker"},user,policy),false);
  assertEquals(isAuthorizedPrincipal({...claims, client_id:"another-client"},user,policy),false);
  assertEquals(isAuthorizedPrincipal({...claims, role:"service_role"},user,policy),false);
  assertEquals(isAuthorizedPrincipal({...claims, aud:"another-audience"},user,policy),false);
  assertEquals(isAuthorizedPrincipal({...claims, iss:"https://another.supabase.co/auth/v1"},user,policy),false);
  assertEquals(isAuthorizedPrincipal({...claims, client_id:undefined},user,policy),false);
  assertEquals(isAuthorizedPrincipal(claims,"another-user",policy),false);
  assertEquals(isAuthorizedPrincipal(claims,user,{...policy,enabled:false}),false);
});

Deno.test("missing or wildcard allowlist never authorizes", () => {
  assertEquals(parseAllowlist("").size, 0);
  assertEquals(parseAllowlist("*").size, 0);
  assertEquals(isAuthorizedPrincipal(claims,user,{...policy,allowedUserIds:""}),false);
  assertEquals(isAuthorizedPrincipal(claims,user,{...policy,allowedClientIds:"*"}),false);
  assertEquals(isAuthorizedPrincipal(claims,user,{...policy,projectUrl:"https://random.example.org"}),false);
});

Deno.test("Bearer header parser rejects non-tokens and oversized tokens", () => {
  assertEquals(bearerToken(null),null);
  assertEquals(bearerToken("sb_publishable_publicapikey"),null);
  assertEquals(bearerToken("Bearer eyJ.abc.xyz"),"eyJ.abc.xyz");
  assertEquals(bearerToken("Basic eXk="),null);
  assertEquals(bearerToken("Bearer "+"x".repeat(9000)),null);
  assertEquals(bearerToken("Bearer a b"),null);
});

Deno.test("unverified JWT reader decodes only structurally valid payload", () => {
  const raw=JSON.stringify({...claims,exp:2000000000,iat:1000000000});
  const middle=btoa(raw).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
  const result=jwtClaimsFromVerifiedToken("header."+middle+".signature");
  assertEquals(result?.client_id,"approved-oauth-client");
  assertEquals(jwtClaimsFromVerifiedToken("invalid"),null);
  assertEquals(jwtClaimsFromVerifiedToken("a.!!!.c"),null);
  // Reader alone is not authentication and MUST be followed by the middleware.
});
