"""Unit tests for mapping/trace_capture.py — in-memory capture sessions
(stop() persists via trace_store, exercised against tmp_path).

Coverage targets
----------------
[TC-1]  _make_run_id: trace_<ts>_<map>_<room> shape; sanitizes dots/spaces.
[TC-2]  _make_run_id: None room_id → "unassigned".
[TC-3]  _vacuum_slug: strips the domain, lowercases; no-dot passthrough.
[TC-4]  start: returns started=True and marks the session active.
[TC-5]  start: a second start discards the prior session (previous_cancelled).
[TC-6]  append_sample: appends rounded x/y when active; no session → False.
[TC-7]  stop: persists a TraceRun and reports the sample count + path.
[TC-8]  stop: no active session → stopped=False, reason no_active_session.
[TC-9]  cancel: discards without writing, reports discarded_samples.
[TC-10] cancel: no active session → cancelled=False.
[TC-11] is_active / active_session_summary reflect session state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.eufy_vacuum.mapping.trace_capture import (
    TraceCapture,
    _make_run_id,
    _vacuum_slug,
)
from custom_components.eufy_vacuum.mapping.trace_store import load_trace_run


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def capture(tmp_path: Path) -> TraceCapture:
    return TraceCapture(tmp_path)


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def test_make_run_id_shape():
    """[TC-1]"""
    run_id = _make_run_id("6.5", "living room")
    assert run_id.startswith("trace_")
    assert "6_5" in run_id
    assert "living_room" in run_id


def test_make_run_id_unassigned():
    """[TC-2]"""
    assert _make_run_id("6", None).endswith("_unassigned")


@pytest.mark.parametrize("entity,expected", [
    ("vacuum.Alfred", "alfred"),
    ("alfred", "alfred"),
    ("vacuum.living_room_bot", "living_room_bot"),
])
def test_vacuum_slug(entity, expected):
    """[TC-3]"""
    assert _vacuum_slug(entity) == expected


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def test_start_activates(capture):
    """[TC-4]"""
    result = capture.start(vacuum_entity_id=_VAC, map_id=_MAP, room_id="3")
    assert result["started"] is True
    assert result["previous_cancelled"] is False
    assert capture.is_active(vacuum_entity_id=_VAC, map_id=_MAP)


def test_start_replaces_previous(capture):
    """[TC-5]"""
    first = capture.start(vacuum_entity_id=_VAC, map_id=_MAP)
    second = capture.start(vacuum_entity_id=_VAC, map_id=_MAP)
    assert second["previous_cancelled"] is True
    assert second["previous_run_id"] == first["run_id"]


def test_append_sample(capture):
    """[TC-6]"""
    assert capture.append_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=1.0, y=2.0) is False
    capture.start(vacuum_entity_id=_VAC, map_id=_MAP)
    assert capture.append_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=1.23456, y=9.0) is True
    summary = capture.active_session_summary(vacuum_entity_id=_VAC, map_id=_MAP)
    assert summary["sample_count"] == 1


def test_stop_persists(capture, tmp_path):
    """[TC-7]"""
    start = capture.start(vacuum_entity_id=_VAC, map_id=_MAP, room_id="3")
    capture.append_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=1.0, y=1.0)
    capture.append_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=2.0, y=2.0)
    result = capture.stop(vacuum_entity_id=_VAC, map_id=_MAP)

    assert result["stopped"] is True
    assert result["sample_count"] == 2
    assert not capture.is_active(vacuum_entity_id=_VAC, map_id=_MAP)
    # the run was written and is reloadable
    loaded = load_trace_run(tmp_path, "alfred", start["run_id"])
    assert loaded is not None
    assert loaded["sample_count"] == 2
    assert loaded["room_id"] == "3"


def test_stop_no_session(capture):
    """[TC-8]"""
    result = capture.stop(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["stopped"] is False
    assert result["reason"] == "no_active_session"


def test_cancel_discards(capture):
    """[TC-9]"""
    capture.start(vacuum_entity_id=_VAC, map_id=_MAP)
    capture.append_sample(vacuum_entity_id=_VAC, map_id=_MAP, x=1.0, y=1.0)
    result = capture.cancel(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["cancelled"] is True
    assert result["discarded_samples"] == 1
    assert not capture.is_active(vacuum_entity_id=_VAC, map_id=_MAP)


def test_cancel_no_session(capture):
    """[TC-10]"""
    result = capture.cancel(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["cancelled"] is False
    assert result["reason"] == "no_active_session"


def test_is_active_and_summary(capture):
    """[TC-11]"""
    assert capture.active_session_summary(vacuum_entity_id=_VAC, map_id=_MAP) is None
    capture.start(vacuum_entity_id=_VAC, map_id=_MAP, room_id="7")
    summary = capture.active_session_summary(vacuum_entity_id=_VAC, map_id=_MAP)
    assert summary["room_id"] == "7"
    assert summary["sample_count"] == 0
