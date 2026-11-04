# Shared Team Workspace · 10-member laboratory setup

**Status:** GitHub implementation with CI tests. No Render/PostgreSQL service has been provisioned yet.

This system stores exactly **one shared research profile** and one shared paper/idea corpus for the lab. Each human has a distinct account and role for permissions and an audit trail. This is not ten isolated personal knowledge stores.

## Data model

- Existing \`profiles\` (id=1): one team profile JSON. Its \`team\` (name, mission, priorities), \`research_lines\`, \`datasets\`, \`methods\`, \`goals\`, and \`excluded_terms\` fields are shared.
- Existing \`papers\`, \`ideas\`, \`evidence\`, \`events\`, \`research_tasks\`: unchanged and shared. Pre-existing records are kept.
- New \`team_members\`: email, display name, Argon2 password hash, role, active flag.
- New \`team_sessions\`: SHA-256 hashes of random opaque session tokens, expiry and revocation.
- New \`team_profile_revisions\`: immutable JSON snapshots and editor attribution.
- New \`team_audit\`: audit log for member creation/changes, profile updates, idea feedback and task creation.
- New \`team_login_throttle\`: persistent protection against repeated sign-in attempts.

### Roles

| Role | Shared library | Run Agent / feedback | Update profile | Manage members / audit |
|---|---|---|---|---|
| admin | Read | Yes | Yes | Yes |
| researcher | Read | Yes | Read only | No |
| viewer | Read | No | Read only | No |

All roles see the same underlying paper/idea records. The Agent reads the shared team profile, and paper ingestion updates the same literature corpus.

## Local setup

Start with the existing deployment steps in \`README.md\`. After installing Python dependencies:

\`\`\`bash
python -m backend.team_cli bootstrap-admin --email admin@your-institution.org --name "Team Admin"
\`\`\`

The CLI prompts for a new password (12+ characters) without printing or storing the plaintext in source code. Run it **once**, pointing \`DATABASE_URL\` at the database used by the backend API. If the first administrator already exists, the CLI refuses to repeat bootstrap.

For the FastAPI process:

\`\`\`text
APP_ENV=production
TEAM_AUTH_ENABLED=true
DATABASE_URL=postgresql+psycopg://<USER>:<PASSWORD>@<DBHOST>:5432/<DB>?sslmode=require
API_BEARER_TOKEN=<generate a long independent random server key>
\`\`\`

For the Next.js Vercel deployment:

\`\`\`text
TEAM_AUTH_ENABLED=true
BACKEND_URL=https://<your-fastapi-service>
API_BEARER_TOKEN=<same service key as FastAPI>
\`\`\`

The \`APP_PASSWORD\` legacy shared password is **not used** once team mode is enabled. Keep \`SESSION_SECRET\` for compatibility while migrating. Never prefix server credentials with \`NEXT_PUBLIC_\`.

**Activation order matters:** (1) create persistent Postgres, (2) deploy API and verify health, (3) bootstrap administrator in the exact same database, (4) turn on \`TEAM_AUTH_ENABLED\` in API, (5) turn on team mode on Vercel, (6) sign in as admin and create the other nine users. Deploy the worker with the same database URL.

### In-app onboarding

1. Team admin signs in using email/password instead of the old shared workspace password.
2. Open **系统状态 → 团队成员与权限**, add researchers/viewers with a **temporary password of 12+ characters**. Communicate that password through a separate secure channel.
3. Go to **团队研究画像**, edit the shared research profile JSON. The profile is versioned: concurrent edits with outdated versions are rejected (409).
4. Researchers can read that profile, run searches, create research jobs and give idea feedback.
5. Viewers can read papers, ideas, logs and reports but cannot modify research tasks or the profile.

## Database selection

For the current team size, a **managed PostgreSQL** instance is enough. Render Postgres, Supabase and Neon all use PostgreSQL; selecting Render Postgres simplifies hosting, while Supabase adds integrated Auth/Storage features you do not currently require. The application uses standard SQLAlchemy/PostgreSQL tables and is not locked to any provider.

### Production checklist

- Turn on point-in-time restore/backups appropriate to your retention requirements and test a recovery.
- Use TLS database connections, private networking where available, separate database credentials, and restrict DB reachability.
- Keep both the API and its independent Worker running against the same persistent DB.
- Keep \`API_BEARER_TOKEN\` private to Next.js and backend; all team API endpoints require it **and** a valid per-member session token when team mode is enabled.
- Set hosting ingress limits / WAF rules on \`/api/login\`. Basic persisted throttling exists but is not a substitute for edge abuse protection.
- Protect Vercel preview deployments, especially if they share production secrets.
- No email verification, automated invites, self-service password reset, MFA or SSO yet. Accounts are created by an administrator; for ten people, establish a secure account-recovery protocol before relying on it for critical data.
- Audit logs are stored in the same DB; protect them with regular backups and consider export to immutable logging for stronger compliance.
- Store private PDFs outside GitHub, using object storage with access policies.
- Database model is still initialized with \`create_all\`. Plan Alembic migrations before further production schema evolution.

### Migration from personal MVP

This change **adds new tables** and does not delete or rename the existing \`papers\`, \`ideas\`, \`events\` or \`profiles\` tables. The existing Profile id=1 becomes the initial shared team profile. An administrator's first saved edit creates team profile revision V1; prior unversioned JSON remains until edited. Back up the database before enabling team auth.

## Known limits

One laboratory/team only. User accounts are individual, but there is no tenant-scoped isolation for hosting multiple unrelated teams. Work history for existing single-user jobs has no actor attribution; new writes after team mode is enabled include audit actor IDs. Multiple independent workers can process queued tasks, but crash recovery and strict transactional job orchestration remain future work.
