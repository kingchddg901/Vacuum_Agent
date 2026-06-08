"""Counter-plateau room segmentation — brand-agnostic, frame-invariant.

`cleaning_time` (a pure ~30 s clock) and `cleaning_area` (unique m² covered) are
cumulative progress counters. This module turns their time series into ordered
per-room segments **without geometry** — raw coordinates drift across sessions on
some firmware (Eufy), so position is never consulted here.

Boundary rules (validated in `scratch-external-estimator/` against real runs,
including a multi-setting external run the same-instant rule got wrong):

- **job start** — `cleaning_time` resets to 0; segmentation starts after the last
  reset (a stale pre-reset value from the previous job is dropped).
- **long plateau** (gap between `cleaning_time` increments > ``gap_plateau_s``) — a
  room boundary: the robot is washing (ByRoom) or making a long transit. Pass-turns
  are seconds, never minutes, so no area check is needed (and the live path can roll
  the moment the wash starts, before the next room covers any floor).
- **delayed step** (``gap_delayed_s`` < gap ≤ ``gap_plateau_s``) — a ~40 s hop. It
  is a **room boundary** iff `cleaning_area` rises (≥ ``area_jump_m2``) in the
  stretch *after* it, read FORWARD to the next blip; otherwise it is a **multi-pass
  turn** (re-covering the same room — area stays flat) and does not split.
- **normal** (gap ≤ ``gap_delayed_s``) — in-room cleaning progress.

The forward look on the delayed step matters: `cleaning_area` packets lag the
`cleaning_time` tick, so the next room's area-jump can land a tick *after* the
boundary. The earlier same-instant rule (area must jump *at* the gap) missed
path-varied boundaries — a Narrow-intensity room whose area has already plateaued,
the next room's area catching up a tick later — returning 1 segment for a real
2-room run.

``expected_rooms`` (internal: the dispatched queue length) caps over-splitting: the
counters alone can't tell an edge→fill / progressive-area pass-turn from a true
boundary, so when more boundaries are found than the queue allows, only the most
confident are kept (a long plateau outranks a short delayed step). External callers
pass None and may over-split — the user merges in review.

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

from .timestamp_utils import UTC, datetime_to_utc_iso, parse_timestamp

# Defaults (seconds / m²). cleaning_time ticks every ~30 s while cleaning.
_CADENCE_S = 30.0
_GAP_DELAYED_S = 35.0   # gap above this = a delayed step (a hop or a pass-turn)
_GAP_PLATEAU_S = 90.0   # gap above this = an unambiguous boundary (wash / long transit)
_AREA_JUMP_M2 = 2.0     # cleaning_area delta across a delayed step marking new floor


def _to_dt(value: Any) -> datetime | None:
    """Coerce a timestamp to an aware UTC datetime via the shared timestamp_utils,
    so segment timestamps never drift between naive and "...Z". Counter/settings
    samples are UTC, so a naive string is read as UTC (not local)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return parse_timestamp(value, assume_local_naive=False)


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
    expected_rooms: int | None = None,
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

    ``expected_rooms`` (internal callers: the dispatched queue length) caps
    over-splitting — when more boundaries are found than ``expected_rooms - 1``,
    only the strongest (largest forward area-rise) are kept. The counters alone
    cannot separate an edge→fill / progressive-area pass-turn from a real boundary
    (both show area rising after the gap), so the known room count is the
    tie-breaker. External callers pass ``None`` and may over-split — the user
    merges in review.
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

    # Blips = gaps above the 30 s clock (a hop, a mop wash, or a multi-pass turn).
    # A blip is a room boundary when EITHER it is a long plateau (gap > gap_plateau_s
    # — a minutes-long wash or transit; pass-turns are seconds) OR cleaning_area
    # RISES (>= area_jump_m2) in the stretch AFTER it, read FORWARD to the next blip.
    # The forward look fixes path-varied boundaries the old same-instant check missed
    # (a Narrow room re-covers so its area has plateaued, and the next room's
    # area-jump lands a tick later). A short delayed step with flat area after is a
    # multi-pass turn and does not split.
    blip_positions = [
        i for i in range(1, len(incs))
        if (incs[i][0] - incs[i - 1][0]).total_seconds() > gap_delayed_s
    ]
    candidates: list[tuple[float, float, int]] = []  # (area_after, gap, position)
    for n, bi in enumerate(blip_positions):
        nxt = blip_positions[n + 1] if n + 1 < len(blip_positions) else len(incs)
        gap = (incs[bi][0] - incs[bi - 1][0]).total_seconds()
        area_after = area_at(incs[nxt - 1][0]) - area_at(incs[bi][0])
        if gap > gap_plateau_s or area_after >= area_jump_m2:
            candidates.append((area_after, gap, bi))

    # When the room count is known (internal: the dispatched queue length), keep only
    # the most-confident boundaries — a long plateau outranks a short delayed step,
    # then larger forward area-rise wins. The counters alone can't separate an
    # edge→fill / progressive-area pass-turn from a true boundary, so the queue count
    # caps over-splitting. External callers pass None and may over-split (user merges).
    if expected_rooms is not None:
        keep = max(int(expected_rooms) - 1, 0)
        if len(candidates) > keep:
            candidates.sort(key=lambda c: (c[1] > gap_plateau_s, c[0]), reverse=True)
            candidates = candidates[:keep]

    boundary_at: dict[int, str] = {
        bi: ("wash_plateau" if gap > gap_plateau_s else "area_jump")
        for (_area_after, gap, bi) in candidates
    }

    # Split increments into segments at boundaries; pass-turns stay in-segment.
    groups: list[list[tuple[datetime, float]]] = [[incs[0]]]
    boundaries: list[str] = ["job_start"]
    for i in range(1, len(incs)):
        kind = boundary_at.get(i)
        if kind is not None:
            groups.append([incs[i]])
            boundaries.append(kind)
        else:
            groups[-1].append(incs[i])

    out: list[dict[str, Any]] = []
    prev_ct = 0.0
    prev_area = 0.0
    prev_end_t = reset_t
    for idx, g in enumerate(groups):
        start_t = g[0][0]
        end_t, end_ct = g[-1]
        # Forward-attribute area: cleaning_area packets LAG cleaning_time, so a short
        # room's m² often finishes posting during the dock AFTER its last tick (live: a
        # vac bathroom went 1.0 at its last tick -> 3.0 by the next room's start, all
        # during the prewash dock). Read the END area FORWARD to the next room's start
        # ONLY across a wash_plateau/dock — no new floor is covered there, so the area
        # that posts is THIS room's lag. Across an area_jump the rise is the NEXT room's
        # new floor, so stay same-instant and don't steal it. The last segment reads to
        # the final sample (trailing dock lag). No-lag runs are unchanged.
        if idx + 1 >= len(groups):
            area_ref_t = norm[-1][0] if norm else end_t
        elif boundaries[idx + 1] == "wash_plateau":
            area_ref_t = groups[idx + 1][0][0]
        else:
            area_ref_t = end_t
        end_area = area_at(area_ref_t)
        b_start = batt_at(start_t)
        b_end = batt_at(end_t)
        battery_delta: float | None = None
        if b_start is not None and b_end is not None:
            battery_delta = round(max(_f(b_start) - _f(b_end), 0.0), 2)
        out.append(
            {
                "index": idx,
                "t_start": datetime_to_utc_iso(start_t),
                "t_end": datetime_to_utc_iso(end_t),
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
