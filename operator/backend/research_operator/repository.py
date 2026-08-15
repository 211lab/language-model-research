"""PostgreSQL-backed durable queue and run records.

PostgreSQL is intentionally both the source of truth and the queue. The local
inference resource has a durable lease row, so even an accidental
``--scale worker-local=2`` cannot send two models to the one llama.cpp endpoint.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Iterator
from uuid import uuid4

from psycopg import Connection, connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .contracts import ModelSubmission, make_job_payload


TERMINAL_STATUSES = frozenset({"succeeded", "failed", "blocked", "cancelled"})


def _new_id() -> str:
    return uuid4().hex


def _plain(value: Any) -> Any:
    """Convert PostgreSQL JSON and datetime values into response-safe objects."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


class Repository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        with connect(self._dsn, row_factory=dict_row) as connection:
            yield connection

    def create_run(
        self,
        submission: ModelSubmission,
        *,
        luna_model: str,
        harness_contract_id: str,
        preflight_max_age_hours: int = 24,
    ) -> dict[str, Any]:
        """Persist a model request and one queued job per chosen cohort."""
        now = datetime.now(timezone.utc)
        model_id, run_id = _new_id(), _new_id()
        preflight_id: str | None = None
        preflight_reused = False
        job_ids: list[str] = []
        with self._connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO models (
                        id, identity_key, provider, model_ref, display_name,
                        source_repo, source_file, source_revision, metadata, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (identity_key) DO UPDATE SET
                        model_ref = EXCLUDED.model_ref,
                        display_name = EXCLUDED.display_name,
                        source_repo = EXCLUDED.source_repo,
                        source_file = EXCLUDED.source_file,
                        source_revision = EXCLUDED.source_revision,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        model_id,
                        submission.identity_key,
                        submission.provider,
                        submission.model_ref,
                        submission.display_name,
                        submission.source_repo,
                        submission.source_file,
                        submission.source_revision,
                        Jsonb(submission.as_payload()),
                    ),
                )
                stored_model_id = str(cursor.fetchone()["id"])
                cursor.execute(
                    """
                    INSERT INTO research_runs (id, model_id, provider, submission)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (run_id, stored_model_id, submission.provider, Jsonb(submission.as_payload())),
                )

                if submission.provider == "openrouter":
                    # Serialize the reusable preflight lookup/creation. Without
                    # this transaction-scoped lock, two scaled API replicas can
                    # both observe no preflight and spend on duplicate Luna work.
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        (f"luna-preflight:{harness_contract_id}",),
                    )
                    cursor.execute(
                        """
                        SELECT id, status FROM jobs
                        WHERE job_kind = 'luna_preflight'
                          AND payload ->> 'harness_contract_id' = %s
                          AND (
                              (status = 'succeeded' AND finished_at >= %s)
                              OR status IN ('queued', 'running')
                          )
                        ORDER BY
                            CASE status
                                WHEN 'succeeded' THEN 0
                                WHEN 'running' THEN 1
                                ELSE 2
                            END,
                            finished_at DESC NULLS LAST,
                            created_at DESC
                        LIMIT 1
                        """,
                        (
                            harness_contract_id,
                            now - timedelta(hours=preflight_max_age_hours),
                        ),
                    )
                    verified = cursor.fetchone()
                    if verified is not None and verified["status"] in {"queued", "running"}:
                        # One low-cost preflight validates a versioned harness, not a
                        # particular target model. Let concurrent paid runs wait for
                        # it rather than charging for duplicate Luna diagnostics.
                        preflight_id = str(verified["id"])
                        preflight_reused = True
                    elif verified is None:
                        preflight_id = _new_id()
                        preflight_payload = {
                            "provider": "openrouter",
                            "model_ref": luna_model,
                            "display_name": "Luna harness preflight",
                            "target_model_ref": submission.model_ref,
                            "harness_contract_id": harness_contract_id,
                            "assistant_max_tokens": submission.assistant_max_tokens,
                        }
                        cursor.execute(
                            """
                            INSERT INTO jobs (id, run_id, queue, cohort, job_kind, payload, priority)
                            VALUES (%s, %s, 'remote', 'preflight', 'luna_preflight', %s, 10)
                            """,
                            (preflight_id, run_id, Jsonb(preflight_payload)),
                        )
                        self._event_cursor(cursor, preflight_id, "info", "Queued Luna preflight before paid work.")

                for cohort in submission.cohorts:
                    job_id = _new_id()
                    queue = "local" if submission.provider == "local" else "remote"
                    cost_ceiling = (
                        submission.target_cost_ceiling_usd if submission.provider == "openrouter" else None
                    )
                    payload = make_job_payload(submission, cohort) | {
                        "harness_contract_id": harness_contract_id,
                        "judge_cost_ceiling_usd": submission.judge_cost_ceiling_usd,
                    }
                    cursor.execute(
                        """
                        INSERT INTO jobs (
                            id, run_id, queue, cohort, job_kind, payload, depends_on_job_id, cost_ceiling_usd
                        ) VALUES (%s, %s, %s, %s, 'research', %s, %s, %s)
                        """,
                        (job_id, run_id, queue, cohort, Jsonb(payload), preflight_id, cost_ceiling),
                    )
                    self._event_cursor(
                        cursor,
                        job_id,
                        "info",
                        f"Queued {cohort} research for {submission.display_name}.",
                    )
                    job_ids.append(job_id)
        return {
            "run_id": run_id,
            "model_identity_key": submission.identity_key,
            "job_ids": job_ids,
            "preflight_job_id": preflight_id,
            "preflight_reused": preflight_reused,
        }

    def enqueue_discovered_local_run(
        self, submission: ModelSubmission, *, harness_contract_id: str, details: dict[str, Any]
    ) -> dict[str, Any]:
        """Record a discovered exact GGUF and queue it once per harness contract."""
        with self._connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (submission.identity_key,))
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM jobs
                    JOIN research_runs ON research_runs.id = jobs.run_id
                    JOIN models ON models.id = research_runs.model_id
                    WHERE models.identity_key = %s
                      AND jobs.job_kind = 'research'
                      AND jobs.payload ->> 'harness_contract_id' = %s
                      AND jobs.status IN ('queued', 'running', 'succeeded')
                    """,
                    (submission.identity_key, harness_contract_id),
                )
                complete = int(cursor.fetchone()["count"]) >= len(submission.cohorts)
                if complete:
                    cursor.execute(
                        """
                        INSERT INTO discovered_local_models (
                            identity_key, model_ref, display_name, source_repo, source_file,
                            source_revision, eligibility, details
                        ) VALUES (%s, %s, %s, %s, %s, %s, 'already-scheduled-or-published', %s)
                        ON CONFLICT (identity_key) DO UPDATE SET last_seen_at = NOW(), details = EXCLUDED.details
                        """,
                        (submission.identity_key, submission.model_ref, submission.display_name,
                         submission.source_repo, submission.source_file, submission.source_revision, Jsonb(details)),
                    )
                    return {"queued": False, "reason": "already-scheduled-or-published"}
        created = self.create_run(submission, luna_model="", harness_contract_id=harness_contract_id)
        with self._connection() as connection, connection.transaction():
            connection.execute(
                """
                INSERT INTO discovered_local_models (
                    identity_key, model_ref, display_name, source_repo, source_file,
                    source_revision, source_snapshot, eligibility, run_id, details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'eligible', %s, %s)
                ON CONFLICT (identity_key) DO UPDATE SET
                    last_seen_at = NOW(), run_id = EXCLUDED.run_id, source_snapshot = EXCLUDED.source_snapshot,
                    eligibility = 'eligible', details = EXCLUDED.details
                """,
                (submission.identity_key, submission.model_ref, submission.display_name,
                 submission.source_repo, submission.source_file, submission.source_revision,
                 str(details.get("source_snapshot") or ""), created["run_id"], Jsonb(details)),
            )
        return {"queued": True, **created}

    def claim_next(self, queue: str, worker_id: str) -> dict[str, Any] | None:
        """Atomically claim one ready job, with a persistent local-endpoint lock."""
        with self._connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                self._block_failed_dependencies(cursor, queue)
                if queue == "local":
                    cursor.execute(
                        "SELECT locked_by FROM worker_resources WHERE resource = 'local-inference' FOR UPDATE"
                    )
                    resource = cursor.fetchone()
                    if resource and resource["locked_by"]:
                        return None
                cursor.execute(
                    """
                    SELECT j.id
                    FROM jobs j
                    LEFT JOIN jobs prerequisite ON prerequisite.id = j.depends_on_job_id
                    WHERE j.queue = %s
                      AND j.status = 'queued'
                      AND j.available_at <= NOW()
                      AND (j.depends_on_job_id IS NULL OR prerequisite.status = 'succeeded')
                    ORDER BY j.priority ASC, j.created_at ASC
                    FOR UPDATE OF j SKIP LOCKED
                    LIMIT 1
                    """,
                    (queue,),
                )
                candidate = cursor.fetchone()
                if candidate is None:
                    return None
                job_id = str(candidate["id"])
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = 'running', worker_id = %s, heartbeat_at = NOW(),
                        started_at = NOW(), attempt = attempt + 1
                    WHERE id = %s
                    RETURNING *
                    """,
                    (worker_id, job_id),
                )
                job = dict(cursor.fetchone())
                if queue == "local":
                    cursor.execute(
                        """
                        UPDATE worker_resources
                        SET locked_by = %s, locked_at = NOW()
                        WHERE resource = 'local-inference'
                        """,
                        (job_id,),
                    )
                cursor.execute("UPDATE research_runs SET status = 'running' WHERE id = %s", (job["run_id"],))
                self._event_cursor(cursor, job_id, "info", f"Claimed by {worker_id}.")
                return _plain(job)

    def heartbeat(self, job_id: str) -> None:
        with self._connection() as connection, connection.transaction():
            connection.execute(
                "UPDATE jobs SET heartbeat_at = NOW() WHERE id = %s AND status = 'running'", (job_id,)
            )

    def record_local_resolution(self, job: dict[str, Any], resolved: dict[str, Any]) -> None:
        """Carry the chosen GGUF identity to queued sibling cohort jobs in this run."""
        resolution = {
            "model_ref": resolved["model_ref"],
            "source_repo": resolved["source_repo"],
            "source_file": resolved["source_file"],
            "source_revision": resolved["source_revision"],
            "source_snapshot": resolved.get("source_snapshot", ""),
            "resolved_identity_key": (
                "local:"
                f"{resolved['source_repo']}@{resolved.get('source_snapshot') or resolved['source_revision']}:"
                f"{resolved['source_file']}"
            ),
        }
        with self._connection() as connection, connection.transaction():
            connection.execute(
                """
                UPDATE jobs
                SET payload = payload || %s, heartbeat_at = NOW()
                WHERE run_id = %s AND queue = 'local' AND status IN ('queued', 'running')
                """,
                (Jsonb(resolution), job["run_id"]),
            )

    def event(self, job_id: str, level: str, message: str, details: dict[str, Any] | None = None) -> None:
        with self._connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                self._event_cursor(cursor, job_id, level, message, details)

    def finish(self, job: dict[str, Any], result: dict[str, Any]) -> None:
        self._terminal(job, "succeeded", result=result)

    def fail(self, job: dict[str, Any], error: str) -> None:
        self._terminal(job, "failed", error=error)

    def _terminal(
        self,
        job: dict[str, Any],
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        job_id, run_id = str(job["id"]), str(job["run_id"])
        with self._connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = %s, result = %s, error = %s, finished_at = NOW(), heartbeat_at = NOW()
                    WHERE id = %s
                    """,
                    (status, Jsonb(result) if result is not None else None, error, job_id),
                )
                if job["queue"] == "local":
                    cursor.execute(
                        "UPDATE worker_resources SET locked_by = NULL, locked_at = NULL WHERE resource = 'local-inference' AND locked_by = %s",
                        (job_id,),
                    )
                message = "Completed successfully." if status == "succeeded" else f"Failed: {error}"
                self._event_cursor(cursor, job_id, "info" if status == "succeeded" else "error", message)
                if status == "succeeded" and job.get("job_kind") == "research" and result is not None:
                    publication_id = _new_id()
                    cursor.execute(
                        """
                        INSERT INTO publication_jobs (id, research_job_id, run_id, cohort, artifact)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (research_job_id) DO NOTHING
                        """,
                        (publication_id, job_id, run_id, str(job["cohort"]), Jsonb(result)),
                    )
                    self._event_cursor(cursor, job_id, "info", "Validated suite queued for isolated publication.")
                if status != "succeeded" and job.get("job_kind") == "luna_preflight":
                    self._block_dependents(cursor, job_id)
                self._refresh_run_status(cursor, run_id)

    def _block_failed_dependencies(self, cursor: Any, queue: str) -> None:
        cursor.execute(
            """
            UPDATE jobs dependent
            SET status = 'blocked', finished_at = NOW(),
                error = 'A required Luna preflight did not succeed.'
            FROM jobs prerequisite
            WHERE dependent.queue = %s
              AND dependent.status = 'queued'
              AND dependent.depends_on_job_id = prerequisite.id
              AND prerequisite.status IN ('failed', 'blocked', 'cancelled')
            RETURNING dependent.id, dependent.run_id
            """,
            (queue,),
        )
        blocked = cursor.fetchall()
        self._record_blocked_dependents(cursor, blocked)

    def _block_dependents(self, cursor: Any, prerequisite_id: str) -> None:
        """Make failed/cancelled preflight dependencies visible immediately."""
        cursor.execute(
            """
            UPDATE jobs
            SET status = 'blocked', finished_at = NOW(),
                error = 'A required Luna preflight did not succeed.'
            WHERE status = 'queued' AND depends_on_job_id = %s
            RETURNING id, run_id
            """,
            (prerequisite_id,),
        )
        self._record_blocked_dependents(cursor, cursor.fetchall())

    def _record_blocked_dependents(self, cursor: Any, blocked: list[dict[str, Any]]) -> None:
        run_ids: set[str] = set()
        for row in blocked:
            dependent_id = str(row["id"])
            run_ids.add(str(row["run_id"]))
            self._event_cursor(
                cursor,
                dependent_id,
                "warning",
                "Blocked because the required Luna preflight did not succeed.",
            )
        for affected_run_id in run_ids:
            self._refresh_run_status(cursor, affected_run_id)

    def _refresh_run_status(self, cursor: Any, run_id: str) -> None:
        cursor.execute("SELECT status FROM jobs WHERE run_id = %s", (run_id,))
        statuses = {str(row["status"]) for row in cursor.fetchall()}
        if not statuses or statuses - TERMINAL_STATUSES:
            return
        if statuses == {"succeeded"}:
            run_status = "succeeded"
        elif "failed" in statuses:
            run_status = "failed"
        elif "blocked" in statuses:
            run_status = "blocked"
        elif "cancelled" in statuses:
            run_status = "cancelled"
        else:
            run_status = "failed"
        cursor.execute("UPDATE research_runs SET status = %s WHERE id = %s", (run_status, run_id))

    @staticmethod
    def _event_cursor(cursor: Any, job_id: str, level: str, message: str, details: dict[str, Any] | None = None) -> None:
        cursor.execute(
            "INSERT INTO job_events (job_id, level, message, details) VALUES (%s, %s, %s, %s)",
            (job_id, level, message, Jsonb(details or {})),
        )

    def list_jobs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT jobs.*, models.display_name, models.model_ref, models.identity_key,
                       publication_jobs.status AS publication_status,
                       publication_jobs.commit_sha AS publication_commit_sha,
                       publication_jobs.error AS publication_error
                FROM jobs
                JOIN research_runs ON research_runs.id = jobs.run_id
                JOIN models ON models.id = research_runs.model_id
                LEFT JOIN publication_jobs ON publication_jobs.research_job_id = jobs.id
                ORDER BY jobs.created_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [_plain(dict(row)) for row in rows]

    def claim_publication(self, worker_id: str) -> dict[str, Any] | None:
        with self._connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM publication_jobs WHERE status = 'queued'
                    ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """
                    UPDATE publication_jobs SET status = 'running', started_at = NOW()
                    WHERE id = %s RETURNING *
                    """,
                    (str(row["id"]),),
                )
                return _plain(dict(cursor.fetchone()))

    def finish_publication(self, publication_id: str, *, commit_sha: str) -> None:
        with self._connection() as connection, connection.transaction():
            connection.execute(
                "UPDATE publication_jobs SET status = 'succeeded', commit_sha = %s, finished_at = NOW() WHERE id = %s",
                (commit_sha, publication_id),
            )

    def fail_publication(self, publication_id: str, error: str) -> None:
        with self._connection() as connection, connection.transaction():
            connection.execute(
                "UPDATE publication_jobs SET status = 'blocked', error = %s, finished_at = NOW() WHERE id = %s",
                (error[:2000], publication_id),
            )

    def list_publications(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM publication_jobs ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        return [_plain(dict(row)) for row in rows]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT jobs.*, models.display_name, models.model_ref, models.identity_key
                FROM jobs
                JOIN research_runs ON research_runs.id = jobs.run_id
                JOIN models ON models.id = research_runs.model_id
                WHERE jobs.id = %s
                """,
                (job_id,),
            ).fetchone()
        return _plain(dict(row)) if row else None

    def list_events(self, job_id: str, *, limit: int = 300) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, recorded_at, level, message, details
                FROM job_events WHERE job_id = %s
                ORDER BY id ASC LIMIT %s
                """,
                (job_id, limit),
            ).fetchall()
        return [_plain(dict(row)) for row in rows]

    def cancel_queued(self, job_id: str) -> bool:
        """Only queued work can be cancelled; running inference is never force-stopped."""
        with self._connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = 'cancelled', finished_at = NOW(), error = 'Cancelled before a worker claimed it.'
                    WHERE id = %s AND status = 'queued'
                    RETURNING run_id, job_kind
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return False
                self._event_cursor(cursor, job_id, "warning", "Cancelled before execution.")
                if row["job_kind"] == "luna_preflight":
                    self._block_dependents(cursor, job_id)
                self._refresh_run_status(cursor, str(row["run_id"]))
                return True
