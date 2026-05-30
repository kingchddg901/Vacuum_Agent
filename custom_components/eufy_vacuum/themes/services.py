"""HA service handlers for the Eufy Vacuum theme system.

Absorbed from the standalone theme_services.py module.  Validation
failures raise ``ServiceValidationError`` (HA Silver action-exceptions
requirement) rather than returning ``{"ok": False, ...}``.  Pure data
operations that cannot fail (get_library, update_draft, revert) return
their dict directly.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DATA_RUNTIME,
    DOMAIN,
    SERVICE_DELETE_THEME,
    SERVICE_EXPORT_THEME,
    SERVICE_GET_THEME_LIBRARY,
    SERVICE_IMPORT_THEME,
    SERVICE_OVERWRITE_THEME,
    SERVICE_RENAME_THEME,
    SERVICE_REVERT_DRAFT,
    SERVICE_SAVE_THEME_AS_NEW,
    SERVICE_SET_ACTIVE_THEME,
    SERVICE_UPDATE_WORKING_DRAFT,
)

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

GET_THEME_LIBRARY_SCHEMA = vol.Schema({})

SAVE_THEME_AS_NEW_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("name"): cv.string,
        vol.Optional("set_as_default", default=False): cv.boolean,
    }
)

OVERWRITE_THEME_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("theme_id"): cv.string,
    }
)

RENAME_THEME_SCHEMA = vol.Schema(
    {
        vol.Required("theme_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)

DELETE_THEME_SCHEMA = vol.Schema(
    {
        vol.Required("theme_id"): cv.string,
    }
)

SET_ACTIVE_THEME_SCHEMA = vol.Schema(
    {
        vol.Optional("vacuum_entity_id"): vol.Any(None, cv.entity_id),
        vol.Required("theme_id"): cv.string,
    }
)

UPDATE_WORKING_DRAFT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("tokens"): dict,
        vol.Optional("colors"): dict,
        vol.Optional("alpha"): dict,
    }
)

REVERT_DRAFT_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)

EXPORT_THEME_SCHEMA = vol.Schema(
    {
        vol.Required("theme_id"): cv.string,
    }
)

IMPORT_THEME_SCHEMA = vol.Schema(
    {
        vol.Required("payload"): dict,
    }
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_THEME_NOT_FOUND_REASONS = frozenset({"theme_not_found"})
_IMPORT_VALIDATION_REASONS = frozenset(
    {"invalid_payload", "missing_theme", "missing_name", "invalid_tokens", "invalid_colors", "invalid_alpha"}
)


def _get_manager(hass: HomeAssistant):
    """Return the integration manager."""
    return hass.data[DOMAIN][DATA_RUNTIME]


def _raise_if_failed(result: dict, *, operation: str) -> None:
    """Raise ServiceValidationError when a theme operation returns ok=False."""
    if not result.get("ok", True):
        reason = result.get("reason", "unknown_error")
        raise ServiceValidationError(
            f"{operation} failed: {reason}",
            translation_domain=DOMAIN,
            translation_key="theme_operation_failed",
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def async_register_theme_services(hass: HomeAssistant) -> None:
    """Register all theme-related HA services with their schemas."""

    async def handle_get_theme_library(call: ServiceCall) -> dict:
        result = _get_manager(hass).get_theme_library()
        _LOGGER.debug("get_theme_library complete: %s", result)
        return result

    async def handle_save_theme_as_new(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.save_theme_as_new(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            name=call.data["name"],
            set_as_default=call.data.get("set_as_default", False),
        )
        _LOGGER.debug("save_theme_as_new complete: %s", result)
        await manager.async_save()
        return result

    async def handle_overwrite_theme(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.overwrite_theme(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            theme_id=call.data["theme_id"],
        )
        _LOGGER.debug("overwrite_theme complete: %s", result)
        _raise_if_failed(result, operation="overwrite_theme")
        await manager.async_save()
        return result

    async def handle_rename_theme(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.rename_theme(
            theme_id=call.data["theme_id"],
            name=call.data["name"],
        )
        _LOGGER.debug("rename_theme complete: %s", result)
        _raise_if_failed(result, operation="rename_theme")
        await manager.async_save()
        return result

    async def handle_delete_theme(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.delete_theme(theme_id=call.data["theme_id"])
        _LOGGER.debug("delete_theme complete: %s", result)
        _raise_if_failed(result, operation="delete_theme")
        await manager.async_save()
        return result

    async def handle_set_active_theme(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.set_active_theme(
            vacuum_entity_id=call.data.get("vacuum_entity_id"),
            theme_id=call.data["theme_id"],
        )
        _LOGGER.debug("set_active_theme complete: %s", result)
        _raise_if_failed(result, operation="set_active_theme")
        await manager.async_save()
        return result

    async def handle_update_working_draft(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.update_working_draft(
            vacuum_entity_id=call.data["vacuum_entity_id"],
            tokens=call.data.get("tokens"),
            colors=call.data.get("colors"),
            alpha=call.data.get("alpha"),
        )
        _LOGGER.debug("update_working_draft complete: %s", result)
        await manager.async_save()
        return result

    async def handle_revert_draft(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.revert_draft(
            vacuum_entity_id=call.data["vacuum_entity_id"],
        )
        _LOGGER.debug("revert_draft complete: %s", result)
        await manager.async_save()
        return result

    async def handle_export_theme(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.export_theme(theme_id=call.data["theme_id"])
        _LOGGER.debug("export_theme complete: %s", result)
        _raise_if_failed(result, operation="export_theme")
        return result

    async def handle_import_theme(call: ServiceCall) -> dict:
        manager = _get_manager(hass)
        result = manager.import_theme(payload=call.data["payload"])
        _LOGGER.debug("import_theme complete: %s", result)
        _raise_if_failed(result, operation="import_theme")
        await manager.async_save()
        return result

    hass.services.async_register(
        DOMAIN, SERVICE_GET_THEME_LIBRARY, handle_get_theme_library,
        schema=GET_THEME_LIBRARY_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_THEME_AS_NEW, handle_save_theme_as_new,
        schema=SAVE_THEME_AS_NEW_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OVERWRITE_THEME, handle_overwrite_theme,
        schema=OVERWRITE_THEME_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RENAME_THEME, handle_rename_theme,
        schema=RENAME_THEME_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_THEME, handle_delete_theme,
        schema=DELETE_THEME_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ACTIVE_THEME, handle_set_active_theme,
        schema=SET_ACTIVE_THEME_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_WORKING_DRAFT, handle_update_working_draft,
        schema=UPDATE_WORKING_DRAFT_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REVERT_DRAFT, handle_revert_draft,
        schema=REVERT_DRAFT_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_EXPORT_THEME, handle_export_theme,
        schema=EXPORT_THEME_SCHEMA,
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT_THEME, handle_import_theme,
        schema=IMPORT_THEME_SCHEMA,
        supports_response=True,
    )


async def async_unregister_theme_services(hass: HomeAssistant) -> None:
    """Unregister theme services."""
    for service_name in (
        SERVICE_GET_THEME_LIBRARY,
        SERVICE_SAVE_THEME_AS_NEW,
        SERVICE_OVERWRITE_THEME,
        SERVICE_RENAME_THEME,
        SERVICE_DELETE_THEME,
        SERVICE_SET_ACTIVE_THEME,
        SERVICE_UPDATE_WORKING_DRAFT,
        SERVICE_REVERT_DRAFT,
        SERVICE_EXPORT_THEME,
        SERVICE_IMPORT_THEME,
    ):
        hass.services.async_remove(DOMAIN, service_name)
