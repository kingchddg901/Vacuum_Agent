"""Pluggable dispatch engines — brand-specific clean-command payload shapes.

Mirrors the segmenter-engine pattern (``mapping/segmenter_engines.py``): each
brand registers a dispatch engine under a string name in ``_DISPATCH_ENGINES``,
and the adapter selects one via ``dispatch.template`` in its config. The engine
owns the *structure* of the per-clean payload — the thing the adapter config's
field-rename map (``room_fields`` etc.) cannot express:

  - Eufy   → ``{map_id, rooms:[{id, clean_times, fan_speed, …}]}``  (list-of-dicts)
  - Roborock/Ecovacs → ``{segments:[ints], repeat:n}`` (flat id list + batch scalar)
  - Dreame → ``{segments:[…], suction_level:[…], repeats:[…]}`` (positional arrays)

Phase 1 (this module) is **payload-only**: engines produce the inner payload
dict; the send-site envelope (wrapped ``{command, params}`` vs direct merge) and
service domain/name stay in ``core/manager.py``. ``vacuum.clean_area`` (a service
*target*, not a data payload) is deferred until engines own the full call.

Fallback policy differs from segmenter engines on purpose: an absent or unknown
``template`` falls back to the **Eufy** engine, not a noop, because the framework's
historical default (no adapter registered) is the Eufy payload shape. See
``build_room_clean_payload`` — its docstring guarantees Eufy-shape output when
``dispatch`` is absent, and routing through the Eufy engine preserves that
byte-for-byte.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from .queue_engine import build_room_clean_payload

_LOGGER = logging.getLogger(__name__)


class DispatchEngine(Protocol):
    """One pluggable dispatch engine.

    Stateless from the framework's perspective. ``build_payload`` must be a pure
    function of its inputs and return the same envelope the legacy
    ``build_room_clean_payload`` returns: a dict with ``payload``,
    ``resolved_rooms``, and ``room_count``. ``resolved_rooms`` always uses
    canonical (framework-internal) field names regardless of the wire shape, so
    learning/history readers are brand-independent.
    """

    template_name: str   # matches the key in _DISPATCH_ENGINES

    def build_payload(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        managed_rooms: dict[str, dict[str, Any]],
        queue_room_ids: list[int] | None = None,
        stored_profiles: dict[str, dict[str, Any]] | None = None,
        capabilities: dict[str, Any] | None = None,
        dispatch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return ``{payload, resolved_rooms, room_count, …}`` for this brand."""
        ...


class EufyRoomCleanEngine:
    """Eufy ``room_clean`` list-of-dicts payload.

    Delegates verbatim to ``build_room_clean_payload`` — this is the original
    implementation, unchanged, so the Eufy path is byte-for-byte identical to
    pre-engine output. New brand engines replace only ``build_payload``.
    """

    template_name = "eufy_room_clean"

    def build_payload(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        managed_rooms: dict[str, dict[str, Any]],
        queue_room_ids: list[int] | None = None,
        stored_profiles: dict[str, dict[str, Any]] | None = None,
        capabilities: dict[str, Any] | None = None,
        dispatch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_room_clean_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            managed_rooms=managed_rooms,
            queue_room_ids=queue_room_ids,
            stored_profiles=stored_profiles,
            capabilities=capabilities,
            dispatch=dispatch,
        )


