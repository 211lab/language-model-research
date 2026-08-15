#!/usr/bin/env python3
"""Compile scored case studies into an interactive quality-and-cost comparison."""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OVERVIEW_AXES = (
    ("argument", "Argument", (("index.md", "argument"), ("INSTRUCTIONS.md", "argument"))),
    ("grounding", "Grounding", (("index.md", "grounding"),)),
    ("action", "Action", (("index.md", "action"),)),
    ("framework", "Framework", (("INSTRUCTIONS.md", "framework"),)),
    ("voice", "Voice & closing", (("index.md", "closure"), ("INSTRUCTIONS.md", "voice"))),
    ("cost_burden", "Cost burden", ()),
)
OVERVIEW_READABILITY_AXES = (
    ("letter_simplicity", "Letter: Simplicity", "index.md", "intellectual_simplicity"),
    ("letter_rhythm", "Letter: Sentence rhythm", "index.md", "sentence_rhythm"),
    ("letter_economy", "Letter: Semantic economy", "index.md", "semantic_economy"),
    ("instructions_simplicity", "Instructions: Simplicity", "INSTRUCTIONS.md", "intellectual_simplicity"),
    ("instructions_rhythm", "Instructions: Sentence rhythm", "INSTRUCTIONS.md", "sentence_rhythm"),
    ("instructions_economy", "Instructions: Semantic economy", "INSTRUCTIONS.md", "semantic_economy"),
)

COLORS = ("#38bdf8", "#f97316", "#a78bfa", "#34d399", "#facc15", "#fb7185", "#22c55e", "#e879f9", "#f43f5e", "#60a5fa", "#f59e0b", "#2dd4bf", "#c084fc")
RADAR_LOG_TICKS = (1, 5, 20, 50, 100)
READABILITY_METRICS = (
    ("characters", "Characters"), ("letters", "Letters"), ("words", "Words"),
    ("sentences", "Sentences"), ("paragraphs", "Paragraphs"), ("syllables", "Syllables"),
    ("polysyllables", "Polysyllables"), ("long_words", "Long words"),
    ("long_sentences", "Long sentences"), ("average_words_per_sentence", "Average words / sentence"),
    ("average_syllables_per_word", "Average syllables / word"),
    ("average_characters_per_word", "Average characters / word"),
    ("flesch_reading_ease", "Flesch reading ease"), ("flesch_kincaid_grade", "Flesch-Kincaid grade"),
    ("gunning_fog", "Gunning fog"), ("coleman_liau", "Coleman-Liau"),
    ("automated_readability_index", "Automated readability index"), ("smog", "SMOG"),
    ("lexical_diversity", "Lexical diversity"),
)

LOCAL_MODEL_IDS = {
    "cydonia-24b-v4.3",
    "dolphin-mistral-24b-venice",
    "empero-ai-qwythos-9b-claude-mythos-5-1m-gguf-qwythos-9b-claude-mythos-5-1m-mtp-q4-k-m",
    "gemma-4-12b-obliterated",
    "gemma-4-e4b-it",
    "qwen3.6-27b-heretic-neo-code",
    "qwen3.6-35b-hauhaucs-aggressive",
    "unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl",
    "unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s",
    "unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl",
}


def radial_fraction(value: float) -> float:
    """Map the user-facing 0–100 metric to a zero-safe logarithmic radius."""
    bounded = min(100.0, max(0.0, float(value)))
    return math.log1p(bounded) / math.log1p(100.0)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def money(value: float | None) -> str:
    return "Unavailable" if value is None else "$" + f"{value:.6f}"


def company_for(model: str) -> str:
    return {
        "anthropic": "Anthropic",
        "deepseek": "DeepSeek",
        "google": "Google",
        "nvidia": "NVIDIA",
        "openai": "OpenAI",
        "qwen": "Qwen",
        "stepfun": "StepFun",
        "tencent": "Tencent",
        "x-ai": "xAI",
    }.get(model.split("/", 1)[0], "Local / other")


def display_name(model: str, case_study: str | None = None, local: bool = False) -> str:
    if model == "unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl":
        return "Local Qwen3.8 27B UD Q4_K_XL"
    name = model.split("/", 1)[-1].replace("-it", "").replace("-", " ").title().replace("Gpt", "GPT")
    return f"Local model ({name})" if local or (case_study and case_study.startswith("local-models/")) else name


def paid_cost(usage_path: Path) -> float | None:
    if not usage_path.exists():
        return None
    total = 0.0
    for line in usage_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        usage = record.get("usage", {})
        if isinstance(usage, dict):
            total += float(usage.get("cost", 0.0) or 0.0)
    return total


