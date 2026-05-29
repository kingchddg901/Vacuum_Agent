"""Adapter-config services + per-vacuum capability detection.

Six services driving the UI-based adapter-config flow (for future
multi-brand setups) plus the capability detection service:

- save_adapter_config: persist a UI-built adapter config
- delete_adapter_config: drop a stored adapter config
- get_adapter_config: read the registered adapter config
- discover_adapter_entities: scan for entities matching adapter roles
- observe_entity_states: read entity states for vocabulary mapping
- get_vacuum_capabilities: detect capability flags for one vacuum
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DATA_RUNTIME,
    DOMAIN,
    SERVICE_DELETE_ADAPTER_CONFIG,
    SERVICE_DISCOVER_ADAPTER_ENTITIES,
    SERVICE_GET_ADAPTER_CONFIG,
    SERVICE_GET_VACUUM_CAPABILITIES,
    SERVICE_OBSERVE_ENTITY_STATES,
    SERVICE_SAVE_ADAPTER_CONFIG,
)
from ._common import get_manager

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_SAVE_ADAPTER_CONFIG,
    SERVICE_DELETE_ADAPTER_CONFIG,
    SERVICE_GET_ADAPTER_CONFIG,
    SERVICE_DISCOVER_ADAPTER_ENTITIES,
    SERVICE_OBSERVE_ENTITY_STATES,
    SERVICE_GET_VACUUM_CAPABILITIES,
)


_GET_VACUUM_CAPABILITIES_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("detected_model"): vol.Any(None, cv.string),
        vol.Optional("refresh", default=True): cv.boolean,
    }
)


async def _handle_save_adapter_config(hass: HomeAssistant, call: ServiceCall) -> None:
    """Save a UI-submitted adapter config for one vacuum."""
    vacuum_entity_id = call.data["vacuum_entity_id"]
    config = dict(call.data["config"])

    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        _LOGGER.error("save_adapter_config: runtime manager not available")
        return

    if not config.get("adapter_id"):
        _LOGGER.error(
            "save_adapter_config: missing adapter_id for %s",
            vacuum_entity_id,
        )
        return
    if not config.get("dispatch", {}).get("template"):
        _LOGGER.error(
            "save_adapter_config: missing dispatch.template for %s",
            vacuum_entity_id,
        )
        return

    # Source field is always set by the service — never trusted from caller.
    config["source"] = "config"

    from ..adapters.config_loader import save_adapter_config as _save_stored
    from ..adapters.registry import register_adapter_config as _register

    _save_stored(manager.data, vacuum_entity_id, config)
    _register(vacuum_entity_id, config)
    await manager.async_save()

    _LOGGER.debug(
        "save_adapter_config: saved and registered adapter '%s' for %s",
        config.get("adapter_id"),
        vacuum_entity_id,
    )


async def _handle_delete_adapter_config(hass: HomeAssistant, call: ServiceCall) -> None:
    """Delete a stored adapter config for one vacuum."""
    vacuum_entity_id = call.data["vacuum_entity_id"]

    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        return

    from ..adapters.config_loader import delete_adapter_config as _delete_stored
    from ..adapters.registry import unregister_adapter_config as _unregister

    deleted = _delete_stored(manager.data, vacuum_entity_id)
    if deleted:
        _unregister(vacuum_entity_id)
        await manager.async_save()
        _LOGGER.debug(
            "delete_adapter_config: deleted adapter config for %s",
            vacuum_entity_id,
        )


async def _handle_get_adapter_config(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return the registered adapter config for one vacuum."""
    vacuum_entity_id = call.data["vacuum_entity_id"]

    from ..adapters.registry import get_adapter_config as _get_config

    config = _get_config(vacuum_entity_id)
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "config": config,
        "source": (config or {}).get("source"),
        "adapter_id": (config or {}).get("adapter_id"),
    }


async def _handle_discover_adapter_entities(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Discover companion entities for a vacuum and suggest role mappings."""
    vacuum_entity_id = call.data["vacuum_entity_id"]
    object_id = vacuum_entity_id.split(".", 1)[-1]

    from homeassistant.helpers import entity_registry as er
    registry = er.async_get(hass)

    matches: list[dict] = []
    for entry in registry.entities.values():
        eid = str(entry.entity_id)
        if object_id in eid:
            state = hass.states.get(eid)
            matches.append({
                "entity_id": eid,
                "domain": eid.split(".")[0],
                "current_state": state.state if state else None,
                "platform": entry.platform,
            })

    by_domain: dict[str, list] = {}
    for match in matches:
        by_domain.setdefault(match["domain"], []).append(match)

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "object_id": object_id,
        "entity_count": len(matches),
        "entities": matches,
        "by_domain": by_domain,
    }


async def _handle_observe_entity_states(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return current states for a list of entities for vocabulary mapping."""
    entity_ids = call.data["entity_ids"]

    observations: list[dict] = []
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is not None:
            observations.append({
                "entity_id": entity_id,
                "state": state.state,
                "attributes": dict(state.attributes),
            })
        else:
            observations.append({
                "entity_id": entity_id,
                "state": None,
                "attributes": {},
            })

    return {
        "observations": observations,
        "entity_count": len(observations),
    }


async def _handle_get_vacuum_capabilities(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Detect and return capability information for one vacuum."""
    vacuum_entity_id = call.data["vacuum_entity_id"]
    detected_model = call.data.get("detected_model")
    refresh = call.data.get("refresh", True)

    payload = get_manager(hass).get_vacuum_capabilities(
        vacuum_entity_id=vacuum_entity_id,
        detected_model=detected_model,
        refresh=refresh,
    )
    _LOGGER.debug("get_vacuum_capabilities complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register adapter-config + capability services."""

    async def save_adapter_config(call: ServiceCall) -> None:
        await _handle_save_adapter_config(hass, call)

    async def delete_adapter_config(call: ServiceCall) -> None:
        await _handle_delete_adapter_config(hass, call)

    async def get_adapter_config(call: ServiceCall) -> dict:
        return await _handle_get_adapter_config(hass, call)

    async def discover_adapter_entities(call: ServiceCall) -> dict:
        return await _handle_discover_adapter_entities(hass, call)

    async def observe_entity_states(call: ServiceCall) -> dict:
        return await _handle_observe_entity_states(hass, call)

    async def get_vacuum_capabilities(call: ServiceCall) -> dict:
        return await _handle_get_vacuum_capabilities(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_ADAPTER_CONFIG, save_adapter_config,
        schema=vol.Schema({
            vol.Required("vacuum_entity_id"): cv.entity_id,
            vol.Required("config"): dict,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_ADAPTER_CONFIG, delete_adapter_config,
        schema=vol.Schema({
            vol.Required("vacuum_entity_id"): cv.entity_id,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_ADAPTER_CONFIG, get_adapter_config,
        schema=vol.Schema({
            vol.Required("vacuum_entity_id"): cv.entity_id,
        }),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISCOVER_ADAPTER_ENTITIES, discover_adapter_entities,
        schema=vol.Schema({
            vol.Required("vacuum_entity_id"): cv.entity_id,
        }),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OBSERVE_ENTITY_STATES, observe_entity_states,
        schema=vol.Schema({
            vol.Required("entity_ids"): [cv.entity_id],
        }),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_VACUUM_CAPABILITIES, get_vacuum_capabilities,
        schema=_GET_VACUUM_CAPABILITIES_SCHEMA, supports_response=True,
    )
