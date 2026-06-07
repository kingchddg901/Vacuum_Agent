"""Counter-plateau room segmentation — brand-agnostic, frame-invariant.

`cleaning_time` (a pure ~30 s clock) and `cleaning_area` (unique m² covered) are
cumulative progress counters. This module turns their time series into ordered
per-room segments **without geometry** — raw coordinates drift across sessions on
some firmware (Eufy), so position is never consulted here.

Boundary rules (validated in `scratch-external-estimator/segment_internal.py` +
`nomop_boundary.py` against real runs):

- **job start** — `cleaning_time` resets to 0; segmentation starts after the last
  reset (a stale pre-reset value from the previous job is dropped).
- **long plateau** (gap between `cleaning_time` increments > ``gap_plateau_s``) —
  an unambiguous room boundary: the robot is washing (ByRoom mode) or making a
  long transit. Pass-turns never take minutes, so no area check is needed.
- **delayed step** (``gap_delayed_s`` < gap ≤ ``gap_plateau_s``) — a ~40 s hop.
  It is a **room transition** only if `cleaning_area` jumped (new floor,
  ``area_jump_m2``); otherwise it is a **multi-pass turn** (re-covering the same
  room — area stays flat) and does *not* split the segment.
- **normal** (gap ≤ ``gap_delayed_s``) — in-room cleaning progress.

Per segment we recover exact ``area_delta_m2`` (the room's true size), the active
clean count (``time_active_s``), the wall-clock span, the battery delta, and the
inter-segment gap (transit + wash before the room). The caller assigns room
identity (internal: map segment K → dispatched queue room K) and validates the
segment count against the expected room count.

`cleaning_area` and `cleaning_time` update on separate packets that can land out
of order at the same timestamp (the area lags the clock), so area is read via
``area_at(t)`` — the monotonic area *reached by* time t — rather than carried
forward, which would undercount the room that owns the lagging tick.
"""

from __future__ import annotations

import bisect
from datetime import datetime
from typing import Any

# Defaults (seconds / m²). cleaning_time ticks every ~30 s while cleaning.
_CADENCE_S = 30.0
_GAP_DELAYED_S = 35.0   # gap above this = a delayed step (a hop or a pass-turn)
_GAP_PLATEAU_S = 90.0   # gap above this = an unambiguous boundary (wash / long transit)
_AREA_JUMP_M2 = 2.0     # cleaning_area delta across a delayed step marking new floor


