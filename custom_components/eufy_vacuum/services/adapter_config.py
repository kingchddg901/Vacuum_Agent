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

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INGZFYXX  `profiles/manager.py#INGZFYXX`
#       A4-SETUP-5 (closed RP-033): save_adapter_config persists to storage BEFORE registering, so a config the registry
#              flags as invalid is written to disk anyway and reloaded at every restart


from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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


async def _handle_save_adapter_config(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save a UI-submitted adapter config for one vacuum."""
    vacuum_entity_id = call.data["vacuum_entity_id"]
    config = dict(call.data["config"])

    # RP-031/Q9: runtime manager missing is an INTERNAL failure (unexpected system
    # state), not something the caller did wrong -- HomeAssistantError, not SVE.
    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        raise HomeAssistantError("save_adapter_config: runtime manager not available")

    # Source field is always set by the service — never trusted from caller.
    # Forced BEFORE validation so a caller who (correctly) never supplies it
    # doesn't fail the schema's required-key check on a field it never owns.
    config["source"] = "config"

    # RP-033/RF-32 (INYA5T84): the config's schema used to be `dict` only, checked by hand for
    # exactly two keys (adapter_id, dispatch.template) here -- every OTHER required
    # block (entities, dispatch.service_domain, dispatch.service_name, ...) was
    # silently absent-safe, registering OVER the live adapter with each omitted
    # block falling through to that block's own absent-default (Eufy-shaped)
    # behaviour. ADAPTER_CONFIG_SCHEMA is now applied in full -- the SAME walk the
    # adapter contract test suite runs against the shipped brands -- and this runs
    # strictly BEFORE _save_stored/_register below: validate, then persist.
    from ..adapters.config_schema import validate_adapter_config

    issues = validate_adapter_config(config)
    if issues:
        raise ServiceValidationError(
            f"save_adapter_config: invalid config for {vacuum_entity_id}: "
            + "; ".join(issues)
        )

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
    return {
        "saved": True,
        "vacuum_entity_id": vacuum_entity_id,
        "adapter_id": config.get("adapter_id"),
    }


async def _handle_delete_adapter_config(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete a stored adapter config for one vacuum."""
    vacuum_entity_id = call.data["vacuum_entity_id"]

    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        raise HomeAssistantError("delete_adapter_config: runtime manager not available")

    from ..adapters.config_loader import delete_adapter_config as _delete_stored
    from ..adapters.registry import unregister_adapter_config as _unregister

    deleted = _delete_stored(manager.data, vacuum_entity_id)
    if not deleted:
        # RP-031/Q9: matches the sibling not-found convention already used across
        # this codebase for delete-type services (discard_external_run,
        # delete_saved_zone) -- a structured refusal, not an exception, since
        # deleting an already-absent config is a normal idempotent no-op a caller
        # may not consider an error.
        return {
            "deleted": False,
            "vacuum_entity_id": vacuum_entity_id,
            "reason": "not_found",
        }

    _unregister(vacuum_entity_id)

    # RP-033/SETUP-3: unregistering alone left the vacuum with NO adapter at all
    # until the next full HA restart -- every dispatch/lifecycle/capability read
    # depending on the registry got nothing back in the meantime. Restore the live
    # CODE adapter the same way a restart already would: register_brand_adapter is
    # the exact function __init__.py calls per managed vacuum during
    # async_setup_entry, so this makes delete's restore byte-identical to that.
    from ..adapters.brands import register_brand_adapter

    register_brand_adapter(hass, vacuum_entity_id, data=manager.data)

    await manager.async_save()
    _LOGGER.debug(
        "delete_adapter_config: deleted stored adapter config for %s and "
        "restored the code adapter",
        vacuum_entity_id,
    )
    return {"deleted": True, "vacuum_entity_id": vacuum_entity_id}


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

    async def save_adapter_config(call: ServiceCall) -> dict:
        return await _handle_save_adapter_config(hass, call)

    async def delete_adapter_config(call: ServiceCall) -> dict:
        return await _handle_delete_adapter_config(hass, call)

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
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_ADAPTER_CONFIG, delete_adapter_config,
        schema=vol.Schema({
            vol.Required("vacuum_entity_id"): cv.entity_id,
        }),
        supports_response=True,
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
