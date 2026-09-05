#!/usr/bin/env python3
"""Build the run-centric evidence explorer and per-run audit pages."""

from __future__ import annotations

import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO_ROOT / "runs"
OUTPUT = REPO_ROOT / "research-runs.html"
DETAIL_ROOT = REPO_ROOT / "run-pages"


STYLE = """
:root{color-scheme:dark;--bg:#070b16;--panel:#0d1424;--panel2:#111a2d;--line:#263349;--text:#e8edf5;--muted:#a5b4c7;--cyan:#67e8f9;--blue:#60a5fa;--green:#4ade80;--amber:#fbbf24;--red:#fb7185}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% -10%,#152444 0,transparent 34%),var(--bg);color:var(--text);font:15px/1.5 Inter,ui-sans-serif,system-ui,sans-serif}main{max-width:1240px;margin:auto;padding:28px}a{color:#7dd3fc}h1{font-size:clamp(2rem,5vw,4rem);line-height:1.02;letter-spacing:-.04em;margin:.25em 0}h2{font-size:1.25rem;margin:0 0 12px}h3{font-size:1rem;margin:0 0 9px}.eyebrow{color:var(--cyan);text-transform:uppercase;letter-spacing:.13em;font-weight:800;font-size:.75rem}.lede,.muted{color:var(--muted)}.lede{font-size:1.08rem;max-width:760px}.site-nav{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:34px}.site-brand{color:#f8fafc;text-decoration:none;font-weight:800}.menu-button{margin-left:auto;border:1px solid #38506f;background:var(--panel2);color:var(--text);border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}.menu-links{display:flex;gap:14px;align-items:center}.menu-links a{text-decoration:none}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px;margin:22px 0}.card{grid-column:span 12;background:linear-gradient(145deg,#101a2d,var(--panel));border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:0 18px 50px #0003}.third{grid-column:span 4}.half{grid-column:span 6}.metric{font-size:1.75rem;font-weight:800}.workflow{display:flex;flex-wrap:wrap;gap:8px}.workflow button,.chip{border:1px solid #38506f;border-radius:999px;background:#0b1220;color:var(--text);padding:8px 13px;font:inherit;cursor:pointer}.workflow button[aria-pressed=true]{background:#164e63;border-color:var(--cyan)}details{border:1px solid var(--line);border-radius:10px;padding:12px;background:#0a1120}summary{cursor:pointer;font-weight:750}.provider-group{padding:11px 0;border-top:1px solid #1d2a3e}.provider-group:first-of-type{border-top:0}.model-option{display:flex;align-items:flex-start;gap:8px;padding:5px 0}.status,.compare{display:inline-flex;align-items:center;gap:5px;border:1px solid;border-radius:999px;padding:2px 8px;font-size:.75rem;font-weight:750}.ok,.comparable{color:#86efac;border-color:#166534;background:#052e1655}.partial,.directional{color:#fde68a;border-color:#92400e;background:#451a0355}.error,.not-comparable{color:#fda4af;border-color:#9f1239;background:#4c051955}.bars{display:grid;gap:9px}.bar-row{display:grid;grid-template-columns:minmax(110px,1fr) 4fr 54px;align-items:center;gap:10px}.track{height:12px;background:#1d2a3e;border-radius:99px;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan));border-radius:inherit}.fill.contract{background:linear-gradient(90deg,#8b5cf6,#60a5fa)}.fill.strict{background:linear-gradient(90deg,#059669,#4ade80)}.warning{border-left:3px solid var(--amber);padding:10px 12px;background:#42200655;color:#fde68a;margin:12px 0}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;min-width:760px}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #1c293c;vertical-align:top}th{position:sticky;top:0;background:#111a2d;color:#cbd5e1;font-size:.77rem;text-transform:uppercase;letter-spacing:.06em}tbody tr:hover{background:#152139}.number{text-align:right;font-variant-numeric:tabular-nums}.empty{padding:30px;color:var(--muted);text-align:center}.task-score{font-weight:800}.stage{border-left:2px solid var(--blue);padding:0 0 18px 16px;margin-left:5px}.stage:last-child{padding-bottom:0}.provenance{font-family:ui-monospace,monospace;font-size:.78rem;overflow-wrap:anywhere}.footer{color:var(--muted);padding:24px 0 40px}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:820px){main{padding:18px}.third,.half{grid-column:span 12}.site-nav{position:relative}.menu-links{display:none;position:absolute;right:0;top:42px;z-index:10;min-width:230px;flex-direction:column;align-items:stretch;padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--panel2);box-shadow:0 12px 28px #0008}.menu-links.is-open{display:flex}.menu-links a{padding:7px}.bar-row{grid-template-columns:94px 1fr 44px}}@media(min-width:821px){.menu-button{display:none}}
.plot{min-height:280px}.plot svg{width:100%;height:auto;display:block}.plot text{fill:var(--muted);font:12px system-ui}.plot .axis{stroke:#52647c}.plot .frontier{fill:none;stroke:var(--green);stroke-width:2;stroke-dasharray:6 4}.plot .point{fill:var(--cyan);stroke:#083344;stroke-width:2}
"""


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def nav(prefix: str = "") -> str:
    return f'''<nav class="site-nav" aria-label="Primary"><a class="site-brand" href="{prefix}index.html">Language model research</a><button class="menu-button" type="button" aria-expanded="false" aria-controls="site-menu">Menu ☰</button><div class="menu-links" id="site-menu"><a href="{prefix}index.html">Editorial research</a><a href="{prefix}assistant-benchmark.html">Assistant benchmark</a><a href="{prefix}research-runs.html" aria-current="page">Run explorer</a><a href="{prefix}methodology.html">Methodology</a></div></nav>'''


