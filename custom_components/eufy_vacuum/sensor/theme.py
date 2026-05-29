"""Theme state sensor — active theme + draft state.

State = active theme name (or 'none'). Attributes expose everything the
card needs to drive the theme browser and draft editor without
service calls just to read state.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..entity_helpers import build_entity_name


class EufyVacuumThemeStateSensor(SensorEntity):
    """Exposes the active theme name and draft state for one vacuum.

    State   = active theme name, or 'none' if no theme is selected.
    Attributes expose everything the card needs to drive the theme browser
    and draft editor without needing to call a service just to read state.
    """

    _attr_should_poll = False

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
    ) -> None:
        """Initialize theme state sensor."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id

        self._attr_name = build_entity_name(vacuum_entity_id, "Theme State")
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_theme_state"
        )
        self._attr_icon = "mdi:palette"

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
        return str(entry.get("name", "none"))

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

        return {
            "active_theme_id": vac.get("active_theme_id"),
            "draft_dirty": bool(vac.get("draft_dirty", False)),
            "editor_mode": vac.get("editor_mode", "live"),
            "working_draft": vac.get("working_draft", {"tokens": {}, "colors": {}, "alpha": {}}),
            "library_count": len(library),
            "library_summary": library_summary,
            "default_theme_id": theme_root.get("default_theme_id"),
            "vacuum_entity_id": self._vacuum_entity_id,
        }
