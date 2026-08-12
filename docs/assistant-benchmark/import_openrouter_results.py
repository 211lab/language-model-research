#!/usr/bin/env python3
"""Normalize a completed OpenRouter assistant run for the static dashboard."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


OUTPUT_FIELDS = [
    "model", "display_name", "run_status", "assistant_score", "outcome", "tool_use",
    "grounding", "state", "english", "safety", "efficiency", "tasks_passed",
    "tasks_total", "task_pass_rate", "tool_call_success_rate", "median_task_seconds",
    "total_task_seconds", "cold_start_seconds", "cold_ttft_seconds", "openclaw_seconds",
    "openclaw_ttft_seconds", "latency_total_seconds", "tool_call_detected", "provider",
    "benchmark_track", "error",
]


def normalize(source: Path, destination: Path) -> int:
    rows: list[dict[str, str]] = []
    with source.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = {field: "" for field in OUTPUT_FIELDS}
            for field in OUTPUT_FIELDS:
                if field in raw:
                    row[field] = raw[field]
            row["run_status"] = raw.get("status", "")
            row["assistant_score"] = raw.get("overall_score", "0")
            for old, new in (
                ("outcome_score", "outcome"), ("tool_use_score", "tool_use"),
                ("grounding_score", "grounding"), ("state_score", "state"),
                ("english_score", "english"), ("safety_score", "safety"),
                ("efficiency_score", "efficiency"),
            ):
                row[new] = raw.get(old, "0")
            row["provider"] = "OpenRouter"
            row["benchmark_track"] = "openrouter"
            row["tool_call_detected"] = "false"
            row["cold_start_seconds"] = "0"
            row["cold_ttft_seconds"] = "0"
            row["openclaw_seconds"] = "0"
            row["openclaw_ttft_seconds"] = "0"
            row["latency_total_seconds"] = "0"
            rows.append(row)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Completed run's model_summary.csv")
    parser.add_argument("--destination", type=Path, default=Path(__file__).with_name("openrouter-model-results.csv"))
    parser.add_argument("--manifest", type=Path, help="Optional completed run's results.json")
    args = parser.parse_args()
    count = normalize(args.source, args.destination)
    if args.manifest:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        metadata = data.get("metadata", {})
        manifest = {
            "schema_version": 1,
            "cohort": "openrouter",
            "seed": metadata.get("seed", 42),
            "model_count": count,
            "task_count_per_model": metadata.get("task_count", 21),
            "fixture_sha256": "ea2601bcb637a9c66563e91015f15a007a0a06f7d88532ec218c8c178903efb9",
            "tasks_sha256": "907017aa0d29639967cd0c0702764b73e7cc8ebbf254625fcc07b63e13b4428e",
            "source_run": str(args.manifest),
            "max_tokens": metadata.get("max_tokens", 768),
            "timeout_seconds": metadata.get("timeout_seconds", 120),
        }
        args.destination.with_name("openrouter-round.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Normalized {count} OpenRouter assistant models into {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
