#!/usr/bin/env python3
"""Build cost charts directly from every OpenRouter usage JSONL file."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


COMPANY_ORDER = {"OpenAI": 0, "Google": 1, "DeepSeek": 2}
COMPANY_COLORS = {"OpenAI": "#10b981", "Google": "#60a5fa", "DeepSeek": "#c084fc"}
DISPLAY_NAMES = {
    "openai/gpt-4.1": "GPT-4.1", "openai/gpt-5.4": "GPT-5.4",
    "openai/gpt-5.5": "GPT-5.5", "openai/gpt-5.6-luna": "GPT-5.6 Luna",
    "google/gemma-3-12b-it": "Gemma 3 12B",
    "google/gemma-4-26b-a4b-it": "Gemma 4 26B A4B",
    "google/gemma-4-31b-it": "Gemma 4 31B",
    "google/gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
    "google/gemini-3.6-flash": "Gemini 3.6 Flash",
    "deepseek/deepseek-v3.2": "DeepSeek V3.2",
    "deepseek/deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek/deepseek-v4-pro": "DeepSeek V4 Pro",
}


@dataclass(frozen=True)
class Run:
    model: str
    company: str
    display_name: str
    case_study: str
    calls: int
    total_cost: float
    text_cost: float
    image_cost: float
    costs_by_model: dict[str, float]
    cost_source: str


def company_for(model: str) -> str:
    if model.startswith("openai/"):
        return "OpenAI"
    if model.startswith("google/"):
        return "Google"
    if model.startswith("deepseek/"):
        return "DeepSeek"
    return "Other"


def display_name(model: str) -> str:
    if model in DISPLAY_NAMES:
        return DISPLAY_NAMES[model]
    words = model.split("/", 1)[-1].replace("-it", "").replace("-", " ").split()
    return " ".join(word.upper() if word in {"gpt", "v"} else word.capitalize() for word in words)


def model_from_comparison(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("- model:") or line.lower().startswith("- text model:"):
            return line.split(":", 1)[1].strip().strip(chr(96))
    return path.parent.name


def natural_key(value: str) -> tuple[object, ...]:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value.lower()))


def sort_key(run: Run) -> tuple[object, ...]:
    family = run.display_name.split()[0].lower()
    family_rank = {"gemma": 0, "gemini": 1}.get(family, 0)
    return (COMPANY_ORDER.get(run.company, 9), family_rank, natural_key(run.display_name))


def cost_for(record: dict[str, object]) -> float:
    usage = record.get("usage", {})
    if not isinstance(usage, dict):
        return 0.0
    return float(usage.get("cost", 0.0) or 0.0)


def discover_runs(root: Path) -> list[Run]:
    runs = []
    seen: set[Path] = set()
    for usage_path in sorted(root.rglob("OPENROUTER_USAGE.jsonl")):
        records = [json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not records:
            continue
        calls = Counter(str(record.get("model", "")) for record in records)
        text_model = calls.most_common(1)[0][0]
        costs = defaultdict(float)
        for record in records:
            costs[str(record.get("model", ""))] += cost_for(record)
        image_cost = sum(cost for model, cost in costs.items() if "image" in model.lower())
        total = sum(costs.values())
        runs.append(Run(
            model=text_model,
            company=company_for(text_model),
            display_name=display_name(text_model),
            case_study=usage_path.parent.relative_to(root).as_posix(),
            calls=len(records),
            total_cost=total,
            text_cost=total - image_cost,
            image_cost=image_cost,
            costs_by_model=dict(sorted(costs.items())),
            cost_source="openrouter",
        ))
        seen.add(usage_path.parent.resolve())
    for comparison_path in sorted(root.rglob("MODEL_COMPARISON.md")):
        study_root = comparison_path.parent.resolve()
        if study_root in seen:
            continue
        model = model_from_comparison(comparison_path)
        runs.append(Run(
            model=model,
            company=company_for(model),
            display_name=display_name(model),
            case_study=study_root.relative_to(root).as_posix(),
            calls=0,
            total_cost=0.0,
            text_cost=0.0,
            image_cost=0.0,
            costs_by_model={},
            cost_source="local",
        ))
    return sorted(runs, key=sort_key)


def money(value: float) -> str:
    return chr(36) + f"{value:.6f}"


def nice_max(value: float) -> float:
    magnitude = 10 ** math.floor(math.log10(value))
    return next(multiplier * magnitude for multiplier in (1, 2, 2.5, 5, 10) if multiplier * magnitude >= value)


def ticks_linear(maximum: float) -> list[float]:
    return [maximum * index / 5 for index in range(6)]


def ticks_log(minimum: float, maximum: float) -> list[float]:
    ticks, decade = [], 10 ** math.floor(math.log10(minimum))
    while decade <= maximum:
        for multiplier in (1, 2, 5):
            value = multiplier * decade
            if minimum <= value <= maximum:
                ticks.append(value)
        decade *= 10
    return ticks


def chart(runs: list[Run], logarithmic: bool) -> str:
    groups: dict[str, list[Run]] = {}
    for run in runs:
        groups.setdefault(run.company, []).append(run)
    chart_bottom = 160 + len(runs) * 55 + max(0, len(groups) - 1) * 35
    height, graph_x, graph_width = chart_bottom + 150, 420, 520
    maximum = nice_max(max(run.total_cost for run in runs))
    positive_costs = [run.total_cost for run in runs if run.total_cost > 0]
    minimum = 10 ** math.floor(math.log10(min(positive_costs)))
    if logarithmic:
        tick_values = ticks_log(minimum, maximum)
        def scale(value: float) -> float:
            if value <= 0:
                return 0
            if maximum == minimum:
                return graph_width
            return graph_width * (math.log10(value) - math.log10(minimum)) / (math.log10(maximum) - math.log10(minimum))
        title, subtitle = "SteadyBurn weekly bundle: recorded model cost (log scale)", "base-10 logarithmic scale in USD"
    else:
        tick_values = ticks_linear(maximum)
        def scale(value: float) -> float:
            return graph_width * value / maximum
        title, subtitle = "SteadyBurn weekly bundle: recorded model cost", "linear scale in USD"
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title description">',
        f'  <title id="title">{html.escape(title)}</title>',
        '  <desc id="description">Costs are calculated from OpenRouter usage JSONL records for each completed weekly SteadyBurn case study.</desc>',
        '  <style>.bg{fill:#111827}.title{fill:#f9fafb;font:700 30px Arial,sans-serif}.subtitle,.axis,.note{fill:#9ca3af;font:16px Arial,sans-serif}.group{fill:#f9fafb;font:700 19px Arial,sans-serif}.label{fill:#e5e7eb;font:16px Arial,sans-serif}.value{fill:#f9fafb;font:700 16px Arial,sans-serif;text-anchor:end}.axis{font-size:13px;text-anchor:middle}.note{font-size:14px}.grid{stroke:#374151;stroke-width:1}</style>',
        f'  <rect class="bg" width="1200" height="{height}" rx="18"/>',
        f'  <text class="title" x="60" y="62">{html.escape(title)}</text>',
        f'  <text class="subtitle" x="60" y="91">Complete text bundle plus one hero cover · {subtitle}</text>',
    ]
    for tick in tick_values:
        x = graph_x + scale(tick)
        lines.extend([f'  <line class="grid" x1="{x:.0f}" y1="145" x2="{x:.0f}" y2="{chart_bottom}"/>', f'  <text class="axis" x="{x:.0f}" y="132">{money(tick)}</text>'])
    y = 187
    for company in sorted(groups, key=lambda value: COMPANY_ORDER.get(value, 9)):
        lines.append(f'  <text class="group" x="60" y="{y}">{company}</text>')
        y += 41
        for run in groups[company]:
            marker = "†" if run.model == "google/gemma-3-12b-it" else ""
            lines.extend([
                f'  <text class="label" x="90" y="{y}">{html.escape(run.display_name)}</text>',
                f'  <rect fill="{COMPANY_COLORS.get(company, "#d1d5db")}" x="{graph_x}" y="{y - 21}" width="{max(4, scale(run.total_cost)):.0f}" height="27" rx="4"/>',
                f'  <text class="value" x="1130" y="{y}">{money(run.total_cost)}{" local baseline" if run.cost_source == "local" else marker}</text>',
            ])
            y += 55
        y += 35
    lines.extend([
        f'  <line class="grid" x1="60" y1="{chart_bottom + 5}" x2="1140" y2="{chart_bottom + 5}"/>',
        f'  <text class="note" x="60" y="{chart_bottom + 38}">Local baseline is $0.000000. On log scale it is shown as a labelled zero-length bar.</text>',
        f'  <text class="note" x="60" y="{chart_bottom + 66}">† Gemma 3 was an earlier, non-equivalent comparison.</text>',
        f'  <text class="note" x="60" y="{chart_bottom + 94}">Source: each completed case study’s OPENROUTER_USAGE.jsonl.</text>',
        "</svg>",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    root = args.root.resolve()
    runs = discover_runs(root)
    if not runs:
        raise SystemExit("No OPENROUTER_USAGE.jsonl files found.")
    (root / "weekly-bundle-costs.svg").write_text(chart(runs, logarithmic=False), encoding="utf-8")
    (root / "weekly-bundle-costs-log.svg").write_text(chart(runs, logarithmic=True), encoding="utf-8")
    (root / "cost-chart-data.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "runs": [asdict(run) for run in runs]}, indent=2) + "\n", encoding="utf-8")
    print(f"Processed {len(runs)} case-study cost records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
