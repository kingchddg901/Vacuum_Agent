"""Unit tests for listeners/pose_sampler.py — the W5b run-active external pose sampler.

Covers the adapter-driven cadence/gating helpers and the per-vacuum sample tick (records
external pose, skips absent-pose / dispatched / no-attribution / no-live-map cases).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tests._factories import spec_manager

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


def test_source_defaults_to_live_pose(monkeypatch):
    """Absent source key (block predates it) -> live_pose; explicit values pass through."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"room_attribution": {"engine": "eufy_anchor_winding_v1"}})
    assert pose_sampler._room_attribution_source("vacuum.alfred") == "live_pose"
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"room_attribution": {"source": "NATIVE_CURRENT_ROOM"}})
    assert pose_sampler._room_attribution_source("vacuum.ivy") == "native_current_room"
    monkeypatch.setattr(pose_sampler, "get_adapter_config", lambda vid: {})
    assert pose_sampler._room_attribution_source("vacuum.x") == "live_pose"


def test_can_sample_live_pose(monkeypatch):
    """live_pose source gates on a map_state_source.live_pose block."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"map_state_source": {"live_pose": {}}})
    assert pose_sampler._can_sample("vacuum.alfred") is True
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"map_state_source": {}})
    assert pose_sampler._can_sample("vacuum.alfred") is False


def test_can_sample_native_current_room(monkeypatch):
    """native_current_room source gates on a declared active_cleaning_target entity — NOT on a
    live_pose map block (Roborock has none)."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"room_attribution": {"source": "native_current_room"},
                                     "entities": {"active_cleaning_target": "sensor.ivy_current_room"}})
    assert pose_sampler._can_sample("vacuum.ivy") is True
    # source declared but no entity -> cannot sample.
    monkeypatch.setattr(pose_sampler, "get_adapter_config",
                        lambda vid: {"room_attribution": {"source": "native_current_room"},
                                     "entities": {}})
    assert pose_sampler._can_sample("vacuum.ivy") is False


# --- the per-vacuum sample tick ---


def _mock_manager(pose, *, status="external"):
    mgr = spec_manager()
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


async def test_sample_records_dispatched_run(monkeypatch):
    """A DISPATCHED (started) run is now sampled too — the atomic finalize reconciles its
    positional room identity against the buffered native current_room."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_full)
    mgr = _mock_manager({"present": True, "current_room": 5, "robot_anchor": [0.1, 0.2]}, status="started")
    n = await pose_sampler._sample_vacuum_once(_hass_with_area("3.0"), mgr, "vacuum.alfred")
    assert n == 1
    assert mgr.record_pose_sample.call_args.kwargs["current_room"] == 5


async def test_sample_skips_idle_map(monkeypatch):
    """A map with no active external/dispatched run (idle) records nothing."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_full)
    mgr = _mock_manager({"present": True, "current_room": 5}, status="idle")
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


# --- W1: native_current_room source (Roborock — the brand publishes the room NAME) ----------
#
# The ROOM comes from entities.active_cleaning_target (a room NAME), slugified and matched to a
# MANAGED room id via manager.get_managed_rooms. The ANCHOR is a separate axis: read from the
# declared live pose when the adapter has one, None when it does not — "this source has no pixel
# pose" was true of the NAME entity and false of the brand, and the literal None it justified is
# what kept the pose ring empty. Docked-gate is the MQTT task_status (Roborock reverts the target
# to the dock room + task_status -> charging when parked), and it nulls BOTH axes. Fixtures mirror
# reference_roborock_ivy_signals.

# Roborock's active-run task states (subset — `charging` is deliberately NOT active -> parked).
_ROBO_ACTIVE = ["segment_cleaning", "segment_mopping", "returning_home", "cleaning", "docking"]


def _cfg_native(_vid):
    return {
        "room_attribution": {"engine": "eufy_anchor_winding_v1",
                             "source": "native_current_room", "tuning": {"interval_s": 5.0}},
        "entities": {"active_cleaning_target": "sensor.ivy_current_room",
                     "cleaning_area": "sensor.ivy_cleaning_area",
                     "task_status": "sensor.ivy_status"},
        "vocabulary": {"active_run_task_states": _ROBO_ACTIVE},
    }