MENU_SCRIPT = """<script>const mb=document.querySelector('.menu-button'),mm=document.querySelector('.menu-links');if(mb)mb.addEventListener('click',()=>{const o=mm.classList.toggle('is-open');mb.setAttribute('aria-expanded',String(o))});</script>"""


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def aggregates(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        repro = run["reproducibility"]
        key = (
            run["suite"], run["model"], run["provider_kind"], str(repro.get("fixture_sha256")),
            str(repro.get("tasks_sha256")), str(repro.get("prompt_sha256")), str(repro.get("tool_schema_sha256")),
            str(run["replicate"]["seed"]), str(run["endpoint_class"]),
        )
        groups[key].append(run)
    output = []
    for key, group in groups.items():
        scores = [float(row["score"]) for row in group]
        times = [float(row["efficiency"].get("total_seconds", 0)) for row in group]
        costs = [
            float(row["provider_reported_cost_usd"])
            for row in group
            if isinstance(row.get("provider_reported_cost_usd"), (int, float))
        ]
        first = group[0]
        exactness = {name: sum(int(row["exactness"][name]) for row in group) for name in ("core", "contract", "strict", "total")}
        output.append({
            "key": "|".join(key), "suite": first["suite"], "model": first["model"],
            "display_name": first["display_name"], "provider": first["provider"],
            "provider_kind": first["provider_kind"], "cohort": first["cohort"],
            "endpoint_class": first["endpoint_class"], "seed": first["replicate"]["seed"],
            "status": "error" if all(row["status"] == "error" for row in group) else ("partial" if any(row["status"] != "ok" for row in group) else "ok"),
            "replicates": len(group), "score_median": round(statistics.median(scores), 3),
            "score_q1": round(percentile(scores, .25), 3), "score_q3": round(percentile(scores, .75), 3),
            "score_min": min(scores), "score_max": max(scores),
            "total_seconds_median": round(statistics.median(times), 3),
            "provider_cost_median": round(statistics.median(costs), 6) if costs else None,
            "exactness": exactness, "reliability": {
                "scheduled_pass_rate": round(exactness["strict"] / exactness["total"] * 100, 3) if exactness["total"] else 0,
                "evaluated_pass_rate": round(statistics.mean(float(row["reliability"]["evaluated_pass_rate"]) for row in group), 3),
            },
            "dimensions": first.get("dimensions", {}), "reproducibility": first["reproducibility"],
            "run_ids": [row["run_id"] for row in group], "caveats": sorted({item for row in group for item in row.get("caveats", [])}),
        })
    return sorted(output, key=lambda row: (row["suite"], -row["score_median"], row["model"]))


def main_page(registry: dict[str, Any]) -> str:
    runs = registry["runs"]
    task_data = {}
    for run in runs:
        task_data[run["run_id"]] = [
            {key: row.get(key) for key in ("task_id", "title", "category", "score", "strict_passed", "failure_type")}
            for row in read_jsonl(RUNS_ROOT / run["run_id"] / "task-results.jsonl")
        ]
    payload = json.dumps({"runs": runs, "aggregates": aggregates(runs), "tasks": task_data}, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Benchmark evidence explorer</title><style>{STYLE}</style></head><body><main>{nav()}
<div class="eyebrow">Run-centric benchmark evidence</div><h1>Choose evidence,<br>not a leaderboard.</h1><p class="lede">Compare models only when the benchmark contract and execution conditions support it. Every score links to task outcomes, trajectories, raw responses, provenance, and explicit caveats.</p>
<section class="grid" aria-label="Dataset summary"><article class="card third"><div class="metric">{len(runs)}</div><div class="muted">immutable run bundles</div></article><article class="card third"><div class="metric">{len({row['model'] for row in runs})}</div><div class="muted">models with retained evidence</div></article><article class="card third"><div class="metric">{len({row['suite'] for row in runs})}</div><div class="muted">distinct benchmark suites</div></article></section>
<section class="card"><h2>Start with the workflow</h2><p class="muted">A model can be strong in one workflow and weak in another. Suite scores are never blended.</p><div class="workflow" role="group" aria-label="Select workflow"><button data-suite="assistant" aria-pressed="true">Personal assistant</button><button data-suite="editorial" aria-pressed="false">Editorial production</button><button data-suite="latency" aria-pressed="false">Latency-sensitive local use</button></div></section>
<section class="grid"><article class="card half"><h2>Selected evidence</h2><div id="selection-summary" class="muted">Select up to four model runs to compare.</div><div id="comparability"></div></article><article class="card half"><h2>What this proves</h2><p>Task-level performance under the recorded prompt, tool schema, fixture, seed, runtime, and lifecycle controls.</p><h3>What it does not prove</h3><p class="muted">General intelligence, unseen-task reliability, another quantization or host, or provider-wide service quality.</p></article></section>
<section class="card"><details><summary>Choose models · grouped by provider</summary><div id="model-options"></div></details></section>
<section class="card"><h2>Exactness funnel</h2><p class="muted">Core requirements → full contract → strict pass. Bars use both labels and values; the table below is the accessible equivalent.</p><div id="funnel-chart" class="bars"></div></section>
<section class="card"><h2>Quality–speed frontier</h2><p class="muted">Upper-left is better: higher task score with less recorded task time. The dashed line marks non-dominated selected evidence. Provider-reported monetary cost is shown separately below; local infrastructure cost is excluded.</p><div id="frontier-chart" class="plot"></div></section>
<section class="card"><h2>Quality, reliability, speed, and cost</h2><p class="muted">Replicate distributions are median, interquartile range, and min–max. Single runs are labeled as such. Cost is provider-reported workload cost; $0 local does not mean zero infrastructure cost.</p><div class="table-wrap"><table><thead><tr><th>Model</th><th>Provider</th><th>Status</th><th class="number">Score</th><th class="number">Strict pass</th><th class="number">Total time</th><th class="number">Provider cost</th><th>Replicates / spread</th><th>Evidence</th></tr></thead><tbody id="results-body"></tbody></table></div></section>
<section class="card"><h2>Task matrix</h2><p class="muted">Mean task score across selected replicates. The text value is authoritative; color is only a secondary cue.</p><div class="table-wrap"><table><thead id="task-head"></thead><tbody id="task-body"></tbody></table></div></section>
<section class="card"><h2>Failure taxonomy</h2><div id="failure-summary" class="muted"></div></section>
<p class="footer">Registry generated {esc(registry['generated_at'])}. Raw artifacts are retained under <a href="runs/index.json">runs/</a>.</p>
</main><script id="evidence-data" type="application/json">{payload}</script><script>
const DATA=JSON.parse(document.getElementById('evidence-data').textContent);let suite=new URLSearchParams(location.search).get('suite')||'assistant';let selected=new Set((new URLSearchParams(location.search).get('runs')||'').split(',').filter(Boolean));
const e=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)],pct=(n,d)=>d?100*n/d:0,fmt=n=>Number(n||0).toFixed(1),cost=r=>r.provider_cost_median===null?'unavailable':(r.provider_kind==='local'?'$0 provider':'$'+Number(r.provider_cost_median).toFixed(4));
function sameContract(a,b){{const keys=['fixture_sha256','tasks_sha256','seed_document_sha256','prompt_sha256','tool_schema_sha256'];if(a.suite!==b.suite)return ['not-comparable','Suite differs'];const diff=keys.filter(k=>a.reproducibility[k]!==b.reproducibility[k]);if(a.seed!==b.seed)diff.push('sampling seed');if(diff.length)return ['not-comparable',diff.join(', ')+' differs'];if(a.provider_kind!==b.provider_kind)return ['directional','Local and hosted execution differ'];if(a.endpoint_class!==b.endpoint_class)return ['directional','Runtime or endpoint class differs'];return ['comparable','Contract and execution class match']}}
function current(){{return DATA.aggregates.filter(r=>r.suite===suite)}}
function updateURL(){{const p=new URLSearchParams();p.set('suite',suite);if(selected.size)p.set('runs',[...selected].join(','));history.replaceState(null,'','?'+p)}}
function renderOptions(){{const groups={{}};current().forEach(r=>(groups[r.provider]||(groups[r.provider]=[])).push(r));e('#model-options').innerHTML=Object.entries(groups).sort().map(([p,rows])=>`<div class="provider-group"><strong>${{p}}</strong>${{rows.map(r=>`<label class="model-option"><input type="checkbox" value="${{r.key}}" ${{selected.has(r.key)?'checked':''}}><span>${{r.display_name}} <span class="muted">${{r.replicates}} run${{r.replicates===1?'':'s'}}</span></span></label>`).join('')}}</div>`).join('')||'<div class="empty">No published runs for this suite yet.</div>';all('#model-options input').forEach(x=>x.addEventListener('change',()=>{{if(x.checked&&selected.size>=4){{x.checked=false;alert('Select up to four runs.');return}}x.checked?selected.add(x.value):selected.delete(x.value);render();updateURL()}}))}}
function chosen(){{const c=current();let rows=c.filter(r=>selected.has(r.key));if(!rows.length)rows=c.slice(0,Math.min(4,c.length));return rows}}
function render(){{const rows=chosen();e('#selection-summary').textContent=`${{rows.length}} model evidence set${{rows.length===1?'':'s'}} shown · ${{suite}} suite`;let comparison='';for(let i=0;i<rows.length;i++)for(let j=i+1;j<rows.length;j++){{const [level,reason]=sameContract(rows[i],rows[j]);comparison+=`<p><span class="compare ${{level}}">${{level.replace('-', ' ')}}</span> ${{rows[i].display_name}} ↔ ${{rows[j].display_name}} <span class="muted">${{reason}}</span></p>`}}e('#comparability').innerHTML=comparison||'<p class="muted">Select a second evidence set to classify comparability.</p>';
e('#funnel-chart').innerHTML=rows.map(r=>{{const x=r.exactness,t=x.total||1;return `<div><h3>${{r.display_name}}</h3>${{[['Core',x.core,''],['Contract',x.contract,'contract'],['Strict',x.strict,'strict']].map(([label,n,c])=>`<div class="bar-row"><span>${{label}}</span><div class="track"><div class="fill ${{c}}" style="width:${{pct(n,t)}}%"></div></div><span class="number">${{n}}/${{x.total}}</span></div>`).join('')}}</div>`}}).join('')||'<div class="empty">No evidence available.</div>';
const pw=760,ph=280,pad=46,maxTime=Math.max(1,...rows.map(r=>r.total_seconds_median)),x=r=>pad+(pw-pad*2)*(r.total_seconds_median/maxTime),y=r=>ph-pad-(ph-pad*2)*(r.score_median/100);const ordered=[...rows].sort((a,b)=>a.total_seconds_median-b.total_seconds_median);let best=-1,front=[];ordered.forEach(r=>{{if(r.score_median>best){{front.push(r);best=r.score_median}}}});const poly=front.map(r=>`${{x(r)}},${{y(r)}}`).join(' ');e('#frontier-chart').innerHTML=rows.length?`<svg viewBox="0 0 ${{pw}} ${{ph}}" role="img" aria-labelledby="plot-title plot-desc"><title id="plot-title">Quality versus total task time</title><desc id="plot-desc">Selected model results. Higher and farther left is better. Exact values are in the following table.</desc><line class="axis" x1="${{pad}}" y1="${{ph-pad}}" x2="${{pw-pad}}" y2="${{ph-pad}}"/><line class="axis" x1="${{pad}}" y1="${{pad}}" x2="${{pad}}" y2="${{ph-pad}}"/><text x="${{pw/2}}" y="${{ph-8}}" text-anchor="middle">total task seconds →</text><text x="12" y="${{ph/2}}" transform="rotate(-90 12 ${{ph/2}})" text-anchor="middle">task score →</text><polyline class="frontier" points="${{poly}}"/>${{rows.map(r=>`<g><circle class="point" cx="${{x(r)}}" cy="${{y(r)}}" r="7"><title>${{r.display_name}}: ${{fmt(r.score_median)}} points, ${{fmt(r.total_seconds_median)}} seconds</title></circle><text x="${{x(r)+10}}" y="${{y(r)-9}}">${{r.display_name.slice(0,26)}}</text></g>`).join('')}}</svg>`:'<div class="empty">No evidence available.</div>';
e('#results-body').innerHTML=rows.map(r=>`<tr><td>${{r.display_name}}${{r.caveats.length?'<div class="warning">'+r.caveats.join(' ')+'</div>':''}}</td><td>${{r.provider}}</td><td><span class="status ${{r.status}}">${{r.status}}</span></td><td class="number">${{fmt(r.score_median)}}</td><td class="number">${{fmt(r.reliability.scheduled_pass_rate)}}%</td><td class="number">${{fmt(r.total_seconds_median)}}s</td><td class="number">${{cost(r)}}</td><td>${{r.replicates===1?'single run':`n=${{r.replicates}} · IQR ${{fmt(r.score_q1)}}–${{fmt(r.score_q3)}} · range ${{fmt(r.score_min)}}–${{fmt(r.score_max)}}`}}</td><td>${{r.run_ids.map(id=>`<a href="run-pages/${{id}}.html">inspect</a>`).join(' · ')}}</td></tr>`).join('');
const taskIds=[...new Set(rows.flatMap(r=>r.run_ids.flatMap(id=>(DATA.tasks[id]||[]).map(t=>t.task_id))))];e('#task-head').innerHTML=`<tr><th>Task</th>${{rows.map(r=>`<th class="number">${{r.display_name}}</th>`).join('')}}</tr>`;e('#task-body').innerHTML=taskIds.map(id=>{{const candidate=Object.values(DATA.tasks).flat().find(t=>t.task_id===id),title=candidate?candidate.title:id;return `<tr><td>${{title}}<div class="muted">${{id}}</div></td>${{rows.map(r=>{{const found=r.run_ids.flatMap(runId=>DATA.tasks[runId]||[]).filter(t=>t.task_id===id);if(!found.length)return '<td class="number muted">not run</td>';const mean=found.reduce((s,t)=>s+Number(t.score),0)/found.length;return `<td class="number" style="background:hsla(${{mean*1.2}},60%,28%,.38)">${{fmt(mean)}}</td>`}}).join('')}}</tr>`}}).join('')||'<tr><td class="empty">No tasks available.</td></tr>';
const failures=new Map();rows.flatMap(r=>r.run_ids).forEach(id=>{{const run=DATA.runs.find(x=>x.run_id===id);Object.entries(run.failure_counts).forEach(([k,v])=>failures.set(k,(failures.get(k)||0)+v))}});e('#failure-summary').innerHTML=[...failures].sort().map(([k,v])=>`<span class="chip">${{k.replaceAll('_',' ')}} · ${{v}}</span>`).join(' ')||'No selected failures.';renderOptions()}}
all('[data-suite]').forEach(b=>b.addEventListener('click',()=>{{suite=b.dataset.suite;selected.clear();all('[data-suite]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));render();updateURL()}}));all('[data-suite]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.suite===suite)));render();
</script>{MENU_SCRIPT}</body></html>'''


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bar(label: str, value: int, total: int, css: str = "") -> str:
    width = value / total * 100 if total else 0
    return f'<div class="bar-row"><span>{esc(label)}</span><div class="track"><div class="fill {css}" style="width:{width:.2f}%"></div></div><span class="number">{value}/{total}</span></div>'


def detail_page(run: dict[str, Any]) -> str:
    run_id = run["run_id"]
    bundle = RUNS_ROOT / run_id
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
    tasks = read_jsonl(bundle / "task-results.jsonl")
    trajectory = read_jsonl(bundle / "trajectory.jsonl")
    exact = summary["exactness"]
    warnings = "".join(f'<div class="warning">{esc(item)}</div>' for item in manifest.get("caveats", []))
    dimensions = "".join(f'<div class="bar-row"><span>{esc(key.replace("_", " ").title())}</span><div class="track"><div class="fill" style="width:{float(value):.2f}%"></div></div><span class="number">{float(value):.1f}</span></div>' for key, value in summary.get("dimensions", {}).items()) or '<p class="muted">No scored dimensions for this suite.</p>'
    task_rows = "".join(f'''<tr><td>{esc(row.get('task_id'))}<div class="muted">{esc(row.get('title',''))}</div></td><td>{esc(row.get('category',''))}</td><td><span class="status {'ok' if row.get('failure_type') == 'pass' else 'partial'}">{esc(row.get('failure_type',''))}</span></td><td class="number task-score">{float(row.get('score',0)):.1f}</td><td class="number">{float(row.get('elapsed_seconds',0)):.2f}s</td><td>{'✓' if row.get('core_passed') else '—'} / {'✓' if row.get('contract_passed') else '—'} / {'✓' if row.get('strict_passed') else '—'}</td></tr>''' for row in tasks)
    stages = "".join(f'''<div class="stage"><strong>{esc(item.get('task_id'))}</strong><div class="muted">sequence {esc(item.get('sequence'))}{' · stage '+esc(item.get('stage')) if item.get('stage') else ''}</div><div>{len(item.get('tool_calls',[]))} tool calls · {len(item.get('mutations',[]))} recorded mutations</div></div>''' for item in trajectory)
    repro = manifest["reproducibility"]
    provenance = "".join(f"<dt>{esc(key.replace('_',' '))}</dt><dd class=\"provenance\">{esc(value)}</dd>" for key, value in repro.items())
    failures = " ".join(f'<span class="chip">{esc(key.replace("_", " "))} · {value}</span>' for key, value in summary["failure_counts"].items())
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(run['display_name'])} · run evidence</title><style>{STYLE}dt{{color:var(--muted);margin-top:8px}}dd{{margin-left:0}}</style></head><body><main>{nav('../')}
<div class="eyebrow">{esc(run['suite'])} · immutable run evidence</div><h1>{esc(run['display_name'])}</h1><p class="lede">{esc(run_id)}</p>{warnings}
<section class="grid"><article class="card third"><div class="metric">{summary['score']:.1f}</div><div class="muted">quality score</div></article><article class="card third"><div class="metric">{summary['reliability']['scheduled_pass_rate']:.1f}%</div><div class="muted">scheduled strict pass rate</div></article><article class="card third"><div class="metric">{summary['efficiency']['total_seconds']:.1f}s</div><div class="muted">recorded total task time</div></article></section>
<section class="grid"><article class="card half"><h2>Exactness funnel</h2><div class="bars">{bar('Core',exact['core'],exact['total'])}{bar('Contract',exact['contract'],exact['total'],'contract')}{bar('Strict',exact['strict'],exact['total'],'strict')}</div></article><article class="card half"><h2>Failure taxonomy</h2><p>{failures}</p><p class="muted">Infrastructure failures remain in the scheduled denominator and are shown separately from model failures.</p></article></section>
<section class="card"><h2>Dimension contribution</h2><div class="bars">{dimensions}</div></section>
<section class="card"><h2>Task evidence</h2><div class="table-wrap"><table><thead><tr><th>Task</th><th>Category</th><th>Outcome</th><th class="number">Score</th><th class="number">Time</th><th>Core / contract / strict</th></tr></thead><tbody>{task_rows}</tbody></table></div></section>
<section class="grid"><article class="card half"><h2>Trajectory</h2><p class="muted">Cumulative stages and tool/state events in execution order.</p>{stages or '<p class="muted">No trajectory events retained.</p>'}</article><article class="card half"><h2>Provenance</h2><dl>{provenance}</dl><p><a href="../runs/{esc(run_id)}/manifest.json">manifest</a> · <a href="../runs/{esc(run_id)}/summary.json">summary</a> · <a href="../runs/{esc(run_id)}/task-results.jsonl">task JSONL</a> · <a href="../runs/{esc(run_id)}/trajectory.jsonl">trajectory JSONL</a> · <a href="../runs/{esc(run_id)}/raw/results.json">raw result</a></p></article></section>
<section class="card"><h2>Interpretation boundary</h2><p>This bundle supports claims about this model under the recorded benchmark contract and execution conditions. It does not establish broad intelligence or performance under a different provider, prompt, tool schema, seed, quantization, or host.</p></section>
</main>{MENU_SCRIPT}</body></html>'''


def build() -> dict[str, Any]:
    registry = json.loads((RUNS_ROOT / "index.json").read_text(encoding="utf-8"))
    OUTPUT.write_text(main_page(registry), encoding="utf-8")
    DETAIL_ROOT.mkdir(exist_ok=True)
    expected = set()
    for run in registry["runs"]:
        path = DETAIL_ROOT / f"{run['run_id']}.html"
        expected.add(path.name)
        path.write_text(detail_page(run), encoding="utf-8")
    for path in DETAIL_ROOT.glob("*.html"):
        if path.name not in expected:
            path.unlink()
    return registry


if __name__ == "__main__":
    data = build()
    print(f"Built evidence explorer for {data['run_count']} runs")
