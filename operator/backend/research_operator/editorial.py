"""Generate editorial assessment bundles through pinned Gutenberg, then score and publish them."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable

from .assistant import _publish_lock
from .config import Settings
from .process import run_streaming


def _safe_model_dir(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120]


def _disable_thinking(model_ref: str) -> bool:
    value = model_ref.lower()
    return any(marker in value for marker in ("qwen", "qwythos", "gemma-4-12b"))


GENERATOR_COMMIT = "7db89c344ea63af62998eeb10f58a2397b8c0f03"
GENERATOR_PROFILE = "steadyburn-profile-v1"


def _provider_configuration(settings: Settings, provider: str) -> tuple[str, str, str, str]:
    if provider == "local":
        return "openai-compatible", settings.local_ai_base_url, "openai-compatible", settings.editorial_local_image_model
    return "openrouter", settings.openrouter_base_url, "openrouter", settings.editorial_remote_image_model


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


def _write_compatibility_usage(bundle: Path, provider: str, model_ref: str) -> None:
    if provider != "openrouter":
        return
    usage = json.loads((bundle / "usage.json").read_text(encoding="utf-8"))
    lines = []
    for item in usage.get("usage", []):
        artifact = str(item.get("artifact", "")).lower()
        endpoint = "images/generations" if "image" in artifact or artifact.endswith(".png") else "chat/completions"
        lines.append(json.dumps({
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "model": item.get("model") or model_ref,
            "usage": item.get("usage") or {},
        }))
    (bundle / "OPENROUTER_USAGE.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _generator_revision(generator_root: Path) -> str:
    revision = subprocess.check_output(
        ["git", "-C", str(generator_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != GENERATOR_COMMIT:
        raise RuntimeError(f"Gutenberg checkout revision {revision} does not match pinned {GENERATOR_COMMIT}")
    return revision


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
    generator_commit: str,
    generator_manifest: dict[str, Any],
    generator_usage: dict[str, Any],
    source_sha256: str,
    assessment_brief: str,
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
        "purpose": "candidate-assessment",
        "generator": {
            "commit": generator_commit,
            "profile": generator_manifest.get("profile"),
            "source_sha256": source_sha256,
            "brief": assessment_brief,
            "title": generator_manifest.get("title"),
            "slug": generator_manifest.get("slug"),
            "date": generator_manifest.get("date"),
            "manifest": generator_manifest,
            "usage": generator_usage,
            "batch": generator_usage.get("batch", False),
            "batch_events": generator_usage.get("batch_events", []),
        },
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
        f"- Purpose: `{metadata['purpose']}`",
        f"- Gutenberg commit: `{generator_commit}`",
        f"- Gutenberg profile: `{generator_manifest.get('profile')}`",
        f"- Assessment source SHA-256: `{source_sha256}`",
        f"- Assessment brief: {assessment_brief}",
        f"- Selected tracks: `{', '.join(generator_manifest.get('selected_tracks', []))}`",
        f"- Batch enabled: `{str(generator_usage.get('batch', False)).lower()}`",
        f"- Generator source manifest: `{json.dumps(generator_manifest.get('sources', []), sort_keys=True)}`",
    ]
    for artifact in generator_manifest.get("artifacts", []):
        lines.append(f"- Artifact `{artifact.get('path')}` SHA-256 `{artifact.get('sha256')}`; dependencies: `{', '.join(artifact.get('depends_on', []))}`")
    lines.append(f"- Batch evidence: `{json.dumps(generator_usage.get('batch_events', []), sort_keys=True)}`")
    lines.append(f"- Provider token/cost usage: `{json.dumps(generator_usage.get('usage', []), sort_keys=True)}`")
    if provider == "openrouter":
        lines.append(f"- Provider-reported total cost: `${total:.6f}`")
    else:
        lines.append("- Provider-reported generation cost: `$0.000000 local baseline`")
    lines.extend([
        "",
        "## Gutenberg manifest",
        "",
        "```json",
        json.dumps(generator_manifest, indent=2, sort_keys=True),
        "```",
        "",
        "## Gutenberg usage",
        "",
        "```json",
        json.dumps(generator_usage, indent=2, sort_keys=True),
        "```",
    ])
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
    job_root = settings.runs_root / str(job["id"])
    job_root.mkdir(parents=True, exist_ok=True)
    content_dir = job_root / "editorial-candidate"
    if content_dir.exists():
        shutil.rmtree(content_dir)
    generator_root = settings.research_root / "tools" / "gutenberg"
    generator_revision = _generator_revision(generator_root)
    provider_name, endpoint, image_provider, image_model = _provider_configuration(settings, provider)
    brief = "Assess this fixed editorial seed as a complete SteadyBurn bundle. Preserve the seed's intent and produce clear, actionable, audience-ready content."
    environment: dict[str, str] = {
        "BURN_MAX_TOKENS": str(settings.editorial_max_tokens),
        "BURN_TIMEOUT_SECONDS": "1800",
    }
    if provider == "openrouter":
        if payload.get("target_cost_ceiling_usd"):
            environment["BURN_MAX_COST_USD"] = str(payload["target_cost_ceiling_usd"])
    if _disable_thinking(effective_model_ref):
        environment["BURN_DISABLE_THINKING"] = "1"
    environment["PYTHONPATH"] = str(generator_root / "ralph")
    pipeline_command = [
        "python", "-m", "gutenberg_ralph.interface", "generate",
        "--profile", GENERATOR_PROFILE,
        "--source", str(settings.editorial_seed_path),
        "--brief", brief,
        "--title", settings.editorial_title,
        "--slug", settings.editorial_slug,
        "--date", settings.editorial_date,
        "--provider", provider_name,
        "--model", effective_model_ref,
        "--provider-url", endpoint,
        "--image-provider", image_provider,
        "--image-model", image_model,
        "--image-provider-url", endpoint,
        "--output", str(content_dir),
        "--purpose", "candidate-assessment",
    ]
    if provider == "openrouter" and payload.get("openrouter_batch_mode") is True:
        pipeline_command.append("--batch")
    run_streaming(
        pipeline_command,
        cwd=settings.research_root,
        environment=environment,
        on_line=log,
    )
    generator_manifest = json.loads((content_dir / "manifest.json").read_text(encoding="utf-8"))
    generator_usage = json.loads((content_dir / "usage.json").read_text(encoding="utf-8"))
    if generator_manifest.get("purpose") != "candidate-assessment":
        raise RuntimeError("Gutenberg output is not labeled as candidate assessment")
    _write_compatibility_usage(content_dir, provider, effective_model_ref)

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
        generator_commit=generator_revision,
        generator_manifest=generator_manifest,
        generator_usage=generator_usage,
        source_sha256=hashlib.sha256(settings.editorial_seed_path.read_bytes()).hexdigest(),
        assessment_brief=brief,
    )
    judge_cap = float(payload.get("judge_cost_ceiling_usd") or 1.0)
    scoring_env = {
        "PYTHONPATH": str(settings.harness_root / "automation"),
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
        cwd=settings.research_root,
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
                cwd=settings.research_root,
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
