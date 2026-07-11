"""Integration tests for the non-segment mapping service handlers.

These are thin wrappers over already-tested MappingManager methods; calling
them through the service registry covers the handler closures registered by
async_register_mapping_services.

Coverage targets
----------------
[MSV-1]  get_mapping_state / get_mapping_package return dicts.
[MSV-2]  get_room_bounds_snapshot returns available=True.
[MSV-3]  boundary trace: start → cancel.
[MSV-4]  close_room_boundary with no samples → no_trace_samples.
[MSV-5]  set_dock_room persists the room id.
[MSV-6]  set_dock_anchor (vacuum docked) saves the pixel anchor.
[MSV-7]  trace capture: start → stop.
[MSV-8]  cancel_trace_capture with no session → cancelled=False.
[MSV-9]  append_mapping_trace_evidence grows the package list.
[MSV-10] save_mapping_package persists a package.
[MSV-11] review_trace_run with a missing run → error.
[MSV-12] clear_room_bounds on an unknown room → room_not_found.
[MSV-13] exclude_room_job_bounds on an unknown room → room_not_found.
[MSV-14] delete_map_image when the PNG is already gone → record still dropped.
[MSV-15] set_live_map_rotation stores the display rotation on the map bucket.
[MSV-16] set_map_overlay_visibility persists only the user's deltas (not the resolved map), merges them over the defaults at read time, merges successive partial calls, rejects unknown layers, and resets cleanly back to defaults.
[MSV-17] get_map_render_data is registered and degrades gracefully with present=False / reason=not_configured when the adapter declares no map_render block.
"""

from __future__ import annotations

import os

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
from custom_components.eufy_vacuum.mapping.manager import MappingManager
from custom_components.eufy_vacuum.mapping import mapping_services as ms
from custom_components.eufy_vacuum.mapping.mapping_services import (
    async_register_mapping_services,
    async_unregister_mapping_services,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
async def mapping_services(hass, manager):
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


async def test_room_bounds_snapshot(hass, mapping_services):
    """[MSV-2]"""
    snap = await _call(hass, ms.SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert snap["available"] is True


async def test_set_live_map_rotation(hass, mapping_services):
    """[MSV-15] set_live_map_rotation persists the live-map DISPLAY rotation on the
    map bucket (display only; schema validates 0/90/180/270)."""
    manager = mapping_services
    result = await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "rotation": 90})
    assert result["saved"] is True
    assert result["live_map_rotation"] == 90
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 90
    # overwrite with another valid value
    await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "rotation": 270})
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 270
    # an out-of-set value is rejected by the schema (stored value unchanged)
    with pytest.raises(Exception):
        await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "rotation": 45})
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 270


async def test_set_map_overlay_visibility(hass, mapping_services):
    """[MSV-16] set_map_overlay_visibility stores only the user's deltas, merges them
    over the defaults at read time, rejects unknown layers, and resets cleanly."""
    manager = mapping_services
    result = await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "visibility": {"no_go": True, "dock": False}})
    assert result["saved"] is True
    vis = result["overlay_visibility"]
    assert vis["no_go"] is True and vis["dock"] is False
    assert vis["robot"] is True                       # default preserved
    # only the deltas are persisted, not the full resolved map
    assert manager.data["maps"][_VAC][_MAP]["overlay_visibility"] == {
        "no_go": True, "dock": False}
    # a second partial call MERGES (doesn't wipe the prior deltas)
    await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "visibility": {"path": True}})
    assert manager.data["maps"][_VAC][_MAP]["overlay_visibility"] == {
        "no_go": True, "dock": False, "path": True}
    # an unknown layer is rejected by the schema
    with pytest.raises(Exception):
        await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP,
                     "visibility": {"bogus": True}})
    # reset clears the deltas -> back to defaults
    result = await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "reset": True})
    assert "overlay_visibility" not in manager.data["maps"][_VAC][_MAP]
    assert result["overlay_visibility"]["robot"] is True


async def test_get_map_render_data_absent(hass, mapping_services):
    """[MSV-17] get_map_render_data is registered + degrades gracefully when the adapter
    declares no map_render block (no crash, present:false)."""
    result = await _call(hass, ms.SERVICE_GET_MAP_RENDER_DATA, {"vacuum_entity_id": _VAC})
    assert result["present"] is False
    assert result.get("reason") == "not_configured"


