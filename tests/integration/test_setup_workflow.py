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
[SW-13] RP-039/RF-16: add_vacuum appends its registered panel url to the entry's
        teardown ledger instead of discarding the return value.
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
def _vacuum_is_added(manager):
    """Setup progress only exists for a vacuum that has been ADDED.

    Production reaches every one of these paths through
    ``workflow.add_vacuum_to_manager``, which calls ``ensure_vacuum_record`` BEFORE
    anything records a step — so ``data["vacuums"]`` always has the vacuum by then.
    These tests skipped that, recording setup progress for a vacuum the install had
    never added and Home Assistant did not have.

    NOT autouse in this module: several tests here deliberately exercise the
    UNMANAGED path (add_vacuum succeeding, import_active_map refusing), and
    pre-managing the vacuum would quietly turn those into a different test.

    That is not a state production can reach, and it is the state that let
    setup_progress["vacuum.iv"] — a truncated entity id — become a permanent record on
    a live install. The guard in ``drift._get_progress_record`` now refuses it, so the
    fixture supplies the step production would already have taken.
    """
    manager.data.setdefault("vacuums", {}).setdefault(_VAC, {"vacuum_entity_id": _VAC})
    return manager


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


async def test_add_vacuum_appends_panel_to_entry_ledger(
    hass, manager, mock_config_entry, monkeypatch
):
    """[SW-13] RP-039/RF-16: add_vacuum's panel registration now appends the
    registered url to the entry's teardown ledger
    (hass.data[DOMAIN][f"_panels_{entry_id}"]) -- previously the return value was
    discarded, so a panel registered through THIS path was never tracked and
    never cleanly removed on unload."""
    from unittest.mock import AsyncMock

    mock_config_entry.add_to_hass(hass)
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    monkeypatch.setattr(
        "homeassistant.components.panel_custom.async_register_panel", AsyncMock()
    )

    result = await add_vacuum(hass, _VAC)
    assert result["status"] == "success"

    ledger = hass.data[DOMAIN].get(f"_panels_{mock_config_entry.entry_id}", [])
    assert "eufy-vacuum-alfred" in ledger


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


async def test_import_active_map_service_response(hass, manager, _no_panel):
    """[SW-9b] A service-response brand (Roborock get_maps): import_active_map
    refreshes the get_maps source first, discovers rooms, and creates the map
    bucket — including Roborock responses whose map name is blank while the HA
    active-map select reports a synthetic name such as "Map 0"."""
    from homeassistant.core import SupportsResponse

    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_map": "select.alfred_selected_map"},
        "discovery": {
            "source": "service_response",
            "maps_service": {"domain": "roborock", "service": "get_maps"},
            "maps_rooms_key": "rooms", "map_name_key": "name",
            "room_id_key": "segment_id", "room_name_key": "name",
        },
    })

    async def _get_maps(call):
        return {_VAC: {"maps": [{"flag": 0, "name": "",
                                 "rooms": {"16": "KITCHEN", "17": "Dining Room"}}]}}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY,
    )
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("select.alfred_selected_map", "Map 0")
    await add_vacuum(hass, _VAC)

    result = await import_active_map(hass, _VAC)

    assert result["status"] == "success"
    assert result["data"]["room_count"] == 2
    assert result["data"]["map_id"] == "Map 0"
    rooms = manager.data["maps"][_VAC]["Map 0"]["rooms"]
    assert {r["name"] for r in rooms.values()} == {"KITCHEN", "Dining Room"}


async def test_import_active_map_without_map_selector_entity(hass, manager, _no_panel):
    """[SW-9c] ISSUE #46 — a single-map Roborock whose map-selector entity was
    never created still imports.

    HA 2026.7 (core#173282) changed how the core Roborock integration decides
    which entities to create; on loryanstrant's Q5 `select.<vac>_selected_map`
    is not created at all. `entities.active_map` is a NAMING declaration, so the
    adapter still names an entity that does not exist, every branch of
    get_active_map_id returns None, and import refused at "no map detected"
    while the device's 12 rooms decoded perfectly.

    Two things had to change together. The refresh that populates the get_maps
    cache used to run BELOW the map-id gate, so the cache that identifies the
    map was filled only after the check that needs it — the fallback could never
    be reached. And the resolver had no single-map inference for
    service-response brands (the existing implicit path is attribute-only).

    NOTE the select is never registered here: `hass.states.async_set` for it is
    deliberately absent, which is exactly the Q5's state.
    """
    from homeassistant.core import SupportsResponse

    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        # declared, as the adapter always does — but never created by HA
        "entities": {"active_map": "select.alfred_selected_map"},
        "discovery": {
            "source": "service_response",
            "maps_service": {"domain": "roborock", "service": "get_maps"},
            "maps_rooms_key": "rooms", "map_name_key": "name",
            "room_id_key": "segment_id", "room_name_key": "name",
        },
    })

    async def _get_maps(call):
        return {_VAC: {"maps": [{"flag": 0, "name": "Upstairs",
                                 "rooms": {"16": "KITCHEN", "17": "Dining Room"}}]}}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY,
    )
    hass.states.async_set(_VAC, "docked")
    await add_vacuum(hass, _VAC)

    result = await import_active_map(hass, _VAC)

    assert result["status"] == "success", result["message"]
    assert result["data"]["map_id"] == "Upstairs"
    assert result["data"]["room_count"] == 2
    rooms = manager.data["maps"][_VAC]["Upstairs"]["rooms"]
    assert {r["name"] for r in rooms.values()} == {"KITCHEN", "Dining Room"}


