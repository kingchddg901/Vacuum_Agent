"""Counter-plateau room segmentation — brand-agnostic, frame-invariant.

`cleaning_time` (a pure ~30 s clock) and `cleaning_area` (unique m² covered) are
cumulative progress counters. This module turns their time series into ordered
per-room segments **without geometry** — raw coordinates drift across sessions on
some firmware (Eufy), so position is never consulted here.

The pipeline is three pure stages so a run can be re-segmented from the SAME
frozen samples at any granularity (the external-review wizard re-segments
server-side when the user sets a room count or toggles a boundary):

  find_candidates(samples)            -> every detected boundary, ranked + kinded
  select_active(candidates, ...)      -> pick the active set (count / explicit / default)
  build_segments(samples, active)     -> the per-room segment dicts for that set

``segment_counters`` is a thin back-compat wrapper over the three for internal
queue callers and the existing tests.

Boundary kinds (a blip = a gap between `cleaning_time` increments > ``gap_delayed_s``):

- **wash_plateau** (gap > ``gap_plateau_s``) — a minutes-long mop wash (ByRoom) or
  long transit. An unambiguous boundary; pass-turns are seconds, never minutes.
- **transit** (``gap_transit_s`` < gap ≤ ``gap_plateau_s`` AND area stays flat) — a
  ~60-90 s inter-room hop that covered no new floor yet. A real transition the old
  rule discarded (it required an area jump), which left under-splits unrecoverable.
- **area_jump** (`cleaning_area` rises ≥ ``area_jump_m2`` EITHER in the stretch
  AFTER the blip, read forward to the next blip, OR as the discontinuity AT the
  blip itself) — new floor around a delayed step.
- **weak** (a short delayed step, flat area) — most likely a multi-pass turn
  (re-covering the same room); not a boundary unless the user splits it.

WHY THE AREA SIGNAL IS READ BOTH WAYS. The forward look was added because
`cleaning_area` packets lag the `cleaning_time` tick, so the next room's
area-jump can land a tick *after* the boundary: the original same-instant rule
missed path-varied boundaries — a Narrow-intensity room whose area has already
plateaued, the next room's area catching up a tick later.

But the lag is not always a tick late. Measured across all seven of Alfred's
two-room group phases (2026-08-02..03, replayed from recorder data via
``.claude/notes/_probe_replay_segmenter.py``), the finished room's area often
flushes ON the boundary sample instead: the discontinuity AT the blip was 2-3 m²
in 7/7, while the forward stretch was only 1 m² in 3/7 because the trailing room
was small. Forward-only therefore rejected TRUE boundaries the gap filter had
already found correctly, and every one of those phases fell back to an even split.

Neither look dominates, so a blip is an area_jump when EITHER clears the
threshold. Replacing one with the other just trades which class gets missed.

Area attribution is recomputed from the samples for whatever active set is chosen
— this is why re-segmentation is exact and a client-side regroup would not be:
across a wash_plateau the lagged END area reads FORWARD to the next room's start
(no new floor is covered in the dock, so the area that posts is THIS room's lag);
across every other kind it stays same-instant (the rise is the NEXT room's floor).

``expected_rooms`` (internal: the dispatched queue length) caps over-splitting:
the counters alone can't tell an edge→fill / progressive-area pass-turn from a
true boundary, so when more boundaries are found than the queue allows, only the
strongest are kept (a long plateau outranks a short delayed step). External
callers pass None and let the user reconcile in review.

`cleaning_area` and `cleaning_time` update on separate packets that can land out
of order at the same timestamp (the area lags the clock), so area is read via
``area_at(t)`` — the monotonic area *reached by* time t — rather than carried
forward, which would undercount the room that owns the lagging tick.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .timestamp_utils import UTC, datetime_to_utc_iso, parse_timestamp

# Defaults (seconds / m²). cleaning_time ticks every ~30 s while cleaning.
_CADENCE_S = 30.0
_GAP_DELAYED_S = 35.0   # gap above this = a delayed step (a hop or a pass-turn)
_GAP_TRANSIT_S = 60.0   # gap above this (≤ plateau) with FLAT area = an inter-room transit
_GAP_PLATEAU_S = 90.0   # gap above this = an unambiguous boundary (wash / long transit)
_AREA_JUMP_M2 = 2.0     # cleaning_area delta across a delayed step marking new floor

# A firmware freeze/stall (or an over-long dock) shows up as a long INTERIOR gap between
# cleaning_time increments. cleaning_time is THE cleaning clock (~30 s ticks WHILE cleaning),
# so a gap longer than _STALL_WALL_S between two of its ticks means the robot did not clean
# for that whole span — dead time, not this room's work. Left in, it inflates the enclosing
# segment's time_wall_s, so a real room's learned clean-time reads far too long (external-run
# robustness Item 2). build_segments carves such a gap out of time_wall_s (booked as overhead).
# Deliberately WELL above any legit mop wash (gap_plateau_s = 90 s; a wash is a few minutes)
# AND above any active-cleaning tick gap, so a NORMAL run's segments stay byte-identical. area
# and time_active_s are untouched — time_active_s is already freeze-immune (the counter simply
# doesn't tick while frozen). Note: an area guard would be WRONG here — the post-freeze resume
# tick posts new cleaning area, so area appears to "rise across" the gap even for a real freeze.
_STALL_WALL_S = 600.0        # 10 min — an interior gap between cleaning_time ticks longer than this = dead time

# Only a true wash/dock plateau forward-reads the lagged area to the next room. A
# transit covered no new floor; an area_jump's rise is the NEXT room's — both stay
# same-instant (see build_segments).
_FORWARD_AREA_KINDS = frozenset({"wash_plateau"})

# Strength for count-ranking (select_active(expected_rooms=...)). Integer kind bands
# keep wash > transit > area_jump > weak above any plausible area/gap fraction; the
# settings-flip confidence bonus floats a corroborated cut up within its band. On the
# legacy wash/area_jump-only pool this reproduces the old (gap>plateau, area_after) sort.
_KIND_WEIGHT = {"wash_plateau": 4000.0, "transit": 2000.0, "area_jump": 1000.0, "weak": 0.0}
_CONFIDENT_BONUS = 500.0


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


@dataclass
class _Window:
    """A prepared, frame-invariant view of a counter-sample stream.

    ``incs`` are the cleaning_time increment timestamps (the ~30 s ticks) AFTER the
    last reset; ``area_at``/``batt_at`` read the monotonic value reached by time t.
    Pure given the samples — the same stream always yields the same window, so a
    candidate's ``position`` (its index into ``incs``) is a stable boundary id.
    """

    norm: list[tuple[datetime, float, float, Any]]
    reset_t: datetime
    incs: list[tuple[datetime, float]]
    area_at: Callable[[datetime], float]
    batt_at: Callable[[datetime], Any]


def _prepare_window(samples: list[dict[str, Any]], *, cadence_s: float = _CADENCE_S) -> _Window | None:
    """Normalize → sort → trim to the last job, and expose area_at/batt_at/incs.

    Returns ``None`` when there is no usable signal (empty stream, or no
    cleaning_time increments after the reset — e.g. an adapter without counters)."""
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
        return None

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
        return None

    return _Window(norm=norm, reset_t=reset_t, incs=incs, area_at=area_at, batt_at=batt_at)


#: Tolerance on the area comparison. `cleaning_area` arrives in whole ~1 m² device
#: steps, but an imperial HA reports them in ft² (10.76 per step, itself a 2-dp
#: rounding of 10.7639), so a nominally exact N m² lands at N-0.0007 or N+0.0002
#: depending on which way each step rounded. Comparing that to a threshold of
#: exactly 2.0 is a coin flip run-to-run: measured 4 of 7 real boundaries lost to
#: it. Far below the 1 m² quantum, so it can never promote a smaller real jump.
_AREA_EPS = 0.01


#: Vacuum states that mean the robot is NOT on the floor cleaning. A dock action
#: (wash / dry / empty) is physically impossible unless the robot is docked, and
#: the cleaning counters cannot advance while it is — the two are mutually
#: exclusive by construction, not by observation. Measured on 5 days of Alfred
#: history: all 229 rising counter ticks had the vacuum `cleaning`, and all 49
#: dock-status changes had it `docked`. No overlap.
_UNDOCKED_EXIT_STATES: frozenset[str] = frozenset({"docked", "returning", "returning_to_dock"})


def _left_cleaning(samples: list[dict[str, Any]], a: Any, b: Any) -> bool | None:
    """Did the vacuum report leaving `cleaning` between ``a`` and ``b``?

    ``True`` / ``False`` when the window carries vacuum_state at all, ``None``
    when it carries none — an OLD record, an external ingest, or a synthetic
    stream. None means "no information", and the caller must then behave exactly
    as it did before this signal existed: absence of evidence cannot be allowed
    to silently reclassify historical runs.

    An ANY-match over the interval, not an endpoint check: entity states lag the
    robot, and both edges of a dock trip legitimately read `cleaning`.
    """
    seen = False
    for s in samples:
        if not isinstance(s, dict):
            continue
        state = s.get("vacuum_state")
        if state is None:
            continue
        when = _to_dt(s.get("t"))
        if when is None or not (a <= when <= b):
            continue
        seen = True
        if str(state).strip().lower() in _UNDOCKED_EXIT_STATES:
            return True
    return False if seen else None


def _classify(
    gap: float,
    area_after: float,
    area_delta: float,
    *,
    gap_transit_s: float,
    gap_plateau_s: float,
    area_jump_m2: float,
    left_cleaning: bool | None = None,
) -> str:
    """Kind of a blip from its gap and the area around it.

    ``area_after`` is the stretch forward to the next blip; ``area_delta`` is the
    discontinuity at the blip itself. Either can carry the finished room's
    flushed area depending on when the packet lands, so the stronger one decides
    (see the module docstring for the measurements behind that).
    """
    # A wash_plateau claims "the robot went to the dock and washed". A dock action
    # requires being docked, so if the vacuum never reported leaving `cleaning`
    # across this gap, the claim is false however long the gap was — it is an
    # in-room stall, and letting it keep the kind hands it weight 4000, which
    # outranks the real boundary and displaces it under the expected_rooms cap.
    # `None` = the stream predates the signal; behave exactly as before.
    if gap > gap_plateau_s and left_cleaning is not False:
        return "wash_plateau"
    # Ordered area-first, which is equivalent to the original transit-first form:
    # that arm required `area_after < area_jump_m2`, so the two were already
    # mutually exclusive on the area test. Only the signal and the epsilon change.
    if max(area_after, area_delta) >= area_jump_m2 - _AREA_EPS:
        return "area_jump"
    if gap > gap_transit_s:
        return "transit"
    return "weak"


def find_candidates(
    samples: list[dict[str, Any]],
    *,
    gap_delayed_s: float = _GAP_DELAYED_S,
    gap_transit_s: float = _GAP_TRANSIT_S,
    gap_plateau_s: float = _GAP_PLATEAU_S,
    area_jump_m2: float = _AREA_JUMP_M2,
    cadence_s: float = _CADENCE_S,
) -> list[dict[str, Any]]:
    """Every detected boundary in the stream, in cleaning order — no discards.

    A blip is any gap > ``gap_delayed_s`` between cleaning_time ticks. Each is
    returned (the selector decides which are active) with::

        {id, position, gap_s, area_after_m2, area_at_blip_m2, kind, strength,
         confident, t}

    ``id`` == ``position`` (the increment-tick index) is a stable handle for the
    frozen samples — the card toggles boundaries by id. ``confident`` is the
    geometric base (a wash_plateau only); the ingest layer upgrades it where a
    settings flip corroborates the cut. ``area_after`` is read FORWARD to the next
    blip (the area lag). Returns [] when there is no usable signal.
    """
    win = _prepare_window(samples, cadence_s=cadence_s)
    if win is None:
        return []
    incs = win.incs
    area_at = win.area_at

    blip_positions = [
        i for i in range(1, len(incs))
        if (incs[i][0] - incs[i - 1][0]).total_seconds() > gap_delayed_s
    ]
    out: list[dict[str, Any]] = []
    for n, bi in enumerate(blip_positions):
        nxt = blip_positions[n + 1] if n + 1 < len(blip_positions) else len(incs)
        gap = (incs[bi][0] - incs[bi - 1][0]).total_seconds()
        area_after = area_at(incs[nxt - 1][0]) - area_at(incs[bi][0])
        # The discontinuity AT the blip — the finished room's area flushing onto
        # the boundary sample rather than a tick later.
        area_delta = area_at(incs[bi][0]) - area_at(incs[bi - 1][0])
        kind = _classify(
            gap, area_after, area_delta,
            gap_transit_s=gap_transit_s, gap_plateau_s=gap_plateau_s, area_jump_m2=area_jump_m2,
            left_cleaning=_left_cleaning(samples, incs[bi - 1][0], incs[bi][0]),
        )
        strength = (
            _KIND_WEIGHT[kind]
            + max(area_after, area_delta, 0.0)
            + min(gap, 600.0) / 600.0
        )
        out.append(
            {
                "id": bi,
                "position": bi,
                "gap_s": round(gap, 1),
                "area_after_m2": round(area_after, 2),
                # Distinct name: `area_delta_m2` already means a SEGMENT's own
                # span in the segment dict, and two fields with one name that
                # measure different things is how a reader gets it wrong.
                "area_at_blip_m2": round(area_delta, 2),
                "kind": kind,
                "strength": round(strength, 3),
                "confident": kind == "wash_plateau",
                "t": datetime_to_utc_iso(incs[bi][0]),
            }
        )
    return out


def select_active(
    candidates: list[dict[str, Any]],
    *,
    expected_rooms: int | None = None,
    active_ids: list[int] | None = None,
    default: str = "confident",
    kinds: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Pick the active boundary set from a candidate pool, in cleaning order.

    ``kinds`` (allow-list) pre-filters the pool in every mode. Exactly one mode
    resolves, by precedence:

    - ``active_ids`` — exactly those candidate ids (the per-boundary toggle path;
      unknown ids ignored, ``[]`` ⇒ one room).
    - ``expected_rooms`` — the strongest ``expected_rooms - 1`` by (confident,
      strength); selecting from the full pool lets a higher count activate
      transit/weak boundaries the legacy filter dropped. Does NOT clamp to the
      pool — the caller reports any cap.
    - ``default`` — ``"confident"`` (the default view), ``"all"``, or ``"none"``.
    """
    pool = [c for c in candidates if kinds is None or c.get("kind") in kinds]

    if active_ids is not None:
        ids = {int(x) for x in active_ids}
        return [c for c in pool if int(c.get("id", c.get("position", -1))) in ids]

    if expected_rooms is not None:
        keep = max(int(expected_rooms) - 1, 0)
        if len(pool) <= keep:
            return list(pool)
        ranked = sorted(
            pool, key=lambda c: (bool(c.get("confident")), _f(c.get("strength"))), reverse=True
        )[:keep]
        return sorted(ranked, key=lambda c: int(c.get("position", 0)))

    if default == "confident":
        return [c for c in pool if c.get("confident")]
    if default == "none":
        return []
    return list(pool)  # "all"


