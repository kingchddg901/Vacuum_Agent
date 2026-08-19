"""Dock event listeners — record wash / empty / dry events.

Subscribes to each managed vacuum's dock_status entity (per adapter
config). When the state transitions into a configured trigger value,
records the event into the manager's persistent dock-events store.
Used by maintenance tracking and the Base Station tab UI.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
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
#   IN96V4SA  `listeners/_common.py#IN96V4SA`
#       A1-REG-1 (closed RP-038): dock_events treats any arrival at a trigger value as a NEW dock cycle — a startup,
#              an entity re-add, or an `unavailable` blip mid-cycle re-records the event and
#       A1-REG-4 (closed RP-038): dock_events.register() never reads the adapter's `dock_events.enabled` flag — a
#              brand that declares enabled:False but inherits triggers still records dock events


from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager
from ._common import get_adapter_value, is_dock_trigger_edge

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
        # REG-4: dock_events.enabled (config_schema.py, default False) gates
        # whether this vacuum's dock_status gets watched at all -- an adapter
        # that declares dock_status but explicitly opts out must get no
        # dock-event listener, not a silently-enabled one.
        if not get_adapter_value(
            vacuum_entity_id, "dock_events", "enabled", fallback=False
        ):
            continue
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

        # Raw (un-normalized) values for the shared edge test -- it does its
        # own strip/lower normalization, matching both callers' prior
        # behaviour. old_state may be None (HA restart / first sighting).
        old_val_raw = old_state.state if old_state is not None else None
        new_val_raw = new_state.state
        new_val = str(new_val_raw).strip().lower()

        for event_type, trigger_states in _triggers.items():
            trigger_set = frozenset(
                str(s).strip().lower() for s in trigger_states
            )
            # REG-1/GUARD-3 + old==new dedup, all via the shared edge test
            # (also used by lifecycle.py's inline mop-wash detector) -- not
            # an edge if old_state isn't a known real prior value (missing/
            # unavailable/unknown), not an edge if old==new, otherwise an
            # edge iff new_val is in this event_type's trigger vocabulary.
            if not is_dock_trigger_edge(old_val_raw, new_val_raw, trigger_set):
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
