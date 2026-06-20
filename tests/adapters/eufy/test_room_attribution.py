"""Real Eufy room-attribution classifier — adversarial regression (SOLO Eufy fixtures).

Pins the ported classifier (learning/room_attribution_engines.EufyAnchorWindingAttributor)
to the 3 deliberately-adversarial external runs captured on vacuum.alfred (the 9/9
validation; see docs/dev/eufy-native-transition.md). Each fixture is the per-room
EVIDENCE the analyzer produced (max over that room's runs) + the per-room swept area +
the ground-truth cleaned set from the finalized ext-job records.

Mirrors scratch-external-estimator/test_room_attribution.py, lifted into the integration
against the engine's parameterized _classify. The full attribute() pipeline (segment ->
run_metrics -> swept-area -> classify) is exercised on synthetic streams at the bottom;
real captured raw streams become full-pipeline fixtures once the W5b sampler records them
natively (with cleaning_area).
"""

from __future__ import annotations

from custom_components.eufy_vacuum.learning.room_attribution_engines import (
    DWELL_MIN_S,
    SWEPT_AREA_MIN_M2,
    WIND_TRANSIT,
    EufyAnchorWindingAttributor,
    _classify,
)

# room_id -> (spread, dwell_s, winding, swept_m2)
RUNS = {
    "ext#1 (hallway/bath/entry)": {
        "truth": {2, 4, 6},
        "rooms": {
            4: (0.0688, 118, 126.48, 6.0),   # Hallway  CLEANED
            2: (0.0544, 110, 31.25, 2.0),    # Bathroom CLEANED
            6: (0.0264, 46, 5.22, 1.0),      # Entryway CLEANED (tiny floor)
            8: (0.0282, 271, 43.47, 0.0),    # Dining (DOCK) — PARKED, not cleaned  <- the trap
            7: (0.0700, 18, 1.21, 0.0),      # transit hub
            9: (0.0297, 8, 1.00, 0.0),       # transit
        },
    },
    "dock-first (dining first)": {
        "truth": {2, 6, 8},
        "rooms": {
            8: (0.0728, 657, 39.84, 12.0),   # Dining (DOCK) — CLEANED first
            2: (0.0451, 92, 117.29, 2.0),    # Bathroom CLEANED
            6: (0.0270, 38, 13.60, 1.0),     # Entryway CLEANED (tiny)
            7: (0.0657, 16, 1.18, 0.0),      # transit
            9: (0.0323, 8, 1.00, 0.0),       # transit
            4: (0.0461, 8, 1.00, 0.0),       # Hallway — transit this run
        },
    },
    "vicious (interleaved mop-wash)": {
        "truth": {4, 5, 8},
        "rooms": {
            8: (0.0714, 789, 38.17, 12.0),   # Dining (DOCK) — CLEANED, + folded mid-run wash
            4: (0.0730, 86, 4.93, 2.0),      # Hallway CLEANED
            5: (0.0518, 106, 30.08, 2.0),    # Kitchen CLEANED
            7: (0.0751, 18, 1.22, 0.0),      # transit
            1: (0.0000, 2, 0.00, 0.0),       # 1-tick flicker
        },
    },
}


def _classify_set(rooms, *, use_area):
    per_room = {rid: {"dwell_s": d, "spread": s, "winding": w, "bbox_area": 0.0}
                for rid, (s, d, w, _a) in rooms.items()}
    areas = {rid: a for rid, (_s, _d, _w, a) in rooms.items()} if use_area else None
    return _classify(
        per_room, areas,
        wind_transit=WIND_TRANSIT, dwell_min_s=DWELL_MIN_S, swept_area_min_m2=SWEPT_AREA_MIN_M2,
    )["cleaned"]


def test_area_augmented_recovers_all_3_runs_exactly():
    """The robust (swept-area) rule = ground truth on all 3 adversarial runs: 9/9, 0 FP."""
    for name, fx in RUNS.items():
        assert _classify_set(fx["rooms"], use_area=True) == fx["truth"], name


def test_anchor_only_has_full_recall_but_one_false_positive():
    """Anchor-only (dwell+winding) recovers every cleaned room but leaks the parked dock
    (ext#1 room 8) — the documented reason swept-area is REQUIRED, not optional."""
    fp = 0
    for name, fx in RUNS.items():
        pred = _classify_set(fx["rooms"], use_area=False)
        assert fx["truth"] <= pred, f"{name}: missed {sorted(fx['truth'] - pred)}"
        fp += len(pred - fx["truth"])
    assert fp == 1


def test_swept_area_separates_the_parked_dock():
    """ext#1 room 8 (parked dock) is metrically inside the cleaned cluster on anchors —
    only swept-area excludes it."""
    ext1 = RUNS["ext#1 (hallway/bath/entry)"]["rooms"]
    assert 8 in _classify_set(ext1, use_area=False)   # anchor-only false-positive
    assert 8 not in _classify_set(ext1, use_area=True)  # area excludes it


# --- full attribute() pipeline over synthetic streams ----------------------


def _clean_run(rid, n, area0, step):
    pts = [(0.0, 0.0), (0.1, 0.1)]   # zigzag -> high winding (covered)
    return [{"current_room": rid, "anchor": list(pts[i % 2]), "cleaning_area": area0 + i * step}
            for i in range(n)]


def _transit_run(rid, n, area):
    return [{"current_room": rid, "anchor": [0.05 * i, 0.5], "cleaning_area": area}  # straight line
            for i in range(n)]


def _park_run(rid, n, area):
    pts = [(0.5, 0.5), (0.51, 0.51)]   # jitter in a tiny area, cleaning_area FLAT
    return [{"current_room": rid, "anchor": list(pts[i % 2]), "cleaning_area": area} for i in range(n)]


def test_attribute_full_pipeline_robust_excludes_parked_dock():
    """Full segment -> run_metrics -> swept-area -> classify: a cleaned room is kept, a
    straight transit is dropped, and a jittering parked dock (flat area) is excluded."""
    engine = EufyAnchorWindingAttributor()
    stream = (
        _clean_run(5, n=12, area0=0.0, step=0.2)   # 5 cleaned: covered, area 0 -> 2.2
        + _transit_run(7, n=4, area=2.2)           # 7 transit: straight, area flat
        + _park_run(8, n=30, area=2.2)             # 8 parked dock: jitter, area flat
    )
    result = engine.attribute(stream)
    assert result["mode"] == "robust"
    assert result["cleaned"] == {5}
    assert result["verdicts"][8][0] == "parked/dock"
    assert result["verdicts"][7][0] == "transit"


def test_attribute_anchor_only_false_positives_the_dock():
    """Same parked-dock run with NO cleaning_area -> anchor-only -> wrongly 'cleaned'
    (60s dwell > 25s, high winding). Documents the limitation the area signal closes."""
    engine = EufyAnchorWindingAttributor()
    park = [{"current_room": 8, "anchor": list(((0.5, 0.5), (0.51, 0.51))[i % 2])} for i in range(30)]
    result = engine.attribute(park)
    assert result["mode"] == "anchor_only"
    assert 8 in result["cleaned"]