def model_from_comparison(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("- model:") or line.lower().startswith("- text model:"):
            return line.split(":", 1)[1].strip().strip("`")
    return path.parent.name


def readability_by_case(root: Path) -> dict[str, dict[str, dict[str, float | None]]]:
    path = root / "readability-report.json"
    if not path.exists():
        return {}
    records = load_json(path).get("records", [])
    output: dict[str, dict[str, dict[str, float | None]]] = defaultdict(dict)
    for record in records:
        if not isinstance(record, dict):
            continue
        case_study, document = record.get("case_study"), record.get("document")
        if not isinstance(case_study, str) or not isinstance(document, str):
            continue
        output[case_study][document] = {metric: record.get(metric) for metric, _label in READABILITY_METRICS}
    return dict(output)


def rubric_category_scores(report: dict[str, Any], rubric: dict[str, Any]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for artifact, artifact_score in report["artifacts"].items():
        rubric_criteria = {item["id"]: item["category"] for item in rubric["artifacts"][artifact]["criteria"]}
        grouped: dict[str, list[float]] = defaultdict(list)
        for criterion in artifact_score["criteria"]:
            category = rubric_criteria.get(criterion["id"])
            if category:
                grouped[category].append(float(criterion["score"]))
        output[artifact] = {category: round(sum(scores) / len(scores), 2) for category, scores in grouped.items()}
    return output


def axis_scores(categories: dict[str, dict[str, float]], criteria: dict[str, dict[str, float]]) -> dict[str, float | None]:
    axes: dict[str, float | None] = {}
    for axis_id, _label, sources in OVERVIEW_AXES:
        if not sources:
            axes[axis_id] = None
            continue
        values = [categories.get(artifact, {}).get(category) for artifact, category in sources]
        present = [value for value in values if value is not None]
        axes[axis_id] = round(sum(present) / len(present), 2) if present else None
    for axis_id, _label, artifact, criterion_id in OVERVIEW_READABILITY_AXES:
        axes[axis_id] = criteria.get(artifact, {}).get(criterion_id)
    return axes


def quality_axes(rubric: dict[str, Any]) -> list[dict[str, str]]:
    axes = []
    for artifact, artifact_rubric in rubric["artifacts"].items():
        artifact_label = "Letter" if artifact == "index.md" else "Instructions"
        for criterion in artifact_rubric["criteria"]:
            axes.append({"id": f"{artifact}:{criterion['id']}", "label": f"{artifact_label}: {criterion['label']}"})
    axes.append({"id": "cost_burden", "label": "Cost burden"})
    return axes


def relative_radar_axes(models: list[dict[str, Any]], mode: str) -> None:
    """Map each axis independently to an ordinal 15–100 comparison scale.

    Raw measurements remain in ``radar_raw``.  The visual scale intentionally
    privileges within-axis ranking over an artificial shared zero point.
    """
    axis_ids = {axis_id for model in models for axis_id in model["radar_raw"][mode]}
    for axis_id in axis_ids:
        values = sorted({float(model["radar_raw"][mode][axis_id]) for model in models if isinstance(model["radar_raw"][mode].get(axis_id), (int, float))})
        positions = {value: index for index, value in enumerate(values)}
        for model in models:
            value = model["radar_raw"][mode].get(axis_id)
            if not isinstance(value, (int, float)):
                model["radar"][mode][axis_id] = None
            elif len(values) == 1:
                model["radar"][mode][axis_id] = 57.5
            else:
                model["radar"][mode][axis_id] = round(15 + 85 * positions[float(value)] / (len(values) - 1), 2)


def compile_comparison(root: Path) -> dict[str, Any]:
    rubric_candidates = (
        root.parent / "content_scoring" / "rubrics" / "steadyburn-v1.json",
        root.parent.parent / "automation" / "content_scoring" / "rubrics" / "steadyburn-v1.json",
    )
    rubric_path = next((path for path in rubric_candidates if path.exists()), None)
    if rubric_path is None:
        raise FileNotFoundError("Could not find steadyburn-v1.json rubric")
    rubric = load_json(rubric_path)
    readability = readability_by_case(root)
    models, awaiting_score = [], []
    for comparison_path in sorted(root.rglob("MODEL_COMPARISON.md")):
        study_root = comparison_path.parent
        case_study = study_root.relative_to(root).as_posix()
        score_path = study_root / "CONTENT_SCORE.json"
        metadata_path = study_root / "MODEL_COMPARISON.json"
        metadata = load_json(metadata_path) if metadata_path.exists() else {}
        report = load_json(score_path) if score_path.exists() else None
        if not score_path.exists():
            awaiting_score.append(case_study)
        model = str(report.get("model", "unknown")) if report else model_from_comparison(comparison_path)
        categories = rubric_category_scores(report, rubric) if report else {}
        criteria = {
            artifact: {item["id"]: float(item["score"]) for item in value["criteria"]}
            for artifact, value in report["artifacts"].items()
        } if report else {}
        usage_path = study_root / "OPENROUTER_USAGE.jsonl"
        provider = str(metadata.get("provider", "")).lower()
        local_baseline = (
            case_study.startswith("local-models/")
            or provider.startswith("local")
            or model in LOCAL_MODEL_IDS
        )
        recorded_cost = paid_cost(usage_path) if usage_path.exists() else None
        models.append({
            "model": model,
            "display_name": display_name(model, case_study, local_baseline),
            "company": "Local" if local_baseline else company_for(model),
            "case_study": case_study,
            "content_score": float(report["content_score"]) if report else None,
            "confidence": float(report["confidence"]) if report else None,
            "cost_usd": 0.0 if local_baseline else recorded_cost,
            "cost_source": "local" if local_baseline else ("openrouter" if recorded_cost is not None else "unavailable"),
            "categories": categories,
            "criteria": criteria,
            "measurements": {artifact: value["metrics"] for artifact, value in report["artifacts"].items()} if report else {},
            "readability": readability.get(case_study, {}),
            "radar_raw": {"overview": axis_scores(categories, criteria), "quality": {}, "readability": {}},
            "radar": {"overview": {}, "quality": {}, "readability": {}},
        })
    maximum_cost = max((float(item["cost_usd"]) for item in models if isinstance(item["cost_usd"], (int, float))), default=0.0)
    for model in models:
        cost_burden = round(100 * float(model["cost_usd"]) / maximum_cost, 2) if maximum_cost and isinstance(model["cost_usd"], (int, float)) else None
        model["radar_raw"]["overview"]["cost_burden"] = cost_burden
        model["radar_raw"]["quality"]["cost_burden"] = cost_burden
        for artifact, criterion_scores in model["criteria"].items():
            model["radar_raw"]["quality"].update({f"{artifact}:{criterion_id}": score for criterion_id, score in criterion_scores.items()})
        model["radar_raw"]["readability"]["cost_burden"] = cost_burden
        model["radar_raw"]["readability"].update(model["readability"].get("bundle total", {}))
    for mode in ("overview", "quality", "readability"):
        relative_radar_axes(models, mode)
    return {
        "schema_version": "model-comparison-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rubric_version": rubric["version"],
        "axis_sets": {
            "overview": ([{"id": axis_id, "label": label} for axis_id, label, _sources in OVERVIEW_AXES if axis_id != "cost_burden"]
                         + [{"id": axis_id, "label": label} for axis_id, label, _artifact, _criterion in OVERVIEW_READABILITY_AXES]),
            "quality": [axis for axis in quality_axes(rubric) if axis["id"] != "cost_burden"],
            "readability": [{"id": metric, "label": label} for metric, label in READABILITY_METRICS],
        },
        "models": sorted(models, key=lambda item: item["display_name"].lower()),
        "awaiting_score": awaiting_score,
    }


def dashboard_html(data: dict[str, Any]) -> str:
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = "SteadyBurn model comparison"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
body{{margin:0;background:#0b1020;color:#e5e7eb;font:16px system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px}}h1{{margin-bottom:6px}}.muted{{color:#a5b4c7}}#controls{{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0}}label{{background:#18243a;border-radius:999px;padding:8px 12px;cursor:pointer}}input{{margin-right:6px}}select{{background:#18243a;color:#e5e7eb;border:1px solid #41506d;border-radius:8px;padding:8px}}svg{{width:100%;max-width:760px;background:#111a2d;border-radius:16px}}.axis{{stroke:#41506d;fill:none}}.label{{fill:#cbd5e1;font-size:12px}}.legend{{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0}}.swatch{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}}table{{width:100%;border-collapse:collapse;margin-top:30px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #24324b}}th{{color:#a5b4c7}}code{{font-size:12px}}.warning{{padding:12px;background:#3a2b12;border-radius:8px}}
</style></head><body><main><h1>{html.escape(title)}</h1><p class="muted">Every axis uses its own ordinal 15–100 rank scale across the compared models, so visual distance means rank within that dimension. Raw quality, readability, and cost values remain in JSON. The radial rendering remains zero-safe logarithmic.</p>
<p><label for="mode">Radar view</label> <select id="mode"><option value="readability">Readability metrics + cost</option><option value="quality">LLM quality standards + cost</option><option value="overview">Grouped overview + cost</option></select></p><div id="controls"></div><div id="legend" class="legend"></div><svg id="radar" viewBox="0 0 760 620" role="img" aria-label="Model quality, readability, and cost radar chart"></svg><div id="table"></div><div id="awaiting"></div>
<script>const comparison={embedded};
const axisSets=comparison.axis_sets, models=comparison.models, selected=new Set(models.map(m=>m.model)); let mode='readability';
const colors={json.dumps(COLORS)}, logTicks={json.dumps(RADAR_LOG_TICKS)}; const svg=d3.select('#radar'), cx=380, cy=310, radius=220;
function point(i,value,axes){{const angle=2*Math.PI*i/axes.length-Math.PI/2, bounded=Math.max(0,Math.min(100,value)), r=radius*Math.log1p(bounded)/Math.log1p(100);return [cx+r*Math.cos(angle),cy+r*Math.sin(angle)]}}
function complete(model,axes){{return axes.every(axis=>model.radar[mode][axis.id] !== undefined && model.radar[mode][axis.id] !== null)}}
function draw(){{const axes=axisSets[mode];const visible=models.filter(m=>selected.has(m.model)&&complete(m,axes));svg.selectAll('*').remove();for(const v of logTicks){{svg.append('path').attr('class','axis').attr('d','M'+axes.map((_,i)=>point(i,v,axes).join(',')).join('L')+'Z')}}axes.forEach((axis,i)=>{{const end=point(i,100,axes), angle=2*Math.PI*i/axes.length-Math.PI/2, label=[cx+(radius+28)*Math.cos(angle),cy+(radius+28)*Math.sin(angle)];svg.append('line').attr('class','axis').attr('x1',cx).attr('y1',cy).attr('x2',end[0]).attr('y2',end[1]);svg.append('text').attr('class','label').attr('x',label[0]).attr('y',label[1]).attr('text-anchor','middle').text(axis.label)}});visible.forEach((model,index)=>{{const values=axes.map(axis=>model.radar[mode][axis.id]);const d='M'+values.map((v,i)=>point(i,v,axes).join(',')).join('L')+'Z';svg.append('path').attr('d',d).attr('fill',colors[index%colors.length]).attr('fill-opacity',.16).attr('stroke',colors[index%colors.length]).attr('stroke-width',2.5)}});d3.select('#legend').html(visible.map((m,i)=>`<span><i class="swatch" style="background:${{colors[i%colors.length]}}"></i>${{m.display_name}}</span>`).join('') || '<span class="muted">No selected model has all values for this view.</span>');const rows=models.map(m=>`<tr><td>${{m.display_name}}</td><td>${{m.company}}</td><td>${{m.content_score===null?'Awaiting score':m.content_score.toFixed(2)}}</td><td>${{m.cost_source==='local'?'$0.000000 local baseline':'$'+m.cost_usd.toFixed(6)}}</td><td>${{m.confidence===null?'—':m.confidence.toFixed(3)}}</td></tr>`).join('');d3.select('#table').html(`<table><thead><tr><th>Model</th><th>Provider</th><th>Content score</th><th>Bundle cost</th><th>Confidence</th></tr></thead><tbody>${{rows}}</tbody></table>`);}}
d3.select('#mode').on('change',event=>{{mode=event.target.value;draw()}});d3.select('#controls').selectAll('label').data(models).join('label').html(m=>`<input type="checkbox" ${{selected.has(m.model)?'checked':''}}> ${{m.display_name}}`).on('change',(event,m)=>{{event.target.checked?selected.add(m.model):selected.delete(m.model);draw()}});if(comparison.awaiting_score.length)d3.select('#awaiting').html(`<p class="warning">Awaiting LLM quality score: ${{comparison.awaiting_score.length}} run(s). They remain available in the readability-and-cost view.</p>`);draw();
</script></main></body></html>"""


def dashboard_html_v2(data: dict[str, Any]) -> str:
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = "SteadyBurn model comparison"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
body{{margin:0;background:#0b1020;color:#e5e7eb;font:16px system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px}}h1{{margin-bottom:6px}}h2{{margin-top:32px;margin-bottom:6px}}.muted{{color:#a5b4c7}}#controls{{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0}}label{{background:#18243a;border-radius:999px;padding:8px 12px;cursor:pointer}}input{{margin-right:6px}}select{{background:#18243a;color:#e5e7eb;border:1px solid #41506d;border-radius:8px;padding:8px}}svg{{width:100%;max-width:760px;background:#111a2d;border-radius:16px}}.axis{{stroke:#41506d;fill:none}}.label{{fill:#cbd5e1;font-size:12px}}.legend{{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0}}.swatch{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}}.table-wrap{{overflow-x:auto;margin-top:12px}}table{{width:100%;border-collapse:collapse;margin-top:12px;white-space:nowrap}}th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid #24324b}}th{{color:#a5b4c7}}.warning{{padding:12px;background:#3a2b12;border-radius:8px}}
</style></head><body><main><h1>{html.escape(title)}</h1><p class="muted">Quality and readability are shown in separate charts. Each axis uses its own ordinal 15–100 rank scale; bundle price is kept in the summary below both charts.</p>
<p><label for="mode">Quality radar view</label> <select id="mode"><option value="overview" selected>Grouped overview</option><option value="quality">LLM quality standards</option></select></p><div id="controls"></div>
<h2>Quality comparison</h2><div id="legend" class="legend"></div><svg id="radar" viewBox="0 0 760 620" role="img" aria-label="Model quality radar chart"></svg>
<h2>Readability comparison</h2><p class="muted">The readability radar separates words, sentence structure, grade level, and other readability measurements from the price summary.</p><div id="readability-legend" class="legend"></div><svg id="readability-radar" viewBox="0 0 760 620" role="img" aria-label="Model readability radar chart"></svg>
<h2>Hard values</h2><div id="quality-values"></div><div id="overview-values"></div><div id="readability-values"></div>
<h2>Model and price summary</h2><div id="table"></div><div id="awaiting"></div>
<script>const comparison={embedded};
const axisSets=comparison.axis_sets, models=comparison.models, selected=new Set(models.filter(m=>m.cost_source==='local').map(m=>m.model)); let mode='overview';
const colors={json.dumps(COLORS)}, logTicks={json.dumps(RADAR_LOG_TICKS)}; const cx=380, cy=310, radius=220, svg=d3.select('#radar'), readabilitySvg=d3.select('#readability-radar');
function point(i,value,axes){{const angle=2*Math.PI*i/axes.length-Math.PI/2, bounded=Math.max(0,Math.min(100,value)), r=radius*Math.log1p(bounded)/Math.log1p(100);return [cx+r*Math.cos(angle),cy+r*Math.sin(angle)]}}
function complete(model,axes,modeName){{return axes.every(axis=>model.radar[modeName][axis.id] !== undefined && model.radar[modeName][axis.id] !== null)}}
function drawRadar(target,axes,modeName,legendTarget){{const visible=models.filter(m=>selected.has(m.model)&&complete(m,axes,modeName));target.selectAll('*').remove();for(const v of logTicks){{target.append('path').attr('class','axis').attr('d','M'+axes.map((_,i)=>point(i,v,axes).join(',')).join('L')+'Z')}}axes.forEach((axis,i)=>{{const end=point(i,100,axes), angle=2*Math.PI*i/axes.length-Math.PI/2, label=[cx+(radius+28)*Math.cos(angle),cy+(radius+28)*Math.sin(angle)];target.append('line').attr('class','axis').attr('x1',cx).attr('y1',cy).attr('x2',end[0]).attr('y2',end[1]);target.append('text').attr('class','label').attr('x',label[0]).attr('y',label[1]).attr('text-anchor','middle').text(axis.label)}});visible.forEach((model,index)=>{{const values=axes.map(axis=>model.radar[modeName][axis.id]);const d='M'+values.map((v,i)=>point(i,v,axes).join(',')).join('L')+'Z';target.append('path').attr('d',d).attr('fill',colors[index%colors.length]).attr('fill-opacity',.16).attr('stroke',colors[index%colors.length]).attr('stroke-width',2.5)}});d3.select(legendTarget).html(visible.map((m,i)=>`<span><i class="swatch" style="background:${{colors[i%colors.length]}}"></i>${{m.display_name}}</span>`).join('') || '<span class="muted">No selected model has all values for this view.</span>')}}
function draw(){{drawRadar(svg,axisSets[mode],mode,'#legend');drawRadar(readabilitySvg,axisSets.readability.filter(axis=>axis.id!=='cost_burden'),'readability','#readability-legend');const rows=models.map(m=>`<tr><td>${{m.display_name}}</td><td>${{m.company}}</td><td>${{m.content_score===null?'Awaiting score':m.content_score.toFixed(2)}}</td><td>${{m.cost_source==='local'?'$0.000000 local baseline':'$'+m.cost_usd.toFixed(6)}}</td><td>${{m.confidence===null?'—':m.confidence.toFixed(3)}}</td></tr>`).join('');d3.select('#table').html(`<table><thead><tr><th>Model</th><th>Provider</th><th>Content score</th><th>Bundle cost</th><th>Confidence</th></tr></thead><tbody>${{rows}}</tbody></table>`)}}
function renderValuesTable(containerId,title,axes,modeName){{const visible=models.filter(m=>selected.has(m.model));const headers=axes.map(axis=>'<th>'+axis.label+'</th>').join('');const body=visible.map(model=>'<tr><td>'+model.display_name+'</td>'+axes.map(axis=>{{const value=model.radar_raw[modeName][axis.id];return '<td>'+((typeof value==='number')?value.toFixed(2):'—')+'</td>}}).join('')+'</tr>').join('');d3.select(containerId).html('<h3>'+title+'</h3><div class="table-wrap"><table><thead><tr><th>Model</th>'+headers+'</tr></thead><tbody>'+body+'</tbody></table></div>')}}
const drawCharts=draw;draw=function(){{drawCharts();renderValuesTable('#quality-values','Quality standards — hard values',axisSets.quality,'quality');renderValuesTable('#overview-values','Grouped overview — hard values',axisSets.overview,'overview');renderValuesTable('#readability-values','Readability comparison — hard values',axisSets.readability.filter(axis=>axis.id!=='cost_burden'),'readability')}};d3.select('#mode').on('change',event=>{{mode=event.target.value;draw()}});d3.select('#controls').selectAll('label').data(models).join('label').html(m=>`<input type="checkbox" ${{selected.has(m.model)?'checked':''}}> ${{m.display_name}}`).on('change',(event,m)=>{{event.target.checked?selected.add(m.model):selected.delete(m.model);draw()}});if(comparison.awaiting_score.length)d3.select('#awaiting').html(`<p class="warning">Awaiting LLM quality score: ${{comparison.awaiting_score.length}} run(s).</p>`);draw();
</script></main></body></html>"""


def dashboard_html_v3(data: dict[str, Any]) -> str:
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    template = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:dark}body{margin:0;background:#0b1020;color:#e5e7eb;font:15px system-ui,sans-serif}main{max-width:1280px;margin:auto;padding:28px}h1{margin:0 0 6px}h2{margin:34px 0 6px}h3{margin:22px 0 6px}.muted{color:#a5b4c7}.note{font-size:13px;color:#94a3b8}.controls{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0}.controls label{background:#18243a;border-radius:999px;padding:8px 12px;cursor:pointer}.controls input{margin-right:6px}.panel{background:#111a2d;border:1px solid #24324b;border-radius:14px;padding:16px;overflow:hidden}svg{display:block;width:100%;background:#111a2d;border-radius:10px}.legend{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0}.swatch{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}.summary{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.card{background:#18243a;border-radius:10px;padding:10px 12px}.card strong{display:block;color:#f8fafc}.scroll{overflow-x:auto;margin-top:10px}table{border-collapse:collapse;white-space:nowrap;width:100%;font-size:13px}th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #24324b}th{color:#a5b4c7;position:sticky;top:0;background:#18243a}td.num{text-align:right;font-variant-numeric:tabular-nums}.warning{padding:12px;background:#3a2b12;border-radius:8px}.axis-label{fill:#cbd5e1;font-size:11px}.grid{stroke:#41506d;fill:none}.subtle{stroke:#24324b}.frontier{stroke:#facc15;fill:none;stroke-width:3;stroke-dasharray:7 5}.point{stroke:#0b1020;stroke-width:2}.heat-label{fill:#cbd5e1;font-size:10px}.heat-cell{stroke:#0b1020;stroke-width:1}
</style></head><body><main><h1>SteadyBurn model comparison</h1><p class="muted">The main question is cost versus quality: each point is a model, the yellow line is the observed cost-quality frontier, and the tables below preserve the hard values behind the comparison.</p>
<div id="controls" class="controls"></div>
<h2>Cost versus quality</h2><p class="note">Lower and farther left is cheaper; higher is better quality. The local baseline is placed at the zero-cost edge. A model below the frontier costs more without delivering a higher recorded content score.</p><div class="panel"><svg id="tradeoff" viewBox="0 0 1100 520" role="img" aria-label="Cost versus quality frontier chart"></svg><div id="tradeoff-legend" class="legend"></div><div id="tradeoff-summary" class="summary"></div></div>
<h2>Supporting dimension views</h2><h3>Grouped overview</h3><div class="panel"><svg id="overview-radar" viewBox="0 0 900 620" role="img" aria-label="Grouped overview radar chart"></svg><div id="overview-legend" class="legend"></div></div>
<h3>Readability comparison</h3><div class="panel"><svg id="readability-radar" viewBox="0 0 900 620" role="img" aria-label="Readability radar chart"></svg><div id="readability-legend" class="legend"></div></div>
<h3>Quality standards heatmap</h3><p class="note">This heatmap uses the same within-dimension rank scale as the quality radar, making model-by-model differences easier to scan across all standards.</p><div class="panel"><svg id="quality-heatmap" viewBox="0 0 1200 640" role="img" aria-label="Quality standards heatmap"></svg></div>
<h2>Hard values</h2><div id="quality-values"></div><div id="overview-values"></div><div id="readability-values"></div>
<h2>Model and price summary</h2><div id="price-summary"></div><div id="awaiting"></div>
<script>
const comparison=__DATA__, colors=["#38bdf8","#f97316","#a78bfa","#34d399","#facc15","#fb7185","#22c55e","#e879f9","#f43f5e","#60a5fa","#f59e0b","#2dd4bf","#c084fc"];
const defaultModel=comparison.models.find(m=>m.model==='unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl')||comparison.models.find(m=>m.cost_source==='local');
const selected=new Set(defaultModel?[defaultModel.case_study]:[]);
const NS='http://www.w3.org/2000/svg';
function chosen(){return comparison.models.filter(m=>selected.has(m.case_study))}
function el(parent,name,attrs={},text=''){const node=document.createElementNS(NS,name);Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,value));if(text)node.textContent=text;parent.appendChild(node);return node}
function clear(id){const node=document.getElementById(id);while(node.firstChild)node.removeChild(node.firstChild);return node}
function complete(model,mode,axes){return axes.every(axis=>model.radar[mode][axis.id]!==undefined&&model.radar[mode][axis.id]!==null)}
function addLegend(id,models){const node=clear(id);models.forEach((model,index)=>{const span=document.createElement('span');const swatch=document.createElement('i');swatch.className='swatch';swatch.style.background=colors[index%colors.length];span.append(swatch,model.display_name);node.appendChild(span)})}
function drawControls(){const node=clear('controls');comparison.models.forEach(model=>{const label=document.createElement('label');const input=document.createElement('input');input.type='checkbox';input.checked=selected.has(model.case_study);input.addEventListener('change',()=>{input.checked?selected.add(model.case_study):selected.delete(model.case_study);draw()});label.append(input,model.display_name);node.appendChild(label)})}
function drawTradeoff(){const svg=clear('tradeoff'), left=78, right=1040, top=28, bottom=450, width=right-left, height=bottom-top;const models=chosen().filter(m=>typeof m.content_score==='number');if(!models.length){el(svg,'text',{x:80,y:100,class:'axis-label'},'Select at least one scored model.');return}const maxCost=Math.max(...models.map(m=>m.cost_usd),0.000001), maxScore=100, minScore=0;for(let tick=0;tick<=5;tick++){const y=bottom-height*tick/5;el(svg,'line',{x1:left,y1:y,x2:right,y2:y,class:'subtle'});el(svg,'text',{x:left-12,y:y+4,'text-anchor':'end',class:'axis-label'},String(tick*20));}el(svg,'line',{x1:left,y1:bottom,x2:right,y2:bottom,class:'grid'});el(svg,'line',{x1:left,y1:top,x2:left,y2:bottom,class:'grid'});el(svg,'text',{x:20,y:top+8,class:'axis-label'},'Quality score');el(svg,'text',{x:(left+right)/2,y:500,'text-anchor':'middle',class:'axis-label'},'Bundle cost (USD; log-scaled, local baseline at left)');const x=m=>m.cost_usd===0?left+5:left+width*Math.log1p(m.cost_usd)/Math.log1p(maxCost), y=m=>bottom-height*(m.content_score-minScore)/(maxScore-minScore);const frontier=[...models].sort((a,b)=>a.cost_usd-b.cost_usd||a.content_score-b.content_score).filter((m,index,items)=>index===0||m.content_score>Math.max(...items.slice(0,index).map(item=>item.content_score)));if(frontier.length>1)el(svg,'path',{d:frontier.map((m,index)=>(index?'L':'M')+x(m)+','+y(m)).join(' '),class:'frontier'});models.forEach((model,index)=>{const circle=el(svg,'circle',{cx:x(model),cy:y(model),r:7,fill:colors[index%colors.length],class:'point'});el(circle,'title',{},model.display_name+' — score '+model.content_score.toFixed(2)+' — '+(model.cost_usd===0?'local baseline':'$'+model.cost_usd.toFixed(6)));});addLegend('tradeoff-legend',models);const summary=clear('tradeoff-summary');frontier.forEach(model=>{const card=document.createElement('div');card.className='card';card.innerHTML='<strong>'+model.display_name+'</strong><span>'+model.content_score.toFixed(2)+' quality · '+(model.cost_usd===0?'local baseline':'$'+model.cost_usd.toFixed(6))+'</span>';summary.appendChild(card)})}
function drawRadar(id,mode,axes,legendId){const svg=clear(id), models=chosen().filter(m=>complete(m,mode,axes)), cx=450, cy=300, radius=205;if(!models.length){el(svg,'text',{x:60,y:100,class:'axis-label'},'Select a model with complete values for this view.');return}function point(index,value){const angle=2*Math.PI*index/axes.length-Math.PI/2, r=radius*Math.log1p(Math.max(0,Math.min(100,value)))/Math.log1p(100);return [cx+r*Math.cos(angle),cy+r*Math.sin(angle)]}for(const tick of [20,50,80,100]){el(svg,'polygon',{points:axes.map((_,i)=>point(i,tick).join(',')).join(' '),class:'grid'})}axes.forEach((axis,index)=>{const end=point(index,100), angle=2*Math.PI*index/axes.length-Math.PI/2;el(svg,'line',{x1:cx,y1:cy,x2:end[0],y2:end[1],class:'subtle'});el(svg,'text',{x:cx+(radius+26)*Math.cos(angle),y:cy+(radius+26)*Math.sin(angle),'text-anchor':'middle',class:'axis-label'},axis.label)});models.forEach((model,index)=>el(svg,'polygon',{points:axes.map((axis,i)=>point(i,model.radar[mode][axis.id]).join(',')).join(' '),fill:colors[index%colors.length],'fill-opacity':'.16',stroke:colors[index%colors.length],'stroke-width':'2.5'}));addLegend(legendId,models)}
function drawHeatmap(){const svg=clear('quality-heatmap'), axes=comparison.axis_sets.quality, models=chosen().filter(m=>complete(m,'quality',axes)), left=250, top=92, cellW=Math.max(18,Math.min(28,850/axes.length)), cellH=30;if(!models.length){el(svg,'text',{x:40,y:80,class:'axis-label'},'Select a model with complete quality values.');return}svg.setAttribute('viewBox','0 0 '+Math.max(1200,left+axes.length*cellW+20)+' '+Math.max(260,top+models.length*cellH+40));axes.forEach((axis,index)=>{const x=left+index*cellW+cellW/2;el(svg,'text',{x,y:top-8,transform:'rotate(-62 '+x+' '+(top-8)+')','text-anchor':'start',class:'heat-label'},axis.label)});models.forEach((model,row)=>{const y=top+row*cellH;el(svg,'text',{x:left-10,y:y+20,'text-anchor':'end',class:'heat-label'},model.display_name);axes.forEach((axis,column)=>{const value=model.radar.quality[axis.id];const shade=Math.round(34+value*1.8).toString(16).padStart(2,'0');el(svg,'rect',{x:left+column*cellW,y,width:cellW-1,height:cellH-1,fill:'#'+shade+shade+'80',class:'heat-cell'});})})}
function rawTable(id,title,mode,axes){const models=chosen(), node=clear(id);const heading=document.createElement('h3');heading.textContent=title;node.appendChild(heading);const wrap=document.createElement('div');wrap.className='scroll';const table=document.createElement('table');const head=document.createElement('tr');['Model',...axes.map(axis=>axis.label)].forEach(label=>{const th=document.createElement('th');th.textContent=label;head.appendChild(th)});const thead=document.createElement('thead');thead.appendChild(head);table.appendChild(thead);const tbody=document.createElement('tbody');models.forEach(model=>{const row=document.createElement('tr');const name=document.createElement('td');name.textContent=model.display_name;row.appendChild(name);axes.forEach(axis=>{const cell=document.createElement('td');cell.className='num';const value=model.radar_raw[mode][axis.id];cell.textContent=typeof value==='number'?value.toFixed(2):'—';row.appendChild(cell)});tbody.appendChild(row)});table.appendChild(tbody);wrap.appendChild(table);node.appendChild(wrap)}
function priceSummary(){const models=chosen().filter(m=>typeof m.content_score==='number').sort((a,b)=>a.cost_usd-b.cost_usd||b.content_score-a.content_score), node=clear('price-summary');const local=models.find(m=>m.cost_source==='local');const bestScore=Math.max(...models.map(m=>m.content_score),0);const table=document.createElement('table'), head=document.createElement('tr');['Model','Provider','Quality score','Bundle cost','Score delta vs local','Extra cost vs local','Decision role'].forEach(label=>{const th=document.createElement('th');th.textContent=label;head.appendChild(th)});const thead=document.createElement('thead');thead.appendChild(head);table.appendChild(thead);const tbody=document.createElement('tbody');models.forEach(model=>{const row=document.createElement('tr'), delta=local?model.content_score-local.content_score:0, extra=local?model.cost_usd-local.cost_usd:0, role=model.content_score===bestScore?'Highest recorded quality':model.cost_source==='local'?'Zero-cost baseline':'Paid comparison';[model.display_name,model.company,model.content_score.toFixed(2),model.cost_usd===0?'$0.000000 local baseline':'$'+model.cost_usd.toFixed(6),delta>=0?'+'+delta.toFixed(2):delta.toFixed(2),extra<=0?'$0.000000':'+$'+extra.toFixed(6),role].forEach((value,index)=>{const cell=document.createElement('td');cell.textContent=value;if(index>1)cell.className='num';row.appendChild(cell)});tbody.appendChild(row)});table.appendChild(tbody);const wrap=document.createElement('div');wrap.className='scroll';wrap.appendChild(table);node.appendChild(wrap)}
function draw(){drawControls();drawTradeoff();drawRadar('overview-radar','overview',comparison.axis_sets.overview,'overview-legend');drawRadar('readability-radar','readability',comparison.axis_sets.readability.filter(axis=>axis.id!=='cost_burden'),'readability-legend');drawHeatmap();rawTable('quality-values','Quality standards — hard values','quality',comparison.axis_sets.quality);rawTable('overview-values','Grouped overview — hard values','overview',comparison.axis_sets.overview);rawTable('readability-values','Readability comparison — hard values','readability',comparison.axis_sets.readability.filter(axis=>axis.id!=='cost_burden));priceSummary();if(comparison.awaiting_score.length)document.getElementById('awaiting').textContent='Awaiting quality score: '+comparison.awaiting_score.length+' run(s).'}draw();
</script></main></body></html>"""
    return template.replace("__TITLE__", "SteadyBurn model comparison").replace("__DATA__", embedded)


def dashboard_html_v4(data: dict[str, Any]) -> str:
    """Harden the static renderer around unknown prices and the cost-quality decision."""
    page = dashboard_html_v3(data)

    def replace_between(source: str, start: str, end: str, replacement: str) -> str:
        start_at = source.index(start)
        end_at = source.index(end, start_at)
        return source[:start_at] + replacement + source[end_at:]

    tradeoff = """function drawTradeoff(){const svg=clear('tradeoff'),left=78,right=1040,top=28,bottom=450,width=right-left,height=bottom-top,priced=chosen().filter(m=>typeof m.content_score==='number'&&typeof m.cost_usd==='number');if(!priced.length){el(svg,'text',{x:80,y:100,class:'axis-label'},'Select a model with a recorded price.');return}const maxCost=Math.max(...priced.map(m=>m.cost_usd),0.000001),x=m=>m.cost_usd===0?left+5:left+width*Math.log1p(m.cost_usd)/Math.log1p(maxCost),y=m=>bottom-height*m.content_score/100;for(let tick=0;tick<=5;tick++){const yy=bottom-height*tick/5;el(svg,'line',{x1:left,y1:yy,x2:right,y2:yy,class:'subtle'});el(svg,'text',{x:left-12,y:yy+4,'text-anchor':'end',class:'axis-label'},String(tick*20))}el(svg,'line',{x1:left,y1:bottom,x2:right,y2:bottom,class:'grid'});el(svg,'line',{x1:left,y1:top,x2:left,y2:bottom,class:'grid'});el(svg,'text',{x:20,y:top+8,class:'axis-label'},'Quality score');el(svg,'text',{x:(left+right)/2,y:500,'text-anchor':'middle',class:'axis-label'},'Bundle cost (USD; log-scaled, local baseline at left)');const frontier=[...priced].sort((a,b)=>a.cost_usd-b.cost_usd||a.content_score-b.content_score).filter((m,index,items)=>index===0||m.content_score>Math.max(...items.slice(0,index).map(item=>item.content_score)));if(frontier.length>1)el(svg,'path',{d:frontier.map((m,index)=>(index?'L':'M')+x(m)+','+y(m)).join(' '),class:'frontier'});priced.forEach((model,index)=>{const circle=el(svg,'circle',{cx:x(model),cy:y(model),r:7,fill:colors[index%colors.length],class:'point'});el(circle,'title',{},model.display_name+' — score '+model.content_score.toFixed(2)+' — '+(model.cost_usd===0?'local baseline':'$'+model.cost_usd.toFixed(6)))});addLegend('tradeoff-legend',priced);const summary=clear('tradeoff-summary');frontier.forEach(model=>{const card=document.createElement('div');card.className='card';card.innerHTML='<strong>'+model.display_name+'</strong><span>'+model.content_score.toFixed(2)+' quality · '+(model.cost_usd===0?'local baseline':'$'+model.cost_usd.toFixed(6))+'</span>';summary.appendChild(card)});const unpriced=chosen().filter(m=>typeof m.content_score==='number'&&typeof m.cost_usd!=='number');if(unpriced.length){const card=document.createElement('div');card.className='card';card.innerHTML='<strong>Price unavailable</strong><span>'+unpriced.map(m=>m.display_name).join(', ')+'</span>';summary.appendChild(card)}}"""
    page = replace_between(page, "function drawTradeoff(){", "\nfunction drawRadar", tradeoff + "\n")

    price = """function priceSummary(){const models=chosen().filter(m=>typeof m.content_score==='number').sort((a,b)=>(typeof a.cost_usd==='number'?a.cost_usd:Infinity)-(typeof b.cost_usd==='number'?b.cost_usd:Infinity)||b.content_score-a.content_score),node=clear('price-summary'),local=models.find(m=>m.cost_source==='local'),table=document.createElement('table'),head=document.createElement('tr');['Model','Provider','Quality score','Bundle cost','Score delta vs local','Extra cost vs local','Decision role'].forEach(label=>{const th=document.createElement('th');th.textContent=label;head.appendChild(th)});const thead=document.createElement('thead');thead.appendChild(head);table.appendChild(thead);const tbody=document.createElement('tbody');models.forEach(model=>{const row=document.createElement('tr'),known=typeof model.cost_usd==='number',delta=local?model.content_score-local.content_score:null,extra=local&&known?model.cost_usd-local.cost_usd:null,role=!known?'Quality measured; price unavailable':model.cost_source==='local'?'Zero-cost baseline':model.content_score===Math.max(...models.map(m=>m.content_score))?'Highest recorded quality':'Paid comparison';[model.display_name,model.company,model.content_score.toFixed(2),known?(model.cost_usd===0?'$0.000000 local baseline':'$'+model.cost_usd.toFixed(6)):'Unavailable',delta===null?'—':(delta>=0?'+':'')+delta.toFixed(2),extra===null?'—':(extra>=0?'+$':'-$')+Math.abs(extra).toFixed(6),role].forEach((value,index)=>{const cell=document.createElement('td');cell.textContent=value;if(index>1)cell.className='num';row.appendChild(cell)});tbody.appendChild(row)});table.appendChild(tbody);const wrap=document.createElement('div');wrap.className='scroll';wrap.appendChild(table);node.appendChild(wrap)}"""
    page = replace_between(page, "function priceSummary(){", "\nfunction draw(){", price + "\n")

    draw = """function draw(){drawControls();drawTradeoff();drawRadar('overview-radar','overview',comparison.axis_sets.overview,'overview-legend');drawRadar('readability-radar','readability',comparison.axis_sets.readability,'readability-legend');drawHeatmap();rawTable('quality-values','Quality standards — hard values','quality',comparison.axis_sets.quality);rawTable('overview-values','Grouped overview — hard values','overview',comparison.axis_sets.overview);rawTable('readability-values','Readability comparison — hard values','readability',comparison.axis_sets.readability);priceSummary();if(comparison.awaiting_score.length)document.getElementById('awaiting').textContent='Awaiting quality score: '+comparison.awaiting_score.length+' run(s).'}draw();"""
    page = replace_between(page, "function draw(){", "\n</script>", draw + "\n")
    return page


dashboard_html = dashboard_html_v4


def radar_svg(data: dict[str, Any]) -> str:
    """Render a Markdown-embeddable snapshot of the interactive radar chart."""
    axes = data["axis_sets"]["overview"]
    models = [
        model for model in sorted(data["models"], key=lambda item: item["content_score"] or -1, reverse=True)
        if all(model["radar"]["overview"].get(axis["id"]) is not None for axis in axes)
    ]
    width, height, center_x, center_y, radius = 1100, 760, 430, 390, 255

    def point(index: int, value: float) -> tuple[float, float]:
        angle = 2 * math.pi * index / len(axes) - math.pi / 2
        distance = radius * radial_fraction(value)
        return center_x + distance * math.cos(angle), center_y + distance * math.sin(angle)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
        '  <title id="title">SteadyBurn model quality and cost comparison</title>',
        '  <desc id="description">A radar chart summarizing the scored, priced case studies. The interactive dashboard contains the complete comparison.</desc>',
        '  <style>.bg{fill:#0b1020}.title{fill:#f8fafc;font:700 28px Arial,sans-serif}.sub,.axis-label,.note{fill:#a5b4c7;font:15px Arial,sans-serif}.grid{fill:none;stroke:#41506d;stroke-width:1}.spoke{stroke:#41506d;stroke-width:1}.legend{fill:#e2e8f0;font:16px Arial,sans-serif}</style>',
        f'  <rect class="bg" width="{width}" height="{height}" rx="18"/>',
        '  <text class="title" x="48" y="58">SteadyBurn model quality and cost</text>',
        '  <text class="sub" x="48" y="86">Each axis is a 15–100 within-dimension rank; raw values remain in JSON.</text>',
    ]
    for ring in RADAR_LOG_TICKS:
        points = " ".join(f"{x:.1f},{y:.1f}" for index in range(len(axes)) for x, y in [point(index, ring)])
        lines.append(f'  <polygon class="grid" points="{points}"/>')
    for index, axis in enumerate(axes):
        x, y = point(index, 100)
        label_x = center_x + (radius + 32) * math.cos(2 * math.pi * index / len(axes) - math.pi / 2)
        label_y = center_y + (radius + 32) * math.sin(2 * math.pi * index / len(axes) - math.pi / 2)
        lines.extend((
            f'  <line class="spoke" x1="{center_x}" y1="{center_y}" x2="{x:.1f}" y2="{y:.1f}"/>',
            f'  <text class="axis-label" x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle">{html.escape(axis["label"])}</text>',
        ))
    for index, model in enumerate(models):
        color = COLORS[index % len(COLORS)]
        points = " ".join(
            f"{x:.1f},{y:.1f}" for axis_index, axis in enumerate(axes)
            for x, y in [point(axis_index, float(model["radar"]["overview"][axis["id"]]))]
        )
        legend_y = 190 + index * 42
        lines.extend((
            f'  <polygon points="{points}" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-width="2.5"/>',
            f'  <circle cx="760" cy="{legend_y - 5}" r="6" fill="{color}"/>',
            f'  <text class="legend" x="776" y="{legend_y}">{html.escape(model["display_name"])} — {"$0.000000 local baseline" if model["cost_source"] == "local" else money(model["cost_usd"])}</text>',
        ))
    if not models:
        lines.append('  <text class="note" x="48" y="150">No scored paid case studies are available yet.</text>')
    lines.extend((
        '  <text class="note" x="48" y="708">Cost burden is relative: the local baseline is 0 and the most expensive recorded bundle is 100.</text>',
        '  <text class="note" x="48" y="734">Source: CONTENT_SCORE.json and OPENROUTER_USAGE.jsonl in each case-study directory.</text>',
        '</svg>',
    ))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    data = compile_comparison(root)
    (root / "model-comparison.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (root / "model-comparison.html").write_text(dashboard_html(data), encoding="utf-8")
    (root / "model-comparison-radar.svg").write_text(radar_svg(data), encoding="utf-8")
    print(f"Compiled {len(data['models'])} case studies; {len(data['awaiting_score'])} await LLM quality scoring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
