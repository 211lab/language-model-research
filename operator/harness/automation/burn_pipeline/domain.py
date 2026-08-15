from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    SVG = "svg"
    HTML = "html"
    PNG = "png"
    JPEG = "jpeg"

    @property
    def is_text(self) -> bool:
        return self in {OutputFormat.MARKDOWN, OutputFormat.SVG, OutputFormat.HTML}

    @property
    def is_image(self) -> bool:
        return self in {OutputFormat.PNG, OutputFormat.JPEG}


class GenerationModality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class ProviderKind(str, Enum):
    CODEX_CLI = "codex-cli"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai-compatible"
    OPENROUTER = "openrouter"


class BurnContext(BaseModel):
    title: str = ""
    slug: str = ""
    date: str = ""
    target_dir: str = ""


class InputSource(BaseModel):
    path: Path | None = None
    step: str | None = None
    alias: str = ""
    optional: bool = False

    @model_validator(mode="after")
    def validate_source(self) -> "InputSource":
        if bool(self.path) == bool(self.step):
            raise ValueError("Exactly one of 'path' or 'step' must be set for each input")
        return self

    @property
    def resolved_alias(self) -> str:
        if self.alias:
            return self.alias
        if self.step:
            return self.step
        if self.path is None:
            raise ValueError("Input source has neither alias nor path")
        return self.path.stem or self.path.name


