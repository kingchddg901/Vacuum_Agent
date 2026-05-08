"""Sensor platform for Eufy Vacuum Manager — profile, maintenance, dock event, theme, onboarding, and per-room sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .battery.sensors import build_battery_sensors
from .const import DATA_BATTERY, DOMAIN, EVENT_JOB_FINISHED
from .core.capabilities import MAINTENANCE_COMPONENTS
from .entity_helpers import sort_room_items
from .entity_helpers import build_entity_name
from .profiles.room_profiles import get_available_profiles
from .room_entities import EufyVacuumRoomEntity


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

    maps = manager.data.get("maps", {})
    for vacuum_entity_id in maps.keys():
        capabilities = manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})

        entities.append(
            EufyVacuumProfileSensor(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                capabilities=capabilities,
            )
        )

        for component, meta in MAINTENANCE_COMPONENTS.items():
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

        vacuum_maps = maps.get(vacuum_entity_id, {})
        for map_id, map_bucket in vacuum_maps.items():
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
        """Refresh room history sensors when a vacuum job finishes."""
        data = event.data if isinstance(event.data, dict) else {}
        vacuum_entity_id = str(data.get("vacuum_entity_id", "")).strip()
        map_id = str(data.get("map_id", "")).strip()
        if vacuum_entity_id and map_id:
            _refresh_room_history_entities(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
            )

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


class EufyVacuumProfileSensor(SensorEntity):
    """Sensor reporting the count and details of available cleaning profiles for a vacuum."""

    def __init__(
        self,
        *,
        manager,
        vacuum_entity_id: str,
        capabilities: dict[str, Any],
    ) -> None:
        """Initialize sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._capabilities = capabilities

        self._attr_name = build_entity_name(
            vacuum_entity_id,
            "Available Profiles",
        )
        self._attr_unique_id = f"{vacuum_entity_id}_available_profiles"

    @property
    def native_value(self) -> str:
        """Return the number of available profiles as a string."""
        profiles = self._get_profiles()
        return str(len(profiles))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return profile names, labels, and capability flags."""
        profiles = self._get_profiles()

        return {
            "profile_count": len(profiles),
            "profiles": profiles,
            "profile_labels": {
                key: value.get("label", key)
                for key, value in profiles.items()
            },
            "supports_mop_features": self._capabilities.get("supports_mop_features", False),
            "supports_water_control": self._capabilities.get("supports_water_control", False),
            "capability_filtered": True,
        }

    def _get_profiles(self) -> dict[str, Any]:
        """Return profiles filtered by this vacuum's capabilities."""
        stored_profiles = self._manager.data.get("profiles", {}).get("room_profiles", {})

        return get_available_profiles(
            capabilities=self._capabilities,
            stored_profiles=stored_profiles,
        )


class EufyVacuumMaintenanceRemainingSensor(SensorEntity):
    """Remaining maintenance hours for one vacuum component.

    Computes: interval - (current_usage_hours - reset_snapshot).
    Reads usage_hours live from the source entity mapped in capabilities.
    """

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
        component: str,
        label: str,
        icon: str,
        default_interval: float,
    ) -> None:
        """Initialize maintenance remaining sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._component = component
        self._default_interval = default_interval

        self._attr_name = build_entity_name(
            vacuum_entity_id,
            f"{label} Maintenance Remaining",
        )
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{component}_maintenance_remaining"
        )
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = "h"
        self._attr_state_class = "measurement"
        self._attr_device_class = "duration"

    def _get_interval(self) -> float:
        """Return the current configured interval from storage."""
        maintenance = self._manager.data.get("maintenance", {})
        component_data = maintenance.get(self._vacuum_entity_id, {}).get(
            self._component, {}
        )
        raw = component_data.get("interval_hours")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
        return self._default_interval

    @property
    def native_value(self) -> float:
        """Return remaining hours."""
        interval = self._get_interval()
        result = self._manager.get_maintenance_remaining(
            vacuum_entity_id=self._vacuum_entity_id,
            component=self._component,
            interval_hours=interval,
        )
        return result["remaining_hours"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed maintenance state."""
        interval = self._get_interval()
        result = self._manager.get_maintenance_remaining(
            vacuum_entity_id=self._vacuum_entity_id,
            component=self._component,
            interval_hours=interval,
        )
        return {
            "component": self._component,
            "used_since_reset_hours": result["used_since_reset_hours"],
            "interval_hours": result["interval_hours"],
            "current_usage_hours": result["current_usage_hours"],
            "reset_at_usage_hours": result["reset_at_usage_hours"],
            "reset_at": result["reset_at"],
            "source_entity": result["source_entity"],
            "source_available": result["source_available"],
        }

