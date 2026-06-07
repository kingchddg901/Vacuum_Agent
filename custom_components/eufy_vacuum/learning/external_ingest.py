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
from .utils import _safe_float, _safe_int

# Settings-match nudge (m²-equivalent) so a matching clean_mode breaks ties
# between similar-area rooms without overriding a clear area mismatch.
_SETTINGS_MATCH_BONUS = 1.5
_SHORTLIST_SIZE = 3
_COLD_ROOM_SCORE = -999.0   # no learned area yet → ranks last, still selectable
_MOP_MODES = {"mop", "vacuum_mop"}

PENDING_SCHEMA_VERSION = 1


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return parse_timestamp(value)


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


def _rank_shortlist(
    *,
    seg_area: float,
    seg_clean_mode: str | None,
    rooms: dict[str, Any],
    area_by_slug: dict[str, float],
) -> list[dict[str, Any]]:
    """Top-N rooms for a segment: area-match (learned size) + settings-match
    (clean_mode), map already scoped by the caller, carpet dropped when mopped."""
    mode = str(seg_clean_mode or "").strip().lower()
    mopped = mode in _MOP_MODES
    scored: list[tuple[float, dict[str, Any]]] = []
    for rid, room in (rooms or {}).items():
        if not isinstance(room, dict):
            continue
        slug = str(room.get("slug", "")).strip().lower()
        is_carpet = str(room.get("floor_type", "")).strip().lower().startswith("carpet")
        if mopped and is_carpet:
            continue  # a mopped segment cannot be a carpet room (override = all-rooms)
        learned_area = area_by_slug.get(slug)
        score = -abs(_safe_float(seg_area) - learned_area) if learned_area else _COLD_ROOM_SCORE
        if mode and str(room.get("clean_mode", "")).strip().lower() == mode:
            score += _SETTINGS_MATCH_BONUS
        scored.append(
            (
                score,
                {
                    "room_id": _safe_int(rid, -1),
                    "slug": slug,
                    "name": room.get("name"),
                    "is_carpet": is_carpet,
                    "learned_area_m2": learned_area,
                    "score": round(score, 2),
                },
            )
        )
    scored.sort(key=lambda s: s[0], reverse=True)
    return [entry for _score, entry in scored[:_SHORTLIST_SIZE]]


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

    for seg in segments:
        order = _safe_int(seg.get("index"), 0)
        boundary = seg.get("boundary")
        settings = _segment_settings(settings_samples, seg.get("t_end"))
        clean_mode = settings.get("clean_mode")

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
                "pass_count": _estimate_passes(
                    counter_samples, seg.get("t_start"), seg.get("t_end")
                ),
                "settings": settings,
                "boundary": boundary,
                "confident_boundary": confident,
                "shortlist": _rank_shortlist(
                    seg_area=_safe_float(seg.get("area_delta_m2")),
                    seg_clean_mode=clean_mode,
                    rooms=rooms,
                    area_by_slug=area_by_slug,
                ),
            }
        )
        prev_settings = settings

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
