# Reusable model benchmark tools

This directory contains the complete, dependency-free test harness and
evidence pipeline used to produce the model research. It has three independent
batteries:

- `benchmark.py`: latency and first-token measurements using one tiny cold
  request followed by a fixed OpenClaw-style tool-use request.
- `assistant_benchmark.py`: 21 synthetic personal-assistant tasks across
  project management, calendar, email, research, data, English, safety, and
  judgment. Every task uses a fresh fixture copy and deterministic scoring.
- `editorial_benchmark.py`: four isolated editorial tasks and one five-stage
  cumulative production trajectory covering briefing, outlining, drafting,
  correction, sourcing, safety, and professional English.

`pipeline.py` is the supported entry point. It discovers models, enforces
serial execution, runs one model to completion before the next, and invokes
`evidence.py` to create immutable per-model bundles and rebuild the registry.

The runners use the Python standard library only. All three send seed `42` and
the canonical SteadyBurn seed document by default. The intelligence runners
import shared endpoint helpers from this folder, so keep these files together.

## Fixtures

`fixtures/base_environment.json` and `fixtures/tasks.json` define the fictional
assistant workspace and its tasks. `fixtures/editorial_sources.json` and
`fixtures/editorial_tasks.json` define a separate fictional editorial source
package and task battery. These files are benchmark-contract inputs: changing
one creates a new comparability cohort.

Both batteries receive the canonical SteadyBurn seed document and sampling
seed 42 by default. “Same seed” therefore means both the same seed document
hash and the same numeric sampling seed.

## Run one model

Use the stable wrapper from WSL. It creates evidence bundles directly and
prevents accidental multi-model concurrency.

```bash
# Titan / llama.cpp (WSL)
bash scripts/run_evidence_benchmark.sh \
  --profile titan-local \
  --model 'your-exact-local-model-id' \
  --suite all

# OpenRouter (OpenAI-compatible); use no unload and no artificial load buffer.
OPENROUTER_API_KEY='...' bash scripts/run_evidence_benchmark.sh \
  --profile openrouter \
  --model 'provider/model-name' \
  --suite assistant
```

For a single battery, use `--suite latency`, `--suite assistant`, or
`--suite editorial`. Use `--replicates 3` or more to estimate run-to-run
variation. OpenRouter models can run either intelligence battery; hosted
latency is retained but is not presented as equivalent to lifecycle-controlled
local cold-load latency.

For paid providers, set a fail-closed ceiling and require reported costs:

```bash
OPENROUTER_API_KEY='...' bash scripts/run_evidence_benchmark.sh \
  --profile openrouter \
  --model 'provider/model-name' \
  --suite assistant \
  --max-cost-usd 5 \
  --require-reported-cost
```

The shared JSONL ledger enforces the ceiling across serial suites and resumed
stages. Each evidence bundle records the cost added by its own suite; the
configuration also retains cumulative round spend. Local runs record `$0` in
provider charges while explicitly excluding hardware, electricity, and labor.

## Run all local chat models

```bash
bash scripts/run_local_evidence_round.sh
```

This is intentionally serial: unload every model, wait ten seconds, send a
primer, complete all selected suites, then move to the next model. Progress
messages include model, replicate, suite, and overall suite-run positions.

## Validate and publish

```bash
python3 tools/benchmark/evidence.py validate
python3 tools/benchmark/evidence.py registry --check
python3 scripts/build_radar.py
```

Never edit a bundle after publication. A correction is a new bundle with
lineage to the superseded run. The generated registry and dashboard may be
rebuilt; the evidence itself is append-only.

## Bundle contract

Each directory under `runs/` contains:

- `manifest.json`: system, provider/runtime, seed/replicate, lifecycle,
  comparability hashes, caveats, counts, and artifact hashes.
- `summary.json`: quality, core/contract/strict exactness funnel, scheduled and
  evaluated pass rates, timing, dimensions, and failure taxonomy.
- `task-results.jsonl` and `trajectory.jsonl`: normalized outcomes and ordered
  tool/state or cumulative editorial evidence.
- `raw/results.json`, `configuration.json`, and `lineage.json`: auditable source
  output and transformation provenance.

Remote and local results are both reproducible outputs, but should remain
separate cohorts: remote APIs cannot provide an equivalent unload/cold-load
control, and provider infrastructure is variable.
