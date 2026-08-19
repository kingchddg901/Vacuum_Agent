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
    SERVICE_ADD_QUEUE_ZONE,
    SERVICE_GET_QUEUE_STEPS,
    SERVICE_REMOVE_QUEUE_BREAK,
    SERVICE_SET_QUEUE_BREAKS,
)
from ._common import (
    VACUUM_MAP_SCHEMA,
    get_manager,
    is_managed_vacuum,
    require_managed_vacuum,
    resolved_call_data,
    unmanaged_vacuum_read_result,
)


# anchor: INJSETB0  one contract, three declarations; the write accepts what the read emits
def _require_break_params(value: dict) -> dict:
    """RP-032/RF-28 (A2-JOB-5). voluptuous's per-key vol.Optional can't express
    "required only when break_type has a specific value", so this runs as a
    post-check after the per-key schema (fields already type-coerced). Without
    it a `{break_type: wait}` with no wait_minutes validated cleanly, then
    silently normalized to nothing downstream and came back as a refusal the
    caller had to notice in the response."""
    break_type = value.get("break_type")
    if break_type == "charge_wait" and value.get("target_battery_percent") is None:
        raise vol.Invalid("break_type 'charge_wait' requires target_battery_percent")
    if break_type == "wait" and value.get("wait_minutes") is None:
        raise vol.Invalid("break_type 'wait' requires wait_minutes")
    if break_type == "zone" and not value.get("zone_ids"):
        raise vol.Invalid("break_type 'zone' requires a non-empty zone_ids")
    return value


def _flatten_break_entry(value):
    """RP-032/RF-28 (A2-JOB-6). get_queue_steps's `breaks` returns each entry
    as {after_index, step: {type, ...}} (the same shape a run-profile step
    uses); accept that read shape here too, not just the flat write shape
    ({after_index, break_type, ...}), so the documented read-modify-write
    round trip (get_queue_steps -> edit one field -> set_queue_breaks) works
    without the caller hand-flattening `step` first."""
    if not isinstance(value, dict):
        return value
    step = value.get("step")
    if not isinstance(step, dict):
        return value
    flattened = {k: v for k, v in value.items() if k != "step"}
    flattened.setdefault("break_type", step.get("type"))
    for key in ("target_battery_percent", "wait_minutes", "zone_ids"):
        if key in step and key not in flattened:
            flattened[key] = step[key]
    return flattened


# add_queue_break only ever builds a charge_wait or wait step (see
# core/manager.py add_queue_break) -- a zone step has its own dedicated
# service, add_queue_zone, with its own write path. So break_type here is
# deliberately narrower than _QUEUE_BREAK_ENTRY_SCHEMA's set below: adding
# "zone" here would validate but the handler has no zone branch, so it would
# silently fall through to "wait" instead. _QUEUE_BREAK_ENTRY_SCHEMA needs
# "zone" because set_queue_breaks REPLACES the whole store wholesale,
# including zones added via add_queue_zone.
_ADD_QUEUE_BREAK_SCHEMA = vol.All(
    vol.Schema(
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
    ),
    _require_break_params,
)

_QUEUE_BREAK_ENTRY_SCHEMA = vol.All(
    _flatten_break_entry,
    vol.Schema(
        {
            vol.Required("after_index"): vol.Coerce(int),
            vol.Required("break_type"): vol.In(["charge_wait", "wait", "zone"]),
            vol.Optional("target_battery_percent"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Optional("wait_minutes"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=1440)
            ),
            vol.Optional("zone_ids"): [cv.string],
        }
    ),
    _require_break_params,
)

_ADD_QUEUE_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("after_index"): vol.Coerce(int),
        vol.Required("zone_ids"): [cv.string],
    }
)

_SET_QUEUE_BREAKS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        # The full desired break list; replaces the store wholesale (reorder + retarget).
        vol.Required("breaks"): [_QUEUE_BREAK_ENTRY_SCHEMA],
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
    SERVICE_SET_QUEUE_BREAKS,
    SERVICE_ADD_QUEUE_ZONE,
)


