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
    (REPO_ROOT / "index.html").write_text(dashboard_html(data), encoding="utf-8")
    (REPO_ROOT / "model-comparison.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (REPO_ROOT / "model-comparison-radar.svg").write_text(radar_svg(data), encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison.html").write_text(dashboard_html(data), encoding="utf-8")
    (COMPARISON_ROOT / "model-comparison.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (COMPARISON_ROOT / "model-comparison-radar.svg").write_text(radar_svg(data), encoding="utf-8")
    print(f"Built dashboard for {len(data['models'])} models")


if __name__ == "__main__":
    main()
