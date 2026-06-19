"""Map-overlays sensor — the VA's read of the device's own map, as HA attributes.

State = the current room (name), so automations/templates and the recorder get a clean
room-over-time history. Attributes mirror the normalized map_state_source layers
(per-room bbox+area, dock/robot anchors + heading, no-go / no-mop / walls / zones /
obstacles) PLUS the per-map overlay visibility — so the data is scriptable, not only
card-rendered. The big/dynamic layers are excluded from the recorder (state history
stays the small current-room value); the verbose `path` is omitted entirely (it lives
in the dashboard snapshot for the card).

Data comes from manager._map_state_source_cache, refreshed by the sensor platform's
timer (and by every dashboard-snapshot fetch). This entity only READS the cache, so it
stays a cheap sync property.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from ..entity_helpers import build_vacuum_device_info
from ..mapping.map_source import resolve_overlay_visibility

# Attributes kept OUT of the recorder: the verbose geometry layers + the dynamic
# anchors (they'd bloat history). The small state (current room) + a couple of scalars
# stay recorded so the room-over-time timeline is queryable.
_UNRECORDED = frozenset({
    "rooms", "no_go", "no_mop", "walls", "zones", "obstacles",
    "robot_anchor", "dock_anchor", "robot_heading", "visibility",
})


class EufyVacuumMapOverlaysSensor(SensorEntity):
    """Per-vacuum map-overlays sensor (state = current room; attrs = overlay layers)."""

    _attr_has_entity_name = True
    _attr_translation_key = "map_overlays"
    _attr_icon = "mdi:map-search-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = _UNRECORDED

    def __init__(self, *, manager: Any, vacuum_entity_id: str) -> None:
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._attr_unique_id = f"{vacuum_entity_id.replace('.', '_')}_map_overlays"
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)

    def _result(self) -> dict[str, Any]:
        """The cached normalized map_state_source result (or {} when unwarmed)."""
        cache = getattr(self._manager, "_map_state_source_cache", {}) or {}
        entry = cache.get(self._vacuum_entity_id) or {}
        res = entry.get("result")
        return res if isinstance(res, dict) else {}

    def _visibility(self) -> dict[str, bool]:
        """Resolved overlay visibility for the vacuum's active map."""
        from ..rooms.room_discovery import get_active_map_id

        map_id = get_active_map_id(self.hass, self._vacuum_entity_id)
        bucket = {}
        if map_id:
            bucket = (
                self._manager.data.get("maps", {})
                .get(self._vacuum_entity_id, {})
                .get(str(map_id), {})
                or {}
            )
        return resolve_overlay_visibility(bucket.get("overlay_visibility"))

    @property
    def native_value(self) -> str:
        """Current room name, or a coarse availability marker."""
        res = self._result()
        if not res.get("present"):
            return "unavailable"
        cur = res.get("current_room")
        if cur is None:
            return "available"
        for room in res.get("rooms", []):
            if room.get("number") == cur:
                return str(room.get("name") or f"Room {cur}")
        return f"Room {cur}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Overlay layers + visibility (path omitted; verbose layers recorder-excluded)."""
        res = self._result()
        attrs: dict[str, Any] = {
            "vacuum_entity_id": self._vacuum_entity_id,
            "present": bool(res.get("present")),
            "backend": res.get("backend"),
            "current_room": res.get("current_room"),
            "visibility": self._visibility(),
        }
        if not res.get("present"):
            attrs["reason"] = res.get("reason")
            return attrs
        # Compact per-room geometry (drop pixel_count — internal).
        attrs["rooms"] = [
            {k: room.get(k) for k in ("number", "name", "bbox", "area_m2")}
            for room in res.get("rooms", [])
        ]
        for key in (
            "dock_anchor", "robot_anchor", "robot_heading",
            "no_go", "no_mop", "walls", "zones", "obstacles",
        ):
            if key in res:
                attrs[key] = res[key]
        return attrs
