#!/usr/bin/env python3
"""Build the root static dashboard and supporting comparison artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPARISON_ROOT = REPO_ROOT / "docs" / "model-comparisons"
ASSISTANT_ROOT = REPO_ROOT / "docs" / "assistant-benchmark"
sys.path.insert(0, str(COMPARISON_ROOT))
sys.path.insert(0, str(ASSISTANT_ROOT))

from generate_model_comparison import compile_comparison, dashboard_html, radar_svg, write_text_lf  # noqa: E402
from generate_assistant_dashboard import build as build_assistant_dashboard  # noqa: E402
from build_run_explorer import build as build_run_explorer  # noqa: E402


def add_site_navigation(html: str, home_href: str, assistant_href: str, runs_href: str, methodology_href: str, include_assistant_card: bool) -> str:
    styles = '''.site-nav{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}.site-brand{color:#f8fafc;text-decoration:none;font-weight:750}.menu-button{margin-left:auto;border:1px solid #38506f;background:#111a2d;color:#e5e7eb;border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}.menu-links{display:flex;gap:14px;align-items:center}.menu-links a{text-decoration:none}.research-link{margin:20px 0}.research-link a{display:inline-block;margin-top:6px}@media(max-width:680px){main{padding:18px}.site-nav{position:relative}.menu-links{display:none;position:absolute;right:0;top:42px;z-index:10;min-width:230px;flex-direction:column;align-items:stretch;padding:12px;border:1px solid #263349;border-radius:10px;background:#111a2d;box-shadow:0 12px 28px #0008}.menu-links.is-open{display:flex}.menu-links a{padding:7px}}@media(min-width:681px){.menu-button{display:none}}'''
    nav = f'''<nav class="site-nav" aria-label="Primary"><a class="site-brand" href="{home_href}">Language model research</a><button class="menu-button" type="button" aria-expanded="false" aria-controls="site-menu">Menu ☰</button><div class="menu-links" id="site-menu"><a href="{home_href}">Editorial research</a><a href="{assistant_href}">Assistant benchmark</a><a href="{runs_href}">Run explorer</a><a href="{methodology_href}">Methodology</a></div></nav>'''
    card = ''
    if include_assistant_card:
        card = f'''<section class="card research-link"><strong>Personal-assistant benchmark</strong><div class="note">Compare local models on synthetic information-worker tasks, tool use, cold-load time, and an OpenClaw-style request.</div><a href="{assistant_href}">Open the assistant benchmark →</a></section>'''
    menu_script = '''<script>const menuButton=document.querySelector('.menu-button'),menu=document.querySelector('.menu-links');menuButton.addEventListener('click',()=>{const open=menu.classList.toggle('is-open');menuButton.setAttribute('aria-expanded',String(open))});</script>'''
    html = html.replace("</style>", styles + "</style>", 1)
    html = html.replace("<main><h1>", "<main>" + nav + "<h1>", 1)
    if card:
        html = html.replace('</section>\n<h2>Cost versus quality', '</section>' + card + '\n<h2>Cost versus quality', 1)
    return html.replace("</body>", menu_script + "</body>", 1)


def main() -> None:
    data = compile_comparison(COMPARISON_ROOT)
    if not data["models"]:
        raise RuntimeError("No model comparison records were generated")
    base_html = dashboard_html(data)
    html = add_site_navigation(base_html, "index.html", "assistant-benchmark.html", "research-runs.html", "methodology.html", True)
    docs_html = add_site_navigation(base_html, "../../index.html", "../../assistant-benchmark.html", "../../research-runs.html", "../../methodology.html", False)
    if not all(marker in html for marker in ("id=\"model-browser-title\"", "id=\"model-search\"", "data-selection-preset=\"local-frontier\"", "id=\"tradeoff\"", "id=\"overview-radar\"", "id=\"readability-radar\"", "id=\"quality-values\"", "id=\"price-summary\"")):
        raise RuntimeError("Dashboard output is missing a required visualization")
    radar = radar_svg(data)
    json_output = json.dumps(data, indent=2) + "\n"
    write_text_lf(REPO_ROOT / "index.html", html)
    write_text_lf(REPO_ROOT / "model-comparison.json", json_output)
    write_text_lf(REPO_ROOT / "model-comparison-radar.svg", radar)
    write_text_lf(COMPARISON_ROOT / "model-comparison.html", docs_html)
    write_text_lf(COMPARISON_ROOT / "model-comparison.json", json_output)
    write_text_lf(COMPARISON_ROOT / "model-comparison-radar.svg", radar)
    assistant_data = build_assistant_dashboard(ASSISTANT_ROOT, REPO_ROOT)
    evidence_data = build_run_explorer()
    print(
        f"Built editorial dashboard for {len(data['models'])} models and "
        f"assistant dashboard for {assistant_data['model_count']} models; "
        f"evidence explorer for {evidence_data['run_count']} runs"
    )


if __name__ == "__main__":
    main()
