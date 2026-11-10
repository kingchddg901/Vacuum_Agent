"""End-to-end config-entry lifecycle for __init__.py.

Boots the whole integration through hass.config_entries.async_setup — the real
startup path that was previously untested: async_setup_entry orchestration,
adapter coordinator + manager init, code-adapter registration, service +
listener registration, platform forwarding (binary_sensor/button/switch/
number/sensor async_setup_entry + entity construction), and the unload
teardown. The frontend panel surface is patched out (no frontend component in
the test harness); everything else runs for real.

Coverage targets
----------------
[INIT-1] setup with a configured vacuum → LOADED + runtime/battery/tracker wired
         + platform entities created; unload → NOT_LOADED + state torn down.
[INIT-2] setup with no vacuum → still LOADED (fallback panel path).
[INIT-3] async_remove_entry clears persistent storage.
[INIT-4] setup with the full companion-entity stack present → capability
         detection enables mop/dock/position/maintenance features so the
         switch/number/button/sensor platforms construct those entities.
[INIT-5] boot with stored maps+rooms exercises the sensor orchestrator (room
         history + rule-status sensors built); room-update + job-finished
         callbacks fire the sync/refresh paths + auto-clear the recovered latch.
[INIT-6] adding a room then firing the room-update callback adds NEW history +
         rule-status sensors to the registry (dynamic-entity sync).
[INIT-7] the rule-status + theme refresh callbacks push observable state writes;
         saving a new theme makes the theme sensor report the new theme name.
[INIT-7b] a clean-order cache write reaches hass.states with no poll.
[INIT-7c] the clean-order listener registers after the sensor subscribes.
[INIT-8] the hourly safety-net tick refreshes room-history sensors without crash.
[INIT-9] remove_config_entry_device on the config-flow vacuum tears it down in place
         (trackers/adapter/panel/storage) + defers clearing it from the entry so
         async_setup_entry can't resurrect it; no inline reload. RP-039/RF-16: also
         tears down discovery's per-vacuum listeners + the four in-memory manager
         caches (runtime/room-history-cache-ready/-loading/map-state-source).
[INIT-9b] RP-039/RF-16: discovery.remove_vacuum's per-vacuum isolation — removing
          one vacuum's auto-discovery triggers leaves another vacuum's untouched.
[INIT-10] remove_config_entry_device on a stale/unrelated device is a safe no-op
          (no teardown, no entry clear) but still returns True so HA can drop the orphan.
[INIT-14] D2/C54: the battery-aggregates migration is actually DISPATCHED by setup,
          and its ordering holds. This harness boots with hass ALREADY RUNNING, so
          `async_at_started` fires immediately — the case where a hook registered
          before DATA_BATTERY exists would find it missing and defer forever. A
          migration that only its own unit tests ever call is dead code that passes
          every test it has.
[INIT-2b] INF-1: the fallback panel (no vacuum configured yet) registers using
          panels.py's DEFAULT_PANEL_TITLE / PANEL_ICON / WEBCOMPONENT_NAME
          constants, not hand-retyped literals.
[INIT-11] SN-1: a vacuum added AFTER initial platform setup (ensure_vacuum_record,
          e.g. via the Setup panel's add_vacuum) gets its per-vacuum sensors
          immediately through the vacuum-added creation hook — no reload needed.
[INIT-12] SN-1: a map imported for an already-managed-but-still-mapless vacuum gets
          its active-job sensor immediately through the room-update creation hook.
[INIT-13] SN-4: renaming a room and firing the room-update notification swaps the
          sensor entity object under the SAME unique_id (registry entry — and any
          user name override — survives; no duplicate/orphan entity_id created).
[INIT-14] RP-039/RF-16: a LATE mid-setup failure (panel registration) unwinds
          every step that registered before it — services, listeners, trackers,
          forwarded platforms, hass.data/runtime_data pointers.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum import (
    async_remove_config_entry_device,
    async_remove_entry,
)
from custom_components.eufy_vacuum.const import (
    CONF_VACUUM_ENTITY_ID,
    DATA_BATTERY,
    DATA_ERROR_TRACKER,
    DATA_LEARNING,
    DATA_RUNTIME,
    DOMAIN,
    EVENT_JOB_FINISHED,
)


_VAC = "vacuum.alfred"
_STORAGE_KEY = "eufy_vacuum.storage"


def _patch_frontend():
    """Patch the panel surfaces that need the frontend component."""
    return [
        patch("homeassistant.components.panel_custom.async_register_panel",
              AsyncMock()),
        patch("homeassistant.components.frontend.async_remove_panel"),
    ]


@pytest.fixture(autouse=True)
def _vacuum_registered_as_a_real_eufy(hass):
    """MODULE-SCOPED: put `vacuum.alfred` in the entity registry, owned by `robovac_mqtt`.

    A real Eufy vacuum entity is created by that integration and carries its `platform`.
    Brand resolution matches on platform, so without a registry entry the vacuum is
    UNSUPPORTED, no adapter registers, and the number/button platforms this module
    asserts on are never constructed. That used to be invisible: resolution ended at a
    Eufy default arm, so an unregistered fixture vacuum behaved like a real one.

    ⚠ MUST RUN BEFORE THE STATE IS SET. HA's registry will not generate an entity_id
    that already exists in `hass.states`, so registering after
    `hass.states.async_set("vacuum.alfred", ...)` silently yields `vacuum.alfred_2` and
    the vacuum under test stays unregistered. Hence a fixture rather than a call inside
    `_setup`, which the tests reach only after seeding states.

    Autouse is scoped to THIS MODULE deliberately — `test_core_capabilities` builds its
    own registry entries and a second `vacuum.alfred` underneath it would rename them.
    """
    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "alfred_unique_id", suggested_object_id="alfred"
    )


async def _setup(hass, entry):
    await async_setup_component(hass, "http", {})
    entry.add_to_hass(hass)
    patches = _patch_frontend()
    for p in patches:
        p.start()
    try:
        ok = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        for p in patches:
            p.stop()
    return ok


async def test_setup_and_unload(hass, mock_config_entry):
    """[INIT-1]"""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # core subsystems wired into hass.data
    dd = hass.data[DOMAIN]
    assert dd[DATA_RUNTIME] is not None
    assert dd[DATA_BATTERY] is not None
    assert dd[DATA_ERROR_TRACKER] is not None
    assert dd["mapping_tracker"] is not None
    # the configured vacuum became a managed record
    assert _VAC in dd[DATA_RUNTIME].data.get("vacuums", {})
    # platforms forwarded → eufy_vacuum entities exist in the registry
    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    assert any(e.platform == DOMAIN for e in reg.entities.values())

    # unload tears everything down cleanly
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert DATA_RUNTIME not in hass.data.get(DOMAIN, {})


async def test_mid_setup_failure_unwinds_prior_registrations(hass, mock_config_entry):
    """[INIT-14] RP-039/RF-16: a failure LATE in async_setup_entry — panel
    registration, after every other step already succeeded — must unwind
    everything that registered before it: all 4 service groups +
    battery_rebaseline, all 8 listeners, mapping_tracker/battery_manager/
    error_tracker, the forwarded platforms, and the hass.data/runtime_data
    pointers. Before this packet the ONLY thing torn down on a mid-setup
    failure was the manager (RP-003's own entry.async_on_unload ledger,
    already correct) — everything else dangled.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})

    with patch(
        "custom_components.eufy_vacuum.async_register_vacuum_panel",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        ok = await _setup(hass, mock_config_entry)

    assert ok is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    dd = hass.data.get(DOMAIN, {})
    assert DATA_RUNTIME not in dd
    assert DATA_LEARNING not in dd
    assert DATA_BATTERY not in dd
    assert DATA_ERROR_TRACKER not in dd
    assert "mapping_tracker" not in dd
    assert not hasattr(mock_config_entry, "runtime_data")

    # One service from each of the 4 register_*_services groups, plus the
    # standalone battery_rebaseline registration — all unregistered.
    assert not hass.services.has_service(DOMAIN, "battery_rebaseline")
    assert not hass.services.has_service(DOMAIN, "setup_get_status")        # services/setup.py
    assert not hass.services.has_service(DOMAIN, "save_learning_snapshot")  # learning/services.py
    assert not hass.services.has_service(DOMAIN, "get_theme_library")       # themes/services.py
    assert not hass.services.has_service(DOMAIN, "upload_map_image")        # mapping/mapping_services.py

    # All 8 listener groups removed their state.
    assert "_job_lifecycle_unsubs" not in dd
    assert "_discovery_unsubs" not in dd

    # The forwarded platforms were unforwarded too: the platform-created entity
    # goes "unavailable" (HA's standard unload behaviour for any integration —
    # the state/registry entries persisting is the point of a clean unload, not
    # a full delete) rather than staying live and functioning.
    state = hass.states.get("binary_sensor.alfred_active_run_has_error")
    assert state is not None and state.state == "unavailable"


async def test_global_cards_module_registered(hass, mock_config_entry):
    """[INIT-1b] When the frontend component is present, async_setup registers the
    standalone cards bundle as a GLOBAL es-module so the room-card + dashboard card
    are defined on a cold dashboard that never opens the sidebar panel. The default
    harness has no frontend (the call is guarded out), so seed the module-URL store
    to exercise the positive path.
    """
    from homeassistant.components import frontend

    hass.data[frontend.DATA_EXTRA_MODULE_URL] = set()
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    registered = hass.data[frontend.DATA_EXTRA_MODULE_URL]
    assert any("eufy-vacuum-cards.js" in u for u in registered), (
        f"global cards module not registered: {registered}"
    )


async def test_setup_no_vacuum(hass, mock_entry_no_vacuum):
    """[INIT-2] no configured vacuum still loads (fallback panel branch)."""
    ok = await _setup(hass, mock_entry_no_vacuum)
    assert ok is True
    assert mock_entry_no_vacuum.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_entry_no_vacuum.entry_id)
    await hass.async_block_till_done()


