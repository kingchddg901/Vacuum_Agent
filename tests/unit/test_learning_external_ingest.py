"""Unit tests for learning.external_ingest.build_pending_record — pure, HA-free.

Covers: no-signal -> None, the settings-flip-corroborated suggested count
(confident wash plateau / settings flip vs uncertain flat-settings step), the
area + settings-match shortlist ranking, the carpet drop on mopped segments, and
the pass-count estimate.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.eufy_vacuum.learning.external_ingest import build_pending_record

_BASE = datetime(2026, 6, 7, 3, 0, 0)


def _c(sec: int, ct: float, ca: float, batt: int = 100) -> dict:
    return {
        "t": (_BASE + timedelta(seconds=sec)).isoformat(),
        "cleaning_time": ct,
        "cleaning_area": ca,
        "battery": batt,
    }


def _ss(sec: int, settings: dict) -> dict:
    return {"t": (_BASE + timedelta(seconds=sec)).isoformat(), "settings": settings}


_ROOMS = {
    "1": {"slug": "kitchen", "name": "Kitchen", "floor_type": "hardwood", "clean_mode": "vacuum_mop"},
    "2": {"slug": "hall", "name": "Hall", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "3": {"slug": "den", "name": "Den", "floor_type": "carpet_low_pile", "clean_mode": "vacuum"},
}
_BASELINES = [
    {"map_id": "6", "room_slug": "kitchen", "avg_area_m2": 6.0},
    {"map_id": "6", "room_slug": "hall", "avg_area_m2": 2.0},
    {"map_id": "6", "room_slug": "den", "avg_area_m2": 8.0},
]


def _build(counter, settings):
    return build_pending_record(
        detection_ts=_BASE.isoformat(),
        map_id="6",
        counter_samples=counter,
        settings_samples=settings,
        rooms=_ROOMS,
        baselines=_BASELINES,
    )


def test_no_signal_returns_none():
    assert _build([], []) is None
    assert _build([_c(0, 0, 0)], []) is None  # reset only, never rises


def test_byroom_confident_count_area_ranked_carpet_dropped():
    counter = [
        _c(0, 0, 0),
        _c(60, 30, 1), _c(90, 60, 2), _c(120, 90, 3),
        _c(150, 120, 4), _c(180, 150, 5), _c(210, 180, 6),   # room A: area 0->6, mopped
        _c(540, 210, 6), _c(570, 240, 8),                     # room B after 330s wash: ->8
    ]
    settings = [
        _ss(60, {"clean_mode": "vacuum_mop", "fan_speed": "Turbo"}),
        _ss(540, {"clean_mode": "vacuum", "fan_speed": "Quiet"}),
    ]
    rec = _build(counter, settings)
    assert rec is not None
    assert rec["segment_count"] == 2
    assert rec["suggested_room_count"] == 2          # wash plateau = confident boundary
    assert rec["segments"][1]["confident_boundary"] is True
    # seg0 (area 6, mopped): kitchen wins on area + clean_mode; den (carpet) dropped.
    seg0_slugs = [s["slug"] for s in rec["segments"][0]["shortlist"]]
    assert seg0_slugs[0] == "kitchen"
    assert "den" not in seg0_slugs                   # carpet can't be mopped
    # seg1 (area 2, vacuum): hall wins; den allowed back (not mopped).
    assert rec["segments"][1]["shortlist"][0]["slug"] == "hall"
    seg1_slugs = [s["slug"] for s in rec["segments"][1]["shortlist"]]
    assert "den" in seg1_slugs


def test_settings_flip_makes_short_step_confident():
    counter = [
        _c(0, 0, 0),
        _c(60, 30, 1), _c(90, 60, 2), _c(120, 90, 3),   # room A
        _c(160, 120, 5),                                 # 40s step + area jump -> room B
        _c(190, 150, 6), _c(220, 180, 7),
    ]
    settings = [
        _ss(60, {"clean_mode": "vacuum"}),
        _ss(160, {"clean_mode": "mop"}),                 # flip at the boundary
    ]
    rec = _build(counter, settings)
    assert rec["segment_count"] == 2
    assert rec["segments"][1]["confident_boundary"] is True
    assert rec["suggested_room_count"] == 2


def test_short_step_without_flip_is_uncertain():
    counter = [
        _c(0, 0, 0),
        _c(60, 30, 1), _c(90, 60, 2), _c(120, 90, 3),
        _c(160, 120, 5),
        _c(190, 150, 6), _c(220, 180, 7),
    ]
    settings = [_ss(60, {"clean_mode": "vacuum"})]        # no flip
    rec = _build(counter, settings)
    assert rec["segment_count"] == 2                     # blind still splits
    assert rec["segments"][1]["confident_boundary"] is False
    assert rec["suggested_room_count"] == 1             # uncertain cut excluded from the count


def test_pass_count_estimated_for_multipass_room():
    # one room: area climbs 0->3 then plateaus (re-covering) — ~2 passes.
    counter = [
        _c(0, 0, 0),
        _c(30, 30, 1), _c(60, 60, 2), _c(90, 90, 3),
        _c(120, 120, 3), _c(150, 150, 3), _c(180, 180, 3),
    ]
    rec = _build(counter, [_ss(30, {"clean_mode": "vacuum"})])
    assert rec["segment_count"] == 1
    assert rec["segments"][0]["pass_count"] == 2
    assert rec["segments"][0]["settings"]["clean_mode"] == "vacuum"


def test_cold_rooms_have_no_area_but_are_still_listed():
    # no baselines -> every room is cold; still surfaced (unranked), nothing crashes.
    counter = [_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(90, 90, 3)]
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=counter, settings_samples=[_ss(30, {"clean_mode": "vacuum"})],
        rooms=_ROOMS, baselines=[],
    )
    assert rec["segment_count"] == 1
    slugs = {s["slug"] for s in rec["segments"][0]["shortlist"]}
    assert slugs  # populated from the room list even with no learned area
    assert all(s["learned_area_m2"] is None for s in rec["segments"][0]["shortlist"])
