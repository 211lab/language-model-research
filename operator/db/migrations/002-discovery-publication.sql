-- Applied to already-running operator databases. Keep this idempotent: the
-- original init.sql only runs when PostgreSQL creates a fresh volume.
CREATE TABLE IF NOT EXISTS discovered_local_models (
    identity_key TEXT PRIMARY KEY,
    model_ref TEXT NOT NULL,
    display_name TEXT NOT NULL,
    source_repo TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_revision TEXT NOT NULL DEFAULT 'main',
    source_snapshot TEXT NOT NULL DEFAULT '',
    eligibility TEXT NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_id TEXT REFERENCES research_runs(id),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS publication_jobs (
    id TEXT PRIMARY KEY,
    research_job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    cohort TEXT NOT NULL CHECK (cohort IN ('editorial', 'assistant')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'blocked', 'failed')),
    artifact JSONB NOT NULL DEFAULT '{}'::jsonb,
    commit_sha TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS publication_jobs_ready_idx ON publication_jobs (status, created_at);
