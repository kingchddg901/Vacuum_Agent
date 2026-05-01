"""Select platform for Eufy Vacuum Manager — global icon selects for modes, suction, speed, and water."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


# category -> slot -> (options, default_index).  One HA entity is created per slot.
ICON_SELECTS: dict[str, dict[str, tuple[list[str], int]]] = {
    "mode": {
        "vacuum":  (["🧹", "扫", "💨", "吸"], 0),
        "mop":     (["🧴", "拖", "💧", "🫧"], 0),
        "vacmop":  (["🧹🧴", "扫拖", "🔄", "✨"], 0),
    },
    "suction": {
        "quiet":    (["🌀", "🔈", "💤", "🍃"], 0),
        "standard": (["🌀🌀", "🔉", "🌬️", "✅"], 0),
        "turbo":    (["🌀🌀🌀", "🔊", "🌪️", "🚀"], 0),
        "max":      (["🌀🌀🌀🌀", "📢", "💥", "🔥"], 0),
    },
    "speed": {
        "fast":     (["🐇", "🏃", "⚡", "⏩"], 0),
        "standard": (["🦔", "🚶", "🆗", "▶️"], 0),
        "deep":     (["🐢", "🕵️", "🔍", "⏬"], 0),
    },
    "water": {
        "low":    (["💧", "🌫️", "📉"], 0),
        "medium": (["💧💧", "🌊", "📊"], 0),
        "high":   (["💧💧💧", "⛲", "📈"], 0),
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    manager = hass.data[DOMAIN]["runtime"]
    entities: list[SelectEntity] = []

    for category, slots in ICON_SELECTS.items():
        for slot, (options, _default_index) in slots.items():
            entities.append(
                EufyVacuumIconSelect(
                    manager=manager,
                    category=category,
                    slot=slot,
                    options=options,
                )
            )

    async_add_entities(entities)


class EufyVacuumIconSelect(SelectEntity):
    """Global icon select — one per category/slot, shared across all vacuums.

    Stores the selected emoji/icon in integration storage so the value
    persists across restarts and is readable by the card as a standard
    HA select entity.
    """

    def __init__(
        self,
        *,
        manager: Any,
        category: str,
        slot: str,
        options: list[str],
    ) -> None:
        """Initialize icon select."""
        self._manager = manager
        self._category = category
        self._slot = slot
        self._attr_options = options

        label = f"Icon {category.title()} {slot.title()}"
        self._attr_name = label
        self._attr_unique_id = f"eufy_vacuum_icon_{category}_{slot}"
        self._attr_icon = "mdi:emoticon-outline"

    @property
    def current_option(self) -> str:
        """Return the currently selected icon, defaulting to the first option."""
        stored = self._manager.get_icon_value(
            category=self._category,
            slot=self._slot,
        )
        if stored and stored in self._attr_options:
            return stored
        return self._attr_options[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose category and slot so the card can identify this entity."""
        return {
            "category": self._category,
            "slot": self._slot,
        }

    async def async_select_option(self, option: str) -> None:
        """Persist the selected icon."""
        if option not in self._attr_options:
            raise ValueError(
                f"Invalid icon option '{option}' for {self._category}/{self._slot}"
            )
        self._manager.set_icon_value(
            category=self._category,
            slot=self._slot,
            value=option,
        )
        await self._manager.async_save()
