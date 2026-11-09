"""Integration tests for services/errors.py + services/setup.py handlers.

Registered via the domain async_register_services (manager_with_services).

Coverage targets
----------------
[SVE-1] acknowledge_error: no tracker → tracker_not_loaded; with tracker → acked.
[SVE-2] get_recent_errors: no tracker → []; with tracker → errors list.
[SVS-1] setup_get_status returns a status dict.
[SVS-2] setup_get_map_rooms returns the managed room list.
[SVS-3] setup_save_rooms saves discovered rooms.
[SVS-4] setup_add_vacuum records the vacuum + stamps the setup step.
[SVS-5] setup_delete_map removes a map given a confirmation token.
[SVS-6] setup_reject_rooms strips rooms + reports the result.
[SVS-7] setup_force_remove_room bumps the missing-pass counter.
[SVS-8] setup_import_active_map discovers + saves the active map.
[SVS-9] setup_set_panel_title stores/clears the sidebar title + surfaces it; an
        unmanaged vacuum errors.
[SVS-10] setup_set_map_camera stores/clears the per-vacuum live-map image/camera
        entity override + surfaces it in setup status; an unmanaged vacuum errors.
[SVS-9b] RP-039/RF-16: setup_set_panel_title appends its registered panel url to
        the entry's teardown ledger instead of discarding the return value.
"""

from __future__ import annotations

import json

from unittest.mock import MagicMock, patch

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import (
    DATA_ERROR_TRACKER,
    DOMAIN,
    ENTITY_OVERRIDES_KEY,
    SERVICE_ACKNOWLEDGE_ERROR,
    SERVICE_GET_RECENT_ERRORS,
    SERVICE_SET_ENTITY_OVERRIDE,
    SERVICE_SETUP_ADD_VACUUM,
    SERVICE_SETUP_REPAIR_RENAME,
    SERVICE_SETUP_UNREJECT_ROOMS,
    SERVICE_SETUP_DELETE_MAP,
    SERVICE_SETUP_FORCE_REMOVE_ROOM,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_GET_STATUS,
    SERVICE_SETUP_IMPORT_MAP,
    SERVICE_SETUP_REJECT_ROOMS,
    SERVICE_SETUP_SAVE_ROOMS,
    SERVICE_SETUP_SET_MAP_CAMERA,
    SERVICE_SETUP_SET_PANEL_TITLE,
)
from .conftest import seed_discovery, make_rooms, setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

async def test_acknowledge_error(hass, manager_with_services):
    """[SVE-1]"""
    # no tracker loaded
    result = await _call(hass, SERVICE_ACKNOWLEDGE_ERROR, {"vacuum_entity_id": _VAC})
    assert result["acknowledged"] is False and result["reason"] == "tracker_not_loaded"
    # tracker present
    tracker = MagicMock()
    tracker.acknowledge.return_value = True
    hass.data[DOMAIN][DATA_ERROR_TRACKER] = tracker
    result = await _call(hass, SERVICE_ACKNOWLEDGE_ERROR,
                         {"vacuum_entity_id": _VAC, "scope": "both"})
    assert result["acknowledged"] is True
    tracker.acknowledge.assert_called_once_with(_VAC, scope="both")


async def test_get_recent_errors(hass, manager_with_services, managed_vacuum):
    """[SVE-2]"""
    result = await _call(hass, SERVICE_GET_RECENT_ERRORS, {"vacuum_entity_id": _VAC})
    assert result["errors"] == [] and result["reason"] == "tracker_not_loaded"

    tracker = MagicMock()
    tracker.recent_errors.return_value = [{"message": "E1"}, {"message": "E2"}]
    hass.data[DOMAIN][DATA_ERROR_TRACKER] = tracker
    result = await _call(hass, SERVICE_GET_RECENT_ERRORS,
                         {"vacuum_entity_id": _VAC, "limit": 5})
    assert result["count"] == 2
    tracker.recent_errors.assert_called_once_with(_VAC, limit=5)


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

async def test_setup_get_status(hass, manager_with_services):
    """[SVS-1]"""
    result = await _call(hass, SERVICE_SETUP_GET_STATUS, {})
    assert isinstance(result, dict)


