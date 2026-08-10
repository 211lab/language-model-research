#!/usr/bin/env python3
"""Measure comparable readability statistics for all case-study text bundles."""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DOCUMENTS = ("LESSON.md", "index.md", "INSTRUCTIONS.md")
VOWELS = re.compile(r"[aeiouy]+", re.IGNORECASE)
WORDS = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])(?:[”’\"')\]]*)\s+")
FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
FENCED_CODE = re.compile(r"~~~.*?~~~", re.DOTALL)
BACKTICK_FENCE = re.compile(re.escape(chr(96) * 3) + r".*?" + re.escape(chr(96) * 3), re.DOTALL)
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
HTML_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class TextStats:
    characters: int
    letters: int
    words: int
    sentences: int
    paragraphs: int
    syllables: int
    polysyllables: int
    long_words: int
    long_sentences: int
    average_words_per_sentence: float
    average_syllables_per_word: float
    average_characters_per_word: float
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog: float
    coleman_liau: float
    automated_readability_index: float
    smog: float | None
    lexical_diversity: float


def clean_markdown(markdown: str) -> str:
    markdown = FRONT_MATTER.sub("", markdown)
    markdown = FENCED_CODE.sub(" ", markdown)
    markdown = BACKTICK_FENCE.sub(" ", markdown)
    markdown = MARKDOWN_LINK.sub(r"\1", markdown)
    markdown = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    markdown = re.sub(r"^\s{0,3}#{1,6}\s+", "", markdown, flags=re.MULTILINE)
    markdown = re.sub(r"^\s*[-*+]\s+", "", markdown, flags=re.MULTILINE)
    markdown = re.sub(r"^\s*\d+[.)]\s+", "", markdown, flags=re.MULTILINE)
    markdown = re.sub(r"[*_>#]", "", markdown)
    return HTML_TAG.sub(" ", markdown).strip()


def syllables(word: str) -> int:
    normalized = re.sub(r"[^a-z]", "", word.lower())
    groups = len(VOWELS.findall(normalized))
    if normalized.endswith("e") and not normalized.endswith(("le", "ye")) and groups > 1:
        groups -= 1
    if normalized.endswith("le") and len(normalized) > 2 and normalized[-3] not in "aeiouy":
        groups += 1
    return max(1, groups)


def sentence_list(text: str) -> list[str]:
    pieces = [piece.strip() for piece in SENTENCE_BREAK.split(text) if WORDS.search(piece)]
    return pieces or ([text] if WORDS.search(text) else [])


def rounded(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def analyze(markdown: str) -> TextStats:
    text = clean_markdown(markdown)
    words = WORDS.findall(text)
    sentences = sentence_list(text)
    sentence_word_counts = [len(WORDS.findall(sentence)) for sentence in sentences]
    syllable_counts = [syllables(word) for word in words]
    word_count = len(words)
    denominator_sentences = max(1, len(sentences))
    letters = sum(character.isalpha() for character in text)
    characters = sum(character.isalnum() for character in text)
    paragraphs = len([block for block in re.split(r"\n\s*\n", text) if WORDS.search(block)])
    total_syllables = sum(syllable_counts)
    polysyllables = sum(count >= 3 for count in syllable_counts)
    average_words_per_sentence = word_count / denominator_sentences
    average_syllables_per_word = total_syllables / word_count if word_count else 0
    average_characters_per_word = letters / word_count if word_count else 0
    flesch = 206.835 - 1.015 * average_words_per_sentence - 84.6 * average_syllables_per_word
    fk_grade = 0.39 * average_words_per_sentence + 11.8 * average_syllables_per_word - 15.59
    fog = 0.4 * (average_words_per_sentence + 100 * polysyllables / word_count) if word_count else 0
    letters_per_100 = 100 * letters / word_count if word_count else 0
    sentences_per_100 = 100 * denominator_sentences / word_count if word_count else 0
    coleman_liau = 0.0588 * letters_per_100 - 0.296 * sentences_per_100 - 15.8
    ari = 4.71 * average_characters_per_word + 0.5 * average_words_per_sentence - 21.43
    smog = 1.043 * math.sqrt(polysyllables * 30 / denominator_sentences) + 3.1291 if len(sentences) >= 3 else None
    return TextStats(
        characters=characters,
        letters=letters,
        words=word_count,
        sentences=len(sentences),
        paragraphs=paragraphs,
        syllables=total_syllables,
        polysyllables=polysyllables,
        long_words=sum(len(re.sub(r"[^A-Za-z]", "", word)) >= 7 for word in words),
        long_sentences=sum(count >= 20 for count in sentence_word_counts),
        average_words_per_sentence=rounded(average_words_per_sentence),
        average_syllables_per_word=rounded(average_syllables_per_word),
        average_characters_per_word=rounded(average_characters_per_word),
        flesch_reading_ease=rounded(flesch),
        flesch_kincaid_grade=rounded(fk_grade),
        gunning_fog=rounded(fog),
        coleman_liau=rounded(coleman_liau),
        automated_readability_index=rounded(ari),
        smog=rounded(smog),
        lexical_diversity=rounded(len({word.lower() for word in words}) / word_count if word_count else 0),
    )


def study_model(path: Path) -> str:
    comparison = path / "MODEL_COMPARISON.md"
    match = re.search(
        r"^- (?:Text )?model:\s*([^\n]+)",
        comparison.read_text(encoding="utf-8"),
        re.MULTILINE | re.IGNORECASE,
    )
    return match.group(1).strip().strip(chr(96)) if match else path.parent.name


def studies(root: Path) -> Iterable[Path]:
    for comparison in sorted(root.rglob("MODEL_COMPARISON.md")):
        path = comparison.parent
        if all((path / document).exists() for document in DOCUMENTS):
            yield path


def report(records: list[dict[str, object]]) -> str:
    lines = [
        "# Case Study Readability Report",
        "",
        "Comparable measurements for LESSON.md, index.md, and INSTRUCTIONS.md from every completed case study.",
        "",
        "Markdown presentation syntax is removed before one deterministic English syllable heuristic is applied to every source. Scores are estimates, not editorial judgments.",
        "",
        "## Bundle summary",
        "",
        "| Model | Words | Sentences | Avg words/sentence | Flesch ease | FK grade | Fog | Coleman-Liau | ARI | SMOG | Lexical diversity |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in (item for item in records if item["document"] == "bundle total"):
        smog = "—" if row["smog"] is None else f"{row['smog']:.2f}"
        lines.append(
            f"| {row['model']} | {row['words']} | {row['sentences']} | {row['average_words_per_sentence']:.2f} | {row['flesch_reading_ease']:.2f} | {row['flesch_kincaid_grade']:.2f} | {row['gunning_fog']:.2f} | {row['coleman_liau']:.2f} | {row['automated_readability_index']:.2f} | {smog} | {row['lexical_diversity']:.2f} |"
        )
    lines.extend([
        "",
        "## Per-document measurements",
        "",
        "| Model | Document | Words | Sentences | Paragraphs | Avg words/sentence | Flesch ease | FK grade | Fog |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in (item for item in records if item["document"] != "bundle total"):
        lines.append(
            f"| {row['model']} | {row['document']} | {row['words']} | {row['sentences']} | {row['paragraphs']} | {row['average_words_per_sentence']:.2f} | {row['flesch_reading_ease']:.2f} | {row['flesch_kincaid_grade']:.2f} | {row['gunning_fog']:.2f} |"
        )
    lines.extend([
        "",
        "## Metric notes",
        "",
        "- Flesch reading ease: higher is generally easier to read.",
        "- FK grade, Fog, Coleman-Liau, ARI, and SMOG: estimated U.S. grade level; lower is generally easier to read.",
        "- Lexical diversity: unique words divided by total words after normalization.",
        "- Long sentence: 20 or more words. Long word: seven or more letters.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--json-output", type=Path, default=Path("readability-report.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("readability-report.md"))
    args = parser.parse_args()
    root = args.root.resolve()
    records: list[dict[str, object]] = []
    for study in studies(root):
        model = study_model(study)
        texts = []
        for document in DOCUMENTS:
            text = (study / document).read_text(encoding="utf-8")
            texts.append(clean_markdown(text))
            row = {
                "model": model,
                "case_study": study.relative_to(root).as_posix(),
                "document": document,
                "source": (study / document).relative_to(root).as_posix(),
                **asdict(analyze(text)),
            }
            records.append(row)
        bundle = {
            "model": model,
            "case_study": study.relative_to(root).as_posix(),
            "document": "bundle total",
            "source": "LESSON.md + index.md + INSTRUCTIONS.md",
            **asdict(analyze("\n\n".join(texts))),
        }
        records.append(bundle)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": list(DOCUMENTS),
        "method": "Markdown is normalized before deterministic English readability estimates are calculated.",
        "records": records,
    }
    json_path = args.json_output if args.json_output.is_absolute() else root / args.json_output
    markdown_path = args.markdown_output if args.markdown_output.is_absolute() else root / args.markdown_output
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(report(records), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
