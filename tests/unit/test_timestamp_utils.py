"""Unit tests for timestamp_utils — pure Python, no HA dependency."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from custom_components.eufy_vacuum.timestamp_utils import (
    datetime_to_utc_iso,
    parse_timestamp,
    utc_now,
    utc_now_iso,
    UTC,
)


# ---------------------------------------------------------------------------
# utc_now / utc_now_iso
# ---------------------------------------------------------------------------

def test_utc_now_is_aware():
    dt = utc_now()
    assert dt.tzinfo is not None
    assert dt.tzinfo == UTC


def test_utc_now_iso_format():
    iso = utc_now_iso()
    assert iso.endswith("Z")
    assert "T" in iso


# ---------------------------------------------------------------------------
# datetime_to_utc_iso
# ---------------------------------------------------------------------------

def test_datetime_to_utc_iso_none():
    assert datetime_to_utc_iso(None) is None


def test_datetime_to_utc_iso_aware():
    dt = datetime(2024, 6, 15, 12, 30, 45, tzinfo=UTC)
    assert datetime_to_utc_iso(dt) == "2024-06-15T12:30:45Z"


def test_datetime_to_utc_iso_strips_microseconds():
    dt = datetime(2024, 1, 1, 0, 0, 0, 999999, tzinfo=UTC)
    result = datetime_to_utc_iso(dt)
    assert result == "2024-01-01T00:00:00Z"


def test_datetime_to_utc_iso_naive_treated_as_utc():
    dt = datetime(2024, 6, 15, 12, 0, 0)  # no tzinfo
    result = datetime_to_utc_iso(dt)
    assert result == "2024-06-15T12:00:00Z"


def test_datetime_to_utc_iso_offset_converted():
    from datetime import timedelta
    tz_plus5 = timezone(timedelta(hours=5))
    dt = datetime(2024, 6, 15, 17, 0, 0, tzinfo=tz_plus5)  # 17:00+05 = 12:00Z
    assert datetime_to_utc_iso(dt) == "2024-06-15T12:00:00Z"


# ---------------------------------------------------------------------------
# parse_timestamp
# ---------------------------------------------------------------------------

def test_parse_timestamp_none():
    assert parse_timestamp(None) is None


def test_parse_timestamp_empty_string():
    assert parse_timestamp("") is None
    assert parse_timestamp("   ") is None


def test_parse_timestamp_z_suffix():
    dt = parse_timestamp("2024-06-15T12:30:45Z")
    assert dt is not None
    assert dt.tzinfo == UTC
    assert dt.year == 2024
    assert dt.hour == 12
    assert dt.minute == 30


def test_parse_timestamp_numeric_offset():
    dt = parse_timestamp("2024-06-15T17:30:45+05:00")
    assert dt is not None
    assert dt.tzinfo == UTC
    assert dt.hour == 12  # 17:30+05 → 12:30Z


def test_parse_timestamp_legacy_T_format():
    dt = parse_timestamp("2024-06-15T12:30:45", assume_local_naive=False)
    assert dt is not None
    assert dt.tzinfo == UTC
    assert dt.hour == 12


def test_parse_timestamp_legacy_space_format():
    dt = parse_timestamp("2024-06-15 08:00:00", assume_local_naive=False)
    assert dt is not None
    assert dt.tzinfo == UTC
    assert dt.year == 2024


def test_parse_timestamp_invalid_returns_none():
    assert parse_timestamp("not-a-date") is None
    assert parse_timestamp("2024-99-99") is None


# ---------------------------------------------------------------------------
# INF-2 — the local zone is resolved per call via dt_util, never frozen
# ---------------------------------------------------------------------------

async def test_parse_timestamp_naive_resolves_local_zone_per_call(hass):
    """INF-2: assume_local_naive=True (the default) resolves the local zone
    via Home Assistant's dt_util.DEFAULT_TIME_ZONE, read fresh on every call —
    not a module-level constant captured once at import. Proven two ways:
    (1) a DST-observing zone assigns DIFFERENT UTC offsets to a January vs a
    July naive timestamp, and (2) changing dt_util.DEFAULT_TIME_ZONE between
    two calls changes the very next call's result, so nothing was resolved
    once and cached at import time.

    Uses hass.config.async_set_time_zone (the official HA API — the same one
    the test harness's own hass fixture uses to set its default test zone)
    rather than monkeypatching dt_util.DEFAULT_TIME_ZONE directly: the harness
    already has an active hass with its own timezone per test, so a raw
    monkeypatch races that fixture's own setup/teardown of the same global.
    """
    import zoneinfo

    from custom_components.eufy_vacuum import timestamp_utils

    ny = zoneinfo.ZoneInfo("America/New_York")
    await hass.config.async_set_time_zone("America/New_York")

    winter = timestamp_utils.parse_timestamp("2024-01-15T12:00:00")
    summer = timestamp_utils.parse_timestamp("2024-07-15T12:00:00")
    assert winter is not None and summer is not None
    # DST differs by an hour between the two dates in this zone.
    assert winter != summer
    assert winter == datetime(2024, 1, 15, 12, 0, 0, tzinfo=ny).astimezone(UTC)
    assert summer == datetime(2024, 7, 15, 12, 0, 0, tzinfo=ny).astimezone(UTC)

    # Switching the configured zone changes the very NEXT call — proves
    # nothing was resolved/cached once, at import time.
    tokyo = zoneinfo.ZoneInfo("Asia/Tokyo")  # fixed +09:00, no DST
    await hass.config.async_set_time_zone("Asia/Tokyo")
    same_wall_clock_tokyo = timestamp_utils.parse_timestamp("2024-01-15T12:00:00")
    assert same_wall_clock_tokyo != winter
    assert same_wall_clock_tokyo == datetime(
        2024, 1, 15, 12, 0, 0, tzinfo=tokyo
    ).astimezone(UTC)


async def test_parse_timestamp_naive_false_ignores_local_zone(hass):
    """Control: assume_local_naive=False must NOT consult dt_util at all —
    changing the configured time zone must not move this result."""
    from custom_components.eufy_vacuum import timestamp_utils

    await hass.config.async_set_time_zone("America/New_York")
    result = timestamp_utils.parse_timestamp(
        "2024-06-15T12:00:00", assume_local_naive=False
    )
    assert result == datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
