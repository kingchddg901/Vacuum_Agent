"""
Setup status evaluation for the eufy_vacuum framework.

The panel calls ``get_setup_status(hass)`` on load to decide which view to
render. The state machine is now data-driven by each adapter's
``setup.steps`` declaration — the framework iterates whatever steps the
adapter requires rather than baking Eufy-specific assumptions ("map must
be imported") into the status logic.

Response shape (new fields surfaced; legacy fields kept for backward
compatibility with the current card while it is refactored):

    {
        # NEW data-driven fields
        "setup_complete": bool,
        "vacuums": [
            {
                "vacuum_entity_id": str,
                "display_name":     str,
                "setup_steps": [
                    {
                        "id":        str,    # step ID from drift.SETUP_STEP_IDS
                        "label":     str,
                        "completed": bool,
                        "service":   str,    # "eufy_vacuum.<service_name>"
                    },
                    ...
                ],
                "next_step": str | None,     # first incomplete step, None when all done
                "room_drift": {
                    "in_sync":             bool,
                    "new_rooms":           [{room_id, name, map_id}, ...],
                    "removed_rooms":       [{room_id, name, map_id}, ...],
                    "transiently_missing": [{room_id, name, map_id}, ...],
                    "rejected_rooms":      [room_id, ...],
                },
                "maps": [ ... ],             # same as before, when relevant
                # LEGACY (backward-compat for current card; will be removed):
                "has_imported_map": bool,
            }
        ],

        # LEGACY (backward-compat; will be removed):
        "state":        "no_vacuums" | "no_map" | "ready",
        "next_actions": list[str],
    }
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import DATA_RUNTIME, DOMAIN
from ..panels import effective_panel_title
from .drift import (
    SETUP_STEP_LABELS,
    SETUP_STEP_SERVICES,
    compute_room_drift,
    get_adapter_setup_steps,
    is_step_completed,
)
from .protection import evaluate_map_protection


def _build_setup_steps_for_vacuum(
    manager: Any, vacuum_entity_id: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Build the per-vacuum setup_steps list and identify the next step.

    Returns (steps_list, next_step_id).
    """
    declared = get_adapter_setup_steps(vacuum_entity_id)
    progress = manager.data.get("setup_progress", {}).get(vacuum_entity_id, {})

    steps_out: list[dict[str, Any]] = []
    next_step: str | None = None
    for step_id in declared:
        completed = is_step_completed(progress, step_id)
        steps_out.append({
            "id": step_id,
            "label": SETUP_STEP_LABELS.get(step_id, step_id),
            "completed": completed,
            "service": f"{DOMAIN}.{SETUP_STEP_SERVICES.get(step_id, step_id)}",
        })
        if next_step is None and not completed:
            next_step = step_id

    return steps_out, next_step


def _build_maps_list(
    manager: Any, vacuum_entity_id: str
) -> tuple[list[dict[str, Any]], bool]:
    """Build the maps list for one vacuum and return (maps, has_imported_map).

    has_imported_map is preserved for legacy callers; new code should
    rely on `next_step is None` and `room_drift.in_sync` instead.
    """
    vacuum_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    maps_out: list[dict[str, Any]] = []
    has_imported_map = False

    for map_id, bucket in vacuum_maps.items():
        if not isinstance(bucket, dict):
            continue
        rooms = bucket.get("rooms", {}) or {}
        imported = bool(rooms)
        if imported:
            has_imported_map = True

        display_name = (
            bucket.get("metadata", {}).get("display_name")
            or f"Map {map_id}"
        )

        protection = (
            evaluate_map_protection(
                manager,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            if imported
            else None
        )

        maps_out.append({
            "map_id": str(map_id),
            "display_name": display_name,
            "room_count": len(rooms),
            "imported": imported,
            "protection": protection,
        })

    return maps_out, has_imported_map


def get_setup_status(hass: HomeAssistant) -> dict[str, Any]:
    """Return the current setup state for panel rendering.

    See module docstring for the response shape.

    Both the new data-driven fields (`setup_steps`, `next_step`,
    `room_drift`) and the legacy fields (`state`, `next_actions`,
    `has_imported_map`) are populated. The card refactor will eventually
    drop the legacy fields.
    """
    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        return {
            "setup_complete": False,
            "vacuums": [],
            # Legacy:
            "state": "no_vacuums",
            "next_actions": ["add_vacuum"],
        }

    managed = manager.get_managed_vacuums().get("vacuums", [])
    vacuums_out: list[dict[str, Any]] = []
    all_steps_complete = True
    all_in_sync = True

    for vac in managed:
        vacuum_entity_id = vac["vacuum_entity_id"]
        steps, next_step = _build_setup_steps_for_vacuum(
            manager, vacuum_entity_id
        )
        maps_out, has_imported_map = _build_maps_list(
            manager, vacuum_entity_id
        )

        # Drift is computed without a live discovery probe — the response
        # reflects the latest stored history. Discovery passes run via
        # auto-triggers (see setup/drift.py and stage-2 listener wiring)
        # and update history out-of-band.
        drift = compute_room_drift(manager, vacuum_entity_id)

        if next_step is not None:
            all_steps_complete = False
        if not drift["in_sync"]:
            all_in_sync = False

        object_id = vacuum_entity_id.split(".", 1)[-1]
        vacuums_out.append({
            "vacuum_entity_id": vacuum_entity_id,
            "display_name": object_id.replace("_", " ").title(),
            # Current sidebar panel title (user-set, or the "Vacuum Agent" default)
            # so the Setup tab's rename field can pre-fill the live value.
            "panel_title": effective_panel_title(
                manager.data.get("vacuums", {}).get(vacuum_entity_id, {})
            ),
            # The user's explicit live-map image/camera entity override (or None to use
            # the adapter pattern) so the Setup-tab camera picker can pre-select it.
            "live_map_image_entity": manager.data.get("vacuums", {})
            .get(vacuum_entity_id, {})
            .get("live_map_image_entity"),
            "setup_steps": steps,
            "next_step": next_step,
            "room_drift": drift,
            "maps": maps_out,
            # Legacy field — current card consumers.
            "has_imported_map": has_imported_map,
        })

    setup_complete = bool(managed) and all_steps_complete and all_in_sync

    # Legacy state derivation — preserve the three-state enum so the
    # current card keeps working until it's refactored.
    if not vacuums_out:
        legacy_state = "no_vacuums"
        legacy_next_actions = ["add_vacuum"]
    elif not any(v["has_imported_map"] for v in vacuums_out):
        legacy_state = "no_map"
        legacy_next_actions = ["import_active_map"]
    else:
        legacy_state = "ready"
        legacy_next_actions = []

    return {
        "setup_complete": setup_complete,
        "vacuums": vacuums_out,
        # Legacy backward-compat fields:
        "state": legacy_state,
        "next_actions": legacy_next_actions,
    }
