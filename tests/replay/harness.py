"""Replay driver — fire a recorder-save bundle through the live state machine.

The production listeners subscribe via async_track_state_change_event, so
``hass.states.async_set`` IS the public seam: every event a real HA install
would have fired for this run fires here, in recorded order, at recorded
(frozen) time. Production code runs unmodified; the only fakery is the clock.

Time model: before each event the freezer jumps to the event's timestamp and
async_fire_time_changed fires, so time-scheduled callbacks (pollers, reapers,
debounces) get their shot exactly as wall-clock would have given them between
these two signals. Deterministic by construction — sequences and gaps replay,
await-interleavings do not; this is never race evidence (audit-2 charter
delta 6/7 limits).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed


def _t(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def apply_initial(
    hass: HomeAssistant,
    bundle: dict,
    supplement: dict[str, str] | None = None,
    *,
    skip: set[str] | None = None,
) -> None:
    """Set the pre-window state of every known UPSTREAM entity.

    ``skip`` must hold the integration's OWN entity ids (ask the entity registry
    after setup): a recorder export captures our outputs alongside the upstream
    stimulus, and replaying our own outputs both collides with the live-created
    entities and feeds the system its recorded conclusions as inputs. Replay is
    stimulus-only; the live integration re-derives its own outputs.

    ``supplement`` adds static context the CSV export could not carry (entities
    that never changed in the export window) — explicit per-test assumptions.
    """
    skip = skip or set()
    for entity_id, state in {**bundle.get("initial", {}), **(supplement or {})}.items():
        if entity_id not in skip:
            hass.states.async_set(entity_id, state)


async def replay(
    hass: HomeAssistant,
    bundle: dict,
    freezer,
    *,
    skip: set[str] | None = None,
    settle_s: int = 0,
    on_event: Callable[[int, str, str, str], Awaitable[None] | Any] | None = None,
) -> int:
    """Replay the bundle's events in order under frozen time; return count fired.

    ``skip``: the integration's own entity ids — replay is stimulus-only (see
    apply_initial). ``on_event(index, t_iso, entity_id, state)`` runs after each
    fired event settles — the probe hook for tests that need mid-run state (a
    live queue snapshot, an external-capture slot appearing, a route census tick).
    """
    skip = skip or set()
    fired = 0
    when = None
    for i, (t_iso, entity_id, state) in enumerate(sorted(bundle.get("events", []))):
        if entity_id in skip:
            continue
        when = _t(t_iso)
        freezer.move_to(when)
        async_fire_time_changed(hass, when)
        hass.states.async_set(entity_id, state)
        await hass.async_block_till_done()
        fired += 1
        if on_event is not None:
            result = on_event(i, t_iso, entity_id, state)
            if hasattr(result, "__await__"):
                await result

    # Settle phase: the recorded stream ends, but delayed work scheduled off its
    # tail (the external-run finalize grace, reapers, debounces) still needs the
    # clock to reach it. Step — don't jump — so re-arming callbacks (a grace
    # recheck scheduling another grace recheck) get every intermediate firing.
    if settle_s and when is not None:
        from datetime import timedelta

        step = timedelta(seconds=30)
        end = when + timedelta(seconds=settle_s)
        while when < end:
            when = min(when + step, end)
            freezer.move_to(when)
            async_fire_time_changed(hass, when)
            await hass.async_block_till_done()
    return fired
