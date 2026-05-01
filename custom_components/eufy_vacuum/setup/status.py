"""Setup status evaluation for Eufy Vacuum Manager.

The panel calls ``get_setup_status(hass)`` on load to decide which view to
render.  Three states drive panel behaviour:

    "no_vacuums"  — nothing configured yet → show Add Vacuum
    "no_map"      — vacuum(s) exist but no map imported → show Import Map
    "ready"       — at least one vacuum has an imported map → show dashboard

The result is always a plain dict — no exceptions, no side-effects.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import DATA_RUNTIME, DOMAIN
from .protection import evaluate_map_protection


def get_setup_status(hass: HomeAssistant) -> dict[str, Any]:
    """Return the current setup state for panel rendering.

    Returns a ``SetupStatus`` dict:
    {
        "setup_complete": bool,
        "state":          "no_vacuums" | "no_map" | "ready",
        "vacuums": [
            {
                "vacuum_entity_id": str,
                "display_name":     str,
                "maps": [
                    {
                        "map_id":      str,
                        "display_name": str,
                        "room_count":  int,
                        "imported":    bool,
                    }
                ],
                "has_imported_map": bool,
            }
        ],
        "next_actions": list[str],
    }
    """
    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        return {
            "setup_complete": False,
            "state": "no_vacuums",
            "vacuums": [],
            "next_actions": ["add_vacuum"],
        }

    managed = manager.get_managed_vacuums().get("vacuums", [])
    vacuums_out: list[dict[str, Any]] = []
    any_ready = False

    for vac in managed:
        vacuum_entity_id = vac["vacuum_entity_id"]
        vacuum_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {})

        maps_out: list[dict[str, Any]] = []
        has_imported_map = False

        for map_id, bucket in vacuum_maps.items():
            rooms = bucket.get("rooms", {})
            imported = bool(rooms)
            if imported:
                has_imported_map = True

            # Fall back to "Map {id}" when no display name is stored so the
            # panel always has a label to render.
            display_name = (
                bucket.get("metadata", {}).get("display_name")
                or f"Map {map_id}"
            )

            protection = evaluate_map_protection(
                manager,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            ) if imported else None

            maps_out.append({
                "map_id": str(map_id),
                "display_name": display_name,
                "room_count": len(rooms),
                "imported": imported,
                "protection": protection,
            })

        if has_imported_map:
            any_ready = True

        object_id = vacuum_entity_id.split(".", 1)[-1]
        vacuums_out.append({
            "vacuum_entity_id": vacuum_entity_id,
            "display_name": object_id.replace("_", " ").title(),
            "maps": maps_out,
            "has_imported_map": has_imported_map,
        })

    if not vacuums_out:
        state = "no_vacuums"
        next_actions = ["add_vacuum"]
    elif not any_ready:
        state = "no_map"
        next_actions = ["import_active_map"]
    else:
        state = "ready"
        next_actions = []

    return {
        "setup_complete": state == "ready",
        "state": state,
        "vacuums": vacuums_out,
        "next_actions": next_actions,
    }
