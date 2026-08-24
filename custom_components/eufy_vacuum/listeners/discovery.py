"""Auto-discovery triggers — keep room-drift history fresh.

Each managed vacuum's adapter declares which triggers apply (under
``discovery.auto_refresh_on``) and an optional periodic interval
(``discovery.auto_refresh_interval_seconds``). The framework owns the
trigger semantics; the adapter just opts in.

Triggers wired here:
  - ``vacuum_docked``        — vacuum entity transitions to "docked"
  - ``active_map_changed``   — active_map sensor value changes
  - ``config_entry_reload``  — one-shot pass, DEFERRED to HA-started
  - periodic safety net      — every N seconds, adapter-configurable

``config_entry_reload`` is not a pass "right now": ``register()`` wraps it
in ``async_at_started``, so at boot it waits until HA has finished starting
and only runs immediately when HA is already up (a live config-entry
reload mid-session). The rationale is stated at the site, in the
``config_entry_reload`` block of ``register()``: a service-response source
(Roborock ``get_maps``) may not be registered yet at raw setup time, so an
at-setup pass logs a spurious warning and falls back to the cached source.
⚠ was: "one-shot pass right now (setup time)" — which contradicted both the
code and that inline rationale, so someone debugging a stale room list just
after a boot-time setup would conclude the pass had already run, and anyone
"restoring" the documented behaviour would reintroduce the warning the
deferral exists to avoid.

Manual rescan via the ``discover_rooms`` service also updates drift history
(``SERVICE_DISCOVER_ROOMS = "discover_rooms"`` in const.py, declared in
services.yaml, handled by ``_handle_discover_rooms`` in services/rooms.py,
which runs the drift update itself) — the service path is always available
regardless of which auto triggers are declared.
⚠ was: "``setup_discover_rooms`` service … wired separately in services.py".
Neither exists: ``eufy_vacuum.setup_discover_rooms`` fails with "Action not
found", and the ``setup_`` prefix looks right only because
``setup_unreject_rooms`` really is a service. There is no services.py
either — ``services/`` is a package — so the pointer sent anyone verifying
the claim to a file that is not there.

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
#   INMKEHPQ  `rooms/room_manager.py#INMKEHPQ`
#       A6-GUARD-5 (closed RP-019): A discovery pass on the active map is scored against configured rooms across ALL
#              maps, so switching maps makes the other map's rooms accrue "removed" strikes


from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager
from ._common import is_dock_trigger_edge

#: The vacuum-state value the ``vacuum_docked`` trigger fires on. A frozenset
#: because that is the shape ``is_dock_trigger_edge`` takes; it compares
#: case-insensitively after stripping, so a brand reporting "Docked" also
#: matches (the old ``== "docked"`` did not).
_DOCKED_TRIGGER: frozenset[str] = frozenset({"docked"})

_LOGGER = logging.getLogger(__name__)

_DISCOVERY_UNSUBS = "_discovery_unsubs"


def remove(hass: HomeAssistant) -> None:
    """Tear down all auto-discovery triggers registered for the entry."""
    domain_data = hass.data.get(DOMAIN, {})
    by_vacuum: dict[str, list[Callable[[], None]]] = domain_data.pop(_DISCOVERY_UNSUBS, {})
    for unsubs in by_vacuum.values():
        for unsub in unsubs:
            try:
                unsub()
            except Exception:  # pragma: no cover
                pass


def remove_vacuum(hass: HomeAssistant, vacuum_entity_id: str) -> None:
    """Tear down ONE vacuum's auto-discovery triggers, leaving the others intact.

    RP-039/RF-16 (INT79PB7): the per-vacuum analogue of remove() — used when a single
    managed vacuum is removed (device deleted) so its state-change listeners stop
    firing against a now-nonexistent manager record immediately, instead of
    lingering (inertly) until the next reload/restart.
    """
    domain_data = hass.data.get(DOMAIN, {})
    by_vacuum: dict[str, list[Callable[[], None]]] = domain_data.get(_DISCOVERY_UNSUBS, {})
    for unsub in by_vacuum.pop(vacuum_entity_id, []):
        try:
            unsub()
        except Exception:  # pragma: no cover
            pass


def register(hass: HomeAssistant) -> None:
    """Wire auto-discovery triggers that keep room-drift history fresh."""
    remove(hass)

    # Local import keeps the listener module's import surface narrow at
    # module load time. The drift helpers transitively import a lot more
    # than the listener itself needs; deferring the import until first
    # registration keeps startup lean.
    from ..setup.drift import get_discovery_cadence, run_discovery_pass
    from ..rooms.source_refresh import async_refresh_room_source
    from homeassistant.helpers.start import async_at_started

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    # RP-039/RF-16: keyed per vacuum_entity_id (not a flat list) so remove_vacuum()
    # can tear down exactly one vacuum's triggers without disturbing the others.
    by_vacuum: dict[str, list[Callable[[], None]]] = {}

    for vacuum_entity_id in manager.get_known_vacuum_ids():
        unsubs: list[Callable[[], None]] = []
        cadence = get_discovery_cadence(vacuum_entity_id)
        triggers = set(cadence.get("auto_refresh_on") or [])
        interval_seconds = int(cadence.get("auto_refresh_interval_seconds") or 0)
        adapter_config = get_adapter_config(vacuum_entity_id) or {}
        active_map_entity = (adapter_config.get("entities") or {}).get("active_map")

        # Bind vacuum_entity_id at closure-creation time so per-vacuum
        # callbacks see their own ID rather than the loop variable.
        def _make_run_pass(vid: str) -> Callable[[], None]:
            def _run() -> None:
                async def _do() -> None:
                    try:
                        # Refresh service-response sources (Roborock get_maps)
                        # before the sync pass reads the cache; no-op for Eufy.
                        await async_refresh_room_source(hass, vid)
                        run_discovery_pass(hass, manager, vid)
                        await manager.async_save()
                    except Exception:  # pragma: no cover - best-effort background pass
                        _LOGGER.exception(
                            "discovery: failed for %s", vid
                        )
                hass.async_create_task(_do())
            return _run

        run_pass = _make_run_pass(vacuum_entity_id)

        # --- config_entry_reload: one-shot pass, deferred to HA-started ---
        # Run it once HA has fully started, not at raw setup time: a service-
        # response source (Roborock get_maps) may not be registered yet then
        # ("Action ... not found"), so an at-setup pass logs a spurious warning and
        # falls back to the cached source. async_at_started fires immediately when
        # HA is already running (a live config-entry reload), so the reload trigger
        # still refreshes promptly mid-session. _run binds this vacuum's run_pass
        # (the deferred callback would otherwise close over the loop's last one).
        if "config_entry_reload" in triggers:
            # @callback so async_at_started runs it ON the event loop (a plain
            # callable would be handed to the executor, and run_pass schedules a
            # task — hass.async_create_task is loop-only).
            unsubs.append(
                async_at_started(
                    hass, callback(lambda _hass, _run=run_pass: _run())
                )
            )

        # --- vacuum_docked: state transitions to "docked" ---
        if "vacuum_docked" in triggers:
            @callback
            def _on_vacuum_state(
                event: Event,
                _run_pass: Callable[[], None] = run_pass,
            ) -> None:
                new_state_obj = event.data.get("new_state")
                old_state_obj = event.data.get("old_state")
                new_state = getattr(new_state_obj, "state", None)
                old_state = getattr(old_state_obj, "state", None)
                # RP-038 (RF-30) / LIFE-3 (L11): delegate to the SHARED edge test.
                # This is the THIRD site asking "is this a genuine edge into a
                # trigger state"; dock_events.py and lifecycle.py already delegate,
                # and this one had written a shorter copy of the same predicate.
                #
                # ⚠ THE COMMENT HERE USED TO CLAIM THE STARTUP CASE WAS HANDLED. It
                # was `new_state == "docked" and old_state != "docked"`, above the
                # words "filter out ... unknown → docked startup noise". It does not:
                # "unknown" != "docked", so unknown→docked passes, and so do
                # unavailable→docked and None→docked (no prior state at all — the
                # first sighting after a restart). Only docked→docked was filtered.
                #
                # WHAT THAT COST, and it is not cosmetic. Every HA restart where the
                # vacuum comes back docked fired a full discovery pass at RAW STARTUP
                # — the exact timing the `config_entry_reload` trigger above is
                # deferred through `async_at_started` to avoid, for the reason its own
                # comment gives (a service-response source may not be registered yet).
                # For a service_response brand (Roborock: `roborock.get_maps`) the
                # flattened cache lives in `hass.data` and is therefore EMPTY on
                # restart, so the pass discovers NO rooms.
                #
                # ⚠ THE REST OF THIS NOTE USED TO READ "and `update_drift_history` has
                # no empty-read guard, so it increments `missing_passes` for EVERY
                # configured room ... at `removal_confirmation_passes` every room is
                # flagged removed". That WAS true, and describing the damage was never
                # a ruling to accept it. C58 (Chris, 2026-08-24) closed it at the
                # scoring end: `setup/drift.py#update_drift_history` now returns on an
                # empty `discovered_room_ids`, warns that the pass was UNREADABLE, and
                # leaves every stored counter untouched — neither struck nor reset. A
                # pass fired at raw startup can no longer cost a room a strike.
                #
                # THAT DID NOT MAKE THIS TRIGGER CORRECT, which is why the edge test
                # below stays. Guarding the scorer classifies the bad pass; it does not
                # stop this listener firing one at the exact moment the reload trigger
                # is deferred to avoid, and each such pass now costs a warning in the
                # log for a read nobody asked for. An unreadable source and an empty
                # source are still not the same fact — this path simply no longer gets
                # to spend a user's rooms on the difference.
                #
                # NOTHING LOSES A STARTUP PASS BY THIS. Both shipped brands declare
                # `config_entry_reload` alongside `vacuum_docked`, and so does the
                # framework default trigger tuple, so the one-shot start pass is
                # already provided — correctly deferred. This removes a DUPLICATE that
                # ran at the wrong moment, not the coverage.
                if is_dock_trigger_edge(old_state, new_state, _DOCKED_TRIGGER):
                    _run_pass()

            unsubs.append(
                async_track_state_change_event(
                    hass, [vacuum_entity_id], _on_vacuum_state
                )
            )

        # --- active_map_changed: active_map sensor value changes ---
        if "active_map_changed" in triggers and active_map_entity:
            @callback
            def _on_active_map(
                event: Event,
                _run_pass: Callable[[], None] = run_pass,
            ) -> None:
                new_state_obj = event.data.get("new_state")
                old_state_obj = event.data.get("old_state")
                new_value = getattr(new_state_obj, "state", None)
                old_value = getattr(old_state_obj, "state", None)
                # L11-SIBLING: the SAME defect as the vacuum_docked trigger above, one
                # guard short. This tested the NEW value against the sentinels and left
                # the OLD one unguarded — so `None -> "6"` and `unknown -> "6"` both
                # counted as "the active map CHANGED", and both are what a restart
                # looks like: the entity is created fresh, so its first real reading is
                # an edge from nothing.
                #
                # Found only because L11 sent me to look at the sibling — the same way
                # C16's hang turned up its own sibling in `trail_window_seconds`. The
                # existing test `[LS-11]` asserts the new-value half and reads as
                # covering this; it never supplied a sentinel OLD value.
                #
                # An arrival is not a change. Guarding both ends means a genuine map
                # switch still fires, and a restart no longer runs a discovery pass at
                # raw startup on top of the one the reload trigger already schedules.
                if (
                    new_value not in (None, "unknown", "unavailable")
                    and old_value not in (None, "unknown", "unavailable")
                    and new_value != old_value
                ):
                    _run_pass()

            unsubs.append(
                async_track_state_change_event(
                    hass, [active_map_entity], _on_active_map
                )
            )

        # --- periodic safety net ---
        if interval_seconds > 0:
            @callback
            def _on_tick(
                _now,
                _run_pass: Callable[[], None] = run_pass,
            ) -> None:
                _run_pass()

            unsubs.append(
                async_track_time_interval(
                    hass, _on_tick, timedelta(seconds=interval_seconds)
                )
            )

        by_vacuum[vacuum_entity_id] = unsubs

    domain_data[_DISCOVERY_UNSUBS] = by_vacuum
    _LOGGER.debug(
        "discovery: registered %d auto-discovery trigger(s) across %d vacuum(s)",
        sum(len(v) for v in by_vacuum.values()),
        len(manager.get_known_vacuum_ids()),
    )
