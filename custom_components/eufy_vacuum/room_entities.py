"""Shared room entity base classes for Eufy Vacuum Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import Entity

from .adapters.registry import get_adapter_config
from .entity_helpers import build_vacuum_device_info, make_room_unique_id


class EufyVacuumRoomEntity(Entity):
    """Base entity for a managed room."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator_key: str,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_data: dict[str, Any],
        label: str,
        unique_suffix: str,
    ) -> None:
        """Initialize room entity."""
        self._coordinator_key = coordinator_key
        self._vacuum_entity_id = vacuum_entity_id
        self._map_id = str(map_id)
        self._room_id = int(room_id)
        self._room_name = str(room_data.get("name", f"Room {room_id}"))
        self._room_slug = room_data.get("slug")

        self._attr_unique_id = make_room_unique_id(
            vacuum_entity_id=vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
            suffix=unique_suffix,
        )
        # With has_entity_name=True, the device name is prepended by HA.
        # Store only the room-specific suffix ("Kitchen Cleaning History").
        self._attr_name = f"{self._room_name} {label}"
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)

    @property
    def manager(self):
        """Return integration manager."""
        return self.hass.data[DOMAIN]["runtime"]

    def _get_room_data(self) -> dict[str, Any]:
        """Return current room data from manager storage."""
        map_bucket = (
            self.manager.data.get("maps", {})
            .get(self._vacuum_entity_id, {})
            .get(self._map_id, {})
        )
        rooms = map_bucket.get("rooms", {})
        return rooms.get(str(self._room_id), {})

    async def _async_update_room(self, updates: dict[str, Any]) -> None:
        """Apply field updates to this room, persist storage, and write HA state."""
        profile_name = updates.get("profile_name")
        if isinstance(profile_name, str) and len(updates) == 1:
            self.manager.apply_room_profile(
                vacuum_entity_id=self._vacuum_entity_id,
                map_id=self._map_id,
                room_ids=[self._room_id],
                profile_name=profile_name,
            )
            await self.manager.async_save()
            self.async_write_ha_state()
            return

        managed_field_names = {
            "enabled",
            "clean_mode",
            "fan_speed",
            "water_level",
            "clean_intensity",
            "clean_passes",
            "edge_mopping",
        }
        managed_updates = {
            key: value
            for key, value in updates.items()
            if key in managed_field_names
        }
        if managed_updates:
            self.manager.update_room_fields(
                vacuum_entity_id=self._vacuum_entity_id,
                map_id=self._map_id,
                room_id=self._room_id,
                **managed_updates,
            )
            await self.manager.async_save()
            self.async_write_ha_state()
            return

        map_bucket = (
            self.manager.data.setdefault("maps", {})
            .setdefault(self._vacuum_entity_id, {})
            .setdefault(self._map_id, {})
        )
        rooms = map_bucket.setdefault("rooms", {})
        room_key = str(self._room_id)

        current = dict(rooms.get(room_key, {}))
        current.update(updates)

        rooms[room_key] = current

        from .rooms.room_manager import build_room_selection_summary

        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)
        self.manager._refresh_room_derived_state(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
        )
        self.manager._notify_rooms_updated(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
        )

        await self.manager.async_save()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return whether entity is available."""
        return bool(self._get_room_data())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return common room attributes."""
        room = self._get_room_data()

        raw_grants = room.get("grants_access_to", [])
        grants_access_to = (
            [str(v) for v in raw_grants]
            if isinstance(raw_grants, list)
            else []
        )

        effective = self.manager.get_effective_room_details(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
        ) or {}

        # Adapter-declared dropdown vocabularies. Carried on the room
        # entity so the standalone Eufy Room Card (which reads HA state
        # directly and has no service-layer access) can populate its
        # mode/speed/water/intensity pickers from the adapter without
        # probing upstream brand integration entities. Each list is
        # `[{value, label}, ...]`; absent role keys become empty lists.
        _adapter_vocab = (
            get_adapter_config(self._vacuum_entity_id) or {}
        ).get("vocabulary", {}) or {}

        # Surface the last-cleaned timestamp from room_history on every
        # room entity so the card can render a "2d ago" pill on each
        # room card without an extra service round-trip. data shape:
        # data["room_history"][vacuum][map_id][room_id]["last_cleaned_at"]
        history_entry = (
            self.manager.data.get("room_history", {})
            .get(self._vacuum_entity_id, {})
            .get(str(self._map_id), {})
            .get(str(self._room_id), {})
        )
        if not isinstance(history_entry, dict):
            history_entry = {}

        return {
            "vacuum_entity_id": self._vacuum_entity_id,
            "map_id": self._map_id,
            "room_id": self._room_id,
            "room_name": room.get("name", self._room_name),
            "slug": room.get("slug", self._room_slug),
            "last_cleaned_at": history_entry.get("last_cleaned_at"),
            "last_vacuumed_at": history_entry.get("last_vacuumed_at"),
            "last_mopped_at": history_entry.get("last_mopped_at"),
            "last_job_mode": history_entry.get("last_job_mode"),
            "profile_name": room.get("profile_name", "vacuum_quick"),
            "floor_type": room.get("floor_type", "hardwood"),
            "clean_mode": effective.get("clean_mode"),
            "fan_speed": effective.get("fan_speed"),
            "water_level": effective.get("water_level"),
            "clean_intensity": effective.get("clean_intensity"),
            "clean_passes": effective.get("default_clean_passes", room.get("clean_passes", 1)),
            "edge_mopping": effective.get("default_edge_mopping", room.get("edge_mopping", False)),
            "carpet": str(room.get("floor_type", "")).startswith("carpet"),
            "order": room.get("order", 0),
            "enabled": room.get("enabled", False),
            "is_dock_room": bool(room.get("is_dock_room", False)),
            "grants_access_to": grants_access_to,
            "rules": room.get("rules", []),
            "integration": self._coordinator_key,
            "clean_mode_options": _adapter_vocab.get("clean_mode_options") or [],
            "fan_speed_options": _adapter_vocab.get("fan_speed_options") or [],
            "water_level_options": _adapter_vocab.get("water_level_options") or [],
            "clean_intensity_options": _adapter_vocab.get("clean_intensity_options") or [],
        }
