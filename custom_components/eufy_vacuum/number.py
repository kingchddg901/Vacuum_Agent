"""Number platform for Eufy Vacuum Manager — room order and maintenance interval numbers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .adapters.registry import get_adapter_config
from .const import DOMAIN
from .entity_helpers import build_vacuum_device_info, sort_room_items
from .room_entities import EufyVacuumRoomEntity


MAINTENANCE_INTERVAL_MIN = 1.0
MAINTENANCE_INTERVAL_MAX = 500.0
MAINTENANCE_INTERVAL_STEP = 0.5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    manager = hass.data[DOMAIN]["runtime"]
    entities: list[NumberEntity] = []
    entity_map: dict[str, NumberEntity] = {}

    vacuums = manager.data.get("vacuums", {})
    for vacuum_entity_id in vacuums:
        capabilities = manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        # Maintenance components are now adapter-declared per vacuum.
        _adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
        maintenance_components = _adapter_cfg.get("maintenance_components") or {}

        for component, meta in maintenance_components.items():
            if sources.get(component) is None:
                continue

            entity = EufyVacuumMaintenanceIntervalNumber(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                component=component,
                label=meta["label"],
                icon=meta["icon"],
                default_interval=meta["default_interval_hours"],
            )
            entities.append(entity)
            entity_map[entity.unique_id] = entity

    maps = manager.data.get("maps", {})
    for vacuum_entity_id, vacuum_maps in maps.items():
        for map_id, map_bucket in vacuum_maps.items():
            rooms = map_bucket.get("rooms", {})
            for room_id_key, room_data in sort_room_items(rooms):
                built = _build_room_numbers(
                    entry=entry,
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    room_id=int(room_id_key),
                    room_data=room_data,
                )
                entities.extend(built)
                for entity in built:
                    entity_map[entity.unique_id] = entity

    async_add_entities(entities)

    def _on_rooms_updated(*, vacuum_entity_id: str, map_id: str) -> None:
        """Add new and remove stale room number entities when the room list changes."""
        map_bucket = (
            manager.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        rooms = map_bucket.get("rooms", {})

        desired: dict[str, NumberEntity] = {}
        for room_id_key, room_data in sort_room_items(rooms):
            for entity in _build_room_numbers(
                entry=entry,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                room_id=int(room_id_key),
                room_data=room_data,
            ):
                desired[entity.unique_id] = entity

        prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id}_"
        stale_ids = [
            uid for uid in list(entity_map.keys())
            if uid.startswith(prefix) and uid not in desired
        ]
        _registry = er.async_get(hass)
        for uid in stale_ids:
            stale = entity_map.pop(uid, None)
            if stale is not None:
                hass.async_create_task(stale.async_remove())
            entity_id = _registry.async_get_entity_id("number", DOMAIN, uid)
            if entity_id:
                _registry.async_remove(entity_id)

        new_entities: list[NumberEntity] = []
        for uid, entity in desired.items():
            existing = entity_map.get(uid)
            if existing is not None:
                existing.async_write_ha_state()
            else:
                entity_map[uid] = entity
                new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    manager.register_room_update_callback(_on_rooms_updated)
    entry.async_on_unload(
        lambda: manager.unregister_room_update_callback(_on_rooms_updated)
    )


def _build_room_numbers(
    *,
    entry: ConfigEntry,
    vacuum_entity_id: str,
    map_id: str,
    room_id: int,
    room_data: dict,
) -> list[NumberEntity]:
    """Build number entities for one room."""
    return [
        EufyVacuumRoomOrderNumber(
            coordinator_key=entry.entry_id,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=room_id,
            room_data=room_data,
        ),
    ]


class EufyVacuumRoomOrderNumber(EufyVacuumRoomEntity, NumberEntity):
    """Number entity that controls the cleaning queue position of a room."""

    _attr_translation_key = "room_order"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize order number."""
        super().__init__(unique_suffix="order", **kwargs)

        self._attr_native_min_value = 0
        self._attr_native_max_value = 999
        self._attr_native_step = 1
        self._attr_mode = "box"

    @property
    def native_value(self) -> float:
        """Return the room's current queue position."""
        return float(self._get_room_data().get("order", 0))

    async def async_set_native_value(self, value: float) -> None:
        """Persist a new queue position for this room."""
        await self._async_update_room({"order": int(value)})


class EufyVacuumMaintenanceIntervalNumber(NumberEntity):
    """Configurable maintenance interval (hours) for one vacuum component."""

    _attr_has_entity_name = True
    _attr_translation_key = "maintenance_interval"

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
        """Initialize maintenance interval number."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._component = component
        self._label = label
        self._default_interval = default_interval
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{component}_maintenance_interval"
        )
        self._attr_icon = icon
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        self._attr_native_min_value = MAINTENANCE_INTERVAL_MIN
        self._attr_native_max_value = MAINTENANCE_INTERVAL_MAX
        self._attr_native_step = MAINTENANCE_INTERVAL_STEP
        self._attr_native_unit_of_measurement = "h"
        self._attr_mode = "box"

    @property
    def name_placeholders(self) -> dict[str, str]:
        """Return the component name placeholder for the translation key."""
        return {"component": self._label}

    def _get_stored_interval(self) -> float:
        """Return persisted interval or the default."""
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
        """Return current interval."""
        return self._get_stored_interval()

    async def async_set_native_value(self, value: float) -> None:
        """Persist new interval."""
        self._manager.data.setdefault("maintenance", {})
        self._manager.data["maintenance"].setdefault(self._vacuum_entity_id, {})
        self._manager.data["maintenance"][self._vacuum_entity_id].setdefault(
            self._component, {}
        )
        self._manager.data["maintenance"][self._vacuum_entity_id][self._component][
            "interval_hours"
        ] = round(value, 1)
        await self._manager.async_save()