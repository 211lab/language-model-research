"""Safe adapter around the existing llama.cpp model-switcher script."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import shlex
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from .config import Settings
from .contracts import ContractError, ModelSubmission
from .process import run_streaming


@dataclass(frozen=True)
class LocalCatalogEntry:
    model_ref: str
    display_name: str
    source_repo: str
    source_file: str
    source_revision: str
    source_snapshot: str
    active: bool
    capabilities: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActivatedLocalModel:
    model_ref: str
    source_repo: str
    source_file: str
    source_revision: str
    source_snapshot: str
    model_path: str
    switched: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_shell_environment(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        try:
            token = shlex.split(line, posix=True)[0]
        except ValueError:
            token = line
        key, value = token.split("=", 1)
        values[key] = value
    return values


def _snapshot_from_model_path(model_path: str) -> str:
    normalized = model_path.replace("\\", "/")
    match = re.search(r"/snapshots/([^/]+)/", normalized)
    return match.group(1) if match else ""


def _metadata_from_model(spec: dict[str, Any]) -> tuple[str, str, str, str]:
    metadata = spec.get("metadata") if isinstance(spec.get("metadata"), dict) else {}
    repo = str(metadata.get("sourceRepo") or "").strip()
    source_file = str(metadata.get("sourceFile") or "").strip()
    revision = str(metadata.get("sourceRevision") or "main").strip() or "main"
    description = str(spec.get("description") or "")
    if not repo:
        match = re.search(r"Local GGUF from\s+([^\s]+)", description)
        if match:
            repo = match.group(1)
    command = str(spec.get("cmd") or "")
    if not source_file:
        match = re.search(r"--model\s+([^\s]+\.gguf)", command)
        if match:
            source_file = Path(match.group(1)).name
    return repo, source_file, revision, _snapshot_from_model_path(command)


def local_catalog(config_path: Path, environment_path: Path) -> list[dict[str, Any]]:
    """Read registered chat models without touching the inference endpoint."""
    if not config_path.exists():
        return []
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    models = data.get("models") if isinstance(data, dict) else {}
    if not isinstance(models, dict):
        return []
    current = _read_shell_environment(environment_path)
    active_ref = current.get("LLAMA_MODEL_ID", "")
    entries: list[LocalCatalogEntry] = []
    for model_ref, raw in models.items():
        if not isinstance(raw, dict):
            continue
        capabilities_raw = raw.get("capabilities") if isinstance(raw.get("capabilities"), dict) else {}
        output_capabilities = capabilities_raw.get("out", ["text"])
        if not isinstance(output_capabilities, list) or "text" not in output_capabilities:
            continue
        if "embedding" in str(model_ref).lower():
            continue
        source_repo, source_file, source_revision, source_snapshot = _metadata_from_model(raw)
        entries.append(
            LocalCatalogEntry(
                model_ref=str(model_ref),
                display_name=str(raw.get("name") or model_ref),
                source_repo=source_repo,
                source_file=source_file,
                source_revision=source_revision,
                source_snapshot=source_snapshot,
                active=str(model_ref) == active_ref,
                capabilities=tuple(str(value) for value in output_capabilities),
            )
        )
    return [entry.as_dict() for entry in sorted(entries, key=lambda item: item.display_name.lower())]


class LocalSwitcher:
    """Call the established switcher without changing its endpoint or port."""

    def __init__(self, settings: Settings, log: Callable[[str], None]) -> None:
        self._settings = settings
        self._log = log

    def activate(self, submission: ModelSubmission) -> ActivatedLocalModel:
        if submission.provider != "local":
            raise ContractError("LocalSwitcher can only activate local submissions")
        if not submission.operator_acknowledged_idle:
            raise ContractError("local switching requires the operator idle acknowledgement")
        script = self._settings.local_switcher_script
        if not script.exists():
            raise RuntimeError(
                f"Local switcher script is unavailable: {script}. Set LLAMA_SWITCHER_SCRIPT before queuing local work."
            )
        before = _read_shell_environment(self._settings.local_switcher_environment)
        requested_exact_file = bool(submission.source_file)
        already_active = (
            requested_exact_file
            and before.get("LLAMA_MODEL_REPO") == submission.source_repo
            and before.get("LLAMA_MODEL_FILE") == submission.source_file
            and before.get("LLAMA_MODEL_REVISION", "main") == submission.source_revision
        )
        if already_active:
            self._log("Requested exact GGUF is already active; preserving the running model.")
            return self._activated_from_environment(before, switched=False)

        if (
            submission.local_model_max_gib is not None
            and submission.local_model_max_gib > self._settings.local_model_max_gib
            and not submission.allow_capacity_override
        ):
            raise ContractError(
                "The requested GGUF budget exceeds LOCAL_MODEL_MAX_GIB; set allow_capacity_override only after explicit operator review."
            )

        command = ["bash", str(script), "--revision", submission.source_revision]
        if submission.source_file:
            command.extend(["--file", submission.source_file])
        command.append(submission.source_repo)
        environment: dict[str, str] = {}
        if submission.local_model_max_gib is not None:
            environment["LLAMA_MODEL_MAX_GIB"] = str(submission.local_model_max_gib)
        # Deliberately do not set LLAMA_API_BASE / --api-base. The switcher keeps
        # the endpoint it was already configured to monitor (normally localhost:11434).
        self._log(
            "Switch request accepted after operator idle acknowledgement; preserving the switcher's configured endpoint."
        )
        run_streaming(command, cwd=script.parent, environment=environment, on_line=self._log)
        after = _read_shell_environment(self._settings.local_switcher_environment)
        activated = self._activated_from_environment(after, switched=True)
        self._log(
            f"Activated {activated.model_ref} from {activated.source_repo}/{activated.source_file}."
        )
        if self._settings.local_idle_buffer_seconds:
            self._log(
                f"Holding the configured {self._settings.local_idle_buffer_seconds:g}-second buffer before the benchmark."
            )
            time.sleep(self._settings.local_idle_buffer_seconds)
        return activated

    @staticmethod
    def _activated_from_environment(values: dict[str, str], *, switched: bool) -> ActivatedLocalModel:
        model_ref = values.get("LLAMA_MODEL_ID", "").strip()
        repo = values.get("LLAMA_MODEL_REPO", "").strip()
        source_file = values.get("LLAMA_MODEL_FILE", "").strip()
        if not model_ref or not repo or not source_file:
            raise RuntimeError("The switcher did not record an exact local model identity in current-model.env")
        return ActivatedLocalModel(
            model_ref=model_ref,
            source_repo=repo,
            source_file=source_file,
            source_revision=values.get("LLAMA_MODEL_REVISION", "main").strip() or "main",
            source_snapshot=_snapshot_from_model_path(values.get("LLAMA_MODEL_PATH", "")),
            model_path=values.get("LLAMA_MODEL_PATH", "").strip(),
            switched=switched,
        )