def _to_dt(value: Any) -> datetime | None:
    """Coerce a timestamp (datetime or tolerant ISO string) to datetime."""
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1]
    if "+" in s:
        s = s.split("+", 1)[0]
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _f(value: Any, default: float = 0.0) -> float:
    """Return float safely (sentinels → default)."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def segment_counters(
    samples: list[dict[str, Any]],
    *,
    cadence_s: float = _CADENCE_S,
    gap_delayed_s: float = _GAP_DELAYED_S,
    gap_plateau_s: float = _GAP_PLATEAU_S,
    area_jump_m2: float = _AREA_JUMP_M2,
) -> list[dict[str, Any]]:
    """Segment a counter-sample stream into ordered per-room cleaning bouts.

    ``samples`` is a list of dicts ``{t|observed_at, cleaning_time, cleaning_area,
    battery}`` (each carrying the last-seen value of both counters). Returns a
    list of segment dicts in cleaning order; empty if there is no usable signal
    (e.g. an adapter without these counters). Pure + frame-invariant.
    """
    norm: list[tuple[datetime, float, float, Any]] = []
    for s in samples or []:
        if not isinstance(s, dict):
            continue
        t = _to_dt(s.get("t", s.get("observed_at")))
        if t is None:
            continue
        norm.append((t, _f(s.get("cleaning_time"), -1.0), _f(s.get("cleaning_area"), -1.0), s.get("battery")))
    norm.sort(key=lambda r: r[0])
    if not norm:
        return []

    # Job window: start after the LAST cleaning_time reset to 0, dropping any
    # stale pre-reset sample carried over from the previous job.
    reset_i = 0
    for i, (_t, ct, _ca, _b) in enumerate(norm):
        if ct == 0:
            reset_i = i
    window = norm[reset_i:]
    reset_t = window[0][0]

    # cleaning_area is monotonic non-decreasing post-reset. area_at(t) = the area
    # reached by time t (ties sorted by area so the max wins), robust to area
    # packets that lag the cleaning_time tick at the same timestamp.
    ca_pairs = sorted(((t, ca) for (t, _ct, ca, _b) in window if ca >= 0), key=lambda p: (p[0], p[1]))
    ca_times = [p[0] for p in ca_pairs]
    ca_vals = [p[1] for p in ca_pairs]

    def area_at(t: datetime) -> float:
        i = bisect.bisect_right(ca_times, t) - 1
        return ca_vals[i] if i >= 0 else 0.0

    batt_pairs = sorted(((t, b) for (t, _ct, _ca, b) in window if b is not None), key=lambda p: p[0])
    batt_times = [p[0] for p in batt_pairs]
    batt_vals = [p[1] for p in batt_pairs]

    def batt_at(t: datetime) -> Any:
        i = bisect.bisect_right(batt_times, t) - 1
        return batt_vals[i] if i >= 0 else None

    # Increment timestamps: where cleaning_time strictly rose (the 30 s ticks).
    incs: list[tuple[datetime, float]] = []
    last_ct: float | None = None
    for (t, ct, _ca, _b) in window:
        if ct < 0:
            continue
        if last_ct is None:
            last_ct = ct  # baseline (0 at the reset)
            continue
        if ct > last_ct:
            incs.append((t, ct))
        last_ct = ct
    if not incs:
        return []

    # Split increments into segments at boundaries; pass-turns stay in-segment.
    groups: list[list[tuple[datetime, float]]] = [[incs[0]]]
    boundaries: list[str] = ["job_start"]
    for prev, nxt in zip(incs, incs[1:]):
        gap = (nxt[0] - prev[0]).total_seconds()
        d_area = area_at(nxt[0]) - area_at(prev[0])
        if gap > gap_plateau_s:
            groups.append([nxt])
            boundaries.append("wash_plateau")
        elif gap > gap_delayed_s and d_area >= area_jump_m2:
            groups.append([nxt])
            boundaries.append("area_jump")
        else:
            groups[-1].append(nxt)

    out: list[dict[str, Any]] = []
    prev_ct = 0.0
    prev_area = 0.0
    prev_end_t = reset_t
    for idx, g in enumerate(groups):
        start_t = g[0][0]
        end_t, end_ct = g[-1]
        end_area = area_at(end_t)
        b_start = batt_at(start_t)
        b_end = batt_at(end_t)
        battery_delta: float | None = None
        if b_start is not None and b_end is not None:
            battery_delta = round(max(_f(b_start) - _f(b_end), 0.0), 2)
        out.append(
            {
                "index": idx,
                "t_start": start_t.isoformat(),
                "t_end": end_t.isoformat(),
                "ct_start": prev_ct,
                "ct_end": end_ct,
                "area_start_m2": round(prev_area, 2),
                "area_end_m2": round(end_area, 2),
                "area_delta_m2": round(max(end_area - prev_area, 0.0), 2),
                "time_active_s": round(max(end_ct - prev_ct, 0.0), 1),
                "time_wall_s": round(max((end_t - start_t).total_seconds(), 0.0), 1),
                "gap_before_s": round(max((start_t - prev_end_t).total_seconds(), 0.0), 1),
                "battery_delta": battery_delta,
                "boundary": boundaries[idx],
                "increment_count": len(g),
            }
        )
        prev_ct = end_ct
        prev_area = end_area
        prev_end_t = end_t
    return out
