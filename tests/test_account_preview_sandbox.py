"""The preview-only inbox can never deliver to a real address or other DB."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

from backend import account_onboarding, account_preview_sandbox


class DummySession:
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    def __init__(self, schema=account_preview_sandbox.EXPECTED_SCHEMA):
        self.schema = schema
    def execute(self, _query):
        return SimpleNamespace(scalar_one=lambda: self.schema)
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        pass


def configure(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://somebody:masked@localhost/research_atlas_test_db")
    monkeypatch.setenv("DEVSTUDIO_E2E_ISOLATED", "1")
    monkeypatch.setenv("ACCOUNT_EMAIL_MODE", "preview_inbox")
    monkeypatch.setenv("TEAM_OWNER_EMAIL", "owner-sandbox@research-atlas.invalid")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://branch-preview.vercel.app")


def test_sandbox_rejects_wrong_schema_and_flag(monkeypatch):
    configure(monkeypatch)
    account_preview_sandbox.guard(DummySession())
    with pytest.raises(HTTPException):
        account_preview_sandbox.guard(DummySession("public"))
    monkeypatch.setenv("DEVSTUDIO_E2E_ISOLATED", "0")
    with pytest.raises(HTTPException):
        account_preview_sandbox.guard(DummySession())
    monkeypatch.setenv("DEVSTUDIO_E2E_ISOLATED", "1")
    monkeypatch.setenv("TEAM_OWNER_EMAIL", "2265176686@qq.com")
    with pytest.raises(HTTPException):
        account_preview_sandbox.guard(DummySession())
    monkeypatch.setenv("TEAM_OWNER_EMAIL", "owner-sandbox@research-atlas.invalid")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user@localhost/production")
    with pytest.raises(HTTPException):
        account_preview_sandbox.guard(DummySession())


def test_sandbox_captures_test_mail_but_never_real_email(monkeypatch):
    configure(monkeypatch)
    sandbox = account_preview_sandbox
    prev_sender = account_onboarding._send_email
    sandbox.INBOX.clear()
    dummy = SimpleNamespace(
        get_factory=lambda: lambda: DummySession(),
        app=FastAPI(),
        authenticate=lambda: None,
        require_admin=lambda: None,
        get_db=lambda: None,
    )
    try:
        sandbox.install(dummy)
        account_onboarding._send_email(
            "owner-sandbox@research-atlas.invalid", "Owner test",
            "safe-test-token-that-would-be-random-in-practice", "owner"
        )
        assert len(sandbox.INBOX) == 1
        assert sandbox.INBOX[0]["link"].startswith(
            "https://branch-preview.vercel.app/account/setup#token="
        )
        with pytest.raises(RuntimeError):
            account_onboarding._send_email(
                "2265176686@qq.com", "Not a test recipient", "fake-token", "owner"
            )
        assert len(sandbox.INBOX) == 1
    finally:
        account_onboarding._send_email = prev_sender
        sandbox.INBOX.clear()
