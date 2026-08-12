#!/usr/bin/env python3
"""Compile the local personal-assistant benchmark into static research charts."""

from __future__ import annotations

import csv
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIMENSIONS = (
    ("outcome", "Outcome", 30.0, "#22c55e"),
    ("tool_use", "Tool use", 25.0, "#3b82f6"),
    ("grounding", "Grounding", 15.0, "#8b5cf6"),
    ("state", "State", 10.0, "#06b6d4"),
    ("english", "English", 10.0, "#f59e0b"),
    ("safety", "Safety", 5.0, "#ef4444"),
    ("efficiency", "Efficiency", 5.0, "#64748b"),
)
NUMERIC_FIELDS = {
    "assistant_score", "outcome", "tool_use", "grounding", "state", "english",
    "safety", "efficiency", "task_pass_rate", "tool_call_success_rate",
    "median_task_seconds", "total_task_seconds", "cold_start_seconds",
    "cold_ttft_seconds", "openclaw_seconds", "openclaw_ttft_seconds",
    "latency_total_seconds",
}
INTEGER_FIELDS = {"tasks_passed", "tasks_total"}
PLOT_NAMES = {
    "cydonia-24b-v4.3": "Cydonia 24B",
    "dolphin-mistral-24b-venice": "Dolphin Mistral 24B",
    "empero-ai-qwythos-9b-claude-mythos-5-1m-gguf-qwythos-9b-claude-mythos-5-1m-mtp-q4-k-m": "Qwythos 9B",
    "gemma-4-12b-obliterated": "Gemma 12B",
    "gemma-4-e4b-it": "Gemma E4B",
    "qwen3.6-27b-heretic-neo-code": "Qwen 27B Heretic",
    "qwen3.6-35b-hauhaucs-aggressive": "Qwen 35B HauhauCS",
    "unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl": "Unsloth Qwen 27B",
    "unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s": "Unsloth Qwen 35B A3B",
}


def load_dataset(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with (root / "model-results.csv").open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, Any] = dict(raw)
            for key in NUMERIC_FIELDS:
                row[key] = float(row[key])
            for key in INTEGER_FIELDS:
                row[key] = int(row[key])
            row["tool_call_detected"] = row["tool_call_detected"].lower() == "true"
            rows.append(row)
    rows.sort(key=lambda item: item["assistant_score"], reverse=True)
    return {
        "schema_version": "personal-assistant-benchmark-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": "2026-08-02",
        "runtime": "llama.cpp via llama-swap",
        "protocol": "unload; wait 10 seconds; warm one model; run 21 fresh-fixture tasks; unload; repeat",
        "temperature": 0,
        "seed": 42,
        "max_tokens_per_turn": 768,
        "task_count_per_model": 21,
        "model_count": len(rows),
        "fixture_sha256": "ea2601bcb637a9c66563e91015f15a007a0a06f7d88532ec218c8c178903efb9",
        "tasks_sha256": "907017aa0d29639967cd0c0702764b73e7cc8ebbf254625fcc07b63e13b4428e",
        "dimensions": [{"id": key, "label": label, "weight_percent": weight} for key, label, weight, _ in DIMENSIONS],
        "models": rows,
    }


def esc(value: Any) -> str:
    return html.escape(str(value))


def short_name(value: str, limit: int = 34) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def plot_name(model: dict[str, Any]) -> str:
    return PLOT_NAMES.get(model["model"], short_name(model["display_name"], 25))


