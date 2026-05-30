"""Maintenance services — reset counter / set interval.

Two services:
- reset_maintenance: reset maintenance counter for a specific component
- set_maintenance_interval: persist user-configured interval for one
  component (stays in sync with EufyVacuumMaintenanceIntervalNumber entity)
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_RESET_MAINTENANCE,
    SERVICE_SET_MAINTENANCE_INTERVAL,
)
from ._common import get_manager

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_RESET_MAINTENANCE,
    SERVICE_SET_MAINTENANCE_INTERVAL,
)


_RESET_MAINTENANCE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("component"): cv.string,
    }
)

_SET_MAINTENANCE_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("component"): cv.string,
        vol.Required("interval_hours"): vol.All(
            vol.Coerce(float), vol.Range(min=0.0)
        ),
    }
)


async def _handle_reset_maintenance(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Reset the maintenance counter for a specific component."""
    try:
        payload = get_manager(hass).reset_maintenance(**call.data)
    except Exception as err:
        raise HomeAssistantError(f"Failed to reset maintenance: {err}") from err
    if not payload.get("reset") and payload.get("reason") == "no_source_entity":
        _LOGGER.debug(
            "reset_maintenance blocked: component=%s has no source entity for %s",
            call.data.get("component"),
            call.data.get("vacuum_entity_id"),
        )
        raise ServiceValidationError(
            f"Component '{call.data.get('component')}' has no source entity "
            f"for vacuum '{call.data.get('vacuum_entity_id')}'"
        )
    _LOGGER.debug("reset_maintenance complete: %s", payload)
    if payload.get("reset"):
        await get_manager(hass).async_save()
    return payload


async def _handle_set_maintenance_interval(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Persist a user-configured maintenance interval for one component.

    Writes into manager.data["maintenance"][<vacuum>][<component>]["interval_hours"]
    — same slot the EufyVacuumMaintenanceIntervalNumber entity writes to,
    so the card-side editor and the HA number entity stay in sync. The
    interval is clamped to MAINTENANCE_INTERVAL_MIN/MAX at the entity
    level but the service trusts its caller (the card validates against
    the adapter's declared min/max before submitting).
    """
    manager = get_manager(hass)
    vacuum_entity_id = call.data["vacuum_entity_id"]
    component = call.data["component"]
    interval_hours = round(float(call.data["interval_hours"]), 1)

    try:
        manager.data.setdefault("maintenance", {})
        manager.data["maintenance"].setdefault(vacuum_entity_id, {})
        manager.data["maintenance"][vacuum_entity_id].setdefault(component, {})
        manager.data["maintenance"][vacuum_entity_id][component]["interval_hours"] = interval_hours
        await manager.async_save()
    except Exception as err:
        raise HomeAssistantError(f"Failed to save maintenance interval: {err}") from err

    payload = {
        "saved": True,
        "vacuum_entity_id": vacuum_entity_id,
        "component": component,
        "interval_hours": interval_hours,
    }
    _LOGGER.debug("set_maintenance_interval: %s", payload)
    return payload


def register(hass: HomeAssistant) -> None:
    """Register maintenance services."""

    async def reset_maintenance(call: ServiceCall) -> dict:
        return await _handle_reset_maintenance(hass, call)

    async def set_maintenance_interval(call: ServiceCall) -> dict:
        return await _handle_set_maintenance_interval(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_MAINTENANCE,
        reset_maintenance,
        schema=_RESET_MAINTENANCE_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MAINTENANCE_INTERVAL,
        set_maintenance_interval,
        schema=_SET_MAINTENANCE_INTERVAL_SCHEMA,
        supports_response=True,
    )
