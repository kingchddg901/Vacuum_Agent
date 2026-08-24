"""Trigger the device clean-order READ. Startup once, then on each dock arrival.

⚠ WHY THIS FILE EXISTS: ``CleanOrderManager.async_read`` HAD NO CALLERS. It was
written, tested and shipped, and nothing in the package ever invoked it — so the
sensor sat at ``never_read`` forever on every install. That is not a cosmetic
gap. The card's row derives ``unverifiable`` from ``never_read`` before it
compares anything, and until 2026-08-24 that state offered no Apply button, so
the feature DEADLOCKED: no read -> grey -> no Apply -> no write -> no ack -> no
read. Found by Chris asking "where's apply?" of the live card, not by any test.

This is `f/audit_callsite_reachability` exactly: a correct function with zero
call sites passes every unit test, every gate and two full audits, because each
of them checks that the function is right rather than that anyone calls it.

TWO TRIGGERS, both deliberate (Chris, 2026-08-24):

  (a) ONCE AT STARTUP, deferred through ``async_at_started``. Deferral is not
      politeness — the read runs a ``send_command`` and scrapes the adapter's
      debug log, and at raw startup the vacuum entity may not exist yet. The
      discovery listener carries the same deferral for the same reason, and its
      comment records what skipping it cost.

  (b) ON EACH DOCK ARRIVAL, via the shared ``is_dock_trigger_edge``. Docked is
      when the device is idle and a read is cheapest, and it is the natural
      moment for "what order does the robot actually think it has" to be
      refreshed before the next run is planned.

WHY NOT POLL. Every read costs a command to the robot plus a log scrape. A timer
would spend that repeatedly to answer a question whose answer only changes when
the user edits the sequence in the vendor app or when we write it ourselves —
and we already refresh the cache in-process on our own write.

FAILS SOFT, ALWAYS. ``async_read`` caches ``unavailable`` on every failure path
and never raises; this listener additionally swallows, because a diagnostic read
must not be able to break a dock transition.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.start import async_at_started

from ..const import DOMAIN
from ._common import is_dock_trigger_edge

_LOGGER = logging.getLogger(__name__)

#: The state that means "back on the dock". Shaped as the tuple
#: ``is_dock_trigger_edge`` takes, so the edge test is shared rather than
#: re-spelled — a second copy of "is this a dock arrival" is how the two
#: definitions drift apart.
_DOCKED_TRIGGER = ("docked",)

#: Where this module parks its unsubscribes. Same shape and same lifecycle as
#: every sibling listener (`_job_progress_unsubs` and friends) — see `remove`.
_CLEAN_ORDER_UNSUBS = "_clean_order_refresh_unsubs"


def remove(hass: HomeAssistant) -> None:
    """Tear down both subscriptions.

    ⚠ NOT OPTIONAL, and the first cut of this file omitted it. Every listener in
    this package pairs `register` with a `remove` that `__init__.py` pushes onto
    the unwind stack; this one shipped without either, which is invisible on a
    cold start and compounds on every config-entry RELOAD: the previous
    subscription stays live, so N reloads make one dock arrival fire N reads, and
    each read is a real `send_command` to the robot plus a handler attach on the
    roborock logger. Found by diffing this module against its siblings, not by a
    test — the register half existed, so the module read as complete.
    """
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_CLEAN_ORDER_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover - teardown must never raise
            pass


def register(hass: HomeAssistant) -> None:
    """Wire the startup and dock-arrival clean-order reads."""

    def _capable_vacuums() -> list[str]:
        """Vacuums whose adapter declares a clean-order READ, or []."""
        runtime = (hass.data.get(DOMAIN) or {}).get("runtime")
        clean_order = getattr(runtime, "clean_order", None)
        if runtime is None or clean_order is None:
            return []
        return [
            vid
            for vid in list((runtime.data.get("vacuums") or {}).keys())
            if clean_order.is_supported(vid)
        ]

    async def _read(vacuum_entity_id: str, why: str) -> None:
        runtime = (hass.data.get(DOMAIN) or {}).get("runtime")
        clean_order = getattr(runtime, "clean_order", None)
        if clean_order is None:
            return
        try:
            entry = await clean_order.async_read(vacuum_entity_id)
        except Exception:  # pragma: no cover - a diagnostic read must never escape
            _LOGGER.exception(
                "clean_order: read failed for %s (%s)", vacuum_entity_id, why
            )
            return
        _LOGGER.debug(
            "clean_order: read %s (%s) -> status=%s order=%s",
            vacuum_entity_id, why,
            (entry or {}).get("status"), (entry or {}).get("order"),
        )

    @callback
    def _on_started(_now: Any) -> None:
        vids = _capable_vacuums()
        # INFO, not debug, and deliberately. `async_read` had no callers at all
        # until 2026-08-24 and nothing anywhere said so — the sensor simply sat at
        # `never_read` for the life of the feature. One line per startup naming how
        # many vacuums were found is what makes "the trigger never fired" and "the
        # trigger fired and the device said nothing" distinguishable in a log,
        # which is the exact pair that cost a release-day debug session.
        # INFO only when there is something to say. Every non-Roborock install has
        # zero capable vacuums, and an INFO line on every restart telling those users
        # nothing happened is noise in the log they actually read. Zero still logs, at
        # DEBUG, because "fired and found nothing" and "never fired at all" are the
        # pair that has to stay distinguishable — that ambiguity is what made this
        # feature's failure take a whole session to localise.
        _LOGGER.log(
            logging.INFO if vids else logging.DEBUG,
            "clean_order: startup read for %d capable vacuum(s): %s",
            len(vids), vids or "none",
        )
        for vid in vids:
            hass.async_create_task(_read(vid, "startup"))

    unsubs: list[Callable[[], None]] = [async_at_started(hass, _on_started)]

    @callback
    def _on_vacuum_state(event: Any) -> None:
        """Read again when a capable vacuum ARRIVES on the dock.

        Edge, not level: ``is_dock_trigger_edge`` compares old and new so a
        repeated ``docked`` state (an attribute-only update, a restart that comes
        back docked) does not re-fire. Without that this would issue a command
        every time any attribute of a docked vacuum changed.
        """
        vacuum_entity_id = event.data.get("entity_id")
        if not vacuum_entity_id or vacuum_entity_id not in _capable_vacuums():
            return
        # ⚠ `.state`, NOT the State object. `is_dock_trigger_edge` takes STRING
        # VALUES; handed a State it compares `<state vacuum.x=docked; ...>` against
        # the vocabulary, which can never match, so the trigger silently never
        # fires. It shipped that way and looked healthy from every angle — the
        # startup read populated the sensor, so the feature appeared to work.
        # Caught only by a POSITIVE CONTROL ([LR-6a]) asserting a dock arrival does
        # read; the teardown test alone passed against a listener that never fired.
        # dock_events.py has always taken `.state` here; this was the shorter copy.
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if is_dock_trigger_edge(
            old_state.state if old_state is not None else None,
            new_state.state if new_state is not None else None,
            _DOCKED_TRIGGER,
        ):
            hass.async_create_task(_read(vacuum_entity_id, "docked"))

    # Registered against every managed vacuum; the handler re-checks capability on
    # each event so a vacuum added later is covered without re-registering.
    vacuums = list(
        ((hass.data.get(DOMAIN) or {}).get("runtime").data.get("vacuums") or {}).keys()
    ) if (hass.data.get(DOMAIN) or {}).get("runtime") else []
    _LOGGER.debug(
        "clean_order: register() wired dock-arrival reads for %d vacuum(s): %s",
        len(vacuums), vacuums or "none",
    )
    if vacuums:
        unsubs.append(
            async_track_state_change_event(hass, vacuums, _on_vacuum_state)
        )
    hass.data.setdefault(DOMAIN, {})[_CLEAN_ORDER_UNSUBS] = unsubs
