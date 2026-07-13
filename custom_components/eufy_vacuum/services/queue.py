"""Queue management services — build/inspect/clear the cleaning queue.

Five services:
- build_queue: build cleaning queue from enabled rooms
- build_room_payload: build the payload sent to the vacuum
- get_queue_state: current queue snapshot
- get_payload_state: current payload snapshot
- clear_queue: empty the queue
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_ADD_QUEUE_BREAK,
    SERVICE_BUILD_QUEUE,
    SERVICE_BUILD_ROOM_PAYLOAD,
    SERVICE_CLEAR_QUEUE,
    SERVICE_CLEAR_QUEUE_BREAKS,
    SERVICE_GET_PAYLOAD_STATE,
    SERVICE_GET_QUEUE_STATE,
    SERVICE_GET_QUEUE_STEPS,
    SERVICE_REMOVE_QUEUE_BREAK,
)
from ._common import VACUUM_MAP_SCHEMA, get_manager, resolved_call_data

_ADD_QUEUE_BREAK_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("break_type"): vol.In(["charge_wait", "wait"]),
        vol.Required("after_index"): vol.Coerce(int),
        vol.Optional("target_battery_percent"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional("wait_minutes"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1440)
        ),
    }
)

_REMOVE_QUEUE_BREAK_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("index"): vol.Coerce(int),
    }
)

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_BUILD_QUEUE,
    SERVICE_BUILD_ROOM_PAYLOAD,
    SERVICE_GET_QUEUE_STATE,
    SERVICE_GET_PAYLOAD_STATE,
    SERVICE_CLEAR_QUEUE,
    SERVICE_GET_QUEUE_STEPS,
    SERVICE_ADD_QUEUE_BREAK,
    SERVICE_REMOVE_QUEUE_BREAK,
    SERVICE_CLEAR_QUEUE_BREAKS,
)


async def _handle_build_queue(hass: HomeAssistant, call: ServiceCall) -> None:
    """Build cleaning queue from enabled rooms."""
    payload = get_manager(hass).build_queue(**resolved_call_data(hass, call))
    _LOGGER.debug("build_queue complete: %s", payload)
    await get_manager(hass).async_save()


async def _handle_build_room_payload(hass: HomeAssistant, call: ServiceCall) -> None:
    """Build payload for room cleaning."""
    payload = get_manager(hass).build_room_payload(**resolved_call_data(hass, call))
    _LOGGER.debug("build_room_payload complete: %s", payload)
    await get_manager(hass).async_save()


async def _handle_get_queue_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current queue state."""
    payload = get_manager(hass).get_queue_state(**resolved_call_data(hass, call))
    _LOGGER.debug("get_queue_state complete: %s", payload)
    return payload


async def _handle_get_payload_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current payload state."""
    payload = get_manager(hass).get_payload_state(**resolved_call_data(hass, call))
    _LOGGER.debug("get_payload_state complete: %s", payload)
    return payload


async def _handle_clear_queue(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear queue state."""
    payload = get_manager(hass).clear_queue(**resolved_call_data(hass, call))
    _LOGGER.debug("clear_queue complete: %s", payload)
    await get_manager(hass).async_save()


async def _handle_get_queue_steps(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return the live queue as a stepped list (rooms + charge/wait breaks)."""
    payload = get_manager(hass).get_queue_steps(**resolved_call_data(hass, call))
    _LOGGER.debug("get_queue_steps complete: %s", payload)
    return payload


async def _handle_add_queue_break(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Insert a charge/wait break into the live queue."""
    payload = get_manager(hass).add_queue_break(**resolved_call_data(hass, call))
    _LOGGER.debug("add_queue_break complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_remove_queue_break(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Remove one break from the live queue by index."""
    payload = get_manager(hass).remove_queue_break(**resolved_call_data(hass, call))
    _LOGGER.debug("remove_queue_break complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_clear_queue_breaks(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Remove all breaks — the queue drops back to a flat clean."""
    payload = get_manager(hass).clear_queue_breaks(**resolved_call_data(hass, call))
    _LOGGER.debug("clear_queue_breaks complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register queue services."""

    async def build_queue(call: ServiceCall) -> None:
        await _handle_build_queue(hass, call)

    async def build_room_payload(call: ServiceCall) -> None:
        await _handle_build_room_payload(hass, call)

    async def get_queue_state(call: ServiceCall) -> dict:
        return await _handle_get_queue_state(hass, call)

    async def get_payload_state(call: ServiceCall) -> dict:
        return await _handle_get_payload_state(hass, call)

    async def clear_queue(call: ServiceCall) -> None:
        await _handle_clear_queue(hass, call)

    async def get_queue_steps(call: ServiceCall) -> dict:
        return await _handle_get_queue_steps(hass, call)

    async def add_queue_break(call: ServiceCall) -> dict:
        return await _handle_add_queue_break(hass, call)

    async def remove_queue_break(call: ServiceCall) -> dict:
        return await _handle_remove_queue_break(hass, call)

    async def clear_queue_breaks(call: ServiceCall) -> dict:
        return await _handle_clear_queue_breaks(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_BUILD_QUEUE, build_queue, schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_BUILD_ROOM_PAYLOAD, build_room_payload, schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_QUEUE_STATE, get_queue_state,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_PAYLOAD_STATE, get_payload_state,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_QUEUE, clear_queue, schema=VACUUM_MAP_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_QUEUE_STEPS, get_queue_steps,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_QUEUE_BREAK, add_queue_break,
        schema=_ADD_QUEUE_BREAK_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_QUEUE_BREAK, remove_queue_break,
        schema=_REMOVE_QUEUE_BREAK_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_QUEUE_BREAKS, clear_queue_breaks,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
