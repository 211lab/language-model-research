"""Read the generated research datasets for the operator review UI.

Kept independent of FastAPI so the data contract can be verified without
starting a database or HTTP service.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_overview(settings: Settings) -> dict[str, Any]:
    editorial = _read_json(settings.research_root / "model-comparison.json")
    assistant = _read_json(settings.research_root / "assistant-benchmark.json")
    editorial_models = [
        {
            "model": item.get("model"),
            "display_name": item.get("display_name"),
            "company": item.get("company"),
            "identity_key": item.get("identity_key"),
            "source_repo": item.get("source_repo"),
            "source_file": item.get("source_file"),
            "source_revision": item.get("source_revision"),
            "source_snapshot": item.get("source_snapshot"),
            "case_study": item.get("case_study"),
            "content_score": item.get("content_score"),
            "confidence": item.get("confidence"),
            "cost_usd": item.get("cost_usd"),
            "cost_source": item.get("cost_source"),
            "categories": item.get("categories", {}),
            "readability": item.get("readability", {}),
        }
        for item in editorial.get("models", [])
        if isinstance(item, dict)
    ]
    assistant_models = [
        {
            "model": item.get("model"),
            "display_name": item.get("display_name"),
            "provider": item.get("provider"),
            "identity_key": item.get("identity_key"),
            "source_repo": item.get("source_repo"),
            "source_file": item.get("source_file"),
            "source_revision": item.get("source_revision"),
            "source_snapshot": item.get("source_snapshot"),
            "benchmark_track": item.get("benchmark_track"),
            "run_status": item.get("run_status"),
            "assistant_score": item.get("assistant_score"),
            "outcome": item.get("outcome"),
            "tool_use": item.get("tool_use"),
            "grounding": item.get("grounding"),
            "state": item.get("state"),
            "english": item.get("english"),
            "safety": item.get("safety"),
            "efficiency": item.get("efficiency"),
            "tasks_passed": item.get("tasks_passed"),
            "tasks_total": item.get("tasks_total"),
            "median_task_seconds": item.get("median_task_seconds"),
            "latency_total_seconds": item.get("latency_total_seconds"),
            "provider_reported_cost_usd": item.get("provider_reported_cost_usd"),
            "provider_cost_limit_usd": item.get("provider_cost_limit_usd"),
        }
        for item in assistant.get("models", [])
        if isinstance(item, dict)
    ]
    return {
        "editorial": {
            "generated_at": editorial.get("generated_at"),
            "model_count": len(editorial_models),
            "models": editorial_models,
            "awaiting_score": editorial.get("awaiting_score", []),
        },
        "assistant": {
            "generated_at": assistant.get("generated_at"),
            "model_count": len(assistant_models),
            "cohort_counts": assistant.get("cohort_counts", {}),
            "models": assistant_models,
        },
    }