async def test_setup_no_vacuum_fallback_panel_uses_shared_constants(
    hass, mock_entry_no_vacuum
):
    """[INIT-2b] INF-1: the fallback panel (registered when no vacuum is
    configured yet) uses panels.py's DEFAULT_PANEL_TITLE / PANEL_ICON /
    WEBCOMPONENT_NAME constants — the single source of truth its own
    docstring claims — instead of hand-retyped literals."""
    from custom_components.eufy_vacuum import panels

    await async_setup_component(hass, "http", {})
    mock_entry_no_vacuum.add_to_hass(hass)
    with patch(
        "homeassistant.components.panel_custom.async_register_panel", AsyncMock()
    ) as mock_register, patch("homeassistant.components.frontend.async_remove_panel"):
        ok = await hass.config_entries.async_setup(mock_entry_no_vacuum.entry_id)
        await hass.async_block_till_done()
    assert ok is True

    fallback_calls = [
        call for call in mock_register.await_args_list
        if call.kwargs.get("frontend_url_path") == "eufy-vacuum"
    ]
    assert len(fallback_calls) == 1
    kwargs = fallback_calls[0].kwargs
    assert kwargs["webcomponent_name"] == panels.WEBCOMPONENT_NAME
    assert kwargs["sidebar_title"] == panels.DEFAULT_PANEL_TITLE
    assert kwargs["sidebar_icon"] == panels.PANEL_ICON

    assert await hass.config_entries.async_unload(mock_entry_no_vacuum.entry_id)
    await hass.async_block_till_done()


_COMPANIONS = {
    "sensor.alfred_task_status": "cleaning",
    "sensor.alfred_dock_status": "idle",
    "sensor.alfred_active_map": "6",
    "sensor.alfred_active_cleaning_target": "",
    "sensor.alfred_cleaning_time": "1200",
    "sensor.alfred_cleaning_area": "30",
    "sensor.alfred_battery": "80",
    "sensor.alfred_error_message": "",
    "sensor.alfred_water_level": "75",
    "sensor.alfred_work_mode": "auto",
    "sensor.alfred_robot_position_x_raw": "1.0",
    "sensor.alfred_robot_position_y_raw": "2.0",
    "binary_sensor.alfred_charging": "off",
    "select.alfred_cleaning_intensity": "Standard",
    "button.alfred_wash_mop": "2026-01-01T00:00:00+00:00",
    "button.alfred_dry_mop": "2026-01-01T00:00:00+00:00",
    "button.alfred_empty_dust": "2026-01-01T00:00:00+00:00",
    "sensor.alfred_filter_remaining": "90",
    "sensor.alfred_main_brush_remaining": "85",
    "sensor.alfred_side_brush_remaining": "80",
    "sensor.alfred_rolling_brush_remaining": "88",
}


async def test_setup_full_entity_stack(hass, mock_config_entry):
    """[INIT-4] a richly-capable vacuum → more platform entities constructed."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    for entity_id, state in _COMPANIONS.items():
        hass.states.async_set(entity_id, state)
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # capability detection saw the companion stack → entities across all
    # five platforms got constructed
    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    domains = {e.entity_id.split(".", 1)[0] for e in reg.entities.values()
               if e.platform == DOMAIN}
    # the capability-gated platforms construct entities across several domains
    # (maintenance numbers/buttons, status sensors, error binary_sensor)
    assert len(domains) >= 3
    assert "number" in domains and "button" in domains

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_with_maps_and_rooms(hass, hass_storage, mock_config_entry):
    """[INIT-5] boot with stored maps+rooms exercises the sensor orchestrator.

    Pre-seeding storage means the per-map/room loop in sensor.async_setup_entry
    runs (room history + rule-status sensors get built), and the registered
    room-update / job-finished callbacks fire the sync + refresh paths.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {
                "1": {"room_id": 1, "name": "Kitchen", "enabled": True},
                "2": {"room_id": 2, "name": "Bath", "enabled": True},
            }}}},
        "error_tracker": {_VAC: {
            # a recovered latch (blank current_message) → job-finished auto-clears it
            "active_run_error": {"current_message": "", "recovered": True,
                                 "errors": []},
            "last_device_error": None, "recent_errors": []}},
    }}
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    # room-scoped sensors got built from the stored rooms
    assert any(
        e.platform == DOMAIN and "_6_" in (e.unique_id or "")
        for e in reg.entities.values()
    )

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    # room-update notify → _sync_room_history/_rule_status callbacks
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()
    # drop a room then notify again → stale-removal branch
    rt.data["maps"][_VAC]["6"]["rooms"].pop("2", None)
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()

    # job-finished → refresh history sensors + auto-clear the recovered latch
    # job_path is present on EVERY real payload (both builders emit the key) and is only
    # non-empty when a record actually landed. The auto-clear is gated on it, because the
    # event ALSO fires on paths where the finalize raised — where the latch is the run's
    # only surviving error evidence. This models a SUCCESSFUL finalize.
    hass.bus.async_fire(EVENT_JOB_FINISHED,
                        {"vacuum_entity_id": _VAC, "map_id": "6",
                         "job_path": "/config/eufy_vacuum/jobs/job_x.json"})
    await hass.async_block_till_done()
    tracker = hass.data[DOMAIN][DATA_ERROR_TRACKER]
    assert tracker.get_active_run_latch(_VAC) is None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def _boot_storage_one_room():
    """Storage payload with one stored vacuum + map "6" holding a single room.

    Mirrors the [INIT-5] seed but with only room "1" so the dynamic-sync tests
    can observe the *new*-room branch when a second room is introduced.
    """
    return {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {
                "1": {"room_id": 1, "name": "Kitchen", "enabled": True},
            }}}},
    }}


async def test_room_update_callback_adds_new_entities(
    hass, hass_storage, mock_config_entry
):
    """[INIT-6] adding a room + notifying builds & registers new room sensors.

    Boots with a single stored room, then introduces room "3" into the
    manager's live map data and fires _notify_rooms_updated. The registered
    sync callbacks must construct a *new* history sensor AND a *new*
    rule-status sensor and push them through async_add_entities, so both land
    in the entity registry. We observe the registry growing with unique_ids
    that carry the "_6_3" room coordinate.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)

    def _room_3_unique_ids():
        return {
            e.unique_id
            for e in reg.entities.values()
            if e.platform == DOMAIN and "_6_3_" in (e.unique_id or "")
        }

    # Room "3" does not exist yet → no sensors for it.
    assert _room_3_unique_ids() == set()

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    # A newly-introduced, user-configured room. ``is_configured`` is the
    # entity-creation gate sort_room_items enforces, so without it the room
    # would be treated as discovered-but-unapproved and never materialize.
    rt.data["maps"][_VAC]["6"]["rooms"]["3"] = {
        "room_id": 3, "name": "Office", "enabled": True, "is_configured": True,
    }
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()

    new_ids = _room_3_unique_ids()
    # Both the history and rule-status sync callbacks fired → two new entities.
    assert any(uid.endswith("_cleaning_history") for uid in new_ids), new_ids
    assert any(uid.endswith("_rule_status") for uid in new_ids), new_ids

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_refresh_callbacks_push_state(hass, hass_storage, mock_config_entry):
    """[INIT-7] rule-status + theme refresh callbacks write observable state.

    _notify_room_rule_status_updated drives the rule-status refresh callback
    (a no-crash state-write fan-out). save_theme_as_new fires the theme update
    callback through the targeted-vacuum branch; afterwards the theme sensor's
    HA state reflects the new theme name, proving the scheduled state write
    actually reached hass.states.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    theme_entity_id = reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_theme_state"
    )
    assert theme_entity_id is not None
    # No theme selected yet.
    assert hass.states.get(theme_entity_id).state == "none"

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    # Rule-status refresh fan-out — must not raise and must flush cleanly.
    rt._notify_room_rule_status_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()

    # Saving a new theme activates it and fires the theme callback for this
    # vacuum (targeted-vacuum branch). The sensor state must update to "X".
    rt.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="X")
    await hass.async_block_till_done()
    assert hass.states.get(theme_entity_id).state == "X"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_clean_order_refresh_callback_pushes_state(
    hass, hass_storage, mock_config_entry
):
    """[INIT-7b] a clean-order cache write reaches hass.states WITHOUT a poll.

    The clean-order sensor is poll-driven, so before the update-callback seam
    existed every read landed in the manager's cache and stayed invisible until
    the platform's next scan — measured at 10s and 29s against real hardware.
    That delay lands squarely on the Apply -> "the row turns green" confirmation
    the whole override flow is built around, so the button reads as broken while
    the device has already acked.

    This is the [INIT-7] shape applied to clean order: boot for real, write the
    cache, and assert the ENTITY STATE changed. Asserting the callback fired
    would not do — the callback firing into an entity whose `hass` is unset is
    exactly the silent no-op this has to rule out.
    """
    # The block is forced at the RESOLVER rather than through
    # register_adapter_config, because booting the entry re-registers the code
    # adapter for this vacuum and would overwrite a config planted beforehand.
    _CLEAN_ORDER_BLOCK = {
        "device_clean_order": {
            "enabled": True,
            "read": {
                "via": "v1_debug_log",
                "command": "get_clean_sequence",
                "service": {"domain": "vacuum", "service": "send_command"},
                "source_logger": "test.init7b.protocol",
                "decoded_prefix": "Decoded V1 message result: ",
            },
        },
    }

    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    with patch(
        "custom_components.eufy_vacuum.clean_order.manager._get_adapter_config",
        return_value=_CLEAN_ORDER_BLOCK,
    ):
        ok = await _setup(hass, mock_config_entry)
        assert ok is True
        await _assert_clean_order_push(hass)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def _assert_clean_order_push(hass):
    """The body of [INIT-7b], run inside the adapter-config patch."""

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    clean_order_entity_id = reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_clean_order"
    )
    assert clean_order_entity_id is not None, (
        "no clean-order sensor was built for an adapter that declares the block"
    )
    # Nothing read yet: unknown, which is NOT the same fact as an empty order.
    assert hass.states.get(clean_order_entity_id).state == "unknown"

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    rt.clean_order._store(_VAC, [1, 2, 3], "ok")
    await hass.async_block_till_done()

    assert hass.states.get(clean_order_entity_id).state == "3", (
        "the cache write never reached the entity — the sensor is still "
        "waiting on its poll"
    )


