"""Setup workflow for Vacuum Agent.

Two atomic operations callable from services (and therefore from the panel):

    add_vacuum(hass, vacuum_entity_id)      → ActionResult
    import_active_map(hass, vacuum_entity_id) → ActionResult

Every function returns an explicit ActionResult dict — it never raises,
never silently no-ops, and always tells the caller what to do next.

ActionResult schema:
    {
        "status":       "success" | "already_done" | "blocked" | "error",
        "message":      str,
        "data":         dict,           # operation-specific payload
        "next_actions": list[str],      # e.g. ["import_active_map"]
    }
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from ..const import DATA_RUNTIME, DOMAIN
from ..rooms.room_discovery import discover_rooms_for_vacuum, get_active_map_id

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _result(
    status: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Build a canonical ActionResult dict."""
    return {
        "status": status,
        "message": message,
        "data": data or {},
        "next_actions": next_actions or [],
    }


def _get_manager(hass: HomeAssistant):
    """Return the runtime manager or None."""
    return hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)


# ---------------------------------------------------------------------------
# add_vacuum
# ---------------------------------------------------------------------------


async def add_vacuum(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Add a vacuum to the integration.

    Idempotent — returns ``"already_done"`` if the vacuum is already managed.
    Returns ``"blocked"`` if the entity does not exist in the HA state machine.

    On success, also registers a per-vacuum sidebar panel so the user can
    immediately navigate to that vacuum's command-center view.
    """
    manager = _get_manager(hass)
    if manager is None:
        return _result("error", "Integration manager not available.")

    # The entity must be present in the HA state machine before it can be managed.
    if hass.states.get(vacuum_entity_id) is None:
        return _result(
            "blocked",
            (
                f"Vacuum entity '{vacuum_entity_id}' not found in Home Assistant. "
                "Ensure the vacuum integration is loaded and the device is online."
            ),
            data={"vacuum_entity_id": vacuum_entity_id},
        )

    if vacuum_entity_id in manager.data.get("vacuums", {}):
        return _result(
            "already_done",
            f"Vacuum '{vacuum_entity_id}' is already managed.",
            data={"vacuum_entity_id": vacuum_entity_id},
            next_actions=["import_active_map"],
        )

    record = manager.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)
    await manager.async_save()

    # Register a per-vacuum sidebar panel so the user can reach the command center
    # immediately. Title = the vacuum's panel_title (or "Vacuum Agent" default).
    from ..panels import async_register_vacuum_panel, effective_panel_title

    await async_register_vacuum_panel(
        hass,
        vacuum_entity_id,
        title=effective_panel_title(record),
    )

    _LOGGER.debug("eufy_vacuum: added vacuum %s", vacuum_entity_id)
    return _result(
        "success",
        f"Vacuum '{vacuum_entity_id}' added.",
        data={"vacuum_entity_id": vacuum_entity_id},
        next_actions=["import_active_map"],
    )


# ---------------------------------------------------------------------------
# import_active_map
# ---------------------------------------------------------------------------


async def import_active_map(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Import the currently active map for a managed vacuum.

    Upstream constraint: only the map that is currently active on the device
    can be imported.  This is a hard limitation of the upstream cloud API —
    there is no way to query historical or alternate maps.

    Idempotent — returns ``"already_done"`` if that exact map_id is already
    known and has rooms.  If the map exists but has no rooms (empty bucket),
    the import runs again so the user can recover from a partial state.
    """
    manager = _get_manager(hass)
    if manager is None:
        return _result("error", "Integration manager not available.")

    if vacuum_entity_id not in manager.data.get("vacuums", {}):
        return _result(
            "blocked",
            f"Vacuum '{vacuum_entity_id}' is not yet managed — add it first.",
            data={"vacuum_entity_id": vacuum_entity_id},
            next_actions=["add_vacuum"],
        )

    map_id = get_active_map_id(hass, vacuum_entity_id)
    if not map_id:
        return _result(
            "blocked",
            (
                f"No active map detected for '{vacuum_entity_id}'. "
                "Ensure the vacuum is powered on and has completed at least one "
                "mapping run, then try again."
            ),
            data={"vacuum_entity_id": vacuum_entity_id},
        )

    existing_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {})
    existing_rooms = existing_maps.get(str(map_id), {}).get("rooms", {})
    if existing_rooms:
        room_count = len(existing_rooms)
        return _result(
            "already_done",
            f"Map '{map_id}' is already imported ({room_count} rooms).",
            data={
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": map_id,
                "room_count": room_count,
            },
            next_actions=["configure_rooms"],
        )

    # Service-response brands (Roborock: rooms live in the get_maps response, not
    # an entity attribute) need the source cache refreshed before the sync
    # discovery reads it. No-op for attribute brands (Eufy).
    from ..rooms.source_refresh import async_refresh_room_source
    await async_refresh_room_source(hass, vacuum_entity_id)

    rooms = discover_rooms_for_vacuum(
        hass,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
    )
    if not rooms:
        return _result(
            "blocked",
            (
                f"No rooms detected for '{vacuum_entity_id}' on map '{map_id}'. "
                "Ensure the vacuum has completed a mapping run and room "
                "segmentation is configured in your vacuum app, then try again."
            ),
            data={"vacuum_entity_id": vacuum_entity_id, "map_id": map_id},
        )

    # Cache the raw discovery result so repair flows and services can reference it without re-querying.
    manager.data.setdefault("discovery", {})
    manager.data["discovery"].setdefault(vacuum_entity_id, {})[str(map_id)] = {
        "vacuum_entity_id": vacuum_entity_id,
        "active_map_id": map_id,
        "room_count": len(rooms),
        "rooms": rooms,
    }

    # Import every discovered room with hardwood defaults; the user sets per-room
    # floor type via the panel's room editor after import.
    manager.save_managed_rooms(
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id,
        enabled_room_ids=None,
        floor_types={},
    )

    await manager.async_save()

    room_count = len(rooms)
    _LOGGER.debug(
        "eufy_vacuum: imported map %s for %s — %d rooms",
        map_id,
        vacuum_entity_id,
        room_count,
    )

    return _result(
        "success",
        f"Map '{map_id}' imported with {room_count} rooms.",
        data={
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id,
            "room_count": room_count,
            "rooms": [
                {"room_id": r["room_id"], "name": r["name"]}
                for r in rooms
            ],
        },
        next_actions=["configure_rooms"],
    )
