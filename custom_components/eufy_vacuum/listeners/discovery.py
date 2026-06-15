"""Auto-discovery triggers — keep room-drift history fresh.

Each managed vacuum's adapter declares which triggers apply (under
``discovery.auto_refresh_on``) and an optional periodic interval
(``discovery.auto_refresh_interval_seconds``). The framework owns the
trigger semantics; the adapter just opts in.

Triggers wired here:
  - ``vacuum_docked``        — vacuum entity transitions to "docked"
  - ``active_map_changed``   — active_map sensor value changes
  - ``config_entry_reload``  — one-shot pass right now (setup time)
  - periodic safety net      — every N seconds, adapter-configurable

Manual rescan via ``setup_discover_rooms`` service also updates drift
history (wired separately in services.py — the service path is always
available regardless of which auto triggers are declared).

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

_DISCOVERY_UNSUBS = "_discovery_unsubs"


def remove(hass: HomeAssistant) -> None:
    """Tear down all auto-discovery triggers registered for the entry."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_DISCOVERY_UNSUBS, [])
    for unsub in unsubs:
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

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    unsubs: list[Callable[[], None]] = []

    for vacuum_entity_id in manager.get_known_vacuum_ids():
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

        # --- config_entry_reload: one-shot pass right now ---
        if "config_entry_reload" in triggers:
            run_pass()

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
                # Only fire on transition INTO docked — filter out
                # repeat docked-to-docked attribute updates and unknown
                # → docked startup noise.
                if new_state == "docked" and old_state != "docked":
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
                if (
                    new_value not in (None, "unknown", "unavailable")
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

    domain_data[_DISCOVERY_UNSUBS] = unsubs
    _LOGGER.debug(
        "discovery: registered %d auto-discovery trigger(s) across %d vacuum(s)",
        len(unsubs),
        len(manager.get_known_vacuum_ids()),
    )
