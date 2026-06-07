"""Unit tests for learning.external_ingest.build_pending_record — pure, HA-free.

Covers: no-signal -> None, the settings-flip-corroborated suggested count
(confident wash plateau / settings flip vs uncertain flat-settings step), the
area + settings-match shortlist ranking, the carpet drop on mopped segments, and
the pass-count estimate.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from custom_components.eufy_vacuum.learning.external_ingest import (
    build_graduated_job,
    build_pending_record,
    gate_segment_identity,
)

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


# ---------------------------------------------------------------------------
# W6.3 — tier-1 identity gate + graduate into a completed_job record
# ---------------------------------------------------------------------------

def _pending_two_rooms():
    counter = [
        _c(0, 0, 0),
        _c(60, 30, 1), _c(90, 60, 2), _c(120, 90, 3),
        _c(150, 120, 4), _c(180, 150, 5), _c(210, 180, 6),   # room A: area 6, mopped
        _c(540, 210, 6), _c(570, 240, 8),                     # room B after wash: area 2
    ]
    settings = [
        _ss(60, {"clean_mode": "vacuum_mop"}),
        _ss(540, {"clean_mode": "vacuum"}),
    ]
    return _build(counter, settings)


def test_gate_cold_start_and_no_band_are_plausible():
    assert gate_segment_identity(area_m2=5.0, band=None)["reason"] == "cold_start"
    assert gate_segment_identity(
        area_m2=5.0, band={"area_sample_count": 1, "avg_area_m2": 6.0}
    )["plausible"] is True


def test_gate_in_band_plausible_far_blocked():
    band = {"area_sample_count": 6, "avg_area_m2": 6.0, "area_m2_stddev": 0.5}
    assert gate_segment_identity(area_m2=6.3, band=band)["plausible"] is True
    far = gate_segment_identity(area_m2=15.0, band=band)
    assert far["plausible"] is False
    assert far["reason"] == "area_mismatch"


def test_gate_override_forces_plausible():
    band = {"area_sample_count": 6, "avg_area_m2": 6.0, "area_m2_stddev": 0.5}
    res = gate_segment_identity(area_m2=15.0, band=band, override=True)
    assert res["plausible"] is True and res["reason"] == "override"


def test_build_graduated_job_produces_completed_record():
    rec, blocked = build_graduated_job(
        pending_record=_pending_two_rooms(),
        assignments=[
            {"segment_order": 0, "room_id": 1, "edge_mopping": True},
            {"segment_order": 1, "room_id": 2, "edge_mopping": False},
        ],
        rooms=_ROOMS, bands_by_slug={},
        vacuum_entity_id="vacuum.alfred", job_id="ext-1",
        ended_at="2026-06-07T04:00:00",
    )
    assert blocked == []
    assert rec["record_type"] == "completed_job"
    assert rec["origin"] == "external"
    assert rec["outcome"] == {"status": "completed", "used_for_learning": True, "origin": "external"}
    assert rec["job"]["transit_capture_valid"] is True
    assert rec["job"]["room_timings"][0]["area_m2"] == 6.0
    assert rec["job_profile"]["rooms"][0]["slug"] == "kitchen"
    assert rec["job_profile"]["rooms"][0]["edge_mopping"] is True


def test_build_graduated_job_blocks_then_overrides_area_mismatch():
    den_band = {"den": {"area_sample_count": 6, "avg_area_m2": 1.0, "area_m2_stddev": 0.2}}
    # seg0 area 6 assigned to den (learned ~1) -> blocked.
    rec, blocked = build_graduated_job(
        pending_record=_pending_two_rooms(),
        assignments=[{"segment_order": 0, "room_id": 3, "edge_mopping": False}],
        rooms=_ROOMS, bands_by_slug=den_band,
        vacuum_entity_id="vacuum.alfred", job_id="ext-2", ended_at="x",
    )
    assert rec is None
    assert blocked and blocked[0]["reason"] == "area_mismatch" and blocked[0]["room_id"] == 3
    # the user overrides -> graduates anyway.
    rec2, blocked2 = build_graduated_job(
        pending_record=_pending_two_rooms(),
        assignments=[{"segment_order": 0, "room_id": 3, "edge_mopping": False, "override": True}],
        rooms=_ROOMS, bands_by_slug=den_band,
        vacuum_entity_id="vacuum.alfred", job_id="ext-2b", ended_at="x",
    )
    assert blocked2 == [] and rec2 is not None
    assert rec2["job_profile"]["rooms"][0]["slug"] == "den"


def test_build_graduated_job_merges_segment_orders():
    rec, blocked = build_graduated_job(
        pending_record=_pending_two_rooms(),
        assignments=[{"segment_orders": [0, 1], "room_id": 1, "edge_mopping": False}],
        rooms=_ROOMS, bands_by_slug={},
        vacuum_entity_id="vacuum.alfred", job_id="ext-3", ended_at="x",
    )
    assert blocked == []
    assert len(rec["job"]["room_timings"]) == 1
    assert rec["job"]["room_timings"][0]["area_m2"] == 8.0   # 6 + 2 merged


def test_graduated_record_ingests_into_room_stats(tmp_path):
    """End-to-end contract check: a graduated external record feeds the real
    stats rebuilder and produces per-room area in room_stats."""
    from custom_components.eufy_vacuum.learning.stats_rebuilder import LearningStatsRebuilder

    rec, blocked = build_graduated_job(
        pending_record=_pending_two_rooms(),
        assignments=[
            {"segment_order": 0, "room_id": 1, "edge_mopping": False},
            {"segment_order": 1, "room_id": 2, "edge_mopping": False},
        ],
        rooms=_ROOMS, bands_by_slug={},
        vacuum_entity_id="vacuum.alfred", job_id="ext-5",
        ended_at="2026-06-07T04:00:00",
    )
    assert rec is not None and blocked == []
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    payload = LearningStatsRebuilder(hass).build_room_stats_payload(
        vacuum_entity_id="vacuum.alfred", jobs=[rec],
    )
    by_slug = {r.get("room_slug"): r for r in payload.get("room_stats", [])}
    assert "kitchen" in by_slug and "hall" in by_slug
    assert by_slug["kitchen"]["avg_area_m2"] == 6.0
    assert by_slug["hall"]["avg_area_m2"] == 2.0