async def test_setup_get_map_rooms(hass, manager_with_services):
    """[SVS-2]"""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await _call(hass, SERVICE_SETUP_GET_MAP_ROOMS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert len(result["rooms"]) == 2
    assert result["rooms"][0]["room_id"] == 1


async def test_setup_save_rooms(hass, manager_with_services):
    """[SVS-3]"""
    seed_discovery(manager_with_services, _VAC, _MAP, make_rooms(_MAP, 3))
    result = await _call(hass, SERVICE_SETUP_SAVE_ROOMS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert result["status"] == "success"
    assert result["room_count"] == 3


async def test_setup_save_rooms_refuses_empty_replacement(hass, manager_with_services):
    """[SVS-3b] RP-005/RF-02. A discovery glitch that would wipe a non-empty
    stored room map is refused -- the step is NOT stamped complete and the
    stored rooms are untouched."""
    seed_discovery(manager_with_services, _VAC, _MAP, make_rooms(_MAP, 3))
    await _call(hass, SERVICE_SETUP_SAVE_ROOMS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    stored_before = dict(manager_with_services.data["maps"][_VAC][_MAP]["rooms"])
    assert stored_before

    seed_discovery(manager_with_services, _VAC, _MAP, [])
    result = await _call(hass, SERVICE_SETUP_SAVE_ROOMS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})

    assert result["status"] == "error"
    assert result["reason"] == "empty_replacement_refused"
    assert manager_with_services.data["maps"][_VAC][_MAP]["rooms"] == stored_before


def test_setup_save_rooms_schema_rejects_null_enabled_room_ids():
    """[SVS-3c] Same enabled_room_ids null/[] rejection as services/rooms.py's
    schema, wired independently here (setup panel path)."""
    from custom_components.eufy_vacuum.services.setup import _SETUP_SAVE_ROOMS_SCHEMA
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        _SETUP_SAVE_ROOMS_SCHEMA(
            {"vacuum_entity_id": _VAC, "map_id": _MAP, "enabled_room_ids": None}
        )
    with pytest.raises(vol.Invalid):
        _SETUP_SAVE_ROOMS_SCHEMA(
            {"vacuum_entity_id": _VAC, "map_id": _MAP, "enabled_room_ids": []}
        )


# ---------------------------------------------------------------------------
# setup write-path service handlers (add / delete / reject / force-remove)
# ---------------------------------------------------------------------------

@pytest.fixture
def _no_panel(monkeypatch):
    async def _fake(*a, **k):
        return None
    import homeassistant.components.panel_custom as panel_custom
    monkeypatch.setattr(panel_custom, "async_register_panel", _fake)


async def test_setup_add_vacuum(hass, manager_with_services, _no_panel):
    """[SVS-4] add_vacuum service records the vacuum + stamps the setup step."""
    hass.states.async_set(_VAC, "docked")
    result = await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": _VAC})
    assert result["status"] == "success"
    assert _VAC in manager_with_services.data.get("vacuums", {})
    steps = manager_with_services.data["setup_progress"][_VAC]["completed_steps"]
    assert "add_vacuum" in steps


def _capture_reloads(hass, monkeypatch) -> list[str]:
    """Add a real DOMAIN config entry + mock only async_reload to record calls.

    (Mocking async_entries itself breaks HA's internal cleanup, which calls it
    with other signatures — so use a MockConfigEntry and leave async_entries real.)
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    MockConfigEntry(domain=DOMAIN, entry_id="entry1").add_to_hass(hass)

    reload_calls: list[str] = []

    async def _reload(entry_id):
        reload_calls.append(entry_id)

    monkeypatch.setattr(hass.config_entries, "async_reload", _reload)
    return reload_calls


async def test_setup_add_vacuum_reloads_to_wire_new(
    hass, manager_with_services, _no_panel, monkeypatch
):
    """[SVS-4b] A newly-added vacuum schedules a config-entry reload — the only
    path that wires its adapter / entities / listeners / panel (async_setup_entry).
    Without it the second vacuum is half-wired (recorded but not functional)."""
    reload_calls = _capture_reloads(hass, monkeypatch)
    hass.states.async_set(_VAC, "docked")

    result = await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": _VAC})
    await hass.async_block_till_done()  # run the scheduled reload task

    assert result["status"] == "success"
    assert reload_calls == ["entry1"]


async def test_setup_add_vacuum_already_managed_no_reload(
    hass, manager_with_services, _no_panel, monkeypatch
):
    """[SVS-4b] Re-adding an already-managed vacuum does NOT reload (no churn)."""
    reload_calls = _capture_reloads(hass, monkeypatch)
    hass.states.async_set(_VAC, "docked")

    await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": _VAC})
    await hass.async_block_till_done()
    reload_calls.clear()

    result = await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": _VAC})
    await hass.async_block_till_done()

    assert result["status"] == "already_done"
    assert reload_calls == []


async def test_setup_import_active_map(hass, manager_with_services, _no_panel):
    """[SVS-8] import_active_map service discovers + saves the active map."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_active_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity", "room_list_attribute": "segments",
            "room_id_key": "id", "room_name_key": "name"},
    })
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Bath"}]})
    await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": _VAC})
    hass.states.async_set("sensor.alfred_active_map", "svsimp")
    result = await _call(hass, SERVICE_SETUP_IMPORT_MAP, {"vacuum_entity_id": _VAC})
    assert result["status"] == "success"
    assert result["data"]["room_count"] == 2
    steps = manager_with_services.data["setup_progress"][_VAC]["completed_steps"]
    assert "import_active_map" in steps