def svg_shell(title: str, description: str, width: int, height: int, body: list[str]) -> str:
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{esc(title)}</title><desc id="desc">{esc(description)}</desc>',
        '<style>.bg{fill:#0b1020}.title{fill:#f8fafc;font:700 27px Arial,sans-serif}.sub,.tick{fill:#94a3b8;font:14px Arial,sans-serif}.label{fill:#e2e8f0;font:15px Arial,sans-serif}.value{fill:#f8fafc;font:700 15px Arial,sans-serif}.grid{stroke:#334155;stroke-width:1}.axis{stroke:#64748b;stroke-width:1.5}</style>',
        f'<rect class="bg" width="{width}" height="{height}" rx="18"/>',
        f'<text class="title" x="32" y="46">{esc(title)}</text>',
        f'<text class="sub" x="32" y="72">{esc(description)}</text>',
        *body,
        '</svg>',
    ]) + "\n"


def score_svg(data: dict[str, Any]) -> str:
    models = data["models"]
    width, height, left, top, plot_width, row_height = 1240, 690, 360, 128, 790, 55
    body: list[str] = []
    for tick in (0, 25, 50, 75, 100):
        x = left + plot_width * tick / 100
        body += [f'<line class="grid" x1="{x:.1f}" y1="112" x2="{x:.1f}" y2="{height-42}"/>', f'<text class="tick" x="{x:.1f}" y="{height-18}" text-anchor="middle">{tick}</text>']
    legend_x, legend_y = 32, 96
    for _key, label, weight, color in DIMENSIONS:
        body += [f'<rect x="{legend_x}" y="{legend_y}" width="12" height="12" rx="2" fill="{color}"/>', f'<text class="tick" x="{legend_x+18}" y="{legend_y+11}">{esc(label)} ({weight:.0f}%)</text>']
        legend_x += 145
    for index, model in enumerate(models):
        y = top + index * row_height
        body.append(f'<text class="label" x="{left-16}" y="{y+18}" text-anchor="end">{esc(plot_name(model))}</text>')
        cursor = left
        for key, _label, weight, color in DIMENSIONS:
            contribution = model[key] * weight / 100
            segment = plot_width * contribution / 100
            body.append(f'<rect x="{cursor:.2f}" y="{y}" width="{segment:.2f}" height="26" fill="{color}"/>')
            cursor += segment
        body.append(f'<text class="value" x="{cursor+9:.1f}" y="{y+19}">{model["assistant_score"]:.1f}</text>')
    return svg_shell("Personal-assistant intelligence", "Weighted score; higher is better. Timing is excluded from this score.", width, height, body)


