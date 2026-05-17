"""
Adapter config registry for the ha_vacuum_manager framework.

This module owns the per-vacuum adapter config mapping. There are two
co-existing access surfaces, kept aligned during the migration from
module-level state to a per-config-entry coordinator:

  1. **AdapterCoordinator** — the new pattern. One instance is constructed
     in ``__init__.py:async_setup_entry`` and stashed under
     ``hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR]``. Its public methods
     mirror the bare module-level functions one-for-one. New code should
     use the coordinator.

  2. **Bare module-level functions** — the legacy pattern. These exist
     as thin shims that route to the active coordinator when one is
     present, falling back to a module-level ``_REGISTRY`` dict
     otherwise. The shims keep the ~99 existing call sites working
     without simultaneous code churn. They can be migrated to
     ``coordinator.get_adapter_config(...)`` in subsequent passes and
     deleted once the last call site is converted.

Storage on disk (the user-built "config adapter" overlay) is handled
by ``config_loader.py`` and writes into ``manager.data``, independent
of the registry — both the legacy and coordinator surfaces consume
those entries the same way.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback module-level registry.
#
# Used for two purposes:
#   - As the backing store when no AdapterCoordinator has been constructed
#     yet (e.g. during unit tests that exercise the registry directly,
#     or any code path that runs before async_setup_entry completes).
#   - As the *only* store before the coordinator wiring is added to
#     async_setup_entry. After that wiring is in place, the coordinator
#     becomes the canonical store and this dict stays empty in normal
#     operation.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Active coordinator pointer.
#
# Set by AdapterCoordinator.__init__ when an instance is constructed and
# cleared by AdapterCoordinator.shutdown(). The bare-function shims below
# check this pointer first; only when it's None do they fall back to
# _REGISTRY. The single-instance guard on this integration
# (async_set_unique_id(DOMAIN)) means there's never more than one
# coordinator alive at a time, so this pointer is a safe lookup vehicle.
# ---------------------------------------------------------------------------

_active_coordinator: AdapterCoordinator | None = None


def _set_active_coordinator(coordinator: AdapterCoordinator | None) -> None:
    """Set or clear the module-level active coordinator pointer.

    Called from AdapterCoordinator's own lifecycle methods. External code
    should not call this directly — go through the coordinator's
    constructor and ``shutdown()``.
    """
    global _active_coordinator
    _active_coordinator = coordinator


def get_active_coordinator() -> AdapterCoordinator | None:
    """Return the currently-active coordinator, or None if none constructed.

    Useful for code paths that prefer the coordinator API but need to
    handle the pre-setup / test-fixture case gracefully.
    """
    return _active_coordinator


# ---------------------------------------------------------------------------
# AdapterCoordinator class.
#
# One instance per config entry. Holds the adapter registry as instance
# state (an attribute, not a module-level dict). When the integration
# unloads, the coordinator is dropped from hass.data and its registry
# goes with it — no manual unregistration loop needed.
# ---------------------------------------------------------------------------


class AdapterCoordinator:
    """Per-config-entry adapter registry.

    Single owner of the in-memory ``vacuum_entity_id -> adapter_config``
    mapping for one config entry. Instance methods mirror the module-level
    function names so callers can migrate one-for-one without rewriting
    their lookup logic.

    Lifecycle:
      - Constructed in ``async_setup_entry`` (in ``__init__.py``).
      - Stashed under ``hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR]``.
      - Sets itself as the module-level active coordinator so legacy
        bare-function callers route through it.
      - Torn down in ``async_unload_entry`` via ``shutdown()``, which
        clears the active pointer and drops the instance registry.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        # Per-instance registry. The module-level _REGISTRY is left
        # alone — it's only consulted by the bare-function fallback
        # when no coordinator is active.
        self._registry: dict[str, dict[str, Any]] = {}
        _set_active_coordinator(self)
        _LOGGER.debug(
            "AdapterCoordinator: constructed for entry %s", entry.entry_id
        )

    def shutdown(self) -> None:
        """Clear the registry and detach from the module-level pointer.

        Called from ``async_unload_entry``. Safe to call multiple times.
        """
        if _active_coordinator is self:
            _set_active_coordinator(None)
        self._registry.clear()
        _LOGGER.debug(
            "AdapterCoordinator: shutdown for entry %s", self.entry.entry_id
        )

    # ----- registry methods -------------------------------------------------

    def register_adapter_config(
        self,
        vacuum_entity_id: str,
        config: dict[str, Any],
    ) -> None:
        """Register an adapter config for one vacuum.

        Idempotent — re-registering the same vacuum overwrites the previous
        config. Runs ``_validate_adapter`` and logs every issue. Hard-fails
        only on structurally unusable configs (non-dict); other issues are
        warnings.
        """
        issues = _validate_adapter(config)
        if issues:
            adapter_id = (
                config.get("adapter_id", "unknown")
                if isinstance(config, dict) else "unknown"
            )
            for issue in issues:
                _LOGGER.warning(
                    "adapter_registry: %s for %s — %s",
                    adapter_id, vacuum_entity_id, issue,
                )
            if not isinstance(config, dict):
                raise TypeError(
                    f"adapter config for {vacuum_entity_id} is not a dict; "
                    f"refusing to register"
                )

        self._registry[vacuum_entity_id] = config
        _LOGGER.debug(
            "adapter_registry: registered adapter '%s' for %s (source=%s)",
            config.get("adapter_id", "unknown"),
            vacuum_entity_id,
            config.get("source", "unknown"),
        )

    def get_adapter_config(
        self,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Return the adapter config for one vacuum, or None if not registered."""
        return self._registry.get(vacuum_entity_id)

    def get_all_adapter_configs(self) -> dict[str, dict[str, Any]]:
        """Return a snapshot of all registered adapter configs."""
        return dict(self._registry)

    def unregister_adapter_config(self, vacuum_entity_id: str) -> None:
        """Remove the adapter config for one vacuum. Safe if absent."""
        self._registry.pop(vacuum_entity_id, None)

    def clear_registry(self) -> None:
        """Clear all registered configs. Used by tests and on full reset."""
        self._registry.clear()

    # ----- convenience lookups ---------------------------------------------

    def get_adapter_value(
        self,
        vacuum_entity_id: str,
        *path: str,
        fallback: Any = None,
    ) -> Any:
        """Convenience: nested-path lookup with a default."""
        node: Any = self._registry.get(vacuum_entity_id) or {}
        for key in path:
            if not isinstance(node, dict):
                return fallback
            node = node.get(key)
            if node is None:
                return fallback
        return node


# ---------------------------------------------------------------------------
# Validation helper.
#
# Lives at module scope (not on the class) so it can be called from the
# bare-function shims as well as the coordinator method. The shape is
# stable: dict-of-config -> list-of-issue-strings.
# ---------------------------------------------------------------------------


def _validate_adapter(config: dict[str, Any]) -> list[str]:
    """Return a list of validation issue strings; empty = config is valid.

    Currently checks:
      - mapping.segmenter_engine resolves to a known engine
      - mapping.segmenter_tuning passes the engine's own tuning validator

    More rules (required entities, completion block presence, dispatch
    template recognition) land here as the framework's expectations
    harden.
    """
    issues: list[str] = []

    if not isinstance(config, dict):
        return ["adapter config must be a dict"]

    # Segmenter engine check — deferred import keeps the registry module
    # free of mapping dependencies at import time.
    mapping_block = config.get("mapping")
    if mapping_block is not None:
        if not isinstance(mapping_block, dict):
            issues.append("'mapping' must be a dict if present")
        else:
            from ..mapping.segmenter_engines import (
                known_engine_names,
                get_segmenter_engine,
            )

            engine_name = mapping_block.get("segmenter_engine")
            if engine_name is None:
                issues.append(
                    "mapping.segmenter_engine is required when 'mapping' is "
                    "present; declare 'noop_fallback' to disable segmentation"
                )
            elif engine_name not in known_engine_names():
                issues.append(
                    f"mapping.segmenter_engine {engine_name!r} is unknown; "
                    f"valid names: {sorted(known_engine_names())}"
                )
            else:
                tuning = mapping_block.get("segmenter_tuning") or {}
                engine = get_segmenter_engine(engine_name)
                issues.extend(engine.validate_tuning(tuning))

    return issues


# ---------------------------------------------------------------------------
# Bare-function shims.
#
# These match the legacy module-level API exactly. They route to the
# active coordinator when one is present; otherwise they touch the
# module-level _REGISTRY so test fixtures and pre-setup paths still work.
#
# Net effect during the migration window: legacy callers
# (~99 call sites across 22 files) keep working unchanged while the
# underlying storage relocates from a module-level dict to coordinator
# instance state.
#
# When migration completes (every call site uses
# coordinator.method(...) explicitly), these shims and the fallback
# _REGISTRY dict can be deleted together. Until then they're the
# safety net.
# ---------------------------------------------------------------------------


def register_adapter_config(
    vacuum_entity_id: str,
    config: dict[str, Any],
) -> None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        _active_coordinator.register_adapter_config(vacuum_entity_id, config)
        return

    # Fallback path — no coordinator constructed yet.
    issues = _validate_adapter(config)
    if issues:
        adapter_id = (
            config.get("adapter_id", "unknown")
            if isinstance(config, dict) else "unknown"
        )
        for issue in issues:
            _LOGGER.warning(
                "adapter_registry (fallback): %s for %s — %s",
                adapter_id, vacuum_entity_id, issue,
            )
        if not isinstance(config, dict):
            raise TypeError(
                f"adapter config for {vacuum_entity_id} is not a dict; "
                f"refusing to register"
            )

    _REGISTRY[vacuum_entity_id] = config
    _LOGGER.debug(
        "adapter_registry (fallback): registered adapter '%s' for %s (source=%s)",
        config.get("adapter_id", "unknown"),
        vacuum_entity_id,
        config.get("source", "unknown"),
    )


def get_adapter_config(
    vacuum_entity_id: str,
) -> dict[str, Any] | None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        return _active_coordinator.get_adapter_config(vacuum_entity_id)
    return _REGISTRY.get(vacuum_entity_id)


def get_all_adapter_configs() -> dict[str, dict[str, Any]]:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        return _active_coordinator.get_all_adapter_configs()
    return dict(_REGISTRY)


def unregister_adapter_config(vacuum_entity_id: str) -> None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        _active_coordinator.unregister_adapter_config(vacuum_entity_id)
        return
    _REGISTRY.pop(vacuum_entity_id, None)


def clear_registry() -> None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        _active_coordinator.clear_registry()
        return
    _REGISTRY.clear()


def get_adapter_value(
    vacuum_entity_id: str,
    *path: str,
    fallback: Any = None,
) -> Any:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        return _active_coordinator.get_adapter_value(
            vacuum_entity_id, *path, fallback=fallback
        )
    node: Any = _REGISTRY.get(vacuum_entity_id) or {}
    for key in path:
        if not isinstance(node, dict):
            return fallback
        node = node.get(key)
        if node is None:
            return fallback
    return node
