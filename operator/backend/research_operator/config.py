"""Environment-backed settings for API and worker containers."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _path(value: str | None, default: Path) -> Path:
    return Path(value).expanduser().resolve() if value else default.resolve()


def _number(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be numeric") from exc


@dataclass(frozen=True)
class Settings:
    database_dsn: str
    operator_root: Path
    research_root: Path
    harness_root: Path
    runs_root: Path
    local_ai_base_url: str
    openrouter_base_url: str
    local_switcher_script: Path
    local_switcher_config: Path
    local_switcher_environment: Path
    local_model_max_gib: float
    local_idle_buffer_seconds: float
    local_settle_seconds: float
    remote_timeout_seconds: float
    luna_model: str
    luna_preflight_max_tasks: int
    luna_preflight_max_tokens: int
    luna_preflight_max_cost_usd: float
    harness_contract_id: str
    assistant_max_tokens: int
    editorial_max_tokens: int
    editorial_judge_model: str
    editorial_evidence_model: str
    editorial_tie_break_model: str
    editorial_local_image_model: str
    editorial_remote_image_model: str
    editorial_title: str
    editorial_slug: str
    editorial_date: str
    editorial_seed_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        package_root = Path(__file__).resolve().parent
        default_operator_root = package_root.parents[1]
        # research_operator -> backend -> operator -> repository root
        default_research_root = package_root.parents[2]
        operator_root = _path(os.environ.get("OPERATOR_ROOT"), default_operator_root)
        research_root = _path(os.environ.get("RESEARCH_ROOT"), default_research_root)
        harness_root = _path(os.environ.get("EDITORIAL_HARNESS_ROOT"), operator_root / "harness")
        seed_default = (
            research_root
            / "docs"
            / "model-comparisons"
            / "google-gemini-3-5-flash-lite"
            / "2026-08-07-master-your-tasks-prioritization-and-time-management"
            / "SEED.md"
        )
        return cls(
            database_dsn=os.environ.get(
                "POSTGRES_DSN", "postgresql://research:research@db:5432/research"
            ),
            operator_root=operator_root,
            research_root=research_root,
            harness_root=harness_root,
            runs_root=_path(os.environ.get("OPERATOR_RUNS_ROOT"), operator_root / "runs"),
            local_ai_base_url=os.environ.get("LOCAL_AI_BASE_URL", "http://localhost:11434").rstrip("/"),
            openrouter_base_url=os.environ.get(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ).rstrip("/"),
            local_switcher_script=_path(
                os.environ.get("LLAMA_SWITCHER_SCRIPT"), Path("/switcher/switch-llama-model.sh")
            ),
            local_switcher_config=_path(
                os.environ.get("LLAMA_SWITCHER_CONFIG"), Path("/switcher/config.yaml")
            ),
            local_switcher_environment=_path(
                os.environ.get("LLAMA_SWITCHER_ENV"), Path("/switcher/current-model.env")
            ),
            local_model_max_gib=_number("LOCAL_MODEL_MAX_GIB", 20.0),
            local_idle_buffer_seconds=_number("LOCAL_IDLE_BUFFER_SECONDS", 10.0),
            local_settle_seconds=_number("LOCAL_SETTLE_SECONDS", 10.0),
            remote_timeout_seconds=_number("REMOTE_TIMEOUT_SECONDS", 900.0),
            luna_model=os.environ.get("LUNA_MODEL", "openai/gpt-5.6-luna"),
            luna_preflight_max_tasks=int(os.environ.get("LUNA_PREFLIGHT_MAX_TASKS", "1")),
            luna_preflight_max_tokens=int(os.environ.get("LUNA_PREFLIGHT_MAX_TOKENS", "128")),
            luna_preflight_max_cost_usd=_number("LUNA_PREFLIGHT_MAX_COST_USD", 0.10),
            harness_contract_id=os.environ.get(
                "HARNESS_CONTRACT_ID", "assistant-fixtures-v1-seed42-max768"
            ),
            assistant_max_tokens=int(os.environ.get("ASSISTANT_MAX_TOKENS", "768")),
            editorial_max_tokens=int(os.environ.get("EDITORIAL_MAX_TOKENS", "2048")),
            editorial_judge_model=os.environ.get("EDITORIAL_JUDGE_MODEL", "openai/gpt-5.6-luna"),
            editorial_evidence_model=os.environ.get(
                "EDITORIAL_EVIDENCE_MODEL", "deepseek/deepseek-v4-flash"
            ),
            editorial_tie_break_model=os.environ.get(
                "EDITORIAL_TIE_BREAK_MODEL", "openai/gpt-5.6-luna"
            ),
            editorial_local_image_model=os.environ.get(
                "EDITORIAL_LOCAL_IMAGE_MODEL", "unsloth-qwen-image-2512-gguf-qwen-image-2512-q4-k-m"
            ),
            editorial_remote_image_model=os.environ.get(
                "EDITORIAL_REMOTE_IMAGE_MODEL", "openai/gpt-5.4-image-2"
            ),
            editorial_title=os.environ.get(
                "EDITORIAL_TITLE", "Master Your Tasks: Prioritization and Time Management"
            ),
            editorial_slug=os.environ.get(
                "EDITORIAL_SLUG", "master-your-tasks-prioritization-and-time-management"
            ),
            editorial_date=os.environ.get("EDITORIAL_DATE", "2026-08-07"),
            editorial_seed_path=_path(os.environ.get("EDITORIAL_SEED_PATH"), seed_default),
        )
