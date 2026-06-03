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

import pytest

from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN

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
