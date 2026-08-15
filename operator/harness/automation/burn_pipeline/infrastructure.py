from __future__ import annotations

import os
import json
import subprocess
import tempfile
import re
import base64
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from .domain import (
    DevelopedModelEntry,
    GeneratedArtifact,
    GenerationModality,
    InferenceRequest,
    ModelRegistry,
    PipelineSpec,
    ProviderConfig,
    ProviderKind,
    SteadyBurnVerbIndex,
    SteadyBurnVerbIndexEntry,
    VerbTrackingStatus,
    extract_actionable_verb,
)


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def read_text(self, path: Path) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str, force: bool) -> None:
        resolved = self._resolve(path)
        if resolved.exists() and not force:
            raise FileExistsError(f"Output exists. Use --force to overwrite: {path}")
        if resolved.is_dir():
            raise IsADirectoryError(f"Output path is a directory: {path}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")

    def write_bytes(self, path: Path, content: bytes, force: bool) -> None:
        resolved = self._resolve(path)
        if resolved.exists() and not force:
            raise FileExistsError(f"Output exists. Use --force to overwrite: {path}")
        if resolved.is_dir():
            raise IsADirectoryError(f"Output path is a directory: {path}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(content)

    def exists(self, path: Path) -> bool:
        return self._resolve(path).exists()

    def glob(self, pattern: str) -> list[Path]:
        base = self._root
        return [path.relative_to(base) for path in base.glob(pattern)]

    def _resolve(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return self._root / path


class CodexCliAgent:
    def __init__(self, command: str = "codex", model: str | None = None, cwd: Path | None = None) -> None:
        self._command = command
        self._model = model
        self._cwd = cwd or Path.cwd()

    def generate(self, request: InferenceRequest) -> GeneratedArtifact:
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            output_file = tmp_dir / "last-message.txt"
            command = [
                self._command,
                "--ask-for-approval",
                "never",
                "exec",
                "--cd",
                str(self._cwd),
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--output-last-message",
                str(output_file),
            ]
            model = request.model or self._model
            if model:
                command.extend(["--model", model])
            command.append("-")

            completed = subprocess.run(
                command,
                input=request.prompt,
                text=True,
                capture_output=True,
                cwd=self._cwd,
                check=False,
            )
            if completed.returncode != 0:
                stderr_tail = "\n".join(completed.stderr.splitlines()[-40:])
                stdout_tail = "\n".join(completed.stdout.splitlines()[-40:])
                raise RuntimeError(
                    "Codex CLI generation failed"
                    f"\nstdout:\n{stdout_tail}"
                    f"\nstderr:\n{stderr_tail}"
                )
            if not output_file.exists():
                raise RuntimeError("Codex CLI did not write the last-message output file")
            return GeneratedArtifact(text=output_file.read_text(encoding="utf-8"))


class ChatCompletionsAdapter:
    def __init__(
        self,
        *,
        providerUrl: str,
        apiKey: str | None,
        model: str | None,
        timeout_seconds: float = 300.0,
        retry_attempts: int = 4,
        retry_wait_seconds: float = 75.0,
    ) -> None:
        self._provider_url = normalize_provider_url(providerUrl)
        self._api_key = apiKey
        self._model = model
        configured_timeout = os.environ.get("BURN_TIMEOUT_SECONDS")
        if configured_timeout:
            try:
                timeout_seconds = float(configured_timeout)
            except ValueError as exc:
                raise ValueError("BURN_TIMEOUT_SECONDS must be numeric") from exc
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = max(1, retry_attempts)
        self._retry_wait_seconds = max(0.0, retry_wait_seconds)

    def generate(self, request: InferenceRequest) -> GeneratedArtifact:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        with httpx.Client(timeout=self._timeout_seconds) as client:
            model = request.model or self._model or self._resolve_model(client, headers)
            payload: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": request.prompt}],
                "temperature": 0,
            }
            max_tokens = os.environ.get("BURN_MAX_TOKENS")
            if max_tokens:
                try:
                    payload["max_tokens"] = int(max_tokens)
                except ValueError as exc:
                    raise ValueError("BURN_MAX_TOKENS must be an integer") from exc
            if os.environ.get("BURN_DISABLE_THINKING", "").strip().lower() in {"1", "true", "yes"}:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            data = self._post_with_retries(
                client,
                f"{self._provider_url}/chat/completions",
                headers=headers,
                payload=payload,
            )

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response shape: {data}") from exc
        if not isinstance(content, str):
            raise RuntimeError(f"Unexpected LLM content type: {type(content).__name__}")
        record_usage(data, endpoint="chat/completions", requested_model=model)
        return GeneratedArtifact(text=content)

    def _resolve_model(self, client: httpx.Client, headers: dict[str, str]) -> str:
        response = client.get(f"{self._provider_url}/models", headers=headers)
        response.raise_for_status()
        data = response.json()
        models = data.get("data")
        if not isinstance(models, list) or not models:
            raise RuntimeError(f"Unable to resolve a default model from {self._provider_url}/models: {data}")
        first = models[0]
        if not isinstance(first, dict) or not isinstance(first.get("id"), str) or not first["id"].strip():
            raise RuntimeError(f"Unexpected model entry from {self._provider_url}/models: {first}")
        return first["id"].strip()

    def _post_with_retries(
        self,
        client: httpx.Client,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code in {502, 503, 504}:
                    raise httpx.HTTPStatusError(
                        f"Transient upstream status: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.ReadTimeout, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if not is_retryable_http_error(exc) or attempt >= self._retry_attempts:
                    raise
                time.sleep(self._retry_wait_seconds)
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected retry state")


IMAGE_SECTION_PATTERN = re.compile(r"(?ms)^# ([^\n]+)\n(.*?)(?=^# |\Z)")
IMAGE_DIMENSIONS_PATTERN = re.compile(
    r"(?im)^- Dimensions:\s*([0-9]+)\s*(?:px)?\s*x\s*([0-9]+)\s*(?:px)?\s*$"
)


class ImageGenerationAdapter:
    def __init__(
        self,
        *,
        providerUrl: str,
        apiKey: str | None,
        model: str | None,
        timeout_seconds: float = 900.0,
        retry_attempts: int = 4,
        retry_wait_seconds: float = 75.0,
    ) -> None:
        self._provider_url = normalize_provider_url(providerUrl)
        self._api_key = apiKey
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = max(1, retry_attempts)
        self._retry_wait_seconds = max(0.0, retry_wait_seconds)

    def generate(self, request: InferenceRequest) -> GeneratedArtifact:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        prompt, negative_prompt, size = parse_image_brief(request.prompt)
        payload: dict[str, Any] = {
            "model": request.model or self._model,
            "prompt": prompt,
            "size": size or "1024x1024",
            "n": 1,
            "output_format": request.output_format.value,
        }
        if not payload["model"]:
            raise ValueError("Image model is required for image generation")
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        with httpx.Client(timeout=self._timeout_seconds) as client:
            data = self._post_with_retries(
                client,
                f"{self._provider_url}/images/generations",
                headers=headers,
                payload=payload,
            )

        try:
            encoded = data["data"][0]["b64_json"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected image response shape: {data}") from exc
        if not isinstance(encoded, str) or not encoded.strip():
            raise RuntimeError(f"Image response did not include b64_json: {data}")
        record_usage(data, endpoint="images/generations", requested_model=str(payload["model"]))
        return GeneratedArtifact(binary=base64.b64decode(encoded))

    def _post_with_retries(
        self,
        client: httpx.Client,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code in {502, 503, 504}:
                    raise httpx.HTTPStatusError(
                        f"Transient upstream status: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.ReadTimeout, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if not is_retryable_http_error(exc) or attempt >= self._retry_attempts:
                    raise
                time.sleep(self._retry_wait_seconds)
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected retry state")


def record_usage(data: dict[str, Any], *, endpoint: str, requested_model: str) -> None:
    """Append provider-reported usage when a comparison run requests it."""
    destination = os.environ.get("BURN_USAGE_LOG")
    usage = data.get("usage")
    if not destination or not isinstance(usage, dict):
        return
    entry = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "model": data.get("model") or requested_model,
        "usage": usage,
    }
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    cap_value = os.environ.get("BURN_MAX_COST_USD")
    if not cap_value:
        return
    try:
        cap = float(cap_value)
    except ValueError as exc:
        raise ValueError("BURN_MAX_COST_USD must be numeric") from exc
    if cap <= 0:
        raise ValueError("BURN_MAX_COST_USD must be greater than zero")
    observed = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            observed += float(json.loads(line).get("usage", {}).get("cost", 0) or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    if observed > cap:
        raise RuntimeError(
            f"Provider-reported usage reached ${observed:.6f}, above BURN_MAX_COST_USD=${cap:.6f}; stopping further generation."
        )


def parse_image_brief(markdown: str) -> tuple[str, str | None, str | None]:
    sections: dict[str, str] = {}
    for match in IMAGE_SECTION_PATTERN.finditer(markdown):
        sections[match.group(1).strip().lower()] = match.group(2).strip()

    image_prompt = sections.get("image prompt")
    if not image_prompt:
        # A model may return a useful image brief without preserving the
        # requested markdown heading. Keep the run moving by passing the
        # complete non-empty brief through to the image provider rather than
        # discarding the model's work or failing the entire editorial run.
        fallback = markdown.strip()
        if not fallback:
            raise ValueError("Image brief is empty and has no '# Image Prompt' section")
        image_prompt = fallback

    prompt_parts = [image_prompt]
    required_copy = sections.get("required on-image copy")
    if required_copy:
        copy_lines = clean_markdown_bullets(required_copy)
        if not is_no_copy_instruction(copy_lines):
            prompt_parts.append("Render the following on-image copy exactly:")
            prompt_parts.extend(copy_lines)

    negative_prompt = sections.get("negative prompt")
    dimensions_match = IMAGE_DIMENSIONS_PATTERN.search(markdown)
    size = None
    if dimensions_match:
        size = f"{dimensions_match.group(1)}x{dimensions_match.group(2)}"

    return "\n\n".join(prompt_parts), negative_prompt.strip() if negative_prompt else None, size


def clean_markdown_bullets(block: str) -> list[str]:
    lines: list[str] = []
    for raw_line in block.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        lines.append(stripped[2:].strip() if stripped.startswith("- ") else stripped)
    return lines


def is_no_copy_instruction(lines: list[str]) -> bool:
    if not lines:
        return True
    normalized = " ".join(line.strip().lower() for line in lines)
    return "no on-image copy" in normalized or normalized.startswith("none")


def is_retryable_http_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ReadTimeout, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {502, 503, 504}:
        return True
    return False


def normalize_provider_url(provider_url: str) -> str:
    normalized = provider_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def load_pipeline_spec(path: Path) -> PipelineSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Pipeline YAML must contain a mapping at the root: {path}")
    return PipelineSpec.model_validate(data)


def load_model_registry(files: LocalFileStore, registry_path: Path) -> ModelRegistry:
    if files.exists(registry_path):
        data = json.loads(files.read_text(registry_path))
        return ModelRegistry.model_validate(data)

    registry = scan_model_registry(files)
    write_model_registry(files, registry_path, registry, force=True)
    return registry


def write_model_registry(
    files: LocalFileStore,
    registry_path: Path,
    registry: ModelRegistry,
    *,
    force: bool,
) -> None:
    payload = registry.model_dump()
    files.write_text(
        registry_path,
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        force=force,
    )


def scan_model_registry(files: LocalFileStore) -> ModelRegistry:
    entries: list[DevelopedModelEntry] = []
    for path in sorted(files.glob("content/letters/**/*.md")):
        if path.name.upper() not in {"CONTEXT.MD", "GPT.MD", "GPT_PROMPT.MD", "SB19-CONTEXT.MD"} and "context" not in path.name.lower():
            continue
        content = files.read_text(path)
        verb = extract_actionable_verb(content)
        if not verb:
            continue
        date_value, slug = split_letter_folder(path)
        title = extract_title(content)
        entries.append(
            DevelopedModelEntry(
                verb=verb,
                title=title,
                slug=slug,
                date=date_value,
                source_path=str(path),
            )
        )
    steadyburn_index = scan_steadyburn_verb_index(files)
    for item in steadyburn_index.entries:
        if not item.verb:
            continue
        entries.append(
            DevelopedModelEntry(
                verb=item.verb,
                title=item.title,
                slug=item.slug,
                date=item.date,
                source_path=item.evidence_path,
            )
        )
    return ModelRegistry(entries=dedupe_registry_entries(entries))


def dedupe_registry_entries(entries: list[DevelopedModelEntry]) -> list[DevelopedModelEntry]:
    by_verb: dict[str, DevelopedModelEntry] = {}
    for entry in sorted(entries, key=lambda item: (item.date, item.slug, item.source_path)):
        by_verb[entry.verb.upper()] = entry
    return list(by_verb.values())


def split_letter_folder(path: Path) -> tuple[str, str]:
    parent_name = path.parent.name
    if len(parent_name) >= 11 and parent_name[4] == "-" and parent_name[7] == "-":
        return parent_name[:10], parent_name[11:]
    return "", parent_name


def extract_title(content: str) -> str:
    lines = content.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        normalized = stripped.lstrip("#").strip().lower()
        if normalized == "title":
            for candidate in lines[index + 1 :]:
                candidate_stripped = candidate.strip()
                if candidate_stripped:
                    return candidate_stripped
        if stripped.startswith("# "):
            title_candidate = stripped[2:].strip()
            if title_candidate.lower() not in {"title", "content crusher response"}:
                return title_candidate
    return ""


STEADYBURN_SERIES_PATTERN = re.compile(r"(?m)^series:\s*$\n\s*-\s*SteadyBurn\s*$")
FRONTMATTER_TITLE_PATTERN = re.compile(r'(?m)^title:\s*"?(.*?)"?\s*$')
FRONTMATTER_SLUG_PATTERN = re.compile(r'(?m)^slug:\s*"?(.*?)"?\s*$')
INLINE_ACTIONABLE_VERB_PATTERN = re.compile(
    r"(?im)actionable\s+verb\s*:\s*\**\s*([A-Z][A-Z0-9-]{2,})\s*\**"
)
UPPERCASE_FILENAME_TOKEN_PATTERN = re.compile(r"^([A-Z][A-Z0-9]{3,})(?:[-_].*)?$")
SERIES_TOKEN_PATTERN = re.compile(r"^SB\d+$")
GENERIC_FILENAME_TOKENS = {
    "LESSON",
    "INSTRUCTIONS",
    "CONTEXT",
    "WORKSHEET",
    "MASKED",
    "COPY",
    "PROMO",
    "CREATIVE",
    "COVER",
    "INDEX",
    "GPT",
    "PROMPT",
}


def scan_steadyburn_verb_index(files: LocalFileStore) -> SteadyBurnVerbIndex:
    folders = []
    for folder in sorted(files.glob("content/letters/*")):
        index_path = folder / "index.md"
        if not files.exists(index_path):
            continue
        text = files.read_text(index_path)
        if not STEADYBURN_SERIES_PATTERN.search(text):
            continue
        folders.append((folder, text))

    entries: list[SteadyBurnVerbIndexEntry] = []
    for sequence, (folder, index_text) in enumerate(folders, start=1):
        title_match = FRONTMATTER_TITLE_PATTERN.search(index_text)
        slug_match = FRONTMATTER_SLUG_PATTERN.search(index_text)
        verb, status, evidence_path, note = detect_folder_verb(files, folder)
        entries.append(
            SteadyBurnVerbIndexEntry(
                sequence=sequence,
                date=folder.name[:10],
                folder=folder.name,
                title=title_match.group(1) if title_match else folder.name,
                slug=slug_match.group(1) if slug_match else folder.name[11:],
                verb=verb,
                status=status,
                evidence_path=evidence_path,
                note=note,
            )
        )
    return SteadyBurnVerbIndex(entries=entries)


def detect_folder_verb(
    files: LocalFileStore,
    folder: Path,
) -> tuple[str, VerbTrackingStatus, str, str]:
    markdown_files = sorted(path for path in files.glob(f"{folder.as_posix()}/*.md"))
    for path in markdown_files:
        content = files.read_text(path)
        verb = extract_actionable_verb(content)
        if verb:
            return verb, VerbTrackingStatus.CONFIRMED, str(path), "Actionable VERB heading"

    for path in markdown_files:
        content = files.read_text(path)
        match = INLINE_ACTIONABLE_VERB_PATTERN.search(content)
        if match:
            return (
                match.group(1).upper(),
                VerbTrackingStatus.INFERRED,
                str(path),
                "Inline Actionable VERB reference",
            )

    for path in sorted(files.glob(f"{folder.as_posix()}/*")):
        if not path.is_file():
            continue
        token = extract_filename_verb_token(path)
        if token:
            return token, VerbTrackingStatus.INFERRED, str(path), "Filename token"

    return "", VerbTrackingStatus.MISSING, "", "No verb evidence found"


def extract_filename_verb_token(path: Path) -> str | None:
    match = UPPERCASE_FILENAME_TOKEN_PATTERN.match(path.stem)
    if not match:
        return None
    token = match.group(1).upper()
    if token in GENERIC_FILENAME_TOKENS:
        return None
    if SERIES_TOKEN_PATTERN.match(token):
        return None
    return token


def render_steadyburn_verb_index_markdown(index: SteadyBurnVerbIndex) -> str:
    lines = [
        "# SteadyBurn Verb Index",
        "",
        f"Total indexed letters: {len(index.entries)}",
        "",
        "| # | Date | Title | Slug | Verb | Status | Evidence | Note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in index.entries:
        verb = entry.verb or "TBD"
        evidence = entry.evidence_path or "-"
        note = entry.note or "-"
        title = entry.title.replace("|", "\\|")
        slug = entry.slug.replace("|", "\\|")
        lines.append(
            f"| {entry.sequence} | {entry.date} | {title} | `{slug}` | `{verb}` | {entry.status.value} | `{evidence}` | {note} |"
        )
    return "\n".join(lines) + "\n"


def build_inference(config: ProviderConfig, cwd: Path, modality: GenerationModality = GenerationModality.TEXT):
    if config.kind.value == "codex-cli":
        if modality == GenerationModality.IMAGE:
            raise ValueError("codex-cli is not supported for binary image generation")
        return CodexCliAgent(command=config.command, model=config.model, cwd=cwd)

    if config.kind.value in {"openai", "openai-compatible", "openrouter"}:
        if config.kind == ProviderKind.OPENAI and not config.model:
            raise ValueError("--model or provider.model is required for openai")
        provider_url, api_key = resolve_provider_connection(config)
        if modality == GenerationModality.IMAGE:
            return ImageGenerationAdapter(
                providerUrl=provider_url,
                apiKey=api_key,
                model=config.model,
                timeout_seconds=config.timeout_seconds or 900.0,
                retry_attempts=config.retry_attempts,
                retry_wait_seconds=config.retry_wait_seconds,
            )
        return ChatCompletionsAdapter(
            providerUrl=provider_url,
            apiKey=api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds or 300.0,
            retry_attempts=config.retry_attempts,
            retry_wait_seconds=config.retry_wait_seconds,
        )

    raise ValueError(f"Unsupported provider: {config.kind}")


def resolve_provider_connection(config: ProviderConfig) -> tuple[str, str | None]:
    provider_url = config.provider_url or default_provider_url(config.kind)
    if not provider_url:
        raise ValueError(f"--provider-url or provider.providerUrl is required for {config.kind.value}")
    environment_variable = provider_api_key_environment(config.kind)
    api_key = os.environ.get(environment_variable) if environment_variable else None
    if config.kind in {ProviderKind.OPENAI, ProviderKind.OPENROUTER} and not api_key:
        raise ValueError(f"{environment_variable} is required for {config.kind.value}")
    return provider_url, api_key


def default_provider_url(kind: ProviderKind) -> str | None:
    if kind == ProviderKind.OPENAI:
        return "https://api.openai.com/v1"
    if kind == ProviderKind.OPENROUTER:
        return "https://openrouter.ai/api/v1"
    if kind == ProviderKind.OPENAI_COMPATIBLE:
        return "http://localhost:11434"
    return None


def provider_api_key_environment(kind: ProviderKind) -> str | None:
    if kind == ProviderKind.OPENROUTER:
        return "OPENROUTER_API_KEY"
    if kind == ProviderKind.OPENAI:
        return "OPENAI_API_KEY"
    return None
