"""Daily discovery of eligible local GGUFs exposed by the established endpoint."""

from __future__ import annotations

import argparse
import json
import time
from typing import TYPE_CHECKING, Any
from urllib.request import urlopen

from .config import Settings
from .contracts import ModelSubmission, local_identity_key

if TYPE_CHECKING:
    from .repository import Repository


def _provider_models(endpoint: str) -> list[dict[str, Any]]:
    with urlopen(f"{endpoint.rstrip('/')}/v1/models", timeout=10) as response:  # nosec B310 - operator endpoint
        payload = json.loads(response.read().decode("utf-8"))
    return [item for item in payload.get("data", []) if isinstance(item, dict)]


def _published_identities(settings: Settings) -> set[str]:
    identities: set[str] = set()
    for relative in ("model-comparison.json", "assistant-benchmark.json"):
        path = settings.research_root / relative
        if not path.exists():
            continue
        try:
            for item in json.loads(path.read_text(encoding="utf-8")).get("models", []):
                identity = str(item.get("identity_key") or "")
                if identity.startswith("local:"):
                    identities.add(identity)
        except (OSError, ValueError, TypeError):
            continue
    return identities


def _submission(
    item: dict[str, Any], settings: Settings, *, idle_acknowledged: bool
) -> ModelSubmission | None:
    model_ref = str(item.get("id") or "").strip()
    meta = ((item.get("meta") or {}).get("llamaswap") or {})
    repo, source_file = str(meta.get("sourceRepo") or ""), str(meta.get("sourceFile") or "")
    description = str(item.get("description") or "").lower()
    output = ((item.get("architecture") or {}).get("output_modalities") or ["text"])
    if not model_ref or not repo or not source_file or "text" not in output:
        return None
    if "embedding" in model_ref.lower() or "image" in model_ref.lower() or "image" in description:
        return None
    is_q4 = "q4" in source_file.lower()
    display_name = str(item.get("name") or model_ref).strip()
    if not display_name.lower().endswith("(local)"):
        display_name = f"{display_name} (Local)"
    return ModelSubmission(
        provider="local",
        model_ref=model_ref,
        display_name=display_name,
        cohorts=("editorial", "assistant"),
        source_repo=repo,
        source_file=source_file,
        source_revision=str(meta.get("sourceRevision") or "main"),
        local_model_max_gib=settings.discovery_local_model_max_gib if is_q4 else None,
        allow_capacity_override=is_q4,
        # This is intentionally a deployment-level acknowledgement, never an
        # assumption based only on /v1/models. That route says what is loaded;
        # it cannot prove that llama.cpp is not processing tokens.
        operator_acknowledged_idle=idle_acknowledged,
    )


def scan_once(settings: Settings, repository: Repository) -> list[dict[str, Any]]:
    published = _published_identities(settings)
    results: list[dict[str, Any]] = []
    for item in _provider_models(settings.local_ai_base_url):
        submission = _submission(
            item, settings, idle_acknowledged=settings.discovery_idle_acknowledged
        )
        if submission is None:
            continue
        snapshot = str((((item.get("meta") or {}).get("llamaswap") or {}).get("sourceSnapshot") or ""))
        identity = local_identity_key(submission.source_repo, submission.source_revision, submission.source_file)
        if identity in published:
            results.append({"model": submission.model_ref, "queued": False, "reason": "already-published"})
            continue
        if not settings.discovery_idle_acknowledged:
            results.append(
                {
                    "model": submission.model_ref,
                    "queued": False,
                    "reason": "awaiting-idle-acknowledgement",
                }
            )
            continue
        details = {"source_snapshot": snapshot, "provider_model": item.get("id"), "discovered_name": item.get("name")}
        results.append(repository.enqueue_discovered_local_run(submission, harness_contract_id=settings.harness_contract_id, details=details))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    from .repository import Repository

    repository = Repository(settings.database_dsn)
    while True:
        scan_once(settings, repository)
        if args.once:
            return 0
        time.sleep(settings.discovery_interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
