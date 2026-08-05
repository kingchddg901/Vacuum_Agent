"""Pose ring — a 24-hour rolling, chunked JSONL record of where the robot was.

WHAT THIS IS FOR. The pose sampler already buffers ``{current_room, anchor,
cleaning_area}`` at the adapter's cadence (2 s on Eufy) into the ACTIVE JOB, where
the room-attribution engines consume it live. That buffer is job-scoped: it lives
until the next run on the same map overwrites it, and it never reaches the
finalized record. So the moment a run ends, the fine-grained history of what the
robot actually did is gone.

This is the parallel copy that outlives the job. Nothing reads the job buffer any
differently; this is purely additive.

WHY IT MATTERS, measured 2026-08-05. A Kitchen -> Entryway transit measured 36 s
from the counters. What the counters CANNOT say is how that 36 s divided. The
2 s pose trace says it exactly:

    06:31:55 -> 06:32:13   ~17 s   still in Kitchen, not cleaning   = EGRESS
    06:32:13 -> 06:32:33   ~20 s   travelling, via rooms 7 then 6   = TRANSIT

and it showed the robot crossing TWO intermediate rooms where the ~15-20 s
``map_overlays`` signal saw only one, and the recorder's raw position sensors saw
nothing at all (they update every 40-150 s; two separate 36 s transits contained
ZERO samples between them).

WHY A RING AND NOT FOREVER. Pose accrues on RUNTIME, not wall-clock, and it is
heavy relative to the other raw stores:

    battery samples.jsonl   12 KB/day    ->   43 MB / 10 yr   (wall-clock)
    pose @ 1 h/day         116 KB/day    ->  413 MB / 10 yr   (runtime)

Ten to twenty times battery. Not ruinous - Home Assistant's own recorder writes
~270 MB/DAY on this install, so pose is under 0.1% of what the system already
does - but large enough that keeping it forever should be the USER's decision,
not a default every install inherits.

24 hours is chosen so a daily export cannot miss a window, with margin. Because
pose only accrues while running, a 24 h window holds ~1-2 h of actual samples on
a normal install: roughly 230 KB steady-state, a quarter of what battery already
occupies, and it does not grow.

Anyone who wants it permanently harvests it - a nightly ``shell_command``, an
rsync, anything. The integration's job is to guarantee the window is long enough
to REACH, not to decide how long someone's data stays interesting.

LAYOUT. One directory per vacuum, one file per half hour, so expiry is an unlink
rather than a rewrite of a file the sampler is appending to:

    <config>/eufy_vacuum/pose/<vacuum_object_id>/2026-08-05T06-00.jsonl
                                                 2026-08-05T05-30.jsonl   <- pruned at 24 h

Rewriting a rolling window in place would cost ~4x the writes for the same
retention and would race the appender. Chunking costs one ``unlink`` per half
hour instead.

BEST-EFFORT THROUGHOUT. This is an observability side-channel: a failure to write
it must never disturb a run, so every I/O error is logged at debug and swallowed.
The authoritative live path remains the job buffer.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: Fields written per line. Fixed and explicit so a reader can rely on the shape
#: and a future field cannot silently widen every historical file.
_FIELDS = ("t", "map_id", "current_room", "anchor", "cleaning_area", "heading")

#: Minutes per chunk file. 30 divides the hour evenly, so chunk names are stable
#: and sortable, and a prune examines at most ~50 files.
_CHUNK_MINUTES = 30

#: How long a chunk survives. See the module docstring for why 24 h.
_RETENTION_HOURS = 24


def _vacuum_dir(config_dir: str, vacuum_entity_id: str) -> str:
    """``<config>/eufy_vacuum/pose/<object_id>`` — object_id, not the full entity_id,
    to match the battery store's layout and to keep the path free of dots."""
    object_id = str(vacuum_entity_id).split(".", 1)[-1]
    return os.path.join(config_dir, "eufy_vacuum", "pose", object_id)


