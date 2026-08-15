"""Entrypoints for the command dispatcher and event projection worker."""

from __future__ import annotations

import argparse
import time

from .config import Settings
from .cqrs import CommandDispatcher, OrchestrationPolicy, ProjectionWorker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("dispatcher", "projector", "policy"), required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.role == "dispatcher":
        worker = CommandDispatcher(settings)
        if args.once:
            worker.run_once()
            return 0
        worker.run_forever(settings.cqrs_poll_seconds)
        return 0
    worker = OrchestrationPolicy(settings.database_dsn) if args.role == "policy" else ProjectionWorker(settings.database_dsn)
    while True:
        count = worker.run_once()
        if args.once:
            return 0
        if not count:
            time.sleep(settings.cqrs_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
