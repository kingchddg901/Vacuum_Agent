"""Tests for services/_common.py — the map_id auto-resolver + job-finished payload.

resolved_call_data substitutes the vacuum's active map when the caller omits
map_id; job_finished_event_payload builds the EVENT_JOB_FINISHED payload from a
finalize result, with defensive guards for malformed / finalize_result-wrapped data.

Coverage targets
----------------
[SC-1]  map_id already present → returned unchanged.
[SC-2]  no vacuum_entity_id → returned unchanged.
[SC-3]  map_id omitted → resolved from the active_map entity state.
[SC-4]  map_id omitted but no active map resolves → map_id NOT added (pass-through;
        downstream raises its own clear error on the missing kwarg).
[SC-5]  job_finished_event_payload: a non-dict completed_job degrades to {}.
[SC-6]  job_finished_event_payload: job_path absent at root → taken from finalize_result.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.services._common import (
    job_finished_event_payload,
    resolved_call_data,
)


_VAC = "vacuum.alfred"


class _Call:
    def __init__(self, data):
        self.data = data


def test_resolved_passthrough_map_id(hass):
    """[SC-1]"""
    out = resolved_call_data(hass, _Call({"vacuum_entity_id": _VAC, "map_id": "6"}))
    assert out["map_id"] == "6"


def test_resolved_no_vacuum(hass):
    """[SC-2]"""
    out = resolved_call_data(hass, _Call({"foo": "bar"}))
    assert out == {"foo": "bar"}


def test_resolved_active_map(hass):
    """[SC-3]"""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_map"}})
    hass.states.async_set("sensor.alfred_map", "9")
    out = resolved_call_data(hass, _Call({"vacuum_entity_id": _VAC}))
    assert out["map_id"] == "9"


def test_resolved_no_active_map_passthrough(hass):
    """[SC-4] no active map resolves -> map_id is NOT added (downstream raises its own error)."""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t", "entities": {}})  # no active_map entity
    out = resolved_call_data(hass, _Call({"vacuum_entity_id": _VAC}))
    assert "map_id" not in out
    assert out == {"vacuum_entity_id": _VAC}


def test_job_finished_non_dict_completed_job():
    """[SC-5] a non-dict completed_job degrades to {} -> the payload uses defaults."""
    payload = job_finished_event_payload(
        vacuum_entity_id=_VAC,
        map_id="6",
        result={"completed_job": "oops-not-a-dict", "job_path": "/p"},
    )
    assert payload["status"] == "completed"   # outcome from the empty completed_job
    assert payload["finalized_at"] is None
    assert payload["room_count"] is None
    assert payload["job_path"] == "/p"


def test_job_finished_job_path_from_finalize_result():
    """[SC-6] job_path absent at root but present in finalize_result -> taken from the wrapper."""
    payload = job_finished_event_payload(
        vacuum_entity_id=_VAC,
        map_id="6",
        result={
            "finalize_result": {
                "completed_job": {"outcome": {"status": "ok"}},
                "job_path": "/from/finalize",
            }
        },
    )
    assert payload["job_path"] == "/from/finalize"
    assert payload["status"] == "ok"          # completed_job resolved from finalize_result