async def test_delete_map_image_file_already_gone(hass, mapping_services):
    """[MSV-14] delete_map_image when the PNG is already missing on disk:
    _remove_file hits FileNotFoundError and returns False, but the service
    still drops the stale variant record. Guards the "PNG gone, still drop
    the record" contract (mapping_services.py:691-692)."""
    manager = mapping_services
    object_id = _VAC.split(".", 1)[1]
    missing_path = os.path.join(
        hass.config.config_dir, "eufy_vacuum", "maps", object_id, "does_not_exist.png"
    )
    # Sanity: the file must be absent so os.remove raises FileNotFoundError.
    assert not os.path.exists(missing_path)

    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP
    )
    map_bucket["image_variants"] = {
        "default": {
            "variant": "default",
            "path": missing_path,
            "browser_url": "/local/eufy_vacuum/missing.png",
            "width": 100,
            "height": 100,
        }
    }

    result = await _call(hass, ms.SERVICE_DELETE_MAP_IMAGE,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "variant": "default"})

    # Record dropped even though the file was already gone.
    assert result["deleted"] is True
    # FileNotFoundError branch: nothing was actually removed from disk.
    assert result["file_removed"] is False
    assert result["remaining_variants"] == []
    # Persisted side effect: the stale variant is gone from the bucket.
    assert map_bucket["image_variants"] == {}


async def test_room_bounds_snapshot_stamps_name_and_archive_flag(hass, mapping_services):
    """[MSV-2b] with a registered mapping_tracker, get_room_bounds_snapshot stamps
    each snapshot room with its managed display name and a has_archive flag that is
    True only for rooms that have a raw-samples archive on disk.

    Covers the tracker-present enrichment loop (mapping_services 1554-1559): name
    stamping plus ``room_data['has_archive'] = tracker._find_raw_samples_path(...)
    is not None`` for both outcomes of the is-not-None test.
    """
    from custom_components.eufy_vacuum.mapping.tracker import MappingTracker
    from .conftest import seed_discovery

    manager = mapping_services  # the core EufyVacuumManager (DATA_RUNTIME)
    mm = hass.data[DOMAIN]["mapping_manager"]
    # Dedicated map id: this test persists managed rooms + map JSON to disk, so it
    # uses its own map to stay isolated from the shared-_MAP dock/clear tests.
    snap_map = "snap_bounds"

    # Managed-room config so get_managed_rooms returns room 3 named "Bedroom".
    # Room 5 is the no-archive control (its name is not asserted on).
    seed_discovery(manager, _VAC, snap_map, [
        {"room_id": 3, "map_id": snap_map, "name": "Bedroom"},
        {"room_id": 5, "map_id": snap_map, "name": "Hallway"},
    ])
    manager.save_managed_rooms(vacuum_entity_id=_VAC, map_id=snap_map)

    # Seed map data so both rooms appear in get_room_bounds_snapshot()['rooms'].
    map_data = mm._ensure_map_data(_VAC, snap_map)
    for rid in ("3", "5"):
        map_data["rooms"][rid] = {
            "bounds": {"min_x": 0.0, "max_x": 10.0, "min_y": 0.0, "max_y": 10.0, "run_count": 1},
            "job_bounds_history": [],
        }
    mm._save_map_data(_VAC, snap_map, map_data)

    # Register a real tracker and give ONLY room 3 a raw-samples archive on disk
    # (_find_raw_samples_path is keyed by vacuum + room id, independent of map).
    tracker = MappingTracker(hass, mm)
    hass.data[DOMAIN]["mapping_tracker"] = tracker
    tracker._append_raw_samples(
        _VAC, snap_map, "3", "j1", "2026-01-01T10:00:00+00:00",
        [(1.0, 1.0)], room_slug="bedroom", room_name="Bedroom",
    )
    assert tracker._find_raw_samples_path(_VAC, "3") is not None
    assert tracker._find_raw_samples_path(_VAC, "5") is None

    snap = await _call(hass, ms.SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
                       {"vacuum_entity_id": _VAC, "map_id": snap_map})

    # Room 3: managed name stamped + archive present -> has_archive True.
    assert snap["rooms"]["3"]["name"] == "Bedroom"
    assert snap["rooms"]["3"]["has_archive"] is True
    # Room 5: no archive file -> has_archive False (the is-not-None False branch).
    assert snap["rooms"]["5"]["has_archive"] is False

