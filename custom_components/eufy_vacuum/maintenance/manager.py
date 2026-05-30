"""MaintenanceManager — owns maintenance reset snapshots and remaining-hours
calculations for each managed vacuum component.

Also exports two pure-function status helpers (maintenance_status,
replacement_status) used by the upkeep snapshot composer in
core/manager.py — they have no dependencies and live here as the
natural home for maintenance logic.

Design
------
Constructed inside EufyVacuumManager after storage is loaded.  Receives:
- data        -- reference to the integration's root data dict
                 (reads/writes data["maintenance"] in place)
- hass        -- HomeAssistant instance (to read source-entity states)
- get_capabilities -- callable matching manager.get_vacuum_capabilities
                 (used to resolve the source entity for each component)

The three public methods are direct lifts from EufyVacuumManager;
EufyVacuumManager keeps thin delegation shims for backward compat with
the services/ layer and sensors that call manager.reset_maintenance() etc.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure-function status helpers
# ---------------------------------------------------------------------------


def maintenance_status(*, remaining_hours: float, interval_hours: float) -> str:
    """Return maintenance status bucket for one component."""
    if interval_hours <= 0:
        return "unknown"
    ratio = remaining_hours / interval_hours
    if remaining_hours <= 0:
        return "replace_now"
    if ratio <= 0.1:
        return "replace_soon"
    if ratio <= 0.25:
        return "warning"
    return "good"


def replacement_status(*, state_value: Any) -> str:
    """Return replacement status bucket from upstream remaining value."""
    try:
        numeric = float(state_value)
    except (TypeError, ValueError):
        return "unknown"
    if numeric <= 5:
        return "replace_now"
    if numeric <= 15:
        return "replace_soon"
    if numeric <= 30:
        return "warning"
    return "good"


# ---------------------------------------------------------------------------
# MaintenanceManager
# ---------------------------------------------------------------------------


class MaintenanceManager:
    """Owns maintenance state, reset snapshots, and remaining-hours logic."""

    def __init__(
        self,
        data: dict[str, Any],
        hass: HomeAssistant,
        get_capabilities,
    ) -> None:
        """Initialise with references to root data, hass, and capabilities resolver.

        Args:
            data:             Integration root data dict — reads/writes data["maintenance"].
            hass:             HomeAssistant instance (to read source entity states).
            get_capabilities: Callable(vacuum_entity_id, refresh) → capabilities dict.
                              Pass manager.get_vacuum_capabilities.
        """
        self._data = data
        self._hass = hass
        self._get_capabilities = get_capabilities
        self._data.setdefault("maintenance", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_maintenance_state(self, *, vacuum_entity_id: str) -> dict[str, Any]:
        """Return current maintenance reset snapshots for one vacuum."""
        self._data.setdefault("maintenance", {})
        return self._data["maintenance"].setdefault(vacuum_entity_id, {})

    def reset_maintenance(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
    ) -> dict[str, Any]:
        """Snapshot current usage_hours for a component as the new reset point."""
        from ..timestamp_utils import utc_now_iso

        capabilities = self._get_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        source_entity = sources.get(component)

        if source_entity is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "no_source_entity",
            }

        state = self._hass.states.get(source_entity)
        if state is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "source_unavailable",
                "source_entity": source_entity,
            }

        try:
            usage_hours = float(state.attributes.get("usage_hours", 0))
        except (TypeError, ValueError):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "invalid_usage_hours",
                "source_entity": source_entity,
            }

        maintenance = self.get_maintenance_state(vacuum_entity_id=vacuum_entity_id)
        maintenance[component] = {
            "reset_at_usage_hours": usage_hours,
            "reset_at": utc_now_iso(),
        }

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "component": component,
            "reset": True,
            "reset_at_usage_hours": usage_hours,
            "reset_at": maintenance[component]["reset_at"],
            "source_entity": source_entity,
        }

    def get_maintenance_remaining(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
        interval_hours: float,
    ) -> dict[str, Any]:
        """Return remaining maintenance hours for one component."""
        capabilities = self._get_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        source_entity = sources.get(component)

        current_usage: float = 0.0
        source_available = False

        if source_entity:
            state = self._hass.states.get(source_entity)
            if state is not None:
                try:
                    current_usage = float(state.attributes.get("usage_hours", 0))
                    source_available = True
                except (TypeError, ValueError):
                    pass

        maintenance = self.get_maintenance_state(vacuum_entity_id=vacuum_entity_id)
        component_data = maintenance.get(component, {})
        reset_snapshot = float(component_data.get("reset_at_usage_hours", 0.0))
        reset_at = component_data.get("reset_at")

        used_since_reset = max(current_usage - reset_snapshot, 0.0)
        remaining = max(interval_hours - used_since_reset, 0.0)

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "component": component,
            "remaining_hours": round(remaining, 2),
            "used_since_reset_hours": round(used_since_reset, 2),
            "interval_hours": interval_hours,
            "current_usage_hours": round(current_usage, 2),
            "reset_at_usage_hours": reset_snapshot,
            "reset_at": reset_at,
            "source_entity": source_entity,
            "source_available": source_available,
        }
