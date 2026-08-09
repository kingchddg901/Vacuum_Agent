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
    phased_job_id_for,
    _cast_map_id,
    _write_room_field,
    advance_active_job_phase,
    build_active_job_state,
    build_queue_from_managed_rooms,
    build_room_clean_payload,
    get_enabled_rooms_in_order,
)

# build_room_clean_payload resolves its own catalog from the ADAPTER REGISTRY, so a
# synthetic brand is registered for the whole module. These tests are about queue
# construction, not vocabulary — a real brand's catalog would let a leaked word satisfy
# them by coincidence, which is how the Eufy default stayed invisible.
pytestmark = pytest.mark.usefixtures("synthetic_adapter")


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


def test_advance_phase_still_resets_per_phase_progress():
    """The per-phase reset is deliberate and UNCHANGED — each phase is a fresh atomic
    sub-job. What changed is that nothing accumulates alongside it any more."""
    nxt = advance_active_job_phase(_phased([1]))
    assert nxt["completed_room_ids"] == []
    assert nxt["completed_rooms"] == []


def test_advance_phase_writes_no_cumulative_key():
    """RP-013c's `completed_room_ids_cumulative` was retired once every phase got its own
    child record: a stored second source of truth that a child would union into itself.
    known_completed_room_ids DERIVES the same facts from the phase index instead — the
    guarantee now lives in tests/unit/test_learning_utils.py, not here. A lingering key
    would be read by that ladder's old callers and silently re-credit rooms."""
    nxt = advance_active_job_phase(_phased([1]))
    assert "completed_room_ids_cumulative" not in nxt


def test_advance_phase_cumulative_ignores_a_break_phases_empty_room_set():
    """[QE-13c] a charge_wait/wait phase carries no rooms, so it contributes nothing."""
    job = _phased([], cumulative=[1], idx=1)
    job["phases"][1] = {"resolved_rooms": [], "room_count": 0,
                        "phase_type": "charge_wait"}
    assert advance_active_job_phase(job)["completed_room_ids_cumulative"] == [1]


# ---------------------------------------------------------------------------
# Phased Jobs wave 0 — the DTG anchor (written, read by nothing yet)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("job_id,expected", [
    ("job_2026-08-02T11-15-51", "pj_2026-08-02T11-15-51"),  # phase 0 shares the run's DTG
    ("2026-08-02T11-15-51", "pj_2026-08-02T11-15-51"),      # tolerate a bare DTG
    ("", ""),                                                # nothing to anchor to
    (None, ""),
])
def test_phased_job_anchor_derivation(job_id, expected):
    """[QE-PJ] The anchor is the RUN's start, so the parent and phase 0 share a timestamp
    and the relationship is visible from a directory listing with no lookup."""
    assert phased_job_id_for(job_id) == expected


def test_phased_job_anchor_survives_the_advance():
    """[QE-PJ] The anchor identifies the RUN, so every phase of it must carry the same
    one. If an advance dropped or rewrote it, siblings could not be reassembled."""
    job = _phased([1])
    job["phased_job_id"] = "pj_2026-08-02T11-15-51"
    nxt = advance_active_job_phase(job)
    assert nxt["phased_job_id"] == "pj_2026-08-02T11-15-51"





def test_atomic_job_state_carries_no_phase_keys():
    """[QE-PJ] PRESENCE IS THE SIGNAL — an atomic run must stay byte-identical, so an
    absent anchor is how 'not phased' is expressed. A boolean would be a second source of
    truth that could disagree with the key."""
    state = build_active_job_state(
        vacuum_entity_id=_VAC, map_id=_MAP,
        queue_state={"queue_room_ids": [1], "queue_rooms": []},
        payload_state={"payload": {}, "room_count": 1, "resolved_rooms": [{"room_id": 1}]},
        phases=None,
    )

    assert "phases" not in state
    assert "phased_job_id" not in state


# ---------------------------------------------------------------------------
# [QE-6c] / [QE-6d] ISSUE #48 on the wire — the mop-field gates
# ---------------------------------------------------------------------------
#
# The two gates that decide whether water_level and edge_mopping reach the
# payload were `clean_mode in {"mop", "vacuum_mop"}` — exact and case-sensitive —
# against a value that arrives as stored, not canonicalized. apply_capability_gate
# re-emits clean_mode untouched for a mop-capable device (pinned by [RP-12c]), and
# the room editor stores the DISPLAY LABEL "Vacuum and mop". So a mop-capable
# vacuum dispatched a mop room with NEITHER field on the wire, while resolved_rooms
# recorded both as applied — the card, the history record and learning all agreed a
# setting had been sent that never left.
#
# Every prior test here uses the token "vacuum_mop", the one spelling that never
# broke, which is exactly why this shipped.

_MOP_CAPS = {
    "supports_mop_features": True,
    "supports_water_control": True,
    "supports_edge_mopping": True,
}


def _mop_room(spelling: str) -> dict:
    return {"1": {
        "room_id": 1, "name": "Kitchen", "enabled": True,
        "clean_mode": spelling, "fan_speed": "SynthMax",
        "water_level": "SynthWet", "edge_mopping": True,
    }}


@pytest.mark.parametrize(
    "spelling",
    ["vacuum_mop", "Vacuum and mop", "vacuum & mop", "VACUUM_MOP", "mop", "Mop"],
)
def test_payload_carries_mop_fields_for_every_spelling(spelling):
    """[QE-6c] water_level + edge_mopping reach the wire for any mop spelling."""
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        managed_rooms=_mop_room(spelling), queue_room_ids=[1],
        capabilities=_MOP_CAPS,
    )
    room = result["payload"]["rooms"][0]
    assert "water_level" in room, f"{spelling!r}: water_level never reached the payload"
    assert "edge_mopping" in room, f"{spelling!r}: edge_mopping never reached the payload"


@pytest.mark.parametrize("spelling", ["vacuum", "Vacuum"])
def test_payload_omits_mop_fields_for_a_vacuum_only_room(spelling):
    """[QE-6d] The other direction, so [QE-6c] cannot pass by writing them always.

    A gate 'fixed' by dropping the mode test entirely would satisfy [QE-6c] for all
    six spellings and put a water level on every vacuum-only run.
    """
    rooms = _mop_room(spelling)
    result = build_room_clean_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        managed_rooms=rooms, queue_room_ids=[1],
        capabilities=_MOP_CAPS,
    )
    room = result["payload"]["rooms"][0]
    assert "water_level" not in room
    assert "edge_mopping" not in room