async def test_setup_import_active_map_blocked_does_not_complete_step(
    hass, manager_with_services
):
    """[SVS-8b] a blocked import leaves the setup step incomplete."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_active_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity", "room_list_attribute": "segments",
            "room_id_key": "id", "room_name_key": "name"},
    })
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    hass.states.async_set(_VAC, "docked", {"segments": []})
    hass.states.async_set("sensor.alfred_active_map", "empty")

    result = await _call(hass, SERVICE_SETUP_IMPORT_MAP, {"vacuum_entity_id": _VAC})

    assert result["status"] == "blocked"
    steps = (
        manager_with_services.data.get("setup_progress", {})
        .get(_VAC, {})
        .get("completed_steps", [])
    )
    assert "import_active_map" not in steps


async def test_setup_delete_map(hass, manager_with_services):
    """[SVS-5] delete_map service removes a map given a confirmation token."""
    setup_map(manager_with_services, _VAC, "svsdel", count=2)
    result = await _call(hass, SERVICE_SETUP_DELETE_MAP,
                         {"vacuum_entity_id": _VAC, "map_id": "svsdel",
                          "confirmation_token": "yes"})
    assert result["status"] == "success"
    assert "svsdel" not in manager_with_services.data.get("maps", {}).get(_VAC, {})


async def test_setup_reject_rooms(hass, manager_with_services):
    """[SVS-6] reject_rooms service strips rooms + reports the result."""
    setup_map(manager_with_services, _VAC, "svsrej", count=3)
    result = await _call(hass, SERVICE_SETUP_REJECT_ROOMS,
                         {"vacuum_entity_id": _VAC, "room_ids": [1, 2]})
    assert result["status"] == "success"
    assert set(result["rejected"]) == {1, 2}


async def test_setup_force_remove_room(hass, manager_with_services):
    """[SVS-7] force_remove_room service bumps the missing-pass counter."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await _call(hass, SERVICE_SETUP_FORCE_REMOVE_ROOM,
                         {"vacuum_entity_id": _VAC, "room_id": 7})
    assert result["status"] == "success"
    assert result["room_id"] == 7


async def test_setup_set_panel_title(hass, manager_with_services, _no_panel):
    """[SVS-9] set_panel_title stores a (trimmed) custom title on the record,
    surfaces it in setup status, and a blank title reverts to the default."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    result = await _call(hass, SERVICE_SETUP_SET_PANEL_TITLE,
                         {"vacuum_entity_id": _VAC, "title": "  Ivy  "})
    assert result["status"] == "success"
    assert result["panel_title"] == "Ivy"  # trimmed
    assert manager_with_services.data["vacuums"][_VAC]["panel_title"] == "Ivy"

    status = await _call(hass, SERVICE_SETUP_GET_STATUS, {})
    entry = next(v for v in status["vacuums"] if v["vacuum_entity_id"] == _VAC)
    assert entry["panel_title"] == "Ivy"

    # Blank -> revert to the default + drop the stored key.
    result = await _call(hass, SERVICE_SETUP_SET_PANEL_TITLE,
                         {"vacuum_entity_id": _VAC, "title": "   "})
    assert result["status"] == "success"
    assert result["panel_title"] == "Vacuum Agent"
    assert "panel_title" not in manager_with_services.data["vacuums"][_VAC]


async def test_setup_set_panel_title_not_managed(hass, manager_with_services, _no_panel):
    """[SVS-9] renaming an unmanaged vacuum errors and creates no record."""
    result = await _call(hass, SERVICE_SETUP_SET_PANEL_TITLE,
                         {"vacuum_entity_id": "vacuum.ghost", "title": "X"})
    assert result["status"] == "error"


async def test_setup_set_panel_title_appends_panel_to_entry_ledger(
    hass, manager_with_services, mock_config_entry, _no_panel
):
    """[SVS-9b] RP-039/RF-16: same orphan bug as add_vacuum -- setup_set_panel_title
    discarded async_register_vacuum_panel's return value and never touched the
    entry's panel-teardown ledger, so a panel registered/renamed through THIS path
    was never tracked and never cleanly removed on unload."""
    mock_config_entry.add_to_hass(hass)
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    result = await _call(hass, SERVICE_SETUP_SET_PANEL_TITLE,
                         {"vacuum_entity_id": _VAC, "title": "Ivy"})
    assert result["status"] == "success"

    ledger = hass.data[DOMAIN].get(f"_panels_{mock_config_entry.entry_id}", [])
    assert "eufy-vacuum-alfred" in ledger
    assert "vacuum.ghost" not in manager_with_services.data.get("vacuums", {})


async def test_setup_set_map_camera(hass, manager_with_services, _no_panel):
    """[SVS-10] set_map_camera stores the (trimmed) live-map image/camera entity
    override on the record, surfaces it in setup status, and a blank value clears it."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    result = await _call(hass, SERVICE_SETUP_SET_MAP_CAMERA,
                         {"vacuum_entity_id": _VAC, "entity_id": "  camera.alfred_map  "})
    assert result["status"] == "success"
    assert result["live_map_image_entity"] == "camera.alfred_map"  # trimmed
    assert (
        manager_with_services.data["vacuums"][_VAC]["live_map_image_entity"]
        == "camera.alfred_map"
    )

    status = await _call(hass, SERVICE_SETUP_GET_STATUS, {})
    entry = next(v for v in status["vacuums"] if v["vacuum_entity_id"] == _VAC)
    assert entry["live_map_image_entity"] == "camera.alfred_map"

    # Blank -> clear the override + drop the stored key (falls back to the pattern).
    result = await _call(hass, SERVICE_SETUP_SET_MAP_CAMERA,
                         {"vacuum_entity_id": _VAC, "entity_id": "   "})
    assert result["status"] == "success"
    assert result["live_map_image_entity"] is None
    assert "live_map_image_entity" not in manager_with_services.data["vacuums"][_VAC]


