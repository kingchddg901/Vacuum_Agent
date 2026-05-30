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
"""

from __future__ import annotations

from datetime import timedelta

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
from ..entity_helpers import sort_room_items
from .dock_event import EufyVacuumDockEventSensor
from .error import EufyVacuumActiveRunErrorSensor, EufyVacuumLastDeviceErrorSensor
from .lifecycle import EufyVacuumActiveJobSensor
from .maintenance import EufyVacuumMaintenanceRemainingSensor
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
    # active_job_entities keyed by (vacuum_entity_id, map_id) so the
    # job-finished handler can refresh the right sensor directly.
    active_job_entities: dict[tuple[str, str], EufyVacuumActiveJobSensor] = {}

    maps = manager.data.get("maps", {})
    for vacuum_entity_id in maps.keys():
        capabilities = manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        # Maintenance components are now adapter-declared per vacuum.
        _adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
        maintenance_components = _adapter_cfg.get("maintenance_components") or {}

        entities.append(
            EufyVacuumProfileSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                capabilities=capabilities,
            )
        )

        for component, meta in maintenance_components.items():
            if sources.get(component) is None:
                continue
            entities.append(
                EufyVacuumMaintenanceRemainingSensor(
                    manager=manager,
                    vacuum_entity_id=vacuum_entity_id,
                    component=component,
                    label=meta["label"],
                    icon=meta["icon"],
                    default_interval=meta["default_interval_hours"],
                )
            )

        entities.append(
            EufyVacuumDockEventSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
            )
        )

        _theme_sensor = EufyVacuumThemeStateSensor(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
        )
        entities.append(_theme_sensor)
        theme_sensor_by_vacuum[vacuum_entity_id] = _theme_sensor

        entities.append(
            EufyVacuumOnboardingSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
            )
        )

        # Battery health sensors — six per vacuum (cycles + 3 rates +
        # last-charge duration + health %). Backed by BatteryHealthManager.
        battery_manager = hass.data[DOMAIN].get(DATA_BATTERY)
        if battery_manager is not None:
            entities.extend(
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
            entities.append(
                EufyVacuumActiveRunErrorSensor(
                    tracker=error_tracker,
                    vacuum_entity_id=vacuum_entity_id,
                )
            )
            entities.append(
                EufyVacuumLastDeviceErrorSensor(
                    tracker=error_tracker,
                    vacuum_entity_id=vacuum_entity_id,
                )
            )

        vacuum_maps = maps.get(vacuum_entity_id, {})
        for map_id, map_bucket in vacuum_maps.items():
            # One active-job sensor per (vacuum, map).
            _active_job_sensor = EufyVacuumActiveJobSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            entities.append(_active_job_sensor)
            active_job_entities[(vacuum_entity_id, str(map_id))] = _active_job_sensor

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

    for vacuum_entity_id in maps.keys():
        hass.async_create_task(
            manager.async_preload_room_history_cache(
                vacuum_entity_id=vacuum_entity_id,
            )
        )

    def _sync_room_history_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        """Add new and remove stale room cleaning history sensors for one vacuum/map."""
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
            entity = EufyVacuumRoomCleaningHistorySensor(
                coordinator_key="room_history_sensor",
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                room_id=int(room_id_key),
                room_data=room_data,
            )
            desired_entities[entity.unique_id] = entity

        prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id}_"

        stale_ids = [
            unique_id
            for unique_id in list(room_history_entities.keys())
            if unique_id.startswith(prefix) and unique_id not in desired_entities
        ]
        _registry = er.async_get(hass)
        for unique_id in stale_ids:
            existing = room_history_entities.pop(unique_id, None)
            if existing is not None:
                hass.async_create_task(existing.async_remove())
            entity_id = _registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id:
                _registry.async_remove(entity_id)

        new_entities: list[SensorEntity] = []
        for unique_id, entity in desired_entities.items():
            existing = room_history_entities.get(unique_id)
            if existing is not None:
                _request_entity_state_write(existing)
                continue
            room_history_entities[unique_id] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    def _refresh_room_history_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        """Push a state refresh to all history sensors for one vacuum/map."""
        prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id}_"
        for unique_id, entity in list(room_history_entities.items()):
            if unique_id.startswith(prefix):
                _request_entity_state_write(entity)

    def _sync_room_rule_status_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        """Add new and remove stale room rule-status sensors for one vacuum/map."""
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
            entity = EufyVacuumRoomRuleStatusSensor(
                coordinator_key="room_rule_status_sensor",
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                room_id=int(room_id_key),
                room_data=room_data,
            )
            desired_entities[entity.unique_id] = entity

        prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id}_"
        stale_ids = [
            unique_id
            for unique_id in list(room_rule_status_entities.keys())
            if unique_id.startswith(prefix) and unique_id not in desired_entities
        ]
        _registry = er.async_get(hass)
        for unique_id in stale_ids:
            existing = room_rule_status_entities.pop(unique_id, None)
            if existing is not None:
                hass.async_create_task(existing.async_remove())
            entity_id = _registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id:
                _registry.async_remove(entity_id)

        new_entities: list[SensorEntity] = []
        for unique_id, entity in desired_entities.items():
            existing = room_rule_status_entities.get(unique_id)
            if existing is not None:
                _request_entity_state_write(existing)
                continue
            room_rule_status_entities[unique_id] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    def _refresh_room_rule_status_entities(*, vacuum_entity_id: str, map_id: str) -> None:
        """Push a state refresh to all rule-status sensors for one vacuum/map."""
        prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id}_"
        for unique_id, entity in list(room_rule_status_entities.items()):
            if unique_id.startswith(prefix):
                _request_entity_state_write(entity)

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
        _error_tracker = hass.data[DOMAIN].get(DATA_ERROR_TRACKER)
        if _error_tracker is not None:
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
