"""OAuth resource-server gates: no accidental public research API access."""
from unittest.mock import MagicMock, patch

import pytest

from backend.business_mcp import AuthConfig, OAuthJwtVerifier, get_auth_config


RESOURCE="https://research-atlas-api-test.onrender.com/research-advisor/mcp"
ISSUER="https://idp.example.org/"
JWKS="https://idp.example.org/.well-known/jwks.json"


def _settings(monkeypatch):
    monkeypatch.setenv("BUSINESS_MCP_ENABLED","true")
    monkeypatch.setenv("BUSINESS_AGENT_SHARING_APPROVED","true")
    monkeypatch.setenv("BUSINESS_MCP_RESOURCE_URL",RESOURCE)
    monkeypatch.setenv("BUSINESS_MCP_ISSUER_URL",ISSUER)
    monkeypatch.setenv("BUSINESS_MCP_JWKS_URL",JWKS)
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_SUBJECTS","research-team-owner")


def test_disabled_without_owner_approval(monkeypatch):
    monkeypatch.delenv("BUSINESS_MCP_ENABLED",raising=False)
    with pytest.raises(RuntimeError,match="disabled"):
        get_auth_config()
    monkeypatch.setenv("BUSINESS_MCP_ENABLED","true")
    monkeypatch.setenv("BUSINESS_AGENT_SHARING_APPROVED","false")
    with pytest.raises(RuntimeError,match="approval"):
        get_auth_config()


def test_requires_https_scopes_and_explicit_authorized_identity(monkeypatch):
    _settings(monkeypatch)
    config=get_auth_config()
    assert config.resource==RESOURCE
    assert config.host=="research-atlas-api-test.onrender.com"
    assert config.allowed_subjects=={"research-team-owner"}
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_SUBJECTS","*")
    with pytest.raises(RuntimeError,match="Explicit approved"):
        get_auth_config()
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_SUBJECTS","research-team-owner")
    monkeypatch.setenv("BUSINESS_MCP_JWKS_URL","http://idp.example.org/jwks")
    with pytest.raises(RuntimeError,match="HTTPS"):
        get_auth_config()


def test_verifier_rejects_unapproved_subject_or_wrong_scope(monkeypatch):
    _settings(monkeypatch)
    config=get_auth_config()
    verifier=OAuthJwtVerifier(config)
    key_client=MagicMock()
    key_client.get_signing_key_from_jwt.return_value.key="test-key"
    verifier._key_client=key_client
    verified={
        "iss":ISSUER,"aud":RESOURCE,"sub":"unknown-user",
        "scope":"research:read research:write","exp":2000000000,
        "iat":1000000000,
    }
    with patch("jwt.decode",return_value=verified):
        assert verifier._validate("opaque-test-token") is None
    verified["sub"]="research-team-owner"
    verified["scope"]="research:write"
    with patch("jwt.decode",return_value=verified):
        assert verifier._validate("opaque-test-token") is None
    verified["scope"]="research:read research:write"
    with patch("jwt.decode",return_value=verified):
        bearer=verifier._validate("opaque-test-token")
    assert bearer is not None
    assert bearer.resource==RESOURCE
    assert "research:write" in bearer.scopes
    assert verifier._validate("") is None


def test_bad_jwt_is_rejected_without_secrets():
    verifier=OAuthJwtVerifier(AuthConfig(
        RESOURCE,ISSUER,JWKS,frozenset({"research-team-owner"}),
        "research-atlas-api-test.onrender.com"
    ))
    with patch("jwt.PyJWKClient") as cls:
        cls.return_value.get_signing_key_from_jwt.side_effect=ValueError("bad jwt")
        assert verifier._validate("bad-token") is None


def test_oauth_server_constructs_with_four_tools_only(monkeypatch):
    _settings(monkeypatch)
    from backend.business_mcp import build_mcp_server
    mcp,asgi=build_mcp_server(get_auth_config())
    assert mcp.session_manager is not None
    assert asgi is not None
    assert any("mcp" in getattr(route,"path","") for route in asgi.routes)


def test_mcp_http_rejects_anonymous_tool_calls(monkeypatch):
    _settings(monkeypatch)
    from fastapi.testclient import TestClient
    from backend.business_mcp import build_mcp_server
    _server,asgi=build_mcp_server(get_auth_config())
    with TestClient(asgi) as client:
        response=client.post(
            "/mcp",
            json={"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}},
            headers={
                "Host":"research-atlas-api-test.onrender.com",
                "Accept":"application/json, text/event-stream",
                "Mcp-Protocol-Version":"2025-06-18",
            },
        )
    assert response.status_code==401
    assert "www-authenticate" in response.headers
    assert "SECRET" not in response.text
