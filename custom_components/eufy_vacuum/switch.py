"""Switch platform for Vacuum Agent — per-room enabled/disabled switches."""

from __future__ import annotations

from typing import Any

# Room switches write directly to manager storage via callbacks; no polling.
PARALLEL_UPDATES = 0

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .debug_capture import build_debug_switch
from .entity_helpers import build_vacuum_device_info, entity_belongs_to, sort_room_items
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

    # Override Order switch — per-vacuum, only where the adapter+model declares the
    # WRITE half of `device_clean_order`. A brand or an unknown model gains no entity,
    # rather than one that turns on and does nothing.
    #
    # ⚠ STATE STORAGE, NOT DEVICE ACTION. Toggling this on does NOT push a sequence
    # to the device; it declares intent. Apply and Clear are separate services, per
    # the FINDINGS-roborock-clean-sequence UI design: "Clear is EXPLICIT, never
    # implicit on toggle-off. Toggling off must not silently write [] — that would
    # destroy a sequence the USER set in their app."
    _clean_order = getattr(manager, "clean_order", None)
    if _clean_order is not None:
        for vacuum_entity_id in list((manager.data.get("vacuums") or {}).keys()):
            if _clean_order.can_write(vacuum_entity_id):
                entities.append(
                    EufyVacuumCleanOrderOverrideSwitch(
                        manager=manager,
                        vacuum_entity_id=vacuum_entity_id,
                    )
                )

    # Integration-level diagnostic: the debug flight-recorder toggle (added once).
    entities.append(build_debug_switch(hass, domain=DOMAIN))
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

        # RP-009 (RF-04 (IN4CW5Y9)): stale = OWNED by this vacuum/map (live attributes, via
        # entity_belongs_to) and absent from desired — never a unique_id prefix
        # scan, which matched sibling vacuums whose entity_id is a string prefix
        # (vacuum.alfred_2 under vacuum.alfred + map "2" — DR-SETUP-1).
        stale_ids = [
            uid for uid, ent in list(entity_map.items())
            if entity_belongs_to(ent, vacuum_entity_id=vacuum_entity_id, map_id=str(map_id))
            and uid not in desired
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


class EufyVacuumCleanOrderOverrideSwitch(SwitchEntity):
    """Per-vacuum toggle that DECLARES INTENT to override the device clean order.

    Storage-only. Toggling this fires no service and pushes nothing to the device —
    Apply and Clear services do that, gated on this switch being ON. The UI design
    (FINDINGS-roborock-clean-sequence 2026-08-19) is explicit that toggling off must
    NOT silently clear the device: doing so would destroy a sequence the user set in
    their own Roborock app.

    ⚠ THIS EDITS A PERSISTENT, MAP-LEVEL SETTING IN THE VENDOR APP when the user
    presses Apply. That is not a per-run concept, and any consent surface built on top
    of this must say so — "this changes the saved sequence in your Roborock app",
    never "this changes the order for this run" (the strict-order chip is the per-run
    control; they are two different mechanisms with two different scopes).

    Only exists on vacuums whose adapter+model declares the WRITE half of
    `device_clean_order`. On the S6 today; on unknown models, absent by design
    (`supports_clean_sequence_write` fails closed).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "clean_order_override"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:sort-numeric-ascending"

    def __init__(self, *, manager: Any, vacuum_entity_id: str) -> None:
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_clean_order_override"
        )
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)

    @property
    def is_on(self) -> bool:
        clean_order = getattr(self._manager, "clean_order", None)
        if clean_order is None:
            return False
        return clean_order.override_enabled(self._vacuum_entity_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._manager.clean_order.set_override_enabled(
            self._vacuum_entity_id, True
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Deliberately does NOT clear the device. See the class docstring.
        await self._manager.clean_order.set_override_enabled(
            self._vacuum_entity_id, False
        )
        self.async_write_ha_state()


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