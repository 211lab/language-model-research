from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ARTIFACTS = ("index.md", "INSTRUCTIONS.md")
VOWELS = re.compile(r"[aeiouy]+", re.IGNORECASE)
WORDS = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])(?:[”’\"')\]]*)\s+")


@dataclass(frozen=True)
class Criterion:
    id: str
    label: str
    category: str
    required: bool
    penalty_group: str = ""


@dataclass(frozen=True)
class ArtifactRubric:
    artifact: str
    categories: dict[str, float]
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True)
class Rubric:
    version: str
    artifacts: dict[str, ArtifactRubric]


@dataclass(frozen=True)
class DeterministicMetrics:
    fk_grade: float
    words: int
    sentences: int
    average_sentence_words: float
    sentence_length_stddev: float
    concrete_opening: bool
    action_signals: int
    framework_signals: int
    late_you_ratio: float
    repeated_sentence_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CriterionResult:
    id: str
    score: float
    passed: bool
    confidence: float
    evidence: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ArtifactScore:
    artifact: str
    base_score: float
    penalties: float
    final_score: float
    confidence: float
    metrics: DeterministicMetrics
    criteria: tuple[CriterionResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact,
            "base_score": self.base_score,
            "penalties": self.penalties,
            "final_score": self.final_score,
            "confidence": self.confidence,
            "metrics": self.metrics.as_dict(),
            "criteria": [asdict(item) for item in self.criteria],
        }


@dataclass(frozen=True)
class CaseStudy:
    root: Path
    model: str
    texts: dict[str, str]

    @property
    def identifier(self) -> str:
        return self.root.as_posix()

    def source_hash(self) -> str:
        digest = hashlib.sha256()
        for artifact in ARTIFACTS:
            digest.update(artifact.encode())
            digest.update(self.texts[artifact].encode("utf-8"))
        return digest.hexdigest()


def syllables(word: str) -> int:
    normalized = re.sub(r"[^a-z]", "", word.lower())
    groups = len(VOWELS.findall(normalized))
    if normalized.endswith("e") and not normalized.endswith(("le", "ye")) and groups > 1:
        groups -= 1
    if normalized.endswith("le") and len(normalized) > 2 and normalized[-3] not in "aeiouy":
        groups += 1
    return max(1, groups)


def normalize_markdown(text: str) -> str:
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    text = re.sub(re.escape(chr(96) * 3) + r".*?" + re.escape(chr(96) * 3), " ", text, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"[*_>#]", "", text).strip()


def deterministic_metrics(markdown: str) -> DeterministicMetrics:
    text = normalize_markdown(markdown)
    words = WORDS.findall(text)
    sentences = [item.strip() for item in SENTENCE_BREAK.split(text) if WORDS.search(item)]
    if not sentences and words:
        sentences = [text]
    lengths = [len(WORDS.findall(sentence)) for sentence in sentences] or [0]
    word_count = len(words)
    sentence_count = max(1, len(sentences))
    syllable_count = sum(syllables(word) for word in words)
    average_words = word_count / sentence_count
    average_syllables = syllable_count / word_count if word_count else 0
    fk = 0.39 * average_words + 11.8 * average_syllables - 15.59
    variance = sum((length - average_words) ** 2 for length in lengths) / len(lengths)
    opening = " ".join(text.splitlines()[:4]).lower()
    concrete = any(token in opening for token in (
        "boots", "truck", "mug", "workbench", "porch", "grocery", "garage", "phone",
        "alarm", "gym", "kitchen", "desk", "bed", "email", "calendar", "door",
    ))
    lowered = text.lower()
    action_signals = sum(lowered.count(token) for token in (" today", " this week", " do ", " choose ", " start ", " stop "))
    framework_signals = sum(lowered.count(token) for token in ("framework", "model", "matrix", "system", "method", "principle"))
    halves = [lowered[: len(lowered) // 2], lowered[len(lowered) // 2 :]]
    early_you = len(re.findall(r"\byou\b", halves[0]))
    late_you = len(re.findall(r"\byou\b", halves[1]))
    late_ratio = late_you / max(1, early_you + late_you)
    normalized_sentences = [re.sub(r"\W+", " ", sentence.lower()).strip() for sentence in sentences if len(WORDS.findall(sentence)) >= 6]
    duplicates = len(normalized_sentences) - len(set(normalized_sentences))
    return DeterministicMetrics(
        fk_grade=round(fk, 2),
        words=word_count,
        sentences=len(sentences),
        average_sentence_words=round(average_words, 2),
        sentence_length_stddev=round(math.sqrt(variance), 2),
        concrete_opening=concrete,
        action_signals=action_signals,
        framework_signals=framework_signals,
        late_you_ratio=round(late_ratio, 2),
        repeated_sentence_ratio=round(duplicates / max(1, len(normalized_sentences)), 3),
    )


def score_artifact(rubric: ArtifactRubric, metrics: DeterministicMetrics, results: list[CriterionResult]) -> ArtifactScore:
    by_id = {result.id: result for result in results}
    category_scores: dict[str, list[float]] = {name: [] for name in rubric.categories}
    penalties = 0.0
    penalized_groups: set[str] = set()
    for criterion in rubric.criteria:
        result = by_id.get(criterion.id)
        if not result:
            result = CriterionResult(criterion.id, 0.0, False, 0.0, (), "Missing evaluator result")
        category_scores[criterion.category].append(result.score)
        if not result.passed:
            group = criterion.penalty_group or criterion.id
            if group not in penalized_groups:
                penalties += 15.0 if criterion.required else 6.0
                penalized_groups.add(group)
    base = sum(
        rubric.categories[name] * (sum(scores) / max(1, len(scores))) / 100
        for name, scores in category_scores.items()
    )
    final = max(0.0, min(100.0, base - penalties))
    confidence = sum(result.confidence for result in results) / max(1, len(results))
    return ArtifactScore(
        artifact=rubric.artifact,
        base_score=round(base, 2),
        penalties=round(penalties, 2),
        final_score=round(final, 2),
        confidence=round(confidence, 3),
        metrics=metrics,
        criteria=tuple(results),
    )
