"""External-run ingestion — build a PENDING review record from a captured app run.

An app-started (external) job is captured into an ``active_jobs`` slot with
``status="external"`` (counters + setting selects buffered, no dispatched queue).
When it finishes, this module turns the raw capture into a *pending record* that
the review card resolves:

- **segment** the counters blind (no queue — ``segment_counters`` with
  ``expected_rooms=None``);
- **suggest a room count** corroborated by settings-flips: a boundary is
  *confident* when it is a long wash plateau OR the per-room setting selects
  changed across it, *uncertain* otherwise (a short area-rise with no flip — an
  edge->fill turn or a same-settings adjacent room);
- per segment, bake the recovered ``{area, time, passes, settings}`` plus an
  **area + settings** ranked, **map-scoped, carpet-filtered** shortlist.

Identity + edge-mop are filled by the user in review; nothing here touches the
learned baselines (that is the confirm service, a later wave). Pure given its
inputs — the caller loads room config + learned baselines and persists the
returned record atomically under ``external_jobs/``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..counter_segmentation import segment_counters
from ..timestamp_utils import parse_timestamp
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

PENDING_SCHEMA_VERSION = 1


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


def build_pending_record(
    *,
    detection_ts: str | None,
    map_id: Any,
    counter_samples: list[dict[str, Any]],
    settings_samples: list[dict[str, Any]],
    rooms: dict[str, Any],
    baselines: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Turn a captured external run into a pending review record, or None when
    there is no usable cleaning signal (so a false-start writes nothing)."""
    segments = segment_counters(counter_samples or [])  # blind: no queue
    if not segments:
        return None

    area_by_slug = _baseline_area_by_slug(baselines, map_id)
    out_segments: list[dict[str, Any]] = []
    confident_boundaries = 0
    prev_settings: dict[str, str] | None = None

    # Drop only TRAILING sub-room segments (the end-of-run station clean / re-pass).
    # A LEADING or middle ~0 m² segment is KEPT: cleaning_area lags, so a short first
    # room can read ~0 m² (its area lands on the next segment) yet is a real room.
    # Find the last real-area segment; drop only what comes after it.
    last_real = -1
    for _i, _s in enumerate(segments):
        if _safe_float(_s.get("area_delta_m2")) >= _MIN_ROOM_AREA_M2:
            last_real = _i

    for index, seg in enumerate(segments):
        if index > last_real:
            break  # trailing sub-room stretch — drop it and everything after
        order = len(out_segments)  # re-index over KEPT segments
        boundary = seg.get("boundary")
        settings = _segment_settings(settings_samples, seg.get("t_end"))
        passes = _estimate_passes(counter_samples, seg.get("t_start"), seg.get("t_end"))

        confident: bool | None = None
        if order > 0:
            if boundary == "wash_plateau":
                confident = True  # a minutes-long wash is an unambiguous boundary
            else:
                # short delayed step: a settings flip across it corroborates a
                # real boundary; flat settings => uncertain (edge->fill or a
                # same-settings adjacent room).
                confident = bool(settings) and settings != prev_settings
            if confident:
                confident_boundaries += 1

        out_segments.append(
            {
                "order": order,
                "t_start": seg.get("t_start"),
                "t_end": seg.get("t_end"),
                "area_m2": _safe_float(seg.get("area_delta_m2")),
                "time_wall_s": _safe_int(seg.get("time_wall_s"), 0),
                "time_active_s": _safe_int(seg.get("time_active_s"), 0),
                "pass_count": passes,
                "settings": settings,
                "boundary": boundary,
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
        prev_settings = settings

    if not out_segments:
        return None  # every stretch was sub-room area (no real cleaning signal)

    return {
        "schema_version": PENDING_SCHEMA_VERSION,
        "status": "pending",
        "origin": "external",
        "detection_ts": detection_ts,
        "map_id": str(map_id),
        "segment_count": len(out_segments),
        # Default count = confident boundaries only; uncertain cuts are shown as
        # toggleable "maybe split here" markers (default off) in the card.
        "suggested_room_count": 1 + confident_boundaries,
        "segments": out_segments,
    }


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
