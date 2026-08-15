from __future__ import annotations

import json
import os
import statistics
import uuid
from pathlib import Path
from typing import Any, Protocol

from .domain import ARTIFACTS, ArtifactRubric, ArtifactScore, CaseStudy, Criterion, CriterionResult, Rubric, deterministic_metrics, score_artifact
from .infrastructure import ModelResponse, Telemetry


EVIDENCE_MODEL = os.environ.get("CONTENT_SCORING_EVIDENCE_MODEL", "deepseek/deepseek-v4-flash")
JUDGE_MODEL = os.environ.get("CONTENT_SCORING_JUDGE_MODEL", "deepseek/deepseek-v4-pro")
TIE_BREAK_MODEL = os.environ.get("CONTENT_SCORING_TIE_BREAK_MODEL", JUDGE_MODEL)
SCHEMA_VERSION = "content-score-v4"


class EvaluatorPort(Protocol):
    def complete(self, *, model: str, prompt: str, schema: dict[str, Any], run_id: str, stage: str, case_study: str, artifact: str) -> ModelResponse:
        ...


def load_rubric(path: Path) -> Rubric:
    data = json.loads(path.read_text(encoding="utf-8"))
    artifacts = {}
    for artifact, raw in data["artifacts"].items():
        artifacts[artifact] = ArtifactRubric(
            artifact=artifact,
            categories=raw["categories"],
            criteria=tuple(Criterion(**item) for item in raw["criteria"]),
        )
    return Rubric(version=data["version"], artifacts=artifacts)


def discover_case_studies(root: Path, requested: list[Path] | None = None) -> list[CaseStudy]:
    candidates = requested or [path.parent for path in root.rglob("MODEL_COMPARISON.md")]
    studies = []
    for path in sorted(set(candidate.resolve() for candidate in candidates)):
        if not all((path / artifact).exists() for artifact in ARTIFACTS):
            continue
        model = path.parent.name
        comparison = path / "MODEL_COMPARISON.md"
        if comparison.exists():
            for line in comparison.read_text(encoding="utf-8").splitlines():
                if line.lower().startswith("- model:") or line.lower().startswith("- text model:"):
                    model = line.split(":", 1)[1].strip().strip(chr(96))
                    break
        studies.append(CaseStudy(path, model, {name: (path / name).read_text(encoding="utf-8") for name in ARTIFACTS}))
    return studies


def evidence_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": {"evidence": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"criterion_id": {"type": "string"}, "quotes": {"type": "array", "items": {"type": "string"}}}, "required": ["criterion_id", "quotes"]}}}, "required": ["evidence"]}


def score_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": {"criteria": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"id": {"type": "string"}, "score": {"type": "number"}, "passed": {"type": "boolean"}, "confidence": {"type": "number"}, "evidence": {"type": "array", "items": {"type": "string"}}, "reason": {"type": "string"}}, "required": ["id", "score", "passed", "confidence", "evidence", "reason"]}}}, "required": ["criteria"]}


def evidence_prompt(artifact: str, text: str, criteria: tuple[Criterion, ...]) -> str:
    names = "\n".join(f"- {item.id}: {item.label}" for item in criteria)
    return f"Extract short verbatim evidence candidates. Do not score. Evidence may be absent.\nArtifact: {artifact}\nCriteria:\n{names}\nSource:\n---BEGIN SOURCE---\n{text}\n---END SOURCE---"


def judge_prompt(artifact: str, text: str, rubric: ArtifactRubric, metrics: dict[str, Any], evidence: dict[str, Any], criteria: tuple[Criterion, ...] | None = None) -> str:
    selected = criteria or rubric.criteria
    names = "\n".join(f"- {item.id} ({'required' if item.required else 'preferred'}): {item.label}" for item in selected)
    return f"""You are an exacting 3F Mindset editorial auditor. Score requested criteria 0 to 100. A passed required criterion must be materially present, not merely named. Cite short exact excerpts from source only. Reject hype, therapy voice, preaching, guru language, empty motivation, and shallow repetition. Low reading level must preserve serious thought.
Artifact: {artifact}
Criteria:
{names}
Deterministic metrics: {json.dumps(metrics, ensure_ascii=True)}
Untrusted evidence candidates: {json.dumps(evidence, ensure_ascii=True)}
Source:
---BEGIN SOURCE---
{text}
---END SOURCE---"""


