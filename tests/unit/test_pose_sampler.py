"""Unit tests for listeners/pose_sampler.py — the W5b run-active external pose sampler.

Covers the adapter-driven cadence/gating helpers and the per-vacuum sample tick (records
external pose, skips absent-pose / dispatched / no-attribution / no-live-map cases).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.eufy_vacuum.listeners import pose_sampler


# --- adapter-driven cadence + gating (settings come from the adapter, not core) ---


def test_interval_from_adapter(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"room_attribution": {"tuning": {"interval_s": 3.0}}})
    assert pose_sampler._room_attribution_interval_s("vacuum.alfred") == 3.0


def test_interval_falls_back_to_engine_default(monkeypatch):
    """No interval_s in tuning -> the resolved engine's DEFAULT_TUNING (single source)."""
    from custom_components.eufy_vacuum.learning.room_attribution_engines import (
        EufyAnchorWindingAttributor,
    )
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"room_attribution": {"engine": "eufy_anchor_winding_v1"}})
    assert (pose_sampler._room_attribution_interval_s("vacuum.alfred")
            == EufyAnchorWindingAttributor.DEFAULT_TUNING["interval_s"])


def test_interval_none_without_room_attribution(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config", lambda vid: {})
    assert pose_sampler._room_attribution_interval_s("vacuum.alfred") is None


def test_has_live_map(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"map_state_source": {"live_pose": {}}})
    assert pose_sampler._has_live_map("vacuum.alfred") is True
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"map_state_source": {}})
    assert pose_sampler._has_live_map("vacuum.alfred") is False


# --- the per-vacuum sample tick ---


def _mock_manager(pose, *, status="external"):
    mgr = MagicMock()
    mgr.get_known_map_ids.return_value = ["6"]
    mgr.get_active_job.return_value = {"status": status}

    async def _live(**_kwargs):
        return pose

    mgr.async_get_map_live_pose = _live
    mgr.record_pose_sample = MagicMock(return_value=True)
    return mgr


def _hass_with_area(area="3.0"):
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state=area)
    return hass


def _cfg_full(_vid):
    return {
        "room_attribution": {"tuning": {"interval_s": 2.0}},
        "map_state_source": {"live_pose": {}},
        "entities": {"cleaning_area": "sensor.alfred_cleaning_area"},
    }


async def test_sample_records_external_pose(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_full)
    mgr = _mock_manager({"present": True, "current_room": 5, "robot_anchor": [0.1, 0.2], "robot_heading": None})
    n = await pose_sampler._sample_vacuum_once(_hass_with_area("3.0"), mgr, "vacuum.alfred")
    assert n == 1
    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["current_room"] == 5 and kw["anchor"] == [0.1, 0.2] and kw["cleaning_area"] == 3.0


