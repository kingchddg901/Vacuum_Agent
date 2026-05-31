"""Phase 4 integration tests — queue service handlers.

Coverage targets
----------------
[SQ-1]  build_queue service populates manager queue data.
[SQ-2]  get_queue_state service returns empty default for unknown vacuum.
[SQ-3]  get_queue_state service returns populated data after build_queue.
[SQ-4]  get_payload_state service returns a response dict.
[SQ-5]  build_room_payload service completes without error.
[SQ-6]  clear_queue service empties the queue.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [SQ-1] build_queue
# ---------------------------------------------------------------------------

async def test_build_queue_service_populates_queue(hass, manager_with_services):
    """[SQ-1] Calling build_queue service populates manager.data['queue']."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN,
        "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    assert _VAC in manager_with_services.data.get("queue", {})
    assert _MAP in manager_with_services.data["queue"][_VAC]


async def test_build_queue_service_sets_room_ids(hass, manager_with_services):
    """[SQ-1] build_queue service wires queue_room_ids into runtime."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    await hass.services.async_call(
        DOMAIN,
        "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    runtime = manager_with_services.ensure_runtime(_VAC)
    assert len(runtime.queue_room_ids) == 2


# ---------------------------------------------------------------------------
# [SQ-2] — [SQ-3] get_queue_state
# ---------------------------------------------------------------------------

async def test_get_queue_state_service_unknown_vacuum_default(hass, manager_with_services):
    """[SQ-2] get_queue_state returns empty default for an unseen vacuum."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_queue_state",
        {"vacuum_entity_id": _VAC, "map_id": "99"},
        blocking=True,
        return_response=True,
    )
    assert result["room_count"] == 0
    assert result["queue_room_ids"] == []


async def test_get_queue_state_service_after_build_has_rooms(hass, manager_with_services):
    """[SQ-3] get_queue_state returns populated state after build_queue service."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    result = await hass.services.async_call(
        DOMAIN, "get_queue_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result["room_count"] == 3
    assert len(result["queue_room_ids"]) == 3


async def test_get_queue_state_service_echoes_ids(hass, manager_with_services):
    """[SQ-2] Response includes the vacuum_entity_id and map_id passed in."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN, "get_queue_state",
        {"vacuum_entity_id": _VAC, "map_id": "5"},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["map_id"] == "5"


# ---------------------------------------------------------------------------
# [SQ-4] get_payload_state
# ---------------------------------------------------------------------------

async def test_get_payload_state_service_returns_dict(hass, manager_with_services):
    """[SQ-4] get_payload_state returns a response dict for any vacuum/map."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN, "get_payload_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result


# ---------------------------------------------------------------------------
# [SQ-5] build_room_payload
# ---------------------------------------------------------------------------

async def test_build_room_payload_service_no_error(hass, manager_with_services):
    """[SQ-5] build_room_payload completes without raising."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "build_room_payload",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )


# ---------------------------------------------------------------------------
# [SQ-6] clear_queue
# ---------------------------------------------------------------------------

async def test_clear_queue_service_empties_queue(hass, manager_with_services):
    """[SQ-6] clear_queue service resets queue_room_ids to empty."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "clear_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    state = manager_with_services.get_queue_state(
        vacuum_entity_id=_VAC, map_id=_MAP
    )
    assert state["queue_room_ids"] == []
    assert state["room_count"] == 0
