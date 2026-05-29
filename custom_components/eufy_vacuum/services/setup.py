"""Setup panel services — onboarding wizard backend.

Eight services driving the panel-based setup flow:
- setup_get_status: read the current setup state
- setup_add_vacuum: register a vacuum with the integration
- setup_import_active_map: import the vacuum's active map
- setup_get_map_rooms: list managed rooms for a map
- setup_save_rooms: persist the room selection
- setup_delete_map: delete a map (gated by protection)
- setup_reject_rooms: mark rooms as phantoms (never re-surface)
- setup_force_remove_room: bypass missing-pass counter for one room
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DATA_RUNTIME,
    DOMAIN,
    SERVICE_SETUP_ADD_VACUUM,
    SERVICE_SETUP_DELETE_MAP,
    SERVICE_SETUP_FORCE_REMOVE_ROOM,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_GET_STATUS,
    SERVICE_SETUP_IMPORT_MAP,
    SERVICE_SETUP_REJECT_ROOMS,
    SERVICE_SETUP_SAVE_ROOMS,
)
from ._common import resolved_call_data

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_SETUP_GET_STATUS,
    SERVICE_SETUP_ADD_VACUUM,
    SERVICE_SETUP_IMPORT_MAP,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_SAVE_ROOMS,
    SERVICE_SETUP_DELETE_MAP,
    SERVICE_SETUP_REJECT_ROOMS,
    SERVICE_SETUP_FORCE_REMOVE_ROOM,
)


_SETUP_ADD_VACUUM_SCHEMA = vol.Schema(
    {vol.Required("vacuum_entity_id"): cv.entity_id}
)
_SETUP_IMPORT_MAP_SCHEMA = vol.Schema(
    {vol.Required("vacuum_entity_id"): cv.entity_id}
)
_SETUP_GET_STATUS_SCHEMA = vol.Schema({})
_SETUP_GET_MAP_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
    }
)
_SETUP_SAVE_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Optional("enabled_room_ids"): vol.All(
            cv.ensure_list, [vol.Coerce(int)]
        ),
        vol.Optional("floor_types"): vol.Schema({cv.string: cv.string}),
    }
)
_SETUP_DELETE_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        # confirmation_token: truthy string for elevated; map display name for high
        vol.Optional("confirmation_token"): cv.string,
    }
)
_SETUP_REJECT_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("room_ids"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    }
)
_SETUP_FORCE_REMOVE_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("room_id"): vol.Coerce(int),
    }
)


def register(hass: HomeAssistant) -> None:
    """Register setup-panel services."""

    # Lazy imports keep services package import-time clean. The setup
    # subpackage transitively pulls in HA storage and more; deferring
    # the imports until first registration is harmless.
    from ..setup.workflow import add_vacuum as _add_vacuum
    from ..setup.workflow import import_active_map as _import_active_map
    from ..setup.status import get_setup_status as _get_setup_status
    from ..setup.delete import delete_map as _delete_map
    from ..setup.drift import (
        record_step_completed as _record_setup_step,
        reject_rooms as _reject_rooms,
        force_remove_room as _force_remove_room,
    )

    async def setup_get_status(call: ServiceCall) -> dict:
        return _get_setup_status(hass)

    async def setup_add_vacuum(call: ServiceCall) -> dict:
        result = await _add_vacuum(hass, call.data["vacuum_entity_id"])
        # Stamp step complete only on a non-error result. The workflow
        # functions today don't return a uniform status key; treat
        # any non-{"status": "error", ...} response as success.
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is not None and (
            not isinstance(result, dict) or result.get("status") != "error"
        ):
            _record_setup_step(
                manager, call.data["vacuum_entity_id"], "add_vacuum"
            )
            await manager.async_save()
        return result

    async def setup_import_active_map(call: ServiceCall) -> dict:
        result = await _import_active_map(hass, call.data["vacuum_entity_id"])
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is not None and (
            not isinstance(result, dict) or result.get("status") != "error"
        ):
            _record_setup_step(
                manager, call.data["vacuum_entity_id"], "import_active_map"
            )
            await manager.async_save()
        return result

    async def setup_get_map_rooms(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        data = resolved_call_data(hass, call)
        if manager is None:
            return {"rooms": [], "vacuum_entity_id": data["vacuum_entity_id"], "map_id": data.get("map_id")}
        result = manager.get_managed_rooms(
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
        )
        rooms_dict = result.get("rooms", {})
        rooms_list = sorted(
            [
                {
                    "room_id": int(room.get("room_id", rid)),
                    "name": str(room.get("name", f"Room {rid}")),
                    "floor_type": str(room.get("floor_type", "hardwood")),
                }
                for rid, room in rooms_dict.items()
                if isinstance(room, dict)
            ],
            key=lambda r: r["room_id"],
        )
        return {
            "vacuum_entity_id": data["vacuum_entity_id"],
            "map_id": str(data["map_id"]),
            "rooms": rooms_list,
        }

    async def setup_save_rooms(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        data = resolved_call_data(hass, call)
        result = manager.save_managed_rooms(
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
            enabled_room_ids=data.get("enabled_room_ids"),
            floor_types=data.get("floor_types") or {},
        )
        # is_configured stamping is handled by build_managed_rooms —
        # every room returned by save_managed_rooms now carries True
        # plus a configured_at timestamp. Mark the step complete here.
        _record_setup_step(
            manager, data["vacuum_entity_id"], "save_rooms"
        )
        await manager.async_save()
        return {"status": "success", "room_count": result.get("room_count", 0)}

    async def setup_delete_map(call: ServiceCall) -> dict:
        data = resolved_call_data(hass, call)
        return await _delete_map(
            hass,
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
            confirmation_token=data.get("confirmation_token"),
        )

    async def setup_reject_rooms(call: ServiceCall) -> dict:
        """Mark discovered rooms as phantoms — never surface them again."""
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = _reject_rooms(
            manager,
            vacuum_entity_id,
            call.data["room_ids"],
        )
        # Fire room-update callbacks for every map that lost a room so
        # the entity-platform cleanup (switch/number/sensor) tears down
        # the orphaned entities. The drift module is pure data; service
        # handler dispatches the HA-side notifications.
        for affected_map_id in result.get("affected_map_ids", []):
            manager._notify_rooms_updated(
                vacuum_entity_id=vacuum_entity_id,
                map_id=affected_map_id,
            )
        await manager.async_save()
        return {"status": "success", **result}

    async def setup_force_remove_room(call: ServiceCall) -> dict:
        """Bypass the missing-pass counter and immediately flag a room removed.

        The room stays in managed_rooms (history preserved); only its
        drift signal flips. Pair with a separate delete operation if
        full removal is wanted.
        """
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        result = _force_remove_room(
            manager,
            call.data["vacuum_entity_id"],
            call.data["room_id"],
        )
        await manager.async_save()
        return {"status": "success", **result}

    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_GET_STATUS, setup_get_status,
        schema=_SETUP_GET_STATUS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_ADD_VACUUM, setup_add_vacuum,
        schema=_SETUP_ADD_VACUUM_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_IMPORT_MAP, setup_import_active_map,
        schema=_SETUP_IMPORT_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_GET_MAP_ROOMS, setup_get_map_rooms,
        schema=_SETUP_GET_MAP_ROOMS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_SAVE_ROOMS, setup_save_rooms,
        schema=_SETUP_SAVE_ROOMS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_DELETE_MAP, setup_delete_map,
        schema=_SETUP_DELETE_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_REJECT_ROOMS, setup_reject_rooms,
        schema=_SETUP_REJECT_ROOMS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_FORCE_REMOVE_ROOM, setup_force_remove_room,
        schema=_SETUP_FORCE_REMOVE_ROOM_SCHEMA, supports_response=True,
    )
