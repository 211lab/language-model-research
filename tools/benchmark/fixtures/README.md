# Synthetic assistant-benchmark fixtures

`base_environment.json` is a fictional information-worker workspace. It
contains projects, tasks, contacts, calendars, email, drafts, documents,
snapshotted web pages, and business tables. No record refers to a real service
or account.

`tasks.json` defines the benchmark prompts and deterministic assertions. The
runner deep-copies the base environment before every task, so mutations never
carry across tasks or models.

Fixture dates are pinned to August 2, 2026. Web results are snapshots rather
than live searches. This is intentional: every model must receive identical
facts, tool results, and starting state.
