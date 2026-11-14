-- Business Research Advisor: additive PostgreSQL schema, 2026-11-07
-- Applies to the SELECTED, BACKED-UP staging database first.
-- Never run this against an unknown DATABASE_URL. No legacy rows are modified.
BEGIN;

CREATE TABLE IF NOT EXISTS business_agent_runs (
    id VARCHAR(36) PRIMARY KEY,
    run_key VARCHAR(120) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    context_hash VARCHAR(64) NOT NULL,
    topic VARCHAR(240) NOT NULL,
    agent_version VARCHAR(80) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'submitted',
    snapshot_json TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_business_agent_runs_run_key
    ON business_agent_runs(run_key);

CREATE TABLE IF NOT EXISTS business_agent_ideas (
    id VARCHAR(36) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL REFERENCES business_agent_runs(id),
    parent_id VARCHAR(36),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    title VARCHAR(240) NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_business_agent_ideas_run_id
    ON business_agent_ideas(run_id);

CREATE TABLE IF NOT EXISTS business_meeting_feedback (
    id VARCHAR(36) PRIMARY KEY,
    idea_id VARCHAR(36) NOT NULL REFERENCES business_agent_ideas(id),
    reviewer_id VARCHAR(36) NOT NULL,
    decision VARCHAR(24) NOT NULL
        CHECK (decision IN ('adopt', 'revise', 'defer', 'reject')),
    novelty INTEGER NOT NULL CHECK (novelty BETWEEN 1 AND 5),
    feasibility INTEGER NOT NULL CHECK (feasibility BETWEEN 1 AND 5),
    scientific_value INTEGER NOT NULL CHECK (scientific_value BETWEEN 1 AND 5),
    testability INTEGER NOT NULL CHECK (testability BETWEEN 1 AND 5),
    comment TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_business_idea_review UNIQUE (idea_id, reviewer_id)
);
CREATE INDEX IF NOT EXISTS ix_business_meeting_feedback_idea_id
    ON business_meeting_feedback(idea_id);
CREATE INDEX IF NOT EXISTS ix_business_meeting_feedback_reviewer_id
    ON business_meeting_feedback(reviewer_id);

-- Lock down the three new tables before the transaction commits.
-- These tables are used by server-side SQLAlchemy only; do not grant Data API access.
ALTER TABLE public.business_agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_agent_ideas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_meeting_feedback ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.business_agent_runs,
                    public.business_agent_ideas,
                    public.business_meeting_feedback FROM PUBLIC;
DO $
DECLARE r TEXT;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('REVOKE ALL ON TABLE public.business_agent_runs, public.business_agent_ideas, public.business_meeting_feedback FROM %I',r);
    END IF;
  END LOOP;
END $;

COMMIT;

-- Verify separately, with read-only queries:
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public'
--     AND tablename LIKE 'business_%';
-- SELECT count(*) FROM business_agent_runs;
-- SELECT count(*) FROM business_agent_ideas;
-- SELECT count(*) FROM business_meeting_feedback;
