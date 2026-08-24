"""
Stored adapter config loader for the ha_vacuum_manager framework.

Reads stored adapter configs from integration storage and registers them with the
adapter registry at startup.

⚠ was: "written by the UI wizard" — there is no UI wizard (ledger A27, corrected
2026-08-24). ``config_flow.py`` contains no reference to adapters at all, and
``save_adapter_config`` appears nowhere in the card's JS/TS sources. The only writers of
``data["adapters"]`` are this module's own ``save_adapter_config()`` and the
``eufy_vacuum.save_adapter_config`` SERVICE that calls it — and
``services/adapter_config.py`` describes its own six services as driving the flow "for
future multi-brand setups", while ``config_schema.py``'s module docstring marks the UI
config flow as the thing that "will generate it in a future pass". Someone tracing "who
writes data['adapters']" went hunting for a config-flow step that does not exist.
``registry.py::register_adapter_config`` gets the wording right: UI/SERVICE-authored.

ORDERING — what it buys, and the invariant it does NOT establish. ``async_setup_entry``
calls ``load_stored_adapter_configs`` BEFORE ``register_brand_adapter``, so AT STARTUP a
code adapter registered afterwards overwrites a stored config for the same vacuum.

⚠ was: "so that code adapters always take precedence over stored configs for the same
vacuum" — "always" states an invariant the system does not hold (ledger A8, corrected
2026-08-24). ``services/adapter_config.py::_handle_save_adapter_config`` calls
``save_adapter_config()`` and then ``registry.register_adapter_config()`` DIRECTLY, so a
saved config registers over whatever code adapter is live and stays in force for the rest
of the session. Both ``registry.register_adapter_config`` and
``config_schema.validate_adapter_config`` describe that direction in their own docstrings,
as a stored config "shadowing the live adapter". The real behaviour is a flip-flop: the
save wins now, and the startup ordering hands the vacuum back to the code adapter at the
next restart. That is the shape of "my saved adapter config works until I reboot Home
Assistant" — worth knowing before touching either registration path.

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
    Called from async_setup_entry before code adapter registration, so a code
    adapter registered afterward overwrites these for the same vacuum entity ID
    ON THIS STARTUP PASS. That is an ordering fact about setup, not a standing
    precedence rule — see the module docstring's ORDERING note for the
    save-service path that reverses it mid-session.
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
