#!/usr/bin/env bash
# Run the two local cohorts serially, then publish only a validated merge.
set -euo pipefail
export PYTHONUNBUFFERED=1

research_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tool_root="$research_root/tools/benchmark"
endpoint=${LOCAL_AI_BASE_URL:-http://titan:11434}
stamp=$(date +%Y%m%d-%H%M%S)
round_root="${BENCHMARK_RESULTS_ROOT:-$research_root/results}/local-assistant-$stamp"
latency_dir="$round_root/latency"
assistant_dir="$round_root/assistant"
steadyburn_seed="$research_root/docs/model-comparisons/google-gemini-3-5-flash-lite/2026-08-07-master-your-tasks-prioritization-and-time-management/SEED.md"

mkdir -p "$round_root"
printf 'Round: %s\nEndpoint: %s\nSeed: 42\n' "$round_root" "$endpoint"

# benchmark.py unloads, waits 10 seconds, then sends its fixed tiny primer before
# the OpenClaw-style latency request. It runs every model sequentially.
python3 "$tool_root/benchmark.py" \
  --base-url "$endpoint" --api openai --seed 42 --settle-seconds 10 \
  --steadyburn-seed "$steadyburn_seed" \
  --exclude 'embedding|image' \
  --output-dir "$latency_dir"

# assistant_benchmark.py unloads, waits 10 seconds, then sends READY as a primer
# after every model switch before starting its 21 fresh-fixture assistant tasks.
python3 "$tool_root/assistant_benchmark.py" \
  --base-url "$endpoint" --run-label local --seed 42 --settle-seconds 10 \
  --steadyburn-seed "$steadyburn_seed" \
  --exclude 'embedding|image' \
  --output-dir "$assistant_dir"

python3 "$research_root/scripts/process_local_assistant_round.py" \
  --assistant-results "$assistant_dir/results.json" \
  --latency-results "$latency_dir/results.json" \
  --seed 42 --build
