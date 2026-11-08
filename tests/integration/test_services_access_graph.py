"""Phase 9 integration tests — services/access_graph.py.

Coverage targets
----------------
[AG-1]  get_room_access_editor returns a dict for a seeded room.
[AG-2]  get_room_access_editor result includes vacuum_entity_id.
[AG-3]  get_room_access_editor for an unknown room_id returns a result (no raise).
[AG-4]  get_access_graph_health returns a dict for a seeded map.
[AG-5]  get_access_graph_health result includes vacuum_entity_id.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [AG-1] / [AG-2] / [AG-3] get_room_access_editor
# ---------------------------------------------------------------------------

async def test_get_room_access_editor_returns_dict(hass, manager_with_services):
    """[AG-1] get_room_access_editor returns a dict for a seeded room."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_room_access_editor",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_room_access_editor_includes_vacuum_entity_id(hass, manager_with_services):
    """[AG-2] get_room_access_editor result includes vacuum_entity_id."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_room_access_editor",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1},
        blocking=True,
        return_response=True,
    )
    assert result.get("vacuum_entity_id") == _VAC


async def test_get_room_access_editor_unknown_room_does_not_raise(hass, manager_with_services):
    """[AG-3] get_room_access_editor handles an unknown room_id without raising."""
    setup_map(manager_with_services, _VAC, _MAP, count=1)
    result = await hass.services.async_call(
        DOMAIN,
        "get_room_access_editor",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 999},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [AG-4] / [AG-5] get_access_graph_health
# ---------------------------------------------------------------------------

async def test_get_access_graph_health_returns_dict(hass, manager_with_services):
    """[AG-4] get_access_graph_health returns a dict for a seeded map."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_access_graph_health",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_access_graph_health_includes_vacuum_entity_id(hass, manager_with_services):
    """[AG-5] get_access_graph_health result includes vacuum_entity_id."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_access_graph_health",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result.get("vacuum_entity_id") == _VAC


# ---------------------------------------------------------------------------
# [AG-6] / [AG-7] set_room_access_graph — through the BUS
#
# This is the card's dock-release Save: `src/bindings/room-access.js` routes a Save
# that releases the dock to `clearRoomAccessGraph`, which calls this service. It is
# one of only two exits from the `partial` access-graph state that refuses every run,
# so a handler returning nothing usable leaves the user stuck with no error shown —
# the card's own check (`result?.ok === false || result?.updated === false || ...`)
# passes on `undefined`.
#
# Everything below the bus is covered at the manager level by
# `test_set_room_access_graph.py`. What had no test is the thread: that the service
# exists, is registered with `supports_response`, that the closure AWAITS the handler,
# and that `resolved_call_data` is what fills the map.
# ---------------------------------------------------------------------------

async def test_ag6_omitting_map_id_resolves_the_active_map(hass, manager_with_services):
    """[AG-6] `map_id` omitted — `resolved_call_data` fills it from the active map.

    `map_id` is a REQUIRED kwarg on `manager.set_room_access_graph`, while every
    service taking one declares it optional because services are adapter-agnostic. So
    the thing under test is the thread: the card omits it, `resolved_call_data` reads
    the adapter's declared `entities.active_map`, and the write lands on the map the
    vacuum is actually on.

    ⚠ TWO MAPS ARE SEEDED SO THIS CAN DISCRIMINATE, and the preconditions are why.
    `tests._factories.set_room_field` defaults to `map_id="1"`, so an arrange that
    silently used the default would resolve cleanly against a seeded map "1" and every
    assertion would pass while proving nothing about resolution. Here the ACTIVE map is
    "7" and map "1" is a decoy: a write landing on the default fails both the
    `result["map_id"]` assertion and the untouched-decoy assertion.

    `""` is the same input — `cv.string` accepts it and `resolved_call_data` treats a
    blank as absent — and blank is what the UI's text selector sends when cleared.

    RED: replace `resolved_call_data(hass, call)` with `dict(call.data)` and the
    manager's required `map_id` is missing, so the call raises TypeError. Drop the
    `return` and hand back `None` and `result["ok"]` raises — the production shape that
    matters, because the card reads `undefined` as success.
    """
    setup_map(manager_with_services, _VAC, "1", count=4)      # the decoy
    setup_map(manager_with_services, _VAC, "7", count=4)      # the active one
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_map"},
    })
    hass.states.async_set("sensor.alfred_map", "7")

    maps = manager_with_services.data["maps"][_VAC]
    assert {"1", "7"} <= set(maps), "precondition: both seeded, so a default write shows"
    assert not maps["1"]["rooms"]["1"].get("grants_access_to"), "decoy starts clean"

    result = await hass.services.async_call(
        DOMAIN,
        "set_room_access_graph",
        {   # map_id DELIBERATELY OMITTED
            "vacuum_entity_id": _VAC,
            "dock_room_id": 1,
            "edges": [{"from": 1, "to": 2}, {"from": 2, "to": 3}],
        },
        blocking=True,
        return_response=True,
    )

    assert isinstance(result, dict), "the closure must await, not return a coroutine"
    assert result["ok"] is True, result
    assert result["map_id"] == "7", "the ACTIVE map, resolved -- not the default"
    assert maps["7"]["rooms"]["1"].get("grants_access_to"), "the graph landed on map 7"
    assert not maps["1"]["rooms"]["1"].get("grants_access_to"), (
        "and the decoy is untouched -- what a default-map write would break"
    )


async def test_ag7_an_invalid_graph_is_refused_through_the_bus(hass, manager_with_services):
    """[AG-7] The refusal exit, so both exits are proven to survive the closure.

    [AG-6] proves a successful response reaches the card; a handler could still mangle
    the failure path, which is the one the card branches on most. A `dock_room_id` the
    map does not have must come back as a dict with `ok: False` — not as a raise, and
    not as `None`.

    RED: register the handler without `supports_response=True` and the
    `return_response=True` call fails; drop the `await` and `result["ok"]` raises on a
    coroutine.
    """
    setup_map(manager_with_services, _VAC, _MAP, count=2)

    result = await hass.services.async_call(
        DOMAIN,
        "set_room_access_graph",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "dock_room_id": 999},
        blocking=True,
        return_response=True,
    )

    assert isinstance(result, dict)
    assert result["ok"] is False, result
    assert result.get("error"), "the refusal must name itself for the card to show it"
    assert not manager_with_services.data["maps"][_VAC][_MAP]["rooms"]["1"].get(
        "grants_access_to"
    ), "a refused graph writes nothing"
