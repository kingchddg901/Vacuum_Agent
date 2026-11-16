"""Theme state sensor — active theme + draft state.

State = active theme name (or 'none'). Attributes expose everything the
card needs to drive the theme browser and draft editor without
service calls just to read state.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from ..entity_helpers import build_vacuum_device_info

# Kept OUT OF THE RECORDER. `card_theme` is the active theme's raw token/colour/alpha
# triplet -- ~8 KB on a real theme -- and this entity's state changes on every keystroke
# of a live theme edit (`working_draft` is an attribute too). Recording 8 KB per draft
# nudge would dwarf the value of the history, and nobody plots a palette. Precedent:
# sensor/map_overlays.py does the same for its layer arrays.
#
# ONLY THE NEW KEY IS LISTED. `working_draft` and `library_summary` are bulky too, but
# they are recorded TODAY and silently dropping them from history is a behaviour change
# for existing installs that is not this change's to make.
_UNRECORDED = frozenset({"card_theme"})


class EufyVacuumThemeStateSensor(SensorEntity):
    """Exposes the active theme name and draft state for one vacuum.

    State   = active theme name, or 'none' if no theme is selected.
    Attributes expose everything the card needs to drive the theme browser
    and draft editor without needing to call a service just to read state.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "theme_state"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:palette"
    _unrecorded_attributes = _UNRECORDED

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
    ) -> None:
        """Initialize theme state sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id

        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_theme_state"
        )
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)

    def _get_vac_theme(self) -> dict[str, Any]:
        """Return per-vacuum theme state safely."""
        theme = self._manager.data.get("theme", {})
        return theme.get("vacuums", {}).get(
            self._vacuum_entity_id,
            {
                "active_theme_id": None,
                "working_draft": {"tokens": {}, "colors": {}, "alpha": {}},
                "draft_dirty": False,
                "editor_mode": "live",
            },
        )

    def _get_theme_library(self) -> dict[str, Any]:
        """Return the global theme library."""
        return self._manager.data.get("theme", {}).get("library", {})

    @property
    def native_value(self) -> str:
        """Return active theme name, or 'none'."""
        vac = self._get_vac_theme()
        active_id = vac.get("active_theme_id")
        if not active_id:
            return "none"
        library = self._get_theme_library()
        entry = library.get(active_id)
        if entry is None:
            return "none"
        # SN-10b: .get's default only fires on an ABSENT key -- a stored
        # {"name": None} entry would render the literal string "None".
        return str(entry.get("name") or "none")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full theme state for card consumption."""
        vac = self._get_vac_theme()
        library = self._get_theme_library()
        theme_root = self._manager.data.get("theme", {})

        library_summary = [
            {"id": tid, "theme_id": tid, "name": t.get("name", "")}
            for tid, t in library.items()
        ]

        # ISSUE #83 / card theming — the RAW active theme, for a dashboard card that has
        # been told to follow the VA theme.
        #
        # RAW, NOT RESOLVED, and that is the whole design decision. Resolution is a
        # four-layer merge that lives in the FRONTEND (`state.resolvedTheme()`); the card
        # already carries the two default layers (the room-fill palette and
        # FLOOR_TEXTURE_REGISTRY), because it already renders materials from them. Serving
        # a resolved set from here would mean porting that merge to Python — a replica of
        # exactly the kind this tree keeps paying for — to save roughly 900 bytes. The card
        # imports the SAME resolver the panel uses instead.
        #
        # UNPRUNED, deliberately. Pruning the floor tokens to materials actually in use
        # saves ~3 KB, but every way of doing it needs a SECOND replica: `resolveFloorType`
        # to map a stored floor_type onto a token segment, or the built-in material list,
        # or a catalogue read inside a property. Measured on a real theme: 8,019 B whole,
        # 4,712 B of it non-floor and unprunable anyway. `_UNRECORDED` above removes the
        # cost that actually mattered, which was the recorder, not the 3 KB.
        #
        # Taken WHOLE from the library entry rather than rebuilt field by field, so a new
        # key in a stored theme reaches the card without a fourth dict learning about it.
        active = library.get(vac.get("active_theme_id") or "") or {}
        card_theme = {
            "theme_id": vac.get("active_theme_id"),
            "tokens": active.get("tokens") or {},
            "colors": active.get("colors") or {},
            "alpha": active.get("alpha") or {},
        }

        return {
            "active_theme_id": vac.get("active_theme_id"),
            "card_theme": card_theme,
            "draft_dirty": bool(vac.get("draft_dirty", False)),
            "editor_mode": vac.get("editor_mode", "live"),
            "working_draft": vac.get("working_draft", {"tokens": {}, "colors": {}, "alpha": {}}),
            "library_count": len(library),
            "library_summary": library_summary,
            "default_theme_id": theme_root.get("default_theme_id"),
            "vacuum_entity_id": self._vacuum_entity_id,
        }