async def test_setup_set_map_camera_not_managed(hass, manager_with_services, _no_panel):
    """[SVS-10] setting the camera on an unmanaged vacuum errors and creates no record."""
    result = await _call(hass, SERVICE_SETUP_SET_MAP_CAMERA,
                         {"vacuum_entity_id": "vacuum.ghost", "entity_id": "camera.x"})
    assert result["status"] == "error"
    assert "vacuum.ghost" not in manager_with_services.data.get("vacuums", {})


# ---------------------------------------------------------------------------
# set_entity_override — the manual entity-role override (shipped 2.1.0)
#
# The panel's write path for const.ENTITY_OVERRIDES_KEY: point a role at an entity
# by hand when auto-resolution picks wrong. The whole handler was uncovered.
#
# It is not one of the `setup_*` onboarding services despite living here — the
# module docstring lists twelve and does not mention it.
# ---------------------------------------------------------------------------


async def test_set_entity_override_stores_and_reloads(
    hass, manager_with_services, _no_panel, monkeypatch
):
    """[SVS-EO-1] the override is persisted AND a config-entry reload is scheduled.

    The reload is not incidental: the override is consumed at adapter-registration
    time, so without it the user saves a choice and sees nothing change — the silent
    failure this feature exists to remove.
    """
    reload_calls = _capture_reloads(hass, monkeypatch)

    result = await _call(hass, SERVICE_SET_ENTITY_OVERRIDE, {
        "vacuum_entity_id": _VAC, "role": "filter", "entity_id": "sensor.my_filter"})
    await hass.async_block_till_done()

    assert result["status"] == "success"
    assert result["role"] == "filter"
    store = manager_with_services.data[ENTITY_OVERRIDES_KEY]
    assert store[_VAC]["filter"] == "sensor.my_filter"
    assert reload_calls == ["entry1"]


async def test_set_entity_override_blank_entity_clears_only_that_role(
    hass, manager_with_services, _no_panel, monkeypatch
):
    """[SVS-EO-2] a blank entity_id CLEARS one role and leaves the others alone."""
    _capture_reloads(hass, monkeypatch)
    for role, ent in (("filter", "sensor.f"), ("brush", "sensor.b")):
        await _call(hass, SERVICE_SET_ENTITY_OVERRIDE, {
            "vacuum_entity_id": _VAC, "role": role, "entity_id": ent})

    await _call(hass, SERVICE_SET_ENTITY_OVERRIDE, {
        "vacuum_entity_id": _VAC, "role": "filter", "entity_id": "   "})
    await hass.async_block_till_done()

    per_vacuum = manager_with_services.data[ENTITY_OVERRIDES_KEY][_VAC]
    assert "filter" not in per_vacuum, "clearing one role must not leave it behind"
    assert per_vacuum["brush"] == "sensor.b", "clearing one role wiped an unrelated one"


async def test_set_entity_override_clearing_the_last_role_prunes_the_vacuum(
    hass, manager_with_services, _no_panel, monkeypatch
):
    """[SVS-EO-3] the per-vacuum dict is removed once its final role is cleared.

    Without the prune the store keeps an empty `{vacuum: {}}` husk forever. Nothing
    reads it, which is exactly why nothing would notice it accumulating.
    """
    _capture_reloads(hass, monkeypatch)
    await _call(hass, SERVICE_SET_ENTITY_OVERRIDE, {
        "vacuum_entity_id": _VAC, "role": "filter", "entity_id": "sensor.f"})

    await _call(hass, SERVICE_SET_ENTITY_OVERRIDE, {
        "vacuum_entity_id": _VAC, "role": "filter", "entity_id": ""})
    await hass.async_block_till_done()

    assert _VAC not in manager_with_services.data[ENTITY_OVERRIDES_KEY]


async def test_set_entity_override_blank_role_errors_and_writes_nothing(
    hass, manager_with_services, _no_panel, monkeypatch
):
    """[SVS-EO-4] a whitespace-only role is refused BEFORE anything is written."""
    _capture_reloads(hass, monkeypatch)

    result = await _call(hass, SERVICE_SET_ENTITY_OVERRIDE, {
        "vacuum_entity_id": _VAC, "role": "   ", "entity_id": "sensor.x"})

    assert result["status"] == "error"
    assert result["reason"] == "missing_role"
    assert _VAC not in manager_with_services.data.get(ENTITY_OVERRIDES_KEY, {})