def build_segments(
    samples: list[dict[str, Any]],
    active_candidates: list[dict[str, Any]],
    *,
    cadence_s: float = _CADENCE_S,
    stall_wall_s: float = _STALL_WALL_S,
) -> list[dict[str, Any]]:
    """The ordered per-room segment dicts for a chosen active boundary set.

    Recomputes the window from ``samples`` so area attribution is exact for THIS
    set (a wash_plateau forward-reads the lagged area; every other kind stays
    same-instant). Each segment carries ``boundary_id`` — the active candidate id
    that started it (``None`` for the first) — so the ingest layer can recover the
    active-boundary list after the trailing-segment drop. Returns [] for no signal.
    """
    win = _prepare_window(samples, cadence_s=cadence_s)
    if win is None:
        return []
    incs = win.incs
    area_at = win.area_at
    batt_at = win.batt_at
    norm = win.norm
    reset_t = win.reset_t

    boundary_at: dict[int, str] = {int(c["position"]): c["kind"] for c in active_candidates}
    bid_at: dict[int, int] = {
        int(c["position"]): int(c.get("id", c["position"])) for c in active_candidates
    }

    # Split increments into segments at the active boundaries; everything else
    # stays in-segment (pass-turns and inactive candidates).
    groups: list[list[tuple[datetime, float]]] = [[incs[0]]]
    boundaries: list[str] = ["job_start"]
    group_bids: list[int | None] = [None]
    for i in range(1, len(incs)):
        kind = boundary_at.get(i)
        if kind is not None:
            groups.append([incs[i]])
            boundaries.append(kind)
            group_bids.append(bid_at.get(i))
        else:
            groups[-1].append(incs[i])

    out: list[dict[str, Any]] = []
    prev_ct = 0.0
    prev_area = 0.0
    prev_end_t = reset_t
    for idx, g in enumerate(groups):
        start_t = g[0][0]
        end_t, end_ct = g[-1]
        # Carve interior FREEZE/stall dead-time out of the wall: a gap between consecutive
        # cleaning_time increments longer than stall_wall_s means the robot did not clean for
        # that whole span (the cleaning clock stopped) — booking it as this room's wall would
        # grossly inflate its learned clean time (it is overhead, not cleaning). A normal run
        # has no such gap → wall unchanged. area / time_active_s are already freeze-immune.
        stall_s = 0.0
        for k in range(1, len(g)):
            gap_s = (g[k][0] - g[k - 1][0]).total_seconds()
            if gap_s > stall_wall_s:
                stall_s += gap_s
        # Forward-attribute area across a wash_plateau/dock ONLY (the area that posts
        # there is THIS room's lag); the last segment reads to the final sample
        # (trailing dock lag). Every other boundary stays same-instant — the rise is
        # the next room's new floor.
        if idx + 1 >= len(groups):
            area_ref_t = norm[-1][0] if norm else end_t
        elif boundaries[idx + 1] in _FORWARD_AREA_KINDS:
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
                "boundary_id": group_bids[idx],
                "t_start": datetime_to_utc_iso(start_t),
                "t_end": datetime_to_utc_iso(end_t),
                "ct_start": prev_ct,
                "ct_end": end_ct,
                "area_start_m2": round(prev_area, 2),
                "area_end_m2": round(end_area, 2),
                "area_delta_m2": round(max(end_area - prev_area, 0.0), 2),
                "time_active_s": round(max(end_ct - prev_ct, 0.0), 1),
                "time_wall_s": round(max((end_t - start_t).total_seconds() - stall_s, 0.0), 1),
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


