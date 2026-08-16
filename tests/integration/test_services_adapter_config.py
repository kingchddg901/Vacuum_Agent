"""Phase 7 integration tests — services/adapter_config.py.

Coverage targets
----------------
[AC-1]  get_adapter_config returns config=None when no adapter is registered.
[AC-2]  get_adapter_config returns the registered config after save_adapter_config.
[AC-3]  save_adapter_config with valid config registers it (side-effect via get).
[AC-3b] RP-031/Q9: save_adapter_config raises ServiceValidationError for a config
        missing adapter_id or dispatch.template (was a silent early return).
[AC-3c] RP-031/Q9: save/delete_adapter_config now supports_response on success too.
[AC-4]  delete_adapter_config removes a registered adapter.
[AC-4c] RP-031/Q9: delete_adapter_config on a never-saved vacuum returns a
        structured {deleted:False, reason:"not_found"}, not a silent no-op.
[AC-5]  observe_entity_states returns observations for known and unknown entities.
[AC-6]  observe_entity_states returns state=None for absent entity.
[AC-7]  discover_adapter_entities returns entity_count and by_domain.
[AC-8]  get_vacuum_capabilities returns a dict with vacuum_entity_id.
"""

from __future__ import annotations

import pytest

from homeassistant.exceptions import ServiceValidationError

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

from tests.brand_catalogs import SYNTHETIC_BLOCK


_VAC = "vacuum.alfred"

_VALID_CONFIG = {
    "adapter_id": "test_adapter",
    "source": "config",
    # RP-033/RF-32: save_adapter_config now runs the config through the full
    # ADAPTER_CONFIG_SCHEMA (validate_adapter_config) before persisting/
    # registering it — template must be a recognized enum value and
    # service_domain/service_name are both required, not just template.
    "dispatch": {
        "template": "eufy_room_clean",
        "service_domain": "vacuum",
        "service_name": "send_command",
    },
    "entities": {
        "task_status": "sensor.alfred_task_status",
    },
    # Required since 2026-08-07: an adapter must DECLARE its profile vocabulary —
    # core carries no catalog to inherit. A stored config is a full adapter (it is
    # the sole source for a vacuum with no code adapter), so this is not optional
    # for it. Declared empty where this brand supplies nothing, which is a
    # different state from omitting the key.
    "room_profiles": {
        "default_profile": "vacuum_quick",
        "builtins": SYNTHETIC_BLOCK["builtins"],
        "custom_template": SYNTHETIC_BLOCK["custom_template"],
        "normalize_defaults": SYNTHETIC_BLOCK["normalize_defaults"],
        "legacy_aliases": {},
        "floor_type_water_defaults": SYNTHETIC_BLOCK["floor_type_water_defaults"],
        "floor_type_fan_defaults": SYNTHETIC_BLOCK["floor_type_fan_defaults"],
    },
}


# ---------------------------------------------------------------------------
# [AC-1] get_adapter_config — no adapter registered
# ---------------------------------------------------------------------------

async def test_get_adapter_config_no_adapter_returns_none_config(hass, manager_with_services):
    """[AC-1] get_adapter_config returns config=None when no adapter is registered."""
    # The manager fixture registers an adapter, because core carries no profile
    # catalog and most tests cannot resolve a room without one. This test is about
    # the genuinely-unregistered state, so it opts out explicitly rather than
    # relying on the fixture happening not to register.
    from custom_components.eufy_vacuum.adapters.registry import unregister_adapter_config
    unregister_adapter_config(_VAC)
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
    """[AC-3b] RP-031/Q9: save_adapter_config rejects configs missing adapter_id
    or dispatch.template with ServiceValidationError (was a silently-logged
    early return that registered nothing but told the caller nothing either --
    Q9's "success-shaped no-op" class) and registers nothing either way."""
    from custom_components.eufy_vacuum.adapters.registry import (
        get_adapter_config,
        unregister_adapter_config,
    )

    # This test asserts that a REJECTED save leaves the registry untouched, so it
    # starts from empty — the manager fixture's adapter would otherwise satisfy the
    # "is None" checks' opposite and hide a regression where a bad config registered.
    unregister_adapter_config(_VAC)

    # missing adapter_id → ServiceValidationError
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "save_adapter_config",
            {"vacuum_entity_id": _VAC, "config": {"dispatch": {"template": "eufy_room_clean"}}},
            blocking=True)
    assert get_adapter_config(_VAC) is None
    # missing dispatch.template → ServiceValidationError
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "save_adapter_config",
            {"vacuum_entity_id": _VAC, "config": {"adapter_id": "a"}}, blocking=True)
    assert get_adapter_config(_VAC) is None


async def test_delete_adapter_config_removes_registration(hass, manager_with_services):
    """[AC-4] RP-033/SETUP-3: delete_adapter_config clears the STORED registration
    and restores the live CODE adapter -- previously left the vacuum with NO
    adapter at all until the next full HA restart (register_brand_adapter is the
    exact function async_setup_entry calls per managed vacuum, so this makes
    delete's restore byte-identical to what a restart would already produce).

    _VAC is registered as a REAL Eufy install would be — in the entity registry, owned
    by `robovac_mqtt`. The previous version of this docstring said it "has no
    device-registry entry, so brand resolution falls through to the declared default arm
    (Eufy)", which described the leak: an unidentified vacuum was silently driven as a
    Eufy. There is no default arm now, so a vacuum with no platform would be UNSUPPORTED
    and delete would restore nothing."""
    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "alfred_unique_id", suggested_object_id="alfred"
    )
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
    assert result_before["adapter_id"] == "test_adapter"
    assert result_before["source"] == "config"

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
    assert result_after["config"] is not None
    assert result_after["source"] == "code"
    assert result_after["adapter_id"] != "test_adapter"


async def test_save_and_delete_adapter_config_responses(hass, manager_with_services):
    """[AC-3c]/[AC-4b] RP-031/Q9: save/delete_adapter_config now support_response
    -- both were previously fire-and-forget (-> None) even on success, so a
    caller had no way to confirm what happened without a separate get_ call."""
    saved = await hass.services.async_call(
        DOMAIN, "save_adapter_config",
        {"vacuum_entity_id": _VAC, "config": dict(_VALID_CONFIG)},
        blocking=True, return_response=True,
    )
    assert saved == {
        "saved": True, "vacuum_entity_id": _VAC, "adapter_id": "test_adapter",
    }

    deleted = await hass.services.async_call(
        DOMAIN, "delete_adapter_config", {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True,
    )
    assert deleted == {"deleted": True, "vacuum_entity_id": _VAC}


async def test_delete_adapter_config_not_found(hass, manager_with_services):
    """[AC-4c] RP-031/Q9: deleting a config that was never saved is a
    structured no-op (not_found), not a silent, response-less success --
    matches the established not-found convention (discard_external_run,
    delete_saved_zone), not an exception (idempotent delete is not a caller
    error)."""
    result = await hass.services.async_call(
        DOMAIN, "delete_adapter_config", {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True,
    )
    assert result == {
        "deleted": False, "vacuum_entity_id": _VAC, "reason": "not_found",
    }


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
