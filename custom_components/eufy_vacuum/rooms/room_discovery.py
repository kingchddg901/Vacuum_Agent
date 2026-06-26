"""Reads room segment data from the vacuum's HA state and normalizes it for storage.

All brand-specific knowledge (which entity exposes the room list, which
attribute contains it, which keys hold room ID and name) comes from the
adapter registry's discovery config block. This file contains no vacuum
brand assumptions — it reads whatever the adapter declares.

Adapter config shape consumed here (adapters/config_schema.py § discovery):
    room_list_entity:    "vacuum_entity" | <full entity_id>
    room_list_attribute: str — attribute name on the entity
    room_id_key:         str — key in each room dict for the room ID
    room_name_key:       str — key in each room dict for the room name

When the adapter is not registered or discovery config is absent, both
functions degrade gracefully (return None / empty list).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import slugify_room_name
from .source_refresh import (
    SOURCE_SERVICE_RESPONSE,
    get_cached_room_source,
)
from ..adapters.registry import get_adapter_config

_LOGGER = logging.getLogger(__name__)

# HA sentinel states that mean "no usable value".
_ACTIVE_MAP_SENTINELS = {"unknown", "unavailable", "", "none", "None"}


def get_active_map_id(hass: HomeAssistant, vacuum_entity_id: str) -> str | None:
    """Return the active map ID for a vacuum, if available.

    The adapter declares ``entities.active_map`` from a NAMING PATTERN for every
    device, so the config always carries an entity id — "declared" does NOT mean
    "exists". Resolution therefore keys off whether the entity actually exists:

    - Entity present in the state machine → it is the single source of truth
      (a sentinel value returns None — wait, don't fork a second map).
    - Entity absent from the state machine but present in the ENTITY REGISTRY →
      a novel device whose sensor hasn't materialised yet (boot/restart window):
      return None and wait. Must NOT fork a phantom implicit map.
    - Entity absent from BOTH state machine and registry → the sensor is never
      created: an attribute-mode device (e.g. Eufy on the scalar/Tuya transport)
      that surfaces its room list as a vacuum attribute. Fall back to the
      adapter's single implicit map id (see _implicit_attribute_map_id).

    Returns None when no path yields an id.
    """
    config = get_adapter_config(vacuum_entity_id)
    active_map_entity = (config or {}).get("entities", {}).get("active_map")

    if active_map_entity:
        state = hass.states.get(active_map_entity)
        if state is not None:
            value = state.state
            if value in _ACTIVE_MAP_SENTINELS:
                _LOGGER.debug(
                    "Active map entity %s sentinel value for %s: %s",
                    active_map_entity, vacuum_entity_id, value,
                )
                return None
            return str(value)
        # Declared but not in the state machine. Distinguish a registered-but-
        # not-yet-materialised sensor (novel boot race → wait) from a sensor that
        # is never created (scalar/attribute mode → implicit fallback).
        if _entity_registered(hass, active_map_entity):
            _LOGGER.debug(
                "Active map entity %s registered but no state yet for %s — waiting",
                active_map_entity, vacuum_entity_id,
            )
            return None
        _LOGGER.debug(
            "Active map entity %s declared but never created for %s — trying "
            "implicit attribute map", active_map_entity, vacuum_entity_id,
        )

    return _implicit_attribute_map_id(hass, vacuum_entity_id, config)


def _entity_registered(hass: HomeAssistant, entity_id: str) -> bool:
    """True if entity_id exists in the HA entity registry.

    Used to tell a sensor that is momentarily stateless (registered, e.g. during
    a restart) from one that is never created at all (the scalar transport never
    registers an active_map sensor). Defensive — never raises.
    """
    try:
        return er.async_get(hass).async_get(entity_id) is not None
    except Exception:  # pragma: no cover - defensive
        return False


def _implicit_attribute_map_id(
    hass: HomeAssistant, vacuum_entity_id: str, config: dict | None
) -> str | None:
    """Single implicit map id for an attribute-mode device (no active_map sensor).

    A device that exposes its room list as a vacuum-entity attribute but creates
    no active_map sensor still has exactly one map. When the adapter declares
    ``discovery.implicit_map_id`` AND that room-list attribute currently holds at
    least one room-shaped (dict) row, return the implicit id so import/discovery
    have an anchor. Returns None otherwise — so brands that don't opt in
    (Roborock, which uses a service-response source and sets no implicit_map_id)
    are unaffected, and the implicit map never appears for a device that exposes
    no usable rooms (an empty or all-junk segments list — which discovery would
    reject anyway).
    """
    discovery = (config or {}).get("discovery", {}) or {}
    implicit = discovery.get("implicit_map_id")
    attr = discovery.get("room_list_attribute")
    # Only the vacuum-attribute room source supports an implicit single map.
    if not implicit or not attr or discovery.get("room_list_entity") != "vacuum_entity":
        return None
    state = hass.states.get(vacuum_entity_id)
    rooms = state.attributes.get(attr) if state is not None else None
    # Require at least one dict row — a non-empty list of non-dicts is not a usable
    # room list and must not anchor a phantom map (matches discover_rooms' filter).
    if isinstance(rooms, list) and any(isinstance(r, dict) for r in rooms):
        return str(implicit)
    return None


def discover_rooms_for_vacuum(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return normalized room dicts from the adapter's declared room list entity.

    Reads discovery config from the adapter registry:
      room_list_entity    — "vacuum_entity" or a full entity ID
      room_list_attribute — attribute name that holds the room list
      room_id_key         — key in each room dict for the room ID
      room_name_key       — key in each room dict for the room name

    Returns an empty list when the adapter is not registered, discovery
    config is absent, or the room list attribute is missing/invalid.
    """
    config = get_adapter_config(vacuum_entity_id)
    discovery = (config or {}).get("discovery", {})

    source_kind = discovery.get("source")
    room_id_key = discovery.get("room_id_key")
    room_name_key = discovery.get("room_name_key")

    # Both sources still need to know which keys carry the room id + name.
    if not all((room_id_key, room_name_key)):
        _LOGGER.debug(
            "Discovery config incomplete for %s — skipping room discovery",
            vacuum_entity_id,
        )
        return []

    resolved_map_id = map_id or get_active_map_id(hass, vacuum_entity_id) or "unknown"

    if source_kind == SOURCE_SERVICE_RESPONSE:
        # The room list lives in a cached service response (refreshed at the
        # async boundaries by async_refresh_room_source), keyed by map NAME —
        # the same value entities.active_map reports for these brands.
        per_map = get_cached_room_source(hass, vacuum_entity_id)
        segments = per_map.get(str(resolved_map_id))
        if segments is None and len(per_map) == 1:
            # Single-map brand whose active_map value didn't line up with the
            # cache key (e.g. active_map unknown at refresh time) — use the one
            # map we have rather than discovering nothing.
            segments = next(iter(per_map.values()))
        if not isinstance(segments, list):
            _LOGGER.debug(
                "No cached room source for %s map %s",
                vacuum_entity_id,
                resolved_map_id,
            )
            return []
    else:
        # Attribute source (default, e.g. Eufy): the room list is a live
        # attribute on an entity. room_list_entity / room_list_attribute are
        # required here.
        room_list_entity_key = discovery.get("room_list_entity")
        room_list_attribute = discovery.get("room_list_attribute")
        if not all((room_list_entity_key, room_list_attribute)):
            _LOGGER.debug(
                "Attribute discovery config incomplete for %s — skipping",
                vacuum_entity_id,
            )
            return []

        source_entity_id = (
            vacuum_entity_id
            if room_list_entity_key == "vacuum_entity"
            else room_list_entity_key
        )
        source_state = hass.states.get(source_entity_id)
        if source_state is None:
            _LOGGER.debug(  # pragma: no cover
                "Room list entity %s missing for %s", source_entity_id, vacuum_entity_id
            )
            return []

        segments = source_state.attributes.get(room_list_attribute)
        if not isinstance(segments, list):
            _LOGGER.debug(
                "Room list attribute '%s' missing or invalid for %s",
                room_list_attribute,
                vacuum_entity_id,
            )
            return []

    rooms: list[dict[str, Any]] = []
    seen_room_ids: set[int] = set()

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        raw_name = segment.get(room_name_key)
        raw_id = segment.get(room_id_key)

        if raw_name is None or raw_id is None:
            continue

        try:
            room_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if room_id in seen_room_ids:
            continue

        seen_room_ids.add(room_id)

        name = str(raw_name).strip()
        if not name:
            continue

        rooms.append(
            {
                "room_id": room_id,
                "map_id": str(resolved_map_id),
                "name": name,
                "slug": slugify_room_name(name),
            }
        )

    return rooms


def discover_rooms_payload(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> dict[str, Any]:
    """Return discovery payload shaped for storage, services, and card use."""
    resolved_map_id = map_id or get_active_map_id(hass, vacuum_entity_id)

    rooms = discover_rooms_for_vacuum(
        hass,
        vacuum_entity_id=vacuum_entity_id,
        map_id=resolved_map_id,
    )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "active_map_id": resolved_map_id,
        "room_count": len(rooms),
        "rooms": rooms,
    }
