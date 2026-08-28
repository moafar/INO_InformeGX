"""Helpers for patient names and visit datetimes."""

from __future__ import annotations

from datetime import datetime


def format_full_name(
    first_name: str | None,
    middle_name: str | None,
    last_name: str | None,
) -> str:
    """Format a name while omitting empty parts."""
    surname = (last_name or "").strip()
    given_names = " ".join(
        part
        for part in (
            (first_name or "").strip(),
            (middle_name or "").strip(),
        )
        if part
    )

    if surname and given_names:
        return f"{surname}, {given_names}"
    if surname:
        return surname
    if given_names:
        return given_names
    return "No disponible"


def format_visit_datetime(value: datetime | str | None) -> str:
    """Format a visit timestamp without timezone conversion."""
    if value is None:
        return "No disponible"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)
