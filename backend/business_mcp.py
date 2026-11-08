"""OAuth-protected Streamable HTTP MCP adapter for Business Research Advisor.

Fail-closed, not mounted unless BUSINESS_MCP_ENABLED=true and explicit owner
authorization is present. Uses an external OAuth 2.1 authorization server
(the team's Supabase project) rather than implementing an unsafe custom
authorization server. Supabase JWTs default to aud="authenticated" and do
not support custom OAuth scopes, so exact issuer, audience, authorized subject,
client_id and an independent write allowlist are all enforced server-side.

This is an *adapter*. It doesn't publish an app in ChatGPT or create an Agent.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

# MCP SDK introspects function annotations in module globals.
from backend.business_memory import RunSubmission


@dataclass(frozen=True)
class AuthConfig:
    resource: str
    issuer: str
    jwks_url: str
    allowed_subjects: frozenset[str]
    host: str
    allowed_clients: frozenset[str] = frozenset()
    write_clients: frozenset[str] = frozenset()


def get_auth_config() -> AuthConfig:
    """Read configuration only; never expose raw credentials or URI passwords."""
    if os.getenv("BUSINESS_MCP_ENABLED","").lower().strip()!="true":
        raise RuntimeError("Private MCP endpoint disabled")
    if os.getenv("BUSINESS_AGENT_SHARING_APPROVED","").lower().strip()!="true":
        raise RuntimeError("Owner sharing approval is required")
    resource=os.getenv("BUSINESS_MCP_RESOURCE_URL","").strip()
    issuer=os.getenv("BUSINESS_MCP_ISSUER_URL","").strip()
    jwks_url=os.getenv("BUSINESS_MCP_JWKS_URL","").strip()
    subjects=frozenset(
        x.strip() for x in os.getenv("BUSINESS_MCP_ALLOWED_SUBJECTS","").split(",")
        if x.strip())
    clients=frozenset(
        x.strip() for x in os.getenv("BUSINESS_MCP_ALLOWED_CLIENT_IDS","").split(",")
        if x.strip())
    write_clients=frozenset(
        x.strip() for x in os.getenv("BUSINESS_MCP_ALLOWED_WRITE_CLIENT_IDS","").split(",")
        if x.strip())
    urls=[urlparse(v) for v in (resource,issuer,jwks_url)]
    if not all(u.scheme=="https" and u.hostname and not u.username
               and not u.password and not u.query and not u.fragment
               for u in urls):
        raise RuntimeError("MCP OAuth HTTPS configuration missing or invalid")
    if not resource.endswith("/research-advisor/mcp"):
        raise RuntimeError("Unexpected MCP resource path")
    if not subjects or any(v=="*" or len(v)>200 for v in subjects):
        raise RuntimeError("Explicit approved OAuth subjects required")
    if not clients or any(v=="*" or len(v)>240 for v in clients):
        raise RuntimeError("Explicit approved Supabase OAuth client IDs required")
    if not write_clients.issubset(clients):
        raise RuntimeError("Write-allowed clients must also be approved read clients")
    # Pin to the same single Supabase project: an arbitrary OAuth issuer
    # or JWKS endpoint would make the team's data accessible to strangers.
    if not urls[1].hostname.endswith(".supabase.co"):
        raise RuntimeError("Supabase OAuth issuer must be pinned to project")
    if urls[1].path.rstrip("/")!="/auth/v1":
        raise RuntimeError("Unexpected Supabase OAuth issuer path")
    if (urls[2].hostname!=urls[1].hostname
            or urls[2].path!="/auth/v1/.well-known/jwks.json"):
        raise RuntimeError("Supabase signing keys must come from same project")
    return AuthConfig(resource=resource,issuer=issuer,jwks_url=jwks_url,
                      allowed_subjects=subjects,host=urls[0].hostname,
                      allowed_clients=clients,write_clients=write_clients)


class OAuthJwtVerifier:
    """JWT verifier wrapper; no production token can be accepted by default."""

    def __init__(self, config: AuthConfig):
        self.config=config
        self._key_client=None

    def _validate(self, token: str):
        import jwt
        from mcp.server.auth.provider import AccessToken
        if not token or len(token)>8192:
            return None
        try:
            if self._key_client is None:
                self._key_client=jwt.PyJWKClient(self.config.jwks_url,
                                                 cache_jwk_set=True,lifespan=300)
            key=self._key_client.get_signing_key_from_jwt(token).key
            decoded=jwt.decode(
                token,key,algorithms=["RS256","ES256"],
                audience="authenticated",issuer=self.config.issuer,
                leeway=30,options={"require":["exp","iat","iss","aud","sub","client_id"]},
            )
            subject=str(decoded.get("sub",""))
            client_id=str(decoded.get("client_id",""))
            if (not subject or subject not in self.config.allowed_subjects
                    or not client_id or client_id not in self.config.allowed_clients
                    or decoded.get("role")!="authenticated"):
                return None
            # Supabase OAuth supports standard OIDC scopes only. Internal
            # research privileges come from server-side allowlists, NOT any
            # untrusted JWT "scope" or "permissions" claims.
            effective={"research:read"}
            if (client_id in self.config.write_clients
                    and os.getenv("BUSINESS_MCP_WRITE_ENABLED","").lower().strip()=="true"):
                effective.add("research:write")
            return AccessToken(
                token=token,client_id=client_id,
                scopes=sorted(effective),resource=self.config.resource,
            )
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError,
                ConnectionError, OSError):
            return None
        except Exception:
            # Never log raw JWT, keys, issuer hostnames or driver traces.
            return None

    async def verify_token(self, token: str):
        return await asyncio.to_thread(self._validate,token)


def build_mcp_server(config: AuthConfig):
    from pydantic import AnyHttpUrl
    from mcp.server import MCPServer
    from mcp.server.auth.middleware.auth_context import get_access_token
    from mcp.server.auth.settings import AuthSettings
    from mcp.server.transport_security import TransportSecuritySettings
    from sqlalchemy import select

    from backend.business_memory import (
        BusinessAgentRun, _context, _digest, _run_view, persist_run
    )
    from research_workbench.core import session_factory

    def require_scope(value: str):
        token=get_access_token()
        if token is None or value not in set(token.scopes):
            raise PermissionError("The authorized research scope is required")
        if (os.getenv("BUSINESS_MCP_ENABLED","").strip().lower()!="true"
                or os.getenv("BUSINESS_AGENT_SHARING_APPROVED","").strip().lower()!="true"):
            raise PermissionError("Research Agent integration disabled")

    mcp=MCPServer(
        "Team Research Advisor",
        token_verifier=OAuthJwtVerifier(config),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(config.issuer),
            resource_server_url=AnyHttpUrl(config.resource),
            # Supabase access JWTs use aud="authenticated", even though
            # the MCP protected resource is a distinct URL. We instead
            # enforce project issuer + client_id + user UUID at every request.
            required_scopes=[],
            validate_token_resource=False,
        ),
    )

    @mcp.tool(description="Read the team's approved public-safe research metadata and real meeting review history from PostgreSQL; return a context hash.")
    def get_research_context() -> dict:
        require_scope("research:read")
        with session_factory()() as db:
            evidence=_context(db)
            return {"context_hash":_digest(evidence),"context":evidence}

    @mcp.tool(description="Read the latest confirmed versioned research runs from PostgreSQL, not model memory.")
    def get_run_history(limit: int = 10) -> dict:
        require_scope("research:read")
        if not 1 <= limit <= 20:
            raise ValueError("Limit must be from 1 to 20")
        with session_factory()() as db:
            rows=db.scalars(select(BusinessAgentRun).order_by(
                BusinessAgentRun.created_at.desc(),BusinessAgentRun.id.desc()
            ).limit(limit)).all()
            return {"items":[_run_view(db,row) for row in rows]}

    @mcp.tool(description="Retrieve a previously saved research run and verify its persistent idea IDs.")
    def get_research_run(run_id: str) -> dict:
        require_scope("research:read")
        try:
            uuid.UUID(run_id)
        except ValueError:
            raise ValueError("Invalid research run identifier") from None
        with session_factory()() as db:
            row=db.get(BusinessAgentRun,run_id)
            if row is None:
                raise ValueError("Research run does not exist")
            return _run_view(db,row)

    @mcp.tool(description="Persist evidence-checked versioned proposals. Disabled until admin explicitly enables write access for a verified OAuth client; human feedback cannot be written by an Agent.")
    def submit_research_run(submission: RunSubmission) -> dict:
        require_scope("research:read")
        require_scope("research:write")
        with session_factory()() as db:
            return persist_run(db,submission)

    from urllib.parse import urlparse
    parsed=urlparse(config.resource)
    security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[parsed.hostname],
        allowed_origins=["https://chatgpt.com","https://chat.openai.com"],
    )
    return mcp,mcp.streamable_http_app(
        host=parsed.hostname,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )


def mount_mcp(app):
    """Attach an OAuth protected MCP app under /research-advisor when opted in."""
    config=get_auth_config()
    mcp,mcp_app=build_mcp_server(config)
    app.mount("/research-advisor",mcp_app)
    app.state.research_advisor_mcp=mcp
