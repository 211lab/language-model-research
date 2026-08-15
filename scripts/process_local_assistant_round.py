#!/usr/bin/env python3
"""Validate and publish one comparable local assistant-benchmark round."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = REPO_ROOT / "docs" / "assistant-benchmark" / "model-results.csv"
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "assistant-benchmark" / "latest-round.json"
WORKSPACE_ROOT = REPO_ROOT.parent
STEADYBURN_SEED = (
    REPO_ROOT / "docs" / "model-comparisons" / "google-gemini-3-5-flash-lite"
    / "2026-08-07-master-your-tasks-prioritization-and-time-management" / "SEED.md"
)
FIELDS = [
    "model", "display_name", "run_status", "assistant_score", "outcome", "tool_use",
    "grounding", "state", "english", "safety", "efficiency", "tasks_passed",
    "tasks_total", "task_pass_rate", "tool_call_success_rate", "median_task_seconds",
    "total_task_seconds", "cold_start_seconds", "cold_ttft_seconds", "openclaw_seconds",
    "openclaw_ttft_seconds", "latency_total_seconds", "tool_call_detected",
]


def load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc


def require_equal(label: str, left: Any, right: Any) -> None:
    if left != right:
        raise SystemExit(f"Round is not comparable: {label} differs ({left!r} != {right!r})")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_text_sha256(path: Path) -> str:
    """Match the latency runner's canonicalized text hash."""
    return hashlib.sha256(path.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()


def build_rows(assistant: dict[str, Any], latency: dict[str, Any], seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    assistant_meta = assistant["metadata"]
    latency_meta = latency["metadata"]
    require_equal("assistant seed", assistant_meta.get("seed"), seed)
    require_equal("latency seed", latency_meta.get("seed"), seed)
    require_equal("assistant run label", assistant_meta.get("run_label", "local"), "local")
    require_equal(
        "fixture hash", assistant_meta.get("fixture_sha256"),
        sha256(WORKSPACE_ROOT / "assistant_benchmark_fixtures" / "base_environment.json"),
    )
    require_equal(
        "task-suite hash", assistant_meta.get("tasks_sha256"),
        sha256(WORKSPACE_ROOT / "assistant_benchmark_fixtures" / "tasks.json"),
    )
    # The assistant runner records the file-byte hash, whereas the latency runner
    # records its newline-normalized prompt-content hash. Validate both against
    # the same canonical SteadyBurn seed file rather than falsely comparing hash
    # encodings that intentionally differ.
    require_equal("assistant canonical SteadyBurn seed hash", assistant_meta.get("steadyburn_seed_sha256"), sha256(STEADYBURN_SEED))
    require_equal("latency canonical SteadyBurn seed hash", latency_meta.get("steadyburn_seed_sha256"), normalized_text_sha256(STEADYBURN_SEED))

    assistant_models = assistant_meta.get("selected_models", [])
    latency_models = latency_meta.get("selected_models", [])
    require_equal("selected model set", set(assistant_models), set(latency_models))
    require_equal("one result per assistant model", len(assistant_models), len(assistant["model_summaries"]))
    require_equal("one result per latency model", len(latency_models), len(latency["results"]))

    assistant_by_model = {row["model"]: row for row in assistant["model_summaries"]}
    latency_by_model = {row["model"]: row for row in latency["results"]}
    rows: list[dict[str, Any]] = []
    for model in sorted(assistant_models):
        score = assistant_by_model[model]
        timing = latency_by_model[model]
        if timing["status"] != "ok":
            raise SystemExit(f"Latency result is not usable for {model}: {timing.get('error', timing['status'])}")
        category = score["category_scores"]
        rows.append({
            "model": model,
            "display_name": score["display_name"],
            "run_status": score["status"],
            "assistant_score": score["overall_score"],
            "outcome": category["outcome"], "tool_use": category["tool_use"],
            "grounding": category["grounding"], "state": category["state"],
            "english": category["english"], "safety": category["safety"],
            "efficiency": category["efficiency"], "tasks_passed": score["tasks_passed"],
            "tasks_total": score["tasks_total"], "task_pass_rate": score["task_pass_rate"],
            "tool_call_success_rate": score["tool_call_success_rate"],
            "median_task_seconds": score["median_task_seconds"], "total_task_seconds": score["total_task_seconds"],
            "cold_start_seconds": timing["cold_start_seconds"],
            "cold_ttft_seconds": timing["cold_ttft_seconds"],
            "openclaw_seconds": timing["openclaw_seconds"],
            "openclaw_ttft_seconds": timing["openclaw_ttft_seconds"],
            "latency_total_seconds": timing["total_seconds"],
            "tool_call_detected": timing["tool_call_detected"],
        })
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cohort": "local",
        "seed": seed,
        "model_count": len(rows),
        "task_count_per_model": len(assistant_meta["selected_tasks"]),
        "fixture_sha256": assistant_meta["fixture_sha256"],
        "tasks_sha256": assistant_meta["tasks_sha256"],
        "steadyburn_seed_sha256": assistant_meta["steadyburn_seed_sha256"],
        "assistant_protocol": assistant_meta["protocol"],
        "latency_protocol": latency_meta["cold_start_control"],
        "primer": "One fixed READY primer request is sent after each model switch before the assistant workload.",
    }
    return rows, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assistant-results", required=True, type=Path)
    parser.add_argument("--latency-results", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--merge", action="store_true",
        help="Replace or add the validated rows in an existing local-results CSV instead of replacing the cohort.",
    )
    parser.add_argument("--build", action="store_true", help="Regenerate the published dashboard after validation")
    args = parser.parse_args()

    rows, manifest = build_rows(load(args.assistant_results), load(args.latency_results), args.seed)
    if args.merge and args.output.exists():
        with args.output.open(encoding="utf-8", newline="") as handle:
            existing = list(csv.DictReader(handle))
        by_model = {row["model"]: row for row in existing}
        by_model.update({row["model"]: row for row in rows})
        rows = [by_model[model] for model in sorted(by_model)]
        manifest["published_model_count"] = len(rows)
        manifest["merge_mode"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Validated {len(rows)} local models with seed {args.seed}; wrote {args.output}")
    if args.build:
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "build_radar.py")], check=True, cwd=REPO_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