# ---------------------------------------------------------------------------
# [SVS-11] - [SVS-18]  services/setup.py was the lowest-covered file in the
# package at 83.74%. These close every uncovered unit OUTSIDE the standing
# `manager is None` ruling (17-services.md) -- 30 of its 47.
#
# ⚠ THE RULING'S LINE NUMBERS ARE ENTIRELY STALE and that is worth knowing before
# reading it: all SIXTEEN lines it names (64, 114, 187, 190, 237, 264, 303, 335-338,
# 344-345, 356, 375, 425) are COVERED today. Nine uncovered lines and eight arms of
# the same SHAPE remain, at completely different numbers. Its shape is what still
# applies; its list is not. Those 17 units are deliberately untouched here.
# ---------------------------------------------------------------------------


def test_svs11_a_non_dict_workflow_result_advances_the_step(hass, manager_with_services):
    """[SVS-11] `_completed_step_result` treats a non-dict as COMPLETED.

    The setup panel renders a step as done from this predicate. A workflow that
    returns something other than a status dict -- a bool, or None from an older
    helper -- is taken as success, so the step advances rather than wedging the panel
    on a step the user cannot clear.

    The dict arm is the one every other test drives; this is the fallback, and both
    halves are asserted together so "True" cannot come from the dict path by accident.

    RED: flip the fallback to False and a non-dict result stops advancing the step.
    """
    from custom_components.eufy_vacuum.services.setup import _completed_step_result

    assert _completed_step_result(True) is True
    assert _completed_step_result(None) is True
    assert _completed_step_result("done") is True
    # ...and the dict arm still discriminates, or the assertions above prove nothing.
    assert _completed_step_result({"status": "success"}) is True
    assert _completed_step_result({"status": "already_done"}) is True
    assert _completed_step_result({"status": "blocked"}) is False


def test_svs12_the_enabled_room_ids_validator_accepts_and_coerces(hass):
    """[SVS-12] The validator's ACCEPT path, which no test had driven.

    Both of its refusals were covered and its success return was not, so nothing
    asserted that a valid selection survives validation -- or that it comes out as
    INTS. The ids are used as dict keys and compared against stored room ids; a
    string `"3"` would silently miss every one of them.

    ⚠ ITS DOCSTRING CALLS IT THE SAME VALIDATOR AS `services/rooms.py`'s, so the
    coercion is asserted here and the twin is asserted to agree. A replica whose
    copies drift is the failure this repo keeps finding; comparing the two outputs
    is cheaper than trusting the comment.

    RED: drop the `vol.Coerce(int)` and the ids come back as strings.
    """
    import voluptuous as vol

    from custom_components.eufy_vacuum.services.setup import (
        _enabled_room_ids_validator,
    )

    assert _enabled_room_ids_validator([3, "7", 11]) == [3, 7, 11]
    assert _enabled_room_ids_validator("5") == [5], "a scalar is accepted as one id"

    # The two refusals, so the accept path above is not the only thing measured.
    with pytest.raises(vol.Invalid):
        _enabled_room_ids_validator(None)
    with pytest.raises(vol.Invalid):
        _enabled_room_ids_validator([])

    # The replica its docstring names must agree on all three.
    from custom_components.eufy_vacuum.services.rooms import (
        _enabled_room_ids_validator as twin,
    )
    for value in ([3, "7", 11], "5", ["2"]):
        assert _enabled_room_ids_validator(value) == twin(value), (
            f"the two copies of this validator disagree on {value!r}"
        )


async def test_svs13_a_corrupt_pending_rename_list_is_repaired(hass, manager_with_services):
    """[SVS-13] `pending_entity_renames` read back from storage as a non-list.

    The repair handler appends to that list. It comes back from `.storage`, so a dict
    (an older shape) or a string is outside data -- and without the guard the append
    raises `AttributeError` out of a service the user invoked to FIX a rename, which
    is the worst moment for it.

    The replacement must also be STORED, not just local: the assertion reads the
    manager's own data back, because `pending = []` alone would repair a local name
    and leave the corrupt value on disk.

    RED: drop the `isinstance(pending, list)` guard and this raises.
    """
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    manager_with_services.data["pending_entity_renames"] = {"not": "a list"}

    result = await _call(hass, SERVICE_SETUP_REPAIR_RENAME, {
        "old_entity_id": _VAC,
        "new_entity_id": "vacuum.alfred_renamed",
    })

    assert isinstance(result, dict)
    stored = manager_with_services.data["pending_entity_renames"]
    assert isinstance(stored, list), (
        f"the corrupt value survived the repair: {stored!r}"
    )


