"""External-run ingestion — build a PENDING review record from a captured app run.

An app-started (external) job is captured into an ``active_jobs`` slot with
``status="external"`` (counters + setting selects buffered, no dispatched queue).
When it finishes, this module turns the raw capture into a *pending record* (schema
v2) that the review card resolves:

- **find every boundary** (``find_candidates``) and bake the FULL candidate pool
  into the record — including the transit/weak cuts the legacy filter discarded —
  so the card can offer a precise "split here" at any of them;
- the **default segmentation** is the *confident* cuts only (a long wash plateau OR
  a per-room settings flip across the cut). Uncertain cuts (a short area-rise with
  no flip — an edge->fill turn or a same-settings adjacent room) and transit/weak
  cuts default OFF and surface as split-here candidates, matching the pre-v2 view;
- per segment, bake the recovered ``{area, time, passes, settings}`` plus an
  **area + settings** ranked, **map-scoped, carpet-filtered** shortlist;
- **embed the raw samples** (``counter_samples`` / ``settings_samples``) so the run
  can be re-segmented server-side at any room count or boundary set (see
  ``resegment_pending_record``); these are stripped before serving to the card.

Identity + edge-mop are filled by the user in review; nothing here touches the
learned baselines (that is the confirm service). Pure given its inputs — the caller
loads room config + learned baselines and persists the record under
``external_jobs/``. ``strip_samples`` removes the embedded raw samples on the way
out to the card.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

_LOGGER = logging.getLogger(__name__)

# select_active is the brand-agnostic selection stage (pure ranking/filtering over
# the candidate shape) — it stays a direct framework import. find_candidates /
# build_segments are the brand-specific stages, reached through the pluggable
# job-segmenter engine (the Eufy engine delegates to these same primitives, so the
# Eufy path is byte-identical; see job_segmenter_engines).
from ..counter_segmentation import select_active
from ..timestamp_utils import parse_timestamp
from .job_segmenter_engines import get_job_segmenter_engine
from .room_attribution_engines import get_room_attribution_engine
from .utils import _canonical_clean_mode, _safe_bool, _safe_float, _safe_int

# Settings-match is the PRIMARY shortlist signal: a room whose config matches the
# captured mode/passes/intensity/fan/water is far more reliable than area, because
# cleaning_area is path/pass-cumulative (an odd path or extra pass inflates it, a
# light pass deflates it). Weights — mode + passes move identity/time the most.
_MATCH_W_MODE = 4.0
_MATCH_W_PASSES = 3.0
_MATCH_W_INTENSITY = 2.0
_MATCH_W_FAN = 1.0
_MATCH_W_WATER = 1.0
_SHORTLIST_SIZE = 3
_COLD_ROOM_SCORE = -999.0   # no learned area yet → area tiebreak ranks last
_MOP_MODES = {"mop", "vacuum_mop"}
# A stretch that covered less than this much NEW floor is not a room — it is a
# re-pass, transit-to-dock, or an end-of-run station clean (mop wash / dust empty),
# e.g. the trailing 0 m² "Returning to Wash" segment. Dropped from the review.
_MIN_ROOM_AREA_M2 = 0.5

PENDING_SCHEMA_VERSION = 2


def _resolve_engine_tuning(vacuum_entity_id: str | None) -> tuple[Any, dict[str, Any]]:
    """Resolve the (job-segmenter engine, effective tuning) for a vacuum.

    The engine + tuning come from the adapter's ``job_segmenter`` block; an absent
    block or vacuum id falls back to the Eufy counter engine with its default tuning
    — so external ingestion stays byte-identical for Eufy and pure for the unit tests
    (which pass no vacuum id and so never touch the adapter registry). ``eff`` is the
    engine's ``DEFAULT_TUNING`` overlaid with any adapter overrides: the single source
    of the gap/area/cadence numbers, including the persisted ``gap_transit_s``."""
    engine_name = None
    adapter_tuning = None
    if vacuum_entity_id:
        from .brand_facts import brand_facts_for

        engine_name, adapter_tuning = brand_facts_for(vacuum_entity_id).job_segmenter
    engine = get_job_segmenter_engine(engine_name)
    eff: dict[str, Any] = dict(getattr(engine, "DEFAULT_TUNING", {}))
    if isinstance(adapter_tuning, dict):
        eff.update({k: v for k, v in adapter_tuning.items() if v is not None})
    return engine, eff


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    # Segment t_start/t_end are naive UTC (segment_counters strips the "Z" when it
    # isoformats), while counter/settings samples keep "...Z". parse_timestamp's
    # default treats naive as LOCAL, which shifts a segment's end by the server's UTC
    # offset — pushing a non-final segment past every sample so _segment_settings and
    # _estimate_passes read the LAST segment's values (cross-contaminating per-room
    # settings and defaulting passes to 1). These timestamps are UTC: parse as UTC.
    return parse_timestamp(value, assume_local_naive=False)


def _segment_settings(
    settings_samples: list[dict[str, Any]], t_end: Any
) -> dict[str, str]:
    """Settings in effect during a segment = the most recent snapshot at/before
    its end (the timeline is deduped to one entry per flip, so a flip before the
    segment carries forward)."""
    end = _dt(t_end)
    chosen: dict[str, str] = {}
    for sample in settings_samples or []:
        t = _dt(sample.get("t"))
        if t is None:
            continue
        if end is not None and t > end:
            break
        chosen = sample.get("settings", {}) or chosen
    return dict(chosen)


def _estimate_passes(
    counter_samples: list[dict[str, Any]], t_start: Any, t_end: Any
) -> int:
    """Rough pass count from the area-plateau pattern within a segment: the active
    span divided by the span until cleaning_area stopped rising. ~1 when area
    climbs to the end (single pass); ~2 when it plateaus at the midpoint."""
    start, end = _dt(t_start), _dt(t_end)
    if start is None:
        return 1
    rows: list[tuple[datetime, float]] = []
    for sample in counter_samples or []:
        t = _dt(sample.get("t"))
        if t is None or t < start or (end is not None and t > end):
            continue
        area = _safe_float(sample.get("cleaning_area"), -1.0)
        if area >= 0:
            rows.append((t, area))
    if len(rows) < 2:
        return 1
    rows.sort(key=lambda r: r[0])
    peak = max(area for _t, area in rows)
    t_first, t_last = rows[0][0], rows[-1][0]
    t_peak = next((t for t, area in rows if area >= peak), t_last)
    total = (t_last - t_first).total_seconds()
    cover = (t_peak - t_first).total_seconds()
    if cover <= 0 or total <= 0:
        return 1
    return max(1, round(total / cover))


def _baseline_area_by_slug(
    baselines: list[dict[str, Any]], map_id: Any
) -> dict[str, float]:
    """{room_slug -> learned avg_area_m2} for the active map (from room_baselines)."""
    out: dict[str, float] = {}
    for entry in baselines or []:
        if str(entry.get("map_id")) != str(map_id):
            continue
        slug = str(entry.get("room_slug", "")).strip().lower()
        area = _safe_float(entry.get("avg_area_m2"), 0.0)
        if slug and area > 0:
            out[slug] = area
    return out


def _setting_eq(a: Any, b: Any) -> float:
    """1.0 when two setting strings match case-insensitively (and non-empty)."""
    sa = str(a or "").strip().lower()
    sb = str(b or "").strip().lower()
    return 1.0 if sa and sa == sb else 0.0


def _rank_shortlist(
    *,
    seg_area: float,
    seg_settings: dict[str, Any] | None,
    seg_passes: int,
    rooms: dict[str, Any],
    area_by_slug: dict[str, float],
) -> list[dict[str, Any]]:
    """Top-N rooms for a segment, ranked SETTINGS-first.

    cleaning_area is path/pass-cumulative, not a room's unique floor size, so it is
    a poor identity signal (an odd path or extra pass inflates it, a light pass
    deflates it). A room whose *config* matches the captured mode/passes/intensity/
    fan/water is far more reliable, so the weighted settings-match is the primary
    sort key and area-distance is only a tiebreak among settings-equal rooms. The
    map is already scoped by the caller; carpet rooms drop for a mopped segment.
    """
    settings = seg_settings or {}
    mode = _canonical_clean_mode(settings.get("clean_mode"))
    mopped = mode in _MOP_MODES
    scored: list[tuple[float, float, dict[str, Any]]] = []
    for rid, room in (rooms or {}).items():
        if not isinstance(room, dict):
            continue
        slug = str(room.get("slug", "")).strip().lower()
        is_carpet = str(room.get("floor_type", "")).strip().lower().startswith("carpet")
        if mopped and is_carpet:
            continue  # a mopped segment cannot be a carpet room (override = all-rooms)

        settings_score = 0.0
        if mode and _canonical_clean_mode(room.get("clean_mode")) == mode:
            settings_score += _MATCH_W_MODE
        if seg_passes and _safe_int(room.get("clean_passes"), 0) == seg_passes:
            settings_score += _MATCH_W_PASSES
        settings_score += _MATCH_W_INTENSITY * _setting_eq(
            settings.get("clean_intensity"), room.get("clean_intensity")
        )
        settings_score += _MATCH_W_FAN * _setting_eq(
            settings.get("fan_speed"), room.get("fan_speed")
        )
        settings_score += _MATCH_W_WATER * _setting_eq(
            settings.get("water_level"), room.get("water_level")
        )

        learned_area = area_by_slug.get(slug)
        area_tiebreak = (
            -abs(_safe_float(seg_area) - learned_area) if learned_area else _COLD_ROOM_SCORE
        )
        scored.append(
            (
                settings_score,
                area_tiebreak,
                {
                    "room_id": _safe_int(rid, -1),
                    "slug": slug,
                    "name": room.get("name"),
                    "is_carpet": is_carpet,
                    "learned_area_m2": learned_area,
                    "settings_score": round(settings_score, 2),
                    "score": round(area_tiebreak, 2),
                },
            )
        )
    # primary: settings-match DESC; tiebreak: area distance (closer first).
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [entry for _ss, _at, entry in scored[:_SHORTLIST_SIZE]]


def _mark_candidate_confidence(
    candidates: list[dict[str, Any]],
    counter_samples: list[dict[str, Any]],
    settings_samples: list[dict[str, Any]],
    *,
    engine: Any,
    tuning: dict[str, Any],
) -> None:
    """Set ``confident`` on each candidate (mutates in place).

    A cut is confident when it is a long wash plateau OR the per-room settings flip
    across it. Computed the pre-v2 way — over the wash/area_jump finest, comparing
    the settings at consecutive segment ends — so the default (confident-only) view
    matches the old segmentation. transit/weak cuts are never confident here: they
    default OFF and surface only as split-here candidates.
    """
    finest = engine.build_segments(
        counter_samples,
        select_active(candidates, default="all", kinds={"wash_plateau", "area_jump"}),
        tuning=tuning,
    )
    confident_ids: set[int] = set()
    prev_settings: dict[str, str] | None = None
    for k, seg in enumerate(finest):
        settings = _segment_settings(settings_samples, seg.get("t_end"))
        bid = seg.get("boundary_id")
        if k > 0 and bid is not None:
            if seg.get("boundary") == "wash_plateau" or (bool(settings) and settings != prev_settings):
                confident_ids.add(int(bid))
        prev_settings = settings
    for c in candidates:
        c["confident"] = (c.get("kind") == "wash_plateau") or (int(c.get("id", -1)) in confident_ids)


def _enrich_segments(
    segments: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    counter_samples: list[dict[str, Any]],
    settings_samples: list[dict[str, Any]],
    rooms: dict[str, Any],
    baselines: list[dict[str, Any]],
    map_id: Any,
) -> tuple[list[dict[str, Any]], int, list[int]]:
    """Bake per-segment review fields (settings, passes, shortlist, confidence),
    drop only TRAILING sub-room segments, and re-index 0..N-1.

    Returns ``(out_segments, confident_count, active_boundary_ids)``. Shared by
    finalize (build_pending_record) and re-segment so the two never drift. A LEADING
    or middle ~0 m² segment is KEPT (cleaning_area lags — a short first room can read
    ~0 m² as its area lands on the next segment); only the end-of-run station clean /
    re-pass is dropped.
    """
    area_by_slug = _baseline_area_by_slug(baselines, map_id)
    conf_by_id = {int(c.get("id", -1)): bool(c.get("confident")) for c in candidates}

    last_real = -1
    for i, seg in enumerate(segments):
        if _safe_float(seg.get("area_delta_m2")) >= _MIN_ROOM_AREA_M2:
            last_real = i

    out_segments: list[dict[str, Any]] = []
    confident_count = 0
    active_ids: list[int] = []
    for index, seg in enumerate(segments):
        if index > last_real:
            break  # trailing sub-room stretch — drop it and everything after
        order = len(out_segments)  # re-index over KEPT segments
        bid = seg.get("boundary_id")
        settings = _segment_settings(settings_samples, seg.get("t_end"))
        passes = _estimate_passes(counter_samples, seg.get("t_start"), seg.get("t_end"))

        confident: bool | None = None
        if order > 0:
            confident = bool(conf_by_id.get(int(bid), False)) if bid is not None else False
            if confident:
                confident_count += 1
        if bid is not None:
            active_ids.append(int(bid))

        out_segments.append(
            {
                "order": order,
                "boundary_id": bid,
                "t_start": seg.get("t_start"),
                "t_end": seg.get("t_end"),
                "area_m2": _safe_float(seg.get("area_delta_m2")),
                "time_wall_s": _safe_int(seg.get("time_wall_s"), 0),
                "time_active_s": _safe_int(seg.get("time_active_s"), 0),
                "pass_count": passes,
                "settings": settings,
                "boundary": seg.get("boundary"),
                "confident_boundary": confident,
                "shortlist": _rank_shortlist(
                    seg_area=_safe_float(seg.get("area_delta_m2")),
                    seg_settings=settings,
                    seg_passes=passes,
                    rooms=rooms,
                    area_by_slug=area_by_slug,
                ),
            }
        )
    return out_segments, confident_count, active_ids


def strip_samples(rec: dict[str, Any]) -> dict[str, Any]:
    """Remove the embedded raw samples (mutates + returns rec) before serving a
    pending record to the card — it never needs them; re-segmentation (counter) and
    re-attribution (pose) read them server-side. A no-op on v1 records (keys absent)."""
    rec.pop("counter_samples", None)
    rec.pop("settings_samples", None)
    rec.pop("pose_samples", None)
    return rec


# --- W5c: pose-attribution identity (counter owns time/area; classifier owns identity) -----
#
# The counter-plateau segmenter owns each segment's *time/area* boundaries; the room-
# attribution engine owns *which managed room* a segment is. We use the classifier two ways:
#   - ENRICH: when counter segmentation produced segments, label each with the cleaned room
#     the pose stream says dominated its window and PROMOTE that room to ``shortlist[0]`` (the
#     card auto-selects shortlist[0], so the wizard opens pre-answered). Only in ROBUST mode —
#     anchor-only attribution can false-positive a parked dock, so we don't override the
#     settings-based shortlist with a low-confidence guess.
#   - STAND ALONE (``build_attributed_job``): when counter segmentation produced NOTHING (thin
#     counters / no plateaus — the common app-run case), build a pending record straight from
#     the pose attribution so the run isn't lost. Built in BOTH modes (a reviewable pre-fill
#     beats no record), tagged with ``attribution_mode`` so the card can flag anchor-only.


def _resolve_attribution(vacuum_entity_id: str | None) -> tuple[Any, dict[str, Any]]:
    """Resolve the (room-attribution engine, effective tuning) for a vacuum — the adapter's
    ``room_attribution`` block over the engine's ``DEFAULT_TUNING`` (Eufy fallback for an absent
    block, mirroring ``_resolve_engine_tuning``). ``interval_s`` is the single source the engine's
    dwell and this module's stand-alone timing both read."""
    engine_name = None
    adapter_tuning = None
    if vacuum_entity_id:
        from .brand_facts import brand_facts_for

        engine_name, adapter_tuning = brand_facts_for(vacuum_entity_id).room_attribution
    engine = get_room_attribution_engine(engine_name)
    eff: dict[str, Any] = dict(getattr(engine, "DEFAULT_TUNING", {}))
    if isinstance(adapter_tuning, dict):
        eff.update({k: v for k, v in adapter_tuning.items() if v is not None})
    return engine, eff


