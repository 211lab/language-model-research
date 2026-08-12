# DeepSeek and Luna judge comparison

## What changed

The editorial scoring rubric, deterministic measurements, evidence verification, three judge passes, median selection, and tie-break rule stayed the same. The cross-run local editorial bundles were scored with `openai/gpt-5.6-luna` for evidence extraction, all three judge passes, and tie-breaking.

That is a change to the evaluator stack, not only to the final judge. A Luna score can therefore reflect differences in evidence extraction, judging, and tie-breaking together.

## Factual coverage in the current records

The scoring cache and telemetry provide the following coverage:

| Record group | Evaluator evidence | Evaluator judge / tie-break | Complete source snapshots | Notes |
| --- | --- | --- | ---: | --- |
| Earlier editorial scoring | DeepSeek V4 Flash | DeepSeek V4 Flash or V4 Pro | 2 | Sol and Terra have complete DeepSeek-backed artifact records; an earlier Claude Opus DeepSeek attempt is incomplete. |
| Local editorial cross-run | GPT-5.6 Luna | GPT-5.6 Luna | 8 | Cydonia, Dolphin, Gemma 12B, Gemma E4B, Qwen 27B, Qwen 35B, and both Unsloth variants. |
| Exact same source under both stacks | — | DeepSeek and Luna | 0 | No complete same-content pair is currently available. |

The current cache contains no complete immutable content snapshot with both a DeepSeek score and a Luna score. Consequently, the published quality differences between the earlier OpenRouter rows and the newer local rows cannot be attributed to the judge change: model output, cohort, and sometimes evaluator stack all differ.

The `CONTENT_SCORE.json` files predate a formal evaluator-provenance field, so judge provenance is reconstructed from the scoring telemetry and cache keys. Future score artifacts should record the evidence, judge, and tie-break model directly.

## Same-task comparison that is available

The assistant benchmark gives DeepSeek models and Luna the same 21 seeded tasks, but these rows measure the models as task performers. They are not judgments made by DeepSeek or Luna and must not be used as judge calibration.

| Assistant model | Score | Tasks passed | Status |
| --- | ---: | ---: | --- |
| GPT-5.6 Luna | 70.915 | 15/21 | partial |
| DeepSeek V4 Flash | 71.374 | 13/21 | partial |
| DeepSeek V4 Pro | 64.484 | 10/21 | partial |
| DeepSeek V3.2 | 53.054 | 6/21 | partial |

These are factual same-suite model comparisons. They do not tell us whether Luna is a more lenient or stricter editorial evaluator.

## Required paired comparison before claiming judge impact

To measure judge impact, preserve one immutable content snapshot and score it twice under the same rubric and deterministic metrics. Record the full evaluator stack for each run. The cleanest isolation is to hold evidence extraction and tie-breaking constant while changing only the three judge passes; a broader stack comparison may change evidence extraction and tie-breaking too and must be labeled accordingly.

Until that paired run exists, the methodology treats Luna-scored and DeepSeek-scored editorial values as separate scoring regimes and avoids recalibrating or ranking one regime against the other as though they were directly interchangeable.
