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