class EufyVacuumDockEventSensor(SensorEntity):
    """Sensor exposing dock event timestamps (wash, dust empty, dry).

    State = timestamp of the most recent dock event of any type.
    All individual event timestamps and the last dry duration are
    exposed as attributes so the card can read each one independently.
    """

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
    ) -> None:
        """Initialize dock event sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id

        self._attr_name = build_entity_name(vacuum_entity_id, "Dock Events")
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_dock_events"
        )
        self._attr_icon = "mdi:dock-window"

    def _get_events(self) -> dict[str, str | None]:
        """Return stored dock events for this vacuum."""
        return self._manager.get_dock_events(
            vacuum_entity_id=self._vacuum_entity_id,
        )

    @property
    def native_value(self) -> str | None:
        """Return the most recent dock event timestamp across all types."""
        events = self._get_events()
        timestamps = [
            v
            for k, v in events.items()
            if k in {"last_mop_wash", "last_dust_empty", "last_dry_start"}
            and v is not None
        ]
        return max(timestamps) if timestamps else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all dock event timestamps and dry duration."""
        events = self._get_events()
        return {
            "last_mop_wash": events.get("last_mop_wash"),
            "last_dust_empty": events.get("last_dust_empty"),
            "last_dry_start": events.get("last_dry_start"),
            "last_dry_duration": events.get("last_dry_duration"),
            "vacuum_entity_id": self._vacuum_entity_id,
        }


class EufyVacuumThemeStateSensor(SensorEntity):
    """Exposes the active theme name and draft state for one vacuum.

    State   = active theme name, or 'none' if no theme is selected.
    Attributes expose everything the card needs to drive the theme browser
    and draft editor without needing to call a service just to read state.
    """

    _attr_should_poll = False

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
    ) -> None:
        """Initialize theme state sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id

        self._attr_name = build_entity_name(vacuum_entity_id, "Theme State")
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_theme_state"
        )
        self._attr_icon = "mdi:palette"

    def _get_vac_theme(self) -> dict[str, Any]:
        """Return per-vacuum theme state safely."""
        theme = self._manager.data.get("theme", {})
        return theme.get("vacuums", {}).get(
            self._vacuum_entity_id,
            {
                "active_theme_id": None,
                "working_draft": {"tokens": {}, "colors": {}, "alpha": {}},
                "draft_dirty": False,
                "editor_mode": "live",
            },
        )

    def _get_theme_library(self) -> dict[str, Any]:
        """Return the global theme library."""
        return self._manager.data.get("theme", {}).get("library", {})

    @property
    def native_value(self) -> str:
        """Return active theme name, or 'none'."""
        vac = self._get_vac_theme()
        active_id = vac.get("active_theme_id")
        if not active_id:
            return "none"
        library = self._get_theme_library()
        entry = library.get(active_id)
        if entry is None:
            return "none"
        return str(entry.get("name", "none"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full theme state for card consumption."""
        vac = self._get_vac_theme()
        library = self._get_theme_library()
        theme_root = self._manager.data.get("theme", {})

        library_summary = [
            {"id": tid, "theme_id": tid, "name": t.get("name", "")}
            for tid, t in library.items()
        ]

        return {
            "active_theme_id": vac.get("active_theme_id"),
            "draft_dirty": bool(vac.get("draft_dirty", False)),
            "editor_mode": vac.get("editor_mode", "live"),
            "working_draft": vac.get("working_draft", {"tokens": {}, "colors": {}, "alpha": {}}),
            "library_count": len(library),
            "library_summary": library_summary,
            "default_theme_id": theme_root.get("default_theme_id"),
            "vacuum_entity_id": self._vacuum_entity_id,
        }


