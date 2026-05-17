"""
Adapter config registry for the ha_vacuum_manager framework.

Maintains a per-vacuum adapter config dict in memory. Both the code
adapter path and the config adapter path write to this registry.
The framework reads from it at runtime.

Usage:
    # Code adapter registers at startup:
    from .adapters.registry import register_adapter_config, get_adapter_config
    register_adapter_config(vacuum_entity_id, config_dict)

    # Framework reads at runtime:
    config = get_adapter_config(vacuum_entity_id)
    if config is None:
        # No adapter registered — degrade gracefully

The registry is in-memory only. It is repopulated on every HA restart
by the adapter registration call in async_setup_entry.

Config adapters (UI-generated) are loaded from storage during
async_setup_entry and registered via the same path.
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# In-memory registry: vacuum_entity_id -> adapter config dict
_REGISTRY: dict[str, dict[str, Any]] = {}


def register_adapter_config(
    vacuum_entity_id: str,
    config: dict[str, Any],
) -> None:
    """Register an adapter config for one vacuum.

    Idempotent — re-registering the same vacuum overwrites the previous
    config. Called at startup by the code adapter and by the config
    adapter loader when reading from storage.
    """
    _REGISTRY[vacuum_entity_id] = config
    _LOGGER.debug(
        "adapter_registry: registered adapter '%s' for %s (source=%s)",
        config.get("adapter_id", "unknown"),
        vacuum_entity_id,
        config.get("source", "unknown"),
    )


def get_adapter_config(
    vacuum_entity_id: str,
) -> dict[str, Any] | None:
    """Return the adapter config for one vacuum, or None if not registered."""
    return _REGISTRY.get(vacuum_entity_id)


def get_all_adapter_configs() -> dict[str, dict[str, Any]]:
    """Return a snapshot of all registered adapter configs."""
    return dict(_REGISTRY)


def unregister_adapter_config(vacuum_entity_id: str) -> None:
    """Remove the adapter config for one vacuum. Called on entry unload."""
    _REGISTRY.pop(vacuum_entity_id, None)


def clear_registry() -> None:
    """Clear all registered configs. Called on integration unload."""
    _REGISTRY.clear()
