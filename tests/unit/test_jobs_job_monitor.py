"""Unit tests for jobs/job_monitor.py — pure lifecycle evaluation, no HA dependency.

Coverage targets
----------------
[JM-1]  _norm lowercases and strips.
[JM-2]  _norm maps sentinel values (unknown/unavailable/none) to "".
[JM-3]  _norm maps None/falsy to "".
[JM-4]  build_job_metadata_from_payload: None payload → empty defaults.
[JM-5]  build_job_metadata_from_payload: extracts room_ids, slugs, clean_modes.
[JM-6]  build_job_metadata_from_payload: non-dict rooms and bad room_id skipped.
[JM-7]  build_job_metadata_from_payload: has_mop_mode true when a mode contains "mop".
[JM-8]  build_job_metadata_from_payload: has_vacuum_only_mode true for vacuum modes.
[JM-9]  build_job_metadata_from_payload: map_id pulled from the payload sub-dict.
[JM-10] build_job_metadata_from_payload: non-list resolved_rooms / non-dict payload coerced.
[JM-11] evaluate_job_lifecycle: selected != active map → map_mismatch (blocking).
[JM-12] evaluate_job_lifecycle: hard_service_states → mid_job_service (blocking).
[JM-13] evaluate_job_lifecycle: drying_states → dock_drying (non-blocking warning).
[JM-14] evaluate_job_lifecycle: active job + active_cleaning_target → active_job_running.
[JM-15] evaluate_job_lifecycle: active job + task in active_run_task_states → active_job_running.
[JM-16] evaluate_job_lifecycle: active job + vacuum in active_vacuum_states → active_job_running.
[JM-17] evaluate_job_lifecycle: no active job, task in active_run_task_states → vacuum_busy.
[JM-18] evaluate_job_lifecycle: unknown busy vacuum_state → vacuum_busy.
[JM-19] evaluate_job_lifecycle: clean idle state → ready.
[JM-20] evaluate_job_lifecycle: hard_service takes precedence over drying.
[JM-21] evaluate_job_lifecycle: job_metadata is echoed through.
[JM-22] build_start_blocker_from_lifecycle: empty selected map → no_target_map.
[JM-23] build_start_blocker_from_lifecycle: selected != active → map_mismatch.
[JM-24] build_start_blocker_from_lifecycle: empty queue → no_rooms_selected.
[JM-25] build_start_blocker_from_lifecycle: payload_room_count <= 0 → invalid_payload.
[JM-26] build_start_blocker_from_lifecycle: mid_job_service passthrough.
[JM-27] build_start_blocker_from_lifecycle: active_job_running passthrough.
[JM-28] build_start_blocker_from_lifecycle: vacuum_busy passthrough.
[JM-29] build_start_blocker_from_lifecycle: dock_drying → blocked False + warning.
[JM-30] build_start_blocker_from_lifecycle: ready state → blocked False.
[JM-31] build_start_blocker_from_lifecycle: empty lifecycle_message falls back to default.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.jobs.job_monitor import (
    _norm,
    build_job_metadata_from_payload,
    build_start_blocker_from_lifecycle,
    evaluate_job_lifecycle,
)


# ---------------------------------------------------------------------------
# _norm
# ---------------------------------------------------------------------------

def test_norm_lowercases_and_strips():
    """[JM-1]"""
    assert _norm("  Cleaning ") == "cleaning"


@pytest.mark.parametrize("sentinel", ["unknown", "unavailable", "none", "UNKNOWN", " None "])
def test_norm_sentinels_to_empty(sentinel):
    """[JM-2]"""
    assert _norm(sentinel) == ""


def test_norm_none_to_empty():
    """[JM-3]"""
    assert _norm(None) == ""
    assert _norm("") == ""


# ---------------------------------------------------------------------------
# build_job_metadata_from_payload
# ---------------------------------------------------------------------------

def test_metadata_none_payload_defaults():
    """[JM-4]"""
    meta = build_job_metadata_from_payload(None)
    assert meta["room_count"] == 0
    assert meta["room_ids"] == []
    assert meta["room_slugs"] == []
    assert meta["clean_modes"] == []
    assert meta["map_id"] is None
    assert meta["has_mop_mode"] is False
    assert meta["has_vacuum_only_mode"] is False


def test_metadata_extracts_rooms():
    """[JM-5]"""
    meta = build_job_metadata_from_payload({
        "resolved_rooms": [
            {"room_id": 1, "slug": "Kitchen", "clean_mode": "Vacuum"},
            {"room_id": 2, "slug": "Bath", "clean_mode": "mop"},
        ],
        "payload": {"map_id": "6"},
    })
    assert meta["room_count"] == 2
    assert meta["room_ids"] == [1, 2]
    assert meta["room_slugs"] == ["kitchen", "bath"]
    assert meta["clean_modes"] == ["vacuum", "mop"]


def test_metadata_skips_bad_entries():
    """[JM-6] non-dict rooms and unparseable room_id are skipped."""
    meta = build_job_metadata_from_payload({
        "resolved_rooms": [
            "not-a-dict",
            {"room_id": "abc", "slug": "x", "clean_mode": "vacuum"},  # bad id, kept slug/mode
            {"room_id": 3},  # no slug/mode
        ],
    })
    # "not-a-dict" excluded from id/slug/mode but still counts toward room_count
    assert meta["room_count"] == 3
    assert meta["room_ids"] == [3]
    assert meta["room_slugs"] == ["x"]
    assert meta["clean_modes"] == ["vacuum"]


def test_metadata_has_mop_mode():
    """[JM-7]"""
    meta = build_job_metadata_from_payload({
        "resolved_rooms": [{"room_id": 1, "clean_mode": "vacuum_and_mop"}],
    })
    assert meta["has_mop_mode"] is True
    assert meta["has_vacuum_only_mode"] is False


@pytest.mark.parametrize("mode", ["vacuum", "vacuum only"])
def test_metadata_has_vacuum_only_mode(mode):
    """[JM-8]"""
    meta = build_job_metadata_from_payload({
        "resolved_rooms": [{"room_id": 1, "clean_mode": mode}],
    })
    assert meta["has_vacuum_only_mode"] is True


def test_metadata_map_id_from_payload():
    """[JM-9]"""
    meta = build_job_metadata_from_payload({"payload": {"map_id": "12"}})
    assert meta["map_id"] == "12"


def test_metadata_coerces_bad_containers():
    """[JM-10] non-list resolved_rooms and non-dict payload do not raise."""
    meta = build_job_metadata_from_payload({"resolved_rooms": "nope", "payload": 5})
    assert meta["room_count"] == 0
    assert meta["map_id"] is None


# ---------------------------------------------------------------------------
# evaluate_job_lifecycle
# ---------------------------------------------------------------------------

def _eval(**overrides):
    base = dict(
        active_job_exists=False,
        active_cleaning_target=None,
        vacuum_state="docked",
        task_status=None,
        dock_status=None,
        active_map_id="6",
        selected_map_id="6",
    )
    base.update(overrides)
    return evaluate_job_lifecycle(**base)


def test_lifecycle_map_mismatch():
    """[JM-11]"""
    result = _eval(selected_map_id="6", active_map_id="7")
    assert result["lifecycle_state"] == "map_mismatch"
    assert result["blocking"] is True


def test_lifecycle_mid_job_service():
    """[JM-12]"""
    result = _eval(dock_status="washing", hard_service_states=frozenset({"washing"}))
    assert result["lifecycle_state"] == "mid_job_service"
    assert result["blocking"] is True


def test_lifecycle_dock_drying_non_blocking():
    """[JM-13]"""
    result = _eval(dock_status="drying", drying_states=frozenset({"drying"}))
    assert result["lifecycle_state"] == "dock_drying"
    assert result["blocking"] is False
    assert result["warning"] is True


def test_lifecycle_active_job_running_via_target():
    """[JM-14]"""
    result = _eval(active_job_exists=True, active_cleaning_target="room_3")
    assert result["lifecycle_state"] == "active_job_running"
    assert result["blocking"] is True


def test_lifecycle_active_job_running_via_task():
    """[JM-15]"""
    result = _eval(
        active_job_exists=True, task_status="room_clean",
        active_run_task_states=frozenset({"room_clean"}),
    )
    assert result["lifecycle_state"] == "active_job_running"


def test_lifecycle_active_job_running_via_vacuum_state():
    """[JM-16]"""
    result = _eval(active_job_exists=True, vacuum_state="cleaning")
    assert result["lifecycle_state"] == "active_job_running"


def test_lifecycle_vacuum_busy_via_task_no_active_job():
    """[JM-17]"""
    result = _eval(
        active_job_exists=False, vacuum_state="idle", task_status="auto_clean",
        active_run_task_states=frozenset({"auto_clean"}),
    )
    assert result["lifecycle_state"] == "vacuum_busy"
    assert result["blocking"] is True


def test_lifecycle_vacuum_busy_unknown_state():
    """[JM-18] a non-idle, non-active vacuum state blocks as vacuum_busy."""
    result = _eval(vacuum_state="mapping")
    assert result["lifecycle_state"] == "vacuum_busy"


def test_lifecycle_ready():
    """[JM-19]"""
    result = _eval(vacuum_state="docked")
    assert result["lifecycle_state"] == "ready"
    assert result["blocking"] is False


def test_lifecycle_hard_service_precedes_drying():
    """[JM-20] when a state is in both sets, hard service wins (checked first)."""
    result = _eval(
        dock_status="washing",
        hard_service_states=frozenset({"washing"}),
        drying_states=frozenset({"washing"}),
    )
    assert result["lifecycle_state"] == "mid_job_service"


def test_lifecycle_metadata_passthrough():
    """[JM-21]"""
    meta = {"room_count": 2}
    result = _eval(job_metadata=meta)
    assert result["job_metadata"] == meta


# ---------------------------------------------------------------------------
# build_start_blocker_from_lifecycle
# ---------------------------------------------------------------------------

def _blocker(**overrides):
    base = dict(
        lifecycle_state="ready",
        lifecycle_message="",
        selected_map_id="6",
        active_map_id="6",
        queue_room_ids=[1, 2],
        payload_room_count=2,
    )
    base.update(overrides)
    return build_start_blocker_from_lifecycle(**base)


def test_blocker_no_target_map():
    """[JM-22]"""
    result = _blocker(selected_map_id="")
    assert result["reason"] == "no_target_map"
    assert result["blocked"] is True


def test_blocker_map_mismatch():
    """[JM-23]"""
    result = _blocker(selected_map_id="6", active_map_id="7")
    assert result["reason"] == "map_mismatch"
    assert result["blocked"] is True


def test_blocker_no_rooms_selected():
    """[JM-24]"""
    result = _blocker(queue_room_ids=[])
    assert result["reason"] == "no_rooms_selected"


def test_blocker_invalid_payload():
    """[JM-25]"""
    result = _blocker(payload_room_count=0)
    assert result["reason"] == "invalid_payload"


def test_blocker_mid_job_service_passthrough():
    """[JM-26]"""
    result = _blocker(lifecycle_state="mid_job_service")
    assert result["reason"] == "mid_job_service"
    assert result["blocked"] is True


def test_blocker_active_job_running_passthrough():
    """[JM-27]"""
    result = _blocker(lifecycle_state="active_job_running")
    assert result["reason"] == "active_job_running"


def test_blocker_vacuum_busy_passthrough():
    """[JM-28]"""
    result = _blocker(lifecycle_state="vacuum_busy")
    assert result["reason"] == "vacuum_busy"


def test_blocker_dock_drying_warns_not_blocks():
    """[JM-29]"""
    result = _blocker(lifecycle_state="dock_drying")
    assert result["reason"] == "dock_drying"
    assert result["blocked"] is False
    assert result["warning"] is True


def test_blocker_ready():
    """[JM-30]"""
    result = _blocker(lifecycle_state="ready")
    assert result["reason"] == "ready"
    assert result["blocked"] is False


def test_blocker_message_fallback():
    """[JM-31] an empty lifecycle_message falls back to the canned default."""
    result = _blocker(lifecycle_state="vacuum_busy", lifecycle_message="")
    assert result["message"] == "Vacuum is busy and cannot start a new room job."
