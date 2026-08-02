"""Unit tests for queue/queue_engine.py — pure queue + payload builders.

Coverage targets
----------------
[QE-1]  get_enabled_rooms_in_order: filters disabled, sorts by order+name.
[QE-2]  build_queue_from_managed_rooms: queue ids + rooms from enabled set.
[QE-3]  _cast_map_id: int / str / auto.
[QE-4]  _write_room_field: identity / omit (None) / value_map.
[QE-5]  build_active_job_state: stable keys + current room + frozen status.
[QE-6]  build_room_clean_payload: returns payload + resolved_rooms (smoke).
[QE-7]  build_active_job_state: no phases arg -> phase keys absent (atomic, unchanged).
[QE-8]  build_active_job_state: phases arg -> phases + current_phase_index + phase_count stored.
[QE-9]  advance_active_job_phase: atomic/last -> None; mid -> swaps to next phase, resets progress.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.queue.queue_engine import (
    _cast_map_id,
    _write_room_field,
    advance_active_job_phase,
    build_active_job_state,
    build_queue_from_managed_rooms,
    build_room_clean_payload,
    get_enabled_rooms_in_order,
)


_VAC = "vacuum.alfred"
_MAP = "6"


def _rooms():
    return {
        "1": {"room_id": 1, "name": "Kitchen", "enabled": True, "order": 2},
        "2": {"room_id": 2, "name": "Bath", "enabled": True, "order": 1},
        "3": {"room_id": 3, "name": "Closet", "enabled": False, "order": 0},
    }


def test_enabled_in_order():
    """[QE-1] enabled only, sorted by order → Bath(1) before Kitchen(2)."""
    ordered = get_enabled_rooms_in_order(managed_rooms=_rooms())
    assert [r["room_id"] for r in ordered] == [2, 1]


def test_build_queue():
    """[QE-2]"""
    q = build_queue_from_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP, managed_rooms=_rooms())
    assert q["room_count"] == 2
    assert q["queue_room_ids"] == [2, 1]
    assert q["queue_rooms"][0]["name"] == "Bath"


@pytest.mark.parametrize("value,mtype,expected", [
    ("6", "int", 6), ("6", "str", "6"), ("6", None, 6),
    ("abc", "int", "abc"), ("abc", None, "abc"),
])
def test_cast_map_id(value, mtype, expected):
    """[QE-3]"""
    assert _cast_map_id(value, mtype) == expected


def test_write_room_field():
    """[QE-4]"""
    # identity (no rename config)
    room: dict = {}
    _write_room_field(room, {}, "clean_mode", "vacuum")
    assert room["clean_mode"] == "vacuum"
    # omit when field_name is None
    room2: dict = {}
    _write_room_field(room2, {"clean_mode": {"field_name": None}}, "clean_mode", "vacuum")
    assert "clean_mode" not in room2
    # rename + value_map
    room3: dict = {}
    _write_room_field(
        room3, {"clean_mode": {"field_name": "mode", "value_map": {"vacuum": 1}}},
        "clean_mode", "vacuum")
    assert room3 == {"mode": 1}


def test_build_active_job_state():
    """[QE-5]"""
    state = build_active_job_state(
        vacuum_entity_id=_VAC, map_id=_MAP,
        queue_state={"queue_room_ids": [2, 1], "queue_rooms": [{"room_id": 2}]},
        payload_state={"resolved_rooms": [{"room_id": 2}], "payload": {"x": 1}, "room_count": 2})
    assert state["status"] == "started"
    assert state["current_room_id"] == 2
    assert state["queue_stable_keys"] == [f"{_VAC}:{_MAP}:2", f"{_VAC}:{_MAP}:1"]
    assert state["completed_room_ids"] == []


def test_build_room_clean_payload():
    """[QE-6] smoke — minimal managed room yields payload + resolved rooms."""
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        managed_rooms={"1": {"room_id": 1, "name": "Kitchen", "enabled": True,
                             "clean_mode": "vacuum", "fan_speed": "Max"}},
        queue_room_ids=[1])
    assert result["room_count"] >= 1
    assert "payload" in result
    assert isinstance(result["resolved_rooms"], list)


def test_build_room_clean_payload_omits_nonnumeric_map_id_for_int_type():
    """[QE-6a] Regression: an int-typed map_id field DROPS a non-numeric implicit
    map ("main", Eufy scalar/attribute mode) from the WIRE payload rather than
    shipping a string a downstream transport will int() and choke on
    (robovac_mqtt build_set_room_custom_command). The internal tracking id stays."""
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id="main",
        managed_rooms={"1": {"room_id": 1, "name": "Kitchen", "enabled": True,
                             "clean_mode": "vacuum", "fan_speed": "Max"}},
        queue_room_ids=[1],
        dispatch={"map_id_type": "int"})
    assert "map_id" not in result["payload"]   # omitted from the wire
    assert result["map_id"] == "main"          # canonical id kept for job/learning


def test_build_room_clean_payload_keeps_numeric_int_map_id():
    """[QE-6b] A numeric map_id under int type is still sent, as an int."""
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id="6",
        managed_rooms={"1": {"room_id": 1, "name": "Kitchen", "enabled": True,
                             "clean_mode": "vacuum", "fan_speed": "Max"}},
        queue_room_ids=[1],
        dispatch={"map_id_type": "int"})
    assert result["payload"]["map_id"] == 6


def test_build_room_clean_payload_clamps_wire_clean_times():
    """[QE-6c] The WIRE clean_times is clamped to [1, passes_max] (Eufy caps at 2),
    while resolved_rooms.clean_passes keeps the RAW resolved value (learning records
    intent, not the device clamp). Matches the flat-id / Dreame engines."""
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        managed_rooms={"1": {"room_id": 1, "name": "Kitchen", "enabled": True,
                             "clean_mode": "vacuum", "fan_speed": "Max",
                             "clean_passes": 5}},
        queue_room_ids=[1])
    assert result["payload"]["rooms"][0]["clean_times"] == 2   # clamped to passes_max
    assert result["resolved_rooms"][0]["clean_passes"] == 5    # raw resolved kept


def test_build_room_clean_payload_floors_wire_clean_times():
    """[QE-6d] A zero / negative stored pass count floors to 1 on the wire."""
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        managed_rooms={"1": {"room_id": 1, "name": "Kitchen", "enabled": True,
                             "clean_mode": "vacuum", "fan_speed": "Max",
                             "clean_passes": 0}},
        queue_room_ids=[1])
    assert result["payload"]["rooms"][0]["clean_times"] == 1


def test_active_job_no_phases_keys_absent():
    """[QE-7] atomic (no phases arg) -> phase keys are not present at all."""
    state = build_active_job_state(
        vacuum_entity_id=_VAC, map_id=_MAP,
        queue_state={"queue_room_ids": [1], "queue_rooms": []},
        payload_state={"resolved_rooms": [{"room_id": 1}], "payload": {}, "room_count": 1})
    assert "phases" not in state
    assert "current_phase_index" not in state


def test_active_job_with_phases_stored():
    """[QE-8] sequenced -> phases + index + count stored."""
    phases = [
        {"resolved_rooms": [{"room_id": 1}], "payload": {"a": 1}, "room_count": 1},
        {"resolved_rooms": [{"room_id": 1}], "payload": {"a": 2}, "room_count": 1},
    ]
    state = build_active_job_state(
        vacuum_entity_id=_VAC, map_id=_MAP,
        queue_state={"queue_room_ids": [1], "queue_rooms": []},
        payload_state={"resolved_rooms": [{"room_id": 1}], "payload": {"a": 1}, "room_count": 1},
        phases=phases)
    assert state["phases"] == phases
    assert state["current_phase_index"] == 0
    assert state["phase_count"] == 2


def test_advance_phase_atomic_and_last_return_none():
    """[QE-9] no phases -> None; final phase -> None (caller finalizes)."""
    assert advance_active_job_phase({"vacuum_entity_id": _VAC, "map_id": _MAP}) is None
    one_phase = {"vacuum_entity_id": _VAC, "map_id": _MAP,
                 "phases": [{"resolved_rooms": [{"room_id": 1}]}], "current_phase_index": 0}
    assert advance_active_job_phase(one_phase) is None
    on_last = {"vacuum_entity_id": _VAC, "map_id": _MAP,
               "phases": [{"resolved_rooms": []}, {"resolved_rooms": []}],
               "current_phase_index": 1}
    assert advance_active_job_phase(on_last) is None


def test_advance_phase_swaps_and_resets():
    """[QE-9] mid-sequence advance swaps room set + payload and resets progress."""
    phases = [
        {"resolved_rooms": [{"room_id": 1}], "payload": {"mode": "sweep"}, "room_count": 1},
        {"resolved_rooms": [{"room_id": 5}, {"room_id": 6}],
         "payload": {"mode": "mop"}, "room_count": 2},
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "phases": phases, "current_phase_index": 0,
        "resolved_rooms": phases[0]["resolved_rooms"], "payload": phases[0]["payload"],
        "completed_room_ids": [1], "completed_rooms": [{"room_id": 1}],
        "current_room_id": None, "status": "started",
    }
    nxt = advance_active_job_phase(job)
    assert nxt is not None
    assert nxt["current_phase_index"] == 1
    assert nxt["payload"] == {"mode": "mop"}
    assert nxt["queue_room_ids"] == [5, 6]
    assert nxt["current_room_id"] == 5            # first room of the new phase
    assert nxt["completed_room_ids"] == []        # per-phase progress reset
    assert nxt["completed_rooms"] == []
    assert nxt["queue_stable_keys"] == [f"{_VAC}:{_MAP}:5", f"{_VAC}:{_MAP}:6"]
    assert nxt["has_observed_active_lifecycle"] is False   # fresh sub-job
    assert nxt["_phase_dispatch_pending"] is True           # not yet confirmed cleaning


def test_advance_phase_resets_native_current_room_id():
    """[QE-10] RP-012/RF-31 (DQ-PH-6): _native_current_room_id resets with its
    sibling current_room_id -- left alone, the previous phase's native-signal
    room id survives the advance while current_room_id moves on, so the two
    pointers DISAGREE. The next native signal tick could then re-complete the
    PREVIOUS phase's room into the freshly-emptied completed_room_ids and fire
    a second room_completed for it."""
    phases = [
        {"resolved_rooms": [{"room_id": 1}], "payload": {}, "room_count": 1},
        {"resolved_rooms": [{"room_id": 5}], "payload": {}, "room_count": 1},
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "phases": phases, "current_phase_index": 0,
        "resolved_rooms": phases[0]["resolved_rooms"], "payload": phases[0]["payload"],
        "completed_room_ids": [1], "completed_rooms": [{"room_id": 1}],
        "current_room_id": 1, "_native_current_room_id": 1, "status": "started",
    }
    nxt = advance_active_job_phase(job)
    assert nxt is not None
    assert nxt["current_room_id"] == 5
    assert nxt["_native_current_room_id"] is None


# ---------------------------------------------------------------------------
# RP-013c — job-cumulative completed evidence across phase advances
# ---------------------------------------------------------------------------

def _phased(completed, cumulative=None, idx=0):
    phases = [
        {"resolved_rooms": [{"room_id": 1}], "room_count": 1},
        {"resolved_rooms": [{"room_id": 2}], "room_count": 1},
        {"resolved_rooms": [{"room_id": 3}], "room_count": 1},
    ]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP,
        "phases": phases, "current_phase_index": idx,
        "completed_room_ids": list(completed), "status": "started",
    }
    if cumulative is not None:
        job["completed_room_ids_cumulative"] = list(cumulative)
    return job


def test_advance_phase_accumulates_completed_evidence():
    """[QE-13c] the finishing phase's completed rooms survive the per-phase reset."""
    nxt = advance_active_job_phase(_phased([1]))
    assert nxt["completed_room_ids"] == []           # per-phase reset UNCHANGED
    assert nxt["completed_room_ids_cumulative"] == [1]


