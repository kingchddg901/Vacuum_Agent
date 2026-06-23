"""Unit tests for rooms/source_refresh.py — the service-call room source.

Roborock's rooms live ONLY in the get_maps service RESPONSE (a
``{segment_id_str: name}`` mapping per map), never an entity attribute. These
cover the flatten shim (pure), the cache, the async refresher, and the bridge
into the sync discovery path.

Coverage targets
----------------
[SR-1]  flatten turns {id:name} rooms into list-of-dicts keyed by map name.
[SR-2]  flatten unwraps a per-entity response wrapper.
[SR-3]  flatten accepts a bare maps list + already-list rooms.
[SR-4]  flatten skips malformed map entries and names nameless maps.
[SR-5]  cache get/set round-trips; empty -> {}.
[SR-6]  async_refresh calls the service + caches for service_response sources.
[SR-7]  async_refresh is a no-op for attribute sources / missing maps_service.
[SR-8]  the cached source flows through discover_rooms_for_vacuum (int + slug).
[SR-9]  an unavailable vacuum entity -> refresh skips the service cleanly (no
        "did not match any entities" throw); cache untouched.
"""

from __future__ import annotations

import pytest

from homeassistant.core import SupportsResponse

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.rooms.room_discovery import (
    discover_rooms_for_vacuum,
)
from custom_components.eufy_vacuum.rooms.source_refresh import (
    async_refresh_room_source,
    flatten_maps_response,
    get_cached_room_source,
    set_cached_room_source,
)


_VAC = "vacuum.ivy"

_DISCOVERY = {
    "source": "service_response",
    "maps_service": {"domain": "roborock", "service": "get_maps"},
    "maps_rooms_key": "rooms",
    "map_name_key": "name",
    "room_id_key": "segment_id",
    "room_name_key": "name",
}

# The real captured get_maps shape (rooms is a {segment_id_str: name} mapping,
# names are user-set incl. spaces + "&").
_MAPS = [
    {
        "flag": 0,
        "name": "Main floor",
        "rooms": {"16": "KITCHEN", "17": "Dining Room", "20": "Heidi & Chris"},
    }
]


def _service_response_adapter(vac=_VAC):
    register_adapter_config(vac, {
        "adapter_id": "rb",
        "source": "code",
        "entities": {"active_map": "select.ivy_selected_map"},
        "discovery": dict(_DISCOVERY),
    })


# --- flatten shim (pure) ----------------------------------------------------


def test_flatten_mapping_to_list():
    """[SR-1]"""
    out = flatten_maps_response({"maps": _MAPS}, discovery=_DISCOVERY)
    assert set(out) == {"Main floor"}
    rooms = out["Main floor"]
    assert {r["segment_id"] for r in rooms} == {"16", "17", "20"}
    by_id = {r["segment_id"]: r["name"] for r in rooms}
    assert by_id["20"] == "Heidi & Chris"


def test_flatten_unwraps_entity_wrapper():
    """[SR-2] response keyed by the target entity id."""
    out = flatten_maps_response(
        {_VAC: {"maps": _MAPS}},
        discovery=_DISCOVERY,
        vacuum_entity_id=_VAC,
    )
    assert "Main floor" in out


def test_flatten_bare_list_and_list_rooms():
    """[SR-3] a bare maps list, and a map whose rooms are already list-of-dicts."""
    bare = flatten_maps_response(_MAPS, discovery=_DISCOVERY)
    assert "Main floor" in bare

    already_list = flatten_maps_response(
        {"maps": [{"name": "Up", "rooms": [{"segment_id": "5", "name": "Loft"}]}]},
        discovery=_DISCOVERY,
    )
    assert already_list["Up"] == [{"segment_id": "5", "name": "Loft"}]


def test_flatten_skips_bad_entries_and_names_unnamed_maps():
    """[SR-4] non-dict entries are skipped; nameless maps get a fallback key."""
    out = flatten_maps_response(
        {"maps": ["junk", {"rooms": {"1": "X"}}, {"name": "Real", "rooms": {"2": "Y"}}]},
        discovery=_DISCOVERY,
    )
    assert set(out) == {"Map 1", "Real"}
    assert out["Map 1"] == [{"segment_id": "1", "name": "X"}]


def test_flatten_uses_active_map_for_single_unnamed_map():
    """[SR-4] Roborock can return name="" while the active map select says Map 0."""
    out = flatten_maps_response(
        {_VAC: {"maps": [{"flag": 0, "name": "", "rooms": {"16": "Спальня"}}]}},
        discovery=_DISCOVERY,
        vacuum_entity_id=_VAC,
        active_map_id="Map 0",
    )
    assert set(out) == {"Map 0"}
    assert out["Map 0"] == [{"segment_id": "16", "name": "Спальня"}]