class GenericRoomIdsEngine:
    """Flat room-id list + a single batch ``passes`` scalar.

    For brands whose segment-clean service takes a flat list of room/segment ids
    plus one repeat/cleanings value for the *whole batch*:

      - Roborock ``app_segment_clean`` → ``{segments: [ints], repeat: n}``
      - Ecovacs  ``spot_area``         → ``{rooms: [ints], cleanings: n}``

    These brands expose **no per-room fan/water/passes on the wire** (fan is a
    global vacuum setting), so the framework's per-room run-profile passes are
    collapsed to one batch value — the **max** requested across the selected
    rooms, clamped to ``[1, passes_max]`` (``passes_max`` from dispatch config,
    default 3 per Roborock's documented range). Per-room canonical settings still
    survive untouched in ``resolved_rooms`` for learning/history.

    Field names are taken from the adapter ``dispatch`` block:
      - ``rooms_field``       (default ``"segments"``)  — the flat id list key
      - ``clean_passes_field`` (default ``"repeat"``)   — the batch scalar key;
        set to ``None`` to omit passes entirely
    """

    template_name = "generic_room_ids"

    def build_payload(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        managed_rooms: dict[str, dict[str, Any]],
        queue_room_ids: list[int] | None = None,
        stored_profiles: dict[str, dict[str, Any]] | None = None,
        capabilities: dict[str, Any] | None = None,
        dispatch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dispatch = dispatch or {}
        # Reuse the shared resolver for profile resolution + capability gating +
        # canonical resolved_rooms. Its Eufy-shaped payload is discarded; only
        # resolved_rooms (already enabled-filtered and order-sorted) is used.
        base = build_room_clean_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            managed_rooms=managed_rooms,
            queue_room_ids=queue_room_ids,
            stored_profiles=stored_profiles,
            capabilities=capabilities,
            dispatch=dispatch,
        )
        resolved = base["resolved_rooms"]

        rooms_field = dispatch.get("rooms_field", "segments")
        passes_field = dispatch.get("clean_passes_field", "repeat")
        passes_max = int(dispatch.get("passes_max", 3))

        segment_ids = [int(r["room_id"]) for r in resolved]
        passes_values = [int(r.get("clean_passes", 1) or 1) for r in resolved]
        batch_passes = max(1, min(passes_max, max(passes_values, default=1)))

        payload: dict[str, Any] = {rooms_field: segment_ids}
        if passes_field is not None:
            payload[passes_field] = batch_passes

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "payload": payload,
            "resolved_rooms": resolved,
            "room_count": len(segment_ids),
        }


class RoborockSegmentEngine(GenericRoomIdsEngine):
    """Roborock ``app_segment_clean`` — flat segment list + batch ``repeat``.

    Pure naming subclass of :class:`GenericRoomIdsEngine`; the shape is identical
    (flat ids + batch scalar). Kept distinct so the schema's
    ``roborock_segment_clean`` template resolves to a correctly-named engine and
    the contract harness can address it by brand.
    """

    template_name = "roborock_segment_clean"


# =============================================================================
# Registry
# =============================================================================

_DISPATCH_ENGINES: dict[str, DispatchEngine] = {
    "eufy_room_clean": EufyRoomCleanEngine(),
    "roborock_segment_clean": RoborockSegmentEngine(),
    "generic_room_ids": GenericRoomIdsEngine(),  # Ecovacs spot_area + catch-all
    # "dreame_room_clean": DreameSegmentEngine(),  # parallel arrays — next
}

_FALLBACK_TEMPLATE = "eufy_room_clean"


def get_dispatch_engine(name: str | None) -> DispatchEngine:
    """Return the engine registered under ``name``.

    Falls back to the Eufy engine when ``name`` is absent (the legacy
    no-adapter default) or unknown. An *unknown* (non-empty) name is logged as a
    warning since it signals a misconfigured adapter; an absent name is normal
    legacy behavior and is not warned.
    """
    if not name:
        return _DISPATCH_ENGINES[_FALLBACK_TEMPLATE]

    engine = _DISPATCH_ENGINES.get(name)
    if engine is None:
        _LOGGER.warning(
            "Unknown dispatch template %r; falling back to %r. "
            "Check adapter_config.dispatch.template.",
            name, _FALLBACK_TEMPLATE,
        )
        return _DISPATCH_ENGINES[_FALLBACK_TEMPLATE]

    return engine


def known_dispatch_templates() -> list[str]:
    """Return the set of template names ``_validate_adapter`` should accept."""
    return list(_DISPATCH_ENGINES)
