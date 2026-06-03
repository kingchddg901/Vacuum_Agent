"""Phase 7 integration tests — services/adapter_config.py.

Coverage targets
----------------
[AC-1]  get_adapter_config returns config=None when no adapter is registered.
[AC-2]  get_adapter_config returns the registered config after save_adapter_config.
[AC-3]  save_adapter_config with valid config registers it (side-effect via get).
[AC-4]  delete_adapter_config removes a registered adapter.
[AC-5]  observe_entity_states returns observations for known and unknown entities.
[AC-6]  observe_entity_states returns state=None for absent entity.
[AC-7]  discover_adapter_entities returns entity_count and by_domain.
[AC-8]  get_vacuum_capabilities returns a dict with vacuum_entity_id.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config


_VAC = "vacuum.alfred"

_VALID_CONFIG = {
    "adapter_id": "test_adapter",
    "source": "config",
    "dispatch": {"template": "eufy_robovac"},
    "entities": {
        "task_status": "sensor.alfred_task_status",
    },
}


# ---------------------------------------------------------------------------
# [AC-1] get_adapter_config — no adapter registered
# ---------------------------------------------------------------------------

async def test_get_adapter_config_no_adapter_returns_none_config(hass, manager_with_services):
    """[AC-1] get_adapter_config returns config=None when no adapter is registered."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_adapter_config",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["config"] is None
    assert result["adapter_id"] is None


# ---------------------------------------------------------------------------
# [AC-2] — [AC-3] save_adapter_config + get_adapter_config round-trip
# ---------------------------------------------------------------------------

