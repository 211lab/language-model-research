# Language Model Research

Research data, scoring artifacts, and comparisons of language models used in the
SteadyBurn content pipeline.

## Model-first interactive research

Open the [interactive model comparison](./) to start with a searchable model
browser, then compare readability, quality, and cost across the selected runs.
The Local, API, observed-frontier, and Local + frontier shortcuts make it easy
to review a self-hosted baseline against the strongest measured alternatives.
The dashboard is a static HTML page with the comparison data embedded in the
page; it does not require a server or an API key.

The first chart is the decision view: a cost-versus-quality scatter plot with
the observed Pareto frontier. Models without captured usage logs remain in the
quality and readability views, but are explicitly marked as price unavailable
and are excluded from the priced frontier.

The source bundle lives in [`docs/model-comparisons`](docs/model-comparisons).
The generated JSON and SVG snapshot are also available at the repository root.

## Personal-assistant benchmark

The [personal-assistant comparison](assistant-benchmark.html) adds nine local
GGUF models tested on 21 synthetic information-worker tasks, plus cold-load and
OpenClaw-style latency measurements. Its score is kept separate from the
SteadyBurn editorial-content score because the two suites measure different
capabilities. Source data and methodology live in
[`docs/assistant-benchmark`](docs/assistant-benchmark).

## Evidence explorer

The [run explorer](research-runs.html) is the audit-oriented view of this
research. Each displayed result is backed by an immutable per-model bundle in
[`runs/`](runs), containing the raw result, normalized task records, ordered
trajectory, configuration, lineage, manifest, and SHA-256 artifact hashes.
The explorer labels comparisons as directly comparable, directional, or not
comparable from their benchmark-contract and execution metadata.

The benchmark batteries and synthetic fixtures are versioned in
[`tools/benchmark`](tools/benchmark). They support local llama.cpp endpoints
and OpenRouter through provider profiles, run strictly serially, and issue a
primer after each local model switch before measured work begins.

## Rebuild

From the repository root, run:

```bash
# Run from WSL.
python3 scripts/build_radar.py
```

The GitHub Pages workflow rebuilds and publishes the root dashboard whenever
the comparison data, evidence bundles, generator, rubric, or build script
changes.