async def test_svs14_an_explicit_map_id_is_used_verbatim(hass, manager_with_services):
    """[SVS-14] `_rejection_map_id`: an explicitly supplied map_id wins.

    A4-SETUP-6 made rejections map-scoped because room ids are reissued per map. The
    card does not send `map_id` today, so the resolver path is what the suite
    exercised and the explicit path -- the one an automation or a future card uses --
    was never driven.

    THE TWO MAPS ARE SET UP WITH THE SAME ROOM IDS, which is the whole point: a
    rejection that ignored the explicit id and resolved the ACTIVE map instead would
    reject the right NUMBERS on the wrong map, and a test using distinct ids could
    not tell the difference.

    RED: ignore `call.data["map_id"]` and the rejection lands on the resolver's map.
    """
    setup_map(manager_with_services, _VAC, "floor1", count=3)
    setup_map(manager_with_services, _VAC, "floor2", count=3)
    manager_with_services.resolve_active_map_id = lambda vid: "floor1"

    result = await _call(hass, SERVICE_SETUP_REJECT_ROOMS, {
        "vacuum_entity_id": _VAC, "room_ids": [2], "map_id": "floor2",
    })

    assert result["status"] == "success"
    rejected = manager_with_services.data.get("setup_progress", {}).get(_VAC, {})
    assert "floor2" in json.dumps(rejected), (
        f"the rejection did not land on the explicitly named map: {rejected}"
    )


async def test_svs15_no_active_map_resolver_falls_back_to_every_map(
    hass, manager_with_services, monkeypatch
):
    """[SVS-15] `_rejection_map_id` returns None when the manager cannot say.

    The source is explicit that this is the legacy every-map rejection and that it is
    "worse, but it is the pre-existing behaviour and never silently no-ops the
    rejection". So the claim is not "None" in the abstract -- it is that the rejection
    STILL HAPPENS without a resolver, rather than being dropped.

    RED: make the missing resolver raise or return early without rejecting, and the
    rejection vanishes.
    """
    setup_map(manager_with_services, _VAC, "svsnores", count=2)
    # ⚠ `EufyVacuumManager` DOES define `resolve_active_map_id` (core/manager.py), so
    # this arm is not reachable by using the real manager as-is -- which is exactly
    # why line 330 was uncovered. The guard is written `getattr(manager, ..., None)`
    # with `manager: Any`, so what it defends against is a manager object that does
    # not carry the method: an older stored manager, or a duck-typed one from an
    # external pyscript/AppDaemon caller. Shadowing the class method on the instance
    # is the faithful stand-in for that.
    #
    # Two measurements got me here, both worth leaving: `delattr(instance, ...)`
    # raises AttributeError for a CLASS attribute, and `hasattr` then still answers
    # True -- so a draft that tried to delete it concluded the method was absent when
    # it is always present.
    assert callable(getattr(manager_with_services, "resolve_active_map_id", None)), (
        "precondition: the real manager carries this method, which is what makes "
        "the no-resolver arm unreachable without shadowing it"
    )
    monkeypatch.setattr(manager_with_services, "resolve_active_map_id", None)

    result = await _call(hass, SERVICE_SETUP_REJECT_ROOMS, {
        "vacuum_entity_id": _VAC, "room_ids": [1],
    })

    assert result["status"] == "success"
    assert 1 in set(result["rejected"]), (
        "without a map resolver the rejection was dropped instead of applying to "
        "every map"
    )


async def test_svs16_a_blocked_add_vacuum_does_not_stamp_the_step(
    hass, manager_with_services, _no_panel
):
    """[SVS-16] The arm where the workflow did NOT complete.

    `setup_add_vacuum` stamps the step only when the result is a completed one.
    "blocked" means the user still has an action to take, so stamping it would render
    the panel step as done while the user is still stuck on it -- the source comment
    says exactly that.

    THE CONTROL IS A SECOND CALL THAT DOES SUCCEED. "no step recorded" is also what a
    stamp that never works produces, so the same vacuum is driven through a
    successful add afterwards and the step must appear.

    RED: stamp unconditionally and the blocked call records the step.
    """
    # THE REAL PRODUCTION PATH, not a patched one. `setup.workflow.add_vacuum`
    # checks the HA state machine BEFORE the already-managed check, so a vacuum with
    # a STORED record but no live state returns "blocked". (`_add_vacuum` is a lazy
    # import bound into a closure at registration, so patching the module after the
    # fixture registered the services would not take effect anyway -- measured.)
    #
    # ⚠ THE STORED RECORD IS WHAT MAKES THIS ABLE TO FAIL, and a first draft without
    # it was vacuous. `record_step_completed` goes through
    # `drift._get_progress_record`, which refuses to create a record for a vacuum the
    # install does not have -- so for a never-seen id NOTHING stamps the step whatever
    # the guard does, and the assertion held for the wrong reason. With the record in
    # place, unconditional stamping genuinely appends the step.
    offline = "vacuum.stored_but_offline"
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=offline)
    assert hass.states.get(offline) is None, "precondition: no live state"

    result = await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": offline})
    assert result["status"] == "blocked", (
        f"expected the absent-entity arm, got {result.get('status')!r}"
    )
    steps = (manager_with_services.data.get("setup_progress", {})
             .get(offline, {}).get("completed_steps", []))
    assert "add_vacuum" not in steps, (
        f"a blocked add stamped the step as done: {steps}"
    )

    # CONTROL: give it a state and the SAME call returns already_done -- a COMPLETED
    # result -- which must stamp the step.
    hass.states.async_set(offline, "docked")
    result = await _call(hass, SERVICE_SETUP_ADD_VACUUM, {"vacuum_entity_id": offline})
    assert result["status"] == "already_done", (
        f"control: expected already_done, got {result.get('status')!r}"
    )
    steps = (manager_with_services.data.get("setup_progress", {})
             .get(offline, {}).get("completed_steps", []))
    assert "add_vacuum" in steps, (
        "control: a completed result must stamp the step, or SVS-16 passes against a "
        "stamp that never fires"
    )


