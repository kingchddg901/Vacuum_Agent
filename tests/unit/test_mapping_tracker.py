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

The dock-drift compaction (MT-6..MT-12), from the 2026-11-07 coverage pass. It was
the whole of `_compact_dock_drift` plus its trigger and the OSError guard -- eleven
statements, no tests, and a docstring citing TRK-6 as though pinned.
[MT-6]  compaction keeps the `_meta` header first and the NEWEST body entries.
[MT-7]  a log with no header is trimmed from the end (the `elif` arm).
[MT-8]  a log under the cap survives the rewrite byte-identical.
[MT-9]  the rewrite goes through a `.tmp` and leaves no sibling behind.
[MT-10] the trigger fires ONLY past the byte threshold -- both directions.
[MT-11] a failed compaction does not undo the append (housekeeping, not the event).
[MT-12] the two constants keep the relationship the code's own comment states.
[MT-13] an unwritable log returns False so the caller re-queues (NOT pragma'd --
        the pragma there covers the logger call only, which is verified).
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


# ---------------------------------------------------------------------------
# [MT-6]..[MT-12] -- the dock-drift compaction, which had NO tests at all.
#
# `_compact_dock_drift` was eleven uncovered statements: the whole function, plus
# its trigger and the OSError guard around it. Its own docstring cites TRK-6 as
# though pinned. It is the lowest-coverage region of mapping/tracker.py (84%) and
# the gap is not an `except` arm -- it is file-rolling logic with a silent failure
# mode. Lose the `_meta` header and the log stops saying which vacuum it belongs
# to; trim the wrong end and the drift timeline keeps the OLDEST readings and
# discards the ones that show current drift; leave the `.tmp` behind and the next
# compaction reads a half-written file.
#
# THE CAP IS PATCHED PER TEST, which means these do NOT fence its VALUE -- only the
# mechanism. That is deliberate: 5000 lines is a disk-space tunable, not a
# contract, and writing 5001 real lines per test to pin it would buy nothing.
# [MT-12] is what pins the numbers, through the relationship the code's own comment
# states between them.
# ---------------------------------------------------------------------------


