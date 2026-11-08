"""OAuth resource-server gates: real Supabase claims, fail closed, no public data."""
from unittest.mock import MagicMock, patch

import pytest

from backend.business_mcp import AuthConfig, OAuthJwtVerifier, get_auth_config

RESOURCE="https://research-atlas-api-test.onrender.com/research-advisor/mcp"
ISSUER="https://example-project.supabase.co/auth/v1"
JWKS="https://example-project.supabase.co/auth/v1/.well-known/jwks.json"
SUBJECT="11111111-1111-4111-8111-111111111111"
CLIENT="22222222-2222-4222-8222-222222222222"


def _settings(monkeypatch):
    monkeypatch.setenv("BUSINESS_MCP_ENABLED","true")
    monkeypatch.setenv("BUSINESS_AGENT_SHARING_APPROVED","true")
    monkeypatch.setenv("BUSINESS_MCP_RESOURCE_URL",RESOURCE)
    monkeypatch.setenv("BUSINESS_MCP_ISSUER_URL",ISSUER)
    monkeypatch.setenv("BUSINESS_MCP_JWKS_URL",JWKS)
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_SUBJECTS",SUBJECT)
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_CLIENT_IDS",CLIENT)
    monkeypatch.delenv("BUSINESS_MCP_ALLOWED_WRITE_CLIENT_IDS",raising=False)
    monkeypatch.delenv("BUSINESS_MCP_WRITE_ENABLED",raising=False)
    monkeypatch.delenv("BUSINESS_MCP_ALLOWED_EXECUTION_CLIENT_IDS",raising=False)
    monkeypatch.delenv("BUSINESS_MCP_EXECUTION_ENABLED",raising=False)
    monkeypatch.delenv("BUSINESS_MCP_DCR_BOOTSTRAP_ENABLED",raising=False)


def test_disabled_without_owner_approval(monkeypatch):
    monkeypatch.delenv("BUSINESS_MCP_ENABLED",raising=False)
    with pytest.raises(RuntimeError,match="disabled"):
        get_auth_config()
    monkeypatch.setenv("BUSINESS_MCP_ENABLED","true")
    monkeypatch.setenv("BUSINESS_AGENT_SHARING_APPROVED","false")
    with pytest.raises(RuntimeError,match="approval"):
        get_auth_config()


def test_requires_https_same_supabase_issuer_and_explicit_allowlists(monkeypatch):
    _settings(monkeypatch)
    config=get_auth_config()
    assert config.resource==RESOURCE
    assert config.host=="research-atlas-api-test.onrender.com"
    assert config.allowed_subjects=={SUBJECT}
    assert config.allowed_clients=={CLIENT}
    assert config.write_clients==set()
    assert config.execution_clients==set()
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_CLIENT_IDS","*")
    with pytest.raises(RuntimeError,match="Explicit approved Supabase"):
        get_auth_config()
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_CLIENT_IDS",CLIENT)
    monkeypatch.setenv("BUSINESS_MCP_JWKS_URL","http://example-project.supabase.co/jwks")
    with pytest.raises(RuntimeError,match="HTTPS"):
        get_auth_config()
    monkeypatch.setenv("BUSINESS_MCP_JWKS_URL","https://attacker.example.org/auth/v1/.well-known/jwks.json")
    with pytest.raises(RuntimeError,match="same project"):
        get_auth_config()
    monkeypatch.setenv("BUSINESS_MCP_JWKS_URL",JWKS)
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_WRITE_CLIENT_IDS","unknown-client")
    with pytest.raises(RuntimeError,match="Write-allowed"):
        get_auth_config()
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_WRITE_CLIENT_IDS","")
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_EXECUTION_CLIENT_IDS","unknown-client")
    with pytest.raises(RuntimeError,match="Execution-allowed"):
        get_auth_config()



