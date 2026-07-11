"""Unit tests for mapping/room_bounds.py — the per-room bounding-box store.

This is the surviving core of the old mapping-inference lineage: it learns each
room's axis-aligned box from the samples a completed job attributes to it and
answers point-in-room queries. Exercised directly against a tmp config dir with
a minimal fake hass (the store only reads ``hass.config.config_dir``).

Coverage targets
----------------
[RB-1]  _percentile_trim: < min samples unchanged; else trims P10/P90 outliers.
[RB-2]  _point_in_bounds: margin-expanded inclusive AABB test.
[RB-3]  _recompute_bounds_from_history: union of non-excluded entries; all-excluded → None.
[RB-4]  single-room job: every sample attributed unconditionally.
[RB-5]  multi-room job: samples attributed by existing box; low-confidence room skipped;
        unattributed samples discarded.
[RB-6]  legacy accumulated bounds are folded into history on first new job.
[RB-7]  get_room_bounds_snapshot: available flag + per-room bounds/history shape.
[RB-8]  round-trips through the on-disk map JSON (persist + reload).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum.mapping.room_bounds import (
    BOUNDS_MARGIN,
    MULTI_ROOM_MIN_RUNS,
    RoomBoundsStore,
    _percentile_trim,
)

_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def store(tmp_path):
    """A RoomBoundsStore rooted at a throwaway config dir."""
    fake_hass = SimpleNamespace(config=SimpleNamespace(config_dir=str(tmp_path)))
    return RoomBoundsStore(fake_hass)


def _history_entry(min_x, max_x, min_y, max_y, *, excluded=False):
    return {
        "min_x": float(min_x), "max_x": float(max_x),
        "min_y": float(min_y), "max_y": float(max_y),
        "cx": (min_x + max_x) / 2.0, "cy": (min_y + max_y) / 2.0,
        "sample_count": 1, "recorded_at": "2026-01-01T00:00:00+00:00",
        "job_id": "seed", "excluded": excluded,
    }


# ---------------------------------------------------------------------------
# Pure helpers / static methods
# ---------------------------------------------------------------------------

def test_percentile_trim_below_min():
    """[RB-1] fewer than the minimum sample count → returned unchanged."""
    samples = [(float(i), float(i)) for i in range(5)]
    assert _percentile_trim(samples) == samples


def test_percentile_trim_drops_outliers():
    """[RB-1] 10 samples → the extreme low corner is trimmed off."""
    samples = [(float(i), float(i)) for i in range(10)]
    out = _percentile_trim(samples)
    assert (0.0, 0.0) not in out
    assert len(out) == 9


@pytest.mark.parametrize("pt,inside", [
    ((5.0, 5.0), True),      # squarely inside the raw box
    ((10.5, 5.0), True),     # outside the box but within the 1.0 margin
    ((12.0, 5.0), False),    # beyond the margin
])
def test_point_in_bounds_margin(pt, inside):
    """[RB-2]"""
    bounds = {"min_x": 0.0, "max_x": 10.0, "min_y": 0.0, "max_y": 10.0}
    assert RoomBoundsStore._point_in_bounds(pt[0], pt[1], bounds, margin=1.0) is inside


def test_recompute_unions_non_excluded():
    """[RB-3] the accumulated box is the union of the non-excluded history."""
    history = [
        _history_entry(0, 5, 0, 5),
        _history_entry(4, 12, 4, 9),
        _history_entry(-100, 100, -100, 100, excluded=True),  # ignored
    ]
    box = RoomBoundsStore._recompute_bounds_from_history(history)
    assert box["min_x"] == 0.0 and box["max_x"] == 12.0
    assert box["min_y"] == 0.0 and box["max_y"] == 9.0
    assert box["run_count"] == 2   # excluded entry not counted


def test_recompute_all_excluded_returns_none():
    """[RB-3] with every entry excluded there is no box."""
    history = [_history_entry(0, 5, 0, 5, excluded=True)]
    assert RoomBoundsStore._recompute_bounds_from_history(history) is None


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

def test_single_room_attributes_all_samples(store):
    """[RB-4] exactly one non-transition room → all samples belong to it."""
    store.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(2.0, 2.0), (8.0, 6.0), (5.0, 4.0)],
        rooms={"1": {}},
    )
    snap = store.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    box = snap["rooms"]["1"]["bounds"]
    assert box["min_x"] == 2.0 and box["max_x"] == 8.0
    assert box["min_y"] == 2.0 and box["max_y"] == 6.0
    assert len(snap["rooms"]["1"]["job_bounds_history"]) == 1


def test_transition_room_ignored_in_single_room_count(store):
    """[RB-4] a transition room does not count toward the single-room fast path."""
    store.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(3.0, 3.0), (7.0, 7.0)],
        rooms={"1": {}, "99": {"is_transition": True}},
    )
    snap = store.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    # Only room 1 is non-transition → single-room path → it gets all samples.
    assert snap["rooms"]["1"]["bounds"]["max_x"] == 7.0
    assert "99" not in snap["rooms"]


def test_multi_room_gating(store):
    """[RB-5] multi-room job: attributes by existing box, skips low-confidence
    rooms, and discards unattributed samples."""
    # Seed two rooms with existing boxes. Room 1 is a trusted anchor
    # (>= MULTI_ROOM_MIN_RUNS active runs); room 3 is low-confidence (2 runs).
    seeded = store._ensure_map_data(_VAC, _MAP)
    seeded["rooms"]["1"] = {
        "bounds": {"min_x": 0.0, "max_x": 10.0, "min_y": 0.0, "max_y": 10.0},
        "job_bounds_history": [_history_entry(0, 10, 0, 10) for _ in range(MULTI_ROOM_MIN_RUNS)],
    }
    seeded["rooms"]["3"] = {
        "bounds": {"min_x": 100.0, "max_x": 110.0, "min_y": 100.0, "max_y": 110.0},
        "job_bounds_history": [_history_entry(100, 110, 100, 110) for _ in range(2)],
    }
    store._save_map_data(_VAC, _MAP, seeded)

    store.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[
            (5.0, 5.0), (6.0, 5.0),      # inside room 1's box → attributed + written
            (105.0, 105.0),              # inside room 3's box → attributed but SKIPPED (low runs)
            (500.0, 500.0),              # inside nobody's box (+margin) → discarded
        ],
        rooms={"1": {}, "3": {}},
    )

    snap = store.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    # Room 1 got a 5th history entry (the new job appended).
    assert len(snap["rooms"]["1"]["job_bounds_history"]) == MULTI_ROOM_MIN_RUNS + 1
    # Room 3 stayed at its seeded 2 entries — low confidence, nothing written back.
    assert len(snap["rooms"]["3"]["job_bounds_history"]) == 2
    # No stray room was created for the discarded far-away sample.
    assert set(snap["rooms"]) == {"1", "3"}


def test_far_sample_outside_margin_is_discarded(store):
    """[RB-5] a sample beyond box+BOUNDS_MARGIN is not attributed."""
    # Sanity on the margin constant the discard relies on.
    assert BOUNDS_MARGIN == 50.0
    seeded = store._ensure_map_data(_VAC, _MAP)
    seeded["rooms"]["1"] = {
        "bounds": {"min_x": 0.0, "max_x": 10.0, "min_y": 0.0, "max_y": 10.0},
        "job_bounds_history": [_history_entry(0, 10, 0, 10) for _ in range(MULTI_ROOM_MIN_RUNS)],
    }
    seeded["rooms"]["2"] = {
        "bounds": {"min_x": 0.0, "max_x": 10.0, "min_y": 0.0, "max_y": 10.0},
        "job_bounds_history": [_history_entry(0, 10, 0, 10) for _ in range(MULTI_ROOM_MIN_RUNS)],
    }
    store._save_map_data(_VAC, _MAP, seeded)

    store.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(1000.0, 1000.0)],   # far outside both boxes + margin
        rooms={"1": {}, "2": {}},
    )
    snap = store.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    # Neither room grew — the sample was discarded.
    assert len(snap["rooms"]["1"]["job_bounds_history"]) == MULTI_ROOM_MIN_RUNS
    assert len(snap["rooms"]["2"]["job_bounds_history"]) == MULTI_ROOM_MIN_RUNS


def test_legacy_bounds_folded_into_history(store):
    """[RB-6] a room with accumulated bounds but no history migrates that box
    into a 'pre_migration' entry the first time a new job lands."""
    seeded = store._ensure_map_data(_VAC, _MAP)
    seeded["rooms"]["1"] = {
        "bounds": {"min_x": -5.0, "max_x": 5.0, "min_y": -5.0, "max_y": 5.0,
                   "sample_count": 3, "updated_at": "2025-12-31T00:00:00+00:00"},
        # no job_bounds_history
    }
    store._save_map_data(_VAC, _MAP, seeded)

    store.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(20.0, 20.0)],
        rooms={"1": {}},
    )
    snap = store.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    history = snap["rooms"]["1"]["job_bounds_history"]
    # New job entry + the migrated legacy box.
    assert any(e["job_id"] == "pre_migration" for e in history)
    # Union spans both the legacy (-5..5) and the new sample (20).
    box = snap["rooms"]["1"]["bounds"]
    assert box["min_x"] == -5.0 and box["max_x"] == 20.0


# ---------------------------------------------------------------------------
# Snapshot / persistence
# ---------------------------------------------------------------------------

def test_snapshot_available_and_shape(store):
    """[RB-7] snapshot reports available + the expected per-room shape."""
    store.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(1.0, 1.0)], rooms={"1": {}},
    )
    snap = store.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    assert snap["available"] is True
    assert snap["map_id"] == _MAP
    room = snap["rooms"]["1"]
    assert set(room) == {"bounds", "job_bounds_history"}


def test_bounds_round_trip_through_disk(store, tmp_path):
    """[RB-8] a second store on the same config dir reads back the persisted box."""
    store.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP,
        samples=[(2.0, 3.0), (8.0, 9.0)], rooms={"1": {}},
    )
    fake_hass = SimpleNamespace(config=SimpleNamespace(config_dir=str(tmp_path)))
    reopened = RoomBoundsStore(fake_hass)
    snap = reopened.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
    box = snap["rooms"]["1"]["bounds"]
    assert box["min_x"] == 2.0 and box["max_x"] == 8.0
    assert box["min_y"] == 3.0 and box["max_y"] == 9.0
