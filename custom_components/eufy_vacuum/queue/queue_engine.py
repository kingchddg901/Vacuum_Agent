"""Builds queue state, room-clean payloads, and frozen active job snapshots."""

from __future__ import annotations

from typing import Any, Optional

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]

from ..profiles.room_profiles import (
    apply_capability_gate,
    resolve_profile_catalog,
    resolve_room_profile_for_room,
)


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


def _cast_map_id(map_id: Any, map_id_type: str | None) -> Any:
    """Cast the map_id to the wire type the brand expects.

    map_id_type='int' forces int (falling back to str if not numeric).
    map_id_type='str' forces str.
    map_id_type=None preserves the legacy auto-cast: int when numeric,
    str otherwise. This keeps the default behavior identical to
    pre-refactor output for adapters that don't declare a type.
    """
    s = str(map_id)
    if map_id_type == "int":
        try:
            return int(s)
        except (ValueError, TypeError):
            return s
    if map_id_type == "str":
        return s
    return int(s) if s.isdigit() else s


def _write_room_field(
    payload_room: dict[str, Any],
    room_fields: dict[str, dict[str, Any]],
    canonical_name: str,
    canonical_value: Any,
) -> None:
    """Write one per-room field to payload_room using the adapter rename map.

    ``room_fields`` is the ``dispatch.room_fields`` block. For each
    canonical field name the adapter may supply:

      - ``field_name`` (str | None) — wire field name to use; ``None``
        omits the field entirely
      - ``value_map`` (dict[str, Any] | None) — maps stringified
        canonical values to wire values; absent keys pass through

    Absent canonical-name entry in ``room_fields`` → identity rename,
    identity value (passes through unchanged). This makes the function
    safe to call regardless of whether the adapter declared a
    ``room_fields`` block at all.
    """
    cfg = room_fields.get(canonical_name, {})
    wire_name = cfg.get("field_name", canonical_name)
    if wire_name is None:
        return
    value_map = cfg.get("value_map")
    if value_map:
        wire_value = value_map.get(str(canonical_value), canonical_value)
    else:
        wire_value = canonical_value
    payload_room[wire_name] = wire_value