def _attribute(
    pose_samples: list[dict[str, Any]] | None, vacuum_entity_id: str | None
) -> dict[str, Any] | None:
    """Run the resolved attribution engine over the run's pose stream → its result dict plus
    the resolved ``interval_s`` (for stand-alone timing). ``None`` when there is no pose stream
    (no live map / non-map brand) — the caller then behaves exactly as pre-W5c."""
    if not pose_samples:
        return None
    engine, tuning = _resolve_attribution(vacuum_entity_id)
    try:
        result = dict(engine.attribute(pose_samples, tuning=tuning))
    except Exception:
        # Attribution is a best-effort enrichment — never let an engine error lose the run.
        # Returning None degrades to the counter-only path (and build_attributed_job returns
        # None cleanly), so the run is still captured and the slot still clears.
        _LOGGER.exception("eufy_vacuum: room attribution failed; building without pose identity")
        return None
    result["interval_s"] = _safe_float(tuning.get("interval_s"), 2.0)
    return result


def _dominant_room(
    pose_samples: list[dict[str, Any]],
    t_start: Any,
    t_end: Any,
    cleaned: set[int] | None = None,
) -> int | None:
    """The room with the most pose ticks inside ``[t_start, t_end]`` — a counter segment's
    identity. When ``cleaned`` is given, only those rooms count (so transit / parked-dock
    ticks in the window never win); when ``None``, ANY room is eligible — used to NAME a
    counter segment the swept-area couldn't confirm (e.g. the run's first room cleaned while
    ``cleaning_area`` was stale), since the counter has already vouched it IS a real cleaning
    segment, so the only question left is which room the robot physically dwelt in. ``None``
    when no eligible room appears in the window."""
    s0, s1 = _dt(t_start), _dt(t_end)
    counts: dict[int, int] = {}
    for sample in pose_samples or []:
        rid = sample.get("current_room")
        if rid is None or (cleaned is not None and rid not in cleaned):
            continue
        t = _dt(sample.get("t"))
        if t is None or (s0 is not None and t < s0) or (s1 is not None and t > s1):
            continue
        counts[rid] = counts.get(rid, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda r: counts[r])