async def test_svs17_an_entity_override_with_no_config_entry_skips_the_reload(
    hass, manager_with_services, _no_panel
):
    """[SVS-17] ISSUE #63's guard, on the arm where there is no entry to reload.

    Setting an override normally reloads the entry -- an override changes which entity
    a role resolves to, which can change the capability set and therefore which
    maintenance sensors exist. Before the reload it plants
    `_panel_survives_reload`, because this service is invoked FROM the panel and
    unregistering it ejects the user to their default dashboard mid-action (the
    "appears to crash (screen exit)" report).

    With no config entry there is nothing to reload and nothing to protect, so neither
    the marker nor the task may appear -- a marker left behind with no reload coming
    would make the NEXT genuine unload skip its panel teardown.

    The override itself must still be stored: the service's job is the override, and
    the reload is a side effect of it.

    RED: hoist the marker out of the `if entries:` block and it is planted with no
    reload to survive.
    """
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    assert hass.config_entries.async_entries(DOMAIN) == [], (
        "precondition: this test needs NO config entry, which is the arm under test"
    )
    hass.data.setdefault(DOMAIN, {}).pop("_panel_survives_reload", None)

    result = await _call(hass, SERVICE_SET_ENTITY_OVERRIDE, {
        "vacuum_entity_id": _VAC,
        "role": "active_map",
        "entity_id": "sensor.alfred_override",
    })

    assert result["status"] == "success"
    assert result["role"] == "active_map"
    assert "_panel_survives_reload" not in hass.data.get(DOMAIN, {}), (
        "the panel-survival marker was planted with no reload coming, which makes "
        "the next real unload skip its panel teardown"
    )
    # ENTITY_OVERRIDES_KEY is a TOP-LEVEL key in manager.data, keyed by vacuum --
    # not a field on the vacuum record. Measured; the first draft looked inside
    # data["vacuums"][vac] and raised KeyError.
    overrides = manager_with_services.data[ENTITY_OVERRIDES_KEY][_VAC]
    assert overrides["active_map"] == "sensor.alfred_override"


async def test_svs18_unreject_rooms_restores_a_rejected_room(hass, manager_with_services):
    """[SVS-18] `setup_unreject_rooms` -- the handler had NO test at all.

    Its twin `setup_reject_rooms` is covered by [SVS-6]; this is A4-SETUP-6's escape
    hatch, and the source says what it exists for: without it a rejection was one-way,
    so a room rejected by mistake -- or, before rejections were map-scoped, a REAL room
    upstairs sharing an id with a ghost downstairs -- had no route back short of
    hand-editing `.storage`.

    REJECT FIRST, THEN UNREJECT, so the test measures a round trip rather than the
    absence of a rejection that was never made. The assertion after the reject is a
    precondition, not decoration: unrejecting a room that was never rejected would
    report success too.

    RED: have the handler return without calling `_unreject_rooms`, or without saving,
    and the id stays in the rejected set.
    """
    setup_map(manager_with_services, _VAC, "svsunrej", count=3)
    manager_with_services.resolve_active_map_id = lambda vid: "svsunrej"

    rejected = await _call(hass, SERVICE_SETUP_REJECT_ROOMS,
                           {"vacuum_entity_id": _VAC, "room_ids": [2]})
    assert 2 in set(rejected["rejected"]), "precondition: the room must be rejected first"

    # ⚠ READ THE STORED SET THROUGH ITS OWN READER, not a json.dumps string search.
    # A first draft asserted `'"2"' not in json.dumps(...)` and was VACUOUS: the ids
    # are stored as INTS, so `"2"` with quotes never appears and the assertion held
    # whatever the handler did. The ablation caught it -- stubbing the handler's call
    # out entirely reddened nothing. `rejected_room_ids_for` is the module's own
    # accessor and returns `set[int]`, and it deliberately does not materialise the
    # record, so reading it cannot change what is being measured.
    from custom_components.eufy_vacuum.setup.drift import rejected_room_ids_for

    before = rejected_room_ids_for(manager_with_services, _VAC, map_id="svsunrej")
    assert 2 in before, f"precondition: 2 must be in the stored set, got {before}"

    result = await _call(hass, SERVICE_SETUP_UNREJECT_ROOMS,
                         {"vacuum_entity_id": _VAC, "room_ids": [2]})

    assert result["status"] == "success"
    after = rejected_room_ids_for(manager_with_services, _VAC, map_id="svsunrej")
    assert 2 not in after, (
        f"room 2 is still recorded as rejected after un-rejecting it: {after}"
    )


