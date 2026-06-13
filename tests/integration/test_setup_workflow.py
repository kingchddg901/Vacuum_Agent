"""Phase 6 integration tests — setup workflow (add_vacuum, import_active_map).

Extends to the full setup subpackage: workflow (add/import), delete (protection
gating), and drift bookkeeping (step records, reject / force-remove, drift
snapshot). Driven against the real ``manager`` fixture (DATA_RUNTIME wired) plus
adapter config and live hass states.

Coverage targets
----------------
[SW-1]  add_vacuum returns blocked when entity is absent from state machine.
[SW-2]  add_vacuum returns success when entity is present.
[SW-3]  add_vacuum success adds vacuum to manager.data.
[SW-4]  add_vacuum returns already_done when vacuum is already managed.
[SW-5]  add_vacuum returns error when manager is absent.
[SW-6]  import_active_map returns blocked when vacuum is not managed.
[SW-7]  import_active_map returns blocked when no active map sensor is present.
[SW-8]  import_active_map returns already_done when map is already imported.
[SW-9]  import_active_map success discovers + saves rooms.
[SW-10] delete_map: unknown map → already_done.
[SW-11] delete_map: elevated (only map) needs confirm; token → success.
[SW-12] delete_map: high protection typed-confirm mismatch → blocked.
[SD-1]  record_step_completed idempotent + unknown step ignored.
[SD-2]  reject_rooms strips managed rooms + reports affected maps.
[SD-3]  force_remove_room bumps missing_passes to threshold.
[SD-4]  compute_room_drift surfaces a removed room after threshold misses.
[SD-5]  run_discovery_pass reads the adapter room list + updates drift.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.setup import drift as drift_mod
from custom_components.eufy_vacuum.setup.delete import delete_map
from custom_components.eufy_vacuum.setup.workflow import add_vacuum, import_active_map

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


@pytest.fixture
def _no_panel(monkeypatch):
    """Stub panel registration so add_vacuum doesn't touch the frontend."""
    async def _fake_register_panel(*args, **kwargs):
        return None

    import homeassistant.components.panel_custom as panel_custom
    monkeypatch.setattr(panel_custom, "async_register_panel", _fake_register_panel)


def _discovery_adapter(map_entity="sensor.alfred_active_map"):
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": map_entity},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })


# ---------------------------------------------------------------------------
# [SW-1] — [SW-4] add_vacuum
# ---------------------------------------------------------------------------

async def test_add_vacuum_entity_absent_returns_blocked(hass, manager):
    """[SW-1] add_vacuum returns status=blocked when entity not in state machine."""
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "blocked"
    assert _VAC in result["data"].get("vacuum_entity_id", "")


async def test_add_vacuum_entity_present_returns_success(hass, manager):
    """[SW-2] add_vacuum returns status=success when entity exists in HA."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "success"


async def test_add_vacuum_success_writes_vacuum_record(hass, manager):
    """[SW-3] add_vacuum success registers the vacuum in manager.data."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    await add_vacuum(hass, _VAC)
    assert _VAC in manager.data.get("vacuums", {})


async def test_add_vacuum_already_managed_returns_already_done(hass, manager):
    """[SW-4] add_vacuum returns status=already_done when vacuum is already tracked."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "already_done"
    assert "import_active_map" in result.get("next_actions", [])


async def test_add_vacuum_no_manager_returns_error(hass):
    """[SW-5] add_vacuum returns status=error when manager is absent."""
    hass.data.setdefault(DOMAIN, {})
    # DATA_RUNTIME deliberately not set
    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# [SW-6] — [SW-8] import_active_map
# ---------------------------------------------------------------------------

async def test_import_active_map_unmanaged_returns_blocked(hass, manager):
    """[SW-6] import_active_map returns blocked when vacuum is not yet managed."""
    result = await import_active_map(hass, _VAC)
    assert result["status"] == "blocked"
    assert "next_actions" in result
    assert "add_vacuum" in result["next_actions"]


async def test_import_active_map_no_map_sensor_returns_blocked(hass, manager):
    """[SW-7] import_active_map returns blocked when no active_map entity is declared."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    # No adapter with active_map entity → get_active_map_id returns None
    result = await import_active_map(hass, _VAC)
    assert result["status"] == "blocked"


async def test_import_active_map_already_imported_returns_already_done(hass, manager):
    """[SW-8] import_active_map returns already_done when map has rooms."""
    setup_map(manager, _VAC, _MAP, count=3)
    # Simulate active_map entity so get_active_map_id resolves to _MAP
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test",
        "source": "test",
        "entities": {"active_map": "sensor.alfred_active_map"},
    })
    hass.states.async_set("sensor.alfred_active_map", _MAP)
    await hass.async_block_till_done()

    result = await import_active_map(hass, _VAC)
    assert result["status"] == "already_done"
    assert result["data"]["map_id"] == _MAP
    assert result["data"]["room_count"] == 3