async def test_clean_order_listener_registers_after_the_sensor_subscribes(
    hass, hass_storage, mock_config_entry
):
    """[INIT-7c] the clean-order listener registers AFTER the sensor subscribes.

    ⚠ THIS PINS AN ORDERING, and the ordering is the whole finding. The listener
    registers through `async_at_started`, which fires INLINE whenever hass is
    already running — which is every config-entry reload. Registered alongside the
    other listeners it therefore ran BEFORE the platforms were forwarded, so the
    startup read finished while the sensor had not yet subscribed to the cache:
    the notify went to an empty callback list and the entity sat at `never_read`
    until its next poll (29.7s, measured on real hardware).

    The invariant is asserted STRUCTURALLY — how many subscribers exist at the
    moment `register` is called — rather than through the observable sensor state,
    and that is a correction, not a shortcut. The obvious version of this test
    booted the integration and asserted the sensor was not `never_read`; it passed
    with the registration moved back to the broken position, because in a test
    harness the read fails instantly, so the sensor is CREATED AFTER it and simply
    reads the already-populated cache. The live race exists only because a real
    read spends ~350ms waiting on the device. A timing bug that a test cannot make
    slow has to be pinned at the structure that causes it.

    RED IF `clean_order_refresh.register` MOVES BACK ABOVE THE PLATFORM FORWARD.
    """
    from custom_components.eufy_vacuum.listeners import clean_order_refresh

    _CLEAN_ORDER_BLOCK = {
        "device_clean_order": {
            "enabled": True,
            "read": {
                "via": "v1_debug_log",
                "command": "get_clean_sequence",
                "service": {"domain": "vacuum", "service": "send_command"},
                "source_logger": "test.init7c.protocol",
                "decoded_prefix": "Decoded V1 message result: ",
            },
        },
    }

    observed: dict[str, int] = {}
    _real_register = clean_order_refresh.register

    def _spy_register(hass_):
        rt = hass_.data[DOMAIN][DATA_RUNTIME]
        observed["subscribers"] = len(rt.clean_order._update_callbacks)
        return _real_register(hass_)

    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    with patch(
        "custom_components.eufy_vacuum.clean_order.manager._get_adapter_config",
        return_value=_CLEAN_ORDER_BLOCK,
    ), patch(
        "custom_components.eufy_vacuum.listeners.clean_order_refresh.register",
        _spy_register,
    ):
        ok = await _setup(hass, mock_config_entry)
        assert ok is True

    assert "subscribers" in observed, "the listener was never registered at all"
    assert observed["subscribers"] >= 1, (
        "clean_order_refresh.register ran before the sensor platform subscribed "
        "to the clean-order cache — the startup read's result will be published "
        "to nobody and the entity will wait a full poll interval"
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_hourly_refresh_tick(hass, hass_storage, mock_config_entry):
    """[INIT-8] the hourly safety-net interval refreshes history sensors.

    Advancing the clock past the registered 1-hour interval fires
    _handle_hourly_refresh, which schedules a state write on every room-history
    sensor. The tick must complete without crashing and the history sensor must
    still hold a live state afterwards.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    history_entity_id = reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_6_1_cleaning_history"
    )
    assert history_entity_id is not None

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(hours=1, seconds=5)
    )
    await hass.async_block_till_done()

    # Sensor survived the tick and still reports a state (no exception thrown).
    assert hass.states.get(history_entity_id) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_vacuum_added_after_setup_gets_sensors(hass, mock_config_entry):
    """[INIT-11] SN-1: a second vacuum added AFTER the sensor platform has
    already run its initial setup loop (no map, no prior storage entry) gets
    its per-vacuum sensors immediately via the vacuum-added creation hook —
    the bug was these staying absent until a restart/reload."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)

    ivy = "vacuum.ivy"
    assert reg.async_get_entity_id("sensor", DOMAIN, "vacuum_ivy_theme_state") is None

    # Mirrors setup/workflow.add_vacuum's precondition + call, without going
    # through the service layer: the entity must exist, then ensure_vacuum_record
    # creates the managed-vacuum record and fires the vacuum-added notification.
    hass.states.async_set(ivy, "docked", {"supported_features": 0})
    rt = hass.data[DOMAIN][DATA_RUNTIME]
    rt.ensure_vacuum_record(vacuum_entity_id=ivy)
    await hass.async_block_till_done()

    theme_entity_id = reg.async_get_entity_id("sensor", DOMAIN, "vacuum_ivy_theme_state")
    assert theme_entity_id is not None
    assert hass.states.get(theme_entity_id) is not None

    # Idempotent: ensure_vacuum_record is called from many places (capability
    # refresh, discover_rooms, ...) — a repeat call for the SAME vacuum must
    # not re-fire the hook into a duplicate registry entry.
    rt.ensure_vacuum_record(vacuum_entity_id=ivy)
    await hass.async_block_till_done()
    assert reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_ivy_theme_state"
    ) == theme_entity_id

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_map_imported_for_mapless_vacuum_gets_active_job_sensor(
    hass, mock_config_entry
):
    """[INIT-12] SN-1: the configured vacuum boots with NO map at all (so the
    per-map loop in sensor.async_setup_entry never runs for it). Importing a
    map afterwards (save_managed_rooms' own notification path) must build the
    active-job sensor for that (vacuum, map) immediately, not on next reload."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    assert reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_active_job_9"
    ) is None

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    # ensure_map_bucket + a room-update notification is the same shape
    # save_managed_rooms leaves behind after a real map import.
    rt.data.setdefault("maps", {}).setdefault(_VAC, {})["9"] = {
        "map_id": "9", "metadata": {}, "summary": {}, "rooms": {},
    }
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="9")
    await hass.async_block_till_done()

    active_job_entity_id = reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_active_job_9"
    )
    assert active_job_entity_id is not None
    assert hass.states.get(active_job_entity_id) is not None

    # Idempotent: a second notification for the same (vacuum, map) must not
    # create a duplicate registry entry.
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="9")
    await hass.async_block_till_done()
    assert reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_active_job_9"
    ) == active_job_entity_id

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_room_rename_swaps_entity_keeping_unique_id(
    hass, hass_storage, mock_config_entry
):
    """[INIT-13] SN-4: renaming a room and firing the room-update notification
    must swap the sensor entity object (its cached display name is set once,
    at construction, from the room's name) while keeping the SAME unique_id —
    so the registry entry (and any user name override) is not disturbed and
    no duplicate/orphan entity_id is created. Also asserts the swap actually
    happened (new object, new `room_name`) rather than just a state
    re-write on the stale object, which would leave the OLD name cached."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    from homeassistant.helpers import entity_registry as er
    reg = er.async_get(hass)
    history_entity_id = reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_6_1_cleaning_history"
    )
    assert history_entity_id is not None
    assert hass.states.get(history_entity_id) is not None
    sensor_component = hass.data["entity_components"]["sensor"]
    before_entity = sensor_component.get_entity(history_entity_id)
    assert before_entity is not None
    assert before_entity.room_name == "Kitchen"

    rt = hass.data[DOMAIN][DATA_RUNTIME]
    rt.data["maps"][_VAC]["6"]["rooms"]["1"]["name"] = "Great Room"
    rt._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="6")
    await hass.async_block_till_done()

    # Same unique_id → same entity_id after the rename; no duplicate/orphan.
    assert reg.async_get_entity_id(
        "sensor", DOMAIN, "vacuum_alfred_6_1_cleaning_history"
    ) == history_entity_id
    # The swapped-in entity is alive and reporting state (round-tripped
    # through async_remove + async_add_entities, not left removed).
    assert hass.states.get(history_entity_id) is not None
    # The registered entity is genuinely the NEW object (not the stale one
    # with state re-written), and it carries the room's CURRENT name --
    # `room_name` is set once at construction, so this only holds if the
    # swap actually happened rather than a no-op state write on `before_entity`.
    after_entity = sensor_component.get_entity(history_entity_id)
    assert after_entity is not None
    assert after_entity is not before_entity
    assert after_entity.room_name == "Great Room"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_remove_entry_clears_storage(hass, mock_config_entry):
    """[INIT-3] async_remove_entry removes the integration's store."""
    with patch("homeassistant.helpers.storage.Store.async_remove",
               AsyncMock()) as mock_remove:
        await async_remove_entry(hass, mock_config_entry)
    mock_remove.assert_awaited_once()


def _capture_call_later(scheduled):
    """A fake async_call_later that records the scheduled callback (no reload)."""
    def _fake(_hass, _delay, cb):
        scheduled.append(cb)
        return lambda: None
    return _fake


