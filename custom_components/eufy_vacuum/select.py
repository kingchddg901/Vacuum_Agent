"""Select platform for Vacuum Agent — the debug flight-recorder target.

Just the one integration-level diagnostic select; the entity class itself lives in the
reusable ``debug_capture`` helper.
"""

from __future__ import annotations

# Integration-level diagnostic select; no device polling.
PARALLEL_UPDATES = 0

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .debug_capture import build_debug_target_select


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the debug-target select."""
    async_add_entities([build_debug_target_select(hass, domain=DOMAIN)])