def _room_shortlist_entry(room_id: int, rooms: dict[str, Any]) -> dict[str, Any]:
    """A ``shortlist`` entry for a room known by identity (not by area/settings ranking)."""
    room = (rooms or {}).get(str(room_id))
    room = room if isinstance(room, dict) else {}
    return {
        "room_id": room_id,
        "slug": str(room.get("slug", "")).strip().lower(),
        "name": room.get("name"),
        "is_carpet": str(room.get("floor_type", "")).strip().lower().startswith("carpet"),
        "learned_area_m2": None,
        "settings_score": None,
        "score": None,
        "from_pose": True,
    }


def _promote_pose_room(seg: dict[str, Any], room_id: int, rooms: dict[str, Any]) -> None:
    """Make ``room_id`` the segment's ``shortlist[0]`` (the card pre-selects it). If the room
    was already shortlisted, keep its richer (area/settings) entry but move it to front and tag
    ``from_pose``; otherwise prepend a bare identity entry. Caps at ``_SHORTLIST_SIZE``."""
    shortlist = list(seg.get("shortlist") or [])
    existing = next(
        (e for e in shortlist if _safe_int(e.get("room_id"), -2) == room_id), None
    )
    head = {**existing, "from_pose": True} if existing else _room_shortlist_entry(room_id, rooms)
    rest = [e for e in shortlist if _safe_int(e.get("room_id"), -2) != room_id]
    seg["shortlist"] = [head, *rest][:_SHORTLIST_SIZE]
    seg["pose_room_id"] = room_id


def _apply_pose_identity(
    out_segments: list[dict[str, Any]],
    pose_samples: list[dict[str, Any]],
    attribution: dict[str, Any],
    rooms: dict[str, Any],
) -> None:
    """Label each counter segment with its dominant room and promote it to ``shortlist[0]``
    (mutates). ROBUST mode only — see the section note.

    A swept-area-CONFIRMED room (one in ``cleaned``) is preferred; but when no cleaned room
    dominates a segment — e.g. ``cleaning_area`` was stale through the run's FIRST room, so the
    engine never credited it any swept area — we fall back to the dominant room of ANY identity.
    That fallback is safe precisely because the COUNTER already vouched this window is a real
    cleaning segment (a time/area plateau the segmenter split out): the only open question is
    *which* room, and the room the robot dwelt in answers it. Without the fallback the segment
    keeps its settings-ranked ``shortlist[0]`` (a wrong room) and the dropped first room is lost.
    ``pose_confidence`` records which path named the segment (``cleaned`` vs ``presence``)."""
    if attribution.get("mode") != "robust":
        return
    cleaned = attribution.get("cleaned") or set()
    mode = attribution.get("mode")
    for seg in out_segments:
        rid = (
            _dominant_room(pose_samples, seg.get("t_start"), seg.get("t_end"), cleaned)
            if cleaned
            else None
        )
        confidence = "cleaned"
        if rid is None:
            rid = _dominant_room(pose_samples, seg.get("t_start"), seg.get("t_end"))
            confidence = "presence"
        if rid is not None:
            _promote_pose_room(seg, rid, rooms)
            seg["pose_mode"] = mode
            seg["pose_confidence"] = confidence


