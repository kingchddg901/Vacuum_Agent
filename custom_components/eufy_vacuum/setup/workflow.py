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
# anchor: BN47ST30
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
# anchor: BN3WR8AM
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
    from ..panels import (
        append_to_panel_ledger,
        async_register_vacuum_panel,
        effective_panel_title,
    )

    panel_url = await async_register_vacuum_panel(
        hass,
        vacuum_entity_id,
        title=effective_panel_title(record),
    )
    # RP-039/RF-16 (INT79PB7): this is a singleton domain (one config entry manages every
    # vacuum), so the first (only) entry IS the owning entry — same lookup
    # services/setup.py's setup_add_vacuum already uses to find it for a reload.
    # Without this the panel registered above was untracked and never cleanly
    # removed on unload.
    _entries = hass.config_entries.async_entries(DOMAIN)
    if _entries:
        append_to_panel_ledger(hass, _entries[0].entry_id, panel_url)

    _LOGGER.debug("eufy_vacuum: added vacuum %s", vacuum_entity_id)
    return _result(
        "success",
        f"Vacuum '{vacuum_entity_id}' added.",
        data={"vacuum_entity_id": vacuum_entity_id},
        next_actions=["import_active_map"],
    )


# ---------------------------------------------------------------------------
# anchor: BNR06W9B
# import_active_map
# ---------------------------------------------------------------------------


def _no_map_message(
    hass: HomeAssistant, vacuum_entity_id: str, refresh: dict[str, Any] | None
) -> str:
    """Why the map could not be identified, in terms of THIS vacuum's brand.

    ISSUE #46: the old text was one string for every cause and every brand. It
    told a Roborock owner to go check the Eufy app, and said nothing about the
    real reason — HA 2026.7 not creating his map-selector entity. Chris's
    verdict on it ("sit and cry") was fair.

    The refresh result already distinguishes the causes (RP-007/SRC-1 gave it
    five named exits); this just says which one happened, in the right vocabulary.
    """
    from ..adapters.registry import get_adapter_config

    config = get_adapter_config(vacuum_entity_id) or {}
    brand = str(config.get("brand") or config.get("adapter_id") or "").strip()
    app = f"{brand} app" if brand else "vacuum's app"
    reason = (refresh or {}).get("reason")

    if reason == "entity_unavailable":
        return (
            f"'{vacuum_entity_id}' did not respond, so its map could not be read. "
            "The vacuum is usually asleep or off its dock — wake it and try again."
        )
    if reason in ("no_maps_service", "not_declared"):
        return (
            f"This vacuum's adapter does not declare how to fetch its map list, "
            f"so '{vacuum_entity_id}' cannot be imported. This is an integration "
            "bug rather than anything wrong with your setup — please report it."
        )
    if reason == "service_call_failed":
        return (
            f"Asking '{vacuum_entity_id}' for its maps failed. If the vacuum is "
            "online and the problem persists, please report it with diagnostics."
        )

    # Refresh succeeded (or was a no-op) and we still have no anchor. Either the
    # device reports several maps with no selector to say which is active, or it
    # has not finished mapping yet.
    return (
        f"No map could be identified for '{vacuum_entity_id}'. Make sure it has "
        f"completed a mapping run with rooms set up in the {app}, then try again. "
        "If this vacuum reports more than one map, Vacuum Agent needs its "
        "map-selector entity to know which is active — some Home Assistant "
        "versions no longer create that entity, in which case please report this "
        "with diagnostics attached."
    )


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

    # ISSUE #46: FETCH THE ROOM LIST FIRST. This refresh used to sit BELOW the
    # map-id gate, so the cache that can identify the map was populated only
    # after the check that needs it. A Roborock on HA 2026.7 — where
    # core#173282 means the map-selector entity is never created — hit the gate
    # with an empty cache and was refused at "no map detected", even though its
    # rooms decoded perfectly. The single-map fallback inside
    # discover_rooms_for_vacuum could never help either: nothing reached it.
    #
    # Safe to hoist: it is a no-op for attribute brands (Eufy) by its own first
    # branch, and it does not depend on map_id.
    from ..rooms.source_refresh import async_refresh_room_source
    refresh = await async_refresh_room_source(hass, vacuum_entity_id)

    map_id = get_active_map_id(hass, vacuum_entity_id)
    if not map_id:
        return _result(
            "blocked",
            _no_map_message(hass, vacuum_entity_id, refresh),
            data={
                "vacuum_entity_id": vacuum_entity_id,
                # The reason the refresh gave, so a support capture says whether
                # the device was asleep, the adapter misdeclared, or the map is
                # genuinely ambiguous — instead of one message for all three.
                "room_source_refresh": refresh,
            },
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