def test_flatten_unrecognized_response_empty():
    """[SR-4] a response with no maps list -> empty dict."""
    assert flatten_maps_response({"nope": 1}, discovery=_DISCOVERY) == {}
    assert flatten_maps_response(None, discovery=_DISCOVERY) == {}


# --- cache ------------------------------------------------------------------


def test_cache_round_trip(hass):
    """[SR-5]"""
    assert get_cached_room_source(hass, _VAC) == {}
    set_cached_room_source(hass, _VAC, {"Main floor": [{"segment_id": "16", "name": "KITCHEN"}]})
    assert get_cached_room_source(hass, _VAC)["Main floor"][0]["name"] == "KITCHEN"


# --- async refresher --------------------------------------------------------


async def test_async_refresh_caches(hass):
    """[SR-6] service_response source -> service called, result flattened + cached."""
    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        return {"maps": _MAPS}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )

    await async_refresh_room_source(hass, _VAC)
    cache = get_cached_room_source(hass, _VAC)
    assert {r["segment_id"] for r in cache["Main floor"]} == {"16", "17", "20"}


async def test_async_refresh_caches_unnamed_map_by_active_select(hass):
    """[SR-6] unnamed Roborock map is cached under the active-map select value."""
    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        return {_VAC: {"maps": [{"flag": 0, "name": "", "rooms": {"16": "KITCHEN"}}]}}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("select.ivy_selected_map", "Map 0")

    await async_refresh_room_source(hass, _VAC)

    cache = get_cached_room_source(hass, _VAC)
    assert list(cache) == ["Map 0"]
    assert cache["Map 0"] == [{"segment_id": "16", "name": "KITCHEN"}]


async def test_async_refresh_skips_unavailable_entity(hass):
    """[SR-9] an unavailable vacuum entity -> skip the service call cleanly (the
    transient that throws 'did not match any entities' post-restart); no cache."""
    clear_registry()
    _service_response_adapter()

    called: list = []

    async def _get_maps(call):
        called.append(call)
        return {"maps": _MAPS}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )

    hass.states.async_set(_VAC, "unavailable")
    await async_refresh_room_source(hass, _VAC)
    assert called == []  # service not called for an unavailable entity
    assert get_cached_room_source(hass, _VAC) == {}


async def test_async_refresh_noop_for_attribute_source(hass):
    """[SR-7] attribute sources have nothing to refresh."""
    clear_registry()
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "discovery": {"source": "entity_attribute", "room_list_attribute": "segments"},
    })
    await async_refresh_room_source(hass, _VAC)
    assert get_cached_room_source(hass, _VAC) == {}


async def test_async_refresh_noop_missing_maps_service(hass):
    """[SR-7] service_response with no maps_service declared -> no-op (no crash)."""
    clear_registry()
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "discovery": {"source": "service_response"},
    })
    await async_refresh_room_source(hass, _VAC)
    assert get_cached_room_source(hass, _VAC) == {}


# --- bridge into discovery --------------------------------------------------


def test_cached_source_flows_into_discovery(hass):
    """[SR-8] discover_rooms_for_vacuum reads the cache for service sources and
    applies the normal int-coerce + slug normalization downstream."""
    clear_registry()
    _service_response_adapter()
    hass.states.async_set("select.ivy_selected_map", "Main floor")
    set_cached_room_source(hass, _VAC, flatten_maps_response({"maps": _MAPS}, discovery=_DISCOVERY))

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)

    by_id = {r["room_id"]: r for r in rooms}
    assert set(by_id) == {16, 17, 20}  # str ids coerced to int
    assert by_id[16]["slug"] == "kitchen"
    assert by_id[20]["slug"] == "heidi_and_chris"  # "&" -> "and", space -> "_"
    assert by_id[16]["map_id"] == "Main floor"


def test_single_map_fallback_when_active_map_unknown(hass):
    """[SR-8] a single cached map is used even if active_map didn't resolve to
    its key (e.g. active_map unknown at refresh time)."""
    clear_registry()
    _service_response_adapter()
    # active_map sentinel -> get_active_map_id returns None -> resolved "unknown".
    hass.states.async_set("select.ivy_selected_map", "unknown")
    set_cached_room_source(hass, _VAC, flatten_maps_response({"maps": _MAPS}, discovery=_DISCOVERY))

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert {r["room_id"] for r in rooms} == {16, 17, 20}
