"""Real API tests for Owner email claim, invitations, password reset and privilege boundaries."""
import pytest
from fastapi.testclient import TestClient

import backend.api as server
import backend.account_onboarding as onboarding
from backend.team import create_member
from research_workbench.core import session_factory

OWNER = "2265176686@qq.com"
SERVICE = {"Authorization": "Bearer owner-invite-test-key"}


@pytest.fixture
def provision(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WORKER_MODE", "queue")
    monkeypatch.setenv("API_BEARER_TOKEN", "owner-invite-test-key")
    monkeypatch.setenv("TEAM_OWNER_SETUP_ENABLED", "true")
    monkeypatch.setenv("TEAM_OWNER_EMAIL", OWNER)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://atlas.example.test")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "Research Atlas <no-reply@example.test>")
    mailbox = []
    monkeypatch.setattr(onboarding, "_send_email",
                        lambda email, title, token, kind: mailbox.append({
                            "email": email, "token": token, "kind": kind
                        }))
    factory = session_factory("sqlite:///" + str(tmp_path / "identity.db"))
    monkeypatch.setattr(server, "get_factory", lambda: factory)
    with TestClient(server.app) as client:
        yield client, mailbox, factory


def auth(token=None):
    return {**SERVICE, **({"X-Research-Session": token} if token else {})}


def login(client, email, password):
    return client.post("/api/auth/login", headers=auth(),
                       json={"email": email, "password": password})


def claim(client, mailbox, *, email=OWNER):
    response = client.post("/api/account/owner/request", headers=auth(),
                           json={"email": email})
    assert response.status_code == 202, response.text
    if email != OWNER:
        return None
    assert len(mailbox) >= 1
    return mailbox[-1]["token"]


def redeem(client, token, password="this-is-a-good-secret-password-2026"):
    return client.post("/api/account/setup/redeem", headers=auth(),
                       json={"token": token, "password": password})


def test_owner_claim_rejects_unverified_and_is_single_use(provision):
    client, mailbox, factory = provision
    assert client.post("/api/account/owner/request",
                       json={"email": OWNER}).status_code == 401
    claim(client, mailbox, email="someone@other.test")
    assert mailbox == []
    assert login(client, OWNER, "any-password").status_code == 401
    token = claim(client, mailbox)
    assert mailbox[0]["email"] == OWNER
    assert token not in str(client.post("/api/account/owner/request", headers=auth(),
                        json={"email": OWNER}).json())
    assert len(mailbox) == 1  # rate limit blocks link spam
    assert redeem(client, "x" * 64).status_code == 410
    assert redeem(client, token, "short").status_code == 422
    accepted = redeem(client, token)
    assert accepted.status_code == 200, accepted.text
    assert redeem(client, token).status_code == 410
    signed = login(client, OWNER, "this-is-a-good-secret-password-2026")
    assert signed.status_code == 200
    assert signed.json()["member"]["role"] == "owner"
    owner_session = signed.json()["token"]
    current = client.get("/api/auth/me", headers=auth(owner_session)).json()["member"]
    demote = client.patch("/api/team/members/" + current["id"], headers=auth(owner_session),
                          json={"role": "admin"})
    assert demote.status_code == 422
    remove = client.patch("/api/team/members/" + current["id"], headers=auth(owner_session),
                          json={"active": False})
    assert remove.status_code == 422
    assert client.post("/api/account/owner/request", headers=auth(),
                       json={"email": OWNER}).status_code == 409


def test_owner_invites_admin_and_admin_cannot_escalate(provision):
    client, mailbox, factory = provision
    token = claim(client, mailbox)
    assert redeem(client, token).status_code == 200
    owner = login(client, OWNER, "this-is-a-good-secret-password-2026").json()["token"]
    payload = {"email": "admin@lab.test", "name": "Lab Admin", "role": "admin"}
    created = client.post("/api/team/invitations", headers=auth(owner), json=payload)
    assert created.status_code == 202, created.text
    assert mailbox[-1]["kind"] == "invite"
    assert mailbox[-1]["email"] == payload["email"]
    assert mailbox[-1]["token"] not in created.text
    record = client.get("/api/team/invitations", headers=auth(owner))
    assert record.status_code == 200
    assert record.json()["items"][0]["status"] == "pending"
    invite_token = mailbox[-1]["token"]
    assert redeem(client, invite_token).status_code == 200
    assert redeem(client, invite_token).status_code == 410
    admin_result = login(client, "admin@lab.test", "this-is-a-good-secret-password-2026")
    assert admin_result.status_code == 200
    admin = admin_result.json()["token"]
    assert client.post("/api/team/invitations", headers=auth(admin),
                       json={"email": "second@lab.test", "name": "Second Admin",
                             "role": "admin"}).status_code == 403
    invite = client.post("/api/team/invitations", headers=auth(admin),
                         json={"email": "researcher@lab.test", "name": "Researcher",
                               "role": "researcher"})
    assert invite.status_code == 202
    assert redeem(client, mailbox[-1]["token"]).status_code == 200
    researcher = login(client, "researcher@lab.test", "this-is-a-good-secret-password-2026").json()["token"]
    assert client.get("/api/team/invitations", headers=auth(researcher)).status_code == 403
    members = client.get("/api/team/members", headers=auth(owner)).json()["items"]
    editor_id = next(x["id"] for x in members if x["email"] == "researcher@lab.test")
    assert client.patch("/api/team/members/" + editor_id, headers=auth(admin),
                        json={"role": "admin"}).status_code == 403
    assert client.patch("/api/team/members/" + editor_id, headers=auth(owner),
                        json={"role": "admin"}).status_code == 200


def test_password_reset_revokes_all_existing_sessions(provision):
    client, mailbox, _ = provision
    token = claim(client, mailbox)
    assert redeem(client, token).status_code == 200
    active = login(client, OWNER, "this-is-a-good-secret-password-2026").json()["token"]
    unknown = client.post("/api/account/reset/request", headers=auth(),
                          json={"email": "unknown@example.test"})
    assert unknown.status_code == 202
    assert len(mailbox) == 1
    reset = client.post("/api/account/reset/request", headers=auth(),
                        json={"email": OWNER})
    assert reset.status_code == 202
    assert mailbox[-1]["kind"] == "reset"
    result = redeem(client, mailbox[-1]["token"], "replaced-password-super-long-2026")
    assert result.status_code == 200
    assert client.get("/api/auth/me", headers=auth(active)).status_code == 401
    assert login(client, OWNER, "this-is-a-good-secret-password-2026").status_code == 401
    assert login(client, OWNER, "replaced-password-super-long-2026").status_code == 200


def test_existing_admin_owner_claim_requires_mailbox(provision):
    client, mailbox, factory = provision
    with factory() as db:
        create_member(db, OWNER, "Existing Admin", "old-admin-password-long-2026",
                      role="admin", initial=True)
    old_session = login(client, OWNER, "old-admin-password-long-2026").json()["token"]
    token = claim(client, mailbox)
    assert redeem(client, token).status_code == 200
    assert client.get("/api/auth/me", headers=auth(old_session)).status_code == 401
    assert login(client, OWNER, "old-admin-password-long-2026").status_code == 401
    promoted = login(client, OWNER, "this-is-a-good-secret-password-2026")
    assert promoted.status_code == 200
    assert promoted.json()["member"]["role"] == "owner"


def test_fail_closed_without_real_mail_delivery(provision, monkeypatch):
    client, mailbox, _ = provision
    def broken_email(*args):
        raise OSError("mail offline")
    monkeypatch.setattr(onboarding, "_send_email", broken_email)
    response = client.post("/api/account/owner/request", headers=auth(),
                           json={"email": OWNER})
    assert response.status_code == 503
    assert login(client, OWNER, "this-is-a-good-secret-password-2026").status_code == 401


def test_invitation_revocation_is_audited_and_token_cannot_be_used(provision):
    client, mailbox, _ = provision
    assert redeem(client, claim(client, mailbox)).status_code == 200
    owner = login(client, OWNER, "this-is-a-good-secret-password-2026").json()["token"]
    invite = client.post("/api/team/invitations", headers=auth(owner),
                         json={"email": "to-revoke@lab.test", "name": "Revoke Me",
                               "role": "viewer"})
    assert invite.status_code == 202
    invite_token = mailbox[-1]["token"]
    invitation_id = client.get("/api/team/invitations", headers=auth(owner)).json()["items"][0]["id"]
    revoke = client.post("/api/team/invitations/" + invitation_id + "/revoke",
                         headers=auth(owner))
    assert revoke.status_code == 200
    assert redeem(client, invite_token).status_code == 410
    rows = client.get("/api/team/invitations", headers=auth(owner)).json()["items"]
    assert rows[0]["status"] == "revoked"
    audit = client.get("/api/team/audit", headers=auth(owner)).json()["items"]
    assert any(x["action"] == "member.invitation.revoked" for x in audit)