async def test_remove_config_entry_device_removes_vacuum(hass, mock_config_entry):
    """[INIT-9] Deleting a vacuum's device tears it down IN PLACE, and — because
    _VAC is the config-flow vacuum — also clears it from the entry so
    async_setup_entry can't resurrect it on the next load.

    No inline reload (that would bounce the other vacuums + race HA's own device
    removal): the trackers + adapter + panel + storage are unwound directly, and
    the entry-clear is deferred.

    RP-039/RF-16: also asserts the two teardown gaps this packet closed —
    discovery's per-vacuum listeners (previously entry-wide only, so a removed
    vacuum's state-change listeners kept firing) and the four in-memory manager
    caches remove_vacuum_record never touched (runtime, room-history-cache-ready/
    -loading, map-state-source) — a vacuum removed then re-added with the same
    entity_id would otherwise short-circuit on a stale-true cache marker.
    """
    from homeassistant.helpers import device_registry as dr

    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    dd = hass.data[DOMAIN]
    rt = dd[DATA_RUNTIME]
    assert _VAC in rt.data["vacuums"]
    assert _VAC in dd[DATA_BATTERY]._vacuum_unsubs
    assert _VAC in dd[DATA_ERROR_TRACKER]._vacuum_unsubs
    # discovery.register() ran during setup — the default cadence (vacuum_docked
    # trigger + periodic) activates for any registered vacuum, so it's already
    # keyed for _VAC.
    assert _VAC in dd.get("_discovery_unsubs", {})
    assert dd["_discovery_unsubs"][_VAC], "discovery registered no listeners for _VAC"

    # Seed the four in-memory caches remove_vacuum_record deliberately does NOT
    # touch (storage-only — see its own docstring) — nothing in a bare _setup()
    # populates these (no job ever ran), so seed them directly to prove
    # clear_vacuum_runtime_caches actually clears them.
    rt.ensure_runtime(_VAC)
    rt._room_history_cache_ready.add(_VAC)
    rt._room_history_cache_loading.add(_VAC)
    rt._map_state_source_cache[_VAC] = {"mtime": None, "map_id": "9", "result": {}}

    # `async_get_device(identifiers=...)` is DEPRECATED and newer Home Assistant RAISES on
    # it — identifiers are no longer unique across config entries. Scoped lookup instead.
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, _VAC.replace(".", "_")), mock_config_entry.entry_id
    )
    assert device is not None

    # Capture the deferred entry-clear so the real reload never runs in the test.
    scheduled: list = []
    with patch("custom_components.eufy_vacuum.async_call_later",
               _capture_call_later(scheduled)), \
         patch("homeassistant.components.frontend.async_remove_panel") as mock_panel:
        result = await async_remove_config_entry_device(
            hass, mock_config_entry, device
        )

    assert result is True
    assert _VAC not in rt.data["vacuums"]                     # storage dropped
    assert _VAC not in dd[DATA_BATTERY]._vacuum_unsubs        # battery torn down
    assert _VAC not in dd[DATA_ERROR_TRACKER]._vacuum_unsubs  # error torn down
    assert _VAC not in dd.get("_discovery_unsubs", {})        # discovery torn down
    assert _VAC not in rt.runtime                             # in-memory runtime cache dropped
    assert _VAC not in rt._room_history_cache_ready           # stale-ready marker cleared
    assert _VAC not in rt._room_history_cache_loading         # stale-loading marker cleared
    assert _VAC not in rt._map_state_source_cache             # map-state-source cache dropped
    mock_panel.assert_called_once_with(hass, "eufy-vacuum-alfred")  # panel removed

    # _VAC was the configured vacuum → a deferred entry-clear was scheduled;
    # running it removes CONF_VACUUM_ENTITY_ID so a reload can't resurrect it.
    assert len(scheduled) == 1
    with patch.object(hass.config_entries, "async_update_entry") as mock_update:
        scheduled[0](None)
    _, kw = mock_update.call_args
    assert CONF_VACUUM_ENTITY_ID not in kw.get("data", {})
    assert CONF_VACUUM_ENTITY_ID not in kw.get("options", {})

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_remove_non_configured_vacuum_keeps_entry(
    hass, hass_storage, mock_config_entry
):
    """[INIT-9b] Deleting a NON-configured vacuum tears it down but does NOT clear
    the entry or schedule a reload — the configured vacuum + the others are left
    exactly as they were.

    RP-039/RF-16: also proves discovery.remove_vacuum's per-vacuum ISOLATION —
    removing _VAC2's auto-discovery triggers must not touch _VAC's (the whole
    point of keying the ledger per vacuum instead of one flat entry-wide list).
    """
    from homeassistant.helpers import device_registry as dr

    _VAC2 = "vacuum.bertie"
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass.states.async_set(_VAC2, "docked", {"supported_features": 0})
    # two managed vacuums; _VAC stays the config-flow (configured) vacuum
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}, _VAC2: {"name": "Bertie"}},
    }}
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    dd = hass.data[DOMAIN]
    rt = dd[DATA_RUNTIME]
    assert _VAC2 in rt.data["vacuums"]
    assert _VAC in dd.get("_discovery_unsubs", {})
    assert _VAC2 in dd.get("_discovery_unsubs", {})
    rt._map_state_source_cache[_VAC2] = {"mtime": None, "map_id": "1", "result": {}}

    device2 = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, _VAC2.replace(".", "_")), mock_config_entry.entry_id
    )
    assert device2 is not None

    scheduled: list = []
    with patch("custom_components.eufy_vacuum.async_call_later",
               _capture_call_later(scheduled)), \
         patch("homeassistant.components.frontend.async_remove_panel") as mock_panel:
        result = await async_remove_config_entry_device(hass, mock_config_entry, device2)

    assert result is True
    assert _VAC2 not in rt.data["vacuums"]   # the deleted (non-configured) one is gone
    assert _VAC in rt.data["vacuums"]        # the configured one is untouched
    mock_panel.assert_called_once_with(hass, "eufy-vacuum-bertie")
    assert scheduled == []                   # NOT the configured vacuum → no entry clear
    assert _VAC2 not in dd.get("_discovery_unsubs", {})  # bertie's triggers torn down
    assert _VAC in dd.get("_discovery_unsubs", {})       # alfred's triggers UNTOUCHED
    assert _VAC2 not in rt._map_state_source_cache       # bertie's cache dropped

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_remove_config_entry_device_unknown_is_safe(hass, mock_config_entry):
    """[INIT-10] Deleting a stale/unrelated device is a safe no-op → still True.

    No matching vacuum → no teardown and no entry clear, but still return True so
    HA can clean up the orphan device.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True
    rt = hass.data[DOMAIN][DATA_RUNTIME]

    class _FakeDevice:
        # identifier matches no managed vacuum
        identifiers = {(DOMAIN, "vacuum_ghost")}

    scheduled: list = []
    with patch("custom_components.eufy_vacuum.async_call_later",
               _capture_call_later(scheduled)), \
         patch("homeassistant.components.frontend.async_remove_panel") as mock_panel:
        result = await async_remove_config_entry_device(
            hass, mock_config_entry, _FakeDevice()
        )

    assert result is True              # HA may still remove the stale device
    assert _VAC in rt.data["vacuums"]  # the real vacuum is untouched
    mock_panel.assert_not_called()     # no teardown for an unknown device
    assert scheduled == []             # and no entry clear

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_init14_battery_aggregates_migration_is_dispatched(hass, mock_config_entry, hass_storage):
    """[INIT-14] Reachability, not behaviour — the behaviour is covered by BAM-1..12.

    Two things are asserted together because either alone is misleading: the migration
    LATCHED (so it ran to completion rather than deferring), and the stale bucket was
    actually replaced (so it ran over the seeded data rather than latching vacuously).

    RED IF THE HOOK MOVES ABOVE `hass.data[DOMAIN][DATA_BATTERY] = battery_manager`.
    `async_at_started` fires immediately against a running hass, which is what a
    config-entry reload does, so a hook registered earlier is dispatched while the
    battery manager is still unset — it would defer, not latch, and the collapse would
    stay armed on exactly the installs that upgrade.
    """
    from custom_components.eufy_vacuum.core.battery_aggregates_migration import (
        BACKUP_FIELD, MIGRATION_KEY,
    )

    # A bucket in the shape an upgraded install actually holds: a populated denominator
    # and NO partnered numerator. Taken from the live store 2026-08-23.
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "battery": {"vacuums": {_VAC: {"job_aggregates": {
            "all_jobs": {
                "count": 47,
                "drain_pct_sum": 159.0,
                "duration_min_sum": 544.45,
                "area_m2_sum": 191.0,
                "drain_per_min_mean": 0.292,
                "drain_per_hour_mean": 17.5223,
                "drain_per_m2_mean": 0.8325,
            },
            "by_clean_mode": {}, "by_fan_speed": {}, "by_water_level": {},
        }}}},
    }}
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    assert await _setup(hass, mock_config_entry) is True
    await hass.async_block_till_done()

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    assert manager.data["migrations"].get(MIGRATION_KEY) is True, (
        "the migration was never dispatched, or it deferred -- check that its "
        "async_at_started hook is registered AFTER DATA_BATTERY is set"
    )
    record = manager.data["battery"]["vacuums"][_VAC]
    bucket = record["job_aggregates"]["all_jobs"]
    # replayed from an empty archive: partnered keys present, stale sums gone
    assert "drain_pct_sum_for_duration" in bucket
    assert bucket["duration_min_sum"] == 0.0
    assert record[BACKUP_FIELD]["all_jobs"]["duration_min_sum"] == pytest.approx(544.45)


# ---------------------------------------------------------------------------
# [INIT-15] every listener is torn down by the REAL unload path
# ---------------------------------------------------------------------------

def _listener_domain_keys() -> dict[str, str]:
    """Every ``hass.data[DOMAIN]`` key the listener package parks state under.

    DERIVED FROM THE MODULES, never hand-listed: a twelfth listener that forgets
    teardown has to be caught on the day it lands, and a hand-kept list reports the
    same clean result whether it is complete or one short.
    """
    import importlib
    import pkgutil

    from custom_components.eufy_vacuum import listeners as pkg

    out: dict[str, str] = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{pkg.__name__}.{info.name}")
        for attr, val in vars(mod).items():
            # The convention throughout the package: a module-private constant whose
            # VALUE is also underscore-prefixed is a domain_data key.
            if attr.startswith("_") and isinstance(val, str) and val.startswith("_"):
                out.setdefault(val, info.name)
    return out


async def test_unload_tears_down_every_listener(hass, hass_storage, mock_config_entry):
    """[INIT-15] After a NORMAL unload, no listener has left state behind.

    ⚠ NOTHING IN tests/ DRIVES async_unload_entry, and that is how a leak shipped.
    `clean_order_refresh` was registered with an entry on `_unwind_stack` and nothing
    in the unload block — and `_unwind_stack` is walked ONLY from the `except` arm of
    async_setup_entry, so an entry that sets up successfully and is later unloaded
    never touches it. `register` then overwrote its unsub key without calling the old
    unsubs, leaving the previous dock-arrival subscription live on the bus. Measured
    on a real setup+reload: ONE dock arrival fired TWO reads, i.e. two real
    send_commands at the robot, growing by one per reload.

    [LR-6b] in test_listeners_registration.py did not catch it and could not: it calls
    `clean_order_refresh.remove(hass)` DIRECTLY. The guard worked; nothing invoked it.
    So this test asserts the PATH, not the function.

    The positive control is load-bearing. A listener that never registered in this
    harness parks no key, and "its key is absent after unload" would then be true for
    a reason that has nothing to do with teardown — the empty-dict pass. So the keys
    actually present after SETUP are captured first, and only those are asserted gone.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    known = _listener_domain_keys()
    assert known, "derived no listener keys at all — the convention changed"

    domain_data = hass.data.get(DOMAIN, {})
    present = {k: mod for k, mod in known.items() if k in domain_data}
    assert len(present) >= 5, (
        "positive control: this harness only exercised "
        f"{len(present)} listener key(s) {sorted(present)}, so asserting them absent "
        "after unload would prove almost nothing"
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    after = hass.data.get(DOMAIN, {})
    leaked = sorted(f"{k} ({mod})" for k, mod in present.items() if k in after)
    assert not leaked, (
        "these listeners registered during setup and were NOT torn down by "
        f"async_unload_entry: {leaked}. Every listener setup registers must appear in "
        "that function's teardown block — the unwind stack does not run on a normal "
        "unload."
    )


# ---------------------------------------------------------------------------
# [INIT-C41] the two override surfaces merge per ROLE  (ledger C41 / issue #63)
# ---------------------------------------------------------------------------


def test_init_c41_1_an_options_entry_does_not_erase_the_panels_roles():
    """[INIT-C41-1] THE RED INPUT, from the report.

    A user pins `work_mode` through the options flow at first config, then sets
    `battery` from the panel's Setup tab. `set_entity_override` reloads the entry, the
    merge runs, and under the old `{**stored, **entry_options}` — keyed by VACUUM — the
    options dict replaced that vacuum's whole role map and `battery` was gone. The pick
    never survived its own save.

    ABLATION: restore the shallow per-vacuum merge and this goes red with battery absent.
    """
    from custom_components.eufy_vacuum import merge_entity_overrides

    stored = {"vacuum.saros": {"battery": "sensor.saros_battery"}}
    options = {"vacuum.saros": {"work_mode": "sensor.betriebsmodus"}}

    merged = merge_entity_overrides(stored, options)
    assert merged["vacuum.saros"] == {
        "battery": "sensor.saros_battery",
        "work_mode": "sensor.betriebsmodus",
    }, "the panel's role was dropped by an unrelated options entry"


def test_init_c41_2_entry_options_still_win_on_the_same_role():
    """[INIT-C41-2] The other direction, so C41-1 cannot be satisfied by simply
    ignoring the options flow.

    Entry options remain the rescue path that works when the frontend does not, so on a
    role BOTH surfaces set, the options value must still win. Only the GRANULARITY
    changed — per role instead of per vacuum.
    """
    from custom_components.eufy_vacuum import merge_entity_overrides

    merged = merge_entity_overrides(
        {"vacuum.saros": {"battery": "sensor.from_panel"}},
        {"vacuum.saros": {"battery": "sensor.from_options"}},
    )
    assert merged["vacuum.saros"]["battery"] == "sensor.from_options"


def test_init_c41_3_a_malformed_options_entry_cannot_erase_a_working_store():
    """[INIT-C41-3] An options entry that is not a role map carries nothing to merge, so
    honouring it could only ever delete. It is ignored and warned about instead.

    This is the asymmetry the rejection store already records in another form: an
    unattributable value may suppress, but it may never destroy.
    """
    from custom_components.eufy_vacuum import merge_entity_overrides

    merged = merge_entity_overrides(
        {"vacuum.saros": {"battery": "sensor.from_panel"}},
        {"vacuum.saros": ["not", "a", "role", "map"]},
    )
    assert merged["vacuum.saros"] == {"battery": "sensor.from_panel"}


def test_init_c41_4_a_vacuum_known_only_to_the_options_flow_still_arrives():
    """[INIT-C41-4] The merge must not become panel-only: a vacuum the panel store has
    never seen, configured entirely through the options flow, still has to come through.
    """
    from custom_components.eufy_vacuum import merge_entity_overrides

    merged = merge_entity_overrides(
        {"vacuum.alfred": {"battery": "sensor.alfred_battery"}},
        {"vacuum.ivy": {"task_status": "sensor.ivy_status"}},
    )
    assert set(merged) == {"vacuum.alfred", "vacuum.ivy"}
    assert merged["vacuum.ivy"] == {"task_status": "sensor.ivy_status"}


# ---------------------------------------------------------------------------
# [INIT-PANEL] the panel survives OUR OWN reload  (issue #63)
# ---------------------------------------------------------------------------
#
# ⚠ THESE SPY ON `frontend.async_remove_panel` RATHER THAN ASKING THE FRONTEND.
# The first version asserted `frontend.async_panel_exists(...)` and PASSED VACUOUSLY:
# this harness never sets up the `frontend`/`panel_custom` components, so no panel is
# ever really registered and "it is absent after unload" was true before the unload too.
# The positive control caught it. What the fix actually changes is whether the removal
# is CALLED, so that is what these assert.


def _spy_remove_panel(monkeypatch):
    """Record every async_remove_panel(url) the unload path makes."""
    from custom_components.eufy_vacuum import frontend as _fe

    removed: list[str] = []
    real = _fe.async_remove_panel

    def _spy(hass_, panel_url, *a, **kw):
        removed.append(panel_url)
        try:
            return real(hass_, panel_url, *a, **kw)
        except Exception:
            return None

    monkeypatch.setattr(_fe, "async_remove_panel", _spy)
    return removed


async def test_init_panel_1_a_genuine_unload_still_removes_the_panel(
    hass, hass_storage, mock_config_entry, monkeypatch
):
    """[INIT-PANEL-1] THE CONTROL, and it has to come first.

    A panel left registered against an integration that is gone is worse than the bug
    being fixed. If this goes red, the override fix has turned every unload into a leak
    and INIT-PANEL-2 is proving nothing.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    assert await _setup(hass, mock_config_entry) is True

    panels = list(hass.data.get(DOMAIN, {}).get(f"_panels_{mock_config_entry.entry_id}", []))
    assert panels, "positive control: the ledger is empty, so removal proves nothing"

    removed = _spy_remove_panel(monkeypatch)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    missed = [u for u in panels if u not in removed]
    assert not missed, f"a genuine unload did not remove: {missed}"


async def test_init_panel_2_the_panel_survives_the_override_reload(
    hass, hass_storage, mock_config_entry, monkeypatch
):
    """[INIT-PANEL-2] THE RED INPUT, from issue #63.

    `set_entity_override` reloads the config entry so the new override reaches the
    adapter, the capabilities and the platforms. Unload used to remove the panel
    unconditionally — so the panel the user was STANDING ON disappeared mid-action, Home
    Assistant bounced them to their default dashboard, and the in-flight render call died
    with it. That is the whole of "appears to crash (screen exit)".

    ABLATION: drop the `_keep_panels` branch from async_unload_entry and this goes red
    while INIT-PANEL-1 stays green — the asymmetry that let the eject ship, because every
    existing test exercised the genuine-unload path.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_one_room()
    assert await _setup(hass, mock_config_entry) is True

    panels = list(hass.data.get(DOMAIN, {}).get(f"_panels_{mock_config_entry.entry_id}", []))
    assert panels, "positive control: the ledger is empty"

    # Exactly what services/setup.py::set_entity_override does before reloading.
    hass.data.setdefault(DOMAIN, {})["_panel_survives_reload"] = mock_config_entry.entry_id

    removed = _spy_remove_panel(monkeypatch)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    took = [u for u in panels if u in removed]
    assert not took, (
        f"the override reload removed {took} — the user is ejected to their default "
        f"dashboard mid-action"
    )
    # And the ledger must survive too, or setup rebuilds it from nothing and the next
    # genuine unload has no panels to tear down.
    assert hass.data.get(DOMAIN, {}).get(f"_panels_{mock_config_entry.entry_id}") == panels


# ---------------------------------------------------------------------------
# [INIT-16]..[INIT-22] the sensor orchestrator's unreached arms.
#
# [INIT-5] is the standing positive control for the latch trio: same storage seed, a
# successful finalize, and it asserts the latch IS cleared. Each test below is that
# input with exactly one thing changed, so the expected values are asymmetric against
# a test already in this file rather than against a fallback.
# ---------------------------------------------------------------------------

def _boot_storage_with_latch(latch):
    """The [INIT-5] seed with the active-run latch supplied by the caller."""
    return {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {"1": {"room_id": 1, "name": "Kitchen", "enabled": True}},
        }}},
        "error_tracker": {_VAC: {
            "active_run_error": latch,
            "last_device_error": None, "recent_errors": [],
        }},
    }}


