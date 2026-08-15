# Reusable model benchmark tools

This directory contains the complete, dependency-free test harness used to
produce the local model research. It has two complementary batteries:

- `benchmark.py`: latency and first-token measurements using one tiny cold
  request followed by a fixed OpenClaw-style tool-use request.
- `assistant_benchmark.py`: 21 synthetic personal-assistant tasks across
  project management, calendar, email, research, data, English, safety, and
  judgment. Every task uses a fresh fixture copy and deterministic scoring.

The runners use the Python standard library only. Both send seed `42` and the
canonical SteadyBurn seed document by default. The assistant runner imports the
latency runner from this folder, so keep these files together.

## Fixtures

`fixtures/base_environment.json` is a fictional information-worker workspace.
`fixtures/tasks.json` defines the fixed task prompts and assertions. These are
part of the benchmark contract: do not edit either between compared runs. The
fixture README explains the synthetic-data guarantee.

## Run one model

Use the stable wrapper from the repository root. It writes an isolated
timestamped result directory and prevents accidental multi-model concurrency.

```bash
# Titan / llama.cpp (WSL)
LOCAL_AI_BASE_URL=http://titan:11434 \
  bash scripts/run_model_benchmark.sh \
  --model 'your-exact-local-model-id' --cohort local --api openai

# OpenRouter (OpenAI-compatible); use no unload and no artificial load buffer.
OPENROUTER_API_KEY='...' \
  bash scripts/run_model_benchmark.sh \
  --model 'provider/model-name' \
  --base-url https://openrouter.ai/api/v1 \
  --api openai --cohort openrouter --no-unload --settle-seconds 0
```

For a single battery, add `--mode latency` or `--mode assistant`. Use
`--output-dir` to choose a persistent result location. Keep the generated
`results.json` files: they contain prompt hashes, fixture hashes, task hashes,
model identity, seed, timing, tool behavior, and individual task outcomes.

## Run all local chat models

```bash
LOCAL_AI_BASE_URL=http://titan:11434 bash scripts/run_local_assistant_round.sh
```

This is intentionally serial: unload every model, wait ten seconds, send a
primer, complete the selected workload, then move to the next model. It is the
appropriate command for a comparable local cohort, not a remote provider.

## Publish a new local round

Add `--publish-local` to `run_model_benchmark.sh` only when rerunning the exact
published local cohort, or use `run_local_assistant_round.sh`, which invokes
`scripts/process_local_assistant_round.py` after both batteries. The processor
rejects merges unless seed `42`, fixture hash, task hash, SteadyBurn seed, and
selected models agree. It then rebuilds the dashboard.

Remote and local results are both reproducible outputs, but should remain
separate cohorts: remote APIs cannot provide an equivalent unload/cold-load
control, and provider infrastructure is variable.
