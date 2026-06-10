"""Tests for core/manager.py lifecycle + start-status surfaces.

Two thin-but-real engines the dashboard polls:

* get_lifecycle_state — folds the ErrorTracker's active-run latch into the
  user-visible lifecycle message (the error-override block).
* get_start_status — the start-protection gate that blocks a new run when a
  job is paused or onboarding is incomplete.

Driven against the real manager with a recording ErrorTracker stand-in and the
shared setup_map helper; no entity listeners or service registry required.

Coverage targets
----------------
[LS-1]  get_lifecycle_state: current_message overrides the generic message.
[LS-2]  get_lifecycle_state: blank current_message → "Run had N…; last:" derived
        from the latest error entry.
[LS-3]  get_start_status: a paused job blocks the start (reason job_paused).
[LS-4]  get_start_status: incomplete floor-type onboarding blocks (onboarding_required).
[LS-5]  get_start_status: every selected room blocked → all_selected_rooms_blocked.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum.adapters.registry import (
    register_adapter_config,
    unregister_adapter_config,
)
from custom_components.eufy_vacuum.const import (
    DATA_ERROR_TRACKER,
    DOMAIN,
    EVENT_EXTERNAL_RUN_PENDING,
)
from custom_components.eufy_vacuum.core.manager import EXTERNAL_FINALIZE_GRACE_S

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"


class _FakeErrorTracker:
    """Returns a canned active-run latch — mirrors ErrorTracker's read API."""

    def __init__(self, latch: dict | None) -> None:
        self._latch = latch

    def get_active_run_latch(self, vacuum_entity_id: str) -> dict | None:
        return self._latch


def _wire_error_tracker(hass, latch: dict | None) -> None:
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = _FakeErrorTracker(latch)


# ---------------------------------------------------------------------------
# get_lifecycle_state — error-message override
# ---------------------------------------------------------------------------

def test_lifecycle_current_message_overrides(manager, hass):
    """[LS-1] a live current_message replaces the generic lifecycle message."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _wire_error_tracker(hass, {
        "error_count": 1,
        "current_message": "Side brush stuck",
        "errors": [],
        "recovered": False,
    })
    out = manager.get_lifecycle_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["message"] == "Side brush stuck"
    assert out["has_error"] is True
    assert out["error_count"] == 1


def test_lifecycle_recovered_message_derived(manager, hass):
    """[LS-2] blank current_message + error history → a "had errors" summary."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _wire_error_tracker(hass, {
        "error_count": 2,
        "current_message": "",
        "errors": [
            {"message": "Wheel jam"},
            {"message": "Cliff sensor dirty"},
        ],
        "recovered": True,
    })
    out = manager.get_lifecycle_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["message"] == "Run had 2 error(s); last: Cliff sensor dirty"
    assert out["has_error"] is True


# ---------------------------------------------------------------------------
# get_start_status — start-protection gates
# ---------------------------------------------------------------------------

def test_start_status_blocked_by_paused_job(manager, hass):
    """[LS-3] a paused tracked job blocks a fresh start."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2, enabled_room_ids=[1, 2])
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "paused", "job_id": "jp", "paused_at": "2026-01-01T00:00:00+00:00",
    }
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "job_paused"


def test_start_status_blocked_by_onboarding(manager, hass):
    """[LS-4] enabled rooms missing a confirmed floor type block the start."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["enabled"] = True
    # save_managed_rooms auto-confirms floor types; clear them so enabled rooms
    # still need confirmation → onboarding incomplete.
    manager.data["onboarding"][_VAC][_MAP]["floor_types_confirmed"] = {}
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "onboarding_required"


def _blocker(entity: str) -> dict:
    return {"kind": "blocker", "id": "b1", "entity_id": entity,
            "operator": "is_on", "effect": {"reason": "window_open"}}


def test_start_status_all_rooms_blocked(manager, hass):
    """[LS-5] when every selected room is blocked, the start is fully blocked."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    keys = list(rooms.keys())
    for i, key in enumerate(keys):
        rooms[key]["enabled"] = True
        rooms[key]["order"] = i + 1
        rooms[key]["rules"] = [_blocker(f"binary_sensor.win_{i}")]
        hass.states.async_set(f"binary_sensor.win_{i}", "on")
    # a complete access graph so rule-bearing rooms pass the graph gate and we
    # reach the all-blocked branch: room1 is the dock room granting room2 access.
    rooms[keys[0]].update({"is_dock_room": True, "grants_access_to": [2]})
    rooms[keys[1]]["grants_access_to"] = []
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "all_selected_rooms_blocked"


def test_start_status_blocked_by_empty_queue(manager, hass):
    """[LS-6] no enabled rooms → empty queue → the build_start_blocker_from_lifecycle
    path returns no_rooms_selected. This is the card-facing blocked payload that
    was previously untested."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2, enabled_room_ids=[])
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "no_rooms_selected"
    # the payload fields the card reads on a lifecycle-block are populated
    assert out["reason_label"] and "preflight" in out
    assert "requires_confirmation" in out and "confirm_token" in out


