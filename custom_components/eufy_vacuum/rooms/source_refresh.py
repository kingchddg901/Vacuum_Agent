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

import asyncio
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config
from ..const import DOMAIN
from ..timestamp_utils import utc_now_iso

_LOGGER = logging.getLogger(__name__)

#: hass.data[DOMAIN] slot holding the flattened per-vacuum room source cache.
#: Entry shape (RP-007): {"per_map": {map_name: [rooms]}, "refreshed_at": iso,
#: "refreshed_mono": float}. Legacy raw per_map dicts are still readable.
DATA_ROOM_SOURCE_CACHE = "room_source_cache"

#: RP-007 step 7 (GATE4 Q16 variant a): how old a cached room source may be for
#: dispatch to trust it when a live refresh FAILS. Operational constant, not
#: empirical tuning — the intent is "recent enough that a vendor-app re-segment
#: in the gap is unlikely", not a measured device property.
REFRESH_TTL_SECONDS = 15 * 60

#: RP-007 step 3 (SRC-4): in-flight refresh coalescing + a monotonic commit
#: generation so a slow stale response can never replace a newer committed one.
_INFLIGHT: dict[str, asyncio.Task] = {}
_GENERATION: dict[str, int] = {}

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
    return get_cached_room_source_with_age(hass, vacuum_entity_id)[0]


def get_cached_room_source_with_age(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], float | None]:
    """Return (per_map, age_seconds) for one vacuum's cached room source.

    age is None when nothing has been cached, or when the entry predates the
    RP-007 freshness stamping (a legacy raw dict) — callers must treat None as
    "age unknown", i.e. NOT fresh.
    """
    cache = hass.data.get(DOMAIN, {}).get(DATA_ROOM_SOURCE_CACHE, {})
    value = cache.get(vacuum_entity_id)
    if isinstance(value, dict) and "per_map" in value:
        per_map = value.get("per_map")
        mono = value.get("refreshed_mono")
        age = (time.monotonic() - mono) if isinstance(mono, (int, float)) else None
        return (per_map if isinstance(per_map, dict) else {}, age)
    # legacy shape: the raw per_map dict, unstamped
    return (value if isinstance(value, dict) else {}, None)


def set_cached_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    per_map: dict[str, list[dict[str, Any]]],
) -> None:
    """Store the flattened per-map room source for one vacuum (freshness-stamped)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    cache = domain_data.setdefault(DATA_ROOM_SOURCE_CACHE, {})
    cache[vacuum_entity_id] = {
        "per_map": per_map,
        "refreshed_at": utc_now_iso(),
        "refreshed_mono": time.monotonic(),
    }


def invalidate_room_source_cache(
    hass: HomeAssistant,
    vacuum_entity_id: str | None = None,
) -> None:
    """Drop cached room sources (RP-007 step 4 / SRC-5): one vacuum's entry, or
    all of them on entry unload — a reloaded entry must not serve the previous
    life's cache as fresh."""
    cache = hass.data.get(DOMAIN, {}).get(DATA_ROOM_SOURCE_CACHE)
    if not isinstance(cache, dict):
        return
    if vacuum_entity_id is None:
        cache.clear()
    else:
        cache.pop(vacuum_entity_id, None)


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


def _active_map_id_from_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    vacuum_entity_id: str,
) -> str | None:
    """Return the adapter-declared active map value if it is currently valid."""
    active_map_entity = (config.get("entities") or {}).get("active_map")
    if not active_map_entity:
        return None

    state = hass.states.get(active_map_entity)
    if state is None:
        return None

    value = str(state.state).strip()
    if value in {"", "unknown", "unavailable", "none", "None"}:
        return None

    return value


