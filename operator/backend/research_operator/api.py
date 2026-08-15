"""HTTP API for the operator UI and durable research queue."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config import Settings
from .contracts import ContractError, parse_model_submission
from .cqrs import CommandStore
from .local_switcher import local_catalog
from .overview import build_overview
from .repository import Repository


def create_app(settings: Settings | None = None, repository: Repository | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    store = repository or Repository(runtime.database_dsn)
    commands = CommandStore(runtime.database_dsn)
    app = FastAPI(title="Language Model Research Operator", version="0.1.0")
    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:8090")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        try:
            store.list_jobs(limit=1)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"queue database unavailable: {type(exc).__name__}") from exc
        return {"status": "ok", "service": "research-operator"}

    @app.get("/api/overview")
    def overview() -> dict[str, Any]:
        return build_overview(runtime)

    @app.get("/api/runtime")
    def runtime_info() -> dict[str, Any]:
        return {
            "local_endpoint": runtime.local_ai_base_url,
            "local_max_model_gib": runtime.local_model_max_gib,
            "local_idle_buffer_seconds": runtime.local_idle_buffer_seconds,
            "assistant_max_tokens": runtime.assistant_max_tokens,
            "luna_model": runtime.luna_model,
            "luna_preflight": {
                "max_tasks": runtime.luna_preflight_max_tasks,
                "max_tokens": runtime.luna_preflight_max_tokens,
                "contract_id": runtime.harness_contract_id,
            },
            "editorial_judge_model": runtime.editorial_judge_model,
        }

    @app.get("/api/models/local")
    def local_models() -> dict[str, Any]:
        try:
            models = local_catalog(runtime.local_switcher_config, runtime.local_switcher_environment)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Unable to read local switcher catalog: {exc}") from exc
        return {"models": models, "switcher_config": str(runtime.local_switcher_config)}

    @app.get("/api/jobs")
    def jobs(limit: int = 100) -> dict[str, Any]:
        return {"jobs": store.list_jobs(limit=max(1, min(limit, 500)))}

    @app.get("/api/query/jobs")
    def query_jobs(limit: int = 100) -> dict[str, Any]:
        return {"jobs": store.list_jobs(limit=max(1, min(limit, 500))), "projection": "legacy-queue"}

    @app.get("/api/query/runs")
    def query_runs(limit: int = 100) -> dict[str, Any]:
        from psycopg import connect
        from psycopg.rows import dict_row
        from .repository import _plain
        with connect(runtime.database_dsn, row_factory=dict_row) as connection:
            rows = connection.execute(
                "SELECT * FROM run_summary_read ORDER BY requested_at DESC NULLS LAST LIMIT %s", (max(1, min(limit, 500)),)
            ).fetchall()
        return {"runs": [_plain(dict(row)) for row in rows], "projection": "operator-read-models"}

    @app.get("/api/publications")
    def publications(limit: int = 100) -> dict[str, Any]:
        return {"publications": store.list_publications(limit=max(1, min(limit, 500)))}

    @app.get("/api/commands/{command_id}")
    def command(command_id: str) -> dict[str, Any]:
        found = commands.get(command_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Command not found")
        return found

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict[str, Any]:
        found = store.get_job(job_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return found

    @app.get("/api/jobs/{job_id}/events")
    def job_events(job_id: str, limit: int = 300) -> dict[str, Any]:
        if store.get_job(job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"events": store.list_events(job_id, limit=max(1, min(limit, 1000)))}

    @app.post("/api/commands/runs", status_code=202)
    @app.post("/api/runs", status_code=202, deprecated=True)
    def create_run(payload: dict[str, Any], idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, Any]:
        try:
            submission = parse_model_submission(payload)
        except ContractError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if submission.provider == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
            raise HTTPException(
                status_code=409,
                detail="OPENROUTER_API_KEY is not configured in the worker environment; no paid work was queued.",
            )
        command = commands.submit(
            "run.submit", submission.as_payload(), idempotency_key=idempotency_key,
        )
        return {"command": command}

    @app.post("/api/commands/jobs/{job_id}/cancel", status_code=202)
    @app.delete("/api/jobs/{job_id}", status_code=202, deprecated=True)
    def cancel_job(job_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> Response | dict[str, Any]:
        found = store.get_job(job_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if found["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail="A running job is never force-stopped. Wait for it to finish or investigate the worker log.",
            )
        command = commands.submit("job.cancel", {"job_id": job_id}, idempotency_key=idempotency_key)
        return {"command": command}

    return app


app = create_app()


def main() -> int:
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("research_operator.api:app", host="0.0.0.0", port=port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