class StepSpec(BaseModel):
    id: str
    format: OutputFormat
    prompt_file: Path
    output: Path
    modality: GenerationModality = GenerationModality.TEXT
    model: str | None = None
    inputs: list[InputSource] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    tracks: list[str] = Field(default_factory=list)

    @field_validator("inputs", mode="before")
    @classmethod
    def normalize_inputs(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        normalized: list[Any] = []
        for item in value:
            if isinstance(item, (str, Path)):
                normalized.append({"path": item})
                continue
            normalized.append(item)
        return normalized


class PipelineSpec(BaseModel):
    context: BurnContext = Field(default_factory=BurnContext)
    variables: dict[str, Any] = Field(default_factory=dict)
    providers: dict[GenerationModality, "ProviderConfig"] = Field(default_factory=dict)
    tracks: dict[str, bool] = Field(default_factory=dict)
    steps: list[StepSpec]


class DevelopedModelEntry(BaseModel):
    verb: str
    title: str = ""
    slug: str = ""
    date: str = ""
    source_path: str = ""


class ModelRegistry(BaseModel):
    entries: list[DevelopedModelEntry] = Field(default_factory=list)

    def used_verbs(self) -> list[str]:
        unique = {entry.verb.upper(): entry.verb.upper() for entry in self.entries if entry.verb.strip()}
        return sorted(unique.values())


class VerbTrackingStatus(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    MISSING = "missing"


class SteadyBurnVerbIndexEntry(BaseModel):
    sequence: int
    date: str
    folder: str
    title: str
    slug: str
    verb: str = ""
    status: VerbTrackingStatus = VerbTrackingStatus.MISSING
    evidence_path: str = ""
    note: str = ""


class SteadyBurnVerbIndex(BaseModel):
    entries: list[SteadyBurnVerbIndexEntry] = Field(default_factory=list)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    kind: ProviderKind = ProviderKind.OPENAI_COMPATIBLE
    model: str | None = None
    provider_url: str | None = Field(default=None, alias="providerUrl")
    command: str = "codex"
    timeout_seconds: float | None = None
    retry_attempts: int = 4
    retry_wait_seconds: float = 75.0

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_provider_url(cls, value: Any) -> Any:
        if isinstance(value, dict) and "providerUrl" not in value and "provider_url" not in value and "base_url" in value:
            return {**value, "providerUrl": value["base_url"]}
        return value


class GenerateCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step: StepSpec
    context: BurnContext
    prompt_template: str
    named_inputs: dict[str, str] = Field(default_factory=dict)


class InferenceRequest(BaseModel):
    prompt: str
    output_format: OutputFormat
    model: str | None = None


class GeneratedArtifact(BaseModel):
    text: str | None = None
    binary: bytes | None = None


class InferencePort(Protocol):
    def generate(self, request: InferenceRequest) -> GeneratedArtifact:
        """Return a generated text or binary artifact."""


class FileStorePort(Protocol):
    def read_text(self, path: Path) -> str:
        """Read UTF-8 text from a path."""

    def write_text(self, path: Path, content: str, force: bool) -> None:
        """Write UTF-8 text to a path."""

    def write_bytes(self, path: Path, content: bytes, force: bool) -> None:
        """Write bytes to a path."""

    def exists(self, path: Path) -> bool:
        """Return whether a path exists."""

    def glob(self, pattern: str) -> list[Path]:
        """Return paths matching a workspace-relative glob pattern."""


TEMPLATE_PATTERN = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")
ACTIONABLE_VERB_HEADER_PATTERN = re.compile(
    r"^\s*(?:#{1,6}\s*)?Actionable\s+VERB\s*$",
    re.IGNORECASE | re.MULTILINE,
)
ATX_HEADER_PATTERN = re.compile(r"^\s*#{1,6}\s+")
EMPHASIS_ONLY_PATTERN = re.compile(r"^\*{1,2}(.*?)\*{1,2}$")


def render_prompt_template(template: str, data: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = resolve_template_value(data, key)
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, ensure_ascii=True)
        return str(value)

    return TEMPLATE_PATTERN.sub(replace, template)


def resolve_template_value(data: dict[str, Any], key: str) -> Any:
    current: Any = data
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise ValueError(f"Missing template value: {key}")
    return current


def build_generation_prompt(command: GenerateCommand) -> str:
    if command.step.modality == GenerationModality.IMAGE and command.step.format.is_image:
        return command.prompt_template.strip()

    lines = [
        "You are generating one file for the 3F Mindset SteadyBurn content pipeline.",
        "",
        "Return only the requested file contents.",
        "Do not include reasoning, explanation, status text, Markdown fences, XML fences, or surrounding commentary.",
        "Do not edit files or run commands. Produce final text only.",
        "",
        f"Output format: {command.step.format.value}",
        f"Title: {command.context.title}",
        f"Slug: {command.context.slug}",
        f"Date: {command.context.date}",
        "",
    ]

    if command.step.format == OutputFormat.SVG:
        lines.extend(
            [
                "SVG constraints:",
                "- Return a complete SVG XML document starting with <svg.",
                "- Do not wrap the SVG in a Markdown code block.",
                "- Do not include prose before or after the XML.",
                "",
            ]
        )
    elif command.step.format == OutputFormat.HTML:
        lines.extend(
            [
                "HTML constraints:",
                "- Return a complete HTML document.",
                "- Start with <!doctype html> or <html.",
                "- Do not wrap the HTML in a Markdown code block.",
                "- Do not include prose before or after the HTML.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Markdown constraints:",
                "- Return Markdown only.",
                "- Do not wrap the Markdown in a code block.",
                "- Do not include prose about the task.",
                "",
            ]
        )

    lines.extend(
        [
            "Prompt instructions:",
            "--- BEGIN PROMPT INSTRUCTIONS ---",
            command.prompt_template,
            "--- END PROMPT INSTRUCTIONS ---",
            "",
        ]
    )

    for name, content in command.named_inputs.items():
        lines.extend(
            [
                f"Input: {name}",
                "--- BEGIN INPUT ---",
                content,
                "--- END INPUT ---",
                "",
            ]
        )

    return "\n".join(lines)


def validate_generated_content(content: str, output_format: OutputFormat) -> None:
    if not output_format.is_text:
        return
    if not content.strip():
        raise ValueError("Generated output is empty")

    if content.lstrip().startswith("```"):
        raise ValueError("Generated output starts with a Markdown fence")

    if output_format == OutputFormat.SVG:
        stripped = content.lstrip().lower()
        if not (stripped.startswith("<svg") or stripped.startswith("<?xml")):
            raise ValueError("Generated SVG does not start with <svg or <?xml")

    if output_format == OutputFormat.HTML:
        stripped = content.lstrip().lower()
        if not (stripped.startswith("<!doctype html") or stripped.startswith("<html")):
            raise ValueError("Generated HTML does not start with <!doctype html> or <html")


def sanitize_generated_content(content: str, output_format: OutputFormat) -> str:
    if not output_format.is_text:
        return content
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            end = -1 if lines[-1].strip() == "```" else None
            cleaned = "\n".join(lines[1:end]).strip()

    if output_format == OutputFormat.SVG:
        lowered = cleaned.lower()
        xml_index = lowered.find("<?xml")
        svg_index = lowered.find("<svg")
        start_indexes = [index for index in (xml_index, svg_index) if index >= 0]
        if start_indexes:
            cleaned = cleaned[min(start_indexes) :].strip()

    if output_format == OutputFormat.HTML:
        lowered = cleaned.lower()
        doctype_index = lowered.find("<!doctype html")
        html_index = lowered.find("<html")
        start_indexes = [index for index in (doctype_index, html_index) if index >= 0]
        if start_indexes:
            cleaned = cleaned[min(start_indexes) :].strip()

    return cleaned


def extract_actionable_verb(content: str) -> str | None:
    match = ACTIONABLE_VERB_HEADER_PATTERN.search(content)
    if not match:
        return None

    remainder = content[match.end() :].splitlines()
    for line in remainder:
        candidate = normalize_actionable_verb_line(line)
        if candidate:
            return candidate
        if line.strip():
            return None
    return None


def normalize_actionable_verb_line(line: str) -> str | None:
    value = line.strip()
    if not value:
        return None
    value = ATX_HEADER_PATTERN.sub("", value).strip()
    emphasis_match = EMPHASIS_ONLY_PATTERN.match(value)
    if emphasis_match:
        value = emphasis_match.group(1).strip()
    value = value.strip("`").strip()
    value = re.sub(r"\s+", " ", value)
    if not value:
        return None
    return value.upper()
