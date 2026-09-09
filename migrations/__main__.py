"""Apply every pending SQL migration to ``APP_DATABASE_URL``."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

from config import resolve_app_database_url


MIGRATION_OPT_IN_ENV = "ALLOW_APP_MIGRATIONS"


def migration_database_url(environ: dict[str, str] | None = None) -> str:
    """Return the explicitly confirmed application database migration target."""
    environment = os.environ if environ is None else environ
    if environment.get(MIGRATION_OPT_IN_ENV) != "1":
        raise RuntimeError(
            f"Debe confirmar las migraciones con {MIGRATION_OPT_IN_ENV}=1."
        )
    database_url = resolve_app_database_url(
        environment.get("APP_ENV", "development").lower(),
        environment.get("APP_DATABASE_URL"),
    )
    if not database_url:
        raise RuntimeError("APP_DATABASE_URL debe configurarse para ejecutar migraciones.")
    return database_url


def apply_pending_migrations(database_url: str) -> None:
    """Apply pending migrations to the already-confirmed application database."""
    migration_dir = Path(__file__).parent
    files = sorted(path for path in migration_dir.glob("[0-9][0-9][0-9]_*.sql"))
    with psycopg.connect(database_url) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS ergo_app")
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS ergo_app.schema_migrations "
                    "(filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
                )
                cursor.execute("SELECT filename FROM ergo_app.schema_migrations")
                applied = {row[0] for row in cursor.fetchall()}
            for path in files:
                if path.name in applied:
                    continue
                with connection.cursor() as cursor:
                    cursor.execute(path.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO ergo_app.schema_migrations (filename) VALUES (%s)",
                        (path.name,),
                    )
                print(f"Applied {path.name}")


def main() -> None:
    apply_pending_migrations(migration_database_url())


if __name__ == "__main__":
    main()
