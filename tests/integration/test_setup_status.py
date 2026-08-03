"""Phase 6 integration tests — setup status (get_setup_status).

Coverage targets
----------------
[STS-1]  No manager in hass.data → state=no_vacuums, setup_complete=False.
[STS-2]  Manager present, no vacuums registered → state=no_vacuums.
[STS-3]  Vacuum registered, no map imported → state=no_map.
[STS-4]  Vacuum with imported map → state=ready, has_imported_map=True.
[STS-5]  Response always contains setup_complete, vacuums, state, next_actions.
[STS-6]  Per-vacuum entry contains setup_steps, next_step, room_drift, maps.
[STS-7]  setup_complete is False when no vacuum has an imported map.
[STS-8]  next_actions is empty when state=ready.
[STS-9]  after the active map changes to one with no configured rooms, save_rooms re-opens despite its sticky flag.
[STS-10] with the active map pointing at the configured map, save_rooms stays complete — no spurious re-open.
[STS-11] reconciliation is None when discover_rooms has never cached one (CARD-7/RP-019 gap 2).
[STS-12] reconciliation embeds the LAST-CACHED discover_rooms review, with map_id stamped on.
[STS-13] reconciliation is a PASSIVE read — get_setup_status never triggers a new discovery
         pass, so a live segment change after discover_rooms ran does not change the response
         until discover_rooms runs again.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.setup.status import get_setup_status

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [STS-1] No manager
# ---------------------------------------------------------------------------

def test_get_setup_status_no_manager(hass):
    """[STS-1] Returns no_vacuums + setup_complete=False when manager is absent."""
    hass.data.setdefault(DOMAIN, {})
    # DATA_RUNTIME deliberately not set
    result = get_setup_status(hass)
    assert result["state"] == "no_vacuums"
    assert result["setup_complete"] is False
    assert result["vacuums"] == []


# ---------------------------------------------------------------------------
# [STS-2] Manager present, no vacuums
# ---------------------------------------------------------------------------

def test_get_setup_status_no_vacuums(hass, manager):
    """[STS-2] Returns state=no_vacuums when manager has no registered vacuums."""
    result = get_setup_status(hass)
    assert result["state"] == "no_vacuums"
    assert result["vacuums"] == []


# ---------------------------------------------------------------------------
# [STS-3] Vacuum registered, no map
# ---------------------------------------------------------------------------

def test_get_setup_status_vacuum_no_map(hass, manager):
    """[STS-3] Returns state=no_map when vacuum is registered but has no map."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    assert result["state"] == "no_map"
    assert len(result["vacuums"]) == 1


# ---------------------------------------------------------------------------
# [STS-4] Vacuum with imported map
# ---------------------------------------------------------------------------

def test_get_setup_status_vacuum_with_map(hass, manager):
    """[STS-4] Returns state=ready and has_imported_map=True when map has rooms."""
    setup_map(manager, _VAC, _MAP, count=3)
    result = get_setup_status(hass)
    assert result["state"] == "ready"
    vac_entry = result["vacuums"][0]
    assert vac_entry["has_imported_map"] is True


# ---------------------------------------------------------------------------
# [STS-5] Response structure
# ---------------------------------------------------------------------------

