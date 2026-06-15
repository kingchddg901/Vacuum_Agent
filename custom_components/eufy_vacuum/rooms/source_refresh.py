"""Service-call room-source refresh + flatten shim.

Two discovery *sources* exist in the framework:

  - ``entity_attribute`` (default, Eufy) — the room list is a live attribute on
    an HA entity. ``rooms/room_discovery.py`` reads it synchronously; nothing to
    refresh because the attribute is always current.

  - ``service_response`` (Roborock) — the room list only exists in the RESPONSE
    of a service call (``roborock.get_maps``), never as an entity attribute.
    Service calls are async; the sync discovery path (and its many callers:
    drift, onboarding) cannot make one. So an async refresher calls the service
    at the async boundaries (the discover service handler + the auto-discovery
    listener), flattens the response into the same list-of-dicts shape an
    attribute would have carried, and caches it. The sync discovery path then
    reads the cache instead of an attribute — one branch, everything downstream
    (slug, dedupe, int-coerce) unchanged.

The flatten shim normalizes ``get_maps``'s ``{segment_id_str: name}`` room
mapping into ``[{<room_id_key>: id_str, <room_name_key>: name}, ...]`` per map,
keyed by the map NAME (which is what ``entities.active_map`` — Roborock's
``select.{id}_selected_map`` — reports, so the sync path's resolved active-map
id lines up with a cache key).

Public surface:
    async_refresh_room_source(hass, vacuum_entity_id) -> None   (async)
    get_cached_room_source(hass, vacuum_entity_id) -> dict[str, list[dict]]
    set_cached_room_source(hass, vacuum_entity_id, per_map) -> None
    flatten_maps_response(response, *, discovery) -> dict[str, list[dict]]  (pure)
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

#: hass.data[DOMAIN] slot holding the flattened per-vacuum room source cache.
#: Shape: {vacuum_entity_id: {map_name: [ {<room_id_key>: str, <room_name_key>: str}, ... ]}}
DATA_ROOM_SOURCE_CACHE = "room_source_cache"

#: Discovery source kinds.
SOURCE_ENTITY_ATTRIBUTE = "entity_attribute"
SOURCE_SERVICE_RESPONSE = "service_response"


# ---------------------------------------------------------------------------
# Cache accessors
# ---------------------------------------------------------------------------

def get_cached_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Return the cached per-map flattened room source for one vacuum.

    Returns an empty dict when nothing has been refreshed yet (the sync
    discovery path then degrades to an empty room list, same as a missing
    attribute).
    """
    cache = hass.data.get(DOMAIN, {}).get(DATA_ROOM_SOURCE_CACHE, {})
    value = cache.get(vacuum_entity_id)
    return value if isinstance(value, dict) else {}


