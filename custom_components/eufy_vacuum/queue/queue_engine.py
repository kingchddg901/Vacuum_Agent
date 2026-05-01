"""Builds queue state, room-clean payloads, and frozen active job snapshots."""

from __future__ import annotations

from typing import Any, Optional

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]

from ..profiles.room_profiles import apply_capability_gate, resolve_room_profile_for_room


class QueueEntry(TypedDict, total=False):
    """Canonical shape for one entry in the room queue.

    ``stable_key`` is ``"{vacuum_entity_id}:{map_id}:{room_id}"`` — a composite
    key that uniquely identifies a room regardless of its queue position.
    """

    stable_key: str         # "{vacuum_entity_id}:{map_id}:{room_id}"
    vacuum_entity_id: str
    map_id: str
    room_id: int
    name: Optional[str]
    slug: Optional[str]
    order: int
    effective_settings: dict  # EffectiveRoomSettings snapshot at queue-build time
    enabled: bool


class PayloadItem(TypedDict, total=False):
    """Canonical shape for one room's vacuum command payload.

    Derived from ``QueueEntry`` at payload-build time. Capability gating has
    already been applied; ``path_type`` is always present.
    """

    stable_key: str
    room_id: int
    map_id: str
    clean_mode: str
    fan_speed: str
    water_level: str
    clean_intensity: str
    clean_passes: int
    edge_mopping: bool
    path_type: str


class ActiveJobSnapshot(TypedDict, total=False):
    """Canonical shape for a frozen active job snapshot.

    Frozen by ``build_active_job_state()`` at job start and treated as
    immutable for the duration of the job. Only ``status`` and ``ended_at``
    are written after the freeze point.
    """

    vacuum_entity_id: str
    job_id: str
    frozen_at: float
    queue_stable_keys: list     # list[str] — composite room keys frozen at job start
    queue_entries: dict         # dict[stable_key, QueueEntry]
    payload_items: dict         # dict[stable_key, PayloadItem]
    status: str                 # "running" | "paused" | "completed" | "cancelled"
    started_at: float
    ended_at: Optional[float]


def get_enabled_rooms_in_order(
    *,
    managed_rooms: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return enabled rooms sorted by configured order."""
    enabled_rooms = [
        room
        for room in managed_rooms.values()
        if bool(room.get("enabled", False))
    ]

    enabled_rooms.sort(
        key=lambda room: (
            int(room.get("order", 999)),
            str(room.get("name", "")),
        )
    )
    return enabled_rooms


def build_queue_from_managed_rooms(
    *,
    vacuum_entity_id: str,
    map_id: str,
    managed_rooms: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return queue state for all enabled rooms, sorted by order.

    Reflects only the ``enabled`` flag — blocker and modifier rules are
    evaluated later at job-start time, not here.
    """
    enabled_rooms = get_enabled_rooms_in_order(managed_rooms=managed_rooms)

    queue_room_ids = [int(room["room_id"]) for room in enabled_rooms if "room_id" in room]

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "room_count": len(enabled_rooms),
        "queue_room_ids": queue_room_ids,
        "queue_rooms": [
            {
                "room_id": int(room["room_id"]),
                "name": room.get("name"),
                "slug": room.get("slug"),
                "order": int(room.get("order", 999)),
                "profile_name": room.get("profile_name", "vacuum_quick"),
            }
            for room in enabled_rooms
        ],
    }


