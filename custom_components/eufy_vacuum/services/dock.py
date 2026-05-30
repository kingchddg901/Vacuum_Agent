"""Dock services — gated actions + event-count override.

Six services:
- get_dock_action_status: gated availability for the four actions
- wash_mop / dry_mop / empty_dust / stop_dry_mop: gated dock actions
- set_dock_event_count: manual override of a dock event counter
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_DRY_MOP,
    SERVICE_EMPTY_DUST,
    SERVICE_GET_DOCK_ACTION_STATUS,
    SERVICE_SET_DOCK_EVENT_COUNT,
    SERVICE_STOP_DRY_MOP,
    SERVICE_WASH_MOP,
)
from ._common import (
    JOB_CONTROL_SCHEMA,
    VACUUM_MAP_SCHEMA,
    get_manager,
    resolved_call_data,
)

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_DOCK_ACTION_STATUS,
    SERVICE_WASH_MOP,
    SERVICE_DRY_MOP,
    SERVICE_EMPTY_DUST,
    SERVICE_STOP_DRY_MOP,
    SERVICE_SET_DOCK_EVENT_COUNT,
)


_SET_DOCK_EVENT_COUNT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("event_type"): vol.In(["last_mop_wash", "last_dust_empty", "last_dry_start"]),
        vol.Required("count"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)


async def _handle_get_dock_action_status(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return gated dock-action availability for one vacuum/map."""
    payload = get_manager(hass).get_dock_action_status(**resolved_call_data(hass, call))
    _LOGGER.debug("get_dock_action_status complete: %s", payload)
    return payload


def _check_dock_action(action: str, payload: dict) -> None:
    """Raise ServiceValidationError if a gated dock action was not allowed."""
    if not payload.get("performed") and not payload.get("allowed", True):
        msg = payload.get("message") or f"Dock action '{action}' is not available right now."
        raise ServiceValidationError(msg)


async def _handle_wash_mop(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated wash-mop dock action."""
    try:
        payload = await get_manager(hass).async_wash_mop(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to wash mop: {err}") from err
    _check_dock_action("wash_mop", payload)
    _LOGGER.debug("wash_mop complete: %s", payload)
    return payload


async def _handle_dry_mop(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated dry-mop dock action."""
    try:
        payload = await get_manager(hass).async_dry_mop(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to dry mop: {err}") from err
    _check_dock_action("dry_mop", payload)
    _LOGGER.debug("dry_mop complete: %s", payload)
    return payload


async def _handle_empty_dust(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated empty-dust dock action."""
    try:
        payload = await get_manager(hass).async_empty_dust(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to empty dust: {err}") from err
    _check_dock_action("empty_dust", payload)
    _LOGGER.debug("empty_dust complete: %s", payload)
    return payload


async def _handle_stop_dry_mop(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Run gated stop-dry-mop dock action."""
    try:
        payload = await get_manager(hass).async_stop_dry_mop(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to stop dry mop: {err}") from err
    _check_dock_action("stop_dry_mop", payload)
    _LOGGER.debug("stop_dry_mop complete: %s", payload)
    return payload


async def _handle_set_dock_event_count(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite a dock event counter to a specific value."""
    try:
        payload = get_manager(hass).set_dock_event_count(**call.data)
    except Exception as err:
        raise HomeAssistantError(f"Failed to set dock event count: {err}") from err
    _LOGGER.debug("set_dock_event_count complete: %s", payload)
    if payload.get("updated"):
        await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register dock services."""

    async def get_dock_action_status(call: ServiceCall) -> dict:
        return await _handle_get_dock_action_status(hass, call)

    async def wash_mop(call: ServiceCall) -> dict:
        return await _handle_wash_mop(hass, call)

    async def dry_mop(call: ServiceCall) -> dict:
        return await _handle_dry_mop(hass, call)

    async def empty_dust(call: ServiceCall) -> dict:
        return await _handle_empty_dust(hass, call)

    async def stop_dry_mop(call: ServiceCall) -> dict:
        return await _handle_stop_dry_mop(hass, call)

    async def set_dock_event_count(call: ServiceCall) -> dict:
        return await _handle_set_dock_event_count(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_GET_DOCK_ACTION_STATUS, get_dock_action_status,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_WASH_MOP, wash_mop,
        schema=JOB_CONTROL_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DRY_MOP, dry_mop,
        schema=JOB_CONTROL_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_EMPTY_DUST, empty_dust,
        schema=JOB_CONTROL_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_DRY_MOP, stop_dry_mop,
        schema=JOB_CONTROL_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_DOCK_EVENT_COUNT, set_dock_event_count,
        schema=_SET_DOCK_EVENT_COUNT_SCHEMA, supports_response=True,
    )