def test_advance_phase_cumulative_grows_across_two_advances():
    """[QE-13c] evidence from every finished phase, not just the last one."""
    after1 = advance_active_job_phase(_phased([1]))
    after1["completed_room_ids"] = [2]               # phase 2 then finishes room 2
    after2 = advance_active_job_phase(after1)
    assert after2["completed_room_ids_cumulative"] == [1, 2]


def test_advance_phase_cumulative_dedupes_and_keeps_order():
    """[QE-13c] a room re-listed by a later phase is not duplicated."""
    nxt = advance_active_job_phase(_phased([2, 1], cumulative=[1]))
    assert nxt["completed_room_ids_cumulative"] == [1, 2]


@pytest.mark.parametrize("junk", [None, "x", -1, 0, {"room_id": 1}])
def test_advance_phase_cumulative_ignores_unusable_ids(junk):
    """[QE-13c] non-positive / non-integer entries are dropped, not crashed on."""
    nxt = advance_active_job_phase(_phased([junk, 4]))
    assert nxt["completed_room_ids_cumulative"] == [4]


def test_advance_phase_cumulative_absent_key_is_safe():
    """[QE-13c] a job written before this landed has no cumulative key."""
    job = _phased([1])
    job.pop("completed_room_ids_cumulative", None)
    assert advance_active_job_phase(job)["completed_room_ids_cumulative"] == [1]
