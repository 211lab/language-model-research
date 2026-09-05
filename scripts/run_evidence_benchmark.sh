#!/usr/bin/env bash
# Run one exact model through the unified evidence pipeline.
set -euo pipefail
export PYTHONUNBUFFERED=1

research_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
model=
profile=titan-local
suite=all
replicates=1
seed=42
output_root="$research_root/runs"
max_tasks=
disable_thinking=false
max_cost_usd=
usage_log=
require_reported_cost=false

usage() {
  printf '%s\n' \
    'Usage: run_evidence_benchmark.sh --model MODEL [options]' \
    '' \
    'Run one exact model through serial, seeded benchmark suites and package' \
    'each result as an immutable evidence bundle.' \
    '' \
    '  --model ID                  Required exact provider model ID.' \
    '  --profile NAME              titan-local or openrouter (default: titan-local).' \
    '  --suite assistant|editorial|latency|all (default: all).' \
    '  --replicates N              Independent serial runs (default: 1).' \
    '  --seed N                    Shared sampling seed (default: 42).' \
    '  --output-root DIR           Evidence bundle directory (default: runs/).' \
    '  --max-tasks N               Assistant smoke test only; do not publish.' \
    '  --disable-thinking          Send enable_thinking=false.' \
    '  --max-cost-usd N            Shared provider-reported round ceiling.' \
    '  --usage-log PATH            Shared provider-cost JSONL ledger.' \
    '  --require-reported-cost     Stop if a paid response omits usage.cost.' \
    '  --help'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model|--profile|--suite|--replicates|--seed|--output-root|--max-tasks|--max-cost-usd|--usage-log)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --model) model=$2 ;; --profile) profile=$2 ;; --suite) suite=$2 ;;
        --replicates) replicates=$2 ;; --seed) seed=$2 ;; --output-root) output_root=$2 ;;
        --max-tasks) max_tasks=$2 ;;
        --max-cost-usd) max_cost_usd=$2 ;; --usage-log) usage_log=$2 ;;
      esac
      shift 2 ;;
    --disable-thinking) disable_thinking=true; shift ;;
    --require-reported-cost) require_reported_cost=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$model" ]] || { echo "--model is required" >&2; usage >&2; exit 2; }
command=(python3 "$research_root/tools/benchmark/pipeline.py" run --profile "$profile" --model "$model" --suite "$suite" --replicates "$replicates" --seed "$seed" --output-root "$output_root")
[[ -n "$max_tasks" ]] && command+=(--max-tasks "$max_tasks")
[[ "$disable_thinking" == true ]] && command+=(--disable-thinking)
[[ -n "$max_cost_usd" ]] && command+=(--max-cost-usd "$max_cost_usd")
[[ -n "$usage_log" ]] && command+=(--usage-log "$usage_log")
[[ "$require_reported_cost" == true ]] && command+=(--require-reported-cost)
exec "${command[@]}"