_RECOVERED = {"current_message": "", "recovered": True, "errors": []}
_JOB_PATH = "/config/eufy_vacuum/jobs/job_x.json"


async def test_init16_a_run_that_wrote_no_record_keeps_its_error_latch(
    hass, hass_storage, mock_config_entry
):
    """[INIT-16] A cancel fires EVENT_JOB_FINISHED with finalize_result=None, so the
    payload carries no `job_path` -- and on that path the latch was deliberately never
    harvested, which makes it the run's ONLY surviving evidence of the fault.

    The comment at sensor/__init__.py:589-597 records that this door already threw away
    "exactly what the peek/commit split exists to preserve" once: the commit keeps the
    latch when the record write fails, and this handler then cleared it anyway.

    THE PAIR IS THE POINT. The same boot, the same latch, two events differing only in
    `job_path`: without it the latch must survive, with it the latch must clear. One
    assertion alone would be satisfied by a handler that never clears or always clears;
    the two together pin the gate. Removing `_finalized_ok` from line 600 reddens the
    first half while leaving the second green.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_with_latch(dict(_RECOVERED))
    assert await _setup(hass, mock_config_entry) is True
    tracker = hass.data[DOMAIN][DATA_ERROR_TRACKER]

    hass.bus.async_fire(EVENT_JOB_FINISHED, {"vacuum_entity_id": _VAC, "map_id": "6"})
    await hass.async_block_till_done()
    latch = tracker.get_active_run_latch(_VAC)
    assert isinstance(latch, dict) and latch.get("recovered") is True, (
        "a run that wrote no record had its only error evidence auto-cleared"
    )

    hass.bus.async_fire(EVENT_JOB_FINISHED, {
        "vacuum_entity_id": _VAC, "map_id": "6", "job_path": _JOB_PATH,
    })
    await hass.async_block_till_done()
    assert tracker.get_active_run_latch(_VAC) is None, (
        "the control half: a finalize that DID write a record must clear the latch"
    )


async def test_init17_an_active_error_latch_survives_the_end_of_the_job(
    hass, hass_storage, mock_config_entry
):
    """[INIT-17] A latch whose `current_message` is non-empty means the fault is still
    live, and sensor/__init__.py:587-588 states the rule: it is left in place so the
    user still sees the error after the job ends and must acknowledge it themselves.

    THE MESSAGE STRING IS THE ASSERTION, not the latch's presence. "Brush stuck" is a
    value nothing in this module can produce by default, so it cannot be satisfied by a
    latch that was rebuilt or by a default dict. [INIT-5] is the asymmetric twin: a
    BLANK message on the same seeding path and the same successful finalize, asserted to
    clear. Dropping the `not latch.get("current_message")` half of line 602 reddens this
    and leaves [INIT-5] green.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_with_latch(
        {"current_message": "Brush stuck", "recovered": False, "errors": []}
    )
    assert await _setup(hass, mock_config_entry) is True
    tracker = hass.data[DOMAIN][DATA_ERROR_TRACKER]

    hass.bus.async_fire(EVENT_JOB_FINISHED, {
        "vacuum_entity_id": _VAC, "map_id": "6", "job_path": _JOB_PATH,
    })
    await hass.async_block_till_done()

    latch = tracker.get_active_run_latch(_VAC)
    assert isinstance(latch, dict), "an ACTIVE error latch was cleared by the job ending"
    assert latch.get("current_message") == "Brush stuck"


