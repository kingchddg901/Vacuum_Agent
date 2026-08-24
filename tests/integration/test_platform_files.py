"""Tests for small platform files: binary_sensor, room_entities,
_frontend_url. Mock-source entity/flow tests.

Coverage targets
----------------
[BIN-1] ActiveRunHasErrorBinarySensor.is_on from latch error_count.
[BIN-2] ActiveRunHasErrorBinarySensor attributes (latch present / absent).
[RE-1]  EufyVacuumRoomEntity._get_room_data reads the managed room.
[RE-2]  available reflects room presence.
[RE-3]  extra_state_attributes surfaces grants_access_to.
[RE-4]  _async_update_room: profile_name path applies a room profile.
[RE-5]  _async_update_room: managed fields path calls update_room_fields.
[RE-6]  _async_update_room: generic field path rebuilds summary + notifies.
[RE-7]  available logs on the present→absent transition.
[RE-8]  EP-7: _async_update_room applies a mixed managed+unmanaged batch via
        BOTH update_room_fields and the generic merge, instead of the managed
        branch's old unconditional early return silently dropping the rest.
[RE-9]  C2: an apply_room_profile that touched NO room is refused, not saved.
        The vanished-room payload is SUCCESS-SHAPED (no `ok`, no `error`), so
        this is the half that a fix written against `ok` leaves open.
[RE-10] C2: an update_room_fields refusal (room_not_found) raises instead of
        saving + writing a state the store never took.
[RE-11] C9: the generic merge finalizes before it stores, so a floor_type
        change through that path still gets the carpet/mop protection.
[FU-1]  panel_js_url returns the base url with a cache-busting query.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ServiceValidationError

from tests._factories import spec_manager
from tests.brand_catalogs import SYNTHETIC_BLOCK

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.binary_sensor import ActiveRunHasErrorBinarySensor
from custom_components.eufy_vacuum.core.manager import EufyVacuumManager
from custom_components.eufy_vacuum.profiles.manager import ProfileManager
from custom_components.eufy_vacuum.profiles.room_profiles import (
    no_water_value,
    resolve_profile_catalog,
)
from custom_components.eufy_vacuum.room_entities import EufyVacuumRoomEntity
from custom_components.eufy_vacuum._frontend_url import _BASE_URL, panel_js_url


_VAC = "vacuum.alfred"
_MAP = "6"

#: The synthetic brand's catalog — the one the `synthetic_adapter` fixture
#: registers for _VAC. Core room protection is asserted against ITS declared
#: no-water word, never a literal, or the test pins one brand's vocabulary.
_CATALOG = resolve_profile_catalog(SYNTHETIC_BLOCK)


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
# room_entities
# ---------------------------------------------------------------------------

def _room_entity(*, rooms=None, room_id=3):
    rooms = rooms if rooms is not None else {
        "3": {"name": "Kitchen", "slug": "kitchen", "grants_access_to": [4]}}
    mgr = spec_manager()
    mgr.data = {"maps": {_VAC: {_MAP: {"rooms": rooms}}}}
    mgr.async_save = AsyncMock()
    # C2: the entity READS both writers' payloads now, so a bare MagicMock would
    # answer every key truthily — the mock agreeing with its caller instead of its
    # callee. These are the real SUCCESS returns (profiles/manager.py
    # ::apply_room_profile's final return; core/manager.py::update_room_fields').
    # A test that wants a REFUSAL therefore has to say so, and RE-9/RE-10 derive
    # theirs by running the real callee rather than hand-writing one.
    mgr.apply_room_profile.return_value = {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "profile_name": "deep_clean",
        "updated_room_ids": [room_id],
        "room_count": 1,
    }
    mgr.update_room_fields.return_value = {
        "ok": True,
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "room_id": room_id,
        "updated": True,
        "profile_name": "custom",
        "room": dict(rooms.get(str(room_id), {})),
    }
    # C9: the generic merge finalizes before it stores. Wire the REAL
    # implementation behind the same shim production calls, because every
    # assertion below is about what actually lands in the store — a stubbed
    # finalizer would let the merge write anything and still pass.
    mgr._finalize_room_update.side_effect = ProfileManager(mgr)._finalize_room_update
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


@pytest.mark.usefixtures("synthetic_adapter")
async def test_room_update_mixed_managed_and_unmanaged_fields():
    """[RE-8] EP-7: a single call mixing a MANAGED field (enabled) with an
    UNMANAGED one (color) must apply the managed subset via
    update_room_fields AND still route the unmanaged field to the generic
    merge — not silently drop it via the managed branch's old unconditional
    early return."""
    ent, mgr = _room_entity()
    mgr._refresh_room_derived_state = MagicMock()
    mgr._notify_rooms_updated = MagicMock()

    await ent._async_update_room({"enabled": False, "color": "#ff0000"})

    mgr.update_room_fields.assert_called_once()
    _, kwargs = mgr.update_room_fields.call_args
    assert kwargs["enabled"] is False
    assert "color" not in kwargs  # color is not a managed_field_names key

    # The unmanaged field still reached the generic merge.
    assert mgr.data["maps"][_VAC][_MAP]["rooms"]["3"]["color"] == "#ff0000"
    mgr._refresh_room_derived_state.assert_called_once()
    mgr._notify_rooms_updated.assert_called_once()
    mgr.async_save.assert_awaited_once()
    ent.async_write_ha_state.assert_called_once()


@pytest.mark.usefixtures("synthetic_adapter")
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


@pytest.mark.usefixtures("synthetic_adapter")
async def test_re9_profile_apply_that_touched_no_room_is_refused():
    """[RE-9] C2, and specifically the half that reading `ok` would miss.

    apply_room_profile has NO `ok` key on any path. When the room was deleted
    between the state write and the button press it is simply `continue`d over,
    so the refusal comes back SUCCESS-SHAPED: updated_room_ids [], room_count 0,
    no error at all. The entity discarded that and ran async_save() +
    async_write_ha_state() anyway — the user saw the control move and the store
    never took it.

    The payload is DERIVED by running the real callee against the same empty map
    rather than hand-written, so if that shape ever changes this test changes
    with it instead of quietly asserting a fossil.
    """
    ent, mgr = _room_entity(rooms={})          # room 3 is gone
    real = ProfileManager(mgr).apply_room_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[3],
        profile_name="vacuum_quick",
    )
    # The DRIFT, pinned: there is nothing in here that says "refused".
    assert "ok" not in real and "error" not in real, real
    assert real["updated_room_ids"] == [] and real["room_count"] == 0, real

    mgr.apply_room_profile.return_value = real
    mgr.async_save.reset_mock()

    with pytest.raises(ServiceValidationError) as excinfo:
        await ent._async_update_room({"profile_name": "vacuum_quick"})

    assert "not_applied" in str(excinfo.value)
    mgr.async_save.assert_not_awaited()
    ent.async_write_ha_state.assert_not_called()


async def test_re10_managed_write_refusal_is_not_reported_as_success():
    """[RE-10] C2, the update_room_fields half.

    Only ``room_not_found`` is reachable from this call site — the entity passes
    the managed subset, and the callee's other two refusals both hang off
    grants_access_to, which never gets here. Refusal payload derived by running
    the real callee against a map the room is missing from.
    """
    ent, mgr = _room_entity(rooms={})          # room 3 is gone
    real = EufyVacuumManager.update_room_fields(
        mgr, vacuum_entity_id=_VAC, map_id=_MAP, room_id=3, enabled=False,
    )
    assert real["ok"] is False and real["error"] == "room_not_found", real

    mgr.update_room_fields.return_value = real
    mgr.async_save.reset_mock()

    with pytest.raises(ServiceValidationError) as excinfo:
        await ent._async_update_room({"enabled": False})

    assert "room_not_found" in str(excinfo.value)
    mgr.async_save.assert_not_awaited()
    ent.async_write_ha_state.assert_not_called()


@pytest.mark.usefixtures("synthetic_adapter")
async def test_re11_generic_merge_applies_carpet_protection():
    """[RE-11] C9: the generic merge must finalize before it stores.

    ``floor_type`` is a protection INPUT and is not a managed field, so it lands
    in exactly this branch. The merge used to write the merged dict straight into
    rooms[room_key], which made it the one room writer in the package that skipped
    _finalize_room_update — a room switched to carpet through this path kept its
    mop mode, its water level and its edge mopping, and the planner would then
    read a carpet room it was cleared to send out wet.

    Water is asserted against the SYNTHETIC brand's own declared no-water word,
    not a literal: "Off" is Eufy's casing and asserting it here would pin one
    brand's vocabulary into a core protection test.
    """
    mop = SYNTHETIC_BLOCK["builtins"]["vacuum_mop_quick"]
    ent, mgr = _room_entity(rooms={"3": {
        "room_id": 3, "name": "Kitchen", "floor_type": "hardwood",
        "clean_mode": mop["clean_mode"], "water_level": mop["water_level"],
        "edge_mopping": True,
    }})

    await ent._async_update_room({"floor_type": "carpet_high_pile"})

    stored = mgr.data["maps"][_VAC][_MAP]["rooms"]["3"]
    assert stored["floor_type"] == "carpet_high_pile"      # the edit landed
    assert stored["clean_mode"] == "vacuum"                # ...and was protected
    assert stored["water_level"] == no_water_value(_CATALOG)
    assert stored["edge_mopping"] is False
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
