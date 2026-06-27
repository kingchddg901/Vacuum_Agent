"""Evaluates protection level for destructive setup operations.

The backend is the single source of truth for protection level; the panel
only displays it. Levels: ``normal`` (one-click), ``elevated`` (confirm
click), ``high`` (typed confirmation — must match the map display name).
"""

from __future__ import annotations

from typing import Any


def evaluate_map_protection(
    manager,
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict[str, Any]:
    """Return protection metadata for deleting one imported map.

    Result shape:
    {
        "protection_level":           "normal" | "elevated" | "high",
        "reasons": [
            {"code": str, "message": str}
        ],
        "requires_typed_confirmation": bool,   # True only for a NAMED high map
        "requires_confirmation":       bool,   # one-click confirm (elevated, or unnamed high)
        "typed_confirmation_value":   str | None,   # stored map name; None when unnamed
    }
    """
    reasons: list[dict[str, str]] = []
    map_id_str = str(map_id)

    vacuum_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {})
    bucket      = vacuum_maps.get(map_id_str, {})
    rooms       = bucket.get("rooms", {})
    # Raw stored name, or None when unnamed. None is load-bearing: a synthesized
    # "Map N" token would be locale-dependent and break the typed match, so an
    # unnamed map drops to a one-click confirm. The card renders setup.map_n.
    stored_name = bucket.get("metadata", {}).get("display_name") or None

    imported_map_ids = [
        mid for mid, b in vacuum_maps.items() if b.get("rooms")
    ]
    if len(imported_map_ids) <= 1:
        reasons.append({
            "code":    "only_map",
            "message": "This is the only imported map for this vacuum.",
        })

    active_job = (
        manager.data.get("active_jobs", {})
        .get(vacuum_entity_id, {})
        .get(map_id_str, {})
    )
    if isinstance(active_job, dict) and active_job.get("has_observed_active_lifecycle"):
        reasons.append({
            "code":    "has_active_job",
            "message": "A cleaning job is running or was recently active on this map.",
        })

    map_history = (
        manager.data.get("room_history", {})
        .get(vacuum_entity_id, {})
        .get(map_id_str, {})
    )
    if map_history:
        reasons.append({
            "code":    "has_learning_data",
            "message": f"This map has cleaning history for {len(map_history)} room(s).",
        })

    has_rules = any(
        room.get("rules") for room in rooms.values()
    )
    if has_rules:
        reasons.append({
            "code":    "has_rules",
            "message": "One or more rooms have automation rules configured.",
        })

    has_access_graph = any(
        room.get("grants_access_to") for room in rooms.values()
    )
    if has_access_graph:
        reasons.append({
            "code":    "has_access_graph",
            "message": "One or more rooms are part of an access graph.",
        })

    elevated_codes = {r["code"] for r in reasons}
    if "has_active_job" in elevated_codes:
        level = "high"
    elif len(reasons) >= 2:
        level = "high"
    elif reasons:
        level = "elevated"
    else:
        level = "normal"

    # Typed confirmation only when we have a real, locale-invariant name to match
    # against. An unnamed map keeps high-level friction via a one-click confirm
    # (requires_confirmation) but cannot demand a typed token it has no name for.
    requires_typed = level == "high" and bool(stored_name)
    requires_confirmation = level != "normal"

    return {
        "protection_level":            level,
        "reasons":                     reasons,
        "requires_typed_confirmation": requires_typed,
        "requires_confirmation":       requires_confirmation,
        "typed_confirmation_value":    stored_name if requires_typed else None,
    }
