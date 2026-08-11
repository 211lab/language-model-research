#!/usr/bin/env python3
"""Build the root static dashboard and supporting comparison artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPARISON_ROOT = REPO_ROOT / "docs" / "model-comparisons"
sys.path.insert(0, str(COMPARISON_ROOT))

from generate_model_comparison import compile_comparison, dashboard_html, radar_svg  # noqa: E402


def main() -> None:
    data = compile_comparison(COMPARISON_ROOT)
    if not data["models"]:
        raise RuntimeError("No model comparison records were generated")
    html = dashboard_html(data)
    if not all(marker in html for marker in ("id=\"tradeoff\"", "id=\"overview-radar\"", "id=\"readability-radar\"", "id=\"quality-values\"", "id=\"price-summary\"")):
        raise RuntimeError("Dashboard output is missing a required visualization")
    radar = radar_svg(data)
    json_output = json.dumps(data, indent=2) + "\n"
    (REPO_ROOT / "index.html").write_text(html, encoding="utf-8")
    (REPO_ROOT / "model-comparison.json").write_text(json_output, encoding="utf-8")
    (REPO_ROOT / "model-comparison-radar.svg").write_text(radar, encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison.html").write_text(html, encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison.json").write_text(json_output, encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison-radar.svg").write_text(radar, encoding="utf-8")
    print(f"Built dashboard for {len(data['models'])} models")


if __name__ == "__main__":
    main()
