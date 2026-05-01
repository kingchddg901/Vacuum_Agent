"""Shared timestamp helpers for consistent UTC ISO handling."""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc
_LOCAL_TZ = datetime.now().astimezone().tzinfo or UTC


def utc_now() -> datetime:
    """Return the current aware UTC datetime."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 with Z suffix."""
    return datetime_to_utc_iso(utc_now())


def datetime_to_utc_iso(value: datetime | None) -> str | None:
    """Serialize a datetime as UTC ISO 8601 with Z suffix."""
    if value is None:
        return None
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str | None, *, assume_local_naive: bool = True) -> datetime | None:
    """Parse supported timestamp strings into aware UTC datetimes.

    Supported inputs:
    - ISO 8601 with Z or numeric offset
    - legacy naive forms: YYYY-MM-DDTHH:MM:SS / YYYY-MM-DD HH:MM:SS

    Legacy naive timestamps are treated as local time by default because most
    stored historical data used local naive serialization.
    """
    text = str(value or "").strip()
    if not text:
        return None

    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text

    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        dt = None

    if dt is None:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LOCAL_TZ if assume_local_naive else UTC)

    return dt.astimezone(UTC)
