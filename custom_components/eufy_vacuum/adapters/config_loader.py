"""
Stored adapter config loader for the ha_vacuum_manager framework.

Reads adapter configs written by the UI wizard from integration storage
and registers them with the adapter registry at startup.

Called from async_setup_entry before code adapter registration so that
code adapters always take precedence over stored configs for the same
vacuum.

Storage path: data["adapters"][vacuum_entity_id] -> adapter config dict
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .registry import register_adapter_config

_LOGGER = logging.getLogger(__name__)


def load_stored_adapter_configs(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> int:
    """Load and register all stored adapter configs from integration storage.

    Returns the number of configs successfully registered.
    Called from async_setup_entry before code adapter registration.
    Code adapters registered afterward will overwrite these for the
    same vacuum entity ID.
    """
    stored_adapters = data.get("adapters", {})
    if not isinstance(stored_adapters, dict):
        return 0

    count = 0
    for vacuum_entity_id, config in stored_adapters.items():
        if not isinstance(config, dict):
            _LOGGER.warning(
                "config_loader: skipping malformed adapter config for %s",
                vacuum_entity_id,
            )
            continue
        try:
            register_adapter_config(vacuum_entity_id, config)
            count += 1
            _LOGGER.debug(
                "config_loader: loaded stored adapter config for %s "
                "(adapter_id=%s)",
                vacuum_entity_id,
                config.get("adapter_id", "unknown"),
            )
        except Exception:
            _LOGGER.exception(
                "config_loader: failed to register stored adapter config "
                "for %s",
                vacuum_entity_id,
            )
    return count


def save_adapter_config(
    data: dict[str, Any],
    vacuum_entity_id: str,
    config: dict[str, Any],
) -> None:
    """Write an adapter config to the storage data dict.

    The caller is responsible for calling manager.async_save() after this.
    Does not register the config with the registry — call
    register_adapter_config() separately after saving.
    """
    data.setdefault("adapters", {})
    data["adapters"][vacuum_entity_id] = config


def delete_adapter_config(
    data: dict[str, Any],
    vacuum_entity_id: str,
) -> bool:
    """Remove a stored adapter config from the storage data dict.

    Returns True if a config was present and removed, False otherwise.
    The caller is responsible for calling manager.async_save() after this.
    """
    adapters = data.get("adapters", {})
    if vacuum_entity_id not in adapters:
        return False
    del adapters[vacuum_entity_id]
    return True


def get_stored_adapter_config(
    data: dict[str, Any],
    vacuum_entity_id: str,
) -> dict[str, Any] | None:
    """Return a stored adapter config from the storage data dict, or None."""
    return data.get("adapters", {}).get(vacuum_entity_id)
