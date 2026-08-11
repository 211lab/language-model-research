# Language Model Research

Research data, scoring artifacts, and comparisons of language models used in the
SteadyBurn content pipeline.

## Interactive radar

Open the [interactive model comparison radar](./) to compare readability,
quality, and cost across the recorded model runs. The dashboard is a static
HTML page with the comparison data embedded in the page; it does not require a
server or an API key.

The first chart is the decision view: a cost-versus-quality scatter plot with
the observed Pareto frontier. Models without captured usage logs remain in the
quality and readability views, but are explicitly marked as price unavailable
and are excluded from the priced frontier.

The source bundle lives in [`docs/model-comparisons`](docs/model-comparisons).
The generated JSON and SVG snapshot are also available at the repository root.

## Rebuild

From the repository root, run:

```powershell
python scripts/build_radar.py
```

The GitHub Pages workflow rebuilds and publishes the root dashboard whenever
the comparison data, generator, rubric, or build script changes.
