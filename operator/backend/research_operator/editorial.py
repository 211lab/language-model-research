"""Fixed-seed editorial benchmark runner and publisher.

The runner uses the same versioned prompts, seed, output bundle, rubric, and
readability compiler as the published research. It creates an isolated harness
copy per job instead of a Git worktree, so Docker workers never mutate source
files while generating an artifact.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable

import yaml

from .assistant import _publish_lock
from .config import Settings
from .process import run_streaming


def _safe_model_dir(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120]


def _disable_thinking(model_ref: str) -> bool:
    value = model_ref.lower()
    return any(marker in value for marker in ("qwen", "qwythos", "gemma-4-12b"))


def _provider_configuration(settings: Settings, provider: str, model_ref: str) -> tuple[str, str, str]:
    if provider == "local":
        return "openai-compatible", settings.local_ai_base_url, settings.editorial_local_image_model
    return "openrouter", settings.openrouter_base_url, settings.editorial_remote_image_model


def _copy_harness(settings: Settings, job_id: str) -> Path:
    if not (settings.harness_root / "scripts" / "burn-pipeline.py").exists():
        raise RuntimeError(f"Editorial harness is incomplete: {settings.harness_root}")
    workspace = settings.runs_root / job_id / "editorial-workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(
        settings.harness_root,
        workspace,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return workspace


def _configure_pipeline(
    source: Path,
    destination: Path,
    *,
    provider_kind: str,
    endpoint: str,
    text_model: str,
    image_model: str,
) -> None:
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("providers"), dict):
        raise RuntimeError(f"Editorial pipeline has no providers block: {source}")
    data["providers"]["text"] = {
        "kind": provider_kind,
        "providerUrl": endpoint,
        "model": text_model,
        "timeout_seconds": 1800,
        "retry_attempts": 3,
        "retry_wait_seconds": 10,
    }
    data["providers"]["image"] = {
        "kind": provider_kind,
        "providerUrl": endpoint,
        "model": image_model,
        "timeout_seconds": 1800,
        "retry_attempts": 3,
        "retry_wait_seconds": 10,
    }
    for step in data.get("steps", []):
        if not isinstance(step, dict):
            continue
        step["model"] = image_model if step.get("modality") == "image" else text_model
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")


def _usage_total(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        total += float((record.get("usage") or {}).get("cost", 0) or 0)
    return total


def _write_manifest(
    target: Path,
    *,
    provider: str,
    model_ref: str,
    source_repo: str,
    source_file: str,
    source_revision: str,
    source_snapshot: str,
    display_name: str,
    endpoint: str,
    run_id: str,
) -> None:
    usage_log = target / "OPENROUTER_USAGE.jsonl"
    total = _usage_total(usage_log)
    metadata = {
        "model": model_ref,
        "displayName": display_name,
        "provider": "local llama-swap" if provider == "local" else "OpenRouter",
        "endpoint": endpoint,
        "sourceRepo": source_repo,
        "sourceFile": source_file,
        "sourceRevision": source_revision,
        "sourceSnapshot": source_snapshot,
        "operatorRunId": run_id,
        "fixedSeed": "2026-08-07-master-your-tasks-prioritization-and-time-management",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
    (target / "MODEL_COMPARISON.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Model Comparison Run",
        "",
        f"- Model: `{model_ref}`",
        f"- Provider: {metadata['provider']}",
        f"- Endpoint: `{endpoint}`",
        f"- Source repository: `{source_repo or 'not applicable'}`",
        f"- Source GGUF: `{source_file or 'not applicable'}`",
        f"- Source revision: `{source_revision}`",
        f"- Resolved source snapshot: `{source_snapshot or 'not recorded'}`",
        "- Workload: fixed 2026-08-07 editorial seed and full text pipeline",
        f"- Run at (UTC): `{metadata['generatedAt']}`",
    ]
    if provider == "openrouter":
        lines.append(f"- Provider-reported total cost: `${total:.6f}`")
    else:
        lines.append("- Provider-reported generation cost: `$0.000000 local baseline`")
    (target / "MODEL_COMPARISON.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_editorial_benchmark(
    settings: Settings,
    job: dict[str, Any],
    *,
    effective_model_ref: str,
    effective_source_repo: str = "",
    effective_source_file: str = "",
    effective_source_revision: str = "main",
    effective_source_snapshot: str = "",
    log: Callable[[str], None],
) -> dict[str, Any]:
    """Generate the complete fixed editorial bundle, then score and publish it."""
    payload = dict(job["payload"])
    provider = str(payload["provider"])
    if not settings.editorial_seed_path.is_file():
        raise RuntimeError(f"Fixed editorial seed is missing: {settings.editorial_seed_path}")
    workspace = _copy_harness(settings, str(job["id"]))
    content_dir = workspace / "content" / "letters" / f"{settings.editorial_date}-{settings.editorial_slug}"
    provider_kind, endpoint, image_model = _provider_configuration(settings, provider, effective_model_ref)
    run_streaming(
        [
            "python", "scripts/burn-pipeline.py", "init-production",
            "--title", settings.editorial_title,
            "--slug", settings.editorial_slug,
            "--date", settings.editorial_date,
            "--force",
        ],
        cwd=workspace,
        on_line=log,
    )
    shutil.copy2(settings.editorial_seed_path, content_dir / "SEED.md")
    usage_log = content_dir / "OPENROUTER_USAGE.jsonl"
    environment: dict[str, str] = {
        "BURN_MAX_TOKENS": str(settings.editorial_max_tokens),
        "BURN_TIMEOUT_SECONDS": "1800",
    }
    if provider == "openrouter":
        environment["BURN_USAGE_LOG"] = str(usage_log)
        if payload.get("target_cost_ceiling_usd"):
            environment["BURN_MAX_COST_USD"] = str(payload["target_cost_ceiling_usd"])
    if _disable_thinking(effective_model_ref):
        environment["BURN_DISABLE_THINKING"] = "1"
    registry_path = f"tmp/operator-registry/{job['id']}.json"
    relative = content_dir.relative_to(workspace)
    context_command = [
        "python", "scripts/burn-pipeline.py",
        "--provider", provider_kind,
        "--provider-url", endpoint,
        "--model", effective_model_ref,
        "--registry-file", registry_path,
        "generate-step",
        "--step-id", "context",
        "--format", "markdown",
        "--prompt-file", "automation/prompts/burn/context.md",
        "--input", str(relative / "SEED.md"),
        "--output", str(relative / "CONTEXT.md"),
        "--title", settings.editorial_title,
        "--slug", settings.editorial_slug,
        "--date", settings.editorial_date,
        "--force",
    ]
    run_streaming(context_command, cwd=workspace, environment=environment, on_line=log)
    pipeline = workspace / "tmp" / "operator-pipelines" / f"{job['id']}.yaml"
    _configure_pipeline(
        content_dir / "pipeline.yaml",
        pipeline,
        provider_kind=provider_kind,
        endpoint=endpoint,
        text_model=effective_model_ref,
        image_model=image_model,
    )
    run_streaming(
        ["python", "scripts/burn-pipeline.py", "run", "--pipeline", str(pipeline), "--force"],
        cwd=workspace,
        environment=environment,
        on_line=log,
    )

    model_dir = _safe_model_dir(effective_model_ref)
    research_root = settings.research_root / "docs" / "model-comparisons"
    published = research_root / model_dir / f"{settings.editorial_date}-{settings.editorial_slug}"
    staging_root = settings.runs_root / str(job["id"]) / "editorial-staging"
    staged = staging_root / model_dir / f"{settings.editorial_date}-{settings.editorial_slug}"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    shutil.copytree(content_dir, staged)
    _write_manifest(
        staged,
        provider=provider,
        model_ref=effective_model_ref,
        source_repo=effective_source_repo or str(payload.get("source_repo") or ""),
        source_file=effective_source_file or str(payload.get("source_file") or ""),
        source_revision=effective_source_revision or str(payload.get("source_revision") or "main"),
        source_snapshot=effective_source_snapshot or str(payload.get("source_snapshot") or ""),
        display_name=str(payload.get("display_name") or effective_model_ref),
        endpoint=endpoint,
        run_id=str(job["run_id"]),
    )
    judge_cap = float(payload.get("judge_cost_ceiling_usd") or 1.0)
    scoring_env = {
        "PYTHONPATH": str(workspace / "automation"),
        "CONTENT_SCORING_EVIDENCE_MODEL": settings.editorial_evidence_model,
        "CONTENT_SCORING_JUDGE_MODEL": settings.editorial_judge_model,
        "CONTENT_SCORING_TIE_BREAK_MODEL": settings.editorial_tie_break_model,
    }
    log("Scoring the isolated editorial bundle before it can replace a published result.")
    run_streaming(
        [
            "python", "-m", "content_scoring.interface",
            "--root", str(staging_root),
            "--case-study", str(staged),
            "--max-cost", str(judge_cap),
            "--force",
        ],
        cwd=workspace,
        environment=scoring_env,
        on_line=log,
    )
    if not (staged / "CONTENT_SCORE.json").exists():
        raise RuntimeError("Editorial scoring completed without a CONTENT_SCORE.json result")

    lock = settings.operator_root / ".research-publish.lock"
    with _publish_lock(lock):
        backup = settings.runs_root / str(job["id"]) / "previous-published"
        if published.exists():
            shutil.move(str(published), str(backup))
        try:
            published.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged), str(published))
            log(f"Published fixed-seed editorial bundle to {published.relative_to(settings.research_root)}.")
            # Rebuild global aggregates from persisted case studies without an
            # evaluator request, then regenerate the static dashboards.
            run_streaming(
                [
                    "python", "-m", "content_scoring.interface",
                    "--root", str(research_root),
                    "--aggregate-existing",
                ],
                cwd=workspace,
                environment=scoring_env,
                on_line=log,
            )
            run_streaming(
                ["python", str(research_root / "analyze_readability.py"), "--root", str(research_root)],
                cwd=settings.research_root,
                on_line=log,
            )
            if provider == "openrouter":
                run_streaming(
                    ["python", str(research_root / "generate_cost_charts.py"), "--root", str(research_root)],
                    cwd=settings.research_root,
                    on_line=log,
                )
            run_streaming(
                ["python", str(settings.research_root / "scripts" / "build_radar.py")],
                cwd=settings.research_root,
                on_line=log,
            )
        except Exception:
            failed_publication = settings.runs_root / str(job["id"]) / "failed-publication"
            if published.exists():
                shutil.move(str(published), str(failed_publication))
            if backup.exists():
                published.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup), str(published))
            raise
    score_path = published / "CONTENT_SCORE.json"
    score = json.loads(score_path.read_text(encoding="utf-8")) if score_path.exists() else {}
    return {
        "published_case_study": str(published.relative_to(settings.research_root)),
        "model": effective_model_ref,
        "content_score": score.get("content_score"),
        "confidence": score.get("confidence"),
        "judge_model": (score.get("evaluator") or {}).get("judge_model"),
        "generation_cost_usd": _usage_total(published / "OPENROUTER_USAGE.jsonl"),
    }
