"""Sensor platform — orchestrator + entity-sync callbacks.

This package is the HA `sensor` platform. The platform contract function
``async_setup_entry`` lives here; each entity class lives in its own
submodule. HA's loader finds ``sensor/__init__.py`` the same way it
would find ``sensor.py``, so the package layout is transparent to HA.

Per-entity submodules:
- profile.py             EufyVacuumProfileSensor
- maintenance.py         EufyVacuumMaintenanceRemainingSensor
- dock_event.py          EufyVacuumDockEventSensor
- theme.py               EufyVacuumThemeStateSensor
- onboarding.py          EufyVacuumOnboardingSensor
- room_history.py        EufyVacuumRoomCleaningHistorySensor
- room_rule_status.py    EufyVacuumRoomRuleStatusSensor
- error.py               _ErrorTrackerSensorBase + ActiveRunError + LastDeviceError
- lifecycle.py           EufyVacuumActiveJobSensor (per vacuum/map)

The orchestrator wires four manager-callback paths for per-room sensors
(room history sync/refresh, room rule-status sync/refresh), a theme
update path, an EVENT_JOB_FINISHED listener (refreshes room history and
auto-clears recovered error latches), and an hourly safety-net tick.
The battery sensors are built externally by
battery/sensors.py:build_battery_sensors and added to the same
collection.

SN-1 creation hooks: the per-vacuum sensor set and the per-(vacuum, map)
active-job sensor are each built once, in ``_build_vacuum_sensors`` /
the map loop below, at initial platform setup. Two additional callbacks
(``_ensure_vacuum_sensors`` on manager's vacuum-added notification,
``_ensure_map_sensors`` on its room-update notification) build the same
sensors for a vacuum added, or a map imported, AFTER setup has already
run -- without either requiring a reload. Both are idempotent against
``built_vacuum_ids`` / ``built_active_job_map_ids``.
"""

from __future__ import annotations

import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

# All sensors are event-driven; centralised callbacks handle data fetching.
PARALLEL_UPDATES = 0

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from ..adapters.registry import get_adapter_config
from ..battery.sensors import build_battery_sensors
from ..const import DATA_BATTERY, DATA_ERROR_TRACKER, DOMAIN, EVENT_JOB_FINISHED
from ..core.error_tracker import ErrorTracker
from ..entity_helpers import entity_belongs_to, sort_room_items
from .dock_event import EufyVacuumDockEventSensor
from .error import EufyVacuumActiveRunErrorSensor, EufyVacuumLastDeviceErrorSensor
from .lifecycle import EufyVacuumActiveJobSensor
from .maintenance import EufyVacuumMaintenanceRemainingSensor
from .map_overlays import EufyVacuumMapOverlaysSensor
from .onboarding import EufyVacuumOnboardingSensor
from .profile import EufyVacuumProfileSensor
from .room_history import EufyVacuumRoomCleaningHistorySensor
from .room_rule_status import EufyVacuumRoomRuleStatusSensor
from .theme import EufyVacuumThemeStateSensor


