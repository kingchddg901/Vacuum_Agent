"""Unit tests for mapping/tracker.py — the pure _RoomConfidenceState machine
(mock hass with tmp_path config_dir).

The position-listener wiring (register_vacuum / state-change events) needs a
real hass and is left to integration; everything here is deterministic.

Coverage targets
----------------
[MT-1]  _RoomConfidenceState.reset_room: sets room, zeroes counters.
[MT-2]  update: movement beyond threshold increments movement_count.
[MT-3]  update: movement below threshold does not increment.
[MT-4]  update: confidence = time_factor * move_factor (saturates at 1.0).
[MT-5]  reset_job: clears fired_rooms and all counters.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.timestamp_utils import utc_now
from custom_components.eufy_vacuum.mapping.tracker import (
    MappingTracker,
    _RoomConfidenceState,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def tracker(tmp_path: Path) -> MappingTracker:
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    return MappingTracker(hass)


# ---------------------------------------------------------------------------
# _RoomConfidenceState
# ---------------------------------------------------------------------------

def test_reset_room():
    """[MT-1]"""
    state = _RoomConfidenceState()
    state.movement_count = 5
    state.reset_room("3")
    assert state.current_room_id == "3"
    assert state.movement_count == 0
    assert state.confidence == 0.0
    assert state.entered_at is not None


def test_update_movement_increments():
    """[MT-2]"""
    state = _RoomConfidenceState()
    state.reset_room("3")
    state.update(0.0, 0.0)       # sets last_position, no increment
    state.update(100.0, 0.0)     # jump of 100 >= threshold → +1
    assert state.movement_count == 1


def test_update_small_movement_ignored():
    """[MT-3]"""
    state = _RoomConfidenceState()
    state.reset_room("3")
    state.update(0.0, 0.0)
    state.update(5.0, 0.0)       # 5 < threshold
    assert state.movement_count == 0


def test_update_confidence_saturates():
    """[MT-4] 60s in room + 10 movements → confidence 1.0."""
    state = _RoomConfidenceState()
    state.reset_room("3")
    state.entered_at = utc_now() - timedelta(seconds=60)  # force time_factor=1.0
    for i in range(11):
        state.update(i * 100.0, 0.0)
    assert state.movement_count == 10
    assert state.confidence == pytest.approx(1.0)


def test_reset_job():
    """[MT-5]"""
    state = _RoomConfidenceState()
    state.reset_room("3")
    state.fired_rooms.add("3")
    state.reset_job()
    assert state.current_room_id is None
    assert state.fired_rooms == set()
    assert state.movement_count == 0


# ---------------------------------------------------------------------------
# Active-samples temp file
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Raw-samples JSONL archive
# ---------------------------------------------------------------------------
