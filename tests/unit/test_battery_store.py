"""Unit tests for battery/store — filesystem I/O exercised via pytest tmp_path."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from custom_components.eufy_vacuum.battery.store import (
    _format_csv_value,
    _vacuum_dir,
    append_sample,
    append_session,
    ensure_dirs,
)


# ---------------------------------------------------------------------------
# _vacuum_dir
# ---------------------------------------------------------------------------

def test_vacuum_dir_extracts_object_id():
    path = _vacuum_dir("/config", "vacuum.alfred")
    assert path.endswith("alfred")
    assert "battery" in path
    assert "eufy_vacuum" in path


def test_vacuum_dir_no_domain_prefix():
    """Entity ID without a dot — split returns the whole string."""
    path = _vacuum_dir("/config", "alfred")
    assert path.endswith("alfred")


def test_vacuum_dir_uses_config_dir():
    path = _vacuum_dir("/my/config", "vacuum.bot")
    assert path.startswith("/my/config")


# ---------------------------------------------------------------------------
# _format_csv_value
# ---------------------------------------------------------------------------

def test_format_csv_none_is_empty_string():
    assert _format_csv_value(None) == ""


def test_format_csv_datetime_contains_date():
    dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = _format_csv_value(dt)
    assert "2024-06-15" in result


def test_format_csv_float_rounded_to_four_decimals():
    assert _format_csv_value(3.14159) == "3.1416"


def test_format_csv_float_zero():
    assert _format_csv_value(0.0) == "0.0000"


def test_format_csv_int_passthrough():
    assert _format_csv_value(42) == 42


def test_format_csv_string_passthrough():
    assert _format_csv_value("hello") == "hello"


def test_format_csv_bool_passthrough():
    assert _format_csv_value(True) is True


# ---------------------------------------------------------------------------
# ensure_dirs
# ---------------------------------------------------------------------------

def test_ensure_dirs_creates_directory(tmp_path):
    result = ensure_dirs(str(tmp_path), "vacuum.alfred")
    expected = tmp_path / "eufy_vacuum" / "battery" / "alfred"
    assert expected.exists()
    assert expected.is_dir()
    assert result == str(expected)


def test_ensure_dirs_is_idempotent(tmp_path):
    ensure_dirs(str(tmp_path), "vacuum.alfred")
    ensure_dirs(str(tmp_path), "vacuum.alfred")  # must not raise
    assert (tmp_path / "eufy_vacuum" / "battery" / "alfred").exists()


# ---------------------------------------------------------------------------
# append_sample
# ---------------------------------------------------------------------------

_SAMPLE = {
    "ts": "2024-01-01T00:00:00Z",
    "battery_level": 80,
    "charging": False,
    "delta_pct": -1,
    "rate_per_min": 0.5,
    "zone": "discharge",
    "drain_added": 1,
    "cycles": 0,
    "rejected_delta_pct": None,
}


def test_append_sample_creates_jsonl_file(tmp_path):
    append_sample(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", sample=_SAMPLE)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "samples.jsonl"
    assert path.exists()


def test_append_sample_content_is_valid_json(tmp_path):
    append_sample(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", sample=_SAMPLE)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "samples.jsonl"
    parsed = json.loads(path.read_text().strip())
    assert parsed["battery_level"] == 80
    assert parsed["charging"] is False


def test_append_sample_multiple_writes_append(tmp_path):
    for _ in range(3):
        append_sample(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", sample=_SAMPLE)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "samples.jsonl"
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 3


def test_append_sample_only_writes_schema_fields(tmp_path):
    sample_with_extra = {**_SAMPLE, "extra_field": "should_be_ignored"}
    append_sample(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", sample=sample_with_extra)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "samples.jsonl"
    parsed = json.loads(path.read_text().strip())
    assert "extra_field" not in parsed


def test_append_sample_missing_fields_written_as_none(tmp_path):
    append_sample(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", sample={})
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "samples.jsonl"
    parsed = json.loads(path.read_text().strip())
    assert parsed["battery_level"] is None
    assert parsed["ts"] is None


# ---------------------------------------------------------------------------
# append_session
# ---------------------------------------------------------------------------

_SESSION = {
    "start_ts": "2024-01-01T00:00:00Z",
    "end_ts": "2024-01-01T01:00:00Z",
    "duration_min": 60.0,
    "start_battery": 40,
    "end_battery": 90,
    "delta_pct": 50,
    "avg_rate_per_min": 0.8333,
    "min_rate_per_min": 0.7,
    "max_rate_per_min": 1.0,
    "samples": 12,
    "ended_reason": "full",
}


def test_append_session_creates_csv_file(tmp_path):
    append_session(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", session=_SESSION)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "sessions.csv"
    assert path.exists()


def test_append_session_first_row_is_header(tmp_path):
    append_session(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", session=_SESSION)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "sessions.csv"
    rows = list(csv.reader(path.read_text().splitlines()))
    assert rows[0][0] == "start_ts"


def test_append_session_data_row_present(tmp_path):
    append_session(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", session=_SESSION)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "sessions.csv"
    rows = list(csv.reader(path.read_text().splitlines()))
    assert len(rows) == 2  # header + one data row


def test_append_session_header_written_only_once(tmp_path):
    for _ in range(3):
        append_session(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", session=_SESSION)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "sessions.csv"
    rows = list(csv.reader(path.read_text().splitlines()))
    header_rows = [r for r in rows if r and r[0] == "start_ts"]
    assert len(header_rows) == 1


def test_append_session_three_writes_produce_four_rows(tmp_path):
    for _ in range(3):
        append_session(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred", session=_SESSION)
    path = tmp_path / "eufy_vacuum" / "battery" / "alfred" / "sessions.csv"
    rows = [r for r in csv.reader(path.read_text().splitlines()) if r]
    assert len(rows) == 4  # 1 header + 3 data
