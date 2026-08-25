"""Device clean-order sensor — the order the vacuum will actually clean its rooms in.

State = how many rooms are in the device's saved order:

* ``0``       no order saved — the robot optimises the path itself
* ``N``       N rooms are ordered; the remainder (if any) are cleaned after them
* ``unknown`` the order could not be READ. NOT the same as zero, and the distinction
              is the point: an empty order is a fact about the device, an unreadable
              one is the absence of a fact.

Attributes carry the ordered room ids and their names, plus the read status and when it
was taken, so a stale or failed read is visible rather than implied.

Created only for vacuums whose adapter declares ``device_clean_order`` — a brand without
the concept gains no entity, rather than one that is permanently unknown.

This entity only READS ``CleanOrderManager``'s cache, so it stays a cheap sync property.
Filling that cache (and the awkwardness of doing so) lives in the manager.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from ..clean_order.manager import STATUS_OK
from ..entity_helpers import build_vacuum_device_info


class EufyVacuumCleanOrderSensor(SensorEntity):
    """Per-vacuum device clean-order sensor (state = ordered room count)."""

    _attr_has_entity_name = True
    _attr_translation_key = "clean_order"
    _attr_icon = "mdi:order-numeric-ascending"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, *, manager: Any, vacuum_entity_id: str) -> None:
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._attr_unique_id = f"{vacuum_entity_id.replace('.', '_')}_clean_order"
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)

    def _entry(self) -> dict[str, Any]:
        """The manager's cache entry for this vacuum (never None)."""
        clean_order = getattr(self._manager, "clean_order", None)
        if clean_order is None:
            return {"order": None, "read_at": None, "status": "never_read"}
        return clean_order.cached(self._vacuum_entity_id)

    def _room_names(self, order: list[int]) -> list[str]:
        """Resolve ordered room ids to names, falling back to the id when a room has
        been deleted or renumbered since the read."""
        try:
            map_id = self._manager.resolve_active_map_id(self._vacuum_entity_id)
            rooms = (
                self._manager.get_managed_rooms(
                    vacuum_entity_id=self._vacuum_entity_id, map_id=map_id
                )
                or {}
            ).get("rooms", {}) or {}
        except Exception:  # pragma: no cover - defensive over map state
            rooms = {}
        out: list[str] = []
        for room_id in order:
            room = rooms.get(str(room_id)) or rooms.get(room_id) or {}
            out.append(str(room.get("name") or room_id))
        return out

    @property
    def native_value(self) -> int | None:
        """Ordered room count, or None when the order could not be read."""
        entry = self._entry()
        if entry.get("status") != STATUS_OK:
            return None
        order = entry.get("order")
        return len(order) if isinstance(order, list) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Cache contents, plus the two keys that let the CARD FIND THIS ENTITY.

        ⚠ `vacuum_entity_id` + `role` exist for the same measured reason the Override
        Order SWITCH carries them, and their absence here was the same bug one entity
        along. With `_attr_has_entity_name` and a `translation_key`, Home Assistant
        composes the entity_id from the entity's NAME — and this sensor's name IS
        TRANSLATED. Eight of the eighteen shipped packs give it one, so a German
        install registers `sensor.<device>_reinigungsreihenfolge` and a French one
        `sensor.<device>_ordre_de_nettoyage`. Both cards were building
        `sensor.<object_id>_clean_order` by convention with NO fallback, so on those
        locales the sensor was simply never found: the row sat permanently grey,
        never confirming, on an install where everything was working.

        `theme_state` hit this first and answered it with a two-tier lookup; the
        switch followed. This is the third entity in the same seam, so it uses the
        same discriminator shape — a stable, language-independent `role` slug, because
        matching on the friendly name fails in exactly the case the fallback exists
        for.
        """
        entry = self._entry()
        order = entry.get("order")
        order = order if isinstance(order, list) else []
        return {
            "vacuum_entity_id": self._vacuum_entity_id,
            "role": "clean_order",
            "order": order,
            "order_names": self._room_names(order),
            "status": entry.get("status"),
            "read_at": entry.get("read_at"),
        }
