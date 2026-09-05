# Immutable benchmark evidence

Every child directory is one model, one suite, and one replicate. Bundles are
append-only: do not replace raw responses or recalculate a published score in
place. Publish a corrected run with explicit lineage instead.

`index.json` is the generated registry consumed by the run explorer. Validate
all artifact hashes and rebuild it from WSL with:

```bash
python3 tools/benchmark/evidence.py validate
python3 tools/benchmark/evidence.py registry
```

The initial 18 bundles normalize the completed August 12 Titan cohort: nine
assistant runs and nine corresponding latency runs. Their manifests clearly
identify them as historical imports and preserve the original per-model raw
results. Editorial evidence appears after that suite is executed; an empty
editorial view is preferable to mixing it with unrelated content-rubric data.