async def _handle_build_queue(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Build cleaning queue from enabled rooms."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).build_queue(**resolved_call_data(hass, call))
    _LOGGER.debug("build_queue complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_build_room_payload(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Build payload for room cleaning."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).build_room_payload(**resolved_call_data(hass, call))
    _LOGGER.debug("build_room_payload complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_get_queue_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current queue state."""
    # INKV8ZQD: a read answers empty-with-a-reason, it does not raise.
    if not is_managed_vacuum(hass, call.data["vacuum_entity_id"]):
        return unmanaged_vacuum_read_result(call.data["vacuum_entity_id"])
    payload = get_manager(hass).get_queue_state(**resolved_call_data(hass, call))
    _LOGGER.debug("get_queue_state complete: %s", payload)
    return payload


async def _handle_get_payload_state(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Get current payload state."""
    # INKV8ZQD: a read answers empty-with-a-reason, it does not raise.
    if not is_managed_vacuum(hass, call.data["vacuum_entity_id"]):
        return unmanaged_vacuum_read_result(call.data["vacuum_entity_id"])
    payload = get_manager(hass).get_payload_state(**resolved_call_data(hass, call))
    _LOGGER.debug("get_payload_state complete: %s", payload)
    return payload


async def _handle_clear_queue(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Clear queue state."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).clear_queue(**resolved_call_data(hass, call))
    _LOGGER.debug("clear_queue complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_get_queue_steps(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return the live queue as a stepped list (rooms + charge/wait breaks)."""
    # INKV8ZQD: a read answers empty-with-a-reason, it does not raise.
    if not is_managed_vacuum(hass, call.data["vacuum_entity_id"]):
        return unmanaged_vacuum_read_result(call.data["vacuum_entity_id"])
    payload = get_manager(hass).get_queue_steps(**resolved_call_data(hass, call))
    _LOGGER.debug("get_queue_steps complete: %s", payload)
    return payload


async def _handle_add_queue_break(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Insert a charge/wait break into the live queue."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).add_queue_break(**resolved_call_data(hass, call))
    _LOGGER.debug("add_queue_break complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_remove_queue_break(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Remove one break from the live queue by index."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).remove_queue_break(**resolved_call_data(hass, call))
    _LOGGER.debug("remove_queue_break complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_clear_queue_breaks(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Remove all breaks — the queue drops back to a flat clean."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).clear_queue_breaks(**resolved_call_data(hass, call))
    _LOGGER.debug("clear_queue_breaks complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_set_queue_breaks(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Replace all queue breaks wholesale (reorder + retarget in one call)."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).set_queue_breaks(**resolved_call_data(hass, call))
    _LOGGER.debug("set_queue_breaks complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_add_queue_zone(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Insert a zone step (clean the named saved zones together) into the live queue."""
    # INKV8ZQD: refuse BEFORE the manager mints anything.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).add_queue_zone(**resolved_call_data(hass, call))
    _LOGGER.debug("add_queue_zone complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register queue services."""

    async def build_queue(call: ServiceCall) -> dict:
        return await _handle_build_queue(hass, call)

    async def build_room_payload(call: ServiceCall) -> dict:
        return await _handle_build_room_payload(hass, call)

    async def get_queue_state(call: ServiceCall) -> dict:
        return await _handle_get_queue_state(hass, call)

    async def get_payload_state(call: ServiceCall) -> dict:
        return await _handle_get_payload_state(hass, call)

    async def clear_queue(call: ServiceCall) -> dict:
        return await _handle_clear_queue(hass, call)

    async def get_queue_steps(call: ServiceCall) -> dict:
        return await _handle_get_queue_steps(hass, call)

    async def add_queue_break(call: ServiceCall) -> dict:
        return await _handle_add_queue_break(hass, call)

    async def remove_queue_break(call: ServiceCall) -> dict:
        return await _handle_remove_queue_break(hass, call)

    async def clear_queue_breaks(call: ServiceCall) -> dict:
        return await _handle_clear_queue_breaks(hass, call)

    async def set_queue_breaks(call: ServiceCall) -> dict:
        return await _handle_set_queue_breaks(hass, call)

    async def add_queue_zone(call: ServiceCall) -> dict:
        return await _handle_add_queue_zone(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_BUILD_QUEUE, build_queue,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_BUILD_ROOM_PAYLOAD, build_room_payload,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
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
        DOMAIN, SERVICE_CLEAR_QUEUE, clear_queue,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
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
    hass.services.async_register(
        DOMAIN, SERVICE_SET_QUEUE_BREAKS, set_queue_breaks,
        schema=_SET_QUEUE_BREAKS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_QUEUE_ZONE, add_queue_zone,
        schema=_ADD_QUEUE_ZONE_SCHEMA, supports_response=True,
    )