async def test_sample_nulls_docked_ticks(monkeypatch):
    """A docked tick carries the dock's room/anchor from the fork — the sampler nulls both
    so a parked dock is a genuine None-run (the parked-dock exclusion). cleaning_area stays."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_full)
    mgr = _mock_manager({"present": True, "current_room": 8, "robot_anchor": [0.7, 0.3], "robot_docked": True})
    n = await pose_sampler._sample_vacuum_once(_hass_with_area("5.0"), mgr, "vacuum.alfred")
    assert n == 1
    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["current_room"] is None and kw["anchor"] is None
    assert kw["cleaning_area"] == 5.0


async def test_sample_skips_when_pose_absent(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_full)
    mgr = _mock_manager({"present": False, "reason": "no_geom"})
    n = await pose_sampler._sample_vacuum_once(_hass_with_area(), mgr, "vacuum.alfred")
    assert n == 0
    mgr.record_pose_sample.assert_not_called()


async def test_sample_skips_dispatched_run(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_full)
    mgr = _mock_manager({"present": True, "current_room": 5}, status="started")
    assert await pose_sampler._sample_vacuum_once(_hass_with_area(), mgr, "vacuum.alfred") == 0


async def test_sample_skips_vacuum_without_room_attribution(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"map_state_source": {"live_pose": {}}})
    mgr = _mock_manager({"present": True, "current_room": 5})
    assert await pose_sampler._sample_vacuum_once(_hass_with_area(), mgr, "vacuum.alfred") == 0


async def test_sample_skips_vacuum_without_live_map(monkeypatch):
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"room_attribution": {"tuning": {}}})
    mgr = _mock_manager({"present": True, "current_room": 5})
    assert await pose_sampler._sample_vacuum_once(_hass_with_area(), mgr, "vacuum.alfred") == 0


# --- W5c: docked-gate from the MQTT task_status (not the unreliable pose flag) ---


def _hass_states(mapping: dict):
    """hass whose states.get(eid) returns SimpleNamespace(state=...) per entity, else None."""
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=mapping[eid]) if eid in mapping else None
    )
    return hass


# Adapter that declares the MQTT signals the W5c docked-gate reads (task_status entity +
# the active-run vocabulary). "returning"/"navigating" ARE active (not nulled).
_ACTIVE = ["cleaning", "room cleaning", "spot cleaning", "returning", "resuming", "navigating"]


def _cfg_mqtt(_vid):
    return {
        "room_attribution": {"tuning": {"interval_s": 2.0}},
        "map_state_source": {"live_pose": {}},
        "entities": {"cleaning_area": "sensor.alfred_cleaning_area",
                     "task_status": "sensor.alfred_task_status"},
        "vocabulary": {"active_run_task_states": _ACTIVE},
    }


def test_is_parked_uses_task_status_over_pose_flag():
    cfg = _cfg_mqtt("vacuum.alfred")
    # Completed/Washing Mop are NOT active -> parked, even though the pose flag says undocked.
    assert pose_sampler._is_parked(
        _hass_states({"sensor.alfred_task_status": "Completed"}), cfg, {"robot_docked": False}) is True
    assert pose_sampler._is_parked(
        _hass_states({"sensor.alfred_task_status": "Washing Mop"}), cfg, {"robot_docked": False}) is True
    # Cleaning / Returning ARE active -> not parked.
    assert pose_sampler._is_parked(
        _hass_states({"sensor.alfred_task_status": "Cleaning"}), cfg, {"robot_docked": True}) is False
    assert pose_sampler._is_parked(
        _hass_states({"sensor.alfred_task_status": "Returning"}), cfg, {"robot_docked": False}) is False


def test_is_parked_falls_back_to_pose_flag_when_task_status_unreadable():
    cfg = _cfg_mqtt("vacuum.alfred")
    # unavailable task_status -> fall back to the pose robot_docked flag.
    assert pose_sampler._is_parked(
        _hass_states({"sensor.alfred_task_status": "unavailable"}), cfg, {"robot_docked": True}) is True
    assert pose_sampler._is_parked(
        _hass_states({"sensor.alfred_task_status": "unavailable"}), cfg, {"robot_docked": False}) is False
    # no vocab/entity at all -> pose flag.
    assert pose_sampler._is_parked(_hass_states({}), {"entities": {}}, {"robot_docked": True}) is True


async def test_sample_nulls_on_inactive_task_status(monkeypatch):
    """The F2-via-MQTT fix: a Completed/docked task_status nulls current_room even when the
    fork's pose flag still says undocked (the live failure that recorded 100 dock-sitting ticks
    as a room). cleaning_area is still recorded."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_mqtt)
    mgr = _mock_manager({"present": True, "current_room": 8, "robot_anchor": [0.7, 0.3],
                         "robot_docked": False})
    hass = _hass_states({"sensor.alfred_cleaning_area": "5.0", "sensor.alfred_task_status": "Completed"})
    n = await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.alfred")
    assert n == 1
    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["current_room"] is None and kw["anchor"] is None
    assert kw["cleaning_area"] == 5.0


async def test_sample_keeps_active_cleaning_task_status(monkeypatch):
    """An active-run task_status (Cleaning) records the room — not nulled — even if the pose
    flag is (wrongly) set."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_mqtt)
    mgr = _mock_manager({"present": True, "current_room": 8, "robot_anchor": [0.7, 0.3],
                         "robot_docked": True})
    hass = _hass_states({"sensor.alfred_cleaning_area": "5.0", "sensor.alfred_task_status": "Cleaning"})
    n = await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.alfred")
    assert n == 1
    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["current_room"] == 8 and kw["anchor"] == [0.7, 0.3]