async def test_init18_a_job_finished_event_without_a_map_is_dropped(
    hass, hass_storage, mock_config_entry
):
    """[INIT-18] EVENT_JOB_FINISHED is a public HA bus event, so any automation can fire
    it -- and the integration itself can too: `FINALIZE_LEARNING_JOB_SCHEMA` declares
    `map_id` as vol.Optional (learning/services.py:105), the handler finalizes through
    the RESOLVED map, and the event at :502-514 then fires `str(call.data["map_id"])` --
    the RAW value. A service call with `map_id: ""` on a vacuum whose active map
    resolves therefore finalizes successfully and emits this exact payload: a real
    `job_path` beside a blank map id.

    THE LATCH IS THE OBSERVABLE, and it is what makes the early return more than
    tidiness: the drop happens BEFORE the acknowledge, so a payload that named no map
    cannot clear a latch. The control is the second fire with the map present, which
    clears it -- so the first assertion is not the absence of an effect nothing was
    going to have.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_with_latch(dict(_RECOVERED))
    assert await _setup(hass, mock_config_entry) is True
    tracker = hass.data[DOMAIN][DATA_ERROR_TRACKER]

    hass.bus.async_fire(EVENT_JOB_FINISHED, {
        "vacuum_entity_id": _VAC, "map_id": "", "job_path": _JOB_PATH,
    })
    await hass.async_block_till_done()
    assert isinstance(tracker.get_active_run_latch(_VAC), dict), (
        "an event naming no map was allowed to acknowledge a latch"
    )

    hass.bus.async_fire(EVENT_JOB_FINISHED, {
        "vacuum_entity_id": _VAC, "map_id": "6", "job_path": _JOB_PATH,
    })
    await hass.async_block_till_done()
    assert tracker.get_active_run_latch(_VAC) is None


def test_init19_the_state_write_funnel_skips_an_entity_with_no_hass():
    """[INIT-19] Every callback-driven refresh in this module funnels through
    `_request_entity_state_write`, and the manager's callbacks can arrive from worker
    threads. An entity not (yet) attached to hass must be skipped rather than
    dereferenced -- one detached entity would otherwise take out whichever notification
    channel touched it, for every other entity on it.

    THE PAIR IS 0 AND 1, NOT TWO ZEROS. Asserting only that nothing was scheduled is
    invariant under a funnel that schedules nothing ever; attaching a hass to the SAME
    entity and asserting exactly one scheduled write is what makes the first half mean
    something. Under the named red input (`if hass is False:`) the detached half raises
    AttributeError on `None.loop`.

    The entity is a REAL `EufyVacuumRoomCleaningHistorySensor`, constructed and never
    added, because "has no hass" is a property of the real class's lifecycle -- HA's
    Entity declares `hass` and leaves it unset until `async_add_entities` runs.
    """
    from types import SimpleNamespace

    from custom_components.eufy_vacuum.sensor import _request_entity_state_write
    from custom_components.eufy_vacuum.sensor.room_history import (
        EufyVacuumRoomCleaningHistorySensor,
    )

    entity = EufyVacuumRoomCleaningHistorySensor(
        coordinator_key="k", vacuum_entity_id=_VAC, map_id="6", room_id=1,
        room_data={"room_id": 1, "name": "Kitchen", "enabled": True},
    )
    assert getattr(entity, "hass", None) is None, (
        "precondition: a freshly constructed entity is detached"
    )

    _request_entity_state_write(entity)          # must not raise

    scheduled = []
    entity.hass = SimpleNamespace(
        loop=SimpleNamespace(call_soon_threadsafe=scheduled.append)
    )
    _request_entity_state_write(entity)
    assert len(scheduled) == 1, (
        "the funnel scheduled %d writes for an ATTACHED entity" % len(scheduled)
    )


async def test_init20_one_vacuums_overlay_failure_does_not_abort_the_tick(
    hass, hass_storage, mock_config_entry
):
    """[INIT-20] The 60-second overlay tick warms the map_state_source cache for
    automations and templates. `async_refresh_map_state_source` does real file and
    introspect I/O, so an unreadable or unparsable map file is a live raise -- and the
    comment on line 648 states the property: "never let one vacuum break the tick".

    THE OBSERVABLE IS THE PER-ITERATION TAIL, not the absence of an exception. Line 650
    pushes state to the overlay sensor and runs AFTER the handler, so a caught failure
    still leaves the sensor refreshed while an escaping one aborts the coroutine before
    it. Narrowing the handler to `except KeyError:` lets the RuntimeError out and the
    tail never runs.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_with_latch(dict(_RECOVERED))
    assert await _setup(hass, mock_config_entry) is True

    import custom_components.eufy_vacuum.sensor as sensor_mod

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    written = []

    async def _boom(**kwargs):
        raise RuntimeError("the stored map file is unreadable")

    with patch.object(manager, "async_refresh_map_state_source", _boom), \
            patch.object(sensor_mod, "_request_entity_state_write", written.append):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
        await hass.async_block_till_done()

    assert written, (
        "the refresh raised and took the rest of the tick with it -- the overlay "
        "sensor was never pushed"
    )


