"""OAuth-protected Streamable HTTP MCP adapter for Business Research Advisor.

Fail-closed, not mounted unless BUSINESS_MCP_ENABLED=true and explicit owner
authorization is present. Uses an external OAuth 2.1 authorization server
(Auth0/Entra/etc) rather than implementing an unsafe custom auth server.
JWT audience, issuer, subject allowlist and scopes are verified per request.

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
    urls=[urlparse(v) for v in (resource,issuer,jwks_url)]
    if not all(u.scheme=="https" and u.hostname and not u.username
               and not u.password and not u.query and not u.fragment
               for u in urls):
        raise RuntimeError("MCP OAuth HTTPS configuration missing or invalid")
    if not resource.endswith("/research-advisor/mcp"):
        raise RuntimeError("Unexpected MCP resource path")
    if not subjects or any(v=="*" or len(v)>200 for v in subjects):
        raise RuntimeError("Explicit approved OAuth subjects required")
    return AuthConfig(resource=resource,issuer=issuer,jwks_url=jwks_url,
                      allowed_subjects=subjects,host=urls[0].hostname)


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
                token,key,algorithms=["RS256"],
                audience=self.config.resource,issuer=self.config.issuer,
                leeway=30,options={"require":["exp","iat","iss","aud","sub"]},
            )
            subject=str(decoded.get("sub",""))
            scopes=set(str(decoded.get("scope","")).split())
            scopes.update(decoded.get("permissions",[])
                          if isinstance(decoded.get("permissions"),list) else [])
            if subject not in self.config.allowed_subjects:
                return None
            if "research:read" not in scopes:
                return None
            return AccessToken(
                token=token,
                client_id=str(decoded.get("azp","approved-oauth-client"))[:240],
                scopes=sorted(scopes),
                resource=self.config.resource,
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
            required_scopes=["research:read"],
            validate_token_resource=True,
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

    @mcp.tool(description="Save evidence-checked, versioned scientific proposals to team PostgreSQL. Requires research:write scope; human review cannot be written by an Agent.")
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
