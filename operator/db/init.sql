CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    identity_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL CHECK (provider IN ('local', 'openrouter')),
    model_ref TEXT NOT NULL,
    display_name TEXT NOT NULL,
    source_repo TEXT NOT NULL DEFAULT '',
    source_file TEXT NOT NULL DEFAULT '',
    source_revision TEXT NOT NULL DEFAULT 'main',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL REFERENCES models(id),
    provider TEXT NOT NULL CHECK (provider IN ('local', 'openrouter')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    requested_by TEXT NOT NULL DEFAULT 'operator',
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'blocked', 'cancelled')),
    submission JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    queue TEXT NOT NULL CHECK (queue IN ('local', 'remote')),
    cohort TEXT NOT NULL CHECK (cohort IN ('editorial', 'assistant', 'preflight')),
    job_kind TEXT NOT NULL CHECK (job_kind IN ('research', 'luna_preflight')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'blocked', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 100,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    depends_on_job_id TEXT REFERENCES jobs(id),
    cost_ceiling_usd NUMERIC,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    worker_id TEXT,
    heartbeat_at TIMESTAMPTZ,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error TEXT
);

CREATE INDEX IF NOT EXISTS jobs_ready_idx ON jobs (queue, status, available_at, priority, created_at);
CREATE INDEX IF NOT EXISTS jobs_dependency_idx ON jobs (depends_on_job_id);
CREATE INDEX IF NOT EXISTS jobs_preflight_idx ON jobs ((payload ->> 'harness_contract_id'), status, finished_at)
    WHERE job_kind = 'luna_preflight';

CREATE TABLE IF NOT EXISTS job_events (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS job_events_job_idx ON job_events (job_id, id);

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

CREATE TABLE IF NOT EXISTS worker_resources (
    resource TEXT PRIMARY KEY,
    locked_by TEXT,
    locked_at TIMESTAMPTZ
);

INSERT INTO worker_resources(resource) VALUES ('local-inference') ON CONFLICT (resource) DO NOTHING;
