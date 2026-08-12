# Personal-assistant benchmark

This dataset compares nine local GGUF chat models from the perspective of a
tool-using personal assistant and information worker. It is intentionally
separate from the repository's SteadyBurn editorial-content score: the two
scores measure different work and must not be merged or treated as equivalent.

## Protocol

- Run date: 2026-08-02
- Runtime: llama.cpp behind llama-swap on one local host
- Models: nine chat models; the discovered image-only model was excluded
- Workload: 21 synthetic project, calendar, email, research, data, English,
  safety, judgment, and multi-source tasks per model (189 task runs total)
- Isolation: one model loaded and one request active at a time
- Lifecycle: explicit unload, 10 seconds with no model resident, warm one model,
  run every task with a fresh fixture and conversation, then unload
- Sampling: temperature 0, seed 42, maximum 768 tokens per model turn
- Fixture SHA-256: `ea2601bcb637a9c66563e91015f15a007a0a06f7d88532ec218c8c178903efb9`
- Task-suite SHA-256: `907017aa0d29639967cd0c0702764b73e7cc8ebbf254625fcc07b63e13b4428e`

The assistant score is a weighted total of outcome (30%), tool use (25%),
grounding (15%), state management (10%), English (10%), safety (5%), and
efficiency (5%). Time is reported separately and does not affect intelligence.

`partial` means at least one task hit the fixed six-turn tool-loop ceiling or
returned an API error. Every scheduled task is retained in the aggregate. The
Qwythos run returned HTTP 502 for its final 12 tasks, so its aggregate is useful
as a reliability result but not as a clean capability estimate.

## Latency companion test

The same models were also tested sequentially with a tiny cold-load request and
a fixed warm OpenClaw-style tool-selection request. `latency_total_seconds` is
the sum of those two full request durations. TTFT is preserved separately.

## Rebuild

From the repository root:

```powershell
python scripts/build_radar.py
```

The build writes the compiled JSON, dashboard, and four SVG snapshots both here
and at the repository root. `model-results.csv` is the source of truth.
