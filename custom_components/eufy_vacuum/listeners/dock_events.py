"""Dock event listeners — record wash / empty / dry events.

Subscribes to each managed vacuum's dock_status entity (per adapter
config). When the state transitions into a configured trigger value,
records the event into the manager's persistent dock-events store.
Used by maintenance tracking and the Base Station tab UI.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager
from ._common import get_adapter_value

_LOGGER = logging.getLogger(__name__)

_DOCK_EVENT_UNSUBS = "_dock_event_unsubs"


def remove(hass: HomeAssistant) -> None:
    """Remove dock event state listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_DOCK_EVENT_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover - best-effort teardown
            _LOGGER.exception("Failed to remove dock event listener")


def register(hass: HomeAssistant) -> None:
    """Register listeners that record dock events (wash, empty, dry) to storage."""
    remove(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    watched: dict[str, str] = {}
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        dock_entity = (get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("dock_status")
        if dock_entity:
            watched[dock_entity] = vacuum_entity_id

    if not watched:
        domain_data[_DOCK_EVENT_UNSUBS] = []
        return

    @callback
    def _handle_dock_event(event: Event) -> None:
        """Handle a dock_status state change and record the event."""
        entity_id = str(event.data.get("entity_id", ""))
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if new_state is None:
            return

        new_val = str(new_state.state).strip().lower()
        old_val = str(old_state.state).strip().lower() if old_state else ""

        if new_val == old_val:
            return

        vacuum_entity_id = watched.get(entity_id)
        if vacuum_entity_id is None:
            return

        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        _triggers = get_adapter_value(
            vacuum_entity_id,
            "dock_events", "triggers",
            fallback={},
        )

        for event_type, trigger_states in _triggers.items():
            trigger_set = frozenset(
                str(s).strip().lower() for s in trigger_states
            )
            if new_val not in trigger_set:
                continue

            dry_duration: str | None = None
            if event_type == "last_dry_start":
                _dry_entity = get_adapter_value(
                    vacuum_entity_id, "entities", "dry_duration", fallback=None
                )
                dry_sel = hass.states.get(_dry_entity) if _dry_entity else None
                if dry_sel is not None and dry_sel.state not in ("unknown", "unavailable", ""):
                    dry_duration = dry_sel.state

            manager_local.record_dock_event(
                vacuum_entity_id=vacuum_entity_id,
                event_type=event_type,
                dry_duration=dry_duration,
            )

            hass.async_create_task(manager_local._async_save_logged())

            _LOGGER.debug(
                "Dock event recorded: %s for %s (dock_status=%s)",
                event_type,
                vacuum_entity_id,
                new_val,
            )

    unsub = async_track_state_change_event(
        hass,
        list(watched.keys()),
        _handle_dock_event,
    )
    domain_data[_DOCK_EVENT_UNSUBS] = [unsub]
