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


def test_shortlist_settings_match_beats_area_match():
    # Segment area 2 m² matches HALL's learned size (2.0), but the captured mode is
    # vacuum_mop, which matches KITCHEN's config (hall is vacuum). cleaning_area is
    # path/pass-cumulative and unreliable for identity, so the settings-match must
    # win the shortlist over the closer area. (This is the kitchen/bathroom case
    # from live: an odd path/extra pass moved the area onto the wrong room.)
    counter = [_c(0, 0, 0), _c(30, 30, 0.7), _c(60, 60, 1.4), _c(90, 90, 2.0)]
    settings = [_ss(30, {"clean_mode": "vacuum_mop", "fan_speed": "Max"})]
    rec = _build(counter, settings)
    assert rec is not None
    slugs = [s["slug"] for s in rec["segments"][0]["shortlist"]]
    assert slugs[0] == "kitchen"  # mode-match wins, not the area-match hall
    assert "hall" in slugs and slugs.index("kitchen") < slugs.index("hall")


def test_zero_area_segment_dropped():
    # An end-of-run station clean (mop wash / dust empty) ticks cleaning_time with
    # NO new area — a 0 m² "Returning to Wash" stretch. It must not surface as a room.
    counter = [
        _c(0, 0, 0),
        _c(60, 30, 1), _c(90, 60, 2), _c(120, 90, 3), _c(150, 120, 4),   # room A -> 4 m²
        _c(540, 150, 4), _c(570, 180, 4), _c(600, 210, 4),               # wash + re-pass: 0 new area
    ]
    settings = [_ss(60, {"clean_mode": "vacuum_mop"})]
    rec = _build(counter, settings)
    assert rec is not None
    assert all(s["area_m2"] >= 0.5 for s in rec["segments"])   # no ~0 m² artifact survives
    assert any(s["area_m2"] >= 3.5 for s in rec["segments"])   # the real room is kept


def test_leading_zero_area_room_kept_when_area_lags():
    # cleaning_area lags: a short first room can read ~0 m² (its area lands on the
    # NEXT segment). A LEADING 0 m² segment must be KEPT (a real room), unlike a
    # trailing station clean. (This is the kitchen-dropped regression from live.)
    counter = [
        _c(0, 0, 0),
        _c(60, 30, 0), _c(90, 60, 0), _c(120, 90, 0),        # room A: ticks, area 0 (lag)
        _c(540, 120, 0),                                      # 420s wash plateau, area still 0
        _c(570, 150, 3), _c(600, 180, 6), _c(630, 210, 8),    # room B: area 0->8 (incl A's)
    ]
    settings = [_ss(60, {"clean_mode": "vacuum"}), _ss(570, {"clean_mode": "vacuum_mop"})]
    rec = _build(counter, settings)
    assert rec is not None
    assert rec["segment_count"] == 2              # leading 0 m² room kept, plus room B
    assert rec["segments"][0]["area_m2"] < 0.5    # room A read ~0 (the lag)
    assert rec["segments"][1]["area_m2"] >= 7.0   # room B carries the area


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


def test_utc_samples_naive_segment_no_cross_contamination(monkeypatch):
    """Regression (live, W6): segment t_start/t_end are naive UTC (segment_counters
    strips the "Z"), while captured samples keep "...Z". If naive is parsed as LOCAL,
    a non-final segment's window shifts past every sample, so it inherits the LAST
    segment's settings AND _estimate_passes can't see its own samples (defaults to 1
    pass). Force a non-UTC server tz so the bug bites unless naive is parsed as UTC."""
    from datetime import timezone

    import custom_components.eufy_vacuum.timestamp_utils as tsu

    monkeypatch.setattr(tsu, "_LOCAL_TZ", timezone(timedelta(hours=-4)))

    def _cz(sec, ct, ca):
        return {
            "t": (_BASE + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cleaning_time": ct, "cleaning_area": ca, "battery": 100,
        }

    def _ssz(sec, settings):
        return {"t": (_BASE + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ"), "settings": settings}

    counter = [
        _cz(0, 0, 0),
        _cz(60, 30, 1), _cz(90, 60, 2), _cz(120, 90, 3),         # room A: vacuum / Quick / High
        _cz(540, 120, 4), _cz(570, 150, 6), _cz(600, 180, 8),    # room B pass 1: area -> 8
        _cz(630, 210, 8), _cz(660, 240, 8),                      # room B pass 2: area flat
    ]
    settings = [
        _ssz(60, {"clean_mode": "vacuum", "clean_intensity": "Quick", "water_level": "High"}),
        _ssz(540, {"clean_mode": "vacuum_mop", "clean_intensity": "Narrow", "water_level": "Medium"}),
    ]
    rec = _build(counter, settings)
    assert rec is not None and rec["segment_count"] == 2
    # seg0 keeps ITS captured settings — the bug pasted room B's (Narrow/Medium) here.
    assert rec["segments"][0]["settings"]["clean_intensity"] == "Quick"
    assert rec["segments"][0]["settings"]["water_level"] == "High"
    assert rec["segments"][1]["settings"]["clean_intensity"] == "Narrow"
    # passes detected per-segment — the shifted window defaulted both to 1.
    assert rec["segments"][1]["pass_count"] == 2


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


def test_load_pending_runs_newest_first_and_tagged(tmp_path):
    import json

    from custom_components.eufy_vacuum.learning.external_ingest import load_pending_runs

    d = tmp_path / "external_jobs"
    d.mkdir()
    (d / "job_2026-06-07T03-00-00.json").write_text(
        json.dumps({"map_id": "6", "segment_count": 1}), encoding="utf-8"
    )
    (d / "job_2026-06-07T05-00-00.json").write_text(
        json.dumps({"map_id": "6", "segment_count": 2}), encoding="utf-8"
    )
    (d / "notes.txt").write_text("ignored", encoding="utf-8")  # non-job files skipped
    runs = load_pending_runs(str(d))
    assert [r["pending_job_id"] for r in runs] == [
        "job_2026-06-07T05-00-00",
        "job_2026-06-07T03-00-00",
    ]
    assert runs[0]["segment_count"] == 2


def test_load_pending_runs_missing_dir_is_empty():
    from custom_components.eufy_vacuum.learning.external_ingest import load_pending_runs

    assert load_pending_runs("/no/such/external_jobs") == []