def build_room_clean_payload(
    *,
    vacuum_entity_id: str,
    map_id: str,
    managed_rooms: dict[str, dict[str, Any]],
    queue_room_ids: list[int] | None = None,
    stored_profiles: dict[str, dict[str, Any]] | None = None,
    capabilities: dict[str, Any] | None = None,
    dispatch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the vacuum room_clean payload and resolved room metadata.

    Profiles are resolved and capability-gated for each room. Returns a
    dict containing the API ``payload``, ``resolved_rooms``, and
    ``room_count``.

    Wire payload field names and value vocabularies are controlled by
    the adapter's ``dispatch`` config block (see
    docs/dev/adapter-config-reference.md). Absent or partial ``dispatch``
    falls back to Eufy-shape defaults so this function is safe to call
    without the parameter — that is the legacy path and produces
    byte-for-byte the same output as pre-refactor.
    """
    capabilities = capabilities or {}
    dispatch = dispatch or {}
    selected_ids = set(queue_room_ids or [])

    # Resolve this vacuum's room-profile catalog (default_profile, built-ins, floor-type
    # defaults) from the adapter's room_profiles block; absent → the in-code defaults
    # (byte-identical for Eufy). Threaded into per-room resolution + the capability gate
    # so a brand's profile vocabulary reaches the dispatched settings. Deferred import
    # keeps queue_engine free of the registry at import time.
    from ..adapters.registry import get_adapter_config

    _catalog = resolve_profile_catalog(
        (get_adapter_config(vacuum_entity_id) or {}).get("room_profiles")
    )

    # Outer wrapper field names — fall back to Eufy defaults.
    map_id_field: str = dispatch.get("map_id_field", "map_id")
    map_id_type: str | None = dispatch.get("map_id_type")  # None = legacy auto-cast
    rooms_field: str = dispatch.get("rooms_field", "rooms")

    # Per-room field names — fall back to Eufy defaults.
    room_id_field: str = dispatch.get("room_id_field", "id")
    clean_passes_field: str = dispatch.get("clean_passes_field", "clean_times")
    room_fields: dict[str, dict[str, Any]] = dispatch.get("room_fields", {}) or {}

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
            catalog=_catalog,
        )

        gated = apply_capability_gate(
            resolved,
            capabilities,
            resolved_profile_name=resolved.get("resolved_profile_name"),
            catalog=_catalog,
        )

        # Canonical (framework-internal) values, before any wire rename.
        # Mop-mode and capability gates below check the canonical value,
        # not the wire value, so they remain valid across brands.
        clean_mode = str(gated["clean_mode"])
        fan_speed = str(gated["fan_speed"])
        water_level = str(gated["water_level"])
        clean_intensity = str(gated["clean_intensity"])
        path_type = str(gated["path_type"])
        clean_passes = int(gated["clean_passes"])
        edge_mopping = bool(gated["edge_mopping"])

        payload_room: dict[str, Any] = {
            room_id_field: room_id,
            clean_passes_field: clean_passes,
        }

        # Per-room fields written through the adapter rename map.
        # Unconditional fields first, then capability-gated ones.
        _write_room_field(payload_room, room_fields, "fan_speed", fan_speed)
        _write_room_field(payload_room, room_fields, "clean_mode", clean_mode)
        _write_room_field(payload_room, room_fields, "clean_intensity", clean_intensity)

        if supports_water and clean_mode in {"mop", "vacuum_mop"}:
            _write_room_field(payload_room, room_fields, "water_level", water_level)

        if supports_edge and clean_mode in {"mop", "vacuum_mop"}:
            _write_room_field(payload_room, room_fields, "edge_mopping", edge_mopping)

        if supports_path:
            _write_room_field(payload_room, room_fields, "path_type", path_type)

        payload_rooms.append(payload_room)

        resolved_rooms.append(
            {
                "room_id": room_id,
                "name": room.get("name"),
                "slug": room.get("slug"),
                "selected_profile_name": resolved["selected_profile_name"],
                "resolved_profile_name": resolved["resolved_profile_name"],
                # Resolved-room metadata always uses canonical names —
                # this is the framework's internal record, not the wire
                # payload. Learning and history readers depend on these
                # canonical keys, so they intentionally do not pass
                # through the rename map.
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
            map_id_field: _cast_map_id(map_id, map_id_type),
            rooms_field: payload_rooms,
        },
        "resolved_rooms": resolved_rooms,
        "room_count": len(payload_rooms),
    }


def build_active_job_state(
    *,
    vacuum_entity_id: str,
    map_id: str,
    queue_state: dict[str, Any],
    payload_state: dict[str, Any],
    phases: list[dict[str, Any]] | None = None,
    current_phase_index: int = 0,
) -> dict[str, Any]:
    """Return the initial active job state dict, frozen at job-start time.

    ``queue_stable_keys`` are composite room identifiers in the form
    ``"{vacuum_entity_id}:{map_id}:{room_id}"``, used for identity-safe
    cross-map room tracking. ``queue_room_ids`` is also populated for
    backward compatibility with the learning subsystem.

    ``phases`` is the sequenced job-model's ordered list of per-phase payload
    envelopes (each like ``build_room_clean_payload`` output). When ``None``
    (atomic_batch — the default and every current adapter) the phase keys are
    omitted entirely, so the output is byte-identical to pre-sequencing.
    ``advance_active_job_phase`` consumes these at the completion hook.
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

    state = {
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

    # Sequenced job model only — atomic_batch (the default, every current
    # adapter) leaves these keys absent so the snapshot is byte-identical.
    if phases is not None:
        state["phases"] = phases
        state["current_phase_index"] = int(current_phase_index)
        state["phase_count"] = len(phases)

    return state


def advance_active_job_phase(active_job: dict[str, Any]) -> dict[str, Any] | None:
    """Advance a sequenced job to its next phase, or return None if it was the last.

    Called at the completion hook when a phase's room set has finished. Returns
    a new active-job dict swapped to the next phase: ``resolved_rooms`` /
    ``payload`` / ``room_count`` / ``queue_*`` come from the next phase, per-phase
    progress (``completed_room_ids`` / ``completed_rooms`` / ``current_room_id`` /
    timing) resets, and ``current_phase_index`` increments. Returns ``None`` for
    an atomic job (no ``phases``) or when already on the final phase — in both
    cases the caller finalizes exactly as today.
    """
    phases = active_job.get("phases")
    if not isinstance(phases, list) or len(phases) < 2:
        return None

    idx = int(active_job.get("current_phase_index", 0))
    if idx >= len(phases) - 1:
        return None

    next_idx = idx + 1
    next_phase = phases[next_idx] if isinstance(phases[next_idx], dict) else {}
    next_resolved = list(next_phase.get("resolved_rooms", []))
    next_room_ids = [
        int(r["room_id"]) for r in next_resolved if isinstance(r, dict) and "room_id" in r
    ]
    vac = active_job.get("vacuum_entity_id")
    mid = active_job.get("map_id")

    advanced = dict(active_job)
    advanced["current_phase_index"] = next_idx
    advanced["resolved_rooms"] = next_resolved
    advanced["payload"] = dict(next_phase.get("payload", {}))
    advanced["room_count"] = int(next_phase.get("room_count", len(next_resolved)))
    advanced["queue_room_ids"] = next_room_ids
    advanced["queue_stable_keys"] = [f"{vac}:{mid}:{rid}" for rid in next_room_ids]
    advanced["queue_rooms"] = list(next_phase.get("queue_rooms", []))
    # Reset per-phase progress — the next phase is a fresh atomic sub-job.
    advanced["completed_room_ids"] = []
    advanced["completed_rooms"] = []
    advanced["current_room_id"] = next_room_ids[0] if next_room_ids else None
    advanced["current_room_started_at"] = None
    advanced["current_room_paused_seconds"] = 0
    advanced["status"] = "started"
    # Each phase is a fresh atomic sub-job: the next phase must be observed
    # active again before it can finalize, so the stale completion signal from
    # the phase that just ended can't immediately re-finalize it.
    advanced["has_observed_active_lifecycle"] = False
    return advanced
