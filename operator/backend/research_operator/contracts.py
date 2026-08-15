"""Stable request and job contracts shared by the API and workers.

The public API intentionally keeps local source identity separate from a model's
display name. A Hugging Face repository can contain several GGUF quants, so a
published local result is only comparable when the source repository, revision,
and selected file are all recorded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable


LOCAL_PROVIDER = "local"
OPENROUTER_PROVIDER = "openrouter"
PROVIDERS = frozenset({LOCAL_PROVIDER, OPENROUTER_PROVIDER})
COHORTS = frozenset({"editorial", "assistant"})
DEFAULT_ASSISTANT_MAX_TOKENS = 768


class ContractError(ValueError):
    """Raised when an operator request would create an unsafe or ambiguous run."""


def _text(value: Any, field: str, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ContractError(f"{field} must be text")
    normalized = value.strip()
    if required and not normalized:
        raise ContractError(f"{field} is required")
    return normalized


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{field} must be true or false")
    return value


def _positive_number(value: Any, field: str, *, required: bool = False) -> float | None:
    if value in (None, ""):
        if required:
            raise ContractError(f"{field} is required")
        return None
    if isinstance(value, bool):
        raise ContractError(f"{field} must be a number")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{field} must be a number") from exc
    if numeric <= 0:
        raise ContractError(f"{field} must be greater than zero")
    return numeric


def local_model_slug(source_repo: str, source_file: str = "") -> str:
    """Create a readable, deterministic fallback model identifier."""
    source = f"{source_repo}-{source_file}" if source_file else source_repo
    return re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")[:120]


def local_identity_key(source_repo: str, source_revision: str, source_file: str) -> str:
    selected = source_file or "auto"
    return f"local:{source_repo}@{source_revision}:{selected}"


def openrouter_identity_key(model_ref: str) -> str:
    return f"openrouter:{model_ref}"


@dataclass(frozen=True)
class ModelSubmission:
    """An operator's request to benchmark one model across selected cohorts."""

    provider: str
    model_ref: str
    display_name: str
    cohorts: tuple[str, ...]
    source_repo: str = ""
    source_file: str = ""
    source_revision: str = "main"
    local_model_max_gib: float | None = None
    allow_capacity_override: bool = False
    operator_acknowledged_idle: bool = False
    confirm_paid_run: bool = False
    target_cost_ceiling_usd: float | None = None
    judge_cost_ceiling_usd: float | None = None
    assistant_max_tokens: int = DEFAULT_ASSISTANT_MAX_TOKENS

    @property
    def identity_key(self) -> str:
        if self.provider == LOCAL_PROVIDER:
            return local_identity_key(self.source_repo, self.source_revision, self.source_file)
        return openrouter_identity_key(self.model_ref)

    def as_payload(self) -> dict[str, Any]:
        return asdict(self) | {"identity_key": self.identity_key}


def _cohorts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ContractError("cohorts must be a non-empty list")
    values: list[str] = []
    for item in value:
        cohort = _text(item, "cohorts item", required=True).lower()
        if cohort not in COHORTS:
            choices = ", ".join(sorted(COHORTS))
            raise ContractError(f"unknown cohort {cohort!r}; choose {choices}")
        if cohort not in values:
            values.append(cohort)
    return tuple(values)


