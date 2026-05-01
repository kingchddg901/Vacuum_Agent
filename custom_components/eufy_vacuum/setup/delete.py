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
    display_name = protection["typed_confirmation_value"]

    if protection["requires_typed_confirmation"]:
        if not confirmation_token:
            return _action_result(
                "requires_confirmation",
                code="typed_confirmation_required",
                message=(
                    f"Deleting '{display_name}' requires typed confirmation. "
                    f"Send the map name as confirmation_token."
                ),
                data={"protection": protection},
            )
        if confirmation_token.strip() != display_name.strip():
            return _action_result(
                "blocked",
                code="confirmation_mismatch",
                message=(
                    f"Confirmation token does not match map name '{display_name}'. "
                    "Check for extra spaces or typos."
                ),
                data={"protection": protection},
            )
    elif level == "elevated" and not confirmation_token:
        # Elevated protection requires a one-click confirm (any truthy token), not a typed name.
        return _action_result(
            "requires_confirmation",
            code="confirmation_required",
            message=f"Confirm deletion of '{display_name}'.",
            data={"protection": protection},
        )

    _LOGGER.info(
        "Deleting map %s for %s (protection=%s)",
        map_id_str, vacuum_entity_id, level,
    )
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

    # Sweep the entity registry directly to remove any stragglers the platform
    # teardown callbacks may have missed.
    prefix = f"{vacuum_entity_id.replace('.', '_')}_{map_id_str}_"
    registry = er.async_get(hass)
    removed_entity_ids: list[str] = []
    for entry in list(registry.entities.values()):
        if (
            entry.platform == DOMAIN
            and entry.unique_id.startswith(prefix)
        ):
            _LOGGER.debug("Removing stale entity %s", entry.entity_id)
            registry.async_remove(entry.entity_id)
            removed_entity_ids.append(entry.entity_id)

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
        message=f"Map '{display_name}' has been deleted.",
        warnings=warnings,
        data={
            "removed": removed,
            "entities_removed": len(removed_entity_ids),
            "remaining_map_count": len(remaining_maps),
        },
        next_actions=["import_active_map"] if not remaining_maps else [],
    )
