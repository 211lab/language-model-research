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
LOCAL_PROVIDERS = {
    "gemma-4-12b-obliterated": "Google local",
    "gemma-4-e4b-it": "Google local",
    "qwen3.6-27b-heretic-neo-code": "Qwen fine-tunes",
    "qwen3.6-35b-hauhaucs-aggressive": "Qwen fine-tunes",
    "unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-ud-q4-k-xl": "Unsloth",
    "unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl": "Unsloth",
    "unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s": "Unsloth",
    "cydonia-24b-v4.3": "Community local",
    "dolphin-mistral-24b-venice": "Community local",
    "empero-ai-qwythos-9b-claude-mythos-5-1m-gguf-qwythos-9b-claude-mythos-5-1m-mtp-q4-k-m": "Community local",
}


def load_dataset(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_files = [root / "model-results.csv"]
    cross_run = root / "openrouter-model-results.csv"
    if cross_run.exists():
        source_files.append(cross_run)
    for source_file in source_files:
        with source_file.open(encoding="utf-8", newline="") as handle:
          for raw in csv.DictReader(handle):
            row: dict[str, Any] = dict(raw)
            for key in NUMERIC_FIELDS:
                row[key] = float(row.get(key) or 0)
            for key in INTEGER_FIELDS:
                row[key] = int(float(row.get(key) or 0))
            row["tool_call_detected"] = str(row.get("tool_call_detected", "false")).lower() == "true"
            row["provider"] = row.get("provider") or LOCAL_PROVIDERS.get(row["model"], "Local models")
            row["benchmark_track"] = row.get("benchmark_track") or "local"
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
        "cohort_counts": {
            "local": sum(row["benchmark_track"] == "local" for row in rows),
            "openrouter": sum(row["benchmark_track"] == "openrouter" for row in rows),
        },
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


def model_attr(model: dict[str, Any]) -> str:
    return f' data-model="{esc(model["model"])}"'


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
        attr = model_attr(model)
        body.append(f'<text class="label"{attr} x="{left-16}" y="{y+18}" text-anchor="end">{esc(plot_name(model))}</text>')
        cursor = left
        for key, _label, weight, color in DIMENSIONS:
            contribution = model[key] * weight / 100
            segment = plot_width * contribution / 100
            body.append(f'<rect{attr} x="{cursor:.2f}" y="{y}" width="{segment:.2f}" height="26" fill="{color}"/>')
            cursor += segment
        body.append(f'<text class="value"{attr} x="{cursor+9:.1f}" y="{y+19}">{model["assistant_score"]:.1f}</text>')
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
        # Keep charts publishable when a newly discovered local model joins a
        # round. Known points have hand-tuned offsets; unknown ones get a
        # readable, deterministic default.
        dx, dy = offsets.get(model["model"], (10, -12))
        anchor = "end" if dx < 0 else "start"
        attr = model_attr(model)
        body += [f'<circle{attr} cx="{xx:.1f}" cy="{yy:.1f}" r="7" fill="#38bdf8"><title>{esc(model["display_name"])}: {model["assistant_score"]:.2f}, {model["median_task_seconds"]:.2f}s median</title></circle>', f'<text class="label"{attr} x="{xx+dx:.1f}" y="{yy+dy:.1f}" text-anchor="{anchor}">{esc(plot_name(model))}</text>']
    body.append(f'<text class="sub" x="{left}" y="{height-4}">Each point uses the recorded median task duration from the same fixed-seed local round.</text>')
    return svg_shell("Assistant quality versus task speed", "Upper-left is better: higher intelligence with lower median task time.", width, height, body)


def latency_svg(data: dict[str, Any]) -> str:
    models = sorted(
        (item for item in data["models"] if item["latency_total_seconds"] > 0),
        key=lambda item: item["latency_total_seconds"],
    )
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
        attr = model_attr(model)
        body += [f'<text class="label"{attr} x="{left-16}" y="{yy+18}" text-anchor="end">{esc(plot_name(model))}</text>', f'<rect{attr} x="{left}" y="{yy}" width="{cold:.2f}" height="26" fill="#3b82f6"/>', f'<rect{attr} x="{left+cold:.2f}" y="{yy}" width="{warm:.2f}" height="26" fill="#f59e0b"/>', f'<text class="value"{attr} x="{left+cold+warm+9:.1f}" y="{yy+19}">{model["latency_total_seconds"]:.1f}s</text>']
    return svg_shell("Cold-load and OpenClaw latency", "Only cohorts with recorded latency telemetry are plotted; unavailable provider timing is omitted.", width, height, body)


def heatmap_svg(data: dict[str, Any]) -> str:
    models = data["models"]
    width, height, left, top, cell_w, cell_h = 1240, 700, 355, 125, 112, 55
    body: list[str] = []
    for col, (_key, label, _weight, _color) in enumerate(DIMENSIONS):
        body.append(f'<text class="tick" x="{left+col*cell_w+cell_w/2}" y="{top-18}" text-anchor="middle">{esc(label)}</text>')
    for row, model in enumerate(models):
        yy = top + row * cell_h
        attr = model_attr(model)
        body.append(f'<text class="label"{attr} x="{left-16}" y="{yy+31}" text-anchor="end">{esc(plot_name(model))}</text>')
        for col, (key, _label, _weight, _color) in enumerate(DIMENSIONS):
            value = model[key]
            hue = 120 * value / 100
            body += [f'<rect{attr} x="{left+col*cell_w}" y="{yy}" width="{cell_w-4}" height="40" rx="4" fill="hsl({hue:.1f} 64% 38%)"/>', f'<text class="value"{attr} x="{left+col*cell_w+(cell_w-4)/2:.1f}" y="{yy+26}" text-anchor="middle">{value:.1f}</text>']
    return svg_shell("Assistant capability heatmap", "Hard 0–100 category scores; green is higher and red is lower.", width, height, body)


def dashboard_html(
    data: dict[str, Any], charts: dict[str, str], source_prefix: str, editorial_href: str, home_href: str, methodology_href: str
) -> str:
    def seconds(value: float) -> str:
        return f"{value:.2f}s" if value > 0 else "—"

    rows = "".join(
        f'<tr{model_attr(model)}><td>{esc(model["display_name"])}</td><td>{model["assistant_score"]:.2f}</td><td>{model["tasks_passed"]}/{model["tasks_total"]}</td><td>{model["tool_call_success_rate"]:.1f}%</td><td>{seconds(model["median_task_seconds"])}</td><td>{seconds(model["cold_start_seconds"])}</td><td>{seconds(model["openclaw_seconds"])}</td><td>{esc(model["run_status"])}</td></tr>'
        for model in data["models"]
    )
    by_id = {model["model"]: model for model in data["models"]}
    provider_models: dict[str, list[str]] = {}
    for model in data["models"]:
        provider_models.setdefault(model["provider"], []).append(model["model"])
    groups = "".join(
        '<section class="provider-group"><label class="provider-toggle"><input type="checkbox" data-provider="{name}" checked> {name}</label>{items}</section>'.format(
            name=esc(name),
            items="".join(
                f'<label><input type="checkbox" data-model-control="{esc(model_id)}" data-provider-name="{esc(name)}" checked> {esc(plot_name(by_id[model_id]))}</label>'
                for model_id in model_ids
            ),
        )
        for name, model_ids in provider_models.items()
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Personal-assistant model benchmark</title><style>
body{{margin:0;background:#070b16;color:#e5e7eb;font:16px system-ui,sans-serif}}main{{max-width:1280px;margin:auto;padding:28px}}a{{color:#7dd3fc}}h1{{margin-bottom:6px}}h2{{margin-top:38px}}.muted{{color:#a5b4c7;max-width:900px}}.chart{{overflow-x:auto;margin:14px 0}}.chart svg{{display:block;width:100%;height:auto;min-width:820px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #263349;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{color:#a5b4c7}}code{{font-size:.85em}}.site-nav{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}}.site-brand{{color:#f8fafc;text-decoration:none;font-weight:750}}.menu-button{{margin-left:auto;border:1px solid #38506f;background:#111a2d;color:#e5e7eb;border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}}.menu-links{{display:flex;gap:14px;align-items:center}}.menu-links a{{text-decoration:none}}.model-selector{{margin:24px 0;padding:14px 16px;border:1px solid #263349;border-radius:12px;background:#0d1424}}.model-selector summary{{cursor:pointer;font-weight:700}}.model-selector[open] summary{{margin-bottom:14px}}.selection-actions{{display:flex;gap:10px;margin:0 0 14px}}.selection-actions button{{border:1px solid #38506f;background:#18243a;color:#e5e7eb;border-radius:7px;padding:6px 10px;cursor:pointer}}.provider-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}}.provider-group{{border-left:2px solid #38bdf8;padding-left:10px;display:grid;gap:7px}}.provider-group label{{cursor:pointer}}.provider-toggle{{font-weight:700}}@media(max-width:680px){{main{{padding:18px}}.site-nav{{position:relative}}.menu-links{{display:none;position:absolute;right:0;top:42px;z-index:10;min-width:230px;flex-direction:column;align-items:stretch;padding:12px;border:1px solid #263349;border-radius:10px;background:#111a2d;box-shadow:0 12px 28px #0008}}.menu-links.is-open{{display:flex}}.menu-links a{{padding:7px}}}}@media(min-width:681px){{.menu-button{{display:none}}}}
</style></head><body><main><nav class="site-nav" aria-label="Primary"><a class="site-brand" href="{home_href}">Language model research</a><button class="menu-button" type="button" aria-expanded="false" aria-controls="site-menu">Menu ☰</button><div class="menu-links" id="site-menu"><a href="{home_href}">Editorial research</a><a href="{editorial_href}">Model comparison</a><a href="{methodology_href}">Methodology</a></div></nav><h1>Personal-assistant model benchmark</h1><p class="muted">Nine local GGUF models, 21 synthetic information-worker tasks each, temperature 0 and seed 42. Intelligence and timing remain separate measurements. A <code>partial</code> run hit a tool-turn ceiling or API error; all scheduled tasks remain represented.</p>
<details class="model-selector"><summary>Choose models by provider</summary><div class="selection-actions"><button type="button" data-selection="all">Select all</button><button type="button" data-selection="none">Clear all</button></div><div class="provider-grid">{groups}</div></details><p class="muted">The local cohort and the OpenRouter cohort use the same assistant task suite. Their scores are comparable on task quality; latency is only reported where the companion measurement exists.</p>
<h2>Weighted assistant intelligence</h2><div class="chart">{charts["score"]}</div>
<h2>Speed–quality decision view</h2><div class="chart">{charts["tradeoff"]}</div>
<h2>Cold-load and agent latency</h2><div class="chart">{charts["latency"]}</div>
<h2>Capability dimensions</h2><div class="chart">{charts["heatmap"]}</div>
<h2>Hard values</h2><div style="overflow-x:auto"><table><thead><tr><th>Model</th><th>Score</th><th>Passed</th><th>Tool success</th><th>Median task</th><th>Cold load</th><th>OpenClaw request</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="muted">Source: <a href="{source_prefix}model-results.csv">model-results.csv</a>. Method and caveats: <a href="{methodology_href}">published methodology</a> and <a href="{source_prefix}README.md">benchmark notes</a>.</p><script>const controls=[...document.querySelectorAll('[data-model-control]')];function applySelection(){{controls.forEach(control=>document.querySelectorAll('[data-model="'+control.dataset.modelControl+'"]').forEach(item=>item.style.display=control.checked?'':'none'));document.querySelectorAll('[data-provider]').forEach(provider=>{{const related=controls.filter(control=>control.dataset.providerName===provider.dataset.provider);provider.checked=related.every(control=>control.checked);provider.indeterminate=related.some(control=>control.checked)&&!provider.checked}})}}controls.forEach(control=>control.addEventListener('change',applySelection));document.querySelectorAll('[data-provider]').forEach(provider=>provider.addEventListener('change',()=>{{controls.filter(control=>control.dataset.providerName===provider.dataset.provider).forEach(control=>control.checked=provider.checked);applySelection()}}));document.querySelectorAll('[data-selection]').forEach(button=>button.addEventListener('click',()=>{{controls.forEach(control=>control.checked=button.dataset.selection==='all');applySelection()}}));const menuButton=document.querySelector('.menu-button'),menu=document.querySelector('.menu-links');menuButton.addEventListener('click',()=>{{const open=menu.classList.toggle('is-open');menuButton.setAttribute('aria-expanded',String(open))}});applySelection();</script></main></body></html>'''


def methodology_html(data: dict[str, Any]) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research methodology</title><style>
body{{margin:0;background:#070b16;color:#e5e7eb;font:16px/1.55 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:28px}}a{{color:#7dd3fc}}h1{{margin-bottom:6px}}h2{{margin-top:36px}}.muted{{color:#a5b4c7}}.site-nav{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}}.site-brand{{color:#f8fafc;text-decoration:none;font-weight:750}}.menu-button{{margin-left:auto;border:1px solid #38506f;background:#111a2d;color:#e5e7eb;border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}}.menu-links{{display:flex;gap:14px;align-items:center}}.menu-links a{{text-decoration:none}}.card{{background:#0d1424;border:1px solid #263349;border-radius:12px;padding:18px;margin:16px 0}}li{{margin:7px 0}}@media(max-width:680px){{main{{padding:18px}}.site-nav{{position:relative}}.menu-links{{display:none;position:absolute;right:0;top:42px;z-index:10;min-width:230px;flex-direction:column;align-items:stretch;padding:12px;border:1px solid #263349;border-radius:10px;background:#111a2d;box-shadow:0 12px 28px #0008}}.menu-links.is-open{{display:flex}}.menu-links a{{padding:7px}}}}@media(min-width:681px){{.menu-button{{display:none}}}}
</style></head><body><main><nav class="site-nav" aria-label="Primary"><a class="site-brand" href="index.html">Language model research</a><button class="menu-button" type="button" aria-expanded="false" aria-controls="site-menu">Menu ☰</button><div class="menu-links" id="site-menu"><a href="index.html">Editorial research</a><a href="assistant-benchmark.html">Assistant benchmark</a><a href="methodology.html">Methodology</a></div></nav><h1>Research methodology</h1><p class="muted">A transparent record of what these comparisons measure, what they do not, and how to reproduce the inputs.</p>
<section class="card"><h2>Personal-assistant benchmark</h2><p>The assistant evaluation uses {data["model_count"]} local GGUF models served through llama.cpp via llama-swap. Each model receives the same 21 fresh synthetic fixtures covering project work, information retrieval, structured tool calls, state tracking, English communication, and safe handling of requests.</p><ul><li>Temperature 0, seed 42, with up to 768 tokens per turn.</li><li>Only one model is loaded and one request is active at a time. The model is unloaded and a 10-second buffer elapses before the next model.</li><li>Intelligence is a weighted 0–100 score: outcome 30%, tool use 25%, grounding 15%, state 10%, English 10%, safety 5%, efficiency 5%.</li><li>Latency is reported separately: cold load plus first response, warm OpenClaw-style request, and their total. It is never folded into the intelligence score.</li><li>A <code>partial</code> result means a tool-turn ceiling or API error affected the run. Its scheduled tasks remain in the report; it is not comparable to a clean <code>ok</code> run without that caveat.</li></ul><p>Exact scores, timings, run status, and source fixtures are retained in the <a href="docs/assistant-benchmark/model-results.csv">published dataset</a> and <a href="docs/assistant-benchmark/README.md">benchmark notes</a>.</p></section>
<section class="card"><h2>Editorial content research</h2><p>The editorial comparison uses the published case-study output for each model, a fixed rubric, readability measurements, and recorded OpenRouter bundle prices when available. The dashboard keeps quality, readability, and price as separate fields so a lower cost is not mistaken for higher quality.</p><ul><li>Content scores are rubric-based rather than a general intelligence claim.</li><li>Charts retain hard values and report unavailable prices explicitly.</li><li>The local model is shown as a zero-cost baseline only for the recorded bundle comparison; hardware and electricity costs are outside that axis.</li></ul><p>Detailed rubric definitions, source artifacts, and per-model evidence live with the <a href="docs/model-comparisons/README.md">model-comparison research</a>.</p></section>
<section class="card"><h2>Judge change: DeepSeek to Luna</h2><p>The rubric, deterministic measurements, evidence verification, three-pass median, and tie-break rule stayed the same. The local editorial cross-run used GPT-5.6 Luna for evidence extraction, judging, and tie-breaking, so this is an evaluator-stack change rather than an isolated final-judge change.</p><ul><li>The current records contain 8 complete Luna-scored local source snapshots.</li><li>They contain 2 complete DeepSeek-backed source snapshots, plus one incomplete earlier DeepSeek attempt.</li><li>No complete immutable content snapshot is currently scored by both DeepSeek and Luna, so a score difference cannot be attributed to Luna alone.</li></ul><p>The <a href="docs/model-comparisons/judge-comparison.md">judge comparison note</a> includes the exact coverage, the same-task assistant comparison, and the paired protocol required before claiming judge impact.</p></section>
<h2>Interpretation limits</h2><p>These results are directional evidence for the stated workflows and runtime. They do not establish broad model capability, reliability across unseen data, provider service quality, or cost on another machine. Model versions, quantization, hardware, prompts, and tool schemas can materially change outcomes.</p><script>const button=document.querySelector('.menu-button'),menu=document.querySelector('.menu-links');button.addEventListener('click',()=>{{const open=menu.classList.toggle('is-open');button.setAttribute('aria-expanded',String(open))}});</script></main></body></html>'''


def build(root: Path, repo_root: Path) -> dict[str, Any]:
    data = load_dataset(root)
    charts = {"score": score_svg(data), "tradeoff": tradeoff_svg(data), "latency": latency_svg(data), "heatmap": heatmap_svg(data)}
    dataset_fields = sorted({key for model in data["models"] for key in model})
    dataset_csv = []
    dataset_csv.append(",".join(dataset_fields))
    for model in data["models"]:
        dataset_csv.append(",".join('"' + str(model.get(field, "")).replace('"', '""') + '"' for field in dataset_fields))
    outputs = {
        "assistant-benchmark.json": json.dumps(data, indent=2) + "\n",
        "assistant-benchmark-score.svg": charts["score"],
        "assistant-benchmark-speed-quality.svg": charts["tradeoff"],
        "assistant-benchmark-latency.svg": charts["latency"],
        "assistant-benchmark-categories.svg": charts["heatmap"],
        "assistant-model-results.csv": "\n".join(dataset_csv) + "\n",
    }
    for directory in (root, repo_root):
        for name, content in outputs.items():
            (directory / name).write_text(content, encoding="utf-8")
    cohort_text = f'{data["model_count"]} models across local and OpenRouter cohorts'
    root_dashboard = dashboard_html(data, charts, "", "../model-comparisons/model-comparison.html", "../../index.html", "../../methodology.html")
    repo_dashboard = dashboard_html(data, charts, "docs/assistant-benchmark/", "index.html", "index.html", "methodology.html")
    root_dashboard = root_dashboard.replace('href="model-results.csv"', 'href="assistant-model-results.csv"')
    repo_dashboard = repo_dashboard.replace('href="docs/assistant-benchmark/model-results.csv"', 'href="docs/assistant-benchmark/assistant-model-results.csv"')
    root_dashboard = root_dashboard.replace("Nine local GGUF models", cohort_text)
    repo_dashboard = repo_dashboard.replace("Nine local GGUF models", cohort_text)
    methodology = methodology_html(data).replace(f'{data["model_count"]} local GGUF models served through llama.cpp via llama-swap', cohort_text)
    (root / "assistant-benchmark.html").write_text(root_dashboard, encoding="utf-8")
    (repo_root / "assistant-benchmark.html").write_text(repo_dashboard, encoding="utf-8")
    (repo_root / "methodology.html").write_text(methodology, encoding="utf-8")
    return data


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    result = build(here, here.parents[1])
    print(f"Built assistant benchmark for {result['model_count']} models")
