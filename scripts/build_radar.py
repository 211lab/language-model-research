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

from generate_model_comparison import compile_comparison, dashboard_html, radar_svg  # noqa: E402
from generate_assistant_dashboard import build as build_assistant_dashboard  # noqa: E402


def main() -> None:
    data = compile_comparison(COMPARISON_ROOT)
    if not data["models"]:
        raise RuntimeError("No model comparison records were generated")
    base_html = dashboard_html(data)
    html = base_html.replace(
        "<main><h1>",
        '<main><nav><a href="assistant-benchmark.html">Personal-assistant benchmark</a></nav><h1>',
        1,
    )
    docs_html = base_html.replace(
        "<main><h1>",
        '<main><nav><a href="../../assistant-benchmark.html">Personal-assistant benchmark</a></nav><h1>',
        1,
    )
    if not all(marker in html for marker in ("id=\"tradeoff\"", "id=\"overview-radar\"", "id=\"readability-radar\"", "id=\"quality-values\"", "id=\"price-summary\"")):
        raise RuntimeError("Dashboard output is missing a required visualization")
    radar = radar_svg(data)
    json_output = json.dumps(data, indent=2) + "\n"
    (REPO_ROOT / "index.html").write_text(html, encoding="utf-8")
    (REPO_ROOT / "model-comparison.json").write_text(json_output, encoding="utf-8")
    (REPO_ROOT / "model-comparison-radar.svg").write_text(radar, encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison.html").write_text(docs_html, encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison.json").write_text(json_output, encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison-radar.svg").write_text(radar, encoding="utf-8")
    assistant_data = build_assistant_dashboard(ASSISTANT_ROOT, REPO_ROOT)
    print(
        f"Built editorial dashboard for {len(data['models'])} models and "
        f"assistant dashboard for {assistant_data['model_count']} models"
    )


if __name__ == "__main__":
    main()
