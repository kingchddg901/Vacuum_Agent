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
                "reconciliation": {          # CARD-7/RP-019 — last-cached identity-shift
                    "reviews":      [ ... ], # review dicts (rooms/reconciliation.py); see
                                             # its docstring for the id_changed / renamed /
                                             # renamed_and_renumbered shapes
                    "has_changes":  bool,
                    "plan_token":   str,     # opaque; round-trip to reconcile_room, never parse
                    "map_id":       str,     # the vacuum's active map this review was cached for
                    "dismissed":    bool,    # optional, present only when a dismissal suppressed it
                } | None,                    # None when no discovery has ever cached one
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
from ..rooms.room_discovery import get_active_map_id
from .drift import (
    SETUP_STEP_LABELS,
    SETUP_STEP_SERVICES,
    active_map_configured,
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
        # save_rooms completion is sticky, but it must reflect the ACTIVE map: a factory
        # reset / switch to a fresh map id can leave the flag set against a now-dead map
        # while the active map has no configured rooms. Re-open when we can confirm the
        # active map is unconfigured (None = can't determine -> leave the sticky flag).
        if (
            completed
            and step_id == "save_rooms"
            and active_map_configured(manager, vacuum_entity_id) is False
        ):
            completed = False
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

        # Emit the raw stored name, or None when unnamed — the CARD owns the
        # localized "Map {id}" fallback (setup.map_n -> "Карта {id}"). Fabricating
        # an English "Map N" here would pre-empt that path and leak English in
        # every locale. map_id is emitted alongside (below) for the card to use.
        display_name = bucket.get("metadata", {}).get("display_name") or None

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


def _build_reconciliation_for_vacuum(
    manager: Any, vacuum_entity_id: str
) -> dict[str, Any] | None:
    """Return the LAST-CACHED identity-shift reconciliation for one vacuum, or None.

    Passive read only (CARD-7/RP-019 gap 2) — mirrors compute_room_drift's own
    contract just above: this NEVER calls ``RoomMapManager.discover_rooms`` and
    never recomputes ``compute_reconciliation`` itself. It reads whatever
    ``RoomMapManager.discover_rooms`` (rooms/room_crud.py) already cached at
    ``manager.data["discovery"][vacuum_entity_id][map_id]["reconciliation"]`` the
    last time discovery actually ran for that map — same "as of the last pass"
    contract room_drift already has. Opening or polling Setup must never itself
    trigger a new discovery pass.

    ``map_id`` is resolved with ``get_active_map_id`` — the SAME resolution
    ``discover_rooms_payload`` uses to pick the cache key it writes
    (``rooms/room_discovery.py``), so this reads the exact bucket the vacuum's
    current active map would have written. The returned dict is the cached
    ``reconciliation`` payload (``reviews``, ``has_changes``, ``plan_token``,
    optionally ``dismissed``) with ``map_id`` stamped onto it — the card needs
    that id to send back on ``reconcile_room`` (its schema requires ``map_id``)
    and the cached payload itself doesn't carry it (it's the dict's own outer key).
    """
    active_map_id = get_active_map_id(manager.hass, vacuum_entity_id)
    if not active_map_id:
        return None

    cached = (
        manager.data.get("discovery", {})
        .get(vacuum_entity_id, {})
        .get(str(active_map_id))
    )
    if not isinstance(cached, dict):
        return None

    reconciliation = cached.get("reconciliation")
    if not isinstance(reconciliation, dict):
        return None

    return {**reconciliation, "map_id": str(active_map_id)}


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
        #
        # Scoped to the ACTIVE map (A4-SETUP-6). The drift history it reads is
        # written by passes against whichever map was loaded, and rejections are
        # per map — so leaving the map unset here would filter new_rooms by the
        # UNION of every map's rejections, and a room rejected downstairs would
        # never be offered upstairs. That is the same defect on the read side,
        # where it is harder to see: the room is simply absent from the panel.
        _drift_map_id = None
        _resolver = getattr(manager, "resolve_active_map_id", None)
        if callable(_resolver):
            _resolved = _resolver(vacuum_entity_id)
            _drift_map_id = str(_resolved) if _resolved else None
        drift = compute_room_drift(manager, vacuum_entity_id, map_id=_drift_map_id)

        # Identity-shift reconciliation reviews (CARD-7/RP-019): same passive,
        # last-cached-pass contract as drift immediately above — see
        # _build_reconciliation_for_vacuum's docstring.
        reconciliation = _build_reconciliation_for_vacuum(manager, vacuum_entity_id)

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
            "reconciliation": reconciliation,
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