def test_get_setup_status_response_has_required_keys(hass, manager):
    """[STS-5] Response always contains setup_complete, vacuums, state, next_actions."""
    result = get_setup_status(hass)
    for key in ("setup_complete", "vacuums", "state", "next_actions"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# [STS-6] Per-vacuum entry structure
# ---------------------------------------------------------------------------

def test_get_setup_status_per_vacuum_entry_structure(hass, manager):
    """[STS-6] Per-vacuum entry contains setup_steps, next_step, room_drift, maps."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    vac_entry = result["vacuums"][0]
    for key in ("setup_steps", "next_step", "room_drift", "maps"):
        assert key in vac_entry, f"Missing per-vacuum key: {key}"


def test_get_setup_status_room_drift_has_in_sync_key(hass, manager):
    """[STS-6] room_drift entry contains at least the in_sync boolean."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    drift = result["vacuums"][0]["room_drift"]
    assert "in_sync" in drift


# ---------------------------------------------------------------------------
# [STS-7] setup_complete logic
# ---------------------------------------------------------------------------

def test_get_setup_status_setup_complete_false_no_map(hass, manager):
    """[STS-7] setup_complete is False when vacuum has no imported map."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    assert result["setup_complete"] is False


# ---------------------------------------------------------------------------
# [STS-8] next_actions when ready
# ---------------------------------------------------------------------------

def test_get_setup_status_next_actions_empty_when_ready(hass, manager):
    """[STS-8] next_actions is empty list when state=ready."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = get_setup_status(hass)
    assert result["state"] == "ready"
    assert result["next_actions"] == []


# ---------------------------------------------------------------------------
# [STS-9 / SS-10] save_rooms re-opens against the ACTIVE map (factory-reset guard)
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
    """[STS-9] After the active map changes to one with no configured rooms (factory
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
    """[STS-10] With the active map pointing at the configured map, save_rooms stays
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


# ---------------------------------------------------------------------------
# [STS-11 / STS-12 / STS-13] reconciliation embed (CARD-7/RP-019 gap 2)
# ---------------------------------------------------------------------------

def _register_reconciliation_adapter(hass, vacuum_entity_id, am_entity):
    """Register an adapter config with a discovery block, so discover_rooms
    (rooms/room_crud.py) can read a live room list off the vacuum entity's
    'segments' attribute — mirrors test_rooms_reconcile.py's RR-1 setup."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    register_adapter_config(vacuum_entity_id, {
        "adapter_id": "test", "source": "code",
        "entities": {"active_map": am_entity},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })


def test_get_setup_status_reconciliation_none_when_never_discovered(hass, manager):
    """[STS-11] reconciliation is None for a vacuum with no cached discovery
    (discover_rooms never ran for it)."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = get_setup_status(hass)
    vac = result["vacuums"][0]
    assert vac["reconciliation"] is None


def test_get_setup_status_embeds_last_cached_reconciliation(hass, manager):
    """[STS-12] After discover_rooms caches reviews for the active map,
    get_setup_status surfaces the SAME reviews/has_changes/plan_token —
    read from the cache (rooms/room_crud.py's discover_rooms writes it),
    never recomputed — plus the map_id they were cached against, which the
    cached payload itself doesn't carry (see _build_reconciliation_for_vacuum's
    docstring)."""
    from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager

    _register_reconciliation_adapter(hass, _VAC, "sensor.alfred_map")
    # Saved: KITCHEN at old id 16 (mirrors test_rooms_reconcile.py's RR-1).
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "map_id": _MAP, "metadata": {}, "summary": {},
        "rooms": {"16": {"room_id": 16, "name": "KITCHEN", "slug": "kitchen"}},
    }
    hass.states.async_set("sensor.alfred_map", _MAP)
    # Discovery reports KITCHEN at a new id (27) -- the re-segment case.
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 27, "name": "KITCHEN"}]})

    payload = RoomMapManager(manager).discover_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    result = get_setup_status(hass)
    vac = result["vacuums"][0]
    reconciliation = vac["reconciliation"]
    assert reconciliation is not None
    assert reconciliation["reviews"] == payload["reconciliation"]["reviews"]
    assert reconciliation["reviews"] == [
        {"kind": "id_changed", "slug": "kitchen", "name": "KITCHEN", "old_id": 16, "new_id": 27}
    ]
    assert reconciliation["has_changes"] is True
    assert reconciliation["plan_token"] == payload["reconciliation"]["plan_token"]
    assert reconciliation["map_id"] == _MAP


def test_get_setup_status_reconciliation_is_passive_never_reprobes(hass, manager):
    """[STS-13] get_setup_status must NEVER trigger a new discovery pass --
    opening/polling Setup must not itself mutate state. A live segment change
    AFTER discover_rooms ran (which would produce a DIFFERENT review if
    re-probed) must not change what get_setup_status reports until
    discover_rooms actually runs again."""
    from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager

    _register_reconciliation_adapter(hass, _VAC, "sensor.alfred_map")
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "map_id": _MAP, "metadata": {}, "summary": {},
        "rooms": {"16": {"room_id": 16, "name": "KITCHEN", "slug": "kitchen"}},
    }
    hass.states.async_set("sensor.alfred_map", _MAP)
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 27, "name": "KITCHEN"}]})
    RoomMapManager(manager).discover_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    first = get_setup_status(hass)["vacuums"][0]["reconciliation"]
    assert first is not None

    # Segments change AGAIN -- a re-probe would report a different new_id.
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 99, "name": "KITCHEN"}]})

    second = get_setup_status(hass)["vacuums"][0]["reconciliation"]
    assert second == first, "get_setup_status re-probed discovery instead of reading the cache"