async def test_save_then_get_adapter_config_round_trip(hass, manager_with_services):
    """[AC-2] save_adapter_config registers the config; get_adapter_config returns it."""
    await hass.services.async_call(
        DOMAIN,
        "save_adapter_config",
        {"vacuum_entity_id": _VAC, "config": dict(_VALID_CONFIG)},
        blocking=True,
    )
    result = await hass.services.async_call(
        DOMAIN,
        "get_adapter_config",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["adapter_id"] == "test_adapter"
    assert result["config"] is not None
    assert result["source"] == "config"


async def test_save_adapter_config_forces_source_config(hass, manager_with_services):
    """[AC-3] save_adapter_config always sets source='config' regardless of caller input."""
    config = dict(_VALID_CONFIG)
    config["source"] = "manual"  # caller tries to set a different source
    await hass.services.async_call(
        DOMAIN,
        "save_adapter_config",
        {"vacuum_entity_id": _VAC, "config": config},
        blocking=True,
    )
    result = await hass.services.async_call(
        DOMAIN,
        "get_adapter_config",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["source"] == "config"


# ---------------------------------------------------------------------------
# [AC-4] delete_adapter_config
# ---------------------------------------------------------------------------

async def test_save_adapter_config_rejects_incomplete(hass, manager_with_services):
    """[AC-3b] save_adapter_config rejects configs missing adapter_id or
    dispatch.template (the early-return validation) and registers nothing."""
    from custom_components.eufy_vacuum.adapters.registry import get_adapter_config
    # missing adapter_id → early return
    await hass.services.async_call(
        DOMAIN, "save_adapter_config",
        {"vacuum_entity_id": _VAC, "config": {"dispatch": {"template": "eufy_room_clean"}}},
        blocking=True)
    assert get_adapter_config(_VAC) is None
    # missing dispatch.template → early return
    await hass.services.async_call(
        DOMAIN, "save_adapter_config",
        {"vacuum_entity_id": _VAC, "config": {"adapter_id": "a"}}, blocking=True)
    assert get_adapter_config(_VAC) is None


async def test_delete_adapter_config_removes_registration(hass, manager_with_services):
    """[AC-4] delete_adapter_config clears the adapter registration."""
    # Save via the service so the config is persisted in manager.data (not
    # just in-memory), which is what delete_adapter_config checks.
    await hass.services.async_call(
        DOMAIN,
        "save_adapter_config",
        {"vacuum_entity_id": _VAC, "config": dict(_VALID_CONFIG)},
        blocking=True,
    )
    result_before = await hass.services.async_call(
        DOMAIN,
        "get_adapter_config",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result_before["adapter_id"] is not None

    await hass.services.async_call(
        DOMAIN,
        "delete_adapter_config",
        {"vacuum_entity_id": _VAC},
        blocking=True,
    )
    result_after = await hass.services.async_call(
        DOMAIN,
        "get_adapter_config",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result_after["config"] is None


# ---------------------------------------------------------------------------
# [AC-5] — [AC-6] observe_entity_states
# ---------------------------------------------------------------------------

async def test_observe_entity_states_returns_known_state(hass, manager_with_services):
    """[AC-5] observe_entity_states returns the current state for a known entity."""
    hass.states.async_set("sensor.alfred_task_status", "cleaning")
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        DOMAIN,
        "observe_entity_states",
        {"entity_ids": ["sensor.alfred_task_status"]},
        blocking=True,
        return_response=True,
    )
    assert result["entity_count"] == 1
    obs = result["observations"][0]
    assert obs["entity_id"] == "sensor.alfred_task_status"
    assert obs["state"] == "cleaning"


async def test_observe_entity_states_returns_none_for_missing_entity(hass, manager_with_services):
    """[AC-6] observe_entity_states returns state=None for an entity not in hass."""
    result = await hass.services.async_call(
        DOMAIN,
        "observe_entity_states",
        {"entity_ids": ["sensor.nonexistent_entity"]},
        blocking=True,
        return_response=True,
    )
    obs = result["observations"][0]
    assert obs["state"] is None
    assert obs["attributes"] == {}


async def test_observe_entity_states_mixed_known_and_missing(hass, manager_with_services):
    """[AC-5] observe_entity_states handles a mix of known and missing entities."""
    hass.states.async_set("sensor.alfred_dock_status", "idle")
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        DOMAIN,
        "observe_entity_states",
        {"entity_ids": ["sensor.alfred_dock_status", "sensor.does_not_exist"]},
        blocking=True,
        return_response=True,
    )
    assert result["entity_count"] == 2
    states = {o["entity_id"]: o["state"] for o in result["observations"]}
    assert states["sensor.alfred_dock_status"] == "idle"
    assert states["sensor.does_not_exist"] is None


# ---------------------------------------------------------------------------
# [AC-7] discover_adapter_entities
# ---------------------------------------------------------------------------

async def test_discover_adapter_entities_returns_structure(hass, manager_with_services):
    """[AC-7] discover_adapter_entities returns entity_count, entities, and by_domain."""
    result = await hass.services.async_call(
        DOMAIN,
        "discover_adapter_entities",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert "entity_count" in result
    assert "entities" in result
    assert "by_domain" in result
    assert isinstance(result["entities"], list)
    assert isinstance(result["by_domain"], dict)


async def test_discover_adapter_entities_collects_matching(hass, manager_with_services):
    """[AC-7b] registry entities whose id contains the vacuum object_id are
    collected with domain/state/platform (the match-collection loop body)."""
    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    reg.async_get_or_create("sensor", "eufy_vacuum", "alfred_battery_x",
                            suggested_object_id="alfred_battery_x")
    hass.states.async_set("sensor.alfred_battery_x", "88")
    result = await hass.services.async_call(
        DOMAIN, "discover_adapter_entities", {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True)
    match = next(
        (e for e in result["entities"] if e["entity_id"] == "sensor.alfred_battery_x"), None)
    assert match is not None
    assert match["domain"] == "sensor" and match["current_state"] == "88"


# ---------------------------------------------------------------------------
# [AC-8] get_vacuum_capabilities
# ---------------------------------------------------------------------------

async def test_get_vacuum_capabilities_returns_dict(hass, manager_with_services):
    """[AC-8] get_vacuum_capabilities returns a dict containing vacuum_entity_id."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_vacuum_capabilities",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert result.get("vacuum_entity_id") == _VAC
