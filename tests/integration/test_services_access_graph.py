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