def _request_entity_state_write(entity: SensorEntity) -> None:
    """Schedule async_write_ha_state() on the HA event loop.

    Manager callbacks may fire from worker threads; async_write_ha_state() must
    run on the main event loop, so all callback-driven refreshes funnel here.
    """
    hass = getattr(entity, "hass", None)
    if hass is None:
        return

    @callback
    def _write_state() -> None:
        entity.async_write_ha_state()

    hass.loop.call_soon_threadsafe(_write_state)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    manager = hass.data[DOMAIN]["runtime"]

    entities: list[SensorEntity] = []
    room_history_entities: dict[str, SensorEntity] = {}
    room_rule_status_entities: dict[str, SensorEntity] = {}
    theme_sensor_by_vacuum: dict[str, EufyVacuumThemeStateSensor] = {}
    # map_overlays sensor per vacuum — refreshed on a timer (below).
    map_overlays_by_vacuum: dict[str, EufyVacuumMapOverlaysSensor] = {}
    # SN-1: dedup guards for the creation hooks (below) — a vacuum/map that
    # already got its sensors, whether at initial setup or from a prior hook
    # fire, is never rebuilt.
    built_vacuum_ids: set[str] = set()
    built_active_job_map_ids: set[tuple[str, str]] = set()

    def _build_vacuum_sensors(vacuum_entity_id: str) -> list[SensorEntity]:
        """Build every per-vacuum-only sensor.

        Called once per managed vacuum at initial platform setup, and again
        (idempotently, via built_vacuum_ids) from the creation hooks below for
        a vacuum that becomes managed AFTER setup has already run.
        """
        built: list[SensorEntity] = []
        capabilities = manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        # Maintenance components are now adapter-declared per vacuum.
        _adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
        maintenance_components = _adapter_cfg.get("maintenance_components") or {}

        built.append(
            EufyVacuumProfileSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                capabilities=capabilities,
            )
        )

        for component, meta in maintenance_components.items():
            if sources.get(component) is None:
                continue
            built.append(
                EufyVacuumMaintenanceRemainingSensor(
                    manager=manager,
                    vacuum_entity_id=vacuum_entity_id,
                    component=component,
                    label=meta["label"],
                    icon=meta["icon"],
                    default_interval=meta["default_interval_hours"],
                )
            )

        built.append(
            EufyVacuumDockEventSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
            )
        )

        _theme_sensor = EufyVacuumThemeStateSensor(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
        )
        built.append(_theme_sensor)
        theme_sensor_by_vacuum[vacuum_entity_id] = _theme_sensor

        built.append(
            EufyVacuumOnboardingSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
            )
        )

        # Map-overlays sensor — the VA's read of the device's own map as attributes.
        _map_overlays_sensor = EufyVacuumMapOverlaysSensor(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
        )
        built.append(_map_overlays_sensor)
        map_overlays_by_vacuum[vacuum_entity_id] = _map_overlays_sensor

        # Battery health sensors — six per vacuum (cycles + 3 rates +
        # last-charge duration + health %). Backed by BatteryHealthManager.
        battery_manager = hass.data[DOMAIN].get(DATA_BATTERY)
        if battery_manager is not None:
            built.extend(
                build_battery_sensors(
                    manager=battery_manager,
                    vacuum_entity_id=vacuum_entity_id,
                )
            )

        # Active-run + last-device error sensors. Backed by ErrorTracker.
        # The companion binary_sensor.<obj>_active_run_has_error lives on
        # the binary_sensor platform.
        error_tracker: ErrorTracker | None = hass.data[DOMAIN].get(
            DATA_ERROR_TRACKER
        )
        if error_tracker is not None:
            built.append(
                EufyVacuumActiveRunErrorSensor(
                    tracker=error_tracker,
                    vacuum_entity_id=vacuum_entity_id,
                )
            )
            built.append(
                EufyVacuumLastDeviceErrorSensor(
                    tracker=error_tracker,
                    vacuum_entity_id=vacuum_entity_id,
                )
            )

        return built

    # SN-1: the ROSTER of managed vacuums (button.py's sibling pattern), not
    # `maps` — `maps` records only what has been imported, so a vacuum added
    # but not yet mapped used to be silently skipped entirely.
    vacuums = manager.data.get("vacuums", {})
    maps = manager.data.get("maps", {})
    for vacuum_entity_id in vacuums:
        entities.extend(_build_vacuum_sensors(vacuum_entity_id))
        built_vacuum_ids.add(vacuum_entity_id)

        vacuum_maps = maps.get(vacuum_entity_id, {})
        for map_id, map_bucket in vacuum_maps.items():
            # One active-job sensor per (vacuum, map).
            entities.append(
                EufyVacuumActiveJobSensor(
                    manager=manager,
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                )
            )
            built_active_job_map_ids.add((vacuum_entity_id, str(map_id)))

            rooms = map_bucket.get("rooms", {})
            if not isinstance(rooms, dict):
                continue
            for room_id_key, room_data in sort_room_items(rooms):
                entity = EufyVacuumRoomCleaningHistorySensor(
                    coordinator_key="room_history_sensor",
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    room_id=int(room_id_key),
                    room_data=room_data,
                )
                entities.append(entity)
                room_history_entities[entity.unique_id] = entity
                rule_entity = EufyVacuumRoomRuleStatusSensor(
                    coordinator_key="room_rule_status_sensor",
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    room_id=int(room_id_key),
                    room_data=room_data,
                )
                entities.append(rule_entity)
                room_rule_status_entities[rule_entity.unique_id] = rule_entity

    async_add_entities(entities)

    for vacuum_entity_id in vacuums:
        hass.async_create_task(
            manager.async_preload_room_history_cache(
                vacuum_entity_id=vacuum_entity_id,
            )
        )

    def _ensure_vacuum_sensors(*, vacuum_entity_id: str) -> None:
        """SN-1 creation hook: a vacuum added after initial setup (e.g. via
        the Setup panel's add_vacuum, which does not reload the config
        entry) gets its per-vacuum sensors immediately, not on the next
        restart."""
        if vacuum_entity_id in built_vacuum_ids:
            return
        new_entities = _build_vacuum_sensors(vacuum_entity_id)
        built_vacuum_ids.add(vacuum_entity_id)
        if new_entities:
            async_add_entities(new_entities)

    manager.register_vacuum_added_callback(_ensure_vacuum_sensors)
    entry.async_on_unload(
        lambda: manager.unregister_vacuum_added_callback(_ensure_vacuum_sensors)
    )

    def _ensure_map_sensors(*, vacuum_entity_id: str, map_id: str) -> None:
        """SN-1 creation hook: importing a map (save_managed_rooms /
        rebuild_map / reconcile_room all fire the room-update notification)
        gets its active-job sensor immediately. Also covers the per-vacuum
        sensors defensively, in case a vacuum somehow got a map without ever
        going through the vacuum-added hook above."""
        new_entities: list[SensorEntity] = []
        if vacuum_entity_id not in built_vacuum_ids:
            new_entities.extend(_build_vacuum_sensors(vacuum_entity_id))
            built_vacuum_ids.add(vacuum_entity_id)
        map_key = (vacuum_entity_id, str(map_id))
        if map_key not in built_active_job_map_ids:
            new_entities.append(
                EufyVacuumActiveJobSensor(
                    manager=manager,
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                )
            )
            built_active_job_map_ids.add(map_key)
        if new_entities:
            async_add_entities(new_entities)

    manager.register_room_update_callback(_ensure_map_sensors)
    entry.async_on_unload(
        lambda: manager.unregister_room_update_callback(_ensure_map_sensors)
    )

    def _sync_dynamic_entities(
        *,
        entity_dict: dict[str, SensorEntity],
        entity_cls,
        coordinator_key: str,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Shared per-room sensor sync (RP-009 step 3 / DR-SENS-2).

        The history and rule-status syncs were 50-line byte-identical twins that
        had already drifted once; one body means the next fix lands in both.

        THREAD MODEL (A2-CB-5 / SN-7): every state write in this sync routes
        through _request_entity_state_write — manager callbacks may fire from
        worker threads, and async_write_ha_state() must run on the loop. The
        funnel is the single documented convention; a bare
        entity.async_write_ha_state() in a callback is a bug.

        Stale classification is by OWNERSHIP ATTRIBUTES (entity_belongs_to) +
        absence from desired — never by unique_id prefix (RP-009/RF-04:
        DR-SETUP-1 proved the prefix scan deleted a sibling vacuum's entities).
        """
        map_bucket = (
            manager.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        rooms = map_bucket.get("rooms", {})
        if not isinstance(rooms, dict):
            rooms = {}

        desired_entities: dict[str, SensorEntity] = {}
        for room_id_key, room_data in sort_room_items(rooms):
            entity = entity_cls(
                coordinator_key=coordinator_key,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                room_id=int(room_id_key),
                room_data=room_data,
            )
            desired_entities[entity.unique_id] = entity

        stale_ids = [
            unique_id
            for unique_id, ent in list(entity_dict.items())
            if entity_belongs_to(ent, vacuum_entity_id=vacuum_entity_id, map_id=str(map_id))
            and unique_id not in desired_entities
        ]
        _registry = er.async_get(hass)
        for unique_id in stale_ids:
            existing = entity_dict.pop(unique_id, None)
            if existing is not None:
                hass.async_create_task(existing.async_remove())
            entity_id = _registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id:
                _registry.async_remove(entity_id)

        new_entities: list[SensorEntity] = []
        for unique_id, entity in desired_entities.items():
            existing = entity_dict.get(unique_id)
            if existing is not None:
                if existing.room_name != entity.room_name:
                    # SN-4: the freshly built `entity` carries the room's CURRENT
                    # name via _attr_translation_placeholders (set once in
                    # __init__, never refreshed otherwise) -- writing state onto
                    # the STALE `existing` object would never update the
                    # friendly name. Swap the entity object instead. Same
                    # unique_id on both, so the registry entry — and any user
                    # name override — survives the swap; deliberately NOT
                    # calling registry.async_update_entity(name=...), which
                    # would stomp a user override and freeze future
                    # translation updates.
                    entity_dict[unique_id] = entity

                    async def _swap_renamed(_old=existing, _new=entity) -> None:
                        await _old.async_remove()
                        async_add_entities([_new])

                    hass.async_create_task(_swap_renamed())
                    continue
                _request_entity_state_write(existing)
                continue
            entity_dict[unique_id] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    def _refresh_dynamic_entities(
        *,
        entity_dict: dict[str, SensorEntity],
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Push a state refresh to one vacuum/map's sensors (ownership match,
        through the state-write funnel)."""
        for _unique_id, entity in list(entity_dict.items()):
            if entity_belongs_to(entity, vacuum_entity_id=vacuum_entity_id, map_id=str(map_id)):
                _request_entity_state_write(entity)

    def _sync_room_history_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        _sync_dynamic_entities(
            entity_dict=room_history_entities,
            entity_cls=EufyVacuumRoomCleaningHistorySensor,
            coordinator_key="room_history_sensor",
            vacuum_entity_id=vacuum_entity_id, map_id=map_id,
        )

    def _refresh_room_history_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        _refresh_dynamic_entities(
            entity_dict=room_history_entities,
            vacuum_entity_id=vacuum_entity_id, map_id=map_id,
        )

    def _sync_room_rule_status_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        _sync_dynamic_entities(
            entity_dict=room_rule_status_entities,
            entity_cls=EufyVacuumRoomRuleStatusSensor,
            coordinator_key="room_rule_status_sensor",
            vacuum_entity_id=vacuum_entity_id, map_id=map_id,
        )

    def _refresh_room_rule_status_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        _refresh_dynamic_entities(
            entity_dict=room_rule_status_entities,
            vacuum_entity_id=vacuum_entity_id, map_id=map_id,
        )

    manager.register_room_update_callback(_sync_room_history_entities)
    entry.async_on_unload(
        lambda: manager.unregister_room_update_callback(_sync_room_history_entities)
    )
    manager.register_room_update_callback(_sync_room_rule_status_entities)
    entry.async_on_unload(
        lambda: manager.unregister_room_update_callback(_sync_room_rule_status_entities)
    )
    manager.register_room_history_update_callback(_refresh_room_history_entities)
    entry.async_on_unload(
        lambda: manager.unregister_room_history_update_callback(
            _refresh_room_history_entities
        )
    )
    manager.register_room_rule_status_update_callback(_refresh_room_rule_status_entities)
    entry.async_on_unload(
        lambda: manager.unregister_room_rule_status_update_callback(
            _refresh_room_rule_status_entities
        )
    )

    def _refresh_theme_entities(*, vacuum_entity_id: str | None = None) -> None:
        """Push a state refresh to the theme sensor(s) for one or all vacuums."""
        targets = (
            [theme_sensor_by_vacuum[vacuum_entity_id]]
            if vacuum_entity_id and vacuum_entity_id in theme_sensor_by_vacuum
            else list(theme_sensor_by_vacuum.values())
        )
        for entity in targets:
            _request_entity_state_write(entity)

    manager.register_theme_update_callback(_refresh_theme_entities)
    entry.async_on_unload(
        lambda: manager.unregister_theme_update_callback(_refresh_theme_entities)
    )

    @callback
    def _handle_job_finished(event) -> None:
        """Handle job-finished: refresh history sensors and auto-clear recovered error latch."""
        data = event.data if isinstance(event.data, dict) else {}
        vacuum_entity_id = str(data.get("vacuum_entity_id", "")).strip()
        map_id = str(data.get("map_id", "")).strip()
        if not (vacuum_entity_id and map_id):
            return

        _refresh_room_history_entities(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        # Auto-clear a recovered (sticky) error latch when the job ends.
        # A latch in "recovered" state means current_message is blank but the
        # latch dict exists — the error cleared mid-run and no new error fired.
        # An "active" latch (current_message non-empty) is left in place so the
        # user still sees the error after the job ends and must acknowledge it.
        # ONLY when a record was actually written. EVENT_JOB_FINISHED also fires on paths
        # where the finalize RAISED (a cancel still marks the job finalized and fires the
        # event with finalize_result=None) — and on those paths the latch was deliberately
        # NOT harvested, so it is the run's only surviving error evidence. Clearing it here
        # discarded exactly what the peek/commit split exists to preserve: the commit keeps
        # the latch when the record write fails, and this door then threw it away anyway.
        #
        # `job_path` is present only on a successful finalize, so it is the cheapest honest
        # proof that the record landed and the latch is genuinely spent.
        _finalized_ok = bool(str((data or {}).get("job_path") or "").strip())
        _error_tracker = hass.data[DOMAIN].get(DATA_ERROR_TRACKER)
        if _finalized_ok and _error_tracker is not None:
            latch = _error_tracker.get_active_run_latch(vacuum_entity_id)
            if isinstance(latch, dict) and not latch.get("current_message"):
                _error_tracker.acknowledge(vacuum_entity_id, scope="active_run")

    unsub_job_finished = hass.bus.async_listen(EVENT_JOB_FINISHED, _handle_job_finished)
    entry.async_on_unload(unsub_job_finished)

    @callback
    def _handle_hourly_refresh(_now) -> None:
        """Push hourly state refresh to all room history sensors."""
        for entity in list(room_history_entities.values()):
            _request_entity_state_write(entity)

    unsub_hourly = async_track_time_interval(
        hass,
        _handle_hourly_refresh,
        timedelta(hours=1),
    )
    entry.async_on_unload(unsub_hourly)

    async def _refresh_map_overlays(_now=None) -> None:
        """Pre-warm the map_state_source cache + push state to the overlay sensors.

        The dashboard snapshot warms the cache when the card is open; this timer keeps
        it fresh for automations/templates when it isn't. The Eufy read is mtime-cached
        (cheap when unchanged) and the Roborock introspect is in-memory, so a modest
        cadence is fine. Per-vacuum failures are isolated.
        """
        from ..rooms.room_discovery import get_active_map_id

        for vac, entity in map_overlays_by_vacuum.items():
            try:
                # Prefer the live active map; fall back to the first STORED map so the
                # cache warms even before the active-map entity is ready / when it's
                # unresolvable (else the sensor sticks at present:false with no cache).
                map_id = None
                try:
                    map_id = get_active_map_id(hass, vac)
                except Exception:  # noqa: BLE001
                    map_id = None
                if not map_id:
                    vac_maps = manager.data.get("maps", {}).get(vac, {})
                    map_id = next(iter(vac_maps), None)
                if map_id:
                    await manager.async_refresh_map_state_source(
                        vacuum_entity_id=vac, map_id=map_id,
                    )
            except Exception:  # noqa: BLE001 - never let one vacuum break the tick
                _LOGGER.debug("map_overlays refresh failed for %s", vac, exc_info=True)
            _request_entity_state_write(entity)

    # Initial warm shortly after setup, then on a steady cadence.
    hass.async_create_task(_refresh_map_overlays())
    unsub_map_overlays = async_track_time_interval(
        hass,
        _refresh_map_overlays,
        timedelta(seconds=60),
    )
    entry.async_on_unload(unsub_map_overlays)
