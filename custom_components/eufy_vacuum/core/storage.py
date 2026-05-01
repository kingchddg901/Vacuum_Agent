"""Storage helpers for Eufy Vacuum Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"


class EufyVacuumStorage:
    """Manages persistent JSON storage for the integration via HA's Store helper."""

    def __init__(self, hass: HomeAssistant) -> None:
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
                "icons": {},
                "onboarding": {},
            }
        return data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save stored data."""
        await self._store.async_save(data)