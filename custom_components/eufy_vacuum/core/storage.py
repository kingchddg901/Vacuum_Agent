"""Storage helpers for Vacuum Agent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..adapters.eufy.const import STORAGE_KEY as STORAGE_KEY  # noqa: F401

STORAGE_VERSION = 1

# DRAFT-5: a burst of rapid successive draft edits (a card slider being dragged)
# used to trigger one full-integration-data disk write PER edit — async_save_delayed
# coalesces them into one write after this much quiet. Long enough to absorb a drag
# gesture, short enough that a crash mid-drag loses at most this much.
DRAFT_SAVE_DELAY_SECONDS = 2.0


class EufyVacuumStorage:
    """Manages persistent JSON storage for the integration via HA's Store helper."""

    def __init__(self, hass: HomeAssistant) -> None:
        # ENMKYC3F: this Store helper is the ONLY supported way our data reaches disk.
        # HA rewrites .storage from its own memory on shutdown, so a hand-edit is not
        # merged -- it is overwritten, and the file it cannot reconcile becomes a .corrupt
        # backup. If a value can only be changed by editing that file, the missing thing
        # is a service, not a licence to edit it.
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> dict[str, Any]:
        """Load stored data."""
        data = await self._store.async_load()
        if data is None:
            return {
                "vacuums": {},
                "maps": {},
                "theme": {
                    "library": {},
                    "default_theme_id": None,
                    "vacuums": {},
                },
                "analytics": {},
                "maintenance": {},
                "dock_events": {},
                "onboarding": {},
                # Per-vacuum error_tracker state:
                #   {<vacuum_entity_id>: {active_run_error, last_device_error, recent_errors}}
                # Loaded by ErrorTracker on start() and re-persisted on
                # rising/falling edges, harvest, and acknowledge.
                "error_tracker": {},
            }
        # Defensive backfill for installs that pre-date the error_tracker
        # section. ensure_record-style: only sets the key if missing.
        data.setdefault("error_tracker", {})
        return data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save stored data immediately."""
        await self._store.async_save(data)

    def async_save_delayed(
        self,
        data_func: Callable[[], dict[str, Any]],
        *,
        delay: float = DRAFT_SAVE_DELAY_SECONDS,
    ) -> None:
        """Schedule a coalesced write via HA's own Store.async_delay_save.

        DRAFT-5: a callback, not a coroutine (mirrors Store.async_delay_save's own
        signature) — rapid successive callers collapse into ONE write `delay` seconds
        after the last call, instead of one write per call. ``data_func`` is invoked
        at WRITE time, not now, so it must keep returning the current data (a bound
        method / closure over the live dict), never a snapshot captured at call time.
        """
        self._store.async_delay_save(data_func, delay)