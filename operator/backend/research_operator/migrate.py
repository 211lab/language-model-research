"""Apply idempotent operator schema migrations before services start."""

from __future__ import annotations

from pathlib import Path

from psycopg import connect

from .config import Settings


def main() -> int:
    settings = Settings.from_env()
    with connect(settings.database_dsn) as connection, connection.transaction():
        for migration in sorted((settings.operator_root / "db" / "migrations").glob("*.sql")):
            connection.execute(migration.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