def parse_model_submission(payload: dict[str, Any]) -> ModelSubmission:
    """Validate a UI payload before it is allowed to create paid or local work."""
    if not isinstance(payload, dict):
        raise ContractError("request body must be an object")
    provider = _text(payload.get("provider"), "provider", required=True).lower()
    if provider not in PROVIDERS:
        raise ContractError("provider must be local or openrouter")
    cohorts = _cohorts(payload.get("cohorts"))
    source_repo = _text(payload.get("source_repo"), "source_repo")
    source_file = _text(payload.get("source_file"), "source_file")
    source_revision = _text(payload.get("source_revision", "main"), "source_revision", required=True)
    model_ref = _text(payload.get("model_ref"), "model_ref")
    display_name = _text(payload.get("display_name"), "display_name")
    local_model_max_gib = _positive_number(payload.get("local_model_max_gib"), "local_model_max_gib")
    allow_capacity_override = _bool(payload.get("allow_capacity_override", False), "allow_capacity_override")
    operator_acknowledged_idle = _bool(
        payload.get("operator_acknowledged_idle", False), "operator_acknowledged_idle"
    )
    confirm_paid_run = _bool(payload.get("confirm_paid_run", False), "confirm_paid_run")
    target_cost_ceiling_usd = _positive_number(
        payload.get("target_cost_ceiling_usd"), "target_cost_ceiling_usd"
    )
    judge_cost_ceiling_usd = _positive_number(
        payload.get("judge_cost_ceiling_usd"), "judge_cost_ceiling_usd"
    )
    assistant_max_tokens = payload.get("assistant_max_tokens", DEFAULT_ASSISTANT_MAX_TOKENS)
    if isinstance(assistant_max_tokens, bool):
        raise ContractError("assistant_max_tokens must be an integer")
    try:
        assistant_max_tokens = int(assistant_max_tokens)
    except (TypeError, ValueError) as exc:
        raise ContractError("assistant_max_tokens must be an integer") from exc
    if assistant_max_tokens != DEFAULT_ASSISTANT_MAX_TOKENS:
        raise ContractError(
            f"assistant_max_tokens is fixed at {DEFAULT_ASSISTANT_MAX_TOKENS} for comparable results"
        )

    if provider == LOCAL_PROVIDER:
        if not source_repo:
            raise ContractError("source_repo is required for a local model")
        if not model_ref:
            model_ref = local_model_slug(source_repo, source_file)
        if not display_name:
            display_name = model_ref.replace("-", " ").title()
        if not operator_acknowledged_idle:
            raise ContractError(
                "operator_acknowledged_idle must be true before a local model can switch"
            )
        if target_cost_ceiling_usd is not None or confirm_paid_run:
            raise ContractError("paid-run options are only valid for OpenRouter models")
    else:
        if not model_ref or "/" not in model_ref:
            raise ContractError("model_ref must be an exact OpenRouter ID such as provider/model")
        if not display_name:
            display_name = model_ref
        if not confirm_paid_run:
            raise ContractError("confirm_paid_run must be true before paid work is queued")
        if target_cost_ceiling_usd is None:
            raise ContractError("target_cost_ceiling_usd is required for a paid OpenRouter run")
        if "editorial" in cohorts and judge_cost_ceiling_usd is None:
            raise ContractError("judge_cost_ceiling_usd is required for editorial scoring")
        if source_repo or source_file:
            raise ContractError("source_repo and source_file are only valid for local models")

    return ModelSubmission(
        provider=provider,
        model_ref=model_ref,
        display_name=display_name,
        cohorts=cohorts,
        source_repo=source_repo,
        source_file=source_file,
        source_revision=source_revision,
        local_model_max_gib=local_model_max_gib,
        allow_capacity_override=allow_capacity_override,
        operator_acknowledged_idle=operator_acknowledged_idle,
        confirm_paid_run=confirm_paid_run,
        target_cost_ceiling_usd=target_cost_ceiling_usd,
        judge_cost_ceiling_usd=judge_cost_ceiling_usd,
        assistant_max_tokens=assistant_max_tokens,
    )


def make_job_payload(submission: ModelSubmission, cohort: str) -> dict[str, Any]:
    if cohort not in submission.cohorts:
        raise ContractError(f"{cohort} was not selected for this submission")
    return submission.as_payload() | {"cohort": cohort}


def model_labels_for_identity(rows: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Return identity-key/display-name pairs without hiding alternate quants."""
    labels: dict[str, str] = {}
    for row in rows:
        identity = str(row.get("identity_key") or "").strip()
        label = str(row.get("display_name") or row.get("model_ref") or "").strip()
        if identity and label:
            labels[identity] = label
    return labels
