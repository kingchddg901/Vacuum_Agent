"""Protected map-delete workflow for the Eufy Vacuum setup layer.

Deletes are integration-only and never touch upstream Eufy cloud data.
Protection level (normal / elevated / high) is evaluated before any removal;
high-protection maps require a typed confirmation token matching the map name.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..const import DATA_RUNTIME, DOMAIN
from ..entity_helpers import unique_ids_for_map
from .protection import evaluate_map_protection

_LOGGER = logging.getLogger(__name__)


def _action_result(
    status: str,
    *,
    code: str = "",
    message: str = "",
    warnings: list[str] | None = None,
    data: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Build a canonical ActionResult dict for delete operations."""
    return {
        "status": status,
        "code": code,
        "message": message,
        "warnings": warnings or [],
        "data": data or {},
        "next_actions": next_actions or [],
    }


async def delete_map(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    """Delete one imported map and all related integration data.

    Evaluates protection level before acting. High-protection maps require
    ``confirmation_token`` to match the map display name exactly.
    Returns an ActionResult dict.
    """
    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        return _action_result(
            "error",
            code="manager_unavailable",
            message="Integration manager is not loaded.",
        )

    map_id_str = str(map_id)

    vacuum_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {})
    bucket = vacuum_maps.get(map_id_str)
    if bucket is None or not bucket.get("rooms"):
        return _action_result(
            "already_done",
            code="map_not_found",
            message=f"Map {map_id_str} has no imported data for {vacuum_entity_id}.",
        )

    protection = evaluate_map_protection(
        manager,
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id_str,
    )
    level = protection["protection_level"]
    typed_value = protection["typed_confirmation_value"]
    # Safe human label for messages/logs — typed_value is None for unnamed maps.
    display_label = typed_value or f"Map {map_id_str}"

    if protection["requires_typed_confirmation"]:
        if not confirmation_token:
            return _action_result(
                "requires_confirmation",
                code="typed_confirmation_required",
                message=(
                    f"Deleting '{display_label}' requires typed confirmation. "
                    f"Send the map name as confirmation_token."
                ),
                data={"protection": protection},
            )
        # typed_value is non-None whenever requires_typed_confirmation is True.
        if confirmation_token.strip() != (typed_value or "").strip():
            return _action_result(
                "blocked",
                code="confirmation_mismatch",
                message=(
                    f"Confirmation token does not match map name '{display_label}'. "
                    "Check for extra spaces or typos."
                ),
                data={"protection": protection},
            )
    elif protection.get("requires_confirmation") and not confirmation_token:
        # One-click confirm (any truthy token) for elevated maps AND unnamed
        # high-protection maps — which have no locale-invariant name to type.
        return _action_result(
            "requires_confirmation",
            code="confirmation_required",
            message=f"Confirm deletion of '{display_label}'.",
            data={"protection": protection},
        )

    _LOGGER.info(
        "Deleting map %s for %s (protection=%s)",
        map_id_str, vacuum_entity_id, level,
    )
    # RP-009 step 4 (REVIEW D3): capture the room ids BEFORE remove_map — the
    # closed-set sweep below reconstructs unique_ids from the stored rooms of
    # the map being deleted, and after remove_map they are gone.
    _deleted_room_ids = [
        rid for rid in (bucket.get("rooms") or {}).keys()
    ]
    removed = manager.remove_map(
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id_str,
    )

    manager._notify_rooms_updated(  # noqa: SLF001
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id_str,
    )
    manager._notify_run_profiles_updated(  # noqa: SLF001
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id_str,
    )

    # RP-009 step 4 (REVIEW D3): sweep the registry by the CLOSED SET of ids
    # forward-reconstructed from this map's stored rooms — never by string
    # prefix. The prefix scan was PROVEN (DR-SETUP-1) to delete every entity of
    # a sibling vacuum whose entity_id was the prefix plus a suffix: deleting
    # map "2" of vacuum.alfred swept ALL of vacuum.alfred_2's entities.
    #
    # Entries the old prefix scan would have matched but the closed set does
    # not — pre-fix orphans from rooms removed before this repair, or older id
    # schemes — are ENUMERATED AND REPORTED, never deleted: what cannot be
    # re-derived must not be destroyed (GATE4 Q15: report-only; exact cleanup
    # only when ownership is reconstructible).
    owned_unique_ids = unique_ids_for_map(
        vacuum_entity_id=vacuum_entity_id,
        map_id=map_id_str,
        room_ids=_deleted_room_ids,
    )
    _legacy_prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id_str}_"
    registry = er.async_get(hass)
    removed_entity_ids: list[str] = []
    orphan_candidates: list[dict[str, str]] = []
    for entry in list(registry.entities.values()):
        if entry.platform != DOMAIN:
            continue
        if entry.unique_id in owned_unique_ids:
            _LOGGER.debug("Removing stale entity %s", entry.entity_id)
            registry.async_remove(entry.entity_id)
            removed_entity_ids.append(entry.entity_id)
        elif entry.unique_id.startswith(_legacy_prefix):
            # the old scan would have (possibly wrongly) deleted this — report it
            orphan_candidates.append({
                "entity_id": entry.entity_id,
                "unique_id": entry.unique_id,
            })
    if orphan_candidates:
        _LOGGER.warning(
            "delete_map %s/%s: %d registry entr%s matched the legacy prefix but "
            "not the closed room-id set — left untouched and reported "
            "(orphan_candidates). They may belong to a SIBLING vacuum or to "
            "rooms removed before the RP-009 repair.",
            vacuum_entity_id, map_id_str, len(orphan_candidates),
            "y" if len(orphan_candidates) == 1 else "ies",
        )

    await manager.async_save()

    warnings: list[str] = []
    remaining_maps = [
        mid for mid, b in manager.data.get("maps", {}).get(vacuum_entity_id, {}).items()
        if b.get("rooms")
    ]
    if not remaining_maps:
        warnings.append(
            "This vacuum now has no imported maps. "
            "Import a new map to resume cleaning."
        )

    return _action_result(
        "success",
        code="map_deleted",
        message=f"Map '{display_label}' has been deleted.",
        warnings=warnings,
        data={
            "removed": removed,
            "entities_removed": len(removed_entity_ids),
            "orphan_candidates": orphan_candidates,
            "remaining_map_count": len(remaining_maps),
        },
        next_actions=["import_active_map"] if not remaining_maps else [],
    )
