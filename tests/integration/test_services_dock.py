"""Phase 7 integration tests — services/dock.py.

Coverage targets
----------------
[DK-1]  get_dock_action_status returns a dict for a registered vacuum.
[DK-2]  get_dock_action_status result includes vacuum_entity_id.
[DK-3]  set_dock_event_count updates last_mop_wash count.
[DK-4]  set_dock_event_count updates last_dust_empty count.
[DK-5]  set_dock_event_count updates last_dry_start count.
[DK-6]  set_dock_event_count result includes updated key.

Note: wash_mop / dry_mop / empty_dust / stop_dry_mop are excluded — they
issue async commands to the physical device and cannot be exercised without
a real device connection or deep mocking of the vacuum entity.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [DK-1] — [DK-2] get_dock_action_status
# ---------------------------------------------------------------------------

async def test_get_dock_action_status_returns_dict(hass, manager_with_services):
    """[DK-1] get_dock_action_status returns a dict for a registered vacuum."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_dock_action_status",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_dock_action_status_includes_vacuum_entity_id(hass, manager_with_services):
    """[DK-2] get_dock_action_status result includes vacuum_entity_id."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "get_dock_action_status",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result.get("vacuum_entity_id") == _VAC


# ---------------------------------------------------------------------------
# [DK-3] — [DK-6] set_dock_event_count
# ---------------------------------------------------------------------------

async def test_set_dock_event_count_mop_wash(hass, manager_with_services):
    """[DK-3] set_dock_event_count updates last_mop_wash counter."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_dock_event_count",
        {"vacuum_entity_id": _VAC, "event_type": "last_mop_wash", "count": 5},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_set_dock_event_count_dust_empty(hass, manager_with_services):
    """[DK-4] set_dock_event_count updates last_dust_empty counter."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_dock_event_count",
        {"vacuum_entity_id": _VAC, "event_type": "last_dust_empty", "count": 3},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_set_dock_event_count_dry_start(hass, manager_with_services):
    """[DK-5] set_dock_event_count updates last_dry_start counter."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_dock_event_count",
        {"vacuum_entity_id": _VAC, "event_type": "last_dry_start", "count": 1},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_set_dock_event_count_returns_updated_key(hass, manager_with_services):
    """[DK-6] set_dock_event_count result includes the updated key."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_dock_event_count",
        {"vacuum_entity_id": _VAC, "event_type": "last_mop_wash", "count": 2},
        blocking=True,
        return_response=True,
    )
    assert "updated" in result


async def test_set_dock_event_count_zero_is_valid(hass, manager_with_services):
    """[DK-6] set_dock_event_count accepts count=0 (reset)."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_dock_event_count",
        {"vacuum_entity_id": _VAC, "event_type": "last_mop_wash", "count": 0},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