def reconcile_dispatched_identity(
    *,
    room_timings: list[dict[str, Any]],
    pose_samples: list[dict[str, Any]] | None,
    vacuum_entity_id: str | None,
    positional_valid: bool,
    slug_by_id: dict[int, str] | None = None,
) -> str | None:
    """CONSERVATIVELY reconcile an ATOMIC dispatched run's POSITIONAL room_timings (segment K ->
    queue room K) against the native current_room the pose sampler buffered. MUTATES room_timings
    in place; returns the attribution mode (or None when there is no usable pose). The counter
    owns each segment's time/area; the room-attribution engine owns *which room* it was.

    ROBUST mode only — a stream with no ``cleaning_area`` (anchor-only) is left untouched, so a
    weak signal never rewrites a dispatched assignment. Per segment, the room the vacuum physically
    DWELT in most during the segment window (``_dominant_room`` presence — dock ticks are already
    nulled to current_room=None, so a dock trip never wins) is the identity signal:

      - CONFIRM  it equals the positional room_id -> stamp ``pose_confidence="confirmed"``, no change.
      - RESCUE   ``positional_valid`` is False (the counter K->K is ALREADY known-unreliable: segment
                 count != queue count) -> set ``room_id``/``slug`` to the pose room + stamp
                 ``pose_correction="rescued"`` / ``pose_prior_room_id``. Pure gain: the positional
                 guess had nothing to lose, and the run is already excluded from the learned
                 aggregate (transit_capture_valid False), so this only sharpens the record/review.
      - FLAG     ``positional_valid`` AND the pose names a DIFFERENT room -> keep the positional
                 room_id, annotate ``attribution_disagreement={positional, pose}`` for human review.
                 Never silently override a working assignment; learning inclusion is UNCHANGED.

    No pose / anchor-only / a window the pose can't name -> that timing is byte-identical to the
    positional path (no regression). Strict-order (phase) jobs never call this — they already
    capture per-phase timings. See ``_apply_pose_identity`` for the external sibling."""
    if not pose_samples:
        return None
    attribution = _attribute(pose_samples, vacuum_entity_id)
    if not attribution or attribution.get("mode") != "robust":
        return attribution.get("mode") if attribution else None
    slug_by_id = slug_by_id or {}
    for rt in room_timings:
        window_room = _dominant_room(
            pose_samples, rt.get("cleaning_start"), rt.get("cleaning_end")
        )
        if window_room is None:
            continue  # pose can't name this window -> leave the positional assignment as-is
        positional = _safe_int(rt.get("room_id"), -1)
        if window_room == positional:
            rt["pose_confidence"] = "confirmed"
        elif not positional_valid:
            rt["pose_prior_room_id"] = positional
            rt["room_id"] = window_room
            rt["slug"] = slug_by_id.get(window_room) or rt.get("slug")
            rt["pose_correction"] = "rescued"
        else:
            rt["attribution_disagreement"] = {"positional": positional, "pose": window_room}
    return "robust"


