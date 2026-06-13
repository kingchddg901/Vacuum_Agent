"""Unit tests for mapping/tracker.py — pure _RoomConfidenceState + the
file-backed MappingTracker helpers (mock hass with tmp_path config_dir).

The position-listener wiring (register_vacuum / state-change events) needs a
real hass and is left to integration; everything here is deterministic.

Coverage targets
----------------
[MT-1]  _RoomConfidenceState.reset_room: sets room, zeroes counters.
[MT-2]  update: movement beyond threshold increments movement_count.
[MT-3]  update: movement below threshold does not increment.
[MT-4]  update: confidence = time_factor * move_factor (saturates at 1.0).
[MT-5]  reset_job: clears fired_rooms and all counters.
[MT-6]  _samples_tmp_path: sanitizes the vacuum slug.
[MT-7]  flush + load round-trips active samples.
[MT-8]  _load_samples_from_disk: map_id mismatch → None.
[MT-9]  _load_samples_from_disk: missing file → None.
[MT-10] _delete_samples_tmp_file: removes the temp file.
[MT-11] _raw_samples_path: slug suffix included when provided.
[MT-12] _find_raw_samples_path: finds existing archive, else None.
[MT-13] _append_raw_samples: writes a _meta header + the job entry.
[MT-14] _append_raw_samples: a second call appends another entry.
[MT-15] update_raw_samples_exclusion: flips the flag; False on no-match/empty id.
[MT-16] rebuild_room_bounds_from_archive: no archive → no_archive; else delegates.
[MT-17] end_job multi-room: attributes each sample to its containing room, archives only rooms above the min-runs gate.
[MT-18] _append_raw_samples rolloff: pins _meta header + baseline first entry, rolls off the middle, keeps most-recent MAX-1.
[MT-19] _append_raw_samples rolloff: headerless archive truncates to last MAX lines, no baseline pin.
[MT-20] end_job multi-room: a sample inside no room's bounds is dropped (orphan), never archived to any room.
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
    return MappingTracker(hass, MagicMock())


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

def test_samples_tmp_path(tracker, tmp_path):
    """[MT-6]"""
    path = tracker._samples_tmp_path(_VAC)
    assert path == (Path(tmp_path) / "eufy_vacuum" / "mapping"
                    / "vacuum_alfred" / "_samples_active.json")


def test_flush_load_roundtrip(tracker):
    """[MT-7]"""
    samples = [(1.0, 2.0), (3.0, 4.0)]
    tracker._flush_samples_to_disk(_VAC, _MAP, {"1": {}}, samples)
    loaded = tracker._load_samples_from_disk(_VAC, _MAP)
    assert loaded == samples


def test_load_map_mismatch(tracker):
    """[MT-8]"""
    tracker._flush_samples_to_disk(_VAC, _MAP, {}, [(1.0, 1.0)])
    assert tracker._load_samples_from_disk(_VAC, "99") is None


def test_load_missing(tracker):
    """[MT-9]"""
    assert tracker._load_samples_from_disk(_VAC, _MAP) is None


def test_delete_samples_tmp(tracker):
    """[MT-10]"""
    tracker._flush_samples_to_disk(_VAC, _MAP, {}, [(1.0, 1.0)])
    assert tracker._samples_tmp_path(_VAC).exists()
    tracker._delete_samples_tmp_file(_VAC)
    assert not tracker._samples_tmp_path(_VAC).exists()


# ---------------------------------------------------------------------------
# Raw-samples JSONL archive
# ---------------------------------------------------------------------------

def test_raw_samples_path_slug(tracker):
    """[MT-11]"""
    with_slug = tracker._raw_samples_path(_VAC, "3", "kitchen")
    without = tracker._raw_samples_path(_VAC, "3")
    assert with_slug.name == "raw_samples_room_3_kitchen.jsonl"
    assert without.name == "raw_samples_room_3.jsonl"


def test_find_raw_samples_path(tracker):
    """[MT-12]"""
    assert tracker._find_raw_samples_path(_VAC, "3") is None
    tracker._append_raw_samples(_VAC, _MAP, "3", "j1", "2026-01-01T10:00:00+00:00",
                                [(1.0, 1.0)], room_slug="kitchen")
    found = tracker._find_raw_samples_path(_VAC, "3")
    assert found is not None and found.name.startswith("raw_samples_room_3")


def test_append_raw_samples_header_and_entry(tracker):
    """[MT-13]"""
    tracker._append_raw_samples(_VAC, _MAP, "3", "j1", "2026-01-01T10:00:00+00:00",
                                [(1.0, 1.0)], room_slug="kitchen", room_name="Kitchen")
    path = tracker._find_raw_samples_path(_VAC, "3")
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert "_meta" in json.loads(lines[0])
    entry = json.loads(lines[1])
    assert entry["job_id"] == "j1"
    assert entry["room_id"] == "3"


def test_append_raw_samples_second_entry(tracker):
    """[MT-14]"""
    for jid in ("j1", "j2"):
        tracker._append_raw_samples(_VAC, _MAP, "3", jid, "2026-01-01T10:00:00+00:00",
                                    [(1.0, 1.0)], room_slug="kitchen")
    path = tracker._find_raw_samples_path(_VAC, "3")
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    job_ids = [json.loads(l).get("job_id") for l in lines[1:]]
    assert job_ids == ["j1", "j2"]


def test_update_exclusion(tracker):
    """[MT-15]"""
    tracker._append_raw_samples(_VAC, _MAP, "3", "j1", "2026-01-01T10:00:00+00:00",
                                [(1.0, 1.0)], room_slug="kitchen")
    assert tracker.update_raw_samples_exclusion(_VAC, "3", "j1", True) is True
    assert tracker.update_raw_samples_exclusion(_VAC, "3", "missing", True) is False
    assert tracker.update_raw_samples_exclusion(_VAC, "3", "", True) is False
    # verify the flag landed
    path = tracker._find_raw_samples_path(_VAC, "3")
    entries = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    job = next(e for e in entries if e.get("job_id") == "j1")
    assert job["excluded"] is True


def test_rebuild_from_archive(tracker):
    """[MT-16]"""
    # no archive yet
    result = tracker.rebuild_room_bounds_from_archive(_VAC, _MAP, "3")
    assert result == {"success": False, "reason": "no_archive", "room_id": "3"}

    # with an archive, delegates to the manager with parsed entries
    tracker._append_raw_samples(_VAC, _MAP, "3", "j1", "2026-01-01T10:00:00+00:00",
                                [(1.0, 1.0)], room_slug="kitchen")
    sentinel = {"success": True}
    tracker._manager.rebuild_room_bounds_from_archive.return_value = sentinel
    out = tracker.rebuild_room_bounds_from_archive(_VAC, _MAP, "3")
    assert out is sentinel
    tracker._manager.rebuild_room_bounds_from_archive.assert_called_once()


def test_end_job_multi_room_attribution(tmp_path: Path):
    """[MT-17] a multi-room job attributes each sample to the room whose bounds
    contain it, then archives only rooms above the min-runs confidence gate.

    Room 1 has 4 archived runs (>= MULTI_ROOM_MIN_RUNS) → its sample is archived.
    Room 2 has a single run (< gate) → it acts as an attribution trap and is
    skipped, exercising the low-confidence continue.
    """
    from custom_components.eufy_vacuum.mapping.manager import MappingManager

    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    mgr = MappingManager(hass)
    tracker = MappingTracker(hass, mgr)

    _MM = "mr"
    runs_1 = [{"job_id": f"a{i}", "recorded_at": "t", "samples": [[0, 0], [10, 10]]}
              for i in range(4)]
    runs_2 = [{"job_id": "b0", "recorded_at": "t", "samples": [[100, 100], [110, 110]]}]
    mgr.rebuild_room_bounds_from_archive(
        vacuum_entity_id=_VAC, map_id=_MM, room_id="1", archived_entries=runs_1)
    mgr.rebuild_room_bounds_from_archive(
        vacuum_entity_id=_VAC, map_id=_MM, room_id="2", archived_entries=runs_2)

    tracker.start_job(vacuum_entity_id=_VAC, map_id=_MM,
                      rooms={"1": {"name": "Kitchen"}, "2": {"name": "Bath"}})
    # one sample inside room 1's box, one inside room 2's box
    tracker._job_samples[_VAC] = [(5.0, 5.0), (105.0, 105.0)]
    tracker.end_job(vacuum_entity_id=_VAC)

    # room 1 cleared the gate → raw samples archived; room 2 (1 run) was skipped
    assert tracker._find_raw_samples_path(_VAC, "1") is not None
    assert tracker._find_raw_samples_path(_VAC, "2") is None


def test_append_raw_samples_rolloff_pins_header_and_baseline(tracker, monkeypatch):
    """[MT-18] beyond RAW_SAMPLES_MAX_LINES, _append_raw_samples pins the _meta
    header + the baseline first-job entry and rolls off the middle, keeping the
    most-recent (MAX-1) entries (covers the header-present rolloff, lines 371-373).

    With cap=3 and 5 jobs (job0..job4) the archive settles to:
    header + job0 (baseline) + job3 + job4 (newest). job1/job2 are dropped.
    """
    monkeypatch.setattr(MappingTracker, "RAW_SAMPLES_MAX_LINES", 3)

    for i in range(5):
        tracker._append_raw_samples(
            _VAC, _MAP, "3", f"job{i}", "2026-01-01T10:00:00+00:00",
            [(float(i), float(i))], room_slug="kitchen", room_name="Kitchen")

    path = tracker._find_raw_samples_path(_VAC, "3")
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    # (1) header pinned at index 0
    assert "_meta" in json.loads(lines[0])
    # (2) baseline first job pinned (NOT rolled off)
    job_entries = [json.loads(l) for l in lines[1:]]
    assert job_entries[0]["job_id"] == "job0"
    # (3) capped at exactly RAW_SAMPLES_MAX_LINES job entries (baseline + MAX-1 recent)
    assert len(job_entries) == 3
    # (4) newest kept, the rolled-off middle gone
    job_ids = [e["job_id"] for e in job_entries]
    assert job_ids == ["job0", "job3", "job4"]
    assert "job1" not in job_ids and "job2" not in job_ids


def test_append_raw_samples_rolloff_headerless_fallback(tracker, monkeypatch):
    """[MT-19] a pre-existing archive with no _meta header takes the elif
    fallback: it truncates to exactly the last RAW_SAMPLES_MAX_LINES lines with
    no baseline-pin behavior (covers lines 375-376).
    """
    monkeypatch.setattr(MappingTracker, "RAW_SAMPLES_MAX_LINES", 3)

    # Seed a headerless JSONL file (two plain entries, no _meta line).
    path = tracker._raw_samples_path(_VAC, "3", "kitchen")
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = [json.dumps({"job_id": f"seed{i}", "map_id": _MAP, "room_id": "3",
                        "recorded_at": "t", "samples": [[i, i]]}) for i in range(2)]
    path.write_text("\n".join(seed) + "\n", encoding="utf-8")

    for i in range(3):
        tracker._append_raw_samples(
            _VAC, _MAP, "3", f"new{i}", "2026-01-01T10:00:00+00:00",
            [(float(i), float(i))], room_slug="kitchen")

    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    entries = [json.loads(l) for l in lines]

    # truncated to exactly the last MAX lines, no header injected
    assert len(lines) == 3
    assert not any("_meta" in e for e in entries)
    # only the most-recent MAX entries survive; the seed lines rolled off, and
    # no baseline-pin keeps seed0 around (that's header-mode-only behavior)
    job_ids = [e["job_id"] for e in entries]
    assert job_ids == ["new0", "new1", "new2"]
    assert "seed0" not in job_ids and "seed1" not in job_ids


def test_end_job_multi_room_orphan_sample_dropped(tmp_path: Path):
    """[MT-20] a multi-room sample inside NO room's bounds is dropped, not archived.

    Covers the inner-loop exhaustion (tracker.py 559->558): when a sample matches
    no non-transition room's expanded bounds, the ``for rid`` loop falls through
    without break, so the sample is never added to ``attributed`` and lands in no
    room's archive. Room 1 clears MULTI_ROOM_MIN_RUNS so it archives a real entry;
    the orphan must be absent from every room file.
    """
    from custom_components.eufy_vacuum.mapping.manager import MappingManager

    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    mgr = MappingManager(hass)
    tracker = MappingTracker(hass, mgr)

    _MM = "mr"
    # Room 1: >= MULTI_ROOM_MIN_RUNS archived runs → clears the confidence gate
    # and gets a real bounds box around 0..10 (margin-expanded to ~ -50..60).
    runs_1 = [{"job_id": f"a{i}", "recorded_at": "t", "samples": [[0, 0], [10, 10]]}
              for i in range(4)]
    runs_2 = [{"job_id": f"b{i}", "recorded_at": "t", "samples": [[100, 100], [110, 110]]}
              for i in range(4)]
    mgr.rebuild_room_bounds_from_archive(
        vacuum_entity_id=_VAC, map_id=_MM, room_id="1", archived_entries=runs_1)
    mgr.rebuild_room_bounds_from_archive(
        vacuum_entity_id=_VAC, map_id=_MM, room_id="2", archived_entries=runs_2)

    tracker.start_job(vacuum_entity_id=_VAC, map_id=_MM,
                      rooms={"1": {"name": "Kitchen"}, "2": {"name": "Bath"}})
    # one sample inside room 1's box, one far outside EVERY room's bounds
    orphan = [9999.0, 9999.0]
    tracker._job_samples[_VAC] = [(5.0, 5.0), tuple(orphan)]
    tracker.end_job(vacuum_entity_id=_VAC)

    # (a) room 1 archived, and its only sample is the in-bounds [5, 5] — the
    #     orphan must NOT have been attributed to it.
    path_1 = tracker._find_raw_samples_path(_VAC, "1")
    assert path_1 is not None
    entries_1 = [json.loads(l) for l in path_1.read_text(encoding="utf-8").splitlines()
                 if l.strip() and "_meta" not in json.loads(l)]
    archived_1 = [s for e in entries_1 for s in e.get("samples", [])]
    assert archived_1 == [[5.0, 5.0]]

    # (b) the orphan appears in NO room's archive file anywhere.
    for rid in ("1", "2"):
        path = tracker._find_raw_samples_path(_VAC, rid)
        if path is None:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            assert orphan not in rec.get("samples", [])

