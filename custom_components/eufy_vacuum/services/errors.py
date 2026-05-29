"""Error tracker services — acknowledge / list recent.

Two services:
- acknowledge_error: clear active-run / last-device error latch(es)
- get_recent_errors: per-device recent_errors ring buffer
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DATA_ERROR_TRACKER,
    DOMAIN,
    SERVICE_ACKNOWLEDGE_ERROR,
    SERVICE_GET_RECENT_ERRORS,
)

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_ACKNOWLEDGE_ERROR,
    SERVICE_GET_RECENT_ERRORS,
)


# ErrorTracker services don't take a map_id (errors are per-device, not
# per-map), so they need their own schemas.
_ACKNOWLEDGE_ERROR_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("scope", default="both"): vol.In(
            ("active_run", "last_device", "both")
        ),
    }
)

_GET_RECENT_ERRORS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("limit", default=20): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=50)
        ),
    }
)


async def _handle_acknowledge_error(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Clear the active-run / last-device error latch(es).

    Scope:
        - "active_run"  — clear only the in-flight active-run latch
        - "last_device" — clear only the persistent last-device latch
        - "both"        — clear both (default)

    Does not affect upstream. The next rising edge re-creates whichever
    latch the upstream condition triggers.
    """
    vacuum_entity_id = call.data["vacuum_entity_id"]
    scope = str(call.data.get("scope") or "both").strip().lower()
    tracker = hass.data.get(DOMAIN, {}).get(DATA_ERROR_TRACKER)
    if tracker is None:
        return {"acknowledged": False, "reason": "tracker_not_loaded"}
    ok = tracker.acknowledge(vacuum_entity_id, scope=scope)
    return {
        "acknowledged": bool(ok),
        "vacuum_entity_id": vacuum_entity_id,
        "scope": scope,
    }


async def _handle_get_recent_errors(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return the last N entries from the per-device recent_errors ring buffer."""
    vacuum_entity_id = call.data["vacuum_entity_id"]
    limit_raw = call.data.get("limit", 20)
    try:
        limit = max(0, min(int(limit_raw), 50))
    except (TypeError, ValueError):
        limit = 20
    tracker = hass.data.get(DOMAIN, {}).get(DATA_ERROR_TRACKER)
    if tracker is None:
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "errors": [],
            "reason": "tracker_not_loaded",
        }
    errors = tracker.recent_errors(vacuum_entity_id, limit=limit)
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "errors": errors,
        "count": len(errors),
    }


def register(hass: HomeAssistant) -> None:
    """Register error tracker services."""

    async def acknowledge_error(call: ServiceCall) -> dict:
        return await _handle_acknowledge_error(hass, call)

    async def get_recent_errors(call: ServiceCall) -> dict:
        return await _handle_get_recent_errors(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ACKNOWLEDGE_ERROR,
        acknowledge_error,
        schema=_ACKNOWLEDGE_ERROR_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RECENT_ERRORS,
        get_recent_errors,
        schema=_GET_RECENT_ERRORS_SCHEMA,
        supports_response=True,
    )
