"""Queue workers for local and OpenRouter research cohorts."""

from __future__ import annotations

import argparse
import os
import socket
import time
import traceback
from typing import Any, Callable

from .assistant import publish_assistant_result, run_assistant_benchmark, run_luna_preflight
from .config import Settings
from .contracts import parse_model_submission
from .editorial import run_editorial_benchmark
from .local_switcher import LocalSwitcher
from .repository import Repository


class ResearchWorker:
    def __init__(self, queue: str, settings: Settings, repository: Repository) -> None:
        self.queue = queue
        self.settings = settings
        self.repository = repository
        self.worker_id = os.environ.get("WORKER_ID") or f"{queue}-{socket.gethostname()}-{os.getpid()}"

    def run_once(self) -> bool:
        job = self.repository.claim_next(self.queue, self.worker_id)
        if job is None:
            return False
        log = self._job_logger(job)
        log(f"Starting {job['job_kind']} job for {job['cohort']}.")
        try:
            self.repository.heartbeat(str(job["id"]))
            if job["job_kind"] == "luna_preflight":
                result = run_luna_preflight(self.settings, str(job["id"]), log)
            else:
                result = self._run_research(job, log)
            self.repository.finish(job, result)
            return True
        except Exception as exc:  # A failed paid workload stays failed; it is never silently rerun.
            error = f"{type(exc).__name__}: {exc}"
            log(error, level="error")
            trace = "\n".join(traceback.format_exc().splitlines()[-8:])
            self.repository.event(str(job["id"]), "debug", trace[:4000])
            self.repository.fail(job, error[:2000])
            return True

    def _run_research(self, job: dict[str, Any], log: Callable[[str], None]) -> dict[str, Any]:
        payload = dict(job["payload"])
        provider = str(payload["provider"])
        effective_model_ref = str(payload["model_ref"])
        resolved: dict[str, Any] = {}
        if provider == "local":
            submission = parse_model_submission(payload)
            activated = LocalSwitcher(self.settings, log).activate(submission)
            resolved = activated.as_dict()
            effective_model_ref = activated.model_ref
            self.repository.record_local_resolution(job, resolved)
            payload.update(
                {
                    "model_ref": activated.model_ref,
                    "source_repo": activated.source_repo,
                    "source_file": activated.source_file,
                    "source_revision": activated.source_revision,
                    "source_snapshot": activated.source_snapshot,
                    "identity_key": (
                        "local:"
                        f"{activated.source_repo}@{activated.source_snapshot or activated.source_revision}:"
                        f"{activated.source_file}"
                    ),
                }
            )
            job["payload"] = payload
            log(
                f"Using exact local identity {activated.source_repo}@{activated.source_revision}/{activated.source_file}."
            )
        if job["cohort"] == "assistant":
            raw_result = run_assistant_benchmark(
                self.settings, job, model_ref=effective_model_ref, log=log
            )
            published = publish_assistant_result(self.settings, job, raw_result, log)
            return {"raw_output_dir": raw_result["output_dir"], "published": published, "local_resolution": resolved}
        if job["cohort"] == "editorial":
            published = run_editorial_benchmark(
                self.settings,
                job,
                effective_model_ref=effective_model_ref,
                effective_source_repo=str(resolved.get("source_repo") or payload.get("source_repo") or ""),
                effective_source_file=str(resolved.get("source_file") or payload.get("source_file") or ""),
                effective_source_revision=str(
                    resolved.get("source_revision") or payload.get("source_revision") or "main"
                ),
                effective_source_snapshot=str(
                    resolved.get("source_snapshot") or payload.get("source_snapshot") or ""
                ),
                log=log,
            )
            return {"published": published, "local_resolution": resolved}
        raise RuntimeError(f"Unsupported research cohort: {job['cohort']}")

    def _job_logger(self, job: dict[str, Any]) -> Callable[[str], None]:
        job_id = str(job["id"])

        def log(message: str, *, level: str = "info") -> None:
            rendered = str(message).strip()
            if not rendered:
                return
            self.repository.heartbeat(job_id)
            self.repository.event(job_id, level, rendered[:2000])

        return log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, choices=("local", "remote"))
    parser.add_argument("--once", action="store_true", help="Claim at most one job, useful for a controlled check.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be greater than zero")
    settings = Settings.from_env()
    worker = ResearchWorker(args.queue, settings, Repository(settings.database_dsn))
    while True:
        claimed = worker.run_once()
        if args.once:
            return 0
        if not claimed:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
