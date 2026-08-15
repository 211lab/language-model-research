# Language Model Research Operator

This directory turns the research repository into one operator-focused monorepo:

- `frontend` is the browser UI for reviewing existing results and adding model runs.
- `backend` is the API and PostgreSQL-backed durable queue.
- `worker-local` selects/downloads a GGUF with the existing llama switcher, then runs the selected editorial and/or assistant cohorts.
- `worker-remote` runs OpenRouter research only after a small Luna harness preflight succeeds.
- `harness` is the versioned editorial pipeline, prompts, and scoring rubric used by the worker. It is kept beside the assistant fixture harness already in this repository.
- `db` is the durable job, event, and run-record database.
- `discovery` checks the existing local provider daily for eligible text GGUFs.
- `publisher` copies each completed cohort into an isolated clone, rebuilds the static pages, and pushes a focused commit to `main`.
- `command-dispatcher` accepts durable asynchronous write commands; `orchestration-policy` turns completed facts into idempotent follow-up commands; `projection-worker` builds query models from immutable events.
- `event-history` is a separate read-only container for live event replay at `http://localhost:8091`.

The generated research pages remain the repository root's `index.html`, `assistant-benchmark.html`, and supporting data files. A completed worker creates a durable publication job. The publisher then copies the validated cohort output into an isolated clone, rebuilds the static pages, and pushes its own focused commit to `main`.

## Start the platform from WSL

```bash
cd /mnt/c/Users/Dave/Documents/_code/momentum-institute/language-model-research-main/operator
cp .env.example .env
# Fill OPENROUTER_API_KEY only when remote work is intentionally enabled.
docker compose --env-file .env -f compose.yaml up --build
```

Open `http://localhost:8090`. The API is also available on `http://localhost:8088` by default.

## CQRS event history

All operator writes now enter the durable command queue. The dispatcher validates a command and records immutable PostgreSQL domain events; the projection worker independently rebuilds read models from the global event cursor. The current queue tables remain compatibility projections while the CQRS read models are introduced. PostgreSQL notifications only wake consumers: replay always reads the stored event sequence, so a container restart cannot lose history.

Use `http://localhost:8091` for live event history. It supports cursor replay through `/api/events`, live Server-Sent Events at `/api/events/stream`, per-run timelines, and projection checkpoint health. Events are retained indefinitely. The history container is read-only and has no inference-provider, switcher, Docker-socket, or model-cache access.

The default local endpoint remains `http://localhost:11434`. `worker-local` uses host networking specifically so the existing endpoint and the operator's existing activity view remain unchanged; it does not publish or remap port `11434`.

## Daily discovery and publication

`discovery` reads only `GET /v1/models` from the configured local endpoint. It ignores embeddings and image-only models, records each exact GGUF repository/file/revision, and skips identities already measured for the current harness. It never changes the endpoint, port, or provider configuration.

Set `DISCOVERY_IDLE_ACKNOWLEDGED=true` only after confirming the endpoint is idle in the existing activity view. This is deliberately false by default: a model list cannot prove that llama.cpp is not actively processing tokens. With the acknowledgement enabled, eligible local models are queued for both editorial and assistant cohorts one at a time through the existing local-inference lease. The worker still has no force-stop operation.

Every successful cohort creates a publication job. `publisher` uses `PUBLISH_REPOSITORY_URL`, the read-only `PUBLISH_SSH_DIR`, and the existing WSL `PUBLISH_GIT_CONFIG` to make a shallow isolated clone, rebuild the static outputs, and push one commit using the existing configured Git author identity. It retries once after rebasing if `main` moved. A failed publication is marked blocked for review; it never reruns inference. If direct publication is disabled, completed publication jobs remain queued and can resume later without repeating a test.

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