async def test_import_refuses_when_several_maps_and_no_selector(hass, manager, _no_panel):
    """[SW-9c] The other side of #46: inference is for ONE map only.

    With two maps and no selector, the selector genuinely carried information we
    no longer have. Picking one would serve one map's rooms under another's id —
    the bug RP-019/ID-2 guards. It must refuse, and the refusal must NOT tell a
    Roborock owner to go and check the Eufy app.
    """
    from homeassistant.core import SupportsResponse

    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code", "brand": "Roborock",
        "entities": {"active_map": "select.alfred_selected_map"},
        "discovery": {
            "source": "service_response",
            "maps_service": {"domain": "roborock", "service": "get_maps"},
            "maps_rooms_key": "rooms", "map_name_key": "name",
            "room_id_key": "segment_id", "room_name_key": "name",
        },
    })

    async def _get_maps(call):
        return {_VAC: {"maps": [
            {"flag": 0, "name": "Upstairs", "rooms": {"16": "KITCHEN"}},
            {"flag": 1, "name": "Downstairs", "rooms": {"21": "Den"}},
        ]}}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY,
    )
    hass.states.async_set(_VAC, "docked")
    await add_vacuum(hass, _VAC)

    result = await import_active_map(hass, _VAC)

    assert result["status"] == "blocked"
    assert "Eufy" not in result["message"], (
        "the refusal must be brand-aware — issue #46's reporter is a Roborock owner"
    )
    # and it carries the refresh outcome so a support capture can tell the
    # causes apart instead of guessing from one generic string
    assert "room_source_refresh" in result["data"]


async def test_import_says_unsupported_without_asking_for_a_bug_report(
    hass, manager, _no_panel
):
    """[SW-9d] ISSUE #55: a device HA refuses to answer for is not a fault.

    The reporter's Roborock Q7 M5 is a B01-protocol device. Home Assistant routes it
    to `RoborockQ7Vacuum`, whose `get_maps()` raises ServiceNotSupported
    unconditionally. We folded that into `service_call_failed`, so he was told the
    call "failed" and asked to "report it with diagnostics" — and he did, correctly.

    The message must now say the truth and explicitly NOT ask for a report, because
    there is nothing to receive and nothing he can fix.

    `manager` is unused in the body and pylint says so; it is LOAD-BEARING anyway —
    dropped, add_vacuum has no manager to register against and the result comes back
    "error" instead of "blocked", so the assertions below never reach the message.
    Checked by removing it, not assumed.
    """
    from homeassistant.core import SupportsResponse
    from homeassistant.exceptions import ServiceNotSupported

    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code", "brand": "Roborock",
        "entities": {"active_map": "select.alfred_selected_map"},
        "discovery": {
            "source": "service_response",
            "maps_service": {"domain": "roborock", "service": "get_maps"},
            "maps_rooms_key": "rooms", "map_name_key": "name",
            "room_id_key": "segment_id", "room_name_key": "name",
        },
    })

    async def _get_maps(call):
        raise ServiceNotSupported("roborock", "get_maps", _VAC)

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY,
    )
    hass.states.async_set(_VAC, "docked")
    await add_vacuum(hass, _VAC)

    result = await import_active_map(hass, _VAC)
    message = result["message"]

    assert result["status"] == "blocked"
    low = message.lower()
    # Not the WORD "report" — the message says "no need to report this" on purpose.
    # What must be gone is the ASK, which is the sentence that produced issue #55.
    assert "please report" not in low and "report it with diagnostics" not in low, (
        "issue #55 IS this sentence: a permanent, correctly-reported 'not supported' "
        f"must not ask the user for a bug report. Got: {message!r}"
    )
    assert "no need to report" in low, (
        "saying nothing about reporting leaves the user to guess; the whole defect was "
        f"an unclear next step. Got: {message!r}"
    )
    assert "failed" not in low, (
        f"nothing failed — HA answered, and the answer was no. Got: {message!r}"
    )
    assert "Roborock" in message, (
        "the cause is the BRAND integration's coverage, so name it — a user cannot "
        "act on 'the integration' when they run several"
    )
    assert "Eufy" not in message, "issue #46: never a brand the owner does not own"


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
    """[SW-12] NAMED map + two protection reasons → high → typed confirm enforced.

    A high map only demands a TYPED token when it has a real (locale-invariant)
    stored name; an unnamed high map drops to a one-click confirm instead.
    """
    setup_map(manager, _VAC, "swdel12", count=2)
    manager.data["maps"][_VAC]["swdel12"].setdefault("metadata", {})["display_name"] = "Garage"
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

def test_record_step_completed(_vacuum_is_added, manager):
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


def test_force_remove_room(_vacuum_is_added, manager):
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
