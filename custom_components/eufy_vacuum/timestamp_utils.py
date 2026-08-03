"""Shared timestamp helpers for consistent UTC ISO handling."""

from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.util import dt as dt_util

UTC = timezone.utc


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
        # INF-2: resolved fresh on every call via Home Assistant's own
        # dt_util, never cached at import — dt_util.DEFAULT_TIME_ZONE is a
        # real (DST-aware) named zone HA keeps current with the user's
        # configured time_zone, unlike a module-level constant captured once
        # at import (which froze whatever fixed UTC offset happened to be in
        # force at that moment, so a naive timestamp from the opposite side
        # of a DST transition was stamped an hour off).
        local_zone = dt_util.DEFAULT_TIME_ZONE if assume_local_naive else UTC
        dt = dt.replace(tzinfo=local_zone)

    return dt.astimezone(UTC)
