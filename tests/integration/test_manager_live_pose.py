"""Tests for the live-pose MANAGER seam (feature coverage).

Targets three core/manager.py methods that surface the fork's fresh in-memory
robot/dock pose as the moving overlay (the ~2s live cadence the card polls):

  * ``_apply_inmem_pose_to_result`` — IN-PLACE overlay of the live pose onto a
    ``map_state_source`` result. Gated on a dict ``live_pose`` cfg AND
    ``result['present']``; degrades to the base overlays (never raises) when the
    pose read or overlay-apply fails.
  * ``async_get_map_live_pose`` — the lightweight overlay-only service payload.
    Adapter-driven via ``map_state_source.live_pose``; returns an absent marker
    (+ diagnostics for deploy-time discovery) at each miss point, or the present
    overlay when both pose and geometry resolve.
  * ``_load_live_pose_geom`` — the mtime-cached static ``map_data`` the pose
    normalization needs (only its absent return is reachable without a real
    .storage file, so that is what we pin here).

Pose locator (``_read_inmem_pose``) and geometry loader (``_load_live_pose_geom``)
are monkeypatched on the manager instance to inject absent / present / raising
results, so the assertions exercise the manager's branching + the REAL
``live_pose_overlay`` / ``apply_live_pose_override`` normalization (not mocks).

Coverage targets
----------------
[LP-1]  _apply_inmem_pose_to_result: non-dict live_cfg -> result untouched.
[LP-2]  _apply_inmem_pose_to_result: result not present -> result untouched.
[LP-3]  _apply_inmem_pose_to_result: pose absent -> base overlays kept.
[LP-4]  _apply_inmem_pose_to_result: pose present -> robot/dock/heading/trail overlaid,
        stale owned keys (current_room/path) replaced.
[LP-5]  _apply_inmem_pose_to_result: pose read raises -> no raise, base overlays kept.
[LP-6]  async_get_map_live_pose: no live_pose cfg -> {present:False, reason:not_configured}.
[LP-7]  async_get_map_live_pose: pose absent -> carries the pose reason + diagnostics.
[LP-8]  async_get_map_live_pose: pose present but geometry missing -> reason:no_geom (+diag).
[LP-9]  async_get_map_live_pose: pose + geometry present -> present overlay + diagnostics.
[LP-10] _load_live_pose_geom: no store path -> None.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

_VAC = "vacuum.alfred"

# A 100x100 map_data with no room_pixels raster: live_pose_overlay then emits
# robot_anchor / dock_anchor / robot_heading / path, but NOT current_room
# (current_room_for_pixel needs the raster) — so the expected overlay is exact.
#   normalize_rendered(px, py, 100, 100) == [round(px/100,5), round((99-py)/100,5)]
_GEOM = {"width": 100, "height": 100}

# robot [40,60] -> [0.4, 0.39]; dock [10,20] -> [0.1, 0.79];
# trail last [50,50] -> [0.5, 0.49]; heading 90.
_POSE_PRESENT = {
    "present": True,
    "robot_pixel": [40, 60],
    "dock_pixel": [10, 20],
    "robot_heading": 90,
    "trail_pixels": [[40, 60], [50, 50]],
    "diagnostics": {"pose_at": "hass_data:robovac_mqtt:.coord", "holder_type": "Coord"},
}

_EXPECT_ROBOT = [0.4, 0.39]
_EXPECT_DOCK = [0.1, 0.79]
_EXPECT_PATH = [[0.4, 0.39], [0.5, 0.49]]


def _register(live_pose=None, *, with_source=True):
    """Register an adapter config; include map_state_source.live_pose when given."""
    cfg = {"adapter_id": "eufy", "source": "code", "entities": {}}
    if with_source:
        source = {"backend": "storage"}
        if live_pose is not None:
            source["live_pose"] = live_pose
        cfg["map_state_source"] = source
    register_adapter_config(_VAC, cfg)


# ---------------------------------------------------------------------------
# _apply_inmem_pose_to_result
# ---------------------------------------------------------------------------

def test_apply_no_live_cfg_leaves_result_untouched(manager):
    """[LP-1] live_cfg=None (not a dict) -> early return, result is byte-identical."""
    result = {"present": True, "robot_anchor": [0.9, 0.9], "current_room": 7}
    before = dict(result)
    manager._apply_inmem_pose_to_result(result, _GEOM, _VAC, None)
    assert result == before


def test_apply_result_not_present_leaves_untouched(manager):
    """[LP-2] result.present falsy -> early return even with a valid live_cfg."""
    result = {"present": False, "reason": "no_store"}
    before = dict(result)

    # Guard: if the gate were skipped, this would have been consulted.
    def _boom(*a, **k):  # pragma: no cover - asserts it is NOT called
        raise AssertionError("_read_inmem_pose called despite result not present")

    manager._read_inmem_pose = _boom
    manager._apply_inmem_pose_to_result(result, _GEOM, _VAC, {"robot_pixel_attrs": ["x"]})
    assert result == before


def test_apply_pose_absent_keeps_base_overlays(manager):
    """[LP-3] pose not present -> no override; base moving overlays survive intact."""
    result = {"present": True, "robot_anchor": [0.9, 0.9], "current_room": 5,
              "path": [[0.1, 0.1]]}
    before = dict(result)
    manager._read_inmem_pose = lambda vid, cfg: {"present": False, "reason": "no_pose"}
    manager._apply_inmem_pose_to_result(result, _GEOM, _VAC, {"robot_pixel_attrs": ["x"]})
    assert result == before


def test_apply_pose_present_overlays_moving_fields(manager):
    """[LP-4] pose present -> robot/dock/heading/trail overlaid; stale owned keys replaced."""
    # Seed STALE moving fields that the live pose must override / clear.
    result = {
        "present": True,
        "rooms": [{"number": 1}],          # static field must survive untouched
        "robot_anchor": [0.99, 0.99],      # stale -> replaced by live
        "current_room": 99,                # stale, NOT re-emitted (no raster) -> cleared
        "path": [[0.99, 0.99]],            # stale -> replaced by fresh trail
    }
    manager._read_inmem_pose = lambda vid, cfg: dict(_POSE_PRESENT)
    manager._apply_inmem_pose_to_result(
        result, _GEOM, _VAC, {"robot_pixel_attrs": ["robot_pixel"]},
    )

    assert result["present"] is True
    assert result["rooms"] == [{"number": 1}]        # static preserved
    assert result["robot_anchor"] == _EXPECT_ROBOT   # live override
    assert result["dock_anchor"] == _EXPECT_DOCK
    assert result["robot_heading"] == 90
    assert result["path"] == _EXPECT_PATH            # fresh trail replaced stale
    # No raster -> current_room cannot resolve, and the owned key was cleared first
    # so the stale 99 does NOT survive next to the fresh anchor.
    assert "current_room" not in result
    # Robot pixel present -> not flagged docked.
    assert "robot_docked" not in result


def test_apply_pose_read_raises_keeps_base_overlays(manager):
    """[LP-5] a raising pose read degrades to the base overlays; does not propagate."""
    result = {"present": True, "robot_anchor": [0.5, 0.5], "current_room": 3}
    before = dict(result)

    def _raise(vid, cfg):
        raise RuntimeError("provider internal blew up")

    manager._read_inmem_pose = _raise
    # Must NOT raise (on-loop snapshot contract).
    manager._apply_inmem_pose_to_result(result, _GEOM, _VAC, {"robot_pixel_attrs": ["x"]})
    assert result == before


def test_apply_docked_robot_flags_and_anchors_to_dock(manager):
    """[LP-4 variant] robot_pixel None (docked) -> anchor falls back to dock + robot_docked."""
    result = {"present": True}
    docked = {
        "present": True,
        "robot_pixel": None,               # fork nulls this while docked
        "dock_pixel": [10, 20],
        "robot_heading": None,
        "trail_pixels": None,
    }
    manager._read_inmem_pose = lambda vid, cfg: dict(docked)
    manager._apply_inmem_pose_to_result(
        result, _GEOM, _VAC, {"robot_pixel_attrs": ["robot_pixel"]},
    )
    assert result["robot_anchor"] == _EXPECT_DOCK    # robot resolved to the dock
    assert result["dock_anchor"] == _EXPECT_DOCK
    assert result["robot_docked"] is True
    assert "robot_heading" not in result             # None heading omitted


# ---------------------------------------------------------------------------
# async_get_map_live_pose
# ---------------------------------------------------------------------------

async def test_get_live_pose_not_configured(manager):
    """[LP-6] adapter has no live_pose block -> {present:False, reason:not_configured}."""
    _register(live_pose=None)
    out = await manager.async_get_map_live_pose(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "not_configured"}


async def test_get_live_pose_no_source_at_all(manager):
    """[LP-6 variant] no map_state_source -> not_configured (source_cfg is None)."""
    _register(with_source=False)
    out = await manager.async_get_map_live_pose(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "not_configured"}


async def test_get_live_pose_pose_absent_carries_reason_and_diag(manager):
    """[LP-7] pose locator returns absent -> reason + diagnostics passthrough; no geom read."""
    _register(live_pose={"robot_pixel_attrs": ["robot_pixel"]})
    diag = {"candidates": ["hass_data:robovac_mqtt"], "structure": {"x": 1}}
    manager._read_inmem_pose = lambda vid, cfg: {
        "present": False, "reason": "no_pose", "diagnostics": diag,
    }

    # Geometry must NOT be consulted once the pose is absent.
    async def _boom(*a, **k):  # pragma: no cover - asserts it is NOT awaited
        raise AssertionError("geometry loaded despite absent pose")

    manager._load_live_pose_geom = _boom

    out = await manager.async_get_map_live_pose(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "no_pose", "diagnostics": diag}


async def test_get_live_pose_no_geom(manager):
    """[LP-8] pose present but geometry missing -> {present:False, reason:no_geom} + diag."""
    _register(live_pose={"robot_pixel_attrs": ["robot_pixel"]})
    manager._read_inmem_pose = lambda vid, cfg: dict(_POSE_PRESENT)

    async def _no_geom(vid, cfg):
        return None

    manager._load_live_pose_geom = _no_geom

    out = await manager.async_get_map_live_pose(vacuum_entity_id=_VAC)
    assert out == {
        "present": False,
        "reason": "no_geom",
        "diagnostics": _POSE_PRESENT["diagnostics"],
    }


async def test_get_live_pose_present_overlay_plus_diag(manager):
    """[LP-9] pose + geometry present -> present overlay + diagnostics breadcrumb."""
    _register(live_pose={"robot_pixel_attrs": ["robot_pixel"]})
    manager._read_inmem_pose = lambda vid, cfg: dict(_POSE_PRESENT)

    async def _geom(vid, cfg):
        return dict(_GEOM)

    manager._load_live_pose_geom = _geom

    out = await manager.async_get_map_live_pose(vacuum_entity_id=_VAC)
    assert out["present"] is True
    assert out["robot_anchor"] == _EXPECT_ROBOT
    assert out["dock_anchor"] == _EXPECT_DOCK
    assert out["robot_heading"] == 90
    assert out["path"] == _EXPECT_PATH
    assert out["diagnostics"] == _POSE_PRESENT["diagnostics"]
    # Overlay-only payload: no static room data leaks in.
    assert "rooms" not in out


# ---------------------------------------------------------------------------
# _load_live_pose_geom
# ---------------------------------------------------------------------------

async def test_load_live_pose_geom_no_path_returns_none(manager):
    """[LP-10] no resolvable store path -> None (the absent branch)."""
    # No active_map entity / store config on the MagicMock-ish hass, so
    # eufy_store_path returns falsy and the method short-circuits to None.
    out = await manager._load_live_pose_geom(_VAC, {"backend": "storage"})
    assert out is None
