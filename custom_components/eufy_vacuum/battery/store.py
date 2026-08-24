"""Raw-data file writers for battery samples and completed charge sessions.

Two append-only files per vacuum, both under
``config/eufy_vacuum/battery/{object_id}/``:

- ``samples.jsonl`` — every accepted sample (battery_level, charging, rate,
  drain delta, ts). One JSON object per line. Easy to truncate / tail / parse.
- ``sessions.csv`` — every completed charge session as a CSV row, but only the
  ``_SESSION_HEADER`` SUBSET of that session's fields. Reviewable in any
  spreadsheet for session-level trend charting (durations, deltas, rates).

These files are write-only from this module's perspective; the manager keeps
its own in-memory aggregates for sensor state and persists those to
``eufy_vacuum.storage``.

⚠ ``sessions.csv`` IS NOT A COMPLETE AUDIT TRAIL, and this docstring called both
files "the long-term raw audit trail" until 2026-08-24 (B22). Counted against the
current tree: the session summary built in ``battery/manager.py`` carries 19 keys;
``_SESSION_HEADER`` below carries 11. The 8 that never reach the CSV are
``rate_samples``, ``kind`` (idle / mid_job / post_job — the field the mid-job
recharge stats gate on, ``if kind == "mid_job" and ...``), and all six regime
fields: ``cc_duration_min``, ``cc_delta_pct``, ``cv_duration_min``,
``cv_delta_pct``, ``cc_min_per_pct``, ``cv_min_per_pct``.

That matters because ``cc_min_per_pct`` / ``cv_min_per_pct`` are the sole inputs
to the health baseline and to every charge-speed sensor. Their only durable home
is the ``.storage`` record, where ``session_history_recent`` is a
``HISTORY_LIMIT``-item ring and ``health_qualifying_sessions`` is capped at
``HEALTH_QUALIFYING_RETENTION_LIMIT``. So a reader who sees a health figure look
wrong CANNOT go back to sessions.csv and re-derive it: the numerator and
denominator of every health computation are absent from the file, and once a
session rotates out of both in-storage rings the values are gone. ``samples.jsonl``
is the raw trail; ``sessions.csv`` is a session-level export.
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
    # for post-hoc analysis.
    #
    # ⚠ THE WORKING FILTER IS `grep -v '"rejected_delta_pct": null' samples.jsonl`.
    # This comment said `grep rejected_delta_pct samples.jsonl` until 2026-08-24
    # (B15), and that CANNOT work: `append_sample` writes
    # `{k: sample.get(k) for k in _SAMPLES_FIELDS}` — a comprehension over ALL of
    # _SAMPLES_FIELDS using `.get()` — so the literal key appears on EVERY line,
    # null when nothing was rejected. The documented grep matches 100% of the file,
    # which reads either as "every sample was rejected" or as a broken field.
    #
    # ⚠ AND IT IS NOT "EVERY REJECTION" EVEN ONCE FILTERED CORRECTLY. This field
    # covers the MAX_DELTA_PCT guard alone. Two other per-sample rejections leave
    # NO trace in samples.jsonl at all:
    #   * an implausible charge rate (> MAX_PLAUSIBLE_RATE_PCT_PER_MIN) is
    #     discarded inside `battery/manager.py::_process_sample` and recorded only
    #     as `record["stats"]["rejected_rate_per_min"]` — a key that is not in
    #     _SAMPLES_FIELDS, and a LAST-value scalar on the live record rather than a
    #     per-sample marker, so it never reaches this file (ledger C67, open);
    #   * an out-of-order sample (`elapsed_sec <= 0`, the DR-BAT-2 guard) skips the
    #     whole delta block, so `delta_pct` AND `rejected_delta_pct` are both left
    #     None — indistinguishable in the JSONL from a first-ever sample.
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
    """Append one sample as a JSONL line. Best-effort; logs and swallows errors.

    ⚠ B31 (2026-08-24): the swallow was narrower than this docstring claimed.
    The handler was ``except OSError`` only, and the call site is
    ``hass.async_add_executor_job(...)`` fire-and-forget (its Future is
    deliberately not retained), so any non-OSError raised out of here surfaced
    as an unretrieved-exception traceback rather than being logged and
    swallowed. That was low-impact today (the sample values are a bounded
    shape), but the promise made the manager stop guarding itself, and a
    future widening of the sample payload — a value whose repr raises, say —
    would have surfaced there instead of here. Broadened to ``Exception`` so
    the docstring's contract is what the code does.
    """
    try:
        directory = ensure_dirs(config_dir, vacuum_entity_id)
        path = os.path.join(directory, "samples.jsonl")
        line = json.dumps({k: sample.get(k) for k in _SAMPLES_FIELDS}, default=str)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as err:  # pragma: no cover - best-effort I/O, logs and swallows
        # B31: was `except OSError`. The docstring above says "swallows errors"
        # in the general form because that is what the fire-and-forget executor
        # submission relies on — a narrower handler put a slice of failure
        # modes on an unrecoverable path this file cannot see. Losing one
        # sample to a bug is fine; taking out the battery-sample writer with a
        # ValueError is not.
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
