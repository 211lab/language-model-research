#!/usr/bin/env python3
"""Build, validate, compare, and index immutable benchmark evidence bundles."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = REPO_ROOT / "runs"
SCHEMA_VERSION = 1
FAILURES = {
    "pass", "model_failure", "tool_protocol_failure", "timeout", "provider_error",
    "harness_error", "invalid_output", "not_run",
}
INFRA_FAILURES = {"timeout", "provider_error", "harness_error", "not_run"}


class EvidenceError(RuntimeError):
    """Raised when a bundle violates the evidence contract."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"Expected an object in {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise EvidenceError(f"{path}:{number}: expected an object")
            rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Cannot read {path}: {exc}") from exc
    return rows


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def slug(value: str, limit: int = 72) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (cleaned[:limit].rstrip("-") or "model")


def git_state() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def portable_path(value: str | Path) -> str:
    """Keep provenance useful without publishing a contributor's home path."""
    text = str(value)
    try:
        return Path(text).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        pass
    normalized = text.replace("\\", "/")
    marker = "/results/"
    if marker in normalized:
        return "external://results/" + normalized.split(marker, 1)[1]
    if "/Users/" in normalized or re.match(r"^[A-Za-z]:/Users/", normalized):
        return "external://local-path/" + normalized.rsplit("/", 1)[-1]
    return text


def portable_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    def clean(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {item_key: clean(item_value, str(item_key)) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [clean(item, key) for item in value]
        if isinstance(value, str):
            normalized = value.replace("\\", "/")
            if key.endswith("_path") or "/Users/" in normalized or re.match(r"^[A-Za-z]:/Users/", normalized):
                return portable_path(value)
        return value

    return clean(deepcopy(metadata))


def provider_for(model: str, cohort: str) -> str:
    if cohort in {"local", "titan-local"}:
        return "Titan"
    if cohort == "openrouter":
        return model.split("/", 1)[0] if "/" in model else "OpenRouter"
    return cohort or "unknown"


def classify_error(error: str, default: str = "model_failure") -> str:
    lowered = error.casefold()
    if not error:
        return default
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if any(token in lowered for token in ("http ", "connection", "request failed", "provider")):
        return "provider_error"
    if any(token in lowered for token in ("invalid", "malformed", "empty response", "json")):
        return "invalid_output"
    return "harness_error"


def status_for(rows: list[dict[str, Any]]) -> str:
    failures = [row["failure_type"] for row in rows if row["failure_type"] in INFRA_FAILURES]
    if not rows or len(failures) == len(rows):
        return "error"
    return "partial" if failures else "ok"


def normalize_assistant(raw: dict[str, Any], model: str, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    source = [row for row in raw.get("task_results", []) if row.get("model") == model]
    rows: list[dict[str, Any]] = []
    trajectory: list[dict[str, Any]] = []
    for index, item in enumerate(source, start=1):
        critical = bool(item.get("critical_failure"))
        score = float(item.get("score", 0))
        strict = bool(item.get("passed")) and item.get("status") == "ok" and not critical
        core = score >= 50 and not critical
        contract = score >= 70 and not critical
        error = str(item.get("error") or "")
        if item.get("status") != "ok":
            failure = classify_error(error)
        elif strict:
            failure = "pass"
        elif item.get("tool_call_count", 0) and not item.get("successful_tool_calls", 0):
            failure = "tool_protocol_failure"
        else:
            failure = "model_failure"
        row = {
            "run_id": run_id, "suite": "assistant", "model": model,
            "task_id": str(item.get("task_id", f"task-{index}")),
            "title": item.get("title", ""), "category": item.get("category", "uncategorized"),
            "status": item.get("status") if item.get("status") in {"ok", "partial", "error"} else "error",
            "failure_type": failure, "score": max(0.0, min(100.0, score)),
            "core_passed": core, "contract_passed": contract, "strict_passed": strict,
            "elapsed_seconds": max(0.0, float(item.get("elapsed_seconds", 0))),
            "tool_call_count": int(item.get("tool_call_count", 0)),
            "successful_tool_calls": int(item.get("successful_tool_calls", 0)),
            "dimension_points": item.get("category_points", {}),
            "assertion_results": item.get("assertion_results", []),
            "final_answer": item.get("final_answer", ""), "error": error,
        }
        rows.append(row)
        trajectory.append({
            "run_id": run_id, "task_id": row["task_id"], "sequence": index,
            "tool_calls": item.get("tool_calls", []), "mutations": item.get("mutations", []),
            "transcript": item.get("transcript", []), "final_answer": item.get("final_answer", ""),
        })
    model_summary = next((row for row in raw.get("model_summaries", []) if row.get("model") == model), {})
    return model_summary, rows, trajectory


def normalize_editorial(raw: dict[str, Any], model: str, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    source = [row for row in raw.get("task_results", []) if row.get("model") == model]
    rows: list[dict[str, Any]] = []
    trajectory: list[dict[str, Any]] = []
    for index, item in enumerate(source, start=1):
        error = str(item.get("error") or "")
        failure = item.get("failure_type") or ("pass" if item.get("strict_passed") else classify_error(error))
        if failure not in FAILURES:
            failure = "harness_error"
        row = {
            "run_id": run_id, "suite": "editorial", "model": model,
            "task_id": str(item.get("task_id", f"task-{index}")), "title": item.get("title", ""),
            "category": item.get("category", "uncategorized"), "track": item.get("track"),
            "stage": item.get("stage"),
            "status": item.get("status") if item.get("status") in {"ok", "partial", "error"} else "error",
            "failure_type": failure, "score": max(0.0, min(100.0, float(item.get("score", 0)))),
            "core_passed": bool(item.get("core_passed")), "contract_passed": bool(item.get("contract_passed")),
            "strict_passed": bool(item.get("strict_passed")),
            "elapsed_seconds": max(0.0, float(item.get("elapsed_seconds", 0))),
            "dimension_points": item.get("dimension_points", {}),
            "assertion_results": item.get("assertion_results", []), "usage": item.get("usage", {}),
            "final_answer": item.get("final_answer", ""), "error": error,
        }
        rows.append(row)
        trajectory.append({
            "run_id": run_id, "task_id": row["task_id"], "sequence": index,
            "track": row["track"], "stage": row["stage"], "prompt": item.get("prompt", ""),
            "artifact": item.get("final_answer", ""),
        })
    model_summary = next((row for row in raw.get("model_summaries", []) if row.get("model") == model), {})
    return model_summary, rows, trajectory


def normalize_latency(raw: dict[str, Any], model: str, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    item = next((row for row in raw.get("results", []) if row.get("model") == model), {})
    ok = item.get("status") == "ok"
    tool = bool(item.get("tool_call_detected"))
    score = 100.0 if ok and tool else (50.0 if ok else 0.0)
    failure = "pass" if ok and tool else ("tool_protocol_failure" if ok else classify_error(str(item.get("error") or "")))
    row = {
        "run_id": run_id, "suite": "latency", "model": model, "task_id": "cold-and-agent-sequence",
        "title": "Cold primer and warm OpenClaw request", "category": "latency",
        "status": "ok" if ok else "error", "failure_type": failure, "score": score,
        "core_passed": ok, "contract_passed": ok and tool, "strict_passed": ok and tool,
        "elapsed_seconds": max(0.0, float(item.get("total_seconds", 0))),
        "cold_start_seconds": item.get("cold_start_seconds"), "cold_ttft_seconds": item.get("cold_ttft_seconds"),
        "workload_seconds": item.get("openclaw_seconds"), "workload_ttft_seconds": item.get("openclaw_ttft_seconds"),
        "tool_call_detected": tool, "final_answer": item.get("openclaw_output", ""),
        "primer_answer": item.get("cold_output", ""), "error": str(item.get("error") or ""),
    }
    return item, [row], [{
        "run_id": run_id, "task_id": row["task_id"], "sequence": 1,
        "primer": {"seconds": row["cold_start_seconds"], "ttft_seconds": row["cold_ttft_seconds"], "answer": row["primer_answer"]},
        "workload": {"seconds": row["workload_seconds"], "ttft_seconds": row["workload_ttft_seconds"], "answer": row["final_answer"]},
    }]


def dimension_scores(rows: list[dict[str, Any]], raw_summary: dict[str, Any]) -> dict[str, float]:
    if isinstance(raw_summary.get("category_scores"), dict):
        return {str(key): round(float(value), 3) for key, value in raw_summary["category_scores"].items()}
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        for key, points in row.get("dimension_points", {}).items():
            if isinstance(points, dict):
                possible = float(points.get("possible", 0))
                value = float(points.get("earned", 0)) / possible * 100 if possible else 0
            else:
                value = float(points)
            buckets[str(key)].append(value)
    return {key: round(statistics.mean(values), 3) for key, values in sorted(buckets.items())}


def summarize(run_id: str, suite: str, model: str, rows: list[dict[str, Any]], raw_summary: dict[str, Any]) -> dict[str, Any]:
    total = len(rows)
    completed = sum(row["failure_type"] not in INFRA_FAILURES for row in rows)
    exactness = {
        "core": sum(row["core_passed"] for row in rows),
        "contract": sum(row["contract_passed"] for row in rows),
        "strict": sum(row["strict_passed"] for row in rows),
        "total": total,
    }
    evaluated = [row for row in rows if row["failure_type"] not in INFRA_FAILURES]
    strict = exactness["strict"]
    elapsed = [row["elapsed_seconds"] for row in rows]
    failure_counts = dict(sorted(Counter(row["failure_type"] for row in rows).items()))
    score = statistics.mean(row["score"] for row in rows) if rows else 0.0
    efficiency: dict[str, Any] = {
        "median_task_seconds": round(statistics.median(elapsed), 4) if elapsed else 0,
        "total_seconds": round(sum(elapsed), 4),
        "tasks_per_minute": round(completed / sum(elapsed) * 60, 4) if sum(elapsed) else 0,
    }
    if suite == "latency" and rows:
        efficiency.update({key: rows[0].get(key) for key in (
            "cold_start_seconds", "cold_ttft_seconds", "workload_seconds", "workload_ttft_seconds",
        )})
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "suite": suite, "model": model,
        "status": status_for(rows), "score": round(score, 3), "exactness": exactness,
        "reliability": {
            "scheduled_pass_rate": round(strict / total * 100, 3) if total else 0,
            "evaluated_pass_rate": round(strict / len(evaluated) * 100, 3) if evaluated else 0,
            "scheduled": total, "evaluated": len(evaluated),
        },
        "efficiency": efficiency, "failure_counts": failure_counts,
        "dimensions": dimension_scores(rows, raw_summary),
    }


def add_scheduled_placeholders(
    rows: list[dict[str, Any]], selected_tasks: list[Any], run_id: str, suite: str, model: str,
) -> None:
    present = {row["task_id"] for row in rows}
    for task in selected_tasks:
        task_id = str(task)
        if task_id in present:
            continue
        rows.append({
            "run_id": run_id, "suite": suite, "model": model, "task_id": task_id,
            "title": "Scheduled task not run", "category": "not_run", "status": "error",
            "failure_type": "not_run", "score": 0.0, "core_passed": False,
            "contract_passed": False, "strict_passed": False, "elapsed_seconds": 0.0,
            "error": "No task result was produced after the model or provider failure.",
        })


def artifact_rows(bundle: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(item for item in bundle.rglob("*") if item.is_file() and item.name != "manifest.json"):
        rows.append({"path": path.relative_to(bundle).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows


def create_bundle(
    source: Path, suite: str, model: str, raw: dict[str, Any], *, cohort: str,
    provider_kind: str, provider: str | None, runtime: str, agent: str,
    replicate_index: int, replicate_count: int, seed: int | None, output_root: Path,
    imported: bool = False,
) -> Path:
    metadata = raw.get("metadata", {})
    published_metadata = portable_metadata(metadata)
    timestamp = str(metadata.get("started_at") or now_utc())[:19].replace(":", "").replace("-", "")
    run_id = f"{timestamp.casefold()}-{suite}-{slug(model)}-r{replicate_index}"
    bundle = output_root / run_id
    if bundle.exists():
        raise EvidenceError(f"Refusing to overwrite immutable bundle: {bundle}")
    bundle.mkdir(parents=True)
    if suite == "assistant":
        import assistant_benchmark as assistant_contract

        raw_summary, rows, trajectory = normalize_assistant(raw, model, run_id)
        fixture_hash = metadata.get("fixture_sha256")
        tasks_hash = metadata.get("tasks_sha256")
        tool_hash = canonical_hash(assistant_contract.TOOL_SCHEMAS)
        prompt_hash = canonical_hash({"system": assistant_contract.SYSTEM_PROMPT, "tasks": metadata.get("selected_tasks", [])})
        caveats = ["Core and contract exactness are derived from legacy assistant-v1 score thresholds (50 and 70); strict preserves the original task pass result."]
    elif suite == "editorial":
        import editorial_benchmark as editorial_contract

        raw_summary, rows, trajectory = normalize_editorial(raw, model, run_id)
        fixture_hash = metadata.get("sources_sha256")
        tasks_hash = metadata.get("tasks_sha256")
        tool_hash = None
        prompt_hash = canonical_hash({"system": editorial_contract.SYSTEM_PROMPT, "tasks": metadata.get("selected_tasks", [])})
        caveats = []
    elif suite == "latency":
        raw_summary, rows, trajectory = normalize_latency(raw, model, run_id)
        fixture_hash = None
        tasks_hash = canonical_hash(metadata.get("openclaw_prompt", []))
        tool_hash = canonical_hash(metadata.get("openclaw_tools", []))
        prompt_hash = canonical_hash({"cold": metadata.get("cold_prompt", []), "workload": metadata.get("openclaw_prompt", [])})
        caveats = ["Cold-load control is available only for local lifecycle-managed runtimes; hosted-provider latency is directional, not equivalent."]
    else:
        raise EvidenceError(f"Unsupported suite: {suite}")
    if suite != "latency":
        add_scheduled_placeholders(rows, metadata.get("selected_tasks", []), run_id, suite, model)
    if imported:
        caveats.append("Imported from a historical cohort result; the bundle is normalized evidence, not a rerun.")
    summary = summarize(run_id, suite, model, rows, raw_summary)
    reported_cost = metadata.get("provider_reported_cost_usd")
    summary["provider_reported_cost_usd"] = (
        float(reported_cost) if isinstance(reported_cost, (int, float)) else (0.0 if provider_kind == "local" else None)
    )
    compact_raw = {"metadata": published_metadata}
    if suite in {"assistant", "editorial"}:
        compact_raw.update({"model_summaries": [raw_summary], "task_results": [item for item in raw.get("task_results", []) if item.get("model") == model]})
    else:
        compact_raw["results"] = [raw_summary]
    configuration = {
        "schema_version": SCHEMA_VERSION, "suite": suite, "model": model, "seed": seed,
        "temperature": metadata.get("temperature", 0), "endpoint": metadata.get("base_url"),
        "thinking_mode": metadata.get("thinking_mode", "provider default"),
        "cost_budget": portable_metadata(metadata.get("cost_budget", {})) if isinstance(metadata.get("cost_budget"), dict) else {},
        "selected_tasks": metadata.get("selected_tasks", [row["task_id"] for row in rows]),
        "settle_seconds": metadata.get("settle_seconds_between_models", metadata.get("settle_seconds", 0)),
        "primer_required": True, "serial_execution": True,
    }
    lineage = {
        "schema_version": SCHEMA_VERSION, "source": portable_path(source), "source_sha256": sha256_file(source),
        "normalizer": "tools/benchmark/evidence.py", "normalized_at": now_utc(),
        "derivations": ["per-model split", "failure taxonomy", "core/contract/strict exactness funnel", "summary metrics"],
    }
    write_json(bundle / "raw" / "results.json", compact_raw)
    write_jsonl(bundle / "task-results.jsonl", rows)
    write_jsonl(bundle / "trajectory.jsonl", trajectory)
    write_json(bundle / "summary.json", summary)
    write_json(bundle / "configuration.json", configuration)
    write_json(bundle / "lineage.json", lineage)
    (bundle / "README.md").write_text(
        f"# {model} — {suite}\n\nRun `{run_id}` is an immutable evidence bundle. "
        "Use the normalized JSONL for analysis and `raw/results.json` for audit detail. "
        "Artifact hashes are recorded in `manifest.json`.\n", encoding="utf-8",
    )
    commit, dirty = git_state()
    expected = len(metadata.get("selected_tasks", [])) if suite != "latency" else 1
    if not expected:
        expected = len(rows)
    failure_counts = summary["failure_counts"]
    manifest = {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "suite": suite,
        "suite_version": str(metadata.get("suite_version", "1.0")), "status": summary["status"],
        "started_at": metadata.get("started_at", now_utc()), "finished_at": metadata.get("finished_at", now_utc()),
        "system": {
            "model": model, "display_name": raw_summary.get("display_name", model),
            "provider": provider or provider_for(model, cohort), "runtime": runtime, "agent": agent,
            "quantization": None,
        },
        "execution": {
            "cohort": cohort, "provider_kind": provider_kind,
            "endpoint_class": runtime, "endpoint": metadata.get("base_url", "unknown"), "serial": True,
            "lifecycle_control": metadata.get("lifecycle_control", metadata.get("cold_start_control")),
            "primer": "One fixed primer request after model switch and before measured workload.",
            "provider_reported_cost_usd": summary["provider_reported_cost_usd"],
        },
        "replicate": {"index": replicate_index, "count": replicate_count, "seed": int(seed if seed is not None else metadata.get("seed", 42))},
        "reproducibility": {
            "runner_commit": commit, "runner_dirty": dirty, "fixture_sha256": fixture_hash,
            "tasks_sha256": str(tasks_hash), "seed_document_sha256": str(metadata.get("steadyburn_seed_sha256", "unknown")),
            "prompt_sha256": prompt_hash, "tool_schema_sha256": tool_hash,
        },
        "counts": {
            "expected": expected, "completed": sum(row["failure_type"] != "not_run" for row in rows),
            "passed": summary["exactness"]["strict"],
            "infrastructure_failures": sum(failure_counts.get(kind, 0) for kind in INFRA_FAILURES),
        },
        "artifacts": artifact_rows(bundle), "caveats": caveats,
    }
    write_json(bundle / "manifest.json", manifest)
    return bundle


def models_in(raw: dict[str, Any], suite: str) -> list[str]:
    metadata_models = raw.get("metadata", {}).get("selected_models", [])
    if metadata_models:
        return [str(item) for item in metadata_models]
    key = "results" if suite == "latency" else "model_summaries"
    return [str(row["model"]) for row in raw.get(key, []) if row.get("model")]


def validate_bundle(bundle: Path) -> list[str]:
    errors: list[str] = []
    required = ["manifest.json", "summary.json", "task-results.jsonl", "trajectory.jsonl", "configuration.json", "lineage.json", "README.md", "raw/results.json"]
    for relative in required:
        if not (bundle / relative).is_file():
            errors.append(f"{bundle.name}: missing {relative}")
    if errors:
        return errors
    try:
        manifest = load_json(bundle / "manifest.json")
        summary = load_json(bundle / "summary.json")
        rows = read_jsonl(bundle / "task-results.jsonl")
    except EvidenceError as exc:
        return [str(exc)]
    for key in ("schema_version", "run_id", "suite", "status", "system", "execution", "reproducibility", "counts", "artifacts"):
        if key not in manifest:
            errors.append(f"{bundle.name}: manifest missing {key}")
    if manifest.get("run_id") != bundle.name or summary.get("run_id") != bundle.name:
        errors.append(f"{bundle.name}: run id/path mismatch")
    if manifest.get("suite") != summary.get("suite"):
        errors.append(f"{bundle.name}: suite mismatch")
    task_ids = [row.get("task_id") for row in rows]
    if len(task_ids) != len(set(task_ids)):
        errors.append(f"{bundle.name}: duplicate task ids")
    completed = sum(row.get("failure_type") != "not_run" for row in rows)
    if manifest.get("counts", {}).get("completed") != completed:
        errors.append(f"{bundle.name}: completed count does not match non-placeholder task results")
    if manifest.get("counts", {}).get("expected") != len(rows):
        errors.append(f"{bundle.name}: expected count does not match scheduled task results")
    for row in rows:
        if row.get("run_id") != bundle.name:
            errors.append(f"{bundle.name}: task {row.get('task_id')} has wrong run id")
        if row.get("failure_type") not in FAILURES:
            errors.append(f"{bundle.name}: task {row.get('task_id')} has invalid failure type")
        if not 0 <= float(row.get("score", -1)) <= 100:
            errors.append(f"{bundle.name}: task {row.get('task_id')} score outside 0..100")
    for artifact in manifest.get("artifacts", []):
        path = bundle / artifact.get("path", "")
        if not path.is_file():
            errors.append(f"{bundle.name}: missing artifact {artifact.get('path')}")
        elif sha256_file(path) != artifact.get("sha256"):
            errors.append(f"{bundle.name}: hash mismatch for {artifact.get('path')}")
        elif path.stat().st_size != artifact.get("bytes"):
            errors.append(f"{bundle.name}: byte count mismatch for {artifact.get('path')}")
    funnel = summary.get("exactness", {})
    if not (funnel.get("strict", 0) <= funnel.get("contract", 0) <= funnel.get("core", 0) <= funnel.get("total", 0)):
        errors.append(f"{bundle.name}: exactness funnel is not monotonic")
    return errors


def comparability(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if left.get("suite") != right.get("suite") or left.get("suite_version") != right.get("suite_version"):
        return {"level": "not-comparable", "reasons": ["suite or suite version differs"]}
    fields = ("fixture_sha256", "tasks_sha256", "seed_document_sha256", "prompt_sha256", "tool_schema_sha256")
    left_repro, right_repro = left.get("reproducibility", {}), right.get("reproducibility", {})
    for field in fields:
        if left_repro.get(field) != right_repro.get(field):
            reasons.append(f"{field} differs")
    if left.get("replicate", {}).get("seed") != right.get("replicate", {}).get("seed"):
        reasons.append("sampling seed differs")
    if reasons:
        return {"level": "not-comparable", "reasons": reasons}
    if left.get("execution", {}).get("provider_kind") != right.get("execution", {}).get("provider_kind"):
        return {"level": "directional", "reasons": ["local and hosted execution differ"]}
    if left.get("execution", {}).get("endpoint_class") != right.get("execution", {}).get("endpoint_class"):
        return {"level": "directional", "reasons": ["runtime or endpoint class differs"]}
    return {"level": "comparable", "reasons": ["benchmark contract and execution class match"]}


def build_registry(root: Path = RUNS_ROOT, *, generated_at: str | None = None) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    errors: list[str] = []
    for bundle in sorted(path.parent for path in root.glob("*/manifest.json")):
        errors.extend(validate_bundle(bundle))
        if errors:
            continue
        manifest = load_json(bundle / "manifest.json")
        summary = load_json(bundle / "summary.json")
        runs.append({
            "run_id": manifest["run_id"], "suite": manifest["suite"],
            "suite_version": manifest["suite_version"], "model": manifest["system"]["model"],
            "display_name": manifest["system"]["display_name"], "provider": manifest["system"]["provider"],
            "provider_kind": manifest["execution"]["provider_kind"], "cohort": manifest["execution"]["cohort"],
            "endpoint_class": manifest["execution"]["endpoint_class"],
            "status": manifest["status"], "started_at": manifest["started_at"],
            "replicate": manifest["replicate"], "score": summary["score"], "exactness": summary["exactness"],
            "reliability": summary["reliability"], "efficiency": summary["efficiency"],
            "failure_counts": summary["failure_counts"], "dimensions": summary.get("dimensions", {}),
            "provider_reported_cost_usd": summary.get("provider_reported_cost_usd"),
            "manifest_path": f"runs/{bundle.name}/manifest.json", "summary_path": f"runs/{bundle.name}/summary.json",
            "task_results_path": f"runs/{bundle.name}/task-results.jsonl",
            "reproducibility": manifest["reproducibility"], "caveats": manifest.get("caveats", []),
        })
    if errors:
        raise EvidenceError("Evidence validation failed:\n- " + "\n- ".join(errors))
    return {"schema_version": SCHEMA_VERSION, "generated_at": generated_at or now_utc(), "run_count": len(runs), "runs": runs}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    imported = sub.add_parser("import", help="Split a cohort result into immutable per-model bundles")
    imported.add_argument("--suite", required=True, choices=("assistant", "editorial", "latency"))
    imported.add_argument("--input", required=True, type=Path)
    imported.add_argument("--cohort", required=True)
    imported.add_argument("--provider-kind", choices=("local", "remote"), required=True)
    imported.add_argument("--provider")
    imported.add_argument("--runtime", default="OpenAI-compatible")
    imported.add_argument("--agent", default="benchmark-harness")
    imported.add_argument("--replicate-index", type=int, default=1)
    imported.add_argument("--replicate-count", type=int, default=1)
    imported.add_argument("--seed", type=int)
    imported.add_argument("--model", action="append", default=[])
    imported.add_argument("--output-root", type=Path, default=RUNS_ROOT)
    validate = sub.add_parser("validate", help="Validate bundles and artifact hashes")
    validate.add_argument("paths", nargs="*", type=Path)
    registry = sub.add_parser("registry", help="Rebuild or check the deterministic run registry")
    registry.add_argument("--output", type=Path, default=RUNS_ROOT / "index.json")
    registry.add_argument("--check", action="store_true")
    compare = sub.add_parser("compare", help="Classify two runs for apples-to-apples use")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "import":
        raw = load_json(args.input)
        models = args.model or models_in(raw, args.suite)
        if not models:
            raise EvidenceError("No models found in source result")
        unknown = sorted(set(models) - set(models_in(raw, args.suite)))
        if unknown:
            raise EvidenceError("Models not present in source: " + ", ".join(unknown))
        created = []
        for model in models:
            created.append(create_bundle(
                args.input.resolve(), args.suite, model, raw, cohort=args.cohort,
                provider_kind=args.provider_kind, provider=args.provider, runtime=args.runtime,
                agent=args.agent, replicate_index=args.replicate_index,
                replicate_count=args.replicate_count, seed=args.seed,
                output_root=args.output_root.resolve(), imported=True,
            ))
        print(f"Created {len(created)} immutable {args.suite} bundles")
        for path in created:
            print(path)
        return 0
    if args.command == "validate":
        bundles = args.paths or sorted(path.parent for path in RUNS_ROOT.glob("*/manifest.json"))
        errors = [error for bundle in bundles for error in validate_bundle(bundle)]
        if errors:
            raise EvidenceError("Validation failed:\n- " + "\n- ".join(errors))
        print(f"VALID: {len(bundles)} evidence bundles")
        return 0
    if args.command == "registry":
        existing = load_json(args.output) if args.check and args.output.exists() else None
        generated = build_registry(args.output.parent, generated_at=existing.get("generated_at") if existing else None)
        if args.check:
            if existing != generated:
                raise EvidenceError(f"Registry is stale: run {Path(__file__).name} registry")
            print(f"VALID: registry contains {generated['run_count']} runs")
            return 0
        write_json(args.output, generated)
        print(f"Wrote {args.output} with {generated['run_count']} runs")
        return 0
    left_path = args.left / "manifest.json" if args.left.is_dir() else args.left
    right_path = args.right / "manifest.json" if args.right.is_dir() else args.right
    print(json.dumps(comparability(load_json(left_path), load_json(right_path)), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