class EufyVacuumOnboardingSensor(SensorEntity):
    """Exposes onboarding status across all maps for one vacuum.

    State   = 'complete' | 'floor_type_needed' | 'rooms_needed'
              (worst-case status across all known maps)
    Attributes expose per-map detail so the card can guide the user.
    """

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
    ) -> None:
        """Initialize onboarding sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id

        self._attr_name = build_entity_name(vacuum_entity_id, "Onboarding State")
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_onboarding_state"
        )
        self._attr_icon = "mdi:clipboard-check-outline"

    def _get_summary(self) -> dict[str, Any]:
        """Return the onboarding summary dict from the manager."""
        return self._manager.get_rooms_onboarding_summary(
            vacuum_entity_id=self._vacuum_entity_id,
        )

    @property
    def native_value(self) -> str:
        """Return the worst-case status across all maps (rooms_needed > floor_type_needed > complete)."""
        summary = self._get_summary()
        for map_state in summary.get("maps", []):
            if map_state.get("status") == "rooms_needed":
                return "rooms_needed"
        for map_state in summary.get("maps", []):
            if map_state.get("status") == "floor_type_needed":
                return "floor_type_needed"
        return "complete"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return per-map onboarding detail."""
        summary = self._get_summary()
        return {
            "all_complete": summary.get("all_complete", False),
            "vacuum_entity_id": self._vacuum_entity_id,
            "maps": summary.get("maps", []),
        }


class EufyVacuumRoomCleaningHistorySensor(EufyVacuumRoomEntity, SensorEntity):
    """Per-room cleaning history sensor for automation and rules."""

    _attr_icon = "mdi:history"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator_key: str,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_data: dict[str, Any],
    ) -> None:
        """Initialize room history sensor."""
        super().__init__(
            coordinator_key=coordinator_key,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=room_id,
            room_data=room_data,
            label="Cleaning History",
            unique_suffix="cleaning_history",
        )

    def _get_history(self) -> dict[str, Any]:
        """Return current room cleaning history from the manager."""
        return self.manager.get_room_cleaning_history(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
        )

    @property
    def native_value(self) -> str | None:
        """Return the timestamp of the last completed cleaning for this room."""
        return self._get_history().get("last_cleaned_at")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return room history fields useful for HA automations and rules."""
        history = self._get_history()
        return {
            **super().extra_state_attributes,
            "last_cleaned_at": history.get("last_cleaned_at"),
            "last_vacuumed_at": history.get("last_vacuumed_at"),
            "last_mopped_at": history.get("last_mopped_at"),
            "hours_since_last_vacuum": history.get("hours_since_last_vacuum"),
            "hours_since_last_mop": history.get("hours_since_last_mop"),
            "last_job_mode": history.get("last_job_mode"),
        }


class EufyVacuumRoomRuleStatusSensor(EufyVacuumRoomEntity, SensorEntity):
    """Per-room last rule/preflight evaluation report sensor."""

    _attr_icon = "mdi:clipboard-text-clock-outline"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator_key: str,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_data: dict[str, Any],
    ) -> None:
        """Initialize room rule-status sensor."""
        super().__init__(
            coordinator_key=coordinator_key,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=room_id,
            room_data=room_data,
            label="Rule Status",
            unique_suffix="rule_status",
        )

    def _get_rule_status(self) -> dict[str, Any]:
        """Return the latest stored rule/preflight evaluation status."""
        return self.manager.get_room_rule_status(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
        )

    @property
    def native_value(self) -> str:
        """Return the last evaluation result for this room."""
        return str(self._get_rule_status().get("last_result", "never"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full rule/preflight evaluation detail for automation reporting."""
        status = self._get_rule_status()
        return {
            **super().extra_state_attributes,
            "last_evaluated_at": status.get("last_evaluated_at"),
            "last_result": status.get("last_result"),
            "last_selected": status.get("last_selected"),
            "last_included": status.get("last_included"),
            "last_block_reason": status.get("last_block_reason"),
            "last_block_source": status.get("last_block_source"),
            "last_blocked_by_room_id": status.get("last_blocked_by_room_id"),
            "last_blocked_by_room_name": status.get("last_blocked_by_room_name"),
            "last_triggered_rule_ids": status.get("last_triggered_rule_ids"),
            "last_modifier_changes": status.get("last_modifier_changes"),
            "last_requires_confirmation": status.get("last_requires_confirmation"),
            "last_preflight_reason": status.get("last_preflight_reason"),
            "last_warning_codes": status.get("last_warning_codes"),
            "last_evaluation_scope": status.get("last_evaluation_scope"),
        }


