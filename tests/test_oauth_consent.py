"""The OAuth consent is a minimal Render-hosted UI and must fail closed."""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from backend.oauth_consent import router


@pytest.fixture
def client(monkeypatch):
    app=FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_off_by_default(client,monkeypatch):
    monkeypatch.delenv("OAUTH_CONSENT_ENABLED",raising=False)
    assert client.get("/oauth/consent").status_code==404
    assert client.get("/oauth/consent/app.js").status_code==404


def test_configuration_requires_project_and_public_key(client,monkeypatch):
    monkeypatch.setenv("OAUTH_CONSENT_ENABLED","true")
    monkeypatch.delenv("OAUTH_CONSENT_PUBLISHABLE_KEY",raising=False)
    assert client.get("/oauth/consent").status_code==503
    monkeypatch.setenv("OAUTH_CONSENT_SUPABASE_URL","https://attacker.example")
    monkeypatch.setenv("OAUTH_CONSENT_PUBLISHABLE_KEY","sb_publishable_abcdef1234567890")
    assert client.get("/oauth/consent/app.js").status_code==503


def test_browser_client_and_consent_have_strict_headers(client,monkeypatch):
    monkeypatch.setenv("OAUTH_CONSENT_ENABLED","true")
    monkeypatch.setenv("OAUTH_CONSENT_SUPABASE_URL","https://team-example.supabase.co")
    monkeypatch.setenv("OAUTH_CONSENT_PUBLISHABLE_KEY","sb_publishable_abcdef1234567890")
    page=client.get("/oauth/consent")
    js=client.get("/oauth/consent/app.js")
    assert page.status_code==200
    assert js.status_code==200
    assert "supabase-js@2.86.0" in js.text
    assert "getAuthorizationDetails" in js.text
    assert "approveAuthorization" in js.text
    assert "denyAuthorization" in js.text
    assert "signInWithOtp" in js.text
    assert "sb_publishable_abcdef1234567890" in js.text
    assert "sb_publishable_abcdef1234567890" not in page.text
    assert page.headers["cache-control"]=="no-store, private"
    assert js.headers["x-content-type-options"]=="nosniff"
    assert "default-src 'none'" in page.headers["content-security-policy"]
    assert "https://team-example.supabase.co" in page.headers["content-security-policy"]
    assert "onclick" not in page.text


def test_publishable_api_key_must_not_be_privileged(client,monkeypatch):
    monkeypatch.setenv("OAUTH_CONSENT_ENABLED","true")
    monkeypatch.setenv("OAUTH_CONSENT_SUPABASE_URL","https://team-example.supabase.co")
    for key in ("sb_secret_dont-disclose","eyJhbGciOiJIUzI1NiJ9",""):
        monkeypatch.setenv("OAUTH_CONSENT_PUBLISHABLE_KEY",key)
        assert client.get("/oauth/consent").status_code==503