def _mock_manager_native(managed_rooms: dict, *, status="external"):
    mgr = spec_manager()
    mgr.get_known_map_ids.return_value = ["6"]
    mgr.get_active_job.return_value = {"status": status}
    mgr.get_managed_rooms.return_value = {"rooms": managed_rooms}
    mgr.record_pose_sample = MagicMock(return_value=True)
    return mgr


def _cfg_native_with_pose(_vid):
    """The Roborock shape as shipped: native room NAME *and* a declared parsed-map pose."""
    cfg = _cfg_native(_vid)
    cfg["map_state_source"] = {
        "backend": "memory",
        "live_pose": {"backend": "parsed_mapdata", "pose_refresh_s": 30.0},
    }
    return cfg


async def test_a_declared_pose_is_banked_alongside_the_native_room(monkeypatch):
    """THE LITERAL None THAT KEPT THE RING EMPTY.

    The room still comes from the NAME entity — that path is recorder-verified and a pose
    lookup would be a worse answer to a question the brand answers directly. The anchor is
    the OTHER fact, and it is now read from the declared pose. Without this the ring holds
    rows with no positions in them, so a stall capture has nothing to draw a trail from and
    the absence looks like a broken renderer rather than a missing declaration.
    """
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native_with_pose)
    mgr = _mock_manager_native({"3": {"room_id": 3, "name": "Kitchen", "slug": "kitchen"}})
    # The autospec'd method off spec_manager, not a bare AsyncMock — it keeps the real
    # signature, so a sampler calling it wrongly fails here instead of passing green.
    mgr.async_get_map_live_pose.return_value = {
        "present": True, "robot_anchor": [0.694, 0.509], "robot_heading": 67,
    }
    hass = _hass_states({"sensor.ivy_current_room": "Kitchen",
                         "sensor.ivy_cleaning_area": "3.1",
                         "sensor.ivy_status": "segment_cleaning"})

    assert await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy") == 1

    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["anchor"] == [0.694, 0.509]
    assert kw["heading"] == 67
    assert kw["current_room"] == 3, "the room must still come from the NAME entity"


async def test_a_docked_tick_banks_no_position(monkeypatch):
    """Parked ticks null BOTH axes, so the dock never enters the ring as a position.

    A trail is evidence of movement; dock-sitting samples would pad it with a place the
    robot was parked, and on a coarse brand a couple of those is the whole window.
    """
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native_with_pose)
    mgr = _mock_manager_native({"3": {"room_id": 3, "name": "Kitchen", "slug": "kitchen"}})
    mgr.async_get_map_live_pose.return_value = {
        "present": True, "robot_anchor": [0.5, 0.5],
    }
    hass = _hass_states({"sensor.ivy_current_room": "Kitchen",
                         "sensor.ivy_cleaning_area": "3.1",
                         "sensor.ivy_status": "charging"})   # parked

    assert await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy") == 1

    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["anchor"] is None and kw["current_room"] is None
    mgr.async_get_map_live_pose.assert_not_awaited()


async def test_a_pose_read_failure_still_records_the_room(monkeypatch):
    """The room is the attribution signal; losing the pose must not lose the sample too."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native_with_pose)
    mgr = _mock_manager_native({"3": {"room_id": 3, "name": "Kitchen", "slug": "kitchen"}})
    mgr.async_get_map_live_pose.side_effect = RuntimeError("provider blew up")
    hass = _hass_states({"sensor.ivy_current_room": "Kitchen",
                         "sensor.ivy_cleaning_area": "3.1",
                         "sensor.ivy_status": "segment_cleaning"})

    assert await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy") == 1

    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["current_room"] == 3 and kw["anchor"] is None


async def test_sample_native_records_room_by_name(monkeypatch):
    """Kitchen (native NAME) -> managed room id 3; no declared pose so anchor/heading stay
    None; cleaning_area recorded."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native)
    mgr = _mock_manager_native({"3": {"room_id": 3, "name": "Kitchen", "slug": "kitchen"},
                                "5": {"room_id": 5, "name": "Living Room", "slug": "living_room"}})
    hass = _hass_states({"sensor.ivy_current_room": "Kitchen",
                         "sensor.ivy_cleaning_area": "3.1",
                         "sensor.ivy_status": "segment_cleaning"})
    n = await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy")
    assert n == 1
    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["current_room"] == 3
    assert kw["anchor"] is None and kw["heading"] is None
    assert kw["cleaning_area"] == 3.1