def build_room_clean_payload(
    *,
    vacuum_entity_id: str,
    map_id: str,
    managed_rooms: dict[str, dict[str, Any]],
    queue_room_ids: list[int] | None = None,
    stored_profiles: dict[str, dict[str, Any]] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the vacuum room_clean payload and resolved room metadata.

    Profiles are resolved and capability-gated for each room. Returns a dict
    containing the API ``payload``, ``resolved_rooms``, and ``room_count``.
    """
    capabilities = capabilities or {}
    selected_ids = set(queue_room_ids or [])

    candidate_rooms = [
        room
        for room in managed_rooms.values()
        if bool(room.get("enabled", False))
        and "room_id" in room
        and (not selected_ids or int(room["room_id"]) in selected_ids)
    ]

    candidate_rooms.sort(
        key=lambda room: (
            int(room.get("order", 999)),
            str(room.get("name", "")),
        )
    )

    payload_rooms: list[dict[str, Any]] = []
    resolved_rooms: list[dict[str, Any]] = []

    supports_mop = bool(capabilities.get("supports_mop_features", False))
    supports_water = bool(capabilities.get("supports_water_control", False))
    supports_path = bool(capabilities.get("supports_path_control", False))
    supports_edge = bool(capabilities.get("supports_edge_mopping", False))
    supports_passes = bool(capabilities.get("supports_passes", True))

    for room in candidate_rooms:
        room_id = int(room.get("room_id", 0))
        if room_id <= 0:
            continue
        resolved = resolve_room_profile_for_room(
            room_config=room,
            stored_profiles=stored_profiles,
        )

        gated = apply_capability_gate(
            resolved,
            capabilities,
            resolved_profile_name=resolved.get("resolved_profile_name"),
        )

        clean_mode = str(gated["clean_mode"])
        fan_speed = str(gated["fan_speed"])
        water_level = str(gated["water_level"])
        clean_intensity = str(gated["clean_intensity"])
        path_type = str(gated["path_type"])
        clean_passes = int(gated["clean_passes"])
        edge_mopping = bool(gated["edge_mopping"])

        payload_room = {
            "id": room_id,
            "clean_times": clean_passes,
            "fan_speed": fan_speed,
            "clean_mode": clean_mode,
            "clean_intensity": clean_intensity,
        }

        if supports_water and clean_mode in {"mop", "vacuum_mop"}:
            payload_room["water_level"] = water_level

        if supports_edge and clean_mode in {"mop", "vacuum_mop"}:
            payload_room["edge_mopping"] = edge_mopping

        if supports_path:
            payload_room["path_type"] = path_type

        payload_rooms.append(payload_room)

        resolved_rooms.append(
            {
                "room_id": room_id,
                "name": room.get("name"),
                "slug": room.get("slug"),
                "selected_profile_name": resolved["selected_profile_name"],
                "resolved_profile_name": resolved["resolved_profile_name"],
                "clean_mode": clean_mode,
                "fan_speed": fan_speed,
                "water_level": water_level,
                "clean_intensity": clean_intensity,
                "path_type": path_type,
                "clean_passes": clean_passes,
                "edge_mopping": edge_mopping,
                "carpet": str(resolved.get("floor_type", "")).startswith("carpet"),
                "capability_gated": {
                    "supports_mop_features": supports_mop,
                    "supports_water_control": supports_water,
                    "supports_path_control": supports_path,
                    "supports_edge_mopping": supports_edge,
                    "supports_passes": supports_passes,
                },
            }
        )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "payload": {
            "map_id": int(map_id) if str(map_id).isdigit() else str(map_id),
            "rooms": payload_rooms,
        },
        "resolved_rooms": resolved_rooms,
        "room_count": len(payload_rooms),
    }


def build_start_block_reason(
    *,
    selected_map_id: str | None,
    active_map_id: str | None,
    queue_room_ids: list[int],
    payload_room_count: int,
    vacuum_state: str | None,
    work_mode: str | None,
    task_status: str | None,
    dock_status: str | None,
) -> dict[str, Any]:
    """Return a start-blocker dict with ``reason``, ``message``, and ``blocked`` flag.

    Checks are evaluated in priority order; the first matching condition wins.
    ``blocked`` is ``False`` only when ``reason`` is ``"ready"``.
    """
    if not selected_map_id:
        reason = "no_target_map"
        message = "Select a target map first."
    elif vacuum_state not in {"docked", "idle", "paused"}:
        reason = "vacuum_busy"
        message = "Vacuum is busy and cannot start a new room job."
    elif selected_map_id != active_map_id:
        reason = "map_mismatch"
        message = "The selected map does not match the vacuum's active map."
    elif work_mode in {"Smart Follow", "Auto", "Room"}:
        reason = "blocked_work_mode"
        message = "Vacuum is still in an active work mode."
    elif task_status in {"Cleaning", "Returning", "Washing Mop"}:
        reason = "blocked_task_status"
        message = "Vacuum task status is still active."
    elif dock_status in {"Washing", "Recycling waste water"}:
        reason = "blocked_dock_status"
        message = "Dock is still servicing the previous job."
    elif not queue_room_ids:
        reason = "no_rooms_selected"
        message = "Select at least one room first."
    elif payload_room_count <= 0:
        reason = "invalid_payload"
        message = "Room-clean payload is missing or invalid."
    else:
        reason = "ready"
        message = "Ready to start cleaning."

    return {
        "reason": reason,
        "message": message,
        "blocked": reason != "ready",
    }


def build_active_job_state(
    *,
    vacuum_entity_id: str,
    map_id: str,
    queue_state: dict[str, Any],
    payload_state: dict[str, Any],
) -> dict[str, Any]:
    """Return the initial active job state dict, frozen at job-start time.

    ``queue_stable_keys`` are composite room identifiers in the form
    ``"{vacuum_entity_id}:{map_id}:{room_id}"``, used for identity-safe
    cross-map room tracking. ``queue_room_ids`` is also populated for
    backward compatibility with the learning subsystem.
    """
    resolved_rooms = list(payload_state.get("resolved_rooms", []))
    queue_room_ids = list(queue_state.get("queue_room_ids", []))
    current_room_id = None
    if resolved_rooms:
        current_room_id = resolved_rooms[0].get("room_id", resolved_rooms[0].get("id"))
    elif queue_room_ids:
        current_room_id = queue_room_ids[0]

    queue_stable_keys = [
        f"{vacuum_entity_id}:{map_id}:{room_id}"
        for room_id in queue_room_ids
    ]

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "queue_room_ids": queue_room_ids,
        "queue_stable_keys": queue_stable_keys,
        "queue_rooms": list(queue_state.get("queue_rooms", [])),
        "payload": dict(payload_state.get("payload", {})),
        "resolved_rooms": resolved_rooms,
        "room_count": int(payload_state.get("room_count", 0)),
        "status": "started",
        "paused_at": None,
        "paused_duration_seconds": 0,
        "completed_room_ids": [],
        "completed_rooms": [],
        "current_room_id": current_room_id,
        "current_room_started_at": None,
        "current_room_paused_seconds": 0,
    }
