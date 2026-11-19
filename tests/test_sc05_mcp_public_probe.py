"""Offline no-secret public MCP handshake check."""
from scripts import sc05_mcp_public_probe as p

BASE="https://mcp.example.test"
def good_response(url,*,method="GET",body=None,timeout=30):
    if url.endswith("/api/health"):
        return 200,{"status":"ok"},{}
    if url.endswith("/.well-known/oauth-protected-resource"):
        return 200,{
            "resource":BASE+"/mcp",
            "authorization_servers":[BASE],
            "scopes_supported":["experiments:read","experiments:run"]
        },{}
    if url.endswith("/.well-known/oauth-authorization-server"):
        return 200,{
            "issuer":BASE,"authorization_endpoint":BASE+"/oauth/authorize",
            "token_endpoint":BASE+"/oauth/token",
            "grant_types_supported":["authorization_code","refresh_token"],
            "code_challenge_methods_supported":["S256"]
        },{}
    if url.endswith("/mcp"):
        assert method=="POST"
        assert body == b'{"jsonrpc":"2.0","id":167,"method":"tools/list"}'
        return 401,{},{"bearer_challenge":True}
    raise AssertionError("Unknown endpoint")

def test_correct_public_mcp_handshake_does_not_send_tokens(monkeypatch):
    monkeypatch.setattr(p,"fetch",good_response)
    r=p.probe(BASE)
    assert r["pass"]
    assert r["owner_tokens_used"]==r["model_calls"]==0
    assert all(x["ok"] for x in r["checks"].values())
    assert "Owner OAuth" in r["next_action"]

def test_missing_mcp_bearer_challenge_fails_even_when_health_is_green(monkeypatch):
    def no_challenge(url,**kwargs):
        status,data,extra=good_response(url,**kwargs)
        if url.endswith("/mcp"):
            return 401,{},{"bearer_challenge":False}
        return status,data,extra
    monkeypatch.setattr(p,"fetch",no_challenge)
    result=p.probe(BASE)
    assert not result["pass"]
    assert result["checks"]["api_health"]["ok"]
    assert not result["checks"]["unauthenticated_mcp_challenge"]["ok"]

def test_origin_must_be_https():
    import pytest
    with pytest.raises(ValueError):
        p.probe("http://mcp.example.test")