def flatten_maps_response(
    response: Any,
    *,
    discovery: dict[str, Any],
    vacuum_entity_id: str | None = None,
    active_map_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Flatten a get_maps response into per-map normalized room lists.

    Each map's ``rooms`` value is a ``{segment_id_str: name}`` mapping; this
    rewrites it into a list of ``{<room_id_key>: id, <room_name_key>: name}``
    dicts — exactly the list-of-dicts shape the attribute-source discovery path
    already iterates. Map keys are the map NAME when present, or the active-map
    select value / map flag fallback when HA's Roborock response omits the name.

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

    active_map_id = str(active_map_id).strip() if active_map_id else None

    for index, map_entry in enumerate(maps):
        if not isinstance(map_entry, dict):
            continue
        map_name = str(map_entry.get(map_name_key, "")).strip()
        if not map_name:
            # HA's Roborock integration can return an unnamed map while the
            # active-map select reports a synthetic name such as "Map 0".
            # Keep the cache key aligned with the select so discovery can find
            # the rooms it just refreshed. If there is no active-map value, use
            # Roborock's numeric flag as the same "Map <flag>" fallback HA shows.
            if active_map_id and len(maps) == 1:
                map_name = active_map_id
            elif map_entry.get("flag") is not None:
                map_name = f"Map {map_entry['flag']}"
            else:
                map_name = f"Map {index}"

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

        # RP-007 (SRC-3): map NAMES are human-editable and can collide (two maps
        # both named "Main"). The last-writer-wins overwrite silently discarded a
        # whole map's rooms; key collision-safely and say so.
        if map_name in out:
            suffix = (
                f"#flag{map_entry['flag']}" if map_entry.get("flag") is not None
                else f"#idx{index}"
            )
            _LOGGER.warning(
                "room_source: duplicate map name %r in get_maps response for %s; "
                "keying the second as %r",
                map_name, vacuum_entity_id, map_name + suffix,
            )
            map_name = map_name + suffix
        out[map_name] = seg_list

    return out


# ---------------------------------------------------------------------------
# Async refresher
# ---------------------------------------------------------------------------

def _refresh_result(ok: bool, reason: str | None) -> dict[str, Any]:
    return {"ok": ok, "reason": reason, "refreshed_at": utc_now_iso() if ok else None}


async def async_refresh_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Refresh the cached room source for one vacuum if it uses a service source.

    RP-007 (SRC-1): returns {"ok": bool, "reason": str|None, "refreshed_at": iso|None}
    so callers can tell the five exits apart instead of every path returning None:

      ok=True,  reason "not_service_source"       - nothing to refresh (always-live)
      ok=False, reason "no_maps_service"          - misdeclared adapter
      ok=False, reason "entity_unavailable"       - device offline/asleep
      ok=False, reason "service_call_failed"      - upstream call raised
      ok=False, reason "empty_response_kept_cache"- flattened to nothing; cache kept
      ok=True,  reason None                       - refreshed and committed

    (SRC-4) Concurrent callers coalesce onto one in-flight refresh, and a commit
    generation guarantees a slow stale response never replaces a newer commit.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    discovery = config.get("discovery") or {}
    if discovery.get("source") != SOURCE_SERVICE_RESPONSE:
        return _refresh_result(True, "not_service_source")

    existing = _INFLIGHT.get(vacuum_entity_id)
    if existing is not None and not existing.done():
        return await asyncio.shield(existing)

    task = hass.loop.create_task(
        _do_refresh_room_source(hass, vacuum_entity_id, config, discovery)
    )
    _INFLIGHT[vacuum_entity_id] = task
    try:
        return await asyncio.shield(task)
    finally:
        if _INFLIGHT.get(vacuum_entity_id) is task:
            _INFLIGHT.pop(vacuum_entity_id, None)


async def _do_refresh_room_source(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    config: dict[str, Any],
    discovery: dict[str, Any],
) -> dict[str, Any]:
    maps_service = discovery.get("maps_service") or {}
    service_domain = maps_service.get("domain")
    service_name = maps_service.get("service")
    if not service_domain or not service_name:
        _LOGGER.debug(
            "room_source: service_response source for %s declares no maps_service; skipping",
            vacuum_entity_id,
        )
        return _refresh_result(False, "no_maps_service")

    # A response-returning entity service raises "did not match any entities" when
    # the target entity is unavailable (e.g. right after a restart, before the
    # brand integration finishes loading, or a Roborock asleep long enough that
    # the integration dropped its entities). Skip cleanly; discovery reads the
    # cached source and dispatch's freshness gate decides whether that is enough.
    state = hass.states.get(vacuum_entity_id)
    if state is not None and state.state in ("unavailable", "unknown"):
        _LOGGER.debug(
            "room_source: %s is %s; skipping %s.%s refresh (using cached source)",
            vacuum_entity_id, state.state, service_domain, service_name,
        )
        return _refresh_result(False, "entity_unavailable")

    generation = _GENERATION.get(vacuum_entity_id, 0)
    try:
        response = await hass.services.async_call(
            service_domain,
            service_name,
            {"entity_id": vacuum_entity_id},
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # pragma: no cover - upstream service errors are best-effort
        _LOGGER.warning(
            "room_source: %s.%s failed for %s (%s); using cached source",
            service_domain, service_name, vacuum_entity_id, err,
        )
        return _refresh_result(False, "service_call_failed")

    per_map = flatten_maps_response(
        response,
        discovery=discovery,
        vacuum_entity_id=vacuum_entity_id,
        active_map_id=_active_map_id_from_config(hass, config, vacuum_entity_id),
    )
    # RP-006 (SRC-2): a response that flattens to NOTHING must not replace a
    # previously-good cache - a transient upstream glitch would otherwise blank
    # the room source for every consumer until the next successful refresh.
    if not per_map and get_cached_room_source(hass, vacuum_entity_id):
        _LOGGER.warning(
            "room_source: refresh for %s returned no maps; keeping the previous "
            "cached source",
            vacuum_entity_id,
        )
        return _refresh_result(False, "empty_response_kept_cache")
    # (SRC-4) commit only if no newer refresh committed while this one awaited.
    if _GENERATION.get(vacuum_entity_id, 0) != generation:
        _LOGGER.debug(
            "room_source: stale refresh response for %s discarded (a newer refresh "
            "already committed)",
            vacuum_entity_id,
        )
        return _refresh_result(True, "superseded_by_newer_refresh")
    _GENERATION[vacuum_entity_id] = generation + 1
    set_cached_room_source(hass, vacuum_entity_id, per_map)
    _LOGGER.debug(
        "room_source: refreshed %s - %d map(s): %s",
        vacuum_entity_id,
        len(per_map),
        {name: len(rooms) for name, rooms in per_map.items()},
    )
    return _refresh_result(True, None)