def _write_log(path: Path, *, meta: bool, body_lines: int) -> None:
    """A dock-drift JSONL shaped like the real one, with numbered body entries.

    The entries are numbered so a trim can be checked for WHICH end it kept --
    asserting only the line count would pass a function that discarded the newest
    readings, which is the failure that matters for a drift timeline.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if meta:
        lines.append(json.dumps({"_meta": "eufy_vacuum dock-coordinate drift log",
                                 "vacuum": _VAC}))
    for i in range(body_lines):
        lines.append(json.dumps({"ts": f"2026-11-07T00:00:{i:02d}Z", "n": i}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _body(path: Path) -> list[dict]:
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if "_meta" not in r]


def test_mt6_compaction_keeps_the_meta_header_and_the_newest_entries(tracker, tmp_path):
    """[MT-6] The header stays line ONE and the trim keeps the NEWEST body entries.

    Both halves matter and a line-count assertion would miss each of them. The
    header carries which vacuum the log belongs to, so losing it makes an archived
    file unattributable. And a drift timeline trimmed from the wrong end keeps the
    readings from when the device was freshly localized and throws away the ones
    showing the drift that has accumulated -- the exact opposite of its purpose.
    """
    tracker.DOCK_DRIFT_MAX_LINES = 4
    path = tracker._dock_drift_path(_VAC)
    _write_log(path, meta=True, body_lines=10)

    tracker._compact_dock_drift(path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert '"_meta"' in lines[0], "the header must still be the FIRST line"
    assert len(lines) == 5, "header + the capped 4 body lines"
    assert [r["n"] for r in _body(path)] == [6, 7, 8, 9], (
        "the NEWEST four entries survive; keeping [0,1,2,3] would discard exactly "
        "the drift the log exists to show"
    )


def test_mt7_a_log_with_no_header_is_trimmed_from_the_end(tracker, tmp_path):
    """[MT-7] The `elif` arm: no `_meta` line, so the whole file is the body.

    A real file always gets a header on creation, but an externally truncated or
    hand-edited log will not have one, and that is the branch. Distinct from [MT-6]
    because the slicing is done on a different list -- `existing` rather than
    `existing[1:]` -- and an off-by-one there is invisible to the header case.
    """
    tracker.DOCK_DRIFT_MAX_LINES = 3
    path = tracker._dock_drift_path(_VAC)
    _write_log(path, meta=False, body_lines=8)

    tracker._compact_dock_drift(path)

    rows = _body(path)
    assert len(rows) == 3
    assert [r["n"] for r in rows] == [5, 6, 7]


def test_mt8_a_log_under_the_cap_survives_compaction_unchanged(tracker, tmp_path):
    """[MT-8] Neither trim branch taken: the rewrite must be faithful.

    Compaction still reads and rewrites the whole file in this case, so "it did
    nothing" is not free -- a rewrite that dropped the trailing newline, reordered,
    or lost a row would corrupt a log that never needed touching. Asserted on the
    exact bytes for that reason.
    """
    tracker.DOCK_DRIFT_MAX_LINES = 100
    path = tracker._dock_drift_path(_VAC)
    _write_log(path, meta=True, body_lines=5)
    before = path.read_text(encoding="utf-8")

    tracker._compact_dock_drift(path)

    assert path.read_text(encoding="utf-8") == before


def test_mt9_compaction_leaves_no_temp_file_behind(tracker, tmp_path):
    """[MT-9] The write goes through a `.tmp` and is MOVED into place.

    The atomicity is the point: a reader (or the next append) that caught a partial
    rewrite would see a truncated JSONL. `Path.replace` is atomic on the same
    filesystem, and the sibling must not survive -- a leftover `.tmp` is both a
    stale artifact and the signature of a rewrite that did not complete.
    """
    tracker.DOCK_DRIFT_MAX_LINES = 2
    path = tracker._dock_drift_path(_VAC)
    _write_log(path, meta=True, body_lines=6)

    tracker._compact_dock_drift(path)

    assert path.exists()
    assert not path.with_suffix(".tmp").exists(), "the temp sibling must be gone"
    assert list(path.parent.iterdir()) == [path], "and nothing else left in the dir"


def test_mt10_the_trigger_fires_only_past_the_byte_threshold(tracker, tmp_path):
    """[MT-10] TRK-6's actual claim: a normal append does NOT read+rewrite the file.

    BOTH DIRECTIONS, because one alone proves nothing. With the shipped threshold a
    single append must not compact -- that is the whole performance argument for the
    O(1) append path. With the threshold lowered it must. A trigger tested only on
    the firing side would pass just as happily if it fired on every event.
    """
    calls: list = []
    tracker._compact_dock_drift = lambda p: calls.append(p)

    assert tracker._append_dock_drift(_VAC, 1.0, 2.0, "docked", None, None) is True
    assert calls == [], (
        "a fresh small log is far under DOCK_DRIFT_COMPACT_BYTES, so compaction "
        "must not run -- appends are meant to be cheap"
    )

    tracker.DOCK_DRIFT_COMPACT_BYTES = 10          # smaller than the header alone
    assert tracker._append_dock_drift(_VAC, 3.0, 4.0, "docked", 2.0, 2.0) is True
    assert len(calls) == 1, "past the threshold it must run"
    assert calls[0] == tracker._dock_drift_path(_VAC)


def test_mt11_a_failed_compaction_does_not_undo_the_append(tracker, tmp_path):
    """[MT-11] Compaction is housekeeping: its failure must not lose the reading.

    The guard's polarity is the test. `_append_dock_drift` returns True/False and
    the caller commits the new last-known dock position ONLY on True -- so if an
    OSError from the housekeeping pass escaped to the outer handler, the function
    would return False, the position would not commit, and the event would be
    re-detected and re-appended on the next reading. The reading itself is already
    safely on disk by then, which is why swallowing is right here.
    """
    def _boom(_path):
        raise OSError("disk full during compaction")

    tracker._compact_dock_drift = _boom
    tracker.DOCK_DRIFT_COMPACT_BYTES = 10

    ok = tracker._append_dock_drift(_VAC, 7.0, 8.0, "docked", 1.0, 1.0)

    assert ok is True, "a failed housekeeping pass must not report the append failed"
    rows = _body(tracker._dock_drift_path(_VAC))
    assert rows and rows[-1]["vx"] == 7.0 and rows[-1]["vy"] == 8.0, (
        "and the appended reading must still be on disk"
    )


def test_mt12_the_two_dock_drift_constants_keep_their_stated_relationship(tracker):
    """[MT-12] The numbers the other tests patch away, pinned where they are stated.

    [MT-6]..[MT-9] patch the cap, so none of them notices it moving -- which is
    correct for a disk tunable but leaves the VALUES unfenced. The code states the
    relationship itself, in the comment above DOCK_DRIFT_COMPACT_BYTES:
    "~80 bytes/line * DOCK_DRIFT_MAX_LINES * ~1.5 headroom". That is not decoration,
    it is why the threshold is large enough that a file reaching it genuinely has
    more than MAX_LINES rows -- raise MAX_LINES alone and compaction starts firing
    on files that do not need trimming (a read+rewrite per append, the cost TRK-6
    exists to avoid); raise the byte threshold alone and the log grows unbounded
    between compactions.

    Asserted as the exact product because that is what the comment says and what the
    shipped values are. If either number is changed deliberately, this is the line
    that says the other one has to move with it.
    """
    assert MappingTracker.DOCK_DRIFT_COMPACT_BYTES == int(
        80 * MappingTracker.DOCK_DRIFT_MAX_LINES * 1.5
    ), (
        "the comment above DOCK_DRIFT_COMPACT_BYTES derives it from "
        "DOCK_DRIFT_MAX_LINES; they have drifted apart"
    )
def test_mt13_an_unwritable_log_reports_failure_rather_than_raising(tracker, tmp_path):
    """[MT-13] A write that cannot happen returns False, so the caller re-queues.

    The broad `except Exception` around the append exists because the return value is
    load-bearing: `_log_dock_drift_and_commit` advances the last-known dock position
    ONLY on True, so a False keeps the old baseline and the same drift is re-detected
    on the next reading instead of being silently lost (TRK-6).

    Tested rather than pragma'd. The `# pragma: no cover` in that handler covers the
    _LOGGER.exception call and only that -- verified: coverage excludes line 310 and
    not the `except` or the `return False`. A logger line is fair to exclude; the
    return value is behaviour.

    The failure is induced without patching: a FILE sits where the log directory needs
    to be, so `mkdir(parents=True)` raises. That is a real shape -- a stray file in the
    mapping tree -- rather than a mock that can only fail the way I imagined.
    """
    path = tracker._dock_drift_path(_VAC)
    path.parent.parent.mkdir(parents=True, exist_ok=True)
    path.parent.write_text("not a directory", encoding="utf-8")

    ok = tracker._append_dock_drift(_VAC, 1.0, 2.0, "docked", None, None)

    assert ok is False, (
        "the caller commits the new dock baseline only on True; a swallowed failure "
        "that returned True would advance the baseline and lose the drift event"
    )