def segment_counters(
    samples: list[dict[str, Any]],
    *,
    expected_rooms: int | None = None,
    cadence_s: float = _CADENCE_S,
    gap_delayed_s: float = _GAP_DELAYED_S,
    gap_plateau_s: float = _GAP_PLATEAU_S,
    area_jump_m2: float = _AREA_JUMP_M2,
    stall_wall_s: float = _STALL_WALL_S,
) -> list[dict[str, Any]]:
    """Segment a counter-sample stream into ordered per-room cleaning bouts.

    Back-compat wrapper over find_candidates → select_active → build_segments for
    internal queue callers. Legacy semantics: a blip is a boundary iff
    ``gap > gap_plateau_s`` OR ``area_after >= area_jump_m2``, trimmed to the
    strongest ``expected_rooms - 1``. The infinite ``gap_transit_s`` collapses the
    transit band (a 60-90 s flat-area gap stays "weak") and the ``kinds`` filter
    drops "weak", so the active set is exactly the old candidate set.

    ``samples`` is a list of dicts ``{t|observed_at, cleaning_time, cleaning_area,
    battery}``. Returns segment dicts in cleaning order; empty if there is no usable
    signal. Pure + frame-invariant. ``expected_rooms`` (the dispatched queue length)
    caps over-splitting; external callers pass ``None``.
    """
    cands = find_candidates(
        samples,
        gap_delayed_s=gap_delayed_s,
        gap_transit_s=float("inf"),
        gap_plateau_s=gap_plateau_s,
        area_jump_m2=area_jump_m2,
        cadence_s=cadence_s,
    )
    active = select_active(
        cands, expected_rooms=expected_rooms, default="all", kinds={"wash_plateau", "area_jump"}
    )
    return build_segments(samples, active, cadence_s=cadence_s, stall_wall_s=stall_wall_s)
