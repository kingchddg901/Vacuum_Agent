"""Switch platform for Eufy Vacuum Manager — per-room enabled/disabled switches."""

from __future__ import annotations

from typing import Any

# Room switches write directly to manager storage via callbacks; no polling.
PARALLEL_UPDATES = 0

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .entity_helpers import sort_room_items
from .room_entities import EufyVacuumRoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up room switches."""
    manager = hass.data[DOMAIN]["runtime"]
    entities: list[SwitchEntity] = []
    entity_map: dict[str, EufyVacuumRoomEnabledSwitch] = {}

    maps = manager.data.get("maps", {})
    for vacuum_entity_id, vacuum_maps in maps.items():
        for map_id, map_bucket in vacuum_maps.items():
            rooms = map_bucket.get("rooms", {})
            for room_id_key, room_data in sort_room_items(rooms):
                entity = EufyVacuumRoomEnabledSwitch(
                    coordinator_key=entry.entry_id,
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    room_id=int(room_id_key),
                    room_data=room_data,
                )
                entities.append(entity)
                entity_map[entity.unique_id] = entity

    async_add_entities(entities)

    def _on_rooms_updated(*, vacuum_entity_id: str, map_id: str) -> None:
        """Add new and remove stale room switches when the room list changes."""
        map_bucket = (
            manager.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        rooms = map_bucket.get("rooms", {})

        desired: dict[str, EufyVacuumRoomEnabledSwitch] = {}
        for room_id_key, room_data in sort_room_items(rooms):
            entity = EufyVacuumRoomEnabledSwitch(
                coordinator_key=entry.entry_id,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                room_id=int(room_id_key),
                room_data=room_data,
            )
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
            entity_id = _registry.async_get_entity_id("switch", DOMAIN, uid)
            if entity_id:
                _registry.async_remove(entity_id)

        new_entities: list[SwitchEntity] = []
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


class EufyVacuumRoomEnabledSwitch(EufyVacuumRoomEntity, SwitchEntity):
    """Switch that enables or disables a room for the next cleaning run."""

    _attr_translation_key = "room_selected"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize enabled switch."""
        super().__init__(unique_suffix="enabled", **kwargs)

    @property
    def is_on(self) -> bool:
        """Return current enabled state."""
        return bool(self._get_room_data().get("enabled", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the room."""
        await self._async_update_room({"enabled": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the room."""
        await self._async_update_room({"enabled": False})