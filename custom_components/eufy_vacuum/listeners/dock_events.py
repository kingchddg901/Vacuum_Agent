"""Dock event listeners — record wash / empty / dry events.

Subscribes to the ``dock_status`` entity of every managed vacuum whose
adapter declares ``dock_events.enabled`` truthy -- not of every managed
vacuum. ``register()`` reads that flag FIRST (``fallback=False``, matching
config_schema.py's "Default: False") and skips the vacuum before it ever
looks at ``entities.dock_status``; the REG-4 comment inside ``register()``
states the same rule at the site. Of the two shipped adapters only Eufy
declares ``"enabled": True`` (adapters/eufy/adapter.py, ``dock_events``
block); the Roborock adapter lists ``dock_events`` among the blocks it
omits entirely, so a managed Roborock gets no subscription at all.
When a watched state transitions into a configured trigger value, records
the event into the manager's persistent dock-events store. Used by
maintenance tracking and the Base Station tab UI.

⚠ was: "Subscribes to each managed vacuum's dock_status entity (per adapter
config)" -- false in both directions, since the default is opt-OUT and one
shipped brand never opts in. Believing it sends anyone asking "why are no
dock events recorded for my Roborock / my new brand?" downstream into the
trigger vocabulary, the edge test and ``record_dock_event``, instead of to
the one-line ``enabled`` gate that returned before any of it ran.

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
    # Per-entity trigger maps for EXTRA watches only. The dock_status entity keeps
    # reading `triggers` live at event time, so the shape that has always worked is
    # byte-identical; an entity absent from here takes that path.
    extra_triggers: dict[str, dict] = {}
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        # REG-4: dock_events.enabled (config_schema.py, default False) gates
        # whether this vacuum's dock_status gets watched at all -- an adapter
        # that declares dock_status but explicitly opts out must get no
        # dock-event listener, not a silently-enabled one.
        if not get_adapter_value(
            vacuum_entity_id, "dock_events", "enabled", fallback=False
        ):
            continue
        _cfg = get_adapter_config(vacuum_entity_id) or {}
        dock_entity = _cfg.get("entities", {}).get("dock_status")
        if dock_entity:
            watched[dock_entity] = vacuum_entity_id

        # ONE SENSOR IS EUFY'S SHAPE, NOT EVERY BRAND'S (issue #62's capture).
        #
        # This listener assumed the whole dock state lives in one `dock_status`
        # string, which is true of Eufy and of nothing else measured since. On a
        # Roborock there is no dock_status role at all: wash and empty appear in the
        # VACUUM's status sensor (`washing_the_mop`, `emptying_the_bin`) and drying
        # appears in NEITHER -- the status returns to `charging` at the same instant
        # the dry switch turns on. Declaring only what a status string can see would
        # have left a dry counter reading a confident zero forever.
        #
        # `extra_watches` is the generic form: each entry names a source and the
        # events it can raise. A `role` is a declared entity role; an `action` is a
        # dock action, resolved through DockManager's three-rung ladder so it still
        # binds on a localized install, where the entity id is in another language
        # ([DK-20]). Nothing here is Roborock-specific.
        for _watch in (_cfg.get("dock_events", {}) or {}).get("extra_watches") or []:
            _trig = _watch.get("triggers") or {}
            if not _trig:
                continue
            _entity: str | None = None
            if _watch.get("role"):
                _entity = _cfg.get("entities", {}).get(_watch["role"])
            elif _watch.get("action"):
                try:
                    _entity = manager.dock._get_dock_action_entity(  # noqa: SLF001
                        vacuum_entity_id=vacuum_entity_id,
                        action=str(_watch["action"]),
                    )
                except Exception:  # pragma: no cover - defensive
                    _LOGGER.debug(
                        "dock_events: could not resolve action %r for %s",
                        _watch.get("action"), vacuum_entity_id, exc_info=True,
                    )
                    _entity = None
            if not _entity:
                _LOGGER.debug(
                    "dock_events: extra_watch %r for %s resolved no entity — the "
                    "events it carries will not be recorded",
                    _watch.get("role") or _watch.get("action"), vacuum_entity_id,
                )
                continue
            watched[_entity] = vacuum_entity_id
            # An entity named twice merges rather than replaces: a brand may route
            # two events through one source.
            extra_triggers[_entity] = {**extra_triggers.get(_entity, {}), **_trig}

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

        # An EXTRA watch carries its own map (it is not the dock_status string and
        # the brand's `triggers` vocabulary does not describe it). Everything else
        # reads `triggers` live, exactly as before.
        _triggers = extra_triggers.get(entity_id)
        if _triggers is None:
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