@pytest.mark.parametrize("estimate,reason", [
    ({"not_enough_clean_water": True}, "not_enough_clean_water"),
    ({"low_clean_water_margin": True}, "low_clean_water_margin"),
])
def test_start_status_water_warning(manager, hass, monkeypatch, estimate, reason):
    """[LS-7] a ready start with a low-clean-water estimate surfaces a non-blocking
    water warning (the card's water-warning payload), covering both reason branches."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2, enabled_room_ids=[1, 2])
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    for i, room in enumerate(rooms.values(), start=1):
        room["enabled"] = True
        room["order"] = i
    hass.states.async_set(_VAC, "docked", {"battery_level": 90})
    monkeypatch.setattr(manager, "get_planned_job_estimate",
                        lambda **kw: {"water_estimate": estimate})
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is False
    assert out["water_warning"] is True
    assert out["water_warning_reason"] == reason
    assert out["warning"] is True


# ---------------------------------------------------------------------------
# maybe_handle_external_run + _external_grace_finalize — app-started run
# detection and the dock grace-window finalize. Real manager, real timers
# driven by async_fire_time_changed (no wall-clock sleeps).
#
# [EXT-1]  cleaning with no dispatched job opens an "external" capture slot.
# [EXT-1b] a dispatched (started) job short-circuits: no external slot opens.
# [EXT-2]  a mid-run dock resume cancels the pending grace finalize.
# [EXT-3]  staying docked past the grace window fires the finalize → slot clears.
# [EXT-4]  a mid-run task_status defers the close → slot stays + timer reschedules.
# ---------------------------------------------------------------------------

_EXT_ADAPTER = {
    "adapter_id": "t",
    "source": "t",
    "entities": {
        "active_map": "sensor.alfred_active_map",
        "task_status": "sensor.alfred_task",
    },
    "external_mid_run_statuses": ["washing mop", "emptying dust"],
}


def _ext_setup(manager):
    """Shared setup: a 2-room map on "6" + the external-aware adapter config."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _EXT_ADAPTER)


async def test_external_run_opens_capture_slot(manager, hass):
    """[EXT-1] cleaning + active_map set + no dispatched job → external slot."""
    _ext_setup(manager)
    try:
        hass.states.async_set("sensor.alfred_active_map", "6")
        hass.states.async_set(_VAC, "cleaning")

        opened = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)

        assert opened is True
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_run_short_circuits_when_dispatched(manager, hass):
    """[EXT-1b] a dispatched (started) job owns the run → no external slot opens."""
    _ext_setup(manager)
    try:
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["6"] = {
            "status": "started"
        }
        hass.states.async_set("sensor.alfred_active_map", "6")
        hass.states.async_set(_VAC, "cleaning")

        opened = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)

        assert opened is False
        # the internal job is untouched — no external capture clobbered it.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "started"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_run_cancels_grace_on_resume(manager, hass):
    """[EXT-2] a mid-run dock schedules a grace finalize; resuming cancels it."""
    _ext_setup(manager)
    try:
        # open the external slot directly, then dock to schedule the timer.
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "docked")

        scheduled = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        assert scheduled is False
        timers = manager._external_grace_timers()
        assert (_VAC, "6") in timers  # a finalize is pending

        # robot resumes mid-run → the pending finalize must be cancelled.
        hass.states.async_set(_VAC, "cleaning")
        resumed = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)

        assert resumed is False
        assert (_VAC, "6") not in manager._external_grace_timers()  # cancelled
        # the capture slot survives — the run is still one record.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_grace_finalize_clears_slot(manager, hass):
    """[EXT-3] docked past the grace window with a non-mid-run task → finalize.

    The timer fires _external_grace_finalize, which clears the capture slot
    (back to the default idle state). Asserting the cleared slot is the clean
    observable for "the run was finalized"."""
    _ext_setup(manager)
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "docked")
        hass.states.async_set("sensor.alfred_task", "Charging")  # NOT mid-run

        deferred = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        assert deferred is False
        assert (_VAC, "6") in manager._external_grace_timers()

        # advance virtual time past the grace window so the timer fires.
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=EXTERNAL_FINALIZE_GRACE_S + 1)
        )
        await hass.async_block_till_done()

        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] != "external"  # finalized → slot cleared
        assert slot["status"] == "idle"
        assert (_VAC, "6") not in manager._external_grace_timers()
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_grace_finalize_defers_when_mid_run(manager, hass):
    """[EXT-4] task_status reports a mid-run station cycle → finalize is deferred.

    _external_status_is_mid_run keeps the run open and reschedules the grace
    timer instead of closing it, so the slot stays "external"."""
    _ext_setup(manager)
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "docked")
        # "Washing Mop" matches external_mid_run_statuses (case-insensitive).
        hass.states.async_set("sensor.alfred_task", "Washing Mop")

        deferred = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        assert deferred is False
        assert (_VAC, "6") in manager._external_grace_timers()

        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=EXTERNAL_FINALIZE_GRACE_S + 1)
        )
        await hass.async_block_till_done()

        # still mid-run → NOT finalized; slot held open + a fresh timer rescheduled.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
        assert (_VAC, "6") in manager._external_grace_timers()
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)