def parse_results(payload: dict[str, Any], criteria: tuple[Criterion, ...], source_text: str) -> dict[str, CriterionResult]:
    raw = payload.get("criteria") if isinstance(payload.get("criteria"), list) else []
    data = {str(item.get("id")): item for item in raw if isinstance(item, dict)}
    results = {}
    for criterion in criteria:
        item = data.get(criterion.id, {})
        evidence = tuple(str(value) for value in item.get("evidence", []) if isinstance(value, str))
        normalized_source = " ".join(source_text.lower().split())
        verified = tuple(value for value in evidence if " ".join(value.lower().split()) in normalized_source)
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0) or 0)))
        reason = str(item.get("reason", "Missing evaluator result"))
        if evidence and not verified:
            confidence *= 0.7
            reason = f"{reason} (evidence could not be verified)"
        results[criterion.id] = CriterionResult(
            id=criterion.id,
            score=max(0.0, min(100.0, float(item.get("score", 0) or 0))),
            passed=bool(item.get("passed", False)),
            confidence=confidence,
            evidence=verified,
            reason=reason,
        )
    return results


class BudgetExceeded(RuntimeError):
    pass


class ContentScorer:
    def __init__(self, root: Path, rubric: Rubric, evaluator: EvaluatorPort | None, telemetry: Telemetry, max_cost: float, resume: bool, force: bool) -> None:
        self.root, self.rubric, self.evaluator, self.telemetry = root, rubric, evaluator, telemetry
        self.max_cost, self.resume, self.force = max_cost, resume, force
        self.spent, self.run_id, self.cache = 0.0, uuid.uuid4().hex, root / ".content-score-cache"

    def _call(self, **kwargs: Any) -> ModelResponse:
        if self.evaluator is None:
            raise RuntimeError("Live evaluator unavailable in dry-run mode")
        if self.spent >= self.max_cost:
            raise BudgetExceeded("Observed evaluator cost reached configured cap")
        response = self.evaluator.complete(run_id=self.run_id, **kwargs)
        self.spent += response.cost
        return response

    def score_artifact(self, study: CaseStudy, artifact: str) -> ArtifactScore:
        rubric = self.rubric.artifacts[artifact]
        metrics = deterministic_metrics(study.texts[artifact])
        cache_name = f"{study.source_hash()}-{artifact}-{self.rubric.version}-{SCHEMA_VERSION}-{EVIDENCE_MODEL}-{JUDGE_MODEL}-{TIE_BREAK_MODEL}".replace("/", "_")
        cache_path = self.cache / f"{cache_name}.json"
        if self.resume and not self.force and cache_path.exists():
            self.telemetry.emit("cache_hit", run_id=self.run_id, case_study=study.identifier, artifact=artifact)
            return artifact_score_from_dict(json.loads(cache_path.read_text(encoding="utf-8")))
        if self.evaluator is None:
            return score_artifact(rubric, metrics, [CriterionResult(item.id, 0, False, 0, (), "Dry run") for item in rubric.criteria])
        evidence = self._call(model=EVIDENCE_MODEL, prompt=evidence_prompt(artifact, study.texts[artifact], rubric.criteria), schema=evidence_schema(), stage="evidence", case_study=study.identifier, artifact=artifact).payload
        passes = []
        for sequence in range(3):
            reply = self._call(model=JUDGE_MODEL, prompt=judge_prompt(artifact, study.texts[artifact], rubric, metrics.as_dict(), evidence), schema=score_schema(), stage=f"judge_{sequence + 1}", case_study=study.identifier, artifact=artifact)
            passes.append(parse_results(reply.payload, rubric.criteria, study.texts[artifact]))
        merged: dict[str, CriterionResult] = {}
        disputed: list[Criterion] = []
        for criterion in rubric.criteria:
            samples = [passed[criterion.id] for passed in passes]
            values = [sample.score for sample in samples]
            middle = sorted(samples, key=lambda item: item.score)[1]
            merged[criterion.id] = middle
            if middle.confidence < 0.75 or max(values) - min(values) >= 12 or (criterion.required and 55 <= middle.score <= 69):
                disputed.append(criterion)
        if disputed:
            try:
                reply = self._call(model=TIE_BREAK_MODEL, prompt=judge_prompt(artifact, study.texts[artifact], rubric, metrics.as_dict(), evidence, tuple(disputed)), schema=score_schema(), stage="tie_break", case_study=study.identifier, artifact=artifact)
                merged.update(parse_results(reply.payload, tuple(disputed), study.texts[artifact]))
            except RuntimeError as exc:
                self.telemetry.emit(
                    "tie_break_fallback",
                    run_id=self.run_id,
                    case_study=study.identifier,
                    artifact=artifact,
                    model=TIE_BREAK_MODEL,
                    reason=type(exc).__name__,
                )
        result = score_artifact(rubric, metrics, [merged[item.id] for item in rubric.criteria])
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
        self.telemetry.emit("artifact_scored", run_id=self.run_id, case_study=study.identifier, artifact=artifact, score=result.final_score, cost=round(self.spent, 6))
        return result

    def score_study(self, study: CaseStudy) -> dict[str, Any]:
        artifacts = {artifact: self.score_artifact(study, artifact) for artifact in ARTIFACTS}
        payload = {
            "schema_version": SCHEMA_VERSION, "rubric_version": self.rubric.version,
            "model": study.model, "case_study": study.identifier,
            "content_score": round(sum(item.final_score for item in artifacts.values()) / 2, 2),
            "confidence": round(sum(item.confidence for item in artifacts.values()) / 2, 3),
            "artifacts": {name: item.as_dict() for name, item in artifacts.items()},
            "evaluator": {"evidence_model": EVIDENCE_MODEL, "judge_model": JUDGE_MODEL, "tie_break_model": TIE_BREAK_MODEL},
            "evaluator_cost": round(self.spent, 6),
        }
        write_study_report(study.root, payload)
        return payload


