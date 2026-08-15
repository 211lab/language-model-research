#!/usr/bin/env bash
# Run one exact model through the reusable latency and/or assistant batteries.
set -euo pipefail
export PYTHONUNBUFFERED=1

research_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tool_root="$research_root/tools/benchmark"
seed_document="$research_root/docs/model-comparisons/google-gemini-3-5-flash-lite/2026-08-07-master-your-tasks-prioritization-and-time-management/SEED.md"

mode=both
base_url=${LOCAL_AI_BASE_URL:-http://titan:11434}
api=auto
api_key=${LOCAL_AI_API_KEY:-${OPENROUTER_API_KEY:-}}
cohort=local
model=
output_dir=
settle_seconds=10
timeout=900
no_unload=false
publish_local=false

usage() {
  cat <<'EOF'
Usage: run_model_benchmark.sh --model MODEL [options]

Run the same seeded latency and assistant batteries for one exact model.

Options:
  --model ID              Required exact provider model ID.
  --base-url URL          OpenAI-compatible endpoint (default: LOCAL_AI_BASE_URL or titan).
  --api auto|openai|ollama
  --api-key KEY           Prefer an environment variable over this option.
  --cohort NAME           Metadata label, e.g. local or openrouter (default: local).
  --mode latency|assistant|both
  --output-dir DIR        Default: results/<cohort>-<model>-<timestamp>.
  --settle-seconds N      Default: 10. Use 0 for remote APIs.
  --timeout N             Per request timeout in seconds (default: 900).
  --no-unload             Required for remote providers without a lifecycle API.
  --publish-local         Validate, merge, and rebuild the local research dashboard.
  --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model|--base-url|--api|--api-key|--cohort|--mode|--output-dir|--settle-seconds|--timeout)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --model) model=$2 ;; --base-url) base_url=$2 ;; --api) api=$2 ;; --api-key) api_key=$2 ;;
        --cohort) cohort=$2 ;; --mode) mode=$2 ;; --output-dir) output_dir=$2 ;;
        --settle-seconds) settle_seconds=$2 ;; --timeout) timeout=$2 ;;
      esac
      shift 2 ;;
    --no-unload) no_unload=true; shift ;;
    --publish-local) publish_local=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$model" ]] || { echo "--model is required" >&2; usage >&2; exit 2; }
[[ "$mode" == latency || "$mode" == assistant || "$mode" == both ]] || { echo "--mode must be latency, assistant, or both" >&2; exit 2; }
[[ "$api" == auto || "$api" == openai || "$api" == ollama ]] || { echo "--api must be auto, openai, or ollama" >&2; exit 2; }
[[ "$publish_local" == false || "$cohort" == local ]] || { echo "--publish-local requires --cohort local" >&2; exit 2; }

stamp=$(date +%Y%m%d-%H%M%S)
round_root=${output_dir:-"$research_root/results/$cohort-$stamp"}
latency_dir="$round_root/latency"
assistant_dir="$round_root/assistant"
mkdir -p "$round_root"

common=(--base-url "$base_url" --model "$model" --seed 42 --timeout "$timeout" --steadyburn-seed "$seed_document")
unload=()
[[ "$no_unload" == true ]] && unload=(--no-unload)
key=()
[[ -n "$api_key" ]] && key=(--api-key "$api_key")

printf 'Model: %s\nCohort: %s\nEndpoint: %s\nSeed: 42\nOutput: %s\n' "$model" "$cohort" "$base_url" "$round_root"

if [[ "$mode" == latency || "$mode" == both ]]; then
  python3 "$tool_root/benchmark.py" "${common[@]}" --api "$api" --settle-seconds "$settle_seconds" "${unload[@]}" "${key[@]}" --output-dir "$latency_dir"
fi
if [[ "$mode" == assistant || "$mode" == both ]]; then
  python3 "$tool_root/assistant_benchmark.py" "${common[@]}" --run-label "$cohort" --settle-seconds "$settle_seconds" "${unload[@]}" "${key[@]}" --output-dir "$assistant_dir"
fi
if [[ "$publish_local" == true ]]; then
  [[ "$mode" == both ]] || { echo "--publish-local requires --mode both" >&2; exit 2; }
  python3 "$research_root/scripts/process_local_assistant_round.py" \
    --assistant-results "$assistant_dir/results.json" \
    --latency-results "$latency_dir/results.json" --seed 42 --build
fi
