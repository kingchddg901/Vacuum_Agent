"""Unit tests for learning/room_attribution_engines.py — the room-attribution seam.

[RA-1]  get_room_attribution_engine resolves a registered engine by name.
[RA-2]  absent name (None/"") -> Eufy fallback (legacy default).
[RA-3]  unknown name -> Eufy fallback (NOT noop).
[RA-4]  known_room_attribution_names includes the registered engines.
[RA-5]  noop engine resolves and attribute() returns an empty result.
[RA-6]  DEFAULT_TUNING references the module thresholds (no drift).
[RA-7]  validate_tuning: non-dict / unknown key / bad value / valid.
[RA-8]  partial tuning merges over DEFAULT_TUNING (unspecified keys keep defaults).
[RA-9]  attribute(): empty -> empty; mode = robust iff cleaning_area present, else anchor_only.
[RA-10] noop validate_tuning rejects tuning keys.

The real classifier behaviour (the 3 adversarial validation runs) lives SOLO in
tests/adapters/eufy/test_room_attribution.py — this file is the brand-agnostic seam.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.learning.room_attribution_engines import (
    DWELL_MIN_TICKS,
    SWEPT_AREA_MIN_M2,
    WIND_TRANSIT,
    EufyAnchorWindingAttributor,
    NoopRoomAttributor,
    get_room_attribution_engine,
    known_room_attribution_names,
)


def _clean_run(rid, n=12, area0=0.0, step=0.2):
    """A covered (zigzag → high winding) run over a rising cleaning_area."""
    pts = [(0.0, 0.0), (0.1, 0.1)]
    return [
        {"current_room": rid, "anchor": list(pts[i % 2]), "cleaning_area": area0 + i * step}
        for i in range(n)
    ]


# --- registry ---------------------------------------------------------------


def test_resolves_registered_engine():
    """[RA-1]"""
    engine = get_room_attribution_engine("eufy_anchor_winding_v1")
    assert isinstance(engine, EufyAnchorWindingAttributor)
    assert engine.engine_name == "eufy_anchor_winding_v1"


def test_absent_name_falls_back_to_eufy():
    """[RA-2]"""
    assert isinstance(get_room_attribution_engine(None), EufyAnchorWindingAttributor)
    assert isinstance(get_room_attribution_engine(""), EufyAnchorWindingAttributor)


def test_unknown_name_falls_back_to_eufy():
    """[RA-3] falls back to Eufy, NOT noop."""
    assert isinstance(get_room_attribution_engine("totally_made_up"), EufyAnchorWindingAttributor)


def test_known_names():
    """[RA-4]"""
    known = known_room_attribution_names()
    assert "eufy_anchor_winding_v1" in known
    assert "noop_room_attribution" in known


def test_noop_returns_empty():
    """[RA-5]"""
    engine = get_room_attribution_engine("noop_room_attribution")
    assert isinstance(engine, NoopRoomAttributor)
    result = engine.attribute(_clean_run(5))
    assert result["cleaned"] == set()
    assert result["verdicts"] == {}


# --- tuning -----------------------------------------------------------------


def test_default_tuning_by_reference():
    """[RA-6] DEFAULT_TUNING references the module constants (single source)."""
    dt = EufyAnchorWindingAttributor.DEFAULT_TUNING
    assert dt["wind_transit"] == WIND_TRANSIT
    assert dt["dwell_min_ticks"] == DWELL_MIN_TICKS
    assert dt["swept_area_min_m2"] == SWEPT_AREA_MIN_M2


def test_validate_tuning():
    """[RA-7]"""
    engine = EufyAnchorWindingAttributor()
    assert engine.validate_tuning("nope") == ["room_attribution.tuning must be a dict"]
    assert any("unknown tuning key" in m and "bogus" in m for m in engine.validate_tuning({"bogus": 1}))
    assert engine.validate_tuning({"wind_transit": -1})
    assert engine.validate_tuning({"wind_transit": "x"})
    assert engine.validate_tuning({"dwell_min_ticks": True})  # bool is not a valid number
    assert engine.validate_tuning({}) == []
    assert engine.validate_tuning({"wind_transit": 1.8, "swept_area_min_m2": 0.3}) == []


def test_partial_tuning_merges_over_defaults():
    """[RA-8] override ONE key; the rest keep defaults.

    A covered room with ~2.2 m² swept is CLEANED under the default
    swept_area_min_m2=0.5; raise ONLY that key above 2.2 and it flips to parked —
    proving the partial dict merged over the defaults (wind_transit etc. unchanged)."""
    engine = EufyAnchorWindingAttributor()
    run = _clean_run(5, n=12, step=0.2)  # 11 steps * 0.2 = 2.2 m² swept
    assert 5 in engine.attribute(run)["cleaned"]
    assert 5 not in engine.attribute(run, tuning={"swept_area_min_m2": 5.0})["cleaned"]


def test_empty_and_mode_selection():
    """[RA-9] empty -> empty; mode = robust iff any cleaning_area present."""
    engine = EufyAnchorWindingAttributor()
    empty = engine.attribute([])
    assert empty["cleaned"] == set()
    assert empty["mode"] == "anchor_only"

    with_area = engine.attribute(_clean_run(5, n=6, step=0.3))
    assert with_area["mode"] == "robust"

    no_area = [{"current_room": 5, "anchor": [0.0, 0.0]}, {"current_room": 5, "anchor": [0.1, 0.1]}]
    assert engine.attribute(no_area)["mode"] == "anchor_only"


def test_noop_validate_tuning_rejects_keys():
    """[RA-10]"""
    assert NoopRoomAttributor().validate_tuning({}) == []
    assert NoopRoomAttributor().validate_tuning({"wind_transit": 1.5})
