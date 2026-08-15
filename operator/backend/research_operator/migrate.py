"""Apply idempotent operator schema migrations before services start."""

from __future__ import annotations

from pathlib import Path

from psycopg import connect

from .config import Settings


def main() -> int:
    settings = Settings.from_env()
    migration = settings.operator_root / "db" / "migrations" / "002-discovery-publication.sql"
    statements = migration.read_text(encoding="utf-8")
    with connect(settings.database_dsn) as connection, connection.transaction():
        connection.execute(statements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
