"""Staging-only simulated mailbox. NEVER import in a regular application deployment.

Protected by the exact preapproved PostgreSQL TEST database/schema and service
identity. No real email is sent. Tokens are held in process memory and are
visible ONLY to signed-in team admins through the service-authenticated API.
"""
from __future__ import annotations

import os
import time
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException
from sqlalchemy import text

EXPECTED_DB = "research_atlas_test_db"
EXPECTED_SCHEMA = "atlas_devstudio_e2e_20261114"
EXPECTED_SERVICE = "research-atlas-devstudio-e2e-ejmh"
TEST_DOMAIN = "@research-atlas.invalid"
INBOX: list[dict[str, object]] = []


def guard(db) -> None:
    db_name = urlsplit(os.getenv("DATABASE_URL", "")).path.lstrip("/")
    if (
        os.getenv("DEVSTUDIO_E2E_ISOLATED") != "1"
        or os.getenv("ACCOUNT_EMAIL_MODE") != "preview_inbox"
        or os.getenv("TEAM_OWNER_EMAIL", "").lower() != "owner-sandbox" + TEST_DOMAIN
        or db_name != EXPECTED_DB
    ):
        raise HTTPException(404, "Simulated mailbox is unavailable")
    if db.bind.dialect.name != "postgresql":
        raise HTTPException(404, "Simulated mailbox requires isolated PostgreSQL")
    schema = db.execute(text("SELECT current_schema()")).scalar_one()
    if schema != EXPECTED_SCHEMA:
        raise HTTPException(404, "Simulated mailbox requires isolated schema")


def install(api) -> None:
    from backend import account_onboarding

    with api.get_factory()() as db:
        guard(db)

    def simulated_send(to_address: str, title: str, token: str, kind: str) -> None:
        if not to_address.lower().endswith(TEST_DOMAIN):
            raise RuntimeError("Sandbox cannot deliver to any real email address")
        if kind not in ("owner", "invite", "reset"):
            raise RuntimeError("Unexpected sandbox mail kind")
        base = os.getenv("PUBLIC_APP_URL", "").rstrip("/")
        url = urlsplit(base)
        if url.scheme != "https" or not url.hostname or not url.hostname.endswith(".vercel.app"):
            raise RuntimeError("Sandbox app URL must be a protected Vercel preview")
        now = int(time.time())
        expiry = {"owner": 1800, "invite": 7 * 86400, "reset": 1800}[kind]
        INBOX.append({
            "recipient": to_address,
            "subject": title,
            "kind": kind,
            "link": base + "/account/setup#token=" + token,
            "received_at": now,
            "expires_at": now + expiry,
        })
        if len(INBOX) > 24:
            del INBOX[:-24]

    # Replaces the external transport ONLY in the isolated executable.
    account_onboarding._send_email = simulated_send

    @api.app.get("/api/account/test-inbox", dependencies=[Depends(api.authenticate)])
    def view_inbox(
        actor=Depends(api.require_admin),
        db=Depends(api.get_db),
    ):
        guard(db)
        now = int(time.time())
        return {
            "mode": "SIMULATED",
            "real_email_verified": False,
            "notice": "测试收件箱：不发送真实邮件，也不证明邮箱所有权",
            "items": [message for message in reversed(INBOX)
                      if int(message["expires_at"]) > now],
        }
