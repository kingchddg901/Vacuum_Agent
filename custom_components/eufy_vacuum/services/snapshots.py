"""Card-facing snapshot services + pause-timeout settings.

Four services, all supports_response=True:
- get_dashboard_snapshot: unified card snapshot
- get_upkeep_snapshot: maintenance/dock-event aggregate
- get_pause_timeout_settings: read persisted default
- set_pause_timeout_settings: write persisted default
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_GET_DASHBOARD_SNAPSHOT,
    SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_GET_UPKEEP_SNAPSHOT,
    SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
)
from ._common import (
    VACUUM_MAP_SCHEMA,
    VACUUM_ONLY_SCHEMA,
    get_manager,
    resolved_call_data,
)

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_DASHBOARD_SNAPSHOT,
    SERVICE_GET_UPKEEP_SNAPSHOT,
    SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
)


_PAUSE_TIMEOUT_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("pause_timeout_minutes_default"): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
    }
)


async def _handle_get_dashboard_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return unified dashboard snapshot for one vacuum/map."""
    # Must NOT use async_add_executor_job here — get_dashboard_snapshot calls
    # hass.bus.async_fire internally (via _maybe_roll_current_room_by_timing),
    # which requires the event loop thread.
    payload = get_manager(hass).get_dashboard_snapshot(**resolved_call_data(hass, call))
    _LOGGER.debug("get_dashboard_snapshot complete: %s", payload)
    return payload


async def _handle_get_upkeep_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return upkeep snapshot for one vacuum."""
    payload = get_manager(hass).get_upkeep_snapshot(**call.data)
    _LOGGER.debug("get_upkeep_snapshot complete: %s", payload)
    return payload


async def _handle_get_pause_timeout_settings(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return persisted default pause-timeout settings for one vacuum."""
    payload = get_manager(hass).get_pause_timeout_settings(**call.data)
    _LOGGER.debug("get_pause_timeout_settings complete: %s", payload)
    return payload


async def _handle_set_pause_timeout_settings(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Persist default pause-timeout settings for one vacuum."""
    payload = get_manager(hass).set_pause_timeout_settings(**call.data)
    _LOGGER.debug("set_pause_timeout_settings complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register snapshot services."""

    async def get_dashboard_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_dashboard_snapshot(hass, call)

    async def get_upkeep_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_upkeep_snapshot(hass, call)

    async def get_pause_timeout_settings(call: ServiceCall) -> dict:
        return await _handle_get_pause_timeout_settings(hass, call)

    async def set_pause_timeout_settings(call: ServiceCall) -> dict:
        return await _handle_set_pause_timeout_settings(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_GET_DASHBOARD_SNAPSHOT, get_dashboard_snapshot,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_UPKEEP_SNAPSHOT, get_upkeep_snapshot,
        schema=VACUUM_ONLY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_PAUSE_TIMEOUT_SETTINGS, get_pause_timeout_settings,
        schema=VACUUM_ONLY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PAUSE_TIMEOUT_SETTINGS, set_pause_timeout_settings,
        schema=_PAUSE_TIMEOUT_SETTINGS_SCHEMA, supports_response=True,
    )