@pytest.mark.parametrize("entity,expect_stored", [
    pytest.param("  camera.upstairs  ", "camera.upstairs", id="set_trimmed"),
    pytest.param("   ", None, id="cleared"),
])
async def test_svs19_the_map_camera_override_is_per_map(
    hass, manager_with_services, _no_panel, entity, expect_stored
):
    """[SVS-19] The PER-MAP branch of `setup_set_map_camera`, the sibling [SVS-10]
    does not cover.

    [SVS-10] drives the per-vacuum override. Passing `map_id` takes a different branch
    entirely, which stores under `live_map_image_entity_by_map` so that the per-vacuum
    value "keeps meaning exactly what it meant before" -- the change was additive, and
    nothing asserted the additive half.

    ⚠ THE PER-VACUUM VALUE IS SET FIRST AND ASSERTED UNCHANGED. That is the claim: a
    per-map write that clobbered the per-vacuum fallback would break every OTHER map
    on that vacuum, and a test that only looked at the per-map dict could not see it.

    The clearing row also pins the cleanup: emptying the last per-map entry must drop
    the whole `live_map_image_entity_by_map` key rather than leave `{}` behind, since
    an empty dict is a stored value that reads as "configured" to anything checking
    for the key.

    RED: write the per-map value to `live_map_image_entity` instead and the
    per-vacuum assertion fires; skip the empty-dict cleanup and the clearing row
    leaves `{}`.
    """
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    record = manager_with_services.data["vacuums"][_VAC]
    record["live_map_image_entity"] = "camera.alfred_default"

    # Seed a per-map entry so the clearing row has something to remove.
    await _call(hass, SERVICE_SETUP_SET_MAP_CAMERA, {
        "vacuum_entity_id": _VAC, "entity_id": "camera.seed", "map_id": "floor9",
    })
    assert record["live_map_image_entity_by_map"]["floor9"] == "camera.seed"

    result = await _call(hass, SERVICE_SETUP_SET_MAP_CAMERA, {
        "vacuum_entity_id": _VAC, "entity_id": entity, "map_id": "floor9",
    })

    assert result["status"] == "success"
    assert result["map_id"] == "floor9", "the response must name the map it scoped to"

    by_map = record.get("live_map_image_entity_by_map")
    if expect_stored is None:
        assert by_map is None, (
            f"clearing the last per-map entry left the key behind: {by_map!r} -- an "
            f"empty dict is a stored value that reads as configured"
        )
    else:
        assert by_map == {"floor9": expect_stored}

    assert record["live_map_image_entity"] == "camera.alfred_default", (
        "the per-map write clobbered the per-vacuum fallback, which would break "
        "every other map on this vacuum"
    )


async def test_svs20_clearing_one_maps_camera_leaves_the_others(
    hass, manager_with_services, _no_panel
):
    """[SVS-20] The cleanup's OTHER arm: clear one map, keep the rest.

    [SVS-19]'s clearing row removes the only per-map entry, so the whole
    `live_map_image_entity_by_map` key is dropped. This is the arm where entries
    REMAIN -- and it is the one with teeth, because an over-eager cleanup that
    dropped the key whenever anything was cleared would silently delete the
    overrides for every other floor the user had configured.

    Two maps in, one cleared, and the assertion is on the SURVIVOR.

    RED: move the `record.pop(...)` out from under `if not by_map:` and floor8's
    override disappears with floor9's.
    """
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    record = manager_with_services.data["vacuums"][_VAC]

    for map_id, cam in (("floor8", "camera.eight"), ("floor9", "camera.nine")):
        await _call(hass, SERVICE_SETUP_SET_MAP_CAMERA, {
            "vacuum_entity_id": _VAC, "entity_id": cam, "map_id": map_id,
        })
    assert record["live_map_image_entity_by_map"] == {
        "floor8": "camera.eight", "floor9": "camera.nine",
    }, "precondition: both maps must be configured before one is cleared"

    result = await _call(hass, SERVICE_SETUP_SET_MAP_CAMERA, {
        "vacuum_entity_id": _VAC, "entity_id": "", "map_id": "floor9",
    })

    assert result["status"] == "success"
    assert record["live_map_image_entity_by_map"] == {"floor8": "camera.eight"}, (
        "clearing one map's camera took another map's override with it"
    )
