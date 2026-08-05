"""The 24-hour pose ring: chunking, retention, and time-range reads."""

from __future__ import annotations

import datetime as dt
import json
import os

from custom_components.eufy_vacuum import pose_store

UTC = dt.timezone.utc


def _at(h, m, s=0):
    return dt.datetime(2026, 8, 5, h, m, s, tzinfo=UTC)


def _write(tmp, when, room, anchor=(0.5, 0.5)):
    pose_store.append_sample(
        config_dir=str(tmp), vacuum_entity_id="vacuum.alfred",
        sample={"t": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "map_id": "12",
                "current_room": room, "anchor": list(anchor),
                "cleaning_area": 1.0, "heading": None},
        now=when,
    )


def _dir(tmp):
    return os.path.join(str(tmp), "eufy_vacuum", "pose", "alfred")


def test_samples_land_in_half_hour_chunks(tmp_path):
    """One file per half hour, named by its start — so expiry is an unlink rather
    than rewriting a file the sampler is still appending to."""
    _write(tmp_path, _at(6, 5), 5)
    _write(tmp_path, _at(6, 29, 59), 5)
    _write(tmp_path, _at(6, 30), 8)
    names = sorted(os.listdir(_dir(tmp_path)))
    assert names == ["2026-08-05T06-00.jsonl", "2026-08-05T06-30.jsonl"]
    first = open(os.path.join(_dir(tmp_path), names[0]), encoding="utf-8").read().strip().splitlines()
    assert len(first) == 2, "both pre-06:30 samples share one chunk"


def test_a_chunk_is_pruned_by_its_END_not_its_start(tmp_path):
    """The chunk being written must never be a prune candidate.

    A chunk named 06-00 COVERS 06:00-06:30, so it only expires 24 h after 06:30,
    not 24 h after 06:00. Judging by start alone would delete it half an hour
    early — and for the LIVE chunk that means discarding samples written seconds
    ago. Both sides are asserted, because only the surviving case proves the
    distinction.
    """
    _write(tmp_path, _at(6, 0), 5)

    # 24h01m after the chunk STARTED — its end (06:30) is still inside retention.
    _write(tmp_path, _at(6, 0) + dt.timedelta(hours=24, minutes=1), 8)
    assert "2026-08-05T06-00.jsonl" in os.listdir(_dir(tmp_path)),         "pruned by start — would drop a chunk half an hour early"

    # 24h31m after the start, i.e. past 24 h after its 06:30 end.
    _write(tmp_path, _at(6, 0) + dt.timedelta(hours=24, minutes=31), 9)
    assert "2026-08-05T06-00.jsonl" not in os.listdir(_dir(tmp_path))


def test_retention_keeps_a_full_day(tmp_path):
    """23 hours old stays; 25 hours old goes."""
    now = _at(12, 0)
    _write(tmp_path, now - dt.timedelta(hours=25), 1)
    _write(tmp_path, now - dt.timedelta(hours=23), 2)
    _write(tmp_path, now, 3)
    rooms = [r["current_room"] for r in pose_store.read_range(
        config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred",
        start_iso="2026-08-01T00:00:00Z", end_iso="2026-08-09T00:00:00Z")]
    assert 1 not in rooms and 2 in rooms and 3 in rooms


def test_read_range_answers_a_transit_window(tmp_path):
    """THE point of the module: finalize asks 'what happened between T0 and T1'
    instead of owning a buffer. Modelled on the real 2026-08-05 Kitchen->Entryway
    transit, where the answer was 17 s of egress then 20 s of travel."""
    for sec, room in ((55, 5), (57, 5), (59, 7), (61, 7), (63, 6), (65, 8), (67, 8)):
        _write(tmp_path, _at(6, 31) + dt.timedelta(seconds=sec), room)
    got = pose_store.read_range(
        config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred",
        start_iso="2026-08-05T06:31:56Z", end_iso="2026-08-05T06:32:04Z")
    assert [r["current_room"] for r in got] == [5, 7, 7, 6]
    assert got == sorted(got, key=lambda r: r["t"]), "must come back in order"


def test_read_range_spans_chunk_boundaries(tmp_path):
    """A window straddling 06:30 must not lose the half of it in the other file."""
    _write(tmp_path, _at(6, 29, 50), 5)
    _write(tmp_path, _at(6, 30, 10), 8)
    got = pose_store.read_range(
        config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred",
        start_iso="2026-08-05T06:29:00Z", end_iso="2026-08-05T06:31:00Z")
    assert [r["current_room"] for r in got] == [5, 8]


def test_a_torn_line_does_not_poison_the_read(tmp_path):
    """A hard stop mid-append leaves a partial final line. It must be skipped, not
    raise — this is an observability side-channel and may never break a caller."""
    _write(tmp_path, _at(6, 5), 5)
    path = os.path.join(_dir(tmp_path), "2026-08-05T06-00.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"t": "2026-08-05T06:06:00Z", "curr')
    got = pose_store.read_range(
        config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred",
        start_iso="2026-08-05T06:00:00Z", end_iso="2026-08-05T07:00:00Z")
    assert len(got) == 1


def test_foreign_files_are_never_deleted(tmp_path):
    """Prune only touches files it named. A stray file in the directory is not
    ours to remove."""
    _write(tmp_path, _at(6, 0), 5)
    stray = os.path.join(_dir(tmp_path), "notes.txt")
    with open(stray, "w", encoding="utf-8") as fh:
        fh.write("keep me")
    pose_store.prune(config_dir=str(tmp_path), vacuum_entity_id="vacuum.alfred",
                     now=_at(6, 0) + dt.timedelta(days=30))
    assert os.path.exists(stray)


def test_missing_directory_reads_empty_rather_than_raising(tmp_path):
    assert pose_store.read_range(
        config_dir=str(tmp_path), vacuum_entity_id="vacuum.nope",
        start_iso="2026-08-05T00:00:00Z", end_iso="2026-08-06T00:00:00Z") == []
