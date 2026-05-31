"""Integration tests for mapping/manager.py — the MappingManager class.

MappingManager is file-backed under hass.config.config_dir, so it needs only
the phac `hass` fixture (which provides an isolated config dir). No core
manager or service registry required.

Coverage targets
----------------
[MGR-1]  update_room_bounds (single-room) records bounds in the snapshot.
[MGR-2]  update_room_bounds with empty samples is a no-op.
[MGR-3]  clear_room_bounds resets a room; unknown room → room_not_found.
[MGR-4]  exclude/restore room job bounds recompute bounds; baseline protected.
[MGR-5]  trace capture lifecycle: start → status → append → stop → list → get → delete.
[MGR-6]  cancel_trace_capture discards the active session.
[MGR-7]  get_trace_run / delete_trace_run_by_id report not-found.
[MGR-8]  review_trace_run_for_room: missing run → error run_not_found.
[MGR-9]  review_trace_run_for_room: run present but no polygon → no_polygon verdict.
[MGR-10] segment_trace_run_for_room: missing run → error; present → segments.
[MGR-11] boundary trace lifecycle: start → append → close stores boundary.
[MGR-12] close_room_boundary with no samples → no_trace_samples.
[MGR-13] cancel_room_boundary_trace reports discarded points.
[MGR-14] append_trace_point with no active trace → False.
[MGR-15] set_dock_anchor requires the vacuum docked.
[MGR-16] set_dock_room persists the dock room id.
[MGR-17] append_mapping_trace_evidence grows the package trace list.
[MGR-18] get_mapping_state returns the room roster + package.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.mapping.manager import MappingManager


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def mapping_manager(hass) -> MappingManager:
    return MappingManager(hass)


def _square_trail(size: int = 100, step: int = 10) -> list[tuple[float, float]]:
    """A closed square perimeter walk — enough points for a valid boundary."""
    pts: list[tuple[float, float]] = []
    pts += [(float(x), 0.0) for x in range(0, size + 1, step)]
    pts += [(float(size), float(y)) for y in range(step, size + 1, step)]
    pts += [(float(x), float(size)) for x in range(size - step, -1, -step)]
    pts += [(0.0, float(y)) for y in range(size - step, 0, -step)]
    return pts


# ---------------------------------------------------------------------------
# Room bounds
# ---------------------------------------------------------------------------

def test_update_room_bounds_single_room(mapping_manager):
    """[MGR-1] dedicated map id — the shared config_dir means other test files
    also write room 3 / map 6 bounds, which would widen this exact-bounds union."""
    mapping_manager.update_room_bounds(
        vacuum_entity_id=_VAC, map_id="mgr1bounds",
        samples=[(0.0, 0.0), (10.0, 10.0), (5.0, 5.0)],
        rooms={"3": {"is_transition": False}},
    )
    snap = mapping_manager.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id="mgr1bounds")
    assert snap["available"] is True
    bounds = snap["rooms"]["3"]["bounds"]
    assert bounds["min_x"] == 0.0 and bounds["max_x"] == 10.0


def test_update_room_bounds_empty_noop(mapping_manager):
    """[MGR-2]"""
    mapping_manager.update_room_bounds(
        vacuum_entity_id=_VAC, map_id="empty", samples=[],
        rooms={"3": {"is_transition": False}},
    )
    snap = mapping_manager.get_room_bounds_snapshot(vacuum_entity_id=_VAC, map_id="empty")
    assert snap["rooms"] == {}


def test_clear_room_bounds(mapping_manager):
    """[MGR-3]"""
    mapping_manager.update_room_bounds(
        vacuum_entity_id=_VAC, map_id=_MAP, samples=[(0.0, 0.0), (4.0, 4.0)],
        rooms={"3": {"is_transition": False}},
    )
    ok = mapping_manager.clear_room_bounds(vacuum_entity_id=_VAC, map_id=_MAP, room_id="3")
    assert ok["success"] is True
    missing = mapping_manager.clear_room_bounds(vacuum_entity_id=_VAC, map_id=_MAP, room_id="99")
    assert missing["success"] is False
    assert missing["reason"] == "room_not_found"


def test_exclude_restore_job_bounds(mapping_manager):
    """[MGR-4] two job entries → exclude the newest (index 0, not baseline)."""
    for _ in range(2):
        mapping_manager.update_room_bounds(
            vacuum_entity_id=_VAC, map_id="excl", samples=[(0.0, 0.0), (8.0, 8.0)],
            rooms={"3": {"is_transition": False}},
        )
    excluded = mapping_manager.exclude_room_job_bounds(
        vacuum_entity_id=_VAC, map_id="excl", room_id="3", job_index=0)
    assert excluded["success"] is True and excluded["excluded"] is True
    restored = mapping_manager.restore_room_job_bounds(
        vacuum_entity_id=_VAC, map_id="excl", room_id="3", job_index=0)
    assert restored["success"] is True and restored["excluded"] is False
    # the single (baseline) entry is protected
    base = mapping_manager.exclude_room_job_bounds(
        vacuum_entity_id=_VAC, map_id="excl", room_id="3", job_index=1)
    assert base["reason"] == "baseline_protected"


# ---------------------------------------------------------------------------
# Trace capture lifecycle
# ---------------------------------------------------------------------------

def test_trace_capture_lifecycle(mapping_manager):
    """[MGR-5]"""
    start = mapping_manager.start_trace_capture(vacuum_entity_id=_VAC, map_id=_MAP, room_id="3")
    run_id = start["run_id"]
    status = mapping_manager.get_trace_capture_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert status["active"] is True

    assert mapping_manager.append_trace_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=1.0, y=1.0) is True
    stop = mapping_manager.stop_trace_capture(vacuum_entity_id=_VAC, map_id=_MAP)
    assert stop["stopped"] is True and stop["sample_count"] == 1

    listing = mapping_manager.list_trace_runs(vacuum_entity_id=_VAC)
    assert run_id in listing["run_ids"]
    got = mapping_manager.get_trace_run(vacuum_entity_id=_VAC, run_id=run_id)
    assert got["found"] is True
    deleted = mapping_manager.delete_trace_run_by_id(vacuum_entity_id=_VAC, run_id=run_id)
    assert deleted["deleted"] is True


def test_cancel_trace_capture(mapping_manager):
    """[MGR-6]"""
    mapping_manager.start_trace_capture(vacuum_entity_id=_VAC, map_id="cap2")
    cancelled = mapping_manager.cancel_trace_capture(vacuum_entity_id=_VAC, map_id="cap2")
    assert cancelled["cancelled"] is True


def test_trace_run_not_found(mapping_manager):
    """[MGR-7]"""
    assert mapping_manager.get_trace_run(vacuum_entity_id=_VAC, run_id="ghost")["found"] is False
    assert mapping_manager.delete_trace_run_by_id(vacuum_entity_id=_VAC, run_id="ghost")["deleted"] is False


# ---------------------------------------------------------------------------
# Review / segment
# ---------------------------------------------------------------------------

def test_review_run_not_found(mapping_manager):
    """[MGR-8]"""
    result = mapping_manager.review_trace_run_for_room(
        vacuum_entity_id=_VAC, map_id=_MAP, run_id="ghost", room_id="3")
    assert result["verdict"] == "error" and result["error"] == "run_not_found"


def test_review_run_no_polygon(mapping_manager):
    """[MGR-9] a captured run with no room boundary → no_polygon."""
    mapping_manager.start_trace_capture(vacuum_entity_id=_VAC, map_id=_MAP, room_id="3")
    for i in range(12):
        mapping_manager.append_trace_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=float(i), y=float(i))
    run_id = mapping_manager.stop_trace_capture(vacuum_entity_id=_VAC, map_id=_MAP)["run_id"]
    result = mapping_manager.review_trace_run_for_room(
        vacuum_entity_id=_VAC, map_id=_MAP, run_id=run_id, room_id="3")
    assert result["error"] == "no_polygon"


def test_segment_run(mapping_manager):
    """[MGR-10]"""
    missing = mapping_manager.segment_trace_run_for_room(
        vacuum_entity_id=_VAC, map_id=_MAP, run_id="ghost")
    assert missing["error"] == "run_not_found"

    mapping_manager.start_trace_capture(vacuum_entity_id=_VAC, map_id=_MAP)
    for i in range(12):
        mapping_manager.append_trace_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=float(i), y=0.0)
    run_id = mapping_manager.stop_trace_capture(vacuum_entity_id=_VAC, map_id=_MAP)["run_id"]
    out = mapping_manager.segment_trace_run_for_room(
        vacuum_entity_id=_VAC, map_id=_MAP, run_id=run_id)
    assert out["error"] is None
    assert isinstance(out["segments"], list)


# ---------------------------------------------------------------------------
# Boundary trace lifecycle
# ---------------------------------------------------------------------------

def test_boundary_trace_lifecycle(mapping_manager):
    """[MGR-11]"""
    started = mapping_manager.start_room_boundary_trace(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id="5")
    assert started["started"] is True
    for x, y in _square_trail():
        mapping_manager.append_trace_point(
            vacuum_entity_id=_VAC, map_id=_MAP, room_id="5", vacuum_x=x, vacuum_y=y)
    closed = mapping_manager.close_room_boundary(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id="5")
    assert closed["closed"] is True
    assert closed["point_count_simplified"] >= 4

    state = mapping_manager.get_mapping_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert state["rooms"]["5"]["boundary_point_count"] >= 4


def test_close_boundary_no_samples(mapping_manager):
    """[MGR-12]"""
    mapping_manager.start_room_boundary_trace(vacuum_entity_id=_VAC, map_id="b2", room_id="5")
    closed = mapping_manager.close_room_boundary(vacuum_entity_id=_VAC, map_id="b2", room_id="5")
    assert closed["closed"] is False
    assert closed["reason"] == "no_trace_samples"


def test_cancel_boundary_trace(mapping_manager):
    """[MGR-13]"""
    mapping_manager.start_room_boundary_trace(vacuum_entity_id=_VAC, map_id="b3", room_id="5")
    mapping_manager.append_trace_point(
        vacuum_entity_id=_VAC, map_id="b3", room_id="5", vacuum_x=1.0, vacuum_y=1.0)
    cancelled = mapping_manager.cancel_room_boundary_trace(
        vacuum_entity_id=_VAC, map_id="b3", room_id="5")
    assert cancelled["cancelled"] is True
    assert cancelled["discarded_points"] == 1


def test_append_trace_point_no_active(mapping_manager):
    """[MGR-14]"""
    assert mapping_manager.append_trace_point(
        vacuum_entity_id=_VAC, map_id="none", room_id="5", vacuum_x=1.0, vacuum_y=1.0) is False


# ---------------------------------------------------------------------------
# Dock + package
# ---------------------------------------------------------------------------

def test_set_dock_anchor_requires_docked(hass, mapping_manager):
    """[MGR-15]"""
    # not docked → raises
    hass.states.async_set(_VAC, "cleaning")
    with pytest.raises(ValueError):
        mapping_manager.set_dock_anchor(
            vacuum_entity_id=_VAC, map_id=_MAP, pixel_x=10.0, pixel_y=20.0)
    # docked → saves
    hass.states.async_set(_VAC, "docked")
    result = mapping_manager.set_dock_anchor(
        vacuum_entity_id=_VAC, map_id=_MAP, pixel_x=10.0, pixel_y=20.0)
    assert result["saved"] is True
    assert result["dock"]["pixel"] == [10.0, 20.0]


def test_set_dock_room(mapping_manager):
    """[MGR-16]"""
    result = mapping_manager.set_dock_room(vacuum_entity_id=_VAC, map_id=_MAP, room_id="2")
    assert result["saved"] is True
    assert result["dock"]["room_id"] == "2"


def test_append_trace_evidence(mapping_manager):
    """[MGR-17]"""
    result = mapping_manager.append_mapping_trace_evidence(
        vacuum_entity_id=_VAC, map_id="evmgr", evidence={"label": "doorway", "x": 1})
    assert result["saved"] is True
    assert result["trace_count"] == 1


def test_get_mapping_state(mapping_manager):
    """[MGR-18]"""
    state = mapping_manager.get_mapping_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert state["vacuum_entity_id"] == _VAC
    assert state["map_id"] == _MAP
    assert "package" in state
    assert "all_rooms" in state
