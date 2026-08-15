from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .domain import (
    BurnContext,
    DevelopedModelEntry,
    FileStorePort,
    GenerateCommand,
    GenerationModality,
    InferencePort,
    InferenceRequest,
    InputSource,
    ModelRegistry,
    PipelineSpec,
    ProviderConfig,
    StepSpec,
    build_generation_prompt,
    extract_actionable_verb,
    render_prompt_template,
    sanitize_generated_content,
    validate_generated_content,
)


class BurnPipeline:
    def __init__(
        self,
        files: FileStorePort,
        inference_factory,
        *,
        registry: ModelRegistry | None = None,
        registry_path: Path | None = None,
        providers: dict[GenerationModality, ProviderConfig] | None = None,
    ) -> None:
        self._files = files
        self._inference_factory = inference_factory
        self._providers = providers or {}
        self._inference_cache: dict[GenerationModality, InferencePort] = {}
        self._registry = registry or ModelRegistry()
        self._registry_path = registry_path

    def generate_step(
        self,
        step: StepSpec,
        context: BurnContext,
        force: bool,
        *,
        variables: dict[str, Any] | None = None,
        state: dict[str, dict[str, str]] | None = None,
        steps_by_id: dict[str, StepSpec] | None = None,
    ) -> str:
        rendered_prompt = self.render_step_prompt(
            step=step,
            context=context,
            variables=variables or {},
            state=state or {},
            steps_by_id=steps_by_id or {},
        )
        named_inputs = self._load_inputs(step, state=state or {}, steps_by_id=steps_by_id or {})
        output_path = self._resolve_output_path(step=step, steps_by_id=steps_by_id or {})
        prompt = build_generation_prompt(
            GenerateCommand(
                step=step.model_copy(update={"output": output_path}),
                context=context,
                prompt_template=rendered_prompt,
                named_inputs=named_inputs,
            )
        )
        artifact = self._inference_for_step(step).generate(
            InferenceRequest(
                prompt=prompt,
                output_format=step.format,
                model=self._model_for_step(step),
            )
        )
        if step.format.is_text:
            content = sanitize_generated_content(artifact.text or "", step.format)
            validate_generated_content(content, step.format)
            self._files.write_text(output_path, content, force=force)
            self._update_registry_for_step(step=step, context=context, output_path=output_path, content=content)
            return content

        binary = artifact.binary or b""
        if not binary:
            raise ValueError(f"Generated binary output is empty for step: {step.id}")
        self._files.write_bytes(output_path, binary, force=force)
        return ""

    def run_pipeline(self, spec: PipelineSpec, force: bool) -> None:
        steps = [
            step for step in spec.steps
            if all(spec.tracks.get(track, True) for track in step.tracks)
        ]
        steps_by_id = {step.id: step for step in steps}
        step_order = {step.id: index for index, step in enumerate(steps)}
        disabled_dependencies = {
            step.id: dependency
            for step in steps
            for dependency in step.depends_on
            if dependency not in steps_by_id
        }
        if disabled_dependencies:
            details = ", ".join(
                f"{step_id} -> {dependency}"
                for step_id, dependency in sorted(disabled_dependencies.items())
            )
            raise ValueError(f"Enabled step depends on a disabled step: {details}")
        state: dict[str, dict[str, str]] = {}
        pending = list(steps)
        current_provider_key: tuple[str, ...] | None = None

        while pending:
            ready = [step for step in pending if all(step_id in state for step_id in step.depends_on)]
            if not ready:
                unresolved = ", ".join(step.id for step in pending)
                raise ValueError(f"No runnable steps remain. Pending: {unresolved}")

            unknown_dependencies: list[str] = []
            for step in ready:
                unknown_dependencies.extend(step_id for step_id in step.depends_on if step_id not in steps_by_id)
            if unknown_dependencies:
                raise ValueError(f"Unknown dependency step(s): {', '.join(sorted(set(unknown_dependencies)))}")

            step = self._choose_next_step(ready, current_provider_key=current_provider_key, step_order=step_order)
            pending.remove(step)
            missing = [step_id for step_id in step.depends_on if step_id not in state]
            unknown = [step_id for step_id in step.depends_on if step_id not in steps_by_id]
            if unknown:
                raise ValueError(f"Step {step.id} depends on unknown step(s): {', '.join(unknown)}")
            if missing:
                raise ValueError(
                    f"Step {step.id} ran before dependency step(s): {', '.join(missing)}"
                )

            output_path = self._resolve_output_path(step=step, steps_by_id=steps_by_id)
            content = self.generate_step(
                step=step,
                context=spec.context,
                force=force,
                variables=spec.variables,
                state=state,
                steps_by_id=steps_by_id,
            )
            state[step.id] = {"content": content, "path": str(output_path)}
            current_provider_key = self._provider_key_for_step(step)

    def _choose_next_step(
        self,
        ready: list[StepSpec],
        *,
        current_provider_key: tuple[str, ...] | None,
        step_order: dict[str, int],
    ) -> StepSpec:
        if current_provider_key is not None:
            same_provider = [step for step in ready if self._provider_key_for_step(step) == current_provider_key]
            if same_provider:
                return min(same_provider, key=lambda step: step_order[step.id])

        grouped: dict[tuple[str, ...], list[StepSpec]] = defaultdict(list)
        for step in ready:
            grouped[self._provider_key_for_step(step)].append(step)

        best_key = min(
            grouped,
            key=lambda key: (-len(grouped[key]), min(step_order[step.id] for step in grouped[key])),
        )
        return min(grouped[best_key], key=lambda step: step_order[step.id])

    def render_step_prompt(
        self,
        *,
        step: StepSpec,
        context: BurnContext,
        variables: dict[str, Any],
        state: dict[str, dict[str, str]],
        steps_by_id: dict[str, StepSpec],
    ) -> str:
        prompt_template = self._files.read_text(step.prompt_file)
        named_inputs = self._load_inputs(step, state=state, steps_by_id=steps_by_id)
        render_data = {
            "context": context.model_dump(),
            "variables": variables,
            "registry": self._build_registry_render_data(),
            "step": {
                step_id: {
                    "output": details["content"],
                    "path": details["path"],
                }
                for step_id, details in state.items()
            },
            "inputs": named_inputs,
            "current_step": {
                "id": step.id,
                "format": step.format.value,
                "output_path": str(self._resolve_output_path(step=step, steps_by_id=steps_by_id)),
            },
        }
        return render_prompt_template(prompt_template, render_data)

    def _build_registry_render_data(self) -> dict[str, Any]:
        verbs = self._registry.used_verbs()
        entries = [
            {
                "verb": entry.verb,
                "title": entry.title,
                "slug": entry.slug,
                "date": entry.date,
                "source_path": entry.source_path,
            }
            for entry in sorted(self._registry.entries, key=lambda item: (item.date, item.verb))
        ]
        lines = [
            f"- {entry['verb']} ({entry['date'] or 'unknown date'} / {entry['slug'] or 'unknown slug'})"
            for entry in entries
        ]
        return {
            "used_verbs": verbs,
            "used_verbs_csv": ", ".join(verbs),
            "used_verbs_count": len(verbs),
            "entries": entries,
            "entries_markdown": "\n".join(lines) if lines else "- none recorded",
        }

    def _load_inputs(
        self,
        step: StepSpec,
        *,
        state: dict[str, dict[str, str]],
        steps_by_id: dict[str, StepSpec],
    ) -> dict[str, str]:
        named_inputs: dict[str, str] = {}
        for input_source in step.inputs:
            content = self._load_input_source(
                input_source,
                state=state,
                steps_by_id=steps_by_id,
            )
            if content is None:
                continue
            named_inputs[input_source.resolved_alias] = content
        return named_inputs

    def _load_input_source(
        self,
        input_source: InputSource,
        *,
        state: dict[str, dict[str, str]],
        steps_by_id: dict[str, StepSpec],
    ) -> str | None:
        if input_source.step:
            if input_source.step in state:
                return state[input_source.step]["content"]
            referenced_step = steps_by_id.get(input_source.step)
            if referenced_step is None:
                if input_source.optional:
                    return None
                raise ValueError(f"Unknown step input reference: {input_source.step}")
            output_path = self._resolve_output_path(step=referenced_step, steps_by_id=steps_by_id)
            if not self._files.exists(output_path):
                if input_source.optional:
                    return None
                raise FileNotFoundError(f"Missing step output for input: {output_path}")
            return self._files.read_text(output_path)

        if input_source.path is None:
            if input_source.optional:
                return None
            raise ValueError("Input source did not include a path")
        if not self._files.exists(input_source.path):
            if input_source.optional:
                return None
            raise FileNotFoundError(f"Missing input file: {input_source.path}")
        return self._files.read_text(input_source.path)

    def _resolve_output_path(self, *, step: StepSpec, steps_by_id: dict[str, StepSpec]) -> Path:
        return step.output

    def _update_registry_for_step(
        self,
        *,
        step: StepSpec,
        context: BurnContext,
        output_path: Path,
        content: str,
    ) -> None:
        if step.id != "context":
            return
        verb = extract_actionable_verb(content)
        if not verb:
            return

        preserved_entries = [
            entry for entry in self._registry.entries if entry.slug != context.slug and entry.verb.upper() != verb
        ]
        preserved_entries.append(
            DevelopedModelEntry(
                verb=verb,
                title=context.title,
                slug=context.slug,
                date=context.date,
                source_path=str(output_path),
            )
        )
        self._registry = ModelRegistry(entries=preserved_entries)
        if self._registry_path is None:
            return
        self._files.write_text(
            self._registry_path,
            self._serialize_registry(),
            force=True,
        )

    def _inference_for_step(self, step: StepSpec) -> InferencePort:
        modality = step.modality
        if modality in self._inference_cache:
            return self._inference_cache[modality]
        provider = self._providers.get(modality)
        if provider is None:
            raise ValueError(f"No provider configured for step modality: {modality.value}")
        inference = self._inference_factory(provider, step.modality)
        self._inference_cache[modality] = inference
        return inference

    def _model_for_step(self, step: StepSpec) -> str | None:
        provider = self._providers.get(step.modality)
        if provider is None:
            return step.model
        return step.model or provider.model

    def _provider_key_for_step(self, step: StepSpec) -> tuple[str, ...]:
        provider = self._providers.get(step.modality)
        if provider is None:
            return (step.modality.value, "missing")
        return (
            step.modality.value,
            provider.kind.value,
            provider.provider_url or "",
            self._model_for_step(step) or "",
            provider.command or "",
        )

    def _serialize_registry(self) -> str:
        import json

        return json.dumps(self._registry.model_dump(), indent=2, ensure_ascii=True) + "\n"


def step_from_paths(
    *,
    step_id: str,
    output_format: str,
    modality: GenerationModality = GenerationModality.TEXT,
    prompt_file: Path,
    output: Path,
    inputs: list[Path],
) -> StepSpec:
    return StepSpec(
        id=step_id,
        format=output_format,
        modality=modality,
        prompt_file=prompt_file,
        output=output,
        inputs=inputs,
    )