def _chunk_name(when: dt.datetime) -> str:
    """The chunk a timestamp belongs to, floored to the half hour."""
    floored = when.replace(minute=(when.minute // _CHUNK_MINUTES) * _CHUNK_MINUTES,
                           second=0, microsecond=0)
    return floored.strftime("%Y-%m-%dT%H-%M") + ".jsonl"


def _parse_chunk_name(name: str) -> dt.datetime | None:
    """The chunk's start time, or None when the filename is not ours."""
    if not name.endswith(".jsonl"):
        return None
    try:
        return dt.datetime.strptime(name[: -len(".jsonl")], "%Y-%m-%dT%H-%M").replace(
            tzinfo=dt.timezone.utc
        )
    except ValueError:
        return None


def append_sample(
    *,
    config_dir: str,
    vacuum_entity_id: str,
    sample: dict[str, Any],
    now: dt.datetime | None = None,
) -> None:
    """Append one pose sample as a JSONL line, and prune expired chunks.

    Runs on an executor thread (the sampler is on the event loop, and direct file
    I/O there trips Home Assistant's blocking-call detector - the same reason
    battery/manager.py offloads its append).

    Pruning rides the append rather than a timer: it is O(number of chunks) at
    most twice a minute during a run, and it means a system that stops running
    stops pruning, which is correct - there is nothing new to expire and the last
    day's data stays reachable rather than being deleted by a clock.
    """
    when = now or dt.datetime.now(dt.timezone.utc)
    try:
        directory = _vacuum_dir(config_dir, vacuum_entity_id)
        os.makedirs(directory, exist_ok=True)
        line = json.dumps({k: sample.get(k) for k in _FIELDS}, default=str)
        with open(os.path.join(directory, _chunk_name(when)), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as err:  # pragma: no cover - best-effort I/O
        _LOGGER.debug("pose: append failed for %s: %s", vacuum_entity_id, err)
        return
    prune(config_dir=config_dir, vacuum_entity_id=vacuum_entity_id, now=when)


def prune(
    *,
    config_dir: str,
    vacuum_entity_id: str,
    now: dt.datetime | None = None,
    retention_hours: int = _RETENTION_HOURS,
) -> int:
    """Unlink chunks whose window ended more than ``retention_hours`` ago.

    A chunk is judged by its END (start + chunk length), so the one currently
    being written is never a prune candidate. Returns the number removed.
    """
    when = now or dt.datetime.now(dt.timezone.utc)
    cutoff = when - dt.timedelta(hours=retention_hours)
    removed = 0
    directory = _vacuum_dir(config_dir, vacuum_entity_id)
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    for name in names:
        start = _parse_chunk_name(name)
        if start is None:
            continue          # not ours - never delete a file we did not name
        if start + dt.timedelta(minutes=_CHUNK_MINUTES) < cutoff:
            try:
                os.remove(os.path.join(directory, name))
                removed += 1
            except OSError as err:  # pragma: no cover - best-effort I/O
                _LOGGER.debug("pose: prune failed for %s: %s", name, err)
    return removed


def read_range(
    *,
    config_dir: str,
    vacuum_entity_id: str,
    start_iso: str,
    end_iso: str,
) -> list[dict[str, Any]]:
    """Samples with ``start_iso <= t <= end_iso``, in order.

    THE POINT OF THE WHOLE MODULE: a finalizing job asks "what happened between
    T0 and T1" instead of owning a buffer. Phases of one run each ask for their
    own window against the same store, and a run whose buffer was already cleared
    is still answerable.

    Only chunks that can overlap the window are opened. Timestamps compare
    lexicographically because they are uniform UTC ISO strings, so no parsing is
    needed per line - which matters when a window can span thousands of samples.
    """
    directory = _vacuum_dir(config_dir, vacuum_entity_id)
    try:
        names = sorted(n for n in os.listdir(directory) if _parse_chunk_name(n))
    except OSError:
        return []

    lo = dt.datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
    hi = dt.datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))
    out: list[dict[str, Any]] = []
    for name in names:
        start = _parse_chunk_name(name)
        if start is None:
            continue
        # Skip a chunk only when it CANNOT overlap: it ends before the window
        # opens, or begins after the window closes.
        if start + dt.timedelta(minutes=_CHUNK_MINUTES) < lo or start > hi:
            continue
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        row = json.loads(raw)
                    except ValueError:
                        continue      # a torn final line after a hard stop
                    stamp = str(row.get("t") or "")
                    if start_iso <= stamp <= end_iso:
                        out.append(row)
        except OSError as err:  # pragma: no cover - best-effort I/O
            _LOGGER.debug("pose: read failed for %s: %s", name, err)
    out.sort(key=lambda r: str(r.get("t") or ""))
    return out
