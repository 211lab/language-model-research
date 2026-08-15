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
    "unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl": "Unsloth Qwen 3.8 27B",
}
LOCAL_PROVIDERS = {
    "gemma-4-12b-obliterated": "Google local",
    "gemma-4-e4b-it": "Google local",
    "qwen3.6-27b-heretic-neo-code": "Qwen fine-tunes",
    "qwen3.6-35b-hauhaucs-aggressive": "Qwen fine-tunes",
    "unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-ud-q4-k-xl": "Unsloth",
    "unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl": "Unsloth",
    "unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s": "Unsloth",
    "unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl": "Unsloth",
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
    width, left, top, plot_width, row_height = 1240, 360, 128, 790, 55
    height = top + max(1, len(models)) * row_height + 48
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
        attr = model_attr(model) + f' data-row="{index}"'
        body.append(f'<text class="label"{attr} x="{left-16}" y="{y+18}" text-anchor="end">{esc(plot_name(model))}</text>')
        cursor = left
        for key, _label, weight, color in DIMENSIONS:
            contribution = model[key] * weight / 100
            segment = plot_width * contribution / 100
            body.append(f'<rect{attr} x="{cursor:.2f}" y="{y}" width="{segment:.2f}" height="26" fill="{color}"/>')
            cursor += segment
        body.append(f'<text class="value"{attr} x="{cursor+9:.1f}" y="{y+19}">{model["assistant_score"]:.1f}</text>')
    return svg_shell("Personal-assistant intelligence", "Weighted score; higher is better. Timing is excluded from this score.", width, height, body).replace("<svg ", '<svg id="assistant-score" ', 1)


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
    width, left, top, cell_w, cell_h = 1240, 355, 125, 112, 55
    height = top + max(1, len(models)) * cell_h + 48
    body: list[str] = []
    for col, (_key, label, _weight, _color) in enumerate(DIMENSIONS):
        body.append(f'<text class="tick" x="{left+col*cell_w+cell_w/2}" y="{top-18}" text-anchor="middle">{esc(label)}</text>')
    for row, model in enumerate(models):
        yy = top + row * cell_h
        attr = model_attr(model) + f' data-row="{row}"'
        body.append(f'<text class="label"{attr} x="{left-16}" y="{yy+31}" text-anchor="end">{esc(plot_name(model))}</text>')
        for col, (key, _label, _weight, _color) in enumerate(DIMENSIONS):
            value = model[key]
            hue = 120 * value / 100
            body += [f'<rect{attr} x="{left+col*cell_w}" y="{yy}" width="{cell_w-4}" height="40" rx="4" fill="hsl({hue:.1f} 64% 38%)"/>', f'<text class="value"{attr} x="{left+col*cell_w+(cell_w-4)/2:.1f}" y="{yy+26}" text-anchor="middle">{value:.1f}</text>']
    return svg_shell("Assistant capability heatmap", "Hard 0–100 category scores; green is higher and red is lower.", width, height, body).replace("<svg ", '<svg id="assistant-heatmap" ', 1)


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
<p class="muted">Source: <a href="{source_prefix}model-results.csv">model-results.csv</a>. Method and caveats: <a href="{methodology_href}">published methodology</a> and <a href="{source_prefix}README.md">benchmark notes</a>.</p><script>const controls=[...document.querySelectorAll('[data-model-control]')];function resizeRowCharts(){{const selected=controls.filter(control=>control.checked).map(control=>control.dataset.modelControl);const count=Math.max(1,selected.length);[['assistant-score',128,55,48],['assistant-heatmap',125,55,48]].forEach(([id,top,rowHeight,bottom])=>{{const svg=document.getElementById(id);if(!svg)return;const rows=[...svg.querySelectorAll('[data-row]')];const originalRows=new Map();rows.forEach(item=>{{const model=item.dataset.model;if(!originalRows.has(model))originalRows.set(model,Number(item.dataset.row))}});const visible=selected.filter(model=>originalRows.has(model)).sort((a,b)=>originalRows.get(a)-originalRows.get(b));visible.forEach((model,index)=>{{const shift=(index-originalRows.get(model))*rowHeight;svg.querySelectorAll('[data-model="'+model+'"]').forEach(item=>item.setAttribute('transform','translate(0 '+shift+')'))}});const height=top+count*rowHeight+bottom;svg.setAttribute('viewBox','0 0 1240 '+height);svg.setAttribute('height',height)}})}}function applySelection(){{controls.forEach(control=>document.querySelectorAll('[data-model="'+control.dataset.modelControl+'"]').forEach(item=>item.style.display=control.checked?'':'none'));document.querySelectorAll('[data-provider]').forEach(provider=>{{const related=controls.filter(control=>control.dataset.providerName===provider.dataset.provider);provider.checked=related.every(control=>control.checked);provider.indeterminate=related.some(control=>control.checked)&&!provider.checked}});resizeRowCharts()}}controls.forEach(control=>control.addEventListener('change',applySelection));document.querySelectorAll('[data-provider]').forEach(provider=>provider.addEventListener('change',()=>{{controls.filter(control=>control.dataset.providerName===provider.dataset.provider).forEach(control=>control.checked=provider.checked);applySelection()}}));document.querySelectorAll('[data-selection]').forEach(button=>button.addEventListener('click',()=>{{controls.forEach(control=>control.checked=button.dataset.selection==='all');applySelection()}}));const menuButton=document.querySelector('.menu-button'),menu=document.querySelector('.menu-links');menuButton.addEventListener('click',()=>{{const open=menu.classList.toggle('is-open');menuButton.setAttribute('aria-expanded',String(open))}});applySelection();</script></main></body></html>'''


def legacy_methodology_html(data: dict[str, Any]) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research methodology</title><style>
body{{margin:0;background:#070b16;color:#e5e7eb;font:16px/1.55 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:28px}}a{{color:#7dd3fc}}h1{{margin-bottom:6px}}h2{{margin-top:36px}}.muted{{color:#a5b4c7}}.site-nav{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}}.site-brand{{color:#f8fafc;text-decoration:none;font-weight:750}}.menu-button{{margin-left:auto;border:1px solid #38506f;background:#111a2d;color:#e5e7eb;border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}}.menu-links{{display:flex;gap:14px;align-items:center}}.menu-links a{{text-decoration:none}}.card{{background:#0d1424;border:1px solid #263349;border-radius:12px;padding:18px;margin:16px 0}}li{{margin:7px 0}}@media(max-width:680px){{main{{padding:18px}}.site-nav{{position:relative}}.menu-links{{display:none;position:absolute;right:0;top:42px;z-index:10;min-width:230px;flex-direction:column;align-items:stretch;padding:12px;border:1px solid #263349;border-radius:10px;background:#111a2d;box-shadow:0 12px 28px #0008}}.menu-links.is-open{{display:flex}}.menu-links a{{padding:7px}}}}@media(min-width:681px){{.menu-button{{display:none}}}}
</style></head><body><main><nav class="site-nav" aria-label="Primary"><a class="site-brand" href="index.html">Language model research</a><button class="menu-button" type="button" aria-expanded="false" aria-controls="site-menu">Menu ☰</button><div class="menu-links" id="site-menu"><a href="index.html">Editorial research</a><a href="assistant-benchmark.html">Assistant benchmark</a><a href="methodology.html">Methodology</a></div></nav><h1>Research methodology</h1><p class="muted">A transparent record of what these comparisons measure, what they do not, and how to reproduce the inputs.</p>
<section class="card"><h2>Personal-assistant benchmark</h2><p>The assistant evaluation uses {data["model_count"]} local GGUF models served through llama.cpp via llama-swap. Each model receives the same 21 fresh synthetic fixtures covering project work, information retrieval, structured tool calls, state tracking, English communication, and safe handling of requests.</p><ul><li>Temperature 0, seed 42, with up to 768 tokens per turn.</li><li>Only one model is loaded and one request is active at a time. The model is unloaded and a 10-second buffer elapses before the next model.</li><li>Intelligence is a weighted 0–100 score: outcome 30%, tool use 25%, grounding 15%, state 10%, English 10%, safety 5%, efficiency 5%.</li><li>Latency is reported separately: cold load plus first response, warm OpenClaw-style request, and their total. It is never folded into the intelligence score.</li><li>A <code>partial</code> result means a tool-turn ceiling or API error affected the run. Its scheduled tasks remain in the report; it is not comparable to a clean <code>ok</code> run without that caveat.</li></ul><p>Exact scores, timings, run status, and source fixtures are retained in the <a href="docs/assistant-benchmark/model-results.csv">published dataset</a> and <a href="docs/assistant-benchmark/README.md">benchmark notes</a>.</p></section>
<section class="card"><h2>Editorial content research</h2><p>The editorial comparison uses the published case-study output for each model, a fixed rubric, readability measurements, and recorded OpenRouter bundle prices when available. The dashboard keeps quality, readability, and price as separate fields so a lower cost is not mistaken for higher quality.</p><ul><li>Content scores are rubric-based rather than a general intelligence claim.</li><li>Charts retain hard values and report unavailable prices explicitly.</li><li>The local model is shown as a zero-cost baseline only for the recorded bundle comparison; hardware and electricity costs are outside that axis.</li></ul><p>Detailed rubric definitions, source artifacts, and per-model evidence live with the <a href="docs/model-comparisons/README.md">model-comparison research</a>.</p></section>
<section class="card"><h2>Judge change: DeepSeek to Luna</h2><p>The rubric, deterministic measurements, evidence verification, three-pass median, and tie-break rule stayed the same. The local editorial cross-run used GPT-5.6 Luna for evidence extraction, judging, and tie-breaking, so this is an evaluator-stack change rather than an isolated final-judge change.</p><ul><li>The current records contain 8 complete Luna-scored local source snapshots.</li><li>They contain 2 complete DeepSeek-backed source snapshots, plus one incomplete earlier DeepSeek attempt.</li><li>No complete immutable content snapshot is currently scored by both DeepSeek and Luna, so a score difference cannot be attributed to Luna alone.</li></ul><p>The <a href="docs/model-comparisons/judge-comparison.md">judge comparison note</a> includes the exact coverage, the same-task assistant comparison, and the paired protocol required before claiming judge impact.</p></section>
<h2>Interpretation limits</h2><p>These results are directional evidence for the stated workflows and runtime. They do not establish broad model capability, reliability across unseen data, provider service quality, or cost on another machine. Model versions, quantization, hardware, prompts, and tool schemas can materially change outcomes.</p><script>const button=document.querySelector('.menu-button'),menu=document.querySelector('.menu-links');button.addEventListener('click',()=>{{const open=menu.classList.toggle('is-open');button.setAttribute('aria-expanded',String(open))}});</script></main></body></html>'''


def compact_methodology_html(data: dict[str, Any]) -> str:
    local_count = data["cohort_counts"]["local"]
    openrouter_count = data["cohort_counts"]["openrouter"]
    partial_count = sum(model["run_status"] == "partial" for model in data["models"])
    ok_count = sum(model["run_status"] == "ok" for model in data["models"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research methodology</title><style>
body{{margin:0;background:#070b16;color:#e5e7eb;font:16px/1.55 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:28px}}a{{color:#7dd3fc}}h1{{margin-bottom:6px}}h2{{margin-top:36px}}.muted{{color:#a5b4c7}}.site-nav{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}}.site-brand{{color:#f8fafc;text-decoration:none;font-weight:750}}.menu-button{{margin-left:auto;border:1px solid #38506f;background:#111a2d;color:#e5e7eb;border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}}.menu-links{{display:flex;gap:14px;align-items:center}}.menu-links a{{text-decoration:none}}.card{{background:#0d1424;border:1px solid #263349;border-radius:12px;padding:18px;margin:16px 0}}li{{margin:7px 0}}@media(max-width:680px){{main{{padding:18px}}.site-nav{{position:relative}}.menu-links{{display:none;position:absolute;right:0;top:42px;z-index:10;min-width:230px;flex-direction:column;align-items:stretch;padding:12px;border:1px solid #263349;border-radius:10px;background:#111a2d;box-shadow:0 12px 28px #0008}}.menu-links.is-open{{display:flex}}.menu-links a{{padding:7px}}}}@media(min-width:681px){{.menu-button{{display:none}}}}
</style></head><body><main><nav class="site-nav" aria-label="Primary"><a class="site-brand" href="index.html">Language model research</a><button class="menu-button" type="button" aria-expanded="false" aria-controls="site-menu">Menu</button><div class="menu-links" id="site-menu"><a href="index.html">Editorial research</a><a href="assistant-benchmark.html">Assistant benchmark</a><a href="methodology.html">Methodology</a></div></nav><h1>Research methodology</h1><p class="muted">This page states what we tested, how we scored it, and what the results cannot prove.</p>
<section class="card"><h2>Two test tracks</h2><p>This project has two tracks. Each track has its own tasks and score. Do not add the scores.</p><ul><li><strong>Assistant:</strong> {data["model_count"]} records: {local_count} local and {openrouter_count} OpenRouter.</li><li><strong>Editorial:</strong> content bundles scored for quality, reading level, and cost.</li></ul></section>
<section class="card"><h2>Assistant test</h2><p>The fixed suite is labeled {data["run_date"]}. The current data combines a local round and a later OpenRouter extension. Each model ran the same {data["task_count_per_model"]} tasks. The tasks cover work, research, tools, state, English, and safety.</p><ul><li>Temperature: {data["temperature"]}.</li><li>Seed: {data["seed"]}.</li><li>Limit: {data["max_tokens_per_turn"]} tokens per turn.</li><li>Each task used a new fixture and chat.</li><li>We ran one model and one request at a time. We unloaded each local model, then waited 10 seconds before the next one.</li><li>Score weights: outcome 30%, tool use 25%, grounding 15%, state 10%, English 10%, safety 5%, efficiency 5%.</li></ul><p>There are {ok_count} <code>ok</code> records and {partial_count} <code>partial</code> records. A partial run had a tool-loop limit or an API error. The report still keeps its task slots. Use it to study failure risk. Do not treat it as a clean run.</p><p>Latency is a second measure. It does not change the score. The report shows cold load, first response, warm OpenClaw-style request, and total time when that data exists.</p><p>Sources: <a href="docs/assistant-benchmark/assistant-benchmark.json">JSON</a>, <a href="docs/assistant-benchmark/assistant-model-results.csv">CSV</a>, and <a href="docs/assistant-benchmark/README.md">notes</a>. Fixture hash: <code>{data["fixture_sha256"]}</code>. Task hash: <code>{data["tasks_sha256"]}</code>.</p></section>
<section class="card"><h2>Editorial test</h2><p>This test measures SteadyBurn content. It does not measure assistant work. Each case study stores the model output, rubric score, reading measures, and cost.</p><ul><li>The scorer checks <code>index.md</code> and <code>INSTRUCTIONS.md</code>.</li><li>The rubric is versioned and fixed for this round.</li><li>Rule-based measures and model scores stay in separate fields.</li><li>Radar charts use rank values so unlike units can share one scale. The tables keep the raw values.</li><li>OpenRouter cost comes from provider usage records when they exist.</li><li>Local runs show $0 in the chart. This is a chart marker. It does not include hardware, power, or other local costs.</li></ul><p>Sources: <a href="docs/model-comparisons/model-comparison.json">comparison JSON</a> and <a href="docs/model-comparisons/readability-report.json">reading report</a>.</p></section>
<section class="card"><h2>DeepSeek and Luna</h2><p>The local editorial round used GPT-5.6 Luna to find evidence, score the files, and break ties. Older rows used DeepSeek, GPT-5.4-mini, or both. More than the final judge changed.</p><ul><li>No saved content has a complete score from both DeepSeek and Luna.</li><li>We cannot call the score gap Luna's effect.</li><li>A fair test saves one output and scores it twice with the same rubric.</li></ul><p>See the <a href="docs/model-comparisons/judge-comparison.md">DeepSeek and Luna note</a> for the evidence and test plan.</p></section>
<h2>Limits</h2><p>These results apply to the listed tasks, prompts, models, hardware, and provider runs. They do not prove general intelligence, all-purpose reliability, or future price. New models, settings, tools, or machines can change the result.</p><script>const button=document.querySelector('.menu-button'),menu=document.querySelector('.menu-links');button.addEventListener('click',()=>{{const open=menu.classList.toggle('is-open');button.setAttribute('aria-expanded',String(open))}});</script></main></body></html>'''


def methodology_html(data: dict[str, Any]) -> str:
    local_count = data["cohort_counts"]["local"]
    openrouter_count = data["cohort_counts"]["openrouter"]
    partial_count = sum(model["run_status"] == "partial" for model in data["models"])
    ok_count = sum(model["run_status"] == "ok" for model in data["models"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research methodology</title><style>
body{{margin:0;background:#070b16;color:#e5e7eb;font:16px/1.55 system-ui,sans-serif}}main{{max-width:960px;margin:auto;padding:28px}}a{{color:#7dd3fc}}h1{{margin-bottom:6px}}h2{{margin-top:36px}}h3{{margin:22px 0 8px}}.muted{{color:#a5b4c7}}.site-nav{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}}.site-brand{{color:#f8fafc;text-decoration:none;font-weight:750}}.menu-button{{margin-left:auto;border:1px solid #38506f;background:#111a2d;color:#e5e7eb;border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}}.menu-links{{display:flex;gap:14px;align-items:center}}.menu-links a{{text-decoration:none}}.card{{background:#0d1424;border:1px solid #263349;border-radius:12px;padding:18px;margin:16px 0}}li{{margin:8px 0}}dt{{font-weight:700;margin-top:12px}}dd{{margin:2px 0 10px}}code{{overflow-wrap:anywhere}}@media(max-width:680px){{main{{padding:18px}}.site-nav{{position:relative}}.menu-links{{display:none;position:absolute;right:0;top:42px;z-index:10;min-width:230px;flex-direction:column;align-items:stretch;padding:12px;border:1px solid #263349;border-radius:10px;background:#111a2d;box-shadow:0 12px 28px #0008}}.menu-links.is-open{{display:flex}}.menu-links a{{padding:7px}}}}@media(min-width:681px){{.menu-button{{display:none}}}}
</style></head><body><main><nav class="site-nav" aria-label="Primary"><a class="site-brand" href="index.html">Language model research</a><button class="menu-button" type="button" aria-expanded="false" aria-controls="site-menu">Menu</button><div class="menu-links" id="site-menu"><a href="index.html">Editorial research</a><a href="assistant-benchmark.html">Assistant benchmark</a><a href="methodology.html">Methodology</a></div></nav><h1>Research methodology</h1><p class="muted">This page explains the test inputs, every reported measure, and how to use the results when cost and usable capacity must be weighed together.</p>
<section class="card"><h2>What this research is for</h2><p>The goal is a specific, repeatable comparison. It does not ask which model is best at everything. It asks what a model can do for the same real work, and what that work costs. A frontier model, a third-party API model, and a self-hosted model can then be compared on the same job.</p><p>Objective measurements matter because model names, parameter counts, and price cards do not tell us whether a model completes the work. The same seed, prompts, fixtures, files, rubric, and calculation rules give an apples-to-apples starting point. Human judgment still exists in the rubric, so the page also names the evaluator limits.</p><p>Use the results to choose the lowest-cost model that meets the needed standard for a named use case. Do not use a high score as proof that a model is safe, current, or right for every job.</p></section>
<section class="card"><h2>Two separate test tracks</h2><p>This project has two tracks. They answer different questions, so their scores must not be added or treated as one ranking.</p><ul><li><strong>Assistant track:</strong> {data["model_count"]} records: {local_count} self-hosted local models and {openrouter_count} OpenRouter models. It tests tool-using assistant work.</li><li><strong>Editorial track:</strong> one SteadyBurn weekly content bundle per model. It tests the quality, reading level, and recorded cost of that bundle.</li></ul><p>A model may be strong at one track and weak at the other. That is useful information, not a conflict.</p></section>
<section class="card"><h2>Assistant test: same work, fixed conditions</h2><p>The fixed suite is labeled {data["run_date"]}. The current data combines a local round and a later OpenRouter extension. Every model received the same {data["task_count_per_model"]} tasks: project work, research, structured tool calls, state tracking, English communication, and safe handling of requests.</p><ul><li><strong>Temperature {data["temperature"]}:</strong> removes random sampling as much as the provider allows. This makes a result easier to repeat.</li><li><strong>Seed {data["seed"]}:</strong> fixes the test starting point. It helps make task conditions equal.</li><li><strong>{data["max_tokens_per_turn"]}-token cap:</strong> gives each model the same maximum reply budget. This prevents a model from winning only by writing much more.</li><li><strong>Fresh fixture and chat:</strong> each task begins with new task data and no earlier conversation. This prevents hidden memory from helping a later task.</li><li><strong>One request at a time:</strong> local models are unloaded, then the runner waits 10 seconds before the next model. This reduces cross-model server state and load effects.</li></ul><h3>Assistant score dimensions</h3><p>The weighted assistant score is a 0–100 summary. The weights show which kinds of failure matter most for this use case. A high score is more valuable than a low price only when the model can do the parts of the job you need.</p><dl><dt>Outcome — 30%</dt><dd>Whether the task reaches the requested result. It matters most because an inexpensive answer has little value if the work is not finished.</dd><dt>Tool use — 25%</dt><dd>Whether the model calls the right tool with usable inputs and uses the result. It matters when the assistant must act on calendars, files, data, or other systems.</dd><dt>Grounding — 15%</dt><dd>Whether the answer stays tied to the supplied facts and tool results. It matters because unsupported claims can create costly follow-up work.</dd><dt>State — 10%</dt><dd>Whether the model keeps track of task facts across turns. It matters for multi-step work where lost details cause rework.</dd><dt>English — 10%</dt><dd>Whether the answer is clear, direct, and usable in English. It matters because a correct plan must still be understood and acted on.</dd><dt>Safety — 5%</dt><dd>Whether the model handles risky or disallowed requests safely. It matters because a low-cost model can have a high operational cost if it creates unsafe output.</dd><dt>Efficiency — 5%</dt><dd>Whether the model completes work without wasteful extra turns. It matters because extra turns add time, cost, and failure chances.</dd></dl><h3>Assistant data fields</h3><dl><dt>Tasks passed and task pass rate</dt><dd>The number and share of the 21 tasks that passed. This is the clearest view of how often the stated workflow worked.</dd><dt>Tool-call success rate</dt><dd>The share of detected tool calls that succeeded. It helps separate good writing from reliable tool execution.</dd><dt>Run status</dt><dd><code>ok</code> means the run completed cleanly. <code>partial</code> means a tool-loop limit or API error affected it. There are {ok_count} <code>ok</code> records and {partial_count} <code>partial</code> records. Partial rows retain their scheduled task slots so failure risk stays visible; do not read them as clean runs.</dd><dt>Cold load, first response, warm request, and total time</dt><dd>Cold load is startup time. First response is time to the first token after a cold start. The warm OpenClaw-style request measures a later request after the model is ready. Total time combines the recorded parts. These are speed and capacity-planning measures, not quality points. Self-hosted inference is expected to be slower in this environment.</dd></dl><p>Sources: <a href="docs/assistant-benchmark/assistant-benchmark.json">JSON</a>, <a href="docs/assistant-benchmark/assistant-model-results.csv">CSV</a>, and <a href="docs/assistant-benchmark/README.md">notes</a>. Fixture hash: <code>{data["fixture_sha256"]}</code>. Task hash: <code>{data["tasks_sha256"]}</code>.</p></section>
<section class="card"><h2>Editorial test: one weekly content bundle</h2><p>Each model receives the same SteadyBurn weekly-content job, pipeline structure, seed, and optional-track settings. A bundle is broader than one article. It shows whether a model can make connected pieces that are useful together.</p><dl><dt>Context</dt><dd>The brief with the audience, topic, and constraints. It sets the same starting facts for each model.</dd><dt>Lesson</dt><dd>The teaching piece. It tests whether the model can explain the central idea.</dd><dt>Long-form letter (<code>index.md</code>)</dt><dd>The main reader-facing letter. It is scored for argument, grounding, action, reading control, and closing voice.</dd><dt>Instructions (<code>INSTRUCTIONS.md</code>)</dt><dd>The practical guide that turns the idea into steps. It is scored for argument, framework, reading control, and voice.</dd><dt>Worksheet copy, worksheet, and masked worksheet</dt><dd>Working prompts and their usable forms. They show whether the idea can become an action tool, including a version that hides answers or guidance when needed.</dd><dt>Newsletter email and community post</dt><dd>Short distribution pieces that bring the weekly idea to readers in different channels.</dd><dt>Cover prompt and rendered hero image</dt><dd>The visual brief and its output. They test whether the model can direct a useful, on-brand visual asset.</dd><dt>Pipeline configuration</dt><dd>The recorded run settings. It makes the case study traceable and helps explain differences.</dd><dt>OpenRouter usage record</dt><dd>For paid-provider runs, the provider-reported token usage and charge record. This is the source for recorded bundle cost.</dd></dl><p>The content-quality scorer directly evaluates only <code>index.md</code> and <code>INSTRUCTIONS.md</code>. Readability is calculated for <code>LESSON.md</code>, <code>index.md</code>, <code>INSTRUCTIONS.md</code>, and the combined text. Other bundle pieces are retained as evidence and for practical review; they are not silently turned into rubric points.</p></section>
<section class="card"><h2>Editorial quality rubric</h2><p>The rubric is versioned as SteadyBurn v1. It keeps rule-based measurements and model-based scores in separate fields. A required criterion can lower the result when it is missed. Category weights show the parts of quality that have more influence on each artifact score.</p><h3>Letter categories</h3><dl><dt>Argument — 40%</dt><dd>The letter has a clear idea that develops. It matters because the main piece must give the reader a reason to change or decide.</dd><dt>Grounding — 15%</dt><dd>The letter uses real, concrete life details. It matters because abstract advice is hard to trust or use.</dd><dt>Action — 15%</dt><dd>The letter leads to a real choice or next step. It matters because content capacity includes helping a reader do something.</dd><dt>Readability — 15%</dt><dd>The letter stays clear without becoming empty. It matters because a strong idea fails if the target reader cannot follow it.</dd><dt>Closure — 15%</dt><dd>The ending and tone stay firm without sounding like a guru, preacher, therapist, or hype message. It matters because voice affects trust and brand fit.</dd></dl><h3>Instruction categories</h3><dl><dt>Argument — 40%</dt><dd>The guide explains why the work matters. It stops steps from becoming empty commands.</dd><dt>Framework — 30%</dt><dd>The guide makes the named method usable. It matters because the reader needs a repeatable process, not only good prose.</dd><dt>Readability — 15%</dt><dd>The guide is easy to scan and follow. It matters because instructions must work during action.</dd><dt>Voice — 15%</dt><dd>The guide stays direct without hype, therapy language, preaching, or guru language. It matters because trust is part of usefulness.</dd></dl><h3>Every scored criterion</h3><p>The items below define the hard values in the quality-standards table and radar. A shared item is checked in both scored files unless the text says otherwise.</p><dl><dt>Perspective shift</dt><dd>The piece helps the reader see the problem in a new way. This matters when paying more for insight instead of familiar advice.</dd><dt>Argument progression</dt><dd>The reasoning moves in a clear order. This matters because a reader can follow and test the claim.</dd><dt>Concrete opening — letter only</dt><dd>The letter begins with a real situation or detail. This matters because it makes the subject immediate and believable.</dd><dt>Psychological interpretation</dt><dd>The piece explains the thought, habit, or pressure behind the problem. This matters because useful change needs more than surface tips.</dd><dt>Behavioral grounding</dt><dd>The claims connect to actions people can observe. This matters because it makes advice testable in daily life.</dd><dt>Practical philosophy</dt><dd>The piece turns a bigger idea into a useful rule. This matters because capacity includes sound judgment, not only instructions.</dd><dt>Intellectual depth</dt><dd>The piece goes beyond a simple slogan. This matters because premium model cost should buy more than polished filler.</dd><dt>Qualification and nuance — letter only</dt><dd>The letter states limits or exceptions where needed. This matters because overconfident writing can mislead readers.</dd><dt>Personal responsibility</dt><dd>The reader has a clear part to play. This matters because the content should support agency, not passive consumption.</dd><dt>Perspective progression — letter only</dt><dd>The letter carries the reader from the old view to the new view. This matters because a strong ending depends on a complete change path.</dd><dt>Decision — letter only</dt><dd>The letter names the choice the reader should make. This matters because vague inspiration is hard to act on.</dd><dt>Prescribed action — letter only</dt><dd>The letter gives a specific next action. This matters because a content bundle must lead to use, not only reflection.</dd><dt>Concrete and abstract balance — letter only</dt><dd>The letter balances examples with ideas. This matters because either extreme can make a piece shallow or unclear.</dd><dt>Everyday realism — letter only</dt><dd>The advice fits normal time, limits, and pressures. This matters because impractical advice creates no real capacity.</dd><dt>Intellectual simplicity control</dt><dd>The language is simple without making the idea childish. This matters because readers need clear, credible writing.</dd><dt>Sentence rhythm</dt><dd>Sentence length and shape vary in a useful way. This matters because readable pacing keeps a long piece usable.</dd><dt>Semantic economy</dt><dd>Each sentence does useful work with few wasted words. This matters because concise output lowers edit time and delivery cost.</dd><dt>Anti-motivational tone</dt><dd>The piece avoids empty cheering or pressure. This matters because hype can damage trust.</dd><dt>Anti-therapy tone</dt><dd>The piece avoids acting like treatment or diagnosis. This matters because content should stay in its intended role.</dd><dt>Anti-preacher tone</dt><dd>The piece avoids moralizing at the reader. This matters because readers need respect, not a lecture.</dd><dt>Anti-guru tone</dt><dd>The piece avoids false certainty or special-authority claims. This matters because reliable content shows limits.</dd><dt>Closing strength — letter only</dt><dd>The ending lands the idea with force and clarity. This matters because the final message shapes recall and action.</dd><dt>Model or framework lands — instructions only</dt><dd>The named method is explained well enough to use. This matters because the guide must deliver the promised framework.</dd><dt>Unique letter-specific action — instructions only</dt><dd>The guide gives an action that fits this letter, not a generic productivity step. This matters because specificity shows real understanding.</dd><dt>Argument to framework to action — instructions only</dt><dd>The guide connects the reason, the method, and the next step. This matters because a reader needs a complete path from insight to use.</dd></dl></section>
<section class="card"><h2>Readability and text measurements</h2><p>Markdown presentation syntax is removed first. One deterministic English syllable rule is then applied to every model output. These numbers describe the text; they do not decide whether the advice is true or good. They show likely reader effort and editing effort, which both affect the real cost of a model choice.</p><dl><dt>Characters</dt><dd>The count of letters and numbers in the normalized text. It shows total text size and helps explain processing or editing volume.</dd><dt>Letters</dt><dd>Alphabetic characters. It is an input for some reading formulas and helps compare writing density.</dd><dt>Words</dt><dd>Detected English word forms. It shows length and is a basic editing-work measure.</dd><dt>Sentences</dt><dd>Detected sentences. It helps show how the model breaks ideas into units a reader can follow.</dd><dt>Paragraphs</dt><dd>Detected blocks of text. It helps show page structure and scanability.</dd><dt>Syllables</dt><dd>Estimated spoken parts of words. More syllables often mean harder words and more reading effort.</dd><dt>Polysyllables</dt><dd>Words with three or more syllables. It is a direct signal used by some grade-level formulas.</dd><dt>Long words</dt><dd>Words with seven or more letters. It is a simple sign of dense language that may need editing.</dd><dt>Long sentences</dt><dd>Sentences with 20 or more words. It shows where readers may need to hold too much in mind.</dd><dt>Average words per sentence</dt><dd>Words divided by sentences. Higher values often raise reading effort, so it helps compare pacing.</dd><dt>Average syllables per word</dt><dd>Syllables divided by words. Higher values often mean more complex vocabulary.</dd><dt>Average characters per word</dt><dd>Letters divided by words. It is another simple view of word length and density.</dd><dt>Flesch reading ease</dt><dd>A 0–100 style formula based on sentence and word length; higher is easier. It gives a quick direction for general ease.</dd><dt>Flesch-Kincaid grade</dt><dd>An estimated U.S. school grade needed to read the text; lower is easier. Grade 6 is a reference target, not a pass rule.</dd><dt>Gunning fog</dt><dd>An estimated school grade based on sentence length and complex words; lower is easier. It checks whether long words are making prose heavy.</dd><dt>Coleman-Liau</dt><dd>An estimated school grade based on letters and sentences; lower is easier. It gives a second view that does not use syllable estimates.</dd><dt>Automated readability index</dt><dd>An estimated school grade based on letters and words; lower is easier. It helps catch dense writing with long words.</dd><dt>SMOG</dt><dd>An estimated school grade based mainly on polysyllables; lower is easier. It highlights complex vocabulary.</dd><dt>Lexical diversity</dt><dd>The share of distinct words. It shows word variety, but very high variety is not always better if it makes text needlessly hard.</dd></dl><p>The readability radar converts each raw measure to a within-measure rank so unlike units can share one shape. It is for quick comparison only. Use the raw tables and <a href="docs/model-comparisons/readability-report.json">reading report</a> for decisions.</p></section>
<section class="card"><h2>Cost, capacity, and chart rules</h2><p>Cost is the recorded price of one completed editorial bundle when provider usage records exist. It is not a price-per-token estimate and it is not a full business cost. Capacity means the measured ability to complete this specific work at the needed quality and reliability.</p><dl><dt>Frontier and paid third-party models</dt><dd>These models may offer high measured quality or speed, but their recorded provider charge can be higher. The value question is whether better output saves enough editing, review, or failure cost to justify that charge.</dd><dt>Self-hosted local models</dt><dd>These models run on the research machine. The editorial chart marks them as $0 direct provider cost because no paid API bill is recorded. That is not a claim that local inference is free: hardware, power, setup, maintenance, and slower local time are outside this field.</dd><dt>Cost burden</dt><dd>The radar reverses recorded cost into a rank where lower cost gives a better value. It is a visual aid, not a quality score. A cheap model with weak quality is not automatically the better choice.</dd><dt>Quality-and-cost frontier</dt><dd>The decision chart highlights observed models that offer the best known quality for a cost level in this sample. A point near the frontier is a candidate for the use case; it is not a universal winner.</dd><dt>Missing cost or score</dt><dd>Missing data stays missing. A model without <code>CONTENT_SCORE.json</code> is marked as awaiting quality scoring. It keeps readability and cost values where available, but the report does not invent an editorial score.</dd><dt>Radar rank and raw table value</dt><dd>Radar shapes use normalized ranks so measures with different units can be displayed together. Tables keep the actual score, seconds, dollars, word counts, and grade estimates. Use tables for a purchasing decision.</dd></dl><p>The editorial sources are the <a href="docs/model-comparisons/model-comparison.json">comparison JSON</a>, <a href="docs/model-comparisons/readability-report.json">readability JSON</a>, and the saved case-study folders. Provider usage records are the source of paid bundle cost.</p></section>
<section class="card"><h2>Judge and evidence limits</h2><p>The local editorial round used GPT-5.6 Luna to find evidence, score the files, and break ties. Older rows used DeepSeek, GPT-5.4-mini, or both. More than the final judge changed between these historical groups.</p><ul><li>No saved content has a complete score from both DeepSeek and Luna.</li><li>We cannot claim that a score difference is Luna’s effect alone.</li><li>A fair judge comparison saves one output and scores it twice with the same rubric.</li></ul><p>See the <a href="docs/model-comparisons/judge-comparison.md">DeepSeek and Luna note</a> for the evidence and paired-test plan.</p></section>
<section class="card"><h2>What the results do and do not prove</h2><p>These results are evidence for the listed prompts, bundle, tasks, model versions, settings, hardware, and provider runs. They do not prove general intelligence, future price, all-purpose reliability, or a model’s value on a different machine. Use them to make a specific model choice, then run a small validation on your own high-risk work before scaling it.</p></section><script>const button=document.querySelector('.menu-button'),menu=document.querySelector('.menu-links');button.addEventListener('click',()=>{{const open=menu.classList.toggle('is-open');button.setAttribute('aria-expanded',String(open))}});</script></main></body></html>'''


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
