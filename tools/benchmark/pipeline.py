#!/usr/bin/env python3
"""Run serial, seeded benchmark suites and package every run as evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import assistant_benchmark as assistant
import benchmark as latency
import evidence


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
PROFILE_ROOT = SCRIPT_DIR / "profiles"
DEFAULT_SEED_DOCUMENT = (
    REPO_ROOT / "docs" / "model-comparisons" / "google-gemini-3-5-flash-lite"
    / "2026-08-07-master-your-tasks-prioritization-and-time-management" / "SEED.md"
)
SUITES = ("latency", "assistant", "editorial")


def load_profile(value: str) -> dict[str, Any]:
    path = Path(value)
    if not path.is_file():
        path = PROFILE_ROOT / f"{value}.json"
    profile = evidence.load_json(path)
    required = {
        "provider", "provider_kind", "endpoint_class", "base_url", "api", "cohort",
        "serial", "unload_between_models", "settle_seconds", "timeout_seconds",
    }
    missing = sorted(required - profile.keys())
    if missing:
        raise evidence.EvidenceError(f"Profile {path} is missing: {', '.join(missing)}")
    if not profile["serial"]:
        raise evidence.EvidenceError("This pipeline requires serial=true")
    profile["_path"] = str(path.resolve())
    return profile


def api_key(profile: dict[str, Any]) -> str | None:
    variable = str(profile.get("api_key_env") or "")
    return os.environ.get(variable) if variable else None


def discover(profile: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_base = latency.normalize_base_url(str(profile["base_url"]))
    base_url = raw_base if raw_base.endswith("/v1") else f"{raw_base}/v1"
    return assistant.discover_chat_models(base_url, api_key(profile), min(float(profile["timeout_seconds"]), 15))


def run_command(command: list[str], profile: dict[str, Any]) -> int:
    printable = " ".join(command[:3] + (["…"] if len(command) > 3 else []))
    print(f"  command: {printable}", flush=True)
    environment = os.environ.copy()
    key = api_key(profile)
    if key:
        environment["LOCAL_AI_API_KEY"] = key
    return subprocess.run(command, check=False, cwd=REPO_ROOT, env=environment).returncode


def suite_command(
    suite: str, profile: dict[str, Any], model: str, seed: int, output: Path,
    seed_document: Path, max_tasks: int | None, *, disable_thinking: bool,
    max_cost_usd: float | None, usage_log: Path | None, require_reported_cost: bool,
) -> list[str]:
    runner = "benchmark.py" if suite == "latency" else f"{suite}_benchmark.py"
    common = [
        sys.executable, str(SCRIPT_DIR / runner), "--base-url", str(profile["base_url"]),
        "--model", model, "--seed", str(seed), "--timeout", str(profile["timeout_seconds"]),
        "--settle-seconds", str(profile["settle_seconds"]), "--steadyburn-seed", str(seed_document),
        "--output-dir", str(output),
    ]
    if not profile["unload_between_models"]:
        common.append("--no-unload")
    if suite == "latency":
        common.extend(["--api", str(profile["api"])])
    else:
        common.extend(["--run-label", str(profile["cohort"])])
    if suite == "assistant" and max_tasks:
        common.extend(["--max-tasks", str(max_tasks)])
    if disable_thinking or model in set(profile.get("disable_thinking_models", [])):
        common.append("--disable-thinking")
    if max_cost_usd is not None:
        common.extend(["--max-cost-usd", str(max_cost_usd)])
    if usage_log is not None:
        common.extend(["--usage-log", str(usage_log)])
    if require_reported_cost:
        common.append("--require-reported-cost")
    return common


def run_pipeline(args: argparse.Namespace, profile: dict[str, Any]) -> list[Path]:
    available, _ = discover(profile)
    available_ids = {str(row["id"]) for row in available}
    if args.all_models:
        models = sorted(available_ids)
        if args.include:
            models = [model for model in models if re.search(args.include, model, re.IGNORECASE)]
        if args.exclude:
            models = [model for model in models if not re.search(args.exclude, model, re.IGNORECASE)]
    else:
        models = args.model
    if not models:
        raise evidence.EvidenceError("No models selected")
    unknown = [model for model in models if model not in available_ids]
    if unknown:
        raise evidence.EvidenceError("Models not advertised by endpoint: " + ", ".join(unknown))
    suites = list(SUITES if args.suite == "all" else [args.suite])
    execution_root = (args.work_root or (REPO_ROOT / ".benchmark-work" / evidence.slug(evidence.now_utc()))).resolve()
    execution_root.mkdir(parents=True, exist_ok=True)
    usage_log = args.usage_log.resolve() if args.usage_log else (
        execution_root / "provider-usage.jsonl"
        if args.max_cost_usd is not None or args.require_reported_cost else None
    )
    created: list[Path] = []
    total_suite_runs = len(models) * args.replicates * len(suites)
    suite_run = 0
    for model_index, model in enumerate(models, start=1):
        for replicate in range(1, args.replicates + 1):
            for suite_index, suite in enumerate(suites, start=1):
                suite_run += 1
                print(
                    f"\n[model {model_index}/{len(models)}] [replicate {replicate}/{args.replicates}] "
                    f"[suite {suite_index}/{len(suites)}; overall {suite_run}/{total_suite_runs}] {model} — {suite}",
                    flush=True,
                )
                raw_dir = execution_root / evidence.slug(model) / f"replicate-{replicate}" / suite
                exit_code = run_command(
                    suite_command(
                        suite, profile, model, args.seed, raw_dir, args.steadyburn_seed, args.max_tasks,
                        disable_thinking=args.disable_thinking, max_cost_usd=args.max_cost_usd,
                        usage_log=usage_log, require_reported_cost=args.require_reported_cost,
                    ),
                    profile,
                )
                source = raw_dir / "results.json"
                if not source.is_file():
                    raise evidence.EvidenceError(
                        f"{suite} runner exited {exit_code} without producing {source}"
                    )
                if exit_code:
                    print(f"  runner exit {exit_code}; retaining partial/error evidence", flush=True)
                raw = evidence.load_json(source)
                created.append(evidence.create_bundle(
                    source, suite, model, raw, cohort=str(profile["cohort"]),
                    provider_kind=str(profile["provider_kind"]), provider=str(profile["provider"]),
                    runtime=str(profile["endpoint_class"]), agent="research-pipeline",
                    replicate_index=replicate, replicate_count=args.replicates, seed=args.seed,
                    output_root=args.output_root.resolve(), imported=False,
                ))
                registry = evidence.build_registry(args.output_root.resolve())
                evidence.write_json(args.output_root.resolve() / "index.json", registry)
    return created


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list-models", help="List chat-capable models from a configured endpoint")
    listing.add_argument("--profile", default="titan-local")
    run = sub.add_parser("run", help="Run one or more models serially")
    run.add_argument("--profile", default="titan-local")
    selection = run.add_mutually_exclusive_group(required=True)
    selection.add_argument("--model", action="append", help="Exact model ID; repeatable and always serial")
    selection.add_argument("--all-models", action="store_true", help="Run every advertised chat model, serially")
    run.add_argument("--include", help="Regex filter used with --all-models")
    run.add_argument("--exclude", help="Regex exclusion used with --all-models")
    run.add_argument("--suite", choices=(*SUITES, "all"), default="all")
    run.add_argument("--replicates", type=int, default=1)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--steadyburn-seed", type=Path, default=DEFAULT_SEED_DOCUMENT)
    run.add_argument("--max-tasks", type=int, help="Assistant smoke-test limit; omit for publishable runs")
    run.add_argument("--disable-thinking", action="store_true")
    run.add_argument("--max-cost-usd", type=float, help="Shared provider-reported USD ceiling for the full serial round")
    run.add_argument("--usage-log", type=Path, help="Shared provider-cost JSONL ledger")
    run.add_argument("--require-reported-cost", action="store_true")
    run.add_argument("--work-root", type=Path, help="Execution directory; default is a new timestamped .benchmark-work child")
    run.add_argument("--output-root", type=Path, default=evidence.RUNS_ROOT)
    args = parser.parse_args(argv)
    if getattr(args, "replicates", 1) < 1:
        parser.error("--replicates must be at least 1")
    if getattr(args, "max_cost_usd", None) is not None and args.max_cost_usd <= 0:
        parser.error("--max-cost-usd must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    profile = load_profile(args.profile)
    if args.command == "list-models":
        models, excluded = discover(profile)
        print(json.dumps({"profile": profile["name"], "models": models, "excluded": excluded}, indent=2))
        return 0
    created = run_pipeline(args, profile)
    print(f"\nCompleted {len(created)} suite runs and rebuilt runs/index.json")
    for path in created:
        print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (evidence.EvidenceError, assistant.AssistantBenchmarkError, latency.BenchmarkError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: benchmark command failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode)