def test_dcr_bootstrap_never_authorizes_unregistered_clients(monkeypatch):
    _settings(monkeypatch)
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_CLIENT_IDS","")
    with pytest.raises(RuntimeError,match="Explicit approved"):
        get_auth_config()

    monkeypatch.setenv("BUSINESS_MCP_DCR_BOOTSTRAP_ENABLED","true")
    config=get_auth_config()
    assert config.allowed_clients==set()
    verifier=_mocked_verifier(config)
    with patch("jwt.decode",return_value=_claims()):
        assert verifier._validate("opaque-test-token") is None


def _claims(sub=SUBJECT,client=CLIENT):
    return {"iss":ISSUER,"aud":"authenticated","sub":sub,
            "client_id":client,"role":"authenticated",
            "exp":2000000000,"iat":1000000000,
            "scope":"email","permissions":["research:write"]}


def _mocked_verifier(config):
    verifier=OAuthJwtVerifier(config)
    key_client=MagicMock()
    key_client.get_signing_key_from_jwt.return_value.key="test-key"
    verifier._key_client=key_client
    return verifier


def test_token_validates_project_subject_client_and_server_write_policy(monkeypatch):
    _settings(monkeypatch)
    cfg=get_auth_config()
    verifier=_mocked_verifier(cfg)
    with patch("jwt.decode",return_value=_claims(sub="unknown-user")):
        assert verifier._validate("opaque-test-token") is None
    with patch("jwt.decode",return_value=_claims(client="unapproved-client")):
        assert verifier._validate("opaque-test-token") is None
    with patch("jwt.decode",return_value={**_claims(),"role":"service_role"}):
        assert verifier._validate("opaque-test-token") is None
    with patch("jwt.decode",return_value=_claims()):
        result=verifier._validate("opaque-test-token")
    assert result is not None
    assert result.resource==RESOURCE
    assert result.client_id==CLIENT
    # Untrusted JWT claims can never grant writes.
    assert result.scopes==["research:read"]
    monkeypatch.setenv("BUSINESS_MCP_WRITE_ENABLED","true")
    with patch("jwt.decode",return_value=_claims()):
        still_read_only=verifier._validate("opaque-test-token")
    assert still_read_only.scopes==["research:read"]

    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_WRITE_CLIENT_IDS",CLIENT)
    allowed=_mocked_verifier(get_auth_config())
    with patch("jwt.decode",return_value=_claims()):
        write_capability=allowed._validate("opaque-test-token")
    assert "research:write" in write_capability.scopes



def test_execution_scope_requires_separate_client_allowlist_and_toggle(monkeypatch):
    _settings(monkeypatch)
    monkeypatch.setenv("BUSINESS_MCP_ALLOWED_EXECUTION_CLIENT_IDS",CLIENT)
    cfg=get_auth_config()
    verifier=_mocked_verifier(cfg)
    with patch("jwt.decode",return_value=_claims()):
        without_toggle=verifier._validate("opaque-test-token")
    assert "research:execute" not in without_toggle.scopes

    monkeypatch.setenv("BUSINESS_MCP_EXECUTION_ENABLED","true")
    enabled=_mocked_verifier(get_auth_config())
    with patch("jwt.decode",return_value=_claims()):
        with_execution=enabled._validate("opaque-test-token")
    assert "research:execute" in with_execution.scopes
    assert "research:write" not in with_execution.scopes


def test_invalid_or_expired_supabase_jwt_rejected(monkeypatch):
    _settings(monkeypatch)
    verifier=_mocked_verifier(get_auth_config())
    import jwt
    with patch("jwt.decode",side_effect=jwt.ExpiredSignatureError):
        assert verifier._validate("expired") is None
    with patch("jwt.decode",side_effect=jwt.InvalidAudienceError):
        assert verifier._validate("wrong-audience") is None
    with patch("jwt.decode",return_value=_claims()):
        assert verifier._validate("") is None
    with patch("jwt.decode",return_value=_claims()):
        assert verifier._validate("opaque-test-token") is not None


def test_mcp_server_constructs_with_business_and_topic_advisor_tools(monkeypatch):
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