def build_attributed_job(
    *,
    detection_ts: str | None,
    map_id: Any,
    pose_samples: list[dict[str, Any]] | None,
    attribution: dict[str, Any] | None,
    settings_samples: list[dict[str, Any]],
    rooms: dict[str, Any],
    baselines: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Stand up a pending review record straight from the pose attribution, for a run the
    counter segmenter couldn't split (the common app-run case — see the section note). One
    segment per cleaned room: area = the engine's swept m² (authoritative), active time = the
    room's tick count × cadence, identity pre-filled as ``shortlist[0]``. Returns ``None`` when
    there is no usable attribution (so finalize writes nothing, exactly as pre-W5c).

    NOT counter-resegmentable (no counter samples embedded → the card hides the room-count /
    split-here controls); the user can still re-assign or merge rooms in the wizard. The raw
    ``pose_samples`` ARE embedded, though, so the run can be re-ATTRIBUTED server-side after an
    engine fix (the pose-path sibling of re-segmentation). ``time_active_s``
    is the real per-room cleaning time even when the ``[t_start, t_end]`` windows of interleaved
    rooms overlap (the windows are display-only). Assumes ``pose_samples`` are time-ordered —
    guaranteed by the single ``async_track_time_interval`` sampler (one append per tick); the
    classification engine shares that assumption (its run-length encoding is order-sensitive)."""
    if not attribution or not attribution.get("cleaned"):
        return None
    cleaned = attribution["cleaned"]
    per_room = attribution.get("per_room") or {}
    mode = attribution.get("mode")
    interval_s = _safe_float(attribution.get("interval_s"), 2.0)
    area_by_slug = _baseline_area_by_slug(baselines, map_id)

    # Per cleaned room: first/last tick t (display window) + tick count (active time).
    info: dict[int, dict[str, Any]] = {}
    for sample in pose_samples or []:
        rid = sample.get("current_room")
        if rid is None or rid not in cleaned:
            continue
        entry = info.get(rid)
        if entry is None:
            info[rid] = {"first": sample.get("t"), "last": sample.get("t"), "n": 1}
        else:
            entry["last"] = sample.get("t")
            entry["n"] += 1
    if not info:
        return None

    # Sort cleaned rooms by first-seen tick. epoch via _dt so its tz-awareness matches the
    # parsed sample timestamps (never mix naive/aware in the sort key).
    epoch = _dt("1970-01-01T00:00:00Z")
    ordered = sorted(info.items(), key=lambda kv: _dt(kv[1]["first"]) or epoch)
    segments: list[dict[str, Any]] = []
    for order, (rid, entry) in enumerate(ordered):
        settings = _segment_settings(settings_samples, entry["last"])
        area = round(_safe_float((per_room.get(rid) or {}).get("swept_area_m2"), 0.0), 2)
        active_s = int(round(entry["n"] * interval_s))
        wall_s = active_s
        ts0, ts1 = _dt(entry["first"]), _dt(entry["last"])
        if ts0 is not None and ts1 is not None:
            wall_s = max(active_s, int((ts1 - ts0).total_seconds()))
        seg = {
            "order": order,
            "boundary_id": None,
            "t_start": entry["first"],
            "t_end": entry["last"],
            "area_m2": area,
            "time_wall_s": wall_s,
            "time_active_s": active_s,
            "pass_count": 1,  # not recoverable from pose alone
            "settings": settings,
            "boundary": "pose_attribution",
            # No counter boundary to be confident about; confidence rides attribution_mode.
            "confident_boundary": None,
            "pose_mode": mode,
            "shortlist": _rank_shortlist(
                seg_area=area,
                seg_settings=settings,
                seg_passes=1,
                rooms=rooms,
                area_by_slug=area_by_slug,
            ),
        }
        _promote_pose_room(seg, rid, rooms)  # classified room becomes shortlist[0]
        segments.append(seg)

    return {
        "schema_version": PENDING_SCHEMA_VERSION,
        "status": "pending",
        "origin": "external",
        "source": "pose_attribution",  # a pose-only record (no counter segmentation)
        "attribution_mode": mode,
        "detection_ts": detection_ts,
        "map_id": str(map_id),
        "segment_count": len(segments),
        "suggested_room_count": len(segments),
        "gap_transit_s": 60.0,  # schema field; unused (no counter resegment for pose-only)
        "candidates": [],  # no counter candidates → resegmentable=False at the service
        "active_boundaries": [],
        # Raw pose embedded so the run can be RE-ATTRIBUTED server-side after an engine fix
        # (the pose-path sibling of counter re-segmentation). Stripped before serving to the
        # card. Bounded by _MAX_POSE_SAMPLES (active_job.py).
        "pose_samples": list(pose_samples or []),
        "segments": segments,
    }


def build_pending_record(
    *,
    detection_ts: str | None,
    map_id: Any,
    counter_samples: list[dict[str, Any]],
    settings_samples: list[dict[str, Any]],
    rooms: dict[str, Any],
    baselines: list[dict[str, Any]],
    vacuum_entity_id: str | None = None,
    pose_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Turn a captured external run into a pending review record (schema v2), or None
    when there is no usable cleaning signal (so a false-start writes nothing).

    The default segmentation is the *confident* cuts only; the full candidate pool
    (incl. the transit/weak cuts the legacy filter dropped) and the raw samples are
    embedded so the card can offer split-here and the server can re-segment to any
    room count or boundary set. Segmentation routes through the adapter's job-segmenter
    engine (``vacuum_entity_id`` resolves it; absent → the Eufy counter engine,
    byte-identical).

    W5c — pose attribution (when ``pose_samples`` is supplied): the room-attribution
    engine recovers the cleaned-room SET, used to (a) PROMOTE each counter segment's
    identified room to ``shortlist[0]`` so the wizard opens pre-answered (robust mode
    only), or (b) STAND UP a record from pose alone (``build_attributed_job``) when the
    counter segmenter found nothing. No pose stream → ``attribution`` is ``None`` and the
    function behaves exactly as pre-W5c.
    """
    counter = counter_samples or []
    settings = settings_samples or []
    # Classifier identity (counter owns time/area; this owns which room). None when there is
    # no pose stream (non-map brand / no live map) → every branch below is pre-W5c behavior.
    attribution = _attribute(pose_samples, vacuum_entity_id)

    engine, tuning = _resolve_engine_tuning(vacuum_entity_id)
    candidates = engine.find_candidates(counter, tuning=tuning)
    _mark_candidate_confidence(candidates, counter, settings, engine=engine, tuning=tuning)

    segments = engine.build_segments(
        counter, select_active(candidates, default="confident"), tuning=tuning
    )
    if not segments:
        # Counter found no plateaus — stand up a record from the pose attribution instead (the
        # common app-run case). None when there's no usable attribution → finalize writes nothing.
        return build_attributed_job(
            detection_ts=detection_ts, map_id=map_id, pose_samples=pose_samples,
            attribution=attribution, settings_samples=settings, rooms=rooms, baselines=baselines,
        )

    out_segments, _confident_count, active_ids = _enrich_segments(
        segments, candidates, counter, settings, rooms, baselines, map_id
    )
    if not out_segments:
        # Every counter stretch was sub-room area — fall back to the pose attribution.
        return build_attributed_job(
            detection_ts=detection_ts, map_id=map_id, pose_samples=pose_samples,
            attribution=attribution, settings_samples=settings, rooms=rooms, baselines=baselines,
        )

    if attribution and pose_samples:
        _apply_pose_identity(out_segments, pose_samples, attribution, rooms)
    # A pose stream existed but named NO segment (degenerate/empty cleaned set, anchor-only which
    # is not promoted, or the engine declined to attribute) → "unavailable", so the wizard prompts
    # a MANUAL room pick instead of silently accepting the settings-ranked shortlist[0] on every
    # segment. "available" when pose named ≥1 segment; None when no pose stream was captured.
    pose_named_any = any(s.get("pose_room_id") is not None for s in out_segments)
    attribution_confidence = (
        "available" if pose_named_any
        else ("unavailable" if pose_samples else None)
    )

    return {
        "schema_version": PENDING_SCHEMA_VERSION,
        "status": "pending",
        "origin": "external",
        # Attribution mode (robust = swept-area; anchor_only = best-effort); None without pose.
        "attribution_mode": attribution.get("mode") if attribution else None,
        # Did the shortlist get a pose identity: available / unavailable (→ prompt manual) / None.
        "attribution_confidence": attribution_confidence,
        "detection_ts": detection_ts,
        "map_id": str(map_id),
        "segment_count": len(out_segments),
        # Default room count = the confident-only view (= segment_count here);
        # uncertain / transit / weak cuts surface as split-here candidates.
        "suggested_room_count": len(out_segments),
        # Persisted from the resolved engine tuning (the single source); for Eufy this
        # is the unchanged 60.0. resegment reads it back to reproduce the candidate pool.
        "gap_transit_s": _safe_float(tuning.get("gap_transit_s"), 60.0),
        "candidates": candidates,
        "active_boundaries": active_ids,
        "counter_samples": counter,
        "settings_samples": settings,
        # Raw pose embedded (when a pose stream was captured) so the run can be RE-ATTRIBUTED
        # server-side after an engine fix — the pose-path sibling of counter re-segmentation.
        # Stripped before serving to the card. Bounded by _MAX_POSE_SAMPLES (active_job.py).
        "pose_samples": list(pose_samples or []),
        "segments": out_segments,
    }


def resegment_pending_record(
    *,
    pending_record: dict[str, Any],
    expected_rooms: int | None = None,
    active_ids: list[int] | None = None,
    rooms: dict[str, Any],
    baselines: list[dict[str, Any]],
    vacuum_entity_id: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Re-segment a v2 pending record from its embedded samples, returning
    ``(new_record, meta)`` (``(None, meta)`` when the selection yields no segment —
    the caller must NOT overwrite a usable record in that case).

    Exactly one selection mode applies: ``active_ids`` (the explicit per-boundary
    toggle set) XOR ``expected_rooms`` (the strongest N-1, capped to the detectable
    pool — ``meta`` reports ``capped``/``capped_at``/``available``) XOR neither
    (reset to the confident-only default). The candidate pool + confidence are
    recomputed from the FROZEN samples (with the record's stored ``gap_transit_s``),
    so the result is internally consistent with the segmentation; samples and the
    full candidate list are preserved in the returned record.
    """
    counter = pending_record.get("counter_samples") or []
    settings = pending_record.get("settings_samples") or []
    if not counter:
        return None, {"error": "no_samples"}

    map_id = pending_record.get("map_id")
    engine, eff = _resolve_engine_tuning(vacuum_entity_id)
    # Reproduce the candidate pool with the record's stored gap_transit_s over the
    # resolved tuning (for Eufy: the engine defaults with the record's 60.0).
    gap_transit_s = _safe_float(
        pending_record.get("gap_transit_s"), _safe_float(eff.get("gap_transit_s"), 60.0)
    )
    seg_tuning = {**eff, "gap_transit_s": gap_transit_s}
    candidates = engine.find_candidates(counter, tuning=seg_tuning)
    _mark_candidate_confidence(candidates, counter, settings, engine=engine, tuning=seg_tuning)

    if active_ids is not None:
        active = select_active(candidates, active_ids=active_ids)
        meta: dict[str, Any] = {"mode": "explicit"}
        suggested = None
    elif expected_rooms is not None:
        requested = int(expected_rooms)
        available = len(candidates) + 1  # max rooms = boundaries + 1
        capped_at = max(1, min(requested, available))
        active = select_active(candidates, expected_rooms=capped_at)
        meta = {
            "mode": "count",
            "requested": requested,
            "available": available,
            "capped": requested > available,
            "capped_at": capped_at,
        }
        if requested > available:
            # Stable reason code so the card can localize this (vocab.resegment_reason.*);
            # the English message is kept as a diagnostic / fallback for non-card consumers.
            meta["reason"] = "capped_to_detectable"
            meta["message"] = f"Only {available} room(s) detectable from this run."
        suggested = capped_at
    else:
        active = select_active(candidates, default="confident")
        meta = {"mode": "reset"}
        suggested = None

    segments = engine.build_segments(counter, active, tuning=seg_tuning)
    out_segments, _confident_count, active_boundary_ids = _enrich_segments(
        segments, candidates, counter, settings, rooms, baselines, map_id
    )
    if not out_segments:
        return None, meta

    new_record = dict(pending_record)
    new_record["schema_version"] = PENDING_SCHEMA_VERSION
    new_record["segment_count"] = len(out_segments)
    new_record["suggested_room_count"] = suggested if suggested is not None else len(out_segments)
    new_record["gap_transit_s"] = gap_transit_s
    new_record["candidates"] = candidates
    new_record["active_boundaries"] = active_boundary_ids
    new_record["segments"] = out_segments
    return new_record, meta


# --- Confirm: gate + graduate into a normal completed-job record -------------

# Tier-1 identity gate: a WIDE plausibility band (the user already picked the
# room; we only bounce a clear size mismatch). The tight W3 partial-exclusion is
# automatic later in the rebuilder, so it is not repeated here.
_IDENTITY_MIN_SAMPLES = 4
_IDENTITY_MIN_TOL_M2 = 3.0


def _vacuum_slug(vacuum_entity_id: str) -> str:
    return (
        vacuum_entity_id.split(".", 1)[1].strip().lower()
        if "." in str(vacuum_entity_id)
        else str(vacuum_entity_id).strip().lower()
    )


def gate_segment_identity(
    *, area_m2: float, band: dict[str, Any] | None, override: bool = False
) -> dict[str, Any]:
    """Tier-1 identity sanity for a confirmed segment area vs the room's learned
    band. Wide on purpose — only a clear mismatch is implausible. ``override``
    forces plausible (the user insisted); a cold room (no band) is accepted as a
    bootstrap sample."""
    if override:
        return {"plausible": True, "reason": "override"}
    band = band or {}
    avg = _safe_float(band.get("avg_area_m2"), 0.0)
    samples = _safe_int(band.get("area_sample_count"), 0)
    if samples < _IDENTITY_MIN_SAMPLES or avg <= 0:
        return {"plausible": True, "reason": "cold_start"}
    stddev = _safe_float(band.get("area_m2_stddev"), 0.0)
    tol = max(3.0 * stddev, 0.5 * avg, _IDENTITY_MIN_TOL_M2)
    if abs(_safe_float(area_m2) - avg) > tol:
        return {
            "plausible": False,
            "reason": "area_mismatch",
            "expected_m2": round(avg, 1),
            "observed_m2": round(_safe_float(area_m2), 1),
        }
    return {"plausible": True, "reason": "in_band"}


def build_graduated_job(
    *,
    pending_record: dict[str, Any],
    assignments: list[dict[str, Any]],
    rooms: dict[str, Any],
    bands_by_slug: dict[str, dict[str, Any]],
    vacuum_entity_id: str,
    job_id: str,
    ended_at: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Turn confirmed assignments into a normal ``completed_job`` record the stats
    rebuilder ingests, or ``(None, blocked)`` when any assignment fails the tier-1
    identity gate without override (atomic — graduate only when all pass).

    Each assignment maps one or more blind ``segment_orders`` (merged uncertain
    cuts) to a room: ``{segment_orders|segment_order, room_id, edge_mopping,
    override, overrides:{clean_mode,...}}``. ``rooms`` is the map's room config
    (id->{slug, name, floor_type, clean_*}); ``bands_by_slug`` the learned area
    band per slug. Settings come from the segment's recovered selects, then any
    explicit override, then the room config; passes from the segment estimate.
    """
    segs_by_order = {s.get("order"): s for s in pending_record.get("segments", [])}
    rooms = rooms or {}
    blocked: list[dict[str, Any]] = []
    room_timings: list[dict[str, Any]] = []
    profile_rooms: list[dict[str, Any]] = []
    total_wall_s = 0

    for assignment in assignments or []:
        orders = assignment.get("segment_orders")
        if orders is None and "segment_order" in assignment:
            orders = [assignment["segment_order"]]
        covered = [segs_by_order[o] for o in (orders or []) if o in segs_by_order]
        if not covered:
            continue
        room_id = _safe_int(assignment.get("room_id"), -1)
        room_cfg = rooms.get(str(room_id), {}) if isinstance(rooms.get(str(room_id)), dict) else {}
        slug = str(room_cfg.get("slug", "")).strip().lower()
        area = round(sum(_safe_float(s.get("area_m2")) for s in covered), 2)
        active_s = sum(_safe_int(s.get("time_active_s")) for s in covered)
        wall_s = sum(_safe_int(s.get("time_wall_s")) for s in covered)

        gate = gate_segment_identity(
            area_m2=area,
            band=bands_by_slug.get(slug),
            override=_safe_bool(assignment.get("override"), False),
        )
        if not gate.get("plausible"):
            blocked.append({"segment_orders": orders, "room_id": room_id, **gate})
            continue

        seg_settings = covered[0].get("settings", {}) or {}
        overrides = assignment.get("overrides", {}) or {}

        def _pick(key: str) -> Any:
            return overrides.get(key) or seg_settings.get(key) or room_cfg.get(key)

        passes = max(1, min(2, _safe_int(covered[0].get("pass_count"), 1)))
        room_timings.append(
            {
                "room_id": room_id,
                "slug": slug,
                "cleaning_start": covered[0].get("t_start"),
                "cleaning_end": covered[-1].get("t_end"),
                "cleaning_seconds": active_s,
                "cleaning_wall_seconds": wall_s,
                "area_m2": area,
            }
        )
        profile_rooms.append(
            {
                "room_id": room_id,
                "slug": slug,
                "name": room_cfg.get("name"),
                "clean_mode": _pick("clean_mode"),
                "clean_intensity": _pick("clean_intensity"),
                "fan_speed": _pick("fan_speed"),
                "water_level": _pick("water_level"),
                "clean_passes": _safe_int(overrides.get("clean_passes", passes), passes),
                "is_carpet": str(room_cfg.get("floor_type", "")).strip().lower().startswith("carpet"),
                "edge_mopping": _safe_bool(assignment.get("edge_mopping"), False),
            }
        )
        total_wall_s += wall_s

    if blocked:
        return None, blocked
    if not room_timings:
        return None, []

    map_id = _safe_int(pending_record.get("map_id"), 0)
    record = {
        "record_type": "completed_job",
        "schema_version": 1,
        "job_id": job_id,
        "origin": "external",
        "vacuum": {"entity_id": vacuum_entity_id, "name": _vacuum_slug(vacuum_entity_id)},
        "job": {
            "started_at": pending_record.get("detection_ts"),
            "ended_at": ended_at,
            "duration_minutes": round(total_wall_s / 60.0, 2),
            "room_count": len(profile_rooms),
            "room_timings": room_timings,
            "transitions": [],
            # The per-room area/timing capture IS valid (this gates the rebuilder's
            # use of room_timings); external runs just emit no transit edges.
            "transit_capture_valid": True,
        },
        "job_profile": {
            "map_id": map_id,
            "room_count": len(profile_rooms),
            "rooms": profile_rooms,
        },
        "resolved_rooms": profile_rooms,
        "outcome": {
            "status": "completed",
            "used_for_learning": True,
            "origin": "external",
            # A run only graduates after passing the tier-1 identity gate and with a
            # valid duration + room set, so it is sane by construction. Set explicitly
            # so the history view never reads a missing key as a sanity failure.
            "sanity_passed": True,
            "sanity_flags": [],
        },
        "finalized_at": ended_at,
    }
    return record, []


def load_pending_runs(external_jobs_dir: str) -> list[dict[str, Any]]:
    """Load pending external review records from ``external_jobs_dir``, newest
    first, each tagged with ``pending_job_id`` (the filename stem) for the confirm
    service. Returns [] when the directory is absent or empty (the card's data API)."""
    import json
    import os

    out: list[dict[str, Any]] = []
    try:
        names = sorted(os.listdir(external_jobs_dir), reverse=True)
    except OSError:
        return out
    for name in names:
        if not (name.startswith("job_") and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(external_jobs_dir, name), encoding="utf-8") as handle:
                rec = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict):
            rec = dict(rec)
            rec["pending_job_id"] = name[:-5]  # strip ".json"
            out.append(rec)
    return out