async def test_sample_native_matches_by_name_when_no_slug(monkeypatch):
    """A managed room with no `slug` key falls back to slugifying its `name` (Cat Room)."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native)
    mgr = _mock_manager_native({"7": {"room_id": 7, "name": "Cat Room"}})
    hass = _hass_states({"sensor.ivy_current_room": "Cat Room",
                         "sensor.ivy_cleaning_area": "3.1",
                         "sensor.ivy_status": "segment_cleaning"})
    n = await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy")
    assert n == 1
    assert mgr.record_pose_sample.call_args.kwargs["current_room"] == 7


async def test_sample_native_nulls_when_docked(monkeypatch):
    """Parked: task_status -> charging (not active) nulls current_room even though the target
    still reads the dock room (Dining Room). cleaning_area is still recorded."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native)
    mgr = _mock_manager_native({"2": {"room_id": 2, "name": "Dining Room", "slug": "dining_room"}})
    hass = _hass_states({"sensor.ivy_current_room": "Dining Room",
                         "sensor.ivy_cleaning_area": "4.4",
                         "sensor.ivy_status": "charging"})
    n = await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy")
    assert n == 1
    kw = mgr.record_pose_sample.call_args.kwargs
    assert kw["current_room"] is None
    assert kw["cleaning_area"] == 4.4


async def test_sample_native_unmatched_name_records_none(monkeypatch):
    """A name not among managed rooms (unimported / transit) records current_room=None — NOT a
    skip. The None marks transit for the engine (splits contiguous room runs)."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native)
    mgr = _mock_manager_native({"3": {"room_id": 3, "name": "Kitchen", "slug": "kitchen"}})
    hass = _hass_states({"sensor.ivy_current_room": "Garage",
                         "sensor.ivy_cleaning_area": "1.0",
                         "sensor.ivy_status": "segment_cleaning"})
    n = await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy")
    assert n == 1
    assert mgr.record_pose_sample.call_args.kwargs["current_room"] is None


async def test_sample_native_unavailable_target_records_none(monkeypatch):
    """An unknown/unavailable current_room entity is a genuine None (transit), still recorded."""
    monkeypatch.setattr(pose_sampler, "get_adapter_config", _cfg_native)
    mgr = _mock_manager_native({"3": {"room_id": 3, "name": "Kitchen", "slug": "kitchen"}})
    hass = _hass_states({"sensor.ivy_current_room": "unknown",
                         "sensor.ivy_cleaning_area": "1.0",
                         "sensor.ivy_status": "segment_cleaning"})
    n = await pose_sampler._sample_vacuum_once(hass, mgr, "vacuum.ivy")
    assert n == 1
    assert mgr.record_pose_sample.call_args.kwargs["current_room"] is None


# --- cleaning_area is normalized to m² by the entity's unit (imperial HA → Eufy ft²) ---------


def _hass_area_state(state, unit):
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state=state, attributes={"unit_of_measurement": unit})
    return hass


def test_read_cleaning_area_converts_ft2_to_m2():
    """Alfred (imperial HA): sensor reads 53.82 ft² -> buffered as 5.0 m², not 53.82."""
    cfg = {"entities": {"cleaning_area": "sensor.alfred_cleaning_area"}}
    assert round(pose_sampler._read_cleaning_area(_hass_area_state("53.82", "ft²"), cfg), 2) == 5.0


def test_read_cleaning_area_m2_unchanged():
    """Ivy: sensor unit m² -> value passes through unscaled."""
    cfg = {"entities": {"cleaning_area": "sensor.ivy_cleaning_area"}}
    assert pose_sampler._read_cleaning_area(_hass_area_state("4.4", "m²"), cfg) == 4.4
