"""Database helpers for the authentication and clinical sources."""

from __future__ import annotations

import psycopg
from flask import Flask, current_app, g


def _get_connection(
    config_key: str,
    g_key: str,
    *,
    connect_options: str | None = None,
) -> psycopg.Connection:
    """Open one PostgreSQL connection per request and reuse it."""
    connection = getattr(g, g_key, None)
    if connection is None:
        database_url = current_app.config.get(config_key)
        if not database_url:
            raise RuntimeError(f"{config_key} is not configured")
        connect_kwargs = {}
        if connect_options is not None:
            connect_kwargs["options"] = connect_options
        connection = psycopg.connect(database_url, **connect_kwargs)
        setattr(g, g_key, connection)
    return connection


def get_auth_db() -> psycopg.Connection:
    """Return the authentication database connection."""
    return _get_connection("AUTH_DATABASE_URL", "auth_db")


def get_clinical_db() -> psycopg.Connection:
    """Return the clinical read-only database connection."""
    return _get_connection(
        "CLINICAL_DATABASE_URL",
        "clinical_db",
        connect_options="-c default_transaction_read_only=on",
    )


def close_db(_error: BaseException | None = None) -> None:
    """Close any open PostgreSQL connections."""
    for key in ("auth_db", "clinical_db"):
        connection = getattr(g, key, None)
        if connection is not None:
            connection.close()
            setattr(g, key, None)


def init_app(app: Flask) -> None:
    """Register teardown handlers for database connections."""
    app.teardown_appcontext(close_db)
