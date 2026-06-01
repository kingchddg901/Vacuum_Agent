"""Raw-data file writers for battery samples and completed charge sessions.

Two append-only files per vacuum, both under
``config/eufy_vacuum/battery/{object_id}/``:

- ``samples.jsonl`` — every accepted sample (battery_level, charging, rate,
  drain delta, ts). One JSON object per line. Easy to truncate / tail / parse.
- ``sessions.csv`` — every completed charge session as a CSV row. Reviewable in
  any spreadsheet for trend charting.

These files are write-only from this module's perspective; the manager keeps
its own in-memory aggregates for sensor state and persists those to
``eufy_vacuum.storage``. The files are the long-term raw audit trail.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from typing import Any

_LOGGER = logging.getLogger(__name__)

_SAMPLES_FIELDS = (
    "ts",
    "battery_level",
    "charging",
    "delta_pct",
    "rate_per_min",
    "zone",
    "drain_added",
    "cycles",
    # Non-null only when the per-sample MAX_DELTA_PCT guard rejected the
    # observed raw_delta (firmware X-to-0 / 0-to-X flip, HA restart gap,
    # multi-hour self-discharge, etc.). Carries the rejected magnitude
    # for post-hoc analysis. Grep `rejected_delta_pct` in samples.jsonl
    # to find every rejection.
    "rejected_delta_pct",
)

_SESSION_HEADER = (
    "start_ts",
    "end_ts",
    "duration_min",
    "start_battery",
    "end_battery",
    "delta_pct",
    "avg_rate_per_min",
    "min_rate_per_min",
    "max_rate_per_min",
    "samples",
    "ended_reason",
)


def _vacuum_dir(config_dir: str, vacuum_entity_id: str) -> str:
    object_id = vacuum_entity_id.split(".", 1)[-1]
    return os.path.join(config_dir, "eufy_vacuum", "battery", object_id)


def ensure_dirs(config_dir: str, vacuum_entity_id: str) -> str:
    """Create the per-vacuum directory if missing and return its path."""
    path = _vacuum_dir(config_dir, vacuum_entity_id)
    os.makedirs(path, exist_ok=True)
    return path


def append_sample(
    *,
    config_dir: str,
    vacuum_entity_id: str,
    sample: dict[str, Any],
) -> None:
    """Append one sample as a JSONL line. Best-effort; logs and swallows errors."""
    try:
        directory = ensure_dirs(config_dir, vacuum_entity_id)
        path = os.path.join(directory, "samples.jsonl")
        line = json.dumps({k: sample.get(k) for k in _SAMPLES_FIELDS}, default=str)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as err:  # pragma: no cover - best-effort I/O, logs and swallows
        _LOGGER.debug("battery: failed to append sample for %s: %s", vacuum_entity_id, err)


def append_session(
    *,
    config_dir: str,
    vacuum_entity_id: str,
    session: dict[str, Any],
) -> None:
    """Append one completed charge session as a CSV row."""
    try:
        directory = ensure_dirs(config_dir, vacuum_entity_id)
        path = os.path.join(directory, "sessions.csv")
        write_header = not os.path.exists(path) or os.path.getsize(path) == 0

        with open(path, "a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            if write_header:
                writer.writerow(_SESSION_HEADER)
            writer.writerow([_format_csv_value(session.get(f)) for f in _SESSION_HEADER])
    except OSError as err:  # pragma: no cover - best-effort I/O, logs and swallows
        _LOGGER.debug("battery: failed to append session for %s: %s", vacuum_entity_id, err)


def _format_csv_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.4f}"
    return "" if value is None else value
