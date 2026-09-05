#!/usr/bin/env bash
# Discover Titan chat models and run the complete evidence battery serially.
set -euo pipefail
export PYTHONUNBUFFERED=1

research_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

exec python3 "$research_root/tools/benchmark/pipeline.py" run \
  --profile titan-local \
  --all-models \
  --exclude 'embedding|image' \
  --suite all \
  --replicates "${BENCHMARK_REPLICATES:-1}" \
  --seed 42 \
  --output-root "$research_root/runs"
