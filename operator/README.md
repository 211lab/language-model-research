# Language Model Research Operator

This directory turns the research repository into one operator-focused monorepo:

- `frontend` is the browser UI for reviewing existing results and adding model runs.
- `backend` is the API and PostgreSQL-backed durable queue.
- `worker-local` selects/downloads a GGUF with the existing llama switcher, then runs the selected editorial and/or assistant cohorts.
- `worker-remote` runs OpenRouter research only after a small Luna harness preflight succeeds.
- `harness` is the versioned editorial pipeline, prompts, and scoring rubric used by the worker. It is kept beside the assistant fixture harness already in this repository.
- `db` is the durable job, event, and run-record database.

The generated research pages remain the repository root's `index.html`, `assistant-benchmark.html`, and supporting data files. A completed worker merges validated output, recalculates readability and cost data, and runs `scripts/build_radar.py`. It does **not** commit or push generated research: that remains an explicit review step.

## Start the platform from WSL

```bash
cd /mnt/c/Users/Dave/Documents/_code/momentum-institute/language-model-research-main/operator
cp .env.example .env
# Fill OPENROUTER_API_KEY only when remote work is intentionally enabled.
docker compose --env-file .env -f compose.yaml up --build
```

Open `http://localhost:8090`. The API is also available on `http://localhost:8088` by default.

The default local endpoint remains `http://localhost:11434`. `worker-local` uses host networking specifically so the existing endpoint and the operator's existing activity view remain unchanged; it does not publish or remap port `11434`.

## Queue behavior

Selecting Editorial, Assistant, or both makes one durable job per cohort. The jobs retain the exact provider/model source and are visible with line-by-line worker events in the UI.

### Local GGUF model

For a local submission, enter the Hugging Face repository and optionally a GGUF filename. With no filename, the existing `switch-llama-model.sh` performs the real selection: it reads the GGUF metadata, totals every shard, selects the preferred quant that fits the current VRAM budget, downloads it if necessary, activates it, and records `sourceRepo`, `sourceFile`, and revision.

The UI requires an explicit acknowledgement that the inference endpoint is idle. The local worker never offers a force-stop action. It does not pass `--api-base` or set `LLAMA_API_BASE`, so it preserves the switcher's configured endpoint. A local run also holds the configured buffer before benchmark traffic begins. The result records the repository, GGUF filename, requested revision, and the resolved Hugging Face snapshot hash, so a later repository update cannot silently replace a measured quant.

If a model is above the normal GGUF budget, the UI requires an explicit capacity override. That maps to `LLAMA_MODEL_MAX_GIB` only for that switch request; no global safety value is changed.

### OpenRouter model

For OpenRouter, the UI requires an exact `provider/model` ID, an explicit paid-run confirmation, and a cost ceiling per selected cohort. Every fresh versioned harness contract first queues a single-task Luna validation job. The paid editorial and/or assistant jobs are dependent on that validation; they become blocked if Luna does not complete it. A matching successful Luna validation is reused for 24 hours, and concurrent paid submissions wait on the same queued or running validation instead of buying duplicate diagnostics.

The assistant suite keeps seed `42` and the fixed 768-token per-turn cap. The editorial scorer records the evidence model, Luna judge, and tie-break model with the result. The Luna preflight is capped separately by `LUNA_PREFLIGHT_MAX_COST_USD` (default `$0.10`) and exercises both the streaming latency probes plus one assistant task. Target assistant work writes one provider-usage ledger across latency and every task turn; if a reply lacks `usage.cost` or crosses the selected ceiling, no later paid request is sent and the incomplete result is not published. Remote editorial generation uses the same fail-closed rule through `BURN_MAX_COST_USD`.

## Scale workers

Remote jobs have no shared local inference state, so they can scale horizontally:

```bash
docker compose --env-file .env -f compose.yaml up -d --scale worker-remote=3
```

`worker-local` has a durable `local-inference` lease in PostgreSQL. It can be deployed separately, but it deliberately executes only one local job at a time even if accidentally scaled, because one llama.cpp endpoint cannot safely serve competing model switches.

## Required WSL mounts

Set these in `.env` to the paths already used by the local switcher:

```dotenv
LLAMA_SWITCHER_ROOT=/home/wsl/llama-model-switcher
HF_CACHE_ROOT=/home/wsl/.cache/huggingface/hub
DOCKER_SOCKET=/var/run/docker.sock
```

If a selected Hugging Face repository is gated, add `HF_TOKEN` to the same `.env`; the local worker reads it when a download needs authentication, and it is never written to a research result.

Only `worker-local` gets write access to the switcher directory, Hugging Face cache, and Docker socket. The API only mounts the switcher read-only to populate the model picker. This separation lets the frontend and remote workers remain independently scalable.

## Verification

From the repository root:

```bash
PYTHONPATH=operator/backend python -m unittest discover -s operator/tests -v
docker compose --env-file operator/.env -f operator/compose.yaml config
```

The unit tests are offline. They verify the cohort, cost-confirmation, exact-local-identity, and fixed-token contracts; they never call a model provider or change the local endpoint.
