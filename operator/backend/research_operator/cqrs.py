"""Durable asynchronous commands, immutable event access, and read projections."""

from __future__ import annotations

from datetime import datetime
import json
import socket
import time
from typing import Any
from uuid import uuid4

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import Settings
from .contracts import ContractError, parse_model_submission
from .repository import Repository, _plain


def _id() -> str:
    return uuid4().hex


class CommandStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def submit(self, command_type: str, payload: dict[str, Any], *, idempotency_key: str | None = None,
               correlation_id: str | None = None, causation_id: str | None = None) -> dict[str, Any]:
        command_id = _id()
        key = idempotency_key or command_id
        correlation = correlation_id or command_id
        with connect(self.dsn, row_factory=dict_row) as connection, connection.transaction():
            row = connection.execute(
                """
                INSERT INTO commands (id, command_type, payload, correlation_id, causation_id, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
                RETURNING *
                """,
                (command_id, command_type, Jsonb(payload), correlation, causation_id, key),
            ).fetchone()
        return _plain(dict(row))

    def get(self, command_id: str) -> dict[str, Any] | None:
        with connect(self.dsn, row_factory=dict_row) as connection:
            row = connection.execute("SELECT * FROM commands WHERE id = %s", (command_id,)).fetchone()
        return _plain(dict(row)) if row else None

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        with connect(self.dsn, row_factory=dict_row) as connection, connection.transaction():
            row = connection.execute(
                """
                SELECT id FROM commands WHERE status = 'queued'
                ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            command = connection.execute(
                """UPDATE commands SET status = 'running', claimed_by = %s, started_at = NOW()
                   WHERE id = %s RETURNING *""",
                (worker_id, row["id"]),
            ).fetchone()
        return _plain(dict(command))

    def resolve(self, command_id: str, *, status: str, result: dict[str, Any] | None = None,
                error: str | None = None) -> None:
        with connect(self.dsn) as connection, connection.transaction():
            connection.execute(
                """UPDATE commands SET status = %s, result = %s, error = %s, finished_at = NOW()
                   WHERE id = %s""",
                (status, Jsonb(result) if result is not None else None, error, command_id),
            )

    def events(self, *, after: int = 0, limit: int = 200, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        clauses = ["event_id > %s"]
        values: list[Any] = [after]
        for column, key in (("correlation_id", "correlation_id"), ("event_type", "event_type"),
                            ("producer", "producer"), ("aggregate_id", "aggregate_id")):
            if filters.get(key):
                clauses.append(f"{column} = %s")
                values.append(filters[key])
        values.append(limit)
        with connect(self.dsn, row_factory=dict_row) as connection:
            rows = connection.execute(
                f"SELECT * FROM domain_events WHERE {' AND '.join(clauses)} ORDER BY event_id LIMIT %s", values
            ).fetchall()
        return [_plain(dict(row)) for row in rows]

    def latest_event_id(self) -> int:
        with connect(self.dsn) as connection:
            return int(connection.execute("SELECT COALESCE(MAX(event_id), 0) FROM domain_events").fetchone()[0])


class CommandDispatcher:
    """Compatibility command handler; legacy queue tables are write projections during migration."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.commands = CommandStore(settings.database_dsn)
        self.repository = Repository(settings.database_dsn)
        self.worker_id = f"command-dispatcher-{socket.gethostname()}"

    def run_once(self) -> bool:
        command = self.commands.claim(self.worker_id)
        if command is None:
            return False
        try:
            payload = dict(command["payload"])
            if command["command_type"] == "run.submit":
                submission = parse_model_submission(payload)
                result = self.repository.create_run(
                    submission, luna_model=self.settings.luna_model,
                    harness_contract_id=self.settings.harness_contract_id,
                )
                self.commands.resolve(str(command["id"]), status="succeeded", result=result)
            elif command["command_type"] == "job.cancel":
                job_id = str(payload.get("job_id") or "")
                if not job_id or not self.repository.cancel_queued(job_id):
                    raise ContractError("Only queued jobs can be cancelled")
                self.commands.resolve(str(command["id"]), status="succeeded", result={"job_id": job_id})
            elif command["command_type"] == "publication.enqueue":
                result = self.repository.enqueue_publication(str(payload.get("research_job_id") or ""))
                self.commands.resolve(str(command["id"]), status="succeeded", result=result)
            else:
                raise ContractError(f"Unsupported command type {command['command_type']!r}")
        except ContractError as exc:
            self.commands.resolve(str(command["id"]), status="rejected", error=str(exc))
        except Exception as exc:
            self.commands.resolve(str(command["id"]), status="failed", error=f"{type(exc).__name__}: {exc}")
        return True

    def run_forever(self, poll_seconds: float) -> None:
        while True:
            if not self.run_once():
                time.sleep(poll_seconds)


class ProjectionWorker:
    """Idempotently maintains CQRS read models from the global event cursor."""

    name = "operator-read-models"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def run_once(self, batch_size: int = 250) -> int:
        with connect(self.dsn, row_factory=dict_row) as connection, connection.transaction():
            checkpoint = connection.execute(
                "SELECT event_id FROM projection_checkpoints WHERE projection_name = %s FOR UPDATE", (self.name,)
            ).fetchone()
            cursor = int(checkpoint["event_id"]) if checkpoint else 0
            events = connection.execute(
                "SELECT * FROM domain_events WHERE event_id > %s ORDER BY event_id LIMIT %s", (cursor, batch_size)
            ).fetchall()
            for event in events:
                item = dict(event)
                payload = item["payload"] or {}
                if item["aggregate_type"] == "run":
                    status = str(payload.get("status") or self._status_for(str(item["event_type"])) or "queued")
                    connection.execute(
                        """INSERT INTO run_summary_read (run_id, model_name, provider, status, correlation_id, requested_at, finished_at, last_event_id, details)
                           VALUES (%s,%s,%s,%s,%s,NOW(),CASE WHEN %s THEN NOW() ELSE NULL END,%s,%s)
                           ON CONFLICT (run_id) DO UPDATE SET status=EXCLUDED.status, last_event_id=EXCLUDED.last_event_id,
                             finished_at=COALESCE(EXCLUDED.finished_at, run_summary_read.finished_at), details=EXCLUDED.details""",
                        (item["aggregate_id"], str(payload.get("display_name") or ""), str(payload.get("provider") or ""),
                         status, item["correlation_id"], status in {"succeeded", "failed", "blocked", "cancelled"},
                         item["event_id"], Jsonb(payload)),
                    )
                connection.execute(
                    """INSERT INTO service_activity_read (service_name,last_event_id,last_seen_at,status,details)
                       VALUES (%s,%s,NOW(),'active',%s) ON CONFLICT (service_name) DO UPDATE SET
                       last_event_id=EXCLUDED.last_event_id,last_seen_at=NOW(),status='active',details=EXCLUDED.details""",
                    (item["producer"], item["event_id"], Jsonb({"event_type": item["event_type"]})),
                )
            if events:
                cursor = int(events[-1]["event_id"])
            connection.execute(
                """INSERT INTO projection_checkpoints (projection_name,event_id) VALUES (%s,%s)
                   ON CONFLICT (projection_name) DO UPDATE SET event_id=EXCLUDED.event_id,updated_at=NOW()""",
                (self.name, cursor),
            )
            return len(events)

    @staticmethod
    def _status_for(event_type: str) -> str | None:
        if event_type.endswith(".completed") or event_type.endswith(".succeeded"):
            return "succeeded"
        if event_type.endswith(".failed"):
            return "failed"
        if event_type.endswith(".blocked"):
            return "blocked"
        if event_type.endswith(".cancelled"):
            return "cancelled"
        return None


class OrchestrationPolicy:
    """Turns completed domain facts into idempotent downstream commands."""

    name = "orchestration-policy"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.commands = CommandStore(dsn)

    def run_once(self, batch_size: int = 250) -> int:
        with connect(self.dsn, row_factory=dict_row) as connection, connection.transaction():
            row = connection.execute(
                "SELECT event_id FROM projection_checkpoints WHERE projection_name = %s FOR UPDATE", (self.name,)
            ).fetchone()
            cursor = int(row["event_id"]) if row else 0
            events = connection.execute(
                "SELECT * FROM domain_events WHERE event_id > %s ORDER BY event_id LIMIT %s", (cursor, batch_size)
            ).fetchall()
            for event in events:
                item = dict(event)
                if item["event_type"] == "job.succeeded":
                    job = connection.execute(
                        "SELECT job_kind FROM jobs WHERE id = %s", (item["aggregate_id"],)
                    ).fetchone()
                    if job and job["job_kind"] == "research":
                        self.commands.submit(
                            "publication.enqueue", {"research_job_id": item["aggregate_id"]},
                            idempotency_key=f"publication:{item['aggregate_id']}",
                            correlation_id=str(item["correlation_id"]), causation_id=str(item["event_id"]),
                        )
            if events:
                cursor = int(events[-1]["event_id"])
            connection.execute(
                """INSERT INTO projection_checkpoints (projection_name,event_id) VALUES (%s,%s)
                   ON CONFLICT (projection_name) DO UPDATE SET event_id=EXCLUDED.event_id,updated_at=NOW()""",
                (self.name, cursor),
            )
            return len(events)