async def test_init21_an_unreadable_active_map_falls_back_to_the_stored_one(
    hass, hass_storage, mock_config_entry
):
    """[INIT-21] The tick prefers the LIVE active map and falls back to the first STORED
    one, for the reason the comment gives: otherwise the sensor sticks at
    `present: false` with no cache at all until the active-map entity is ready.

    `get_active_map_id` reads stored data through its own helpers, so it can raise. The
    INNER catch is what keeps the fallback reachable -- narrowed to `except KeyError:`,
    a RuntimeError escapes to the OUTER handler instead and lines 641-647 are skipped
    entirely, so the refresh never happens.

    THE ASSERTION IS THE CALL AND ITS ARGUMENT, not that nothing raised: the stored map
    "6" is what proves the fallback ran, and `("vacuum.alfred", "6")` is a value the
    live path could not have produced here because the live read is the thing raising.
    It is imported INSIDE the tick (sensor/__init__.py:629), so the patch has to land on
    the source module.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_with_latch(dict(_RECOVERED))
    assert await _setup(hass, mock_config_entry) is True

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    refreshed = []

    async def _record(*, vacuum_entity_id, map_id):
        refreshed.append((vacuum_entity_id, map_id))

    def _boom(_hass, _vac):
        raise RuntimeError("the active-map entity is unresolvable")

    with patch("custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
               _boom), \
            patch.object(manager, "async_refresh_map_state_source", _record):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
        await hass.async_block_till_done()

    assert (_VAC, "6") in refreshed, (
        "the live-map failure skipped the stored-map fallback; refreshed=%r" % (refreshed,)
    )


async def test_init22_a_stale_active_job_sensor_is_removed_on_reload(
    hass, hass_storage, mock_config_entry
):
    """[INIT-22] ENT-ORPHAN-1. A per-(vacuum, map) active-job sensor whose map no longer
    exists would otherwise sit in the registry permanently `unavailable` -- found with
    two real orphans on the maintainer's box and reported independently from the 2.1.0
    beta. The sweep's whole body, the log line and the `async_remove`, had never run.

    IT GOES THROUGH A RELOAD because a registry row cannot be linked to a config entry
    hass has not been told about, and `_setup` is what adds it. The removal is the claim:
    replacing `async_remove` with `pass` reddens this.

    THE LIVE-ROW LINE BELOW IS NOT A CHECK ON THE SWEEP, and saying so is the point of
    this paragraph. I expected the reload path to make it one -- by then the first boot
    has created `vacuum_alfred_active_job_6`, so a sweep that over-collected should be
    visible. Measured with `live_pairs=set()`, which classifies EVERY active-job row as
    an orphan: the test stayed green. The sweep does remove the live row, and
    `async_add_entities` (sensor/__init__.py:328) then re-creates the sensor with the
    same unique_id twelve lines later, so the lookup finds it again either way. The
    clause is invariant under the mutation it looks like it would catch, and it is kept
    only as a true statement about the end state.

    The deletion-safety property it resembles -- doc 37 §4, where the naive version of
    this cleanup registry-deleted a SIBLING vacuum's entities, a prefix scan for
    `vacuum.alfred` sweeping everything belonging to `vacuum.alfred_2`, demonstrated
    rather than theorised -- belongs to `orphaned_active_job_unique_ids` itself and is
    held by its own tests, where the forward-built complement can actually be observed.
    """
    from homeassistant.helpers import entity_registry as er

    from custom_components.eufy_vacuum.entity_helpers import active_job_unique_id

    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = _boot_storage_with_latch(dict(_RECOVERED))
    assert await _setup(hass, mock_config_entry) is True

    reg = er.async_get(hass)
    live = active_job_unique_id(vacuum_entity_id=_VAC, map_id="6")
    stale = active_job_unique_id(vacuum_entity_id=_VAC, map_id="99")
    assert reg.async_get_entity_id("sensor", DOMAIN, live) is not None, (
        "precondition: the first boot built the live map's active-job sensor"
    )

    reg.async_get_or_create(
        "sensor", DOMAIN, stale,
        suggested_object_id="alfred_active_job_99", config_entry=mock_config_entry,
    )
    assert reg.async_get_entity_id("sensor", DOMAIN, stale) is not None

    patches = _patch_frontend()
    for p in patches:
        p.start()
    try:
        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    finally:
        for p in patches:
            p.stop()

    assert reg.async_get_entity_id("sensor", DOMAIN, stale) is None, (
        "the active-job sensor for a map that no longer exists was left behind"
    )
    # NOT a check on the sweep -- see the docstring. The sensor is re-created at
    # sensor/__init__.py:328 regardless, so this records the end state only.
    assert reg.async_get_entity_id("sensor", DOMAIN, live) is not None


# ---------------------------------------------------------------------------
# [INIT-23..28] setup paths a healthy boot never reaches
# ---------------------------------------------------------------------------

async def test_init23_storage_that_will_not_initialise_asks_HA_to_RETRY(
    hass, mock_config_entry
):
    """[INIT-23] ConfigEntryNotReady, not a crash and not a half-loaded entry.

    `async_initialize` reads the store. A disk that is busy, a storage file being
    written by something else, a transient permission problem -- none of those are
    permanent, and the contract for "try me again shortly" is ConfigEntryNotReady.
    Raising anything else marks the entry FAILED, which HA does not retry: the user
    then has a broken integration until they restart, over a condition that would
    have cleared on its own.

    THE TEARDOWN IS THE SECOND HALF OF THE CLAIM, and the comment above the raise
    says why: `entry.async_on_unload(manager.async_shutdown)` is registered BEFORE
    `async_initialize` precisely so a failure here still tears down. So this asserts
    the retry state AND that the runtime left nothing behind in hass.data.
    """
    from homeassistant.config_entries import ConfigEntryState

    with patch(
        "custom_components.eufy_vacuum.core.manager.EufyVacuumManager"
        ".async_initialize",
        side_effect=OSError("storage is busy"),
    ):
        ok = await _setup(hass, mock_config_entry)

    assert ok is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY, (
        "state is %r -- anything but SETUP_RETRY means HA will not try again"
        % (mock_config_entry.state,)
    )
    assert not hass.data.get(DOMAIN, {}).get(DATA_RUNTIME), (
        "a manager survived a failed setup; the next attempt would find a "
        "half-built runtime already in place"
    )


async def test_init24_orphaned_icon_selects_from_older_versions_are_removed(
    hass, mock_config_entry
):
    """[INIT-24] The per-room icon pickers were dropped; their registry rows were not.

    The entities were removed when the card stopped surfacing those pickers, but a
    registry entry outlives the entity that made it. HA shows an orphan as
    `unavailable` FOREVER -- it never expires on its own -- so an upgrader is left
    with a row of permanently broken entities per room and no way to tell they are
    ours to clean up.

    The match is on the unique_id prefix the deleted class used. A NEIGHBOUR IS
    SEEDED TOO, with the same platform and a different prefix: without it, a sweep
    that removed every entity this integration owns would pass, and that sweep would
    delete the live select platform -- which is still in use as the debug
    flight-recorder target.
    """
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    orphan = registry.async_get_or_create(
        "select", DOMAIN, "eufy_vacuum_icon_alfred_1",
        suggested_object_id="alfred_room_1_icon",
    )
    keeper = registry.async_get_or_create(
        "select", DOMAIN, "eufy_vacuum_debug_target_alfred",
        suggested_object_id="alfred_debug_target",
    )

    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    assert await _setup(hass, mock_config_entry)

    assert registry.async_get(orphan.entity_id) is None, (
        "the orphaned icon-select survived; it shows as unavailable forever"
    )
    assert registry.async_get(keeper.entity_id) is not None, (
        "the sweep took a live select with it -- that one is the debug "
        "flight-recorder target, not an orphan"
    )


async def test_init25_a_device_that_is_not_ours_is_handed_straight_back(hass):
    """[INIT-25] `async_remove_config_entry_device` guards on BOTH halves.

    Two ways to reach this: a device whose identifiers belong to another
    integration, and our own device at a moment when nothing is loaded (removal
    during or after teardown). Either way the answer is True -- let HA remove it --
    because refusing would leave the user unable to delete a device we are not in a
    position to say anything about.

    Both halves are exercised: the first device is a stranger's, the second is ours
    with no runtime in hass.data.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum import async_remove_config_entry_device

    class _Device:
        def __init__(self, identifiers):
            self.identifiers = identifiers

    entry = MockConfigEntry(domain=DOMAIN, entry_id="init25")
    entry.add_to_hass(hass)

    # not ours at all
    assert await async_remove_config_entry_device(
        hass, entry, _Device({("some_other_integration", "whatever")})
    ) is True

    # ours, but nothing is loaded
    hass.data.pop(DOMAIN, None)
    assert await async_remove_config_entry_device(
        hass, entry, _Device({(DOMAIN, "vacuum_alfred")})
    ) is True


async def test_init26_a_fallback_panel_that_already_exists_is_not_an_error(
    hass, mock_entry_no_vacuum
):
    """[INIT-26] Registering the same panel twice raises ValueError, and that is fine.

    The fallback panel is registered when there is no managed vacuum yet. A reload,
    or a second config entry, finds it already there -- HA answers that with
    ValueError, which is a statement that the panel exists, not that setup failed.
    Letting it propagate would fail the whole entry over a panel that is present and
    working.

    The assertion is that setup still reports LOADED, because the panel is the last
    thing registered and an escaping error would unwind everything before it.
    """
    from homeassistant.config_entries import ConfigEntryState

    await async_setup_component(hass, "http", {})
    mock_entry_no_vacuum.add_to_hass(hass)
    with patch(
        "homeassistant.components.panel_custom.async_register_panel",
        side_effect=ValueError("Overwriting panel vacuum-agent"),
    ), patch("homeassistant.components.frontend.async_remove_panel"):
        ok = await hass.config_entries.async_setup(mock_entry_no_vacuum.entry_id)
        await hass.async_block_till_done()

    assert ok is True
    assert mock_entry_no_vacuum.state is ConfigEntryState.LOADED, (
        "an already-registered panel failed the entry; the user loses the whole "
        "integration over a panel that is present and working"
    )


