# Model-research editorial caller migration

## Goal

Use the pinned Gutenberg generator to produce each candidate model's editorial assessment bundle. Keep this repository responsible for candidate selection, assessment inputs, scoring, usage ceilings, run evidence, and research reporting—not production generation prompts or dependency graphs.

## User-visible behavior

- An editorial candidate run invokes the exact pinned Gutenberg revision once for that candidate, using the research-owned assessment source/brief and candidate provider/model.
- The generated candidate bundle, generator manifest, and usage evidence are stored under this repository's run directory and included in immutable research evidence.
- Existing scoring, judgement, readability, assistant/model tests, and comparison reports remain in model research. Candidate scores are research evidence, not production publication or a Gutenberg quality gate.
- The existing `openrouter_batch_mode` option is passed to Gutenberg only for the editorial cohort; it remains false by default. Assistant benchmark remains synchronous.
- Historical website comparison evidence is preserved in `runs/legacy-website-model-comparisons/` with its migration manifest.

## Non-goals

- Do not own, fork, or maintain the SteadyBurn production prompt set or production artifact graph in this repository.
- Do not send candidate output to the website or mark it as a production publication.
- Do not change assistant, latency, model discovery, scoring rubric, judging, or historical comparison result semantics.
- Do not store generated candidate output in Gutenberg; the research run directory is the caller-owned destination.

## Acceptance criteria

1. **Pinned generator:** the research repo contains a Gutenberg submodule at a fixed commit. The runner invokes that exact code from the research worker and never checks out floating `main` at run/deploy time.
2. **Per-candidate generation:** for an editorial cohort job, the worker calls `gutenberg-ralph generate` with the assessment seed/source, focus brief, candidate model/provider, unique caller-owned run output, `--purpose candidate-assessment`, and optional `--batch` only when explicitly requested.
3. **Provenance:** the run evidence identifies the Gutenberg commit/profile, source hash, candidate provider/model, selected tracks, all generated artifact hashes/dependencies, batch flag/status when applicable, and provider-reported token/cost usage.
4. **Assessment preserved:** the existing content scorer/judge and model-comparison publication operate on the generated bundle. Assistant benchmark outputs, assertions, provider safeguards, cost caps, and dashboards are unchanged.
5. **Generator removed from research ownership:** after invocation passes equivalence tests, remove active `operator/harness/automation/burn_pipeline/`, production `prompts/burn/`, and the local burn pipeline template/CLI. Keep benchmark-specific task fixtures and content-scoring/evaluation code.
6. **Archive preservation:** `runs/legacy-website-model-comparisons/` remains byte-identical to the migrated source, with a valid source path/file-count/size/SHA-256 manifest and no collision with existing research runs.
7. **Default/safety:** missing batch flag remains synchronous; assistant-only jobs cannot batch; candidate output is labeled assessment-only; no call writes generated output into Gutenberg or the website.
8. **Verification:** operator tests pass, mocked editorial integration proves invocation arguments and usage/manifest import, prior model assessment/reporting tests pass, and no live provider is called.

## Rollback

- This PR is stacked on archive preservation PR #11 and depends on Gutenberg generator PR #6. Merge PR #11 first, then Gutenberg #6, then this caller PR.
- Roll back by reverting the Gutenberg submodule pin and editorial runner integration. Keep the historical archive copy; the previous implementation remains in Git history and can be restored if needed.
- Do not delete generated candidate run outputs or old assessment evidence during rollback.

## Assumptions

- **ASSUMPTION:** The research-owned `EDITORIAL` seed/brief is a caller input to Gutenberg; it is not imported into Gutenberg. Every candidate model receives the same source/config so comparisons remain controlled.
- **ASSUMPTION:** Candidate-generated files stored under `runs/` are assessment outputs and are committed with the research evidence. The corresponding model-comparison website remains research-owned.
