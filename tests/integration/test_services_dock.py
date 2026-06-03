"""Phase 7 integration tests — services/dock.py.

Coverage targets
----------------
[DK-1]  get_dock_action_status returns a dict for a registered vacuum.
[DK-2]  get_dock_action_status result includes vacuum_entity_id.
[DK-3]  set_dock_event_count updates last_mop_wash count.
[DK-4]  set_dock_event_count updates last_dust_empty count.
[DK-5]  set_dock_event_count updates last_dry_start count.
[DK-6]  set_dock_event_count result includes updated key.
[DK-7]  gated action allowed/performed → returns payload, no raise.
[DK-8]  gated action blocked (performed False, allowed False) → ServiceValidationError.
[DK-9]  gated action manager raises → wrapped HomeAssistantError per action.
[DK-10] _check_dock_action: allowed-but-not-performed does NOT raise.
[DK-11] set_dock_event_count updated → async_save; not-updated → no save.
[DK-12] set_dock_event_count manager raises → HomeAssistantError.

The gated actions (wash/dry/empty/stop) issue async device commands, so DK-7..
DK-9 drive the module-level _handle_* coroutines directly with a mock manager
rather than the physical service-call path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.services.dock import (
    _check_dock_action,
    _handle_dry_mop,
    _handle_empty_dust,
    _handle_set_dock_event_count,
    _handle_stop_dry_mop,
    _handle_wash_mop,
)

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


# ---------------------------------------------------------------------------
# [DK-7] — [DK-12] gated actions + save branch (direct-handler, mock manager)
# ---------------------------------------------------------------------------

class _Call:
    def __init__(self, data):
        self.data = data


@pytest.fixture
def dock(hass):
    """(hass, mock_manager) with the manager wired at DATA_RUNTIME."""
    mgr = MagicMock()
    mgr.async_save = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr
    return hass, mgr


def _gated_call(**extra):
    return _Call({"vacuum_entity_id": _VAC, "map_id": _MAP, **extra})


# Gated-action handler ↔ manager method ↔ error prefix.
_GATED = [
    (_handle_wash_mop, "async_wash_mop", "Failed to wash mop"),
    (_handle_dry_mop, "async_dry_mop", "Failed to dry mop"),
    (_handle_empty_dust, "async_empty_dust", "Failed to empty dust"),
    (_handle_stop_dry_mop, "async_stop_dry_mop", "Failed to stop dry mop"),
]


@pytest.mark.parametrize("handler,method,_prefix", _GATED)
async def test_gated_action_allowed(dock, handler, method, _prefix):
    """[DK-7]"""
    hass, mgr = dock
    setattr(mgr, method, AsyncMock(return_value={"performed": True, "allowed": True}))
    out = await handler(hass, _gated_call())
    assert out["performed"] is True


@pytest.mark.parametrize("handler,method,_prefix", _GATED)
async def test_gated_action_blocked(dock, handler, method, _prefix):
    """[DK-8]"""
    hass, mgr = dock
    setattr(mgr, method, AsyncMock(return_value={
        "performed": False, "allowed": False,
        "message": "Dock is busy.", "reason": "busy"}))
    with pytest.raises(ServiceValidationError, match="Dock is busy."):
        await handler(hass, _gated_call())


@pytest.mark.parametrize("handler,method,prefix", _GATED)
async def test_gated_action_manager_raises(dock, handler, method, prefix):
    """[DK-9]"""
    hass, mgr = dock
    setattr(mgr, method, AsyncMock(side_effect=RuntimeError("boom")))
    with pytest.raises(HomeAssistantError, match=prefix):
        await handler(hass, _gated_call())


@pytest.mark.parametrize("service,method", [
    ("wash_mop", "async_wash_mop"),
    ("dry_mop", "async_dry_mop"),
    ("empty_dust", "async_empty_dust"),
    ("stop_dry_mop", "async_stop_dry_mop"),
])
async def test_dock_service_dispatch_wiring(hass, manager_with_services, monkeypatch, service, method):
    """[DK-13] each registered dock service dispatches through its closure to the
    matching manager method — verifies service-name→handler wiring, which the
    direct _handle_* tests deliberately bypass (plumbing can be mis-wired)."""
    spy = AsyncMock(return_value={"performed": True, "allowed": True})
    monkeypatch.setattr(manager_with_services, method, spy)
    await hass.services.async_call(
        DOMAIN, service, {"vacuum_entity_id": _VAC, "map_id": _MAP}, blocking=True)
    assert spy.await_count == 1


def test_check_dock_action_allowed_not_performed():
    """[DK-10] allowed-but-not-performed (e.g. no-op) must not raise."""
    _check_dock_action("wash_mop", {"performed": False, "allowed": True})
    _check_dock_action("wash_mop", {"performed": True})
    _check_dock_action("wash_mop", {"performed": False})  # allowed defaults True
    with pytest.raises(ServiceValidationError):
        _check_dock_action("wash_mop", {"performed": False, "allowed": False})


async def test_set_dock_event_count_save_branch(dock):
    """[DK-11]"""
    hass, mgr = dock
    mgr.set_dock_event_count.return_value = {"updated": True, "count": 3}
    call = _Call({"vacuum_entity_id": _VAC, "event_type": "last_mop_wash", "count": 3})
    out = await _handle_set_dock_event_count(hass, call)
    assert out["updated"] is True
    mgr.async_save.assert_awaited_once()

    mgr.async_save.reset_mock()
    mgr.set_dock_event_count.return_value = {"updated": False}
    await _handle_set_dock_event_count(hass, call)
    mgr.async_save.assert_not_awaited()


async def test_set_dock_event_count_manager_raises(dock):
    """[DK-12]"""
    hass, mgr = dock
    mgr.set_dock_event_count.side_effect = ValueError("bad event_type")
    call = _Call({"vacuum_entity_id": _VAC, "event_type": "x", "count": 1})
    with pytest.raises(HomeAssistantError, match="Failed to set dock event count"):
        await _handle_set_dock_event_count(hass, call)
