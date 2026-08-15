-- PostgreSQL is both the durable command queue and event store. NOTIFY is only
-- a wake-up hint; consumers always advance from the persisted event cursor.
CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    command_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id TEXT NOT NULL,
    causation_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','rejected','failed')),
    result JSONB,
    error TEXT,
    claimed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS commands_ready_idx ON commands (status, created_at);

CREATE TABLE IF NOT EXISTS aggregate_versions (
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (aggregate_type, aggregate_id)
);

CREATE TABLE IF NOT EXISTS domain_events (
    event_id BIGSERIAL PRIMARY KEY,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_sequence BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id TEXT NOT NULL,
    causation_id TEXT,
    producer TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (aggregate_type, aggregate_id, aggregate_sequence)
);
CREATE INDEX IF NOT EXISTS domain_events_replay_idx ON domain_events (event_id);
CREATE INDEX IF NOT EXISTS domain_events_aggregate_idx ON domain_events (aggregate_type, aggregate_id, aggregate_sequence);
CREATE INDEX IF NOT EXISTS domain_events_correlation_idx ON domain_events (correlation_id, event_id);
CREATE INDEX IF NOT EXISTS domain_events_filter_idx ON domain_events (event_type, producer, occurred_at DESC);

CREATE TABLE IF NOT EXISTS projection_checkpoints (
    projection_name TEXT PRIMARY KEY,
    event_id BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS run_summary_read (
    run_id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    correlation_id TEXT NOT NULL DEFAULT '',
    requested_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    last_event_id BIGINT NOT NULL DEFAULT 0,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS run_summary_read_status_idx ON run_summary_read (status, requested_at DESC);

CREATE TABLE IF NOT EXISTS service_activity_read (
    service_name TEXT PRIMARY KEY,
    last_event_id BIGINT NOT NULL DEFAULT 0,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'unknown',
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE OR REPLACE FUNCTION notify_domain_event() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('research_domain_events', NEW.event_id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS domain_events_notify ON domain_events;
CREATE TRIGGER domain_events_notify AFTER INSERT ON domain_events
FOR EACH ROW EXECUTE FUNCTION notify_domain_event();

-- Preserve the operator's existing queue history as immutable baseline facts.
-- This migration runs before the new services, so each legacy aggregate starts
-- at sequence one and future writes continue from aggregate_versions.
INSERT INTO domain_events (
    aggregate_type, aggregate_id, aggregate_sequence, event_type, payload,
    correlation_id, producer, occurred_at
)
SELECT 'run', r.id, 1, 'legacy.run_imported', r.submission, r.id, 'migration', r.requested_at
FROM research_runs r
WHERE NOT EXISTS (
    SELECT 1 FROM domain_events e WHERE e.aggregate_type = 'run' AND e.aggregate_id = r.id
);

INSERT INTO domain_events (
    aggregate_type, aggregate_id, aggregate_sequence, event_type, payload,
    correlation_id, producer, occurred_at
)
SELECT 'job', j.id, 1, 'legacy.job_imported',
       j.payload || jsonb_build_object('status', j.status, 'cohort', j.cohort, 'error', j.error),
       j.run_id, 'migration', j.created_at
FROM jobs j
WHERE NOT EXISTS (
    SELECT 1 FROM domain_events e WHERE e.aggregate_type = 'job' AND e.aggregate_id = j.id
);

INSERT INTO domain_events (
    aggregate_type, aggregate_id, aggregate_sequence, event_type, payload,
    correlation_id, producer, occurred_at
)
SELECT 'job', e.job_id,
       row_number() OVER (PARTITION BY e.job_id ORDER BY e.id) + 1,
       'legacy.job_log_imported',
       jsonb_build_object('level', e.level, 'message', e.message, 'details', e.details),
       j.run_id, 'migration', e.recorded_at
FROM job_events e
JOIN jobs j ON j.id = e.job_id
WHERE NOT EXISTS (
    SELECT 1 FROM domain_events d WHERE d.aggregate_type = 'job' AND d.aggregate_id = e.job_id
      AND d.event_type = 'legacy.job_log_imported'
);

INSERT INTO aggregate_versions (aggregate_type, aggregate_id, version)
SELECT aggregate_type, aggregate_id, MAX(aggregate_sequence)
FROM domain_events GROUP BY aggregate_type, aggregate_id
ON CONFLICT (aggregate_type, aggregate_id) DO UPDATE
SET version = GREATEST(aggregate_versions.version, EXCLUDED.version);
