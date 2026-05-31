"""Tests for small platform files: binary_sensor, repairs, room_entities,
_frontend_url. Mock-source entity/flow tests.

Coverage targets
----------------
[BIN-1] ActiveRunHasErrorBinarySensor.is_on from latch error_count.
[BIN-2] ActiveRunHasErrorBinarySensor attributes (latch present / absent).
[REP-1] async_create_fix_flow returns the redirect flow.
[REP-2] flow confirm step shows a form, then creates an entry on submit.
[RE-1]  EufyVacuumRoomEntity._get_room_data reads the managed room.
[RE-2]  available reflects room presence.
[RE-3]  extra_state_attributes surfaces grants_access_to.
[RE-4]  _async_update_room: profile_name path applies a room profile.
[RE-5]  _async_update_room: managed fields path calls update_room_fields.
[RE-6]  _async_update_room: generic field path rebuilds summary + notifies.
[RE-7]  available logs on the present→absent transition.
[REP-3] flow init step routes to confirm (shows a form).
[FU-1]  panel_js_url returns the base url with a cache-busting query.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.binary_sensor import ActiveRunHasErrorBinarySensor
from custom_components.eufy_vacuum.repairs import (
    EufyVacuumSetupRedirectFlow,
    async_create_fix_flow,
)
from custom_components.eufy_vacuum.room_entities import EufyVacuumRoomEntity
from custom_components.eufy_vacuum._frontend_url import _BASE_URL, panel_js_url


_VAC = "vacuum.alfred"
_MAP = "6"


# ---------------------------------------------------------------------------
# binary_sensor
# ---------------------------------------------------------------------------

def _bin(latch):
    t = MagicMock()
    t.get_active_run_latch.return_value = latch
    t.add_update_listener.return_value = lambda: None
    return ActiveRunHasErrorBinarySensor(tracker=t, vacuum_entity_id=_VAC)


@pytest.mark.parametrize("latch,expected", [
    (None, False), ({}, False), ({"error_count": 0}, False), ({"error_count": 2}, True)])
def test_bin_is_on(latch, expected):
    """[BIN-1]"""
    assert _bin(latch).is_on is expected


def test_bin_attrs():
    """[BIN-2]"""
    present = _bin({"error_count": 1, "current_message": "Stuck", "recovered": True})
    attrs = present.extra_state_attributes
    assert attrs["error_count"] == 1 and attrs["current_message"] == "Stuck"
    absent = _bin(None).extra_state_attributes
    assert absent["error_count"] == 0 and absent["current_message"] is None


# ---------------------------------------------------------------------------
# repairs
# ---------------------------------------------------------------------------

async def test_create_fix_flow(hass):
    """[REP-1]"""
    flow = await async_create_fix_flow(hass, "stale_setup_issue", None)
    assert isinstance(flow, EufyVacuumSetupRedirectFlow)


async def test_repair_flow_steps():
    """[REP-2]"""
    flow = EufyVacuumSetupRedirectFlow(issue_id="x")
    form = await flow.async_step_confirm(None)
    assert form["type"] == "form" and form["step_id"] == "confirm"
    created = await flow.async_step_confirm({})
    assert created["type"] == "create_entry"


async def test_repair_flow_init():
    """[REP-3] init routes straight to the confirm form."""
    flow = EufyVacuumSetupRedirectFlow(issue_id="x")
    result = await flow.async_step_init()
    assert result["type"] == "form" and result["step_id"] == "confirm"


# ---------------------------------------------------------------------------
# room_entities
# ---------------------------------------------------------------------------

def _room_entity(*, rooms=None, room_id=3):
    rooms = rooms if rooms is not None else {
        "3": {"name": "Kitchen", "slug": "kitchen", "grants_access_to": [4]}}
    mgr = MagicMock()
    mgr.data = {"maps": {_VAC: {_MAP: {"rooms": rooms}}}}
    mgr.async_save = AsyncMock()
    mgr.apply_room_profile = MagicMock()
    mgr.update_room_fields = MagicMock()
    mgr.get_effective_room_details.return_value = {"clean_mode": "vacuum"}
    hass = MagicMock()
    hass.data = {DOMAIN: {"runtime": mgr}}
    ent = EufyVacuumRoomEntity(
        coordinator_key="k", vacuum_entity_id=_VAC, map_id=_MAP, room_id=room_id,
        room_data={"name": "Kitchen", "slug": "kitchen"}, unique_suffix="test")
    ent.hass = hass
    ent.async_write_ha_state = MagicMock()
    return ent, mgr


def test_room_get_data():
    """[RE-1]"""
    ent, _ = _room_entity()
    assert ent._get_room_data()["name"] == "Kitchen"


def test_room_available():
    """[RE-2]"""
    assert _room_entity()[0].available is True
    assert _room_entity(rooms={}, room_id=99)[0].available is False


def test_room_attrs():
    """[RE-3]"""
    ent, _ = _room_entity()
    attrs = ent.extra_state_attributes
    assert attrs["grants_access_to"] == ["4"]


async def test_room_update_profile():
    """[RE-4]"""
    ent, mgr = _room_entity()
    await ent._async_update_room({"profile_name": "deep_clean"})
    mgr.apply_room_profile.assert_called_once()
    mgr.async_save.assert_awaited_once()
    ent.async_write_ha_state.assert_called_once()


async def test_room_update_fields():
    """[RE-5]"""
    ent, mgr = _room_entity()
    await ent._async_update_room({"enabled": False, "fan_speed": "max"})
    mgr.update_room_fields.assert_called_once()
    mgr.async_save.assert_awaited_once()


async def test_room_update_generic():
    """[RE-6] a non-managed field falls through to the generic merge + summary path."""
    ent, mgr = _room_entity()
    mgr._refresh_room_derived_state = MagicMock()
    mgr._notify_rooms_updated = MagicMock()
    await ent._async_update_room({"custom_note": "x"})
    assert mgr.data["maps"][_VAC][_MAP]["rooms"]["3"]["custom_note"] == "x"
    assert "summary" in mgr.data["maps"][_VAC][_MAP]
    mgr._refresh_room_derived_state.assert_called_once()
    mgr._notify_rooms_updated.assert_called_once()
    mgr.async_save.assert_awaited_once()


def test_room_availability_transition():
    """[RE-7]"""
    ent, mgr = _room_entity()
    assert ent.available is True            # present
    mgr.data["maps"][_VAC][_MAP]["rooms"] = {}
    assert ent.available is False           # transition present→absent (logs)


# ---------------------------------------------------------------------------
# _frontend_url
# ---------------------------------------------------------------------------

def test_panel_js_url():
    """[FU-1]"""
    url = panel_js_url()
    assert url.startswith(_BASE_URL + "?v=")
    version = url.rsplit("=", 1)[1]
    assert version.isdigit()


def test_panel_js_url_missing_bundle(monkeypatch):
    """[FU-1] a missing bundle file falls back to v=0."""
    import custom_components.eufy_vacuum._frontend_url as fu

    def _raise(_path):
        raise OSError("missing")

    monkeypatch.setattr(fu.os.path, "getmtime", _raise)
    assert fu.panel_js_url() == _BASE_URL + "?v=0"
