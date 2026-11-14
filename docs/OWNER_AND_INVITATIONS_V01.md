# Research Atlas - Owner and Invitation Onboarding V0.1

Status: feature branch only. This is not a production release.

## Scope

Use the existing FastAPI + SQLAlchemy team database and sessions for Owner, invitations, email verification, password setup and reset. No parallel authentication database.

Roles:
- Owner: controls admins and team members; also accesses Development Studio
- Admin: accesses Development Studio and invites researcher/viewer
- Researcher: research operations
- Viewer: read-only

Owner can only be claimed by the configured email after successful mailbox verification. Direct role-edit and direct-member-create endpoints cannot grant Owner.

## Owner setup (initial mailbox: 2265176686@qq.com)

1. Set TEAM_OWNER_EMAIL=2265176686@qq.com and TEAM_OWNER_SETUP_ENABLED=true only on the intended **backend** deployment.
2. Set PUBLIC_APP_URL to its matching HTTPS Vercel environment.
3. Set up an email provider. Prefer Resend HTTPS on Render Free, using RESEND_API_KEY and EMAIL_FROM for an authorized, verified sender. Alternatively SMTP on a host whose outbound ports are allowed.
4. Visit /account/setup and enter the configured Owner email; a single-use 30-minute verification link is emailed to that address. The API never returns the token.
5. Open the link and choose a password. The server verifies the token hash, creates/promotes Owner, revokes any prior sessions for the promoted user, and creates an audit record.
6. Log in at /devstudio; open /account/team to invite members.
7. After successful claim, set TEAM_OWNER_SETUP_ENABLED=false and remove obsolete bootstrap password secrets. Do not publish actual passwords or tokens.

## Invitations and reset

- Owner can invite Admin, Researcher or Viewer; Admin can invite Researcher or Viewer.
- Invitee receives a single-use 7-day link and sets their own password.
- Unused invites can be revoked; list shows pending, expired, used or revoked.
- Password reset sends a 30-minute single-use link; redeeming revokes existing login sessions.
- All privilege changes and verified activation are auditable.
- Legacy direct temporary-password member creation is disabled in production unless explicitly re-enabled. Use invites instead.

## Mail delivery on Render Free

Render has blocked outbound SMTP traffic on ports 25, 465 and 587 for Free web services since September 2025:
https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports

Recommended Render backend environment variables:
- RESEND_API_KEY: secret created in provider dashboard; never send it in chat.
- EMAIL_FROM: authorized sender on a domain the provider has verified.
- PUBLIC_APP_URL: HTTPS Vercel preview/production URL corresponding to this backend.
- TEAM_OWNER_EMAIL: 2265176686@qq.com.
- TEAM_OWNER_SETUP_ENABLED=true during bootstrap only.
- TEAM_AUTH_ENABLED=true and existing server API_BEARER_TOKEN.

QQ mailbox is the **recipient**, not necessarily the sender. A valid verified sending domain/account is required. Without provider configuration, the backend returns HTTP 503 and does not issue an account or reveal a token.

Optional SMTP fallback (paid Render or another permissive host): SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USE_SSL, SMTP_USER, SMTP_PASSWORD. Render Free must use an HTTPS provider unless using a supported alternative relay port.

## Routes

FastAPI:
- POST /api/account/owner/request
- POST /api/account/reset/request
- POST /api/account/setup/redeem
- GET/POST /api/team/invitations
- POST /api/team/invitations/{id}/revoke
- Existing /api/team/members, /api/auth/login, /api/auth/me, /api/team/audit preserved.

Next.js:
- /account/setup
- /account/team (verified Admin/Owner only)
- POST /api/account/onboarding
- /devstudio (verified Admin/Owner only)

## Database and release safety

New tables: team_owner_claim and team_enrollment_tickets. Existing team_members.role is a String: no role-column alteration is required. SQLAlchemy create_all only creates missing tables, never safely alters existing columns. Production database migration must be independently reviewed and backed up.

Automated tests cover Owner mailbox proof, token replay/expiry, invitation acceptance/revocation, role boundaries, password reset and session invalidation. Manual real email and browser end-to-end verification require a configured mail provider.

No secrets or credentials in Git history. Do not merge the E2E-only testing probe from the older staging PR into main. Remaining hardening for broader launch: stronger abuse rate limits, provider delivery monitoring, Owner transfer/recovery, optional MFA, and ticket cleanup.