def tradeoff_svg(data: dict[str, Any]) -> str:
    models = data["models"]
    width, height, left, right, top, bottom = 1240, 650, 92, 1180, 105, 560
    lo, hi = math.log10(1), math.log10(300)
    x = lambda seconds: left + (right-left) * (math.log10(max(1, seconds))-lo) / (hi-lo)
    y = lambda score: bottom - (bottom-top) * score / 100
    body: list[str] = []
    for tick in (1, 3, 10, 30, 100, 300):
        xx = x(tick)
        body += [f'<line class="grid" x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{bottom}"/>', f'<text class="tick" x="{xx:.1f}" y="{bottom+28}" text-anchor="middle">{tick}s</text>']
    for tick in (0, 20, 40, 60, 80, 100):
        yy = y(tick)
        body += [f'<line class="grid" x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}"/>', f'<text class="tick" x="{left-12}" y="{yy+5:.1f}" text-anchor="end">{tick}</text>']
    body += [f'<text class="tick" x="{(left+right)/2:.1f}" y="{height-22}" text-anchor="middle">Median task time (log scale; lower is better)</text>', f'<text class="tick" transform="translate(24 {(top+bottom)/2:.1f}) rotate(-90)" text-anchor="middle">Assistant score (higher is better)</text>']
    offsets = {
        "unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl": (-10, -12),
        "qwen3.6-27b-heretic-neo-code": (-10, 18),
        "unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s": (10, -12),
        "gemma-4-e4b-it": (10, -12),
        "qwen3.6-35b-hauhaucs-aggressive": (10, 18),
        "gemma-4-12b-obliterated": (-10, 18),
        "cydonia-24b-v4.3": (10, 18),
        "dolphin-mistral-24b-venice": (-10, -12),
    }
    for model in models:
        if model["median_task_seconds"] <= 0:
            continue
        xx, yy = x(model["median_task_seconds"]), y(model["assistant_score"])
        dx, dy = offsets[model["model"]]
        anchor = "end" if dx < 0 else "start"
        body += [f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="7" fill="#38bdf8"><title>{esc(model["display_name"])}: {model["assistant_score"]:.2f}, {model["median_task_seconds"]:.2f}s median</title></circle>', f'<text class="label" x="{xx+dx:.1f}" y="{yy+dy:.1f}" text-anchor="{anchor}">{esc(plot_name(model))}</text>']
    body.append(f'<text class="sub" x="{left}" y="{height-4}">Qwythos is omitted: 12 HTTP 502 errors make its recorded median task time invalid.</text>')
    return svg_shell("Assistant quality versus task speed", "Upper-left is better: higher intelligence with lower median task time.", width, height, body)


def latency_svg(data: dict[str, Any]) -> str:
    models = sorted(data["models"], key=lambda item: item["latency_total_seconds"])
    width, height, left, top, plot_width, row_height = 1240, 690, 360, 115, 790, 55
    maximum = 130.0
    body: list[str] = []
    for tick in (0, 25, 50, 75, 100, 125):
        xx = left + plot_width * tick / maximum
        body += [f'<line class="grid" x1="{xx:.1f}" y1="100" x2="{xx:.1f}" y2="{height-42}"/>', f'<text class="tick" x="{xx:.1f}" y="{height-18}" text-anchor="middle">{tick}s</text>']
    body += ['<rect x="32" y="88" width="12" height="12" rx="2" fill="#3b82f6"/><text class="tick" x="50" y="99">Cold load + first response</text>', '<rect x="244" y="88" width="12" height="12" rx="2" fill="#f59e0b"/><text class="tick" x="262" y="99">Warm OpenClaw-style request</text>']
    for index, model in enumerate(models):
        yy = top + index * row_height
        cold = plot_width * model["cold_start_seconds"] / maximum
        warm = plot_width * model["openclaw_seconds"] / maximum
        body += [f'<text class="label" x="{left-16}" y="{yy+18}" text-anchor="end">{esc(plot_name(model))}</text>', f'<rect x="{left}" y="{yy}" width="{cold:.2f}" height="26" fill="#3b82f6"/>', f'<rect x="{left+cold:.2f}" y="{yy}" width="{warm:.2f}" height="26" fill="#f59e0b"/>', f'<text class="value" x="{left+cold+warm+9:.1f}" y="{yy+19}">{model["latency_total_seconds"]:.1f}s</text>']
    return svg_shell("Cold-load and OpenClaw latency", "One model resident and one request active; 10-second unloaded buffer between models.", width, height, body)


def heatmap_svg(data: dict[str, Any]) -> str:
    models = data["models"]
    width, height, left, top, cell_w, cell_h = 1240, 700, 355, 125, 112, 55
    body: list[str] = []
    for col, (_key, label, _weight, _color) in enumerate(DIMENSIONS):
        body.append(f'<text class="tick" x="{left+col*cell_w+cell_w/2}" y="{top-18}" text-anchor="middle">{esc(label)}</text>')
    for row, model in enumerate(models):
        yy = top + row * cell_h
        body.append(f'<text class="label" x="{left-16}" y="{yy+31}" text-anchor="end">{esc(plot_name(model))}</text>')
        for col, (key, _label, _weight, _color) in enumerate(DIMENSIONS):
            value = model[key]
            hue = 120 * value / 100
            body += [f'<rect x="{left+col*cell_w}" y="{yy}" width="{cell_w-4}" height="40" rx="4" fill="hsl({hue:.1f} 64% 38%)"/>', f'<text class="value" x="{left+col*cell_w+(cell_w-4)/2:.1f}" y="{yy+26}" text-anchor="middle">{value:.1f}</text>']
    return svg_shell("Assistant capability heatmap", "Hard 0–100 category scores; green is higher and red is lower.", width, height, body)


def dashboard_html(
    data: dict[str, Any], charts: dict[str, str], source_prefix: str, editorial_href: str
) -> str:
    rows = "".join(
        f'<tr><td>{esc(model["display_name"])}</td><td>{model["assistant_score"]:.2f}</td><td>{model["tasks_passed"]}/{model["tasks_total"]}</td><td>{model["tool_call_success_rate"]:.1f}%</td><td>{model["median_task_seconds"]:.2f}s</td><td>{model["cold_start_seconds"]:.2f}s</td><td>{model["openclaw_seconds"]:.2f}s</td><td>{esc(model["run_status"])}</td></tr>'
        for model in data["models"]
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Personal-assistant model benchmark</title><style>
body{{margin:0;background:#070b16;color:#e5e7eb;font:16px system-ui,sans-serif}}main{{max-width:1280px;margin:auto;padding:28px}}a{{color:#7dd3fc}}h1{{margin-bottom:6px}}h2{{margin-top:38px}}.muted{{color:#a5b4c7;max-width:900px}}.chart{{overflow-x:auto;margin:14px 0}}.chart svg{{display:block;width:100%;height:auto;min-width:820px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #263349;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{color:#a5b4c7}}code{{font-size:.85em}}
</style></head><body><main><nav><a href="{editorial_href}">Editorial content research</a></nav><h1>Personal-assistant model benchmark</h1><p class="muted">Nine local GGUF models, 21 synthetic information-worker tasks each, temperature 0 and seed 42. Intelligence and timing remain separate measurements. A <code>partial</code> run hit a tool-turn ceiling or API error; all scheduled tasks remain represented.</p>
<h2>Weighted assistant intelligence</h2><div class="chart">{charts["score"]}</div>
<h2>Speed–quality decision view</h2><div class="chart">{charts["tradeoff"]}</div>
<h2>Cold-load and agent latency</h2><div class="chart">{charts["latency"]}</div>
<h2>Capability dimensions</h2><div class="chart">{charts["heatmap"]}</div>
<h2>Hard values</h2><div style="overflow-x:auto"><table><thead><tr><th>Model</th><th>Score</th><th>Passed</th><th>Tool success</th><th>Median task</th><th>Cold load</th><th>OpenClaw request</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted">Source: <a href="{source_prefix}model-results.csv">model-results.csv</a>. Method and caveats: <a href="{source_prefix}README.md">benchmark notes</a>.</p></main></body></html>'''


def build(root: Path, repo_root: Path) -> dict[str, Any]:
    data = load_dataset(root)
    charts = {"score": score_svg(data), "tradeoff": tradeoff_svg(data), "latency": latency_svg(data), "heatmap": heatmap_svg(data)}
    outputs = {
        "assistant-benchmark.json": json.dumps(data, indent=2) + "\n",
        "assistant-benchmark-score.svg": charts["score"],
        "assistant-benchmark-speed-quality.svg": charts["tradeoff"],
        "assistant-benchmark-latency.svg": charts["latency"],
        "assistant-benchmark-categories.svg": charts["heatmap"],
    }
    for directory in (root, repo_root):
        for name, content in outputs.items():
            (directory / name).write_text(content, encoding="utf-8")
    (root / "assistant-benchmark.html").write_text(
        dashboard_html(data, charts, "", "../model-comparisons/model-comparison.html"), encoding="utf-8"
    )
    (repo_root / "assistant-benchmark.html").write_text(
        dashboard_html(data, charts, "docs/assistant-benchmark/", "index.html"), encoding="utf-8"
    )
    return data


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    result = build(here, here.parents[1])
    print(f"Built assistant benchmark for {result['model_count']} models")