async def test_import_active_map_success(hass, manager, _no_panel):
    """[SW-9] managed vacuum + active map + discoverable segments → success."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 2, "name": "Bath"},
    ]})
    await add_vacuum(hass, _VAC)
    hass.states.async_set("sensor.alfred_active_map", "sw9map")
    result = await import_active_map(hass, _VAC)
    assert result["status"] == "success"
    assert result["data"]["room_count"] == 2
    assert manager.data["maps"][_VAC]["sw9map"]["rooms"]


# ---------------------------------------------------------------------------
# [SW-10] — [SW-12] delete_map protection gating
# ---------------------------------------------------------------------------

async def test_delete_unknown_map(hass, manager):
    """[SW-10]"""
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id="404")
    assert result["status"] == "already_done"
    assert result["code"] == "map_not_found"


async def test_delete_elevated_requires_confirm(hass, manager):
    """[SW-11] single imported map → elevated; token unlocks the delete."""
    setup_map(manager, _VAC, "swdel11", count=2)
    pending = await delete_map(hass, vacuum_entity_id=_VAC, map_id="swdel11")
    assert pending["status"] == "requires_confirmation"
    done = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id="swdel11", confirmation_token="yes")
    assert done["status"] == "success"
    assert "swdel11" not in manager.data.get("maps", {}).get(_VAC, {})


async def test_delete_high_typed_mismatch(hass, manager):
    """[SW-12] two protection reasons → high → typed confirm enforced."""
    setup_map(manager, _VAC, "swdel12", count=2)
    rooms = manager.data["maps"][_VAC]["swdel12"]["rooms"]
    first_key = next(iter(rooms))
    rooms[first_key]["rules"] = [{"kind": "blocker", "entity_id": "binary_sensor.x"}]
    bad = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id="swdel12", confirmation_token="wrong")
    assert bad["status"] == "blocked"
    assert bad["code"] == "confirmation_mismatch"


# ---------------------------------------------------------------------------
# [SD-1] — [SD-5] drift bookkeeping (setup/drift.py)
# ---------------------------------------------------------------------------

def test_record_step_completed(manager):
    """[SD-1]"""
    drift_mod.record_step_completed(manager, _VAC, "add_vacuum")
    drift_mod.record_step_completed(manager, _VAC, "add_vacuum")  # idempotent
    drift_mod.record_step_completed(manager, _VAC, "bogus_step")   # ignored
    progress = manager.data["setup_progress"][_VAC]
    assert progress["completed_steps"] == ["add_vacuum"]
    assert progress["last_advanced_at"] is not None


def test_reject_rooms_strips_managed(manager):
    """[SD-2]"""
    setup_map(manager, _VAC, "sdrej", count=3)
    result = drift_mod.reject_rooms(manager, _VAC, [1, 2])
    assert set(result["rejected"]) == {1, 2}
    assert "sdrej" in result["affected_map_ids"]
    remaining = manager.data["maps"][_VAC]["sdrej"]["rooms"]
    remaining_ids = {int(r.get("room_id", k)) for k, r in remaining.items()}
    assert 1 not in remaining_ids and 2 not in remaining_ids


def test_force_remove_room(manager):
    """[SD-3] default removal threshold is 3."""
    result = drift_mod.force_remove_room(manager, _VAC, 7)
    assert result["missing_passes"] == 3
    assert result["threshold"] == 3
    entry = manager.data["setup_progress"][_VAC]["room_drift_history"]["7"]
    assert entry["missing_passes"] == 3


def test_run_discovery_pass(manager, hass):
    """[SD-5] run_discovery_pass reads the adapter room list + updates drift."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Bath"}]})
    result = drift_mod.run_discovery_pass(hass, manager, _VAC)
    assert set(result["discovered_room_ids"]) == {1, 2}
    assert result["updated_at"]
    # drift history now tracks the discovered rooms
    hist = manager.data["setup_progress"][_VAC]["room_drift_history"]
    assert "1" in hist and "2" in hist


def test_compute_room_drift_removed(manager):
    """[SD-4] a configured room missing for >= threshold passes → removed."""
    setup_map(manager, _VAC, "sddrift", count=2)
    for _ in range(3):
        drift_mod.update_drift_history(manager, _VAC, {1})
    drift = drift_mod.compute_room_drift(manager, _VAC)
    removed_ids = {r["room_id"] for r in drift["removed_rooms"]}
    assert 2 in removed_ids
    assert drift["in_sync"] is False
