"""Phase 6 integration tests — setup status (get_setup_status).

Coverage targets
----------------
[SS-1]  No manager in hass.data → state=no_vacuums, setup_complete=False.
[SS-2]  Manager present, no vacuums registered → state=no_vacuums.
[SS-3]  Vacuum registered, no map imported → state=no_map.
[SS-4]  Vacuum with imported map → state=ready, has_imported_map=True.
[SS-5]  Response always contains setup_complete, vacuums, state, next_actions.
[SS-6]  Per-vacuum entry contains setup_steps, next_step, room_drift, maps.
[SS-7]  setup_complete is False when no vacuum has an imported map.
[SS-8]  next_actions is empty when state=ready.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.setup.status import get_setup_status

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [SS-1] No manager
# ---------------------------------------------------------------------------

def test_get_setup_status_no_manager(hass):
    """[SS-1] Returns no_vacuums + setup_complete=False when manager is absent."""
    hass.data.setdefault(DOMAIN, {})
    # DATA_RUNTIME deliberately not set
    result = get_setup_status(hass)
    assert result["state"] == "no_vacuums"
    assert result["setup_complete"] is False
    assert result["vacuums"] == []


# ---------------------------------------------------------------------------
# [SS-2] Manager present, no vacuums
# ---------------------------------------------------------------------------

def test_get_setup_status_no_vacuums(hass, manager):
    """[SS-2] Returns state=no_vacuums when manager has no registered vacuums."""
    result = get_setup_status(hass)
    assert result["state"] == "no_vacuums"
    assert result["vacuums"] == []


# ---------------------------------------------------------------------------
# [SS-3] Vacuum registered, no map
# ---------------------------------------------------------------------------

def test_get_setup_status_vacuum_no_map(hass, manager):
    """[SS-3] Returns state=no_map when vacuum is registered but has no map."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    assert result["state"] == "no_map"
    assert len(result["vacuums"]) == 1


# ---------------------------------------------------------------------------
# [SS-4] Vacuum with imported map
# ---------------------------------------------------------------------------

def test_get_setup_status_vacuum_with_map(hass, manager):
    """[SS-4] Returns state=ready and has_imported_map=True when map has rooms."""
    setup_map(manager, _VAC, _MAP, count=3)
    result = get_setup_status(hass)
    assert result["state"] == "ready"
    vac_entry = result["vacuums"][0]
    assert vac_entry["has_imported_map"] is True


# ---------------------------------------------------------------------------
# [SS-5] Response structure
# ---------------------------------------------------------------------------

def test_get_setup_status_response_has_required_keys(hass, manager):
    """[SS-5] Response always contains setup_complete, vacuums, state, next_actions."""
    result = get_setup_status(hass)
    for key in ("setup_complete", "vacuums", "state", "next_actions"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# [SS-6] Per-vacuum entry structure
# ---------------------------------------------------------------------------

def test_get_setup_status_per_vacuum_entry_structure(hass, manager):
    """[SS-6] Per-vacuum entry contains setup_steps, next_step, room_drift, maps."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    vac_entry = result["vacuums"][0]
    for key in ("setup_steps", "next_step", "room_drift", "maps"):
        assert key in vac_entry, f"Missing per-vacuum key: {key}"


def test_get_setup_status_room_drift_has_in_sync_key(hass, manager):
    """[SS-6] room_drift entry contains at least the in_sync boolean."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    drift = result["vacuums"][0]["room_drift"]
    assert "in_sync" in drift


# ---------------------------------------------------------------------------
# [SS-7] setup_complete logic
# ---------------------------------------------------------------------------

def test_get_setup_status_setup_complete_false_no_map(hass, manager):
    """[SS-7] setup_complete is False when vacuum has no imported map."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    assert result["setup_complete"] is False


# ---------------------------------------------------------------------------
# [SS-8] next_actions when ready
# ---------------------------------------------------------------------------

def test_get_setup_status_next_actions_empty_when_ready(hass, manager):
    """[SS-8] next_actions is empty list when state=ready."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = get_setup_status(hass)
    assert result["state"] == "ready"
    assert result["next_actions"] == []


# ---------------------------------------------------------------------------
# [SS-9 / SS-10] save_rooms re-opens against the ACTIVE map (factory-reset guard)
# ---------------------------------------------------------------------------

def _register_active_map_adapter(hass, vacuum_entity_id, am_entity):
    """Register a minimal adapter config declaring the active-map entity."""
    from custom_components.eufy_vacuum.const import DATA_ADAPTER_COORDINATOR

    coordinator = hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR]
    coordinator.register_adapter_config(
        vacuum_entity_id,
        {"adapter_id": "test", "entities": {"active_map": am_entity}},
    )


def test_get_setup_status_save_rooms_reopens_on_unconfigured_active_map(hass, manager):
    """[SS-9] After the active map changes to one with no configured rooms (factory
    reset / new map id), save_rooms re-opens despite its sticky flag, so setup is not
    reported complete."""
    from custom_components.eufy_vacuum.setup.drift import record_step_completed

    setup_map(manager, _VAC, "1", count=3)  # configured map "1"
    record_step_completed(manager, _VAC, "add_vacuum")
    record_step_completed(manager, _VAC, "save_rooms")

    _register_active_map_adapter(hass, _VAC, "sensor.alfred_active_map")
    hass.states.async_set("sensor.alfred_active_map", "11")  # new, blank map
    manager.data["maps"][_VAC]["11"] = {"rooms": {}}  # imported, no rooms

    result = get_setup_status(hass)
    vac = result["vacuums"][0]
    save_rooms = next(s for s in vac["setup_steps"] if s["id"] == "save_rooms")
    assert save_rooms["completed"] is False
    assert vac["next_step"] == "save_rooms"
    assert result["setup_complete"] is False


def test_get_setup_status_save_rooms_stays_complete_on_configured_active_map(hass, manager):
    """[SS-10] With the active map pointing at the configured map, save_rooms stays
    complete — no spurious re-open."""
    from custom_components.eufy_vacuum.setup.drift import record_step_completed

    setup_map(manager, _VAC, "1", count=3)
    record_step_completed(manager, _VAC, "add_vacuum")
    record_step_completed(manager, _VAC, "save_rooms")

    _register_active_map_adapter(hass, _VAC, "sensor.alfred_active_map")
    hass.states.async_set("sensor.alfred_active_map", "1")  # active = the configured map

    result = get_setup_status(hass)
    vac = result["vacuums"][0]
    save_rooms = next(s for s in vac["setup_steps"] if s["id"] == "save_rooms")
    assert save_rooms["completed"] is True