def set_cached_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    per_map: dict[str, list[dict[str, Any]]],
) -> None:
    """Store the flattened per-map room source for one vacuum."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    cache = domain_data.setdefault(DATA_ROOM_SOURCE_CACHE, {})
    cache[vacuum_entity_id] = per_map


# ---------------------------------------------------------------------------
# Flatten shim (pure — no hass)
# ---------------------------------------------------------------------------

def _extract_maps_list(
    response: Any,
    *,
    vacuum_entity_id: str | None = None,
) -> list[Any]:
    """Pull the ``maps`` list out of a get_maps ServiceResponse.

    Tolerates the shapes a ``return_response=True`` service call can produce:
      - ``{"maps": [...]}``                       (handler returns the dict directly)
      - ``{"<entity_id>": {"maps": [...]}}``      (response keyed by target entity)
      - ``[ {...}, ... ]``                        (handler returns the list bare)
    Returns an empty list for anything unrecognized.
    """
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return []

    # Direct {"maps": [...]}.
    maps = response.get("maps")
    if isinstance(maps, list):
        return maps

    # Per-entity wrapper: prefer the targeted entity, else the first dict value
    # that carries a "maps" list.
    if vacuum_entity_id and isinstance(response.get(vacuum_entity_id), dict):
        inner = response[vacuum_entity_id].get("maps")
        if isinstance(inner, list):
            return inner
    for value in response.values():
        if isinstance(value, dict) and isinstance(value.get("maps"), list):
            return value["maps"]

    return []


def flatten_maps_response(
    response: Any,
    *,
    discovery: dict[str, Any],
    vacuum_entity_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Flatten a get_maps response into per-map normalized room lists.

    Each map's ``rooms`` value is a ``{segment_id_str: name}`` mapping; this
    rewrites it into a list of ``{<room_id_key>: id, <room_name_key>: name}``
    dicts — exactly the list-of-dicts shape the attribute-source discovery path
    already iterates. Map keys are the map NAME (matches ``entities.active_map``).

    Defensive against an already-list ``rooms`` value (returned as-is) and skips
    malformed entries. ``room_id_key``/``room_name_key`` default to the Roborock
    shape but honor the adapter's discovery config.
    """
    rooms_key = discovery.get("maps_rooms_key", "rooms")
    map_name_key = discovery.get("map_name_key", "name")
    room_id_key = discovery.get("room_id_key", "segment_id")
    room_name_key = discovery.get("room_name_key", "name")

    maps = _extract_maps_list(response, vacuum_entity_id=vacuum_entity_id)
    out: dict[str, list[dict[str, Any]]] = {}

    for map_entry in maps:
        if not isinstance(map_entry, dict):
            continue
        map_name = str(map_entry.get(map_name_key, "")).strip()
        if not map_name:
            continue

        rooms = map_entry.get(rooms_key)
        seg_list: list[dict[str, Any]] = []

        if isinstance(rooms, dict):
            # The Roborock shape: {"16": "KITCHEN", "17": "Dining Room", ...}.
            # id_coercion + name-stripping happen downstream in discovery; keep
            # raw (str) ids here so this shim stays a pure structural transform.
            for raw_id, raw_name in rooms.items():
                if raw_name is None:
                    continue
                seg_list.append({room_id_key: raw_id, room_name_key: raw_name})
        elif isinstance(rooms, list):
            # Already list-of-dicts — pass dict entries through untouched.
            seg_list = [room for room in rooms if isinstance(room, dict)]

        out[map_name] = seg_list

    return out


# ---------------------------------------------------------------------------
# Async refresher
# ---------------------------------------------------------------------------

async def async_refresh_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> None:
    """Refresh the cached room source for one vacuum if it uses a service source.

    No-op for ``entity_attribute`` sources (and for adapters with no discovery
    block) — their room list is always live, so there is nothing to cache. For
    ``service_response`` sources, calls the adapter-declared maps service with
    ``return_response=True``, flattens the result, and caches it. All failures
    are swallowed (best-effort) — discovery then reads a stale/empty cache and
    degrades gracefully rather than raising into the caller.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    discovery = config.get("discovery") or {}
    if discovery.get("source") != SOURCE_SERVICE_RESPONSE:
        return

    maps_service = discovery.get("maps_service") or {}
    service_domain = maps_service.get("domain")
    service_name = maps_service.get("service")
    if not service_domain or not service_name:
        _LOGGER.debug(
            "room_source: service_response source for %s declares no maps_service; skipping",
            vacuum_entity_id,
        )
        return

    # A response-returning entity service raises "did not match any entities" when
    # the target entity is unavailable (e.g. right after a restart, before the
    # brand integration finishes loading). Guard the known transient: skip cleanly
    # and let discovery read the cached source rather than throw a traceback. A
    # truly-absent state (None) still proceeds — the try/except below downgrades
    # any "no entity" failure to a warning.
    state = hass.states.get(vacuum_entity_id)
    if state is not None and state.state in ("unavailable", "unknown"):
        _LOGGER.debug(
            "room_source: %s is %s; skipping %s.%s refresh (using cached source)",
            vacuum_entity_id, state.state, service_domain, service_name,
        )
        return

    try:
        response = await hass.services.async_call(
            service_domain,
            service_name,
            {"entity_id": vacuum_entity_id},
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # pragma: no cover - upstream service errors are best-effort
        # Best-effort: discovery degrades to the cached/stale source. Log a concise
        # warning (not a full traceback) — a transient unavailable entity or an
        # upstream hiccup is expected, not a framework fault.
        _LOGGER.warning(
            "room_source: %s.%s failed for %s (%s); using cached source",
            service_domain, service_name, vacuum_entity_id, err,
        )
        return

    per_map = flatten_maps_response(
        response,
        discovery=discovery,
        vacuum_entity_id=vacuum_entity_id,
    )
    set_cached_room_source(hass, vacuum_entity_id, per_map)
    _LOGGER.debug(
        "room_source: refreshed %s — %d map(s): %s",
        vacuum_entity_id,
        len(per_map),
        {name: len(rooms) for name, rooms in per_map.items()},
    )
