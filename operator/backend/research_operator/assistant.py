"""Assistant benchmark execution and safe publication into the static research pages."""

from __future__ import annotations

import csv
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Iterator

from .config import Settings
from .process import run_streaming


PUBLISHED_FIELDS = [
    "model",
    "display_name",
    "run_status",
    "assistant_score",
    "outcome",
    "tool_use",
    "grounding",
    "state",
    "english",
    "safety",
    "efficiency",
    "tasks_passed",
    "tasks_total",
    "task_pass_rate",
    "tool_call_success_rate",
    "median_task_seconds",
    "total_task_seconds",
    "cold_start_seconds",
    "cold_ttft_seconds",
    "openclaw_seconds",
    "openclaw_ttft_seconds",
    "latency_total_seconds",
    "tool_call_detected",
    "provider",
    "benchmark_track",
    "error",
    "identity_key",
    "source_repo",
    "source_file",
    "source_revision",
    "source_snapshot",
    "operator_run_id",
    "provider_reported_cost_usd",
    "provider_cost_limit_usd",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local_label(value: str) -> str:
    return value if value.endswith(" (Local)") else f"{value} (Local)"


def _disable_thinking(model_ref: str) -> bool:
    normalized = model_ref.lower()
    return any(marker in normalized for marker in ("qwen", "qwythos", "gemma-4-12b"))


@contextmanager
def _publish_lock(lock_path: Path, *, timeout_seconds: float = 120.0) -> Iterator[None]:
    """Serialize file updates and dashboard builds across horizontally scaled workers."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, f"pid={os.getpid()}\n".encode())
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for research publication lock: {lock_path}")
            time.sleep(0.5)
    try:
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def run_luna_preflight(settings: Settings, job_id: str, log: Callable[[str], None]) -> dict[str, Any]:
    """Validate latency and assistant harnesses with Luna before paid model work starts."""
    assistant_tool = settings.research_root / "tools" / "benchmark" / "assistant_benchmark.py"
    latency_tool = settings.research_root / "tools" / "benchmark" / "benchmark.py"
    output = settings.runs_root / job_id / "luna-preflight"
    output.mkdir(parents=True, exist_ok=True)
    usage_log = output / "OPENROUTER_USAGE.jsonl"
    validation = ["python", str(assistant_tool), "--validate"]
    run_streaming(validation, cwd=settings.research_root, on_line=log)
    latency_command = [
        "python",
        str(latency_tool),
        "--base-url",
        settings.openrouter_base_url,
        "--api",
        "openai",
        "--model",
        settings.luna_model,
        "--seed",
        "42",
        "--settle-seconds",
        "0",
        "--no-unload",
        "--timeout",
        str(settings.remote_timeout_seconds),
        "--max-cost-usd",
        str(settings.luna_preflight_max_cost_usd),
        "--usage-log",
        str(usage_log),
        "--require-reported-cost",
        "--output-dir",
        str(output / "latency"),
    ]
    run_streaming(latency_command, cwd=settings.research_root, on_line=log)
    command = [
        "python",
        str(assistant_tool),
        "--base-url",
        settings.openrouter_base_url,
        "--run-label",
        "luna-preflight",
        "--model",
        settings.luna_model,
        "--max-tasks",
        str(settings.luna_preflight_max_tasks),
        "--max-tokens",
        str(settings.luna_preflight_max_tokens),
        "--seed",
        "42",
        "--settle-seconds",
        "0",
        "--no-unload",
        "--timeout",
        str(settings.remote_timeout_seconds),
        "--max-cost-usd",
        str(settings.luna_preflight_max_cost_usd),
        "--usage-log",
        str(usage_log),
        "--require-reported-cost",
        "--output-dir",
        str(output),
    ]
    run_streaming(command, cwd=settings.research_root, on_line=log)
    result = _load_json(output / "results.json")
    latency = _load_json(output / "latency" / "results.json")
    summaries = result.get("model_summaries") or []
    if not summaries or summaries[0].get("status") != "ok":
        raise RuntimeError("Luna did not complete the required assistant-harness preflight")
    latency_rows = latency.get("results") or []
    if not latency_rows or latency_rows[0].get("status") != "ok":
        raise RuntimeError("Luna did not complete the required latency-harness preflight")
    return {
        "output_dir": str(output),
        "model": settings.luna_model,
        "tasks_checked": settings.luna_preflight_max_tasks,
        "max_tokens": settings.luna_preflight_max_tokens,
        "run_status": summaries[0].get("status"),
        "latency_status": latency_rows[0].get("status"),
        "provider_reported_cost_usd": (result.get("metadata") or {}).get("provider_reported_cost_usd"),
    }


def run_assistant_benchmark(
    settings: Settings,
    job: dict[str, Any],
    *,
    model_ref: str,
    log: Callable[[str], None],
) -> dict[str, Any]:
    """Run the latency companion and 21-task assistant battery for one model."""
    payload = dict(job["payload"])
    provider = str(payload["provider"])
    cohort = "local" if provider == "local" else "openrouter"
    output = settings.runs_root / str(job["id"]) / "assistant"
    command = [
        "bash",
        str(settings.research_root / "scripts" / "run_model_benchmark.sh"),
        "--model",
        model_ref,
        "--base-url",
        settings.local_ai_base_url if provider == "local" else settings.openrouter_base_url,
        "--api",
        "openai",
        "--cohort",
        cohort,
        "--mode",
        "both",
        "--output-dir",
        str(output),
        "--timeout",
        str(settings.remote_timeout_seconds),
    ]
    if provider == "local":
        command.extend(["--settle-seconds", str(settings.local_settle_seconds)])
    else:
        command.extend(
            [
                "--settle-seconds",
                "0",
                "--no-unload",
                "--max-cost-usd",
                str(payload["target_cost_ceiling_usd"]),
                "--usage-log",
                str(output / "OPENROUTER_USAGE.jsonl"),
                "--require-reported-cost",
            ]
        )
    if _disable_thinking(model_ref):
        command.append("--disable-thinking")
    run_streaming(command, cwd=settings.research_root, on_line=log)
    assistant_result = _load_json(output / "assistant" / "results.json")
    latency_result = _load_json(output / "latency" / "results.json")
    return {
        "output_dir": str(output),
        "assistant_results": assistant_result,
        "latency_results": latency_result,
        "effective_model_ref": model_ref,
    }


def _validate_contract(settings: Settings, assistant: dict[str, Any], latency: dict[str, Any]) -> None:
    assistant_metadata = assistant.get("metadata") or {}
    latency_metadata = latency.get("metadata") or {}
    if assistant_metadata.get("seed") != 42 or latency_metadata.get("seed") != 42:
        raise RuntimeError("Assistant results do not use the fixed seed 42")
    if assistant_metadata.get("max_tokens_per_model_turn") != settings.assistant_max_tokens:
        raise RuntimeError("Assistant results changed the fixed max-token cap")
    fixture = settings.research_root / "tools" / "benchmark" / "fixtures" / "base_environment.json"
    tasks = settings.research_root / "tools" / "benchmark" / "fixtures" / "tasks.json"
    if assistant_metadata.get("fixture_sha256") != _sha256(fixture):
        raise RuntimeError("Assistant fixture hash does not match the checked-in contract")
    if assistant_metadata.get("tasks_sha256") != _sha256(tasks):
        raise RuntimeError("Assistant task-suite hash does not match the checked-in contract")
    assistant_models = set(assistant_metadata.get("selected_models") or [])
    latency_models = set(latency_metadata.get("selected_models") or [])
    if assistant_models != latency_models or len(assistant_models) != 1:
        raise RuntimeError("Assistant and latency output must contain the same one exact model")
    summary = next(
        (row for row in assistant.get("model_summaries", []) if row.get("model") in assistant_models),
        None,
    )
    expected_tasks = len(assistant_metadata.get("selected_tasks") or [])
    if summary is None or summary.get("status") != "ok" or summary.get("tasks_total") != expected_tasks:
        raise RuntimeError("Assistant workload was not fully completed; partial or failed paid results are not published")


def _row_for_result(
    job: dict[str, Any],
    effective_model_ref: str,
    assistant: dict[str, Any],
    latency: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    payload = dict(job["payload"])
    assistant_summary = next(
        (row for row in assistant.get("model_summaries", []) if row.get("model") == effective_model_ref),
        None,
    )
    latency_summary = next(
        (row for row in latency.get("results", []) if row.get("model") == effective_model_ref),
        None,
    )
    if assistant_summary is None or latency_summary is None:
        raise RuntimeError("The benchmark output does not contain the selected model")
    if latency_summary.get("status") != "ok":
        raise RuntimeError(f"Latency companion failed: {latency_summary.get('error') or latency_summary.get('status')}")
    category = assistant_summary.get("category_scores") or {}
    provider = str(payload["provider"])
    display_name = str(payload.get("display_name") or assistant_summary.get("display_name") or effective_model_ref)
    if provider == "local":
        display_name = _local_label(display_name)
    row = {
        "model": effective_model_ref,
        "display_name": display_name,
        "run_status": assistant_summary.get("status", "error"),
        "assistant_score": assistant_summary.get("overall_score", 0),
        "outcome": category.get("outcome", 0),
        "tool_use": category.get("tool_use", 0),
        "grounding": category.get("grounding", 0),
        "state": category.get("state", 0),
        "english": category.get("english", 0),
        "safety": category.get("safety", 0),
        "efficiency": category.get("efficiency", 0),
        "tasks_passed": assistant_summary.get("tasks_passed", 0),
        "tasks_total": assistant_summary.get("tasks_total", 0),
        "task_pass_rate": assistant_summary.get("task_pass_rate", 0),
        "tool_call_success_rate": assistant_summary.get("tool_call_success_rate", 0),
        "median_task_seconds": assistant_summary.get("median_task_seconds", 0),
        "total_task_seconds": assistant_summary.get("total_task_seconds", 0),
        "cold_start_seconds": latency_summary.get("cold_start_seconds", 0),
        "cold_ttft_seconds": latency_summary.get("cold_ttft_seconds", 0),
        "openclaw_seconds": latency_summary.get("openclaw_seconds", 0),
        "openclaw_ttft_seconds": latency_summary.get("openclaw_ttft_seconds", 0),
        "latency_total_seconds": latency_summary.get("total_seconds", 0),
        "tool_call_detected": str(bool(latency_summary.get("tool_call_detected", False))).lower(),
        "provider": "Local llama.cpp" if provider == "local" else "OpenRouter",
        "benchmark_track": "local" if provider == "local" else "openrouter",
        "error": assistant_summary.get("error", ""),
        "identity_key": payload.get("resolved_identity_key") or payload.get("identity_key", ""),
        "source_repo": payload.get("source_repo", ""),
        "source_file": payload.get("source_file", ""),
        "source_revision": payload.get("source_revision", ""),
        "source_snapshot": payload.get("source_snapshot", ""),
        "operator_run_id": job.get("run_id", ""),
        "provider_reported_cost_usd": assistant.get("metadata", {}).get("provider_reported_cost_usd", ""),
        "provider_cost_limit_usd": payload.get("target_cost_ceiling_usd", ""),
    }
    return provider, row


def _merge_row(path: Path, row: dict[str, Any]) -> None:
    existing: list[dict[str, Any]] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            existing = list(csv.DictReader(handle))
    by_model = {str(item.get("model") or ""): item for item in existing if item.get("model")}
    by_model[str(row["model"])] = {field: row.get(field, "") for field in PUBLISHED_FIELDS}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLISHED_FIELDS, lineterminator="\n")
        writer.writeheader()
        for model in sorted(by_model):
            normalized = {field: by_model[model].get(field, "") for field in PUBLISHED_FIELDS}
            writer.writerow(normalized)


def publish_assistant_result(
    settings: Settings,
    job: dict[str, Any],
    run_result: dict[str, Any],
    log: Callable[[str], None],
) -> dict[str, Any]:
    """Merge one validated row and regenerate the root and docs dashboards."""
    assistant = dict(run_result["assistant_results"])
    latency = dict(run_result["latency_results"])
    _validate_contract(settings, assistant, latency)
    provider, row = _row_for_result(job, str(run_result["effective_model_ref"]), assistant, latency)
    target = (
        settings.research_root / "docs" / "assistant-benchmark" / "model-results.csv"
        if provider == "local"
        else settings.research_root / "docs" / "assistant-benchmark" / "openrouter-model-results.csv"
    )
    lock = settings.operator_root / ".research-publish.lock"
    with _publish_lock(lock):
        _merge_row(target, row)
        log(f"Merged assistant result into {target.relative_to(settings.research_root)}.")
        run_streaming(
            ["python", str(settings.research_root / "scripts" / "build_radar.py")],
            cwd=settings.research_root,
            on_line=log,
        )
    return {
        "published_csv": str(target.relative_to(settings.research_root)),
        "model": row["model"],
        "display_name": row["display_name"],
        "assistant_score": row["assistant_score"],
        "tasks_total": row["tasks_total"],
    }
