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


def radial_fraction(value: float) -> float:
    """Map the user-facing 0–100 metric to a zero-safe logarithmic radius."""
    bounded = min(100.0, max(0.0, float(value)))
    return math.log1p(bounded) / math.log1p(100.0)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def money(value: float | None) -> str:
    return "Unavailable" if value is None else "$" + f"{value:.6f}"


def company_for(model: str) -> str:
    return {"openai": "OpenAI", "google": "Google", "deepseek": "DeepSeek"}.get(model.split("/", 1)[0], "Local / other")


def display_name(model: str, case_study: str | None = None) -> str:
    name = model.split("/", 1)[-1].replace("-it", "").replace("-", " ").title().replace("Gpt", "GPT")
    return f"Local model ({name})" if case_study and case_study.startswith("local-models/") else name


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
        report = load_json(score_path) if score_path.exists() else None
        if not score_path.exists():
            awaiting_score.append(case_study)
        model = str(report.get("model", "unknown")) if report else model_from_comparison(comparison_path)
        categories = rubric_category_scores(report, rubric) if report else {}
        criteria = {
            artifact: {item["id"]: float(item["score"]) for item in value["criteria"]}
            for artifact, value in report["artifacts"].items()
        } if report else {}
        models.append({
            "model": model,
            "display_name": display_name(model, case_study),
            "company": "Local" if case_study.startswith("local-models/") else company_for(model),
            "case_study": case_study,
            "content_score": float(report["content_score"]) if report else None,
            "confidence": float(report["confidence"]) if report else None,
            "cost_usd": paid_cost(study_root / "OPENROUTER_USAGE.jsonl") or 0.0,
            "cost_source": "openrouter" if (study_root / "OPENROUTER_USAGE.jsonl").exists() else "local",
            "categories": categories,
            "criteria": criteria,
            "measurements": {artifact: value["metrics"] for artifact, value in report["artifacts"].items()} if report else {},
            "readability": readability.get(case_study, {}),
            "radar_raw": {"overview": axis_scores(categories, criteria), "quality": {}, "readability": {}},
            "radar": {"overview": {}, "quality": {}, "readability": {}},
        })
    maximum_cost = max((float(item["cost_usd"]) for item in models), default=0.0)
    for model in models:
        cost_burden = round(100 * float(model["cost_usd"]) / maximum_cost, 2) if maximum_cost else 0.0
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
            "overview": ([{"id": axis_id, "label": label} for axis_id, label, _sources in OVERVIEW_AXES]
                         + [{"id": axis_id, "label": label} for axis_id, label, _artifact, _criterion in OVERVIEW_READABILITY_AXES]),
            "quality": quality_axes(rubric),
            "readability": [{"id": metric, "label": label} for metric, label in READABILITY_METRICS] + [{"id": "cost_burden", "label": "Cost burden"}],
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
body{{margin:0;background:#0b1020;color:#e5e7eb;font:16px system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px}}h1{{margin-bottom:6px}}h2{{margin-top:32px;margin-bottom:6px}}.muted{{color:#a5b4c7}}#controls{{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0}}label{{background:#18243a;border-radius:999px;padding:8px 12px;cursor:pointer}}input{{margin-right:6px}}select{{background:#18243a;color:#e5e7eb;border:1px solid #41506d;border-radius:8px;padding:8px}}svg{{width:100%;max-width:760px;background:#111a2d;border-radius:16px}}.axis{{stroke:#41506d;fill:none}}.label{{fill:#cbd5e1;font-size:12px}}.legend{{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0}}.swatch{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}}table{{width:100%;border-collapse:collapse;margin-top:30px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #24324b}}th{{color:#a5b4c7}}.warning{{padding:12px;background:#3a2b12;border-radius:8px}}
</style></head><body><main><h1>{html.escape(title)}</h1><p class="muted">Quality and readability are shown in separate charts. Each axis uses its own ordinal 15–100 rank scale; bundle price is kept in the summary below both charts.</p>
<p><label for="mode">Quality radar view</label> <select id="mode"><option value="quality">LLM quality standards</option><option value="overview">Grouped overview</option></select></p><div id="controls"></div>
<h2>Quality comparison</h2><div id="legend" class="legend"></div><svg id="radar" viewBox="0 0 760 620" role="img" aria-label="Model quality radar chart"></svg>
<h2>Readability comparison</h2><p class="muted">The readability radar separates words, sentence structure, grade level, and other readability measurements from the price summary.</p><div id="readability-legend" class="legend"></div><svg id="readability-radar" viewBox="0 0 760 620" role="img" aria-label="Model readability radar chart"></svg>
<h2>Model and price summary</h2><div id="table"></div><div id="awaiting"></div>
<script>const comparison={embedded};
const axisSets=comparison.axis_sets, models=comparison.models, selected=new Set(models.map(m=>m.model)); let mode='quality';
const colors={json.dumps(COLORS)}, logTicks={json.dumps(RADAR_LOG_TICKS)}; const cx=380, cy=310, radius=220, svg=d3.select('#radar'), readabilitySvg=d3.select('#readability-radar');
function point(i,value,axes){{const angle=2*Math.PI*i/axes.length-Math.PI/2, bounded=Math.max(0,Math.min(100,value)), r=radius*Math.log1p(bounded)/Math.log1p(100);return [cx+r*Math.cos(angle),cy+r*Math.sin(angle)]}}
function complete(model,axes,modeName){{return axes.every(axis=>model.radar[modeName][axis.id] !== undefined && model.radar[modeName][axis.id] !== null)}}
function drawRadar(target,axes,modeName,legendTarget){{const visible=models.filter(m=>selected.has(m.model)&&complete(m,axes,modeName));target.selectAll('*').remove();for(const v of logTicks){{target.append('path').attr('class','axis').attr('d','M'+axes.map((_,i)=>point(i,v,axes).join(',')).join('L')+'Z')}}axes.forEach((axis,i)=>{{const end=point(i,100,axes), angle=2*Math.PI*i/axes.length-Math.PI/2, label=[cx+(radius+28)*Math.cos(angle),cy+(radius+28)*Math.sin(angle)];target.append('line').attr('class','axis').attr('x1',cx).attr('y1',cy).attr('x2',end[0]).attr('y2',end[1]);target.append('text').attr('class','label').attr('x',label[0]).attr('y',label[1]).attr('text-anchor','middle').text(axis.label)}});visible.forEach((model,index)=>{{const values=axes.map(axis=>model.radar[modeName][axis.id]);const d='M'+values.map((v,i)=>point(i,v,axes).join(',')).join('L')+'Z';target.append('path').attr('d',d).attr('fill',colors[index%colors.length]).attr('fill-opacity',.16).attr('stroke',colors[index%colors.length]).attr('stroke-width',2.5)}});d3.select(legendTarget).html(visible.map((m,i)=>`<span><i class="swatch" style="background:${{colors[i%colors.length]}}"></i>${{m.display_name}}</span>`).join('') || '<span class="muted">No selected model has all values for this view.</span>')}}
function draw(){{drawRadar(svg,axisSets[mode],mode,'#legend');drawRadar(readabilitySvg,axisSets.readability.filter(axis=>axis.id!=='cost_burden'),'readability','#readability-legend');const rows=models.map(m=>`<tr><td>${{m.display_name}}</td><td>${{m.company}}</td><td>${{m.content_score===null?'Awaiting score':m.content_score.toFixed(2)}}</td><td>${{m.cost_source==='local'?'$0.000000 local baseline':'$'+m.cost_usd.toFixed(6)}}</td><td>${{m.confidence===null?'—':m.confidence.toFixed(3)}}</td></tr>`).join('');d3.select('#table').html(`<table><thead><tr><th>Model</th><th>Provider</th><th>Content score</th><th>Bundle cost</th><th>Confidence</th></tr></thead><tbody>${{rows}}</tbody></table>`)}}
d3.select('#mode').on('change',event=>{{mode=event.target.value;draw()}});d3.select('#controls').selectAll('label').data(models).join('label').html(m=>`<input type="checkbox" ${{selected.has(m.model)?'checked':''}}> ${{m.display_name}}`).on('change',(event,m)=>{{event.target.checked?selected.add(m.model):selected.delete(m.model);draw()}});if(comparison.awaiting_score.length)d3.select('#awaiting').html(`<p class="warning">Awaiting LLM quality score: ${{comparison.awaiting_score.length}} run(s).</p>`);draw();
</script></main></body></html>"""


dashboard_html = dashboard_html_v2


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