async def test_init27_an_entry_update_reloads_the_entry(hass, mock_config_entry):
    """[INIT-27] The options listener's only job, and it has to actually reload.

    Settings that change what setup builds -- the managed vacuum, the panel title --
    only take effect on a reload, so the update listener exists to force one. A
    listener that recorded the change without reloading would leave the user looking
    at a saved setting that does nothing until they restart HA.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    assert await _setup(hass, mock_config_entry)

    # autospec, not a bare AsyncMock: the double is built from the real method, so
    # it checks the call SHAPE as well as the fact of the call -- and the mock
    # ratchet in this repo is shrink-only, so a bare one here reddens [MR-2].
    with patch.object(
        hass.config_entries, "async_reload", autospec=True, return_value=True
    ) as reload:
        hass.config_entries.async_update_entry(
            mock_config_entry, options={"panel_title": "Upstairs"}
        )
        await hass.async_block_till_done()

    assert reload.await_count >= 1, "an options change did not trigger a reload"
    assert mock_config_entry.entry_id in reload.await_args[0], (
        "the listener reloaded something other than the entry that changed: %r"
        % (reload.await_args,)
    )


async def test_init28_a_legacy_maintenance_key_is_migrated_and_PERSISTED_on_boot(
    hass, hass_storage, mock_config_entry
):
    """[INIT-28] The interval carry-over has to reach disk, not just memory.

    `rolling_brush` was renamed to `main_brush` in the September 2026
    canonicalisation and never migrated at the time, so a user's custom interval was
    lost. The migration carries it forward on the next load.

    ONLY THE INTERVAL MOVES. Reset timestamps self-heal on the next reset; a
    preference does not, and the old value lives only in .storage, which the user is
    told never to open.

    ⚠ THE CLAIM IS THE MIGRATION, NOT THE SAVE BESIDE IT. Measured: ablating
    `await manager.async_save()` on that branch leaves this test GREEN, because
    setup saves in several other places and the migrated data reaches storage
    anyway. Neutering `migrate_maintenance_component_renames` reddens it exactly.
    So that save is an optimisation on the setup path -- it would only matter if
    nothing else saved before the process ended -- and is crossed here, not claimed.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "maintenance": {_VAC: {
            # the legacy key, carrying a user-set interval and nothing else
            "rolling_brush": {"interval_hours": 250, "reset_at": "2026-01-01T00:00:00+00:00"},
        }},
    }}

    assert await _setup(hass, mock_config_entry)
    await hass.async_block_till_done()

    stored = hass_storage[_STORAGE_KEY]["data"]["maintenance"][_VAC]
    assert (stored.get("main_brush") or {}).get("interval_hours") == 250, (
        "the user's 250 h interval did not reach the renamed component on disk: %r"
        % (stored,)
    )


async def test_init29_records_naming_a_vacuum_this_install_does_not_have_are_swept(
    hass, hass_storage, mock_config_entry
):
    """[INIT-29] The set only ever GREW, which is why a one-shot sweep exists.

    Two of these reached a live install. One is the CARD'S OWN PLACEHOLDER,
    `vacuum.your_vacuum`, persisted because a status query created the very record
    it was asking about; the other was a truncated entity id carrying a whole setup
    record. Individually harmless -- nothing reads them -- but nothing removed them
    either, so every stray query left another one behind.

    THE REAL VACUUM IS SEEDED ALONGSIDE, and that is the assertion that matters. A
    sweep with its predicate inverted, or one that could not tell a real vacuum from
    a placeholder, would delete the user's actual stored record: their maps, their
    room names, their per-room settings. "The placeholder is gone" is satisfied by
    a sweep that removed everything.

    ⚠ THE CLAIM IS THE SWEEP, NOT THE SAVE BENEATH IT. Measured, same as [INIT-28]:
    ablating that `await manager.async_save()` leaves this test green -- setup saves
    elsewhere and the result persists regardless -- while neutering
    `sweep_orphaned_vacuums` reddens it exactly. The save is crossed, not claimed.

    ⚠ THE ORPHAN IS SEEDED INTO `setup_progress`, NOT `vacuums`, AND THAT IS THE
    WHOLE FIXTURE. `is_real_vacuum` accepts "we already have a record for it" as
    proof of realness -- a key in `vacuums`, `maps` or `active_jobs` -- because a
    vacuum renamed or removed in HA must keep its stored history reachable. Written
    with the placeholder in `vacuums`, this test DECLARED IT REAL: the integration
    built its whole entity stack for it (`sensor.your_vacuum_*`, its own sidebar
    panel) and swept nothing. The docstring's second real case is the right shape --
    "a truncated entity id carrying a full SETUP record" -- a record in a bucket
    that confers no identity, with nothing behind it.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}},
        "maps": {_VAC: {"6": {
            "map_id": "6", "metadata": {}, "summary": {},
            "rooms": {"1": {"room_id": 1, "name": "Kitchen", "enabled": True}},
        }}},
        # a full setup record for a vacuum that does not exist and has no identity
        # record behind it -- what a stray status query left on a live install
        "setup_progress": {
            _VAC: {"step": "done"},
            "vacuum.your_vacuum": {"step": "awaiting_map", "attempts": 3},
        },
    }}

    assert await _setup(hass, mock_config_entry)
    await hass.async_block_till_done()

    progress = hass_storage[_STORAGE_KEY]["data"].get("setup_progress") or {}
    assert "vacuum.your_vacuum" not in progress, (
        "the placeholder's setup record survived the sweep and the set keeps "
        "growing: %r" % (progress,)
    )
    assert _VAC in progress, (
        "the sweep took the REAL vacuum's setup record with it"
    )
    assert _VAC in hass_storage[_STORAGE_KEY]["data"]["vacuums"], (
        "the sweep reached the identity record -- that one holds the user's maps, "
        "room names and per-room settings"
    )
    assert hass_storage[_STORAGE_KEY]["data"]["maps"].get(_VAC), (
        "the real vacuum's maps were swept away"
    )


async def test_init30_the_rebaseline_service_with_no_battery_manager_does_nothing(
    hass, mock_config_entry
):
    """[INIT-30] A registered service outliving the thing it drives.

    Services are registered during setup and torn down on unload, but the ordering
    inside a teardown -- or a partially-built runtime -- can leave the service
    callable with `DATA_BATTERY` already gone. Calling it then must return quietly:
    the alternative is an AttributeError surfacing in the user's log from a service
    THEY invoked, with nothing they can do about it.

    The assertion is that the call completes. `blocking=True` means an exception
    inside the handler propagates here, so a handler that reached for `bm.rebaseline`
    on None would fail this test rather than pass silently.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    assert await _setup(hass, mock_config_entry)

    from custom_components.eufy_vacuum.const import DATA_BATTERY

    assert hass.data[DOMAIN].pop(DATA_BATTERY, None) is not None, (
        "the battery manager was not there to remove -- this test would then be "
        "asserting nothing about the guard"
    )

    await hass.services.async_call(
        DOMAIN, "battery_rebaseline", {"vacuum_entity_id": _VAC}, blocking=True
    )
    await hass.async_block_till_done()


async def test_init31_a_panel_that_fails_to_register_unwinds_the_ones_before_it(
    hass, hass_storage, mock_config_entry
):
    """[INIT-31] Mid-setup failure during the panel loop removes the earlier panels.

    Panels are registered one per managed vacuum, and the undo is pushed onto the
    unwind stack BEFORE the loop runs -- so a failure partway through has earlier
    panels to take back. Without that, a retried setup finds the first vacuum's
    panel already registered and the sidebar keeps an entry pointing at an
    integration that did not load.

    TWO VACUUMS, AND THE SECOND REGISTRATION RAISES. One vacuum cannot exercise
    this: the list would be empty when the undo runs, and the test would pass
    against an undo that does nothing. ValueError is deliberately NOT used -- that
    one is caught and tolerated ([INIT-26]); this is the unexpected kind that must
    unwind.

    The assertion is that the FIRST panel was removed by url, which is the only
    observable that distinguishes an unwind from a bail-out.
    """
    from homeassistant.helpers import entity_registry as er

    second = "vacuum.bertie"
    er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "bertie_unique_id", suggested_object_id="bertie"
    )
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass.states.async_set(second, "docked", {"supported_features": 0})
    hass_storage[_STORAGE_KEY] = {"version": 1, "data": {
        "vacuums": {_VAC: {"name": "Alfred"}, second: {"name": "Bertie"}},
    }}

    await async_setup_component(hass, "http", {})
    mock_config_entry.add_to_hass(hass)

    removed: list[str] = []
    calls = {"n": 0}

    async def _register(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("the frontend refused the second panel")

    with patch(
        "homeassistant.components.panel_custom.async_register_panel",
        side_effect=_register,
    ), patch(
        "homeassistant.components.frontend.async_remove_panel",
        side_effect=lambda _hass, url, **kw: removed.append(url),
    ):
        ok = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert ok is False, "setup reported success after a panel registration raised"
    assert removed, (
        "the first panel was left registered; a retry finds it already there and "
        "the sidebar keeps an entry for an integration that did not load"
    )
    assert not hass.data.get(DOMAIN, {}).get(f"_panels_{mock_config_entry.entry_id}"), (
        "the panel marker survived a failed setup"
    )


# [INIT-32] WAS WRITTEN HERE AND REMOVED, 2026-11-10. It asserted that a stored
# capabilities snapshot keyed by pre-rename component ids comes back canonical after
# a boot, and credited `migrate_maintenance_source_keys` for it. ABLATED: with that
# migration neutered to `return {"moved": []}` the test STAYED GREEN -- capability
# re-detection rebuilds `maintenance_sources` during the same setup and converges the
# keys on its own. The tell was there before the ablation: __init__.py:1087, the save
# guarded by `_source_keys["moved"]`, stayed uncovered while the test passed.
# The migration's own behaviour is covered in
# tests/core/test_maintenance_component_rename_migration.py, where nothing else can
# supply the answer. Do not re-add it here without a harness that stops detection.