def artifact_score_from_dict(data: dict[str, Any]) -> ArtifactScore:
    metric = deterministic_metrics("")
    metrics = type(metric)(**data["metrics"])
    criteria = tuple(CriterionResult(**item) for item in data["criteria"])
    return ArtifactScore(data["artifact"], data["base_score"], data["penalties"], data["final_score"], data["confidence"], metrics, criteria)


def write_study_report(root: Path, payload: dict[str, Any]) -> None:
    (root / "CONTENT_SCORE.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [f"# Content Score: {payload['content_score']:.2f}", "", f"- Model: {payload['model']}", f"- Confidence: {payload['confidence']:.3f}", ""]
    for name, artifact in payload["artifacts"].items():
        lines.extend([f"## {name}", "", f"- Score: {artifact['final_score']:.2f}", f"- Base: {artifact['base_score']:.2f}", f"- Penalties: {artifact['penalties']:.2f}", f"- FK Grade: {artifact['metrics']['fk_grade']} (measurement; reference target <= 6)", ""])
    (root / "CONTENT_SCORE.md").write_text("\n".join(lines), encoding="utf-8")


def write_aggregate(root: Path, reports: list[dict[str, Any]], run_id: str, spent: float) -> None:
    ordered = sorted(reports, key=lambda item: item["content_score"], reverse=True)
    (root / "content-score-report.json").write_text(json.dumps({"run_id": run_id, "evaluator_cost": round(spent, 6), "reports": ordered}, indent=2) + "\n", encoding="utf-8")
    lines = ["# Content Score Report", "", "| Model | Score | Confidence |", "| --- | ---: | ---: |"]
    lines.extend(f"| {item['model']} | {item['content_score']:.2f} | {item['confidence']:.3f} |" for item in ordered)
    (root / "content-score-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
