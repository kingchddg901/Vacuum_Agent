"""Tests for the external-run review sub-methods on core/manager.py.

The 2496-2943 external-run capture/review orchestration block has two halves:
the capture/grace-finalize machinery (covered by EXT-1..EXT-5 in
``test_manager_lifecycle_status``) and the review-wizard helpers the card calls
once a run has been captured. This module covers the latter, one helper per
class, driven against the real ``manager`` fixture with real on-disk pending
records under the per-vacuum learning root.

Coverage targets
----------------
[DXR-1]  discard_external_run: deletes external_jobs/<id>.json and reports
         {'ok': True, 'pending_job_id': <id>}; a second discard of the now-absent
         id is still ok (missing_ok unlink), so a double-click never errors.
[EXT-FIN-1]  _finalize_external_run (driven via the grace timer): a captured
         external run with buffered samples is segmented, the pending record is
         written to external_jobs/job_<ts>.json with the return-overhead stamp,
         the EVENT_EXTERNAL_RUN_PENDING event fires carrying record_path +
         segment_count, and the capture slot is cleared. (No room_stats.json on
         disk → the missing-baselines except branch is exercised for free.)
[ERO-1]  _extract_return_overhead: unparseable / out-of-order timestamps
         short-circuit to the empty result before any recorder read
         (manager.py lines 2658-2659).
[ERO-2]  _extract_return_overhead: a cleaning→docked→cleaning state walk books
         the single docked span as overhead and surfaces one return-intervals
         row (the accumulation, lines 2660-2690). The bare-except defensive arm
         (2691-2693) is left unasserted by design — it has no observable
         behaviour distinct from [ERO-1] and faulting recorder internals to
         reach it would be a brittle white-box test.
[CXR-1]  confirm_external_run: a missing pending file → {'ok': False,
         'error': 'pending_not_found'} (manager 2801-2802).
[CXR-2]  confirm_external_run: an override assignment graduates the run — writes
         jobs/<id>.json, unlinks the pending file, and returns ok / job_id (ext-)
         / rooms_learned==1 / rebuilt is False (manager 2827-2860).
[CXR-3]  confirm_external_run: a no-override assignment whose segment area is far
         outside the room's mature learned band → build_graduated_job blocks:
         {'ok': False, 'blocked': [...]} and nothing is graduated (manager
         2824-2825).
[RXR-1]  resegment_external_run: a missing/corrupt pending file → {'ok': False,
         'error': 'pending_not_found'} (manager.py:2922-2923); no file made.
[RXR-2]  resegment_external_run: a v1 record (samples stripped) →
         {'ok': False, 'error': 'not_resegmentable', 'reason': 'no_samples'}
         (2924-2925); the file is left untouched.
[RXR-3]  resegment_external_run: a v2 record with NO room_stats.json on disk
         re-segments successfully — the baseline-read except falls back to
         baselines=[] (2929-2932) and the record is rewritten in place.
[RXR-4]  resegment_external_run: a selection that yields no kept segment →
         {'ok': False, 'error': 'empty_segmentation', **meta} (2942-2943) and
         the still-usable file is left UNCHANGED.
[GEP-1]  get_external_pending_runs: a pending job_*.json is listed (count >= 1,
         pending_job_id == file stem) and the result carries the registered
         adapter's brand label.
[GEP-2]  get_external_pending_runs: a vacuum with no external_jobs dir → count 0,
         pending [] and brand None (no crash, no adapter).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pytest_homeassistant_custom_component.common import async_fire_time_changed

import homeassistant.components.recorder as _recorder
from homeassistant.components.recorder import history as _history
import homeassistant.util.dt as dt_util

from custom_components.eufy_vacuum.adapters.registry import (
    register_adapter_config,
    unregister_adapter_config,
)
from custom_components.eufy_vacuum.const import EVENT_EXTERNAL_RUN_PENDING
from custom_components.eufy_vacuum.learning.constants import EXTERNAL_FINALIZE_GRACE_S
from custom_components.eufy_vacuum.learning.external_ingest import build_pending_record
from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"

# The external-aware adapter config: an active_map + task_status entity and the
# mid-run station-cycle vocabulary (so a plain "Charging" task is NOT mid-run and
# the finalize proceeds rather than rescheduling).
_EXT_ADAPTER = {
    "adapter_id": "t",
    "source": "t",
    "entities": {
        "active_map": "sensor.alfred_active_map",
        "task_status": "sensor.alfred_task",
    },
    "external_mid_run_statuses": ["washing mop", "emptying dust"],
}

_BASE = datetime(2026, 6, 7, 3, 0, 0)


def _c(sec: int, ct: float, ca: float, batt: int = 100) -> dict:
    """One buffered counter sample (cleaning_time/cleaning_area at +sec)."""
    return {
        "t": (_BASE + timedelta(seconds=sec)).isoformat(),
        "cleaning_time": ct,
        "cleaning_area": ca,
        "battery": batt,
    }


def _ss(sec: int, settings: dict) -> dict:
    """One buffered settings sample (the selects snapshot at +sec)."""
    return {"t": (_BASE + timedelta(seconds=sec)).isoformat(), "settings": settings}


# A rising cleaning_area with a long wash plateau between two rooms — the
# confident-cut signature build_pending_record needs to yield 2 segments. Reused
# verbatim from the external-ingest unit suite's _pending_two_rooms fixture.
_COUNTER_SAMPLES = [
    _c(0, 0, 0),
    _c(60, 30, 1), _c(90, 60, 2), _c(120, 90, 3),
    _c(150, 120, 4), _c(180, 150, 5), _c(210, 180, 6),   # room A: area 0->6
    _c(540, 210, 6), _c(570, 240, 8),                     # room B after 330s wash: ->8
]
_SETTINGS_SAMPLES = [
    _ss(60, {"clean_mode": "vacuum_mop"}),
    _ss(540, {"clean_mode": "vacuum"}),
]


def _external_jobs_dir(manager, vacuum_entity_id: str):
    """Resolve the on-disk external_jobs dir for one vacuum (the dir
    discard_external_run unlinks from), creating it so a pending record can be
    seeded the same way the capture path writes it."""
    store = LearningHistoryStore(manager.hass)
    paths = store.get_paths(vacuum_entity_id=vacuum_entity_id)
    ext_dir = paths.root / "external_jobs"
    ext_dir.mkdir(parents=True, exist_ok=True)
    return ext_dir


def test_discard_external_run_deletes_then_idempotent(manager):
    """[DXR-1] discarding a pending record removes the file and is idempotent.

    Write a real pending external_jobs/job_X.json, discard it (file gone,
    {'ok': True, 'pending_job_id': 'job_X'}), then discard the same id again —
    still {'ok': True} because the unlink is missing_ok, so the user double-
    clicking "discard" never produces an error.
    """
    ext_dir = _external_jobs_dir(manager, _VAC)
    pending = ext_dir / "job_X.json"
    pending.write_text(
        json.dumps({"pending_job_id": "job_X", "record_type": "external_pending"}),
        encoding="utf-8",
    )
    assert pending.exists()  # precondition: the record is on disk

    first = manager.discard_external_run(_VAC, "job_X")
    assert first == {"ok": True, "pending_job_id": "job_X"}
    assert not pending.exists()  # the file was actually deleted

    # Discarding the now-absent id again is still ok (missing_ok unlink) —
    # the only observable difference is the file stays gone.
    second = manager.discard_external_run(_VAC, "job_X")
    assert second == {"ok": True, "pending_job_id": "job_X"}
    assert not pending.exists()


async def test_external_grace_finalize_writes_record_and_fires_event(manager, hass):
    """[EXT-FIN-1] the grace timer drives _finalize_external_run to completion.

    EXT-3 only asserts the slot clears; this exercises the *write* half of
    _finalize_external_run: segment the buffered samples into a pending record,
    stamp the return-overhead onto it, write external_jobs/job_<ts>.json, clear
    the slot, and fire EVENT_EXTERNAL_RUN_PENDING with record_path + segment_count.

    No room_stats.json is written, so the missing-baselines ``except (OSError,
    ValueError)`` branch runs (baselines -> []) for free. Time is virtual (the
    grace timer is fired via async_fire_time_changed); the only on-disk side
    effect is the pending record under the per-vacuum learning root.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    # A 2-room map whose rooms carry slug/floor_type/clean_mode (save_managed_rooms
    # defaults: slug="room_n", floor_type="hardwood", clean_mode="vacuum") — what
    # build_pending_record reads to build each segment's shortlist.
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _EXT_ADAPTER)

    events: list[dict] = []
    unsub = hass.bus.async_listen(
        EVENT_EXTERNAL_RUN_PENDING, lambda ev: events.append(dict(ev.data))
    )

    try:
        # Open the external capture slot, then seed the buffered samples directly
        # onto it (the metrics listener does this at runtime; here we inject the
        # rising-area + wash-plateau trace so segmentation yields >=1 segment).
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id=_MAP)
        slot = manager.data["active_jobs"][_VAC][_MAP]
        slot["counter_samples"] = [dict(s) for s in _COUNTER_SAMPLES]
        slot["settings_samples"] = [dict(s) for s in _SETTINGS_SAMPLES]
        slot["started_at"] = _BASE.isoformat()

        # Dock with a non-mid-run task ("Charging" is not in
        # external_mid_run_statuses) so the grace finalize closes the run.
        hass.states.async_set(_VAC, "docked")
        hass.states.async_set("sensor.alfred_task", "Charging")

        deferred = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        assert deferred is False
        assert (_VAC, _MAP) in manager._external_grace_timers()  # finalize pending

        # Advance virtual time past the grace window so the timer fires
        # _external_grace_finalize -> _finalize_external_run -> the write + event.
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=EXTERNAL_FINALIZE_GRACE_S + 1)
        )
        await hass.async_block_till_done()

        # 1) the slot was cleared (the finalize ran to its end). [line 2756]
        cleared = manager.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
        assert cleared["status"] != "external"
        assert (_VAC, _MAP) not in manager._external_grace_timers()

        # 2) EVENT_EXTERNAL_RUN_PENDING fired carrying the write result. [2760-2769]
        assert len(events) == 1
        payload = events[0]
        assert payload["vacuum_entity_id"] == _VAC
        assert payload["map_id"] == _MAP
        assert payload["record_path"]  # the on-disk path of the written record
        assert payload["segment_count"] >= 1  # the wash plateau => >=1 segment

        # 3) the pending record exists on disk under external_jobs/. [line 2751-2752]
        store = LearningHistoryStore(hass)
        paths = store.get_paths(vacuum_entity_id=_VAC)
        ext_dir = paths.root / "external_jobs"
        written = [p for p in ext_dir.glob("job_*.json")
                   if str(p) == payload["record_path"]]
        assert len(written) == 1  # this run's record (external_jobs/ is shared across tests)
        assert str(written[0]) == payload["record_path"]

        # 4) the return-overhead stamp is present on the persisted record. [2746-2747]
        record = json.loads(written[0].read_text(encoding="utf-8"))
        assert "return_overhead_s" in record
        assert "return_intervals" in record
        assert isinstance(record["return_intervals"], list)
        # the record's own segment count matches what the event advertised.
        assert record["segment_count"] == payload["segment_count"]
    finally:
        unsub()
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


# W5c pose stream helpers — a cleaned room (zigzag anchors + rising cleaning_area) and a
# parked dock (jitter + flat area). The finalize resolves the attribution engine from the
# adapter; _EXT_ADAPTER declares no room_attribution block, so it falls back to the Eufy engine.
def _pose_clean(rid: int, start: int, n: int, area0: float, step: float) -> list[dict]:
    pts = [(0.0, 0.0), (0.1, 0.1)]
    return [
        {"t": (_BASE + timedelta(seconds=start + 2 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "current_room": rid, "anchor": list(pts[i % 2]), "cleaning_area": area0 + i * step}
        for i in range(n)
    ]


def _pose_park(rid: int, start: int, n: int, area: float) -> list[dict]:
    pts = [(0.5, 0.5), (0.51, 0.51)]
    return [
        {"t": (_BASE + timedelta(seconds=start + 2 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "current_room": rid, "anchor": list(pts[i % 2]), "cleaning_area": area}
        for i in range(n)
    ]


async def test_external_grace_finalize_pose_only_record(manager, hass):
    """[EXT-FIN-2] W5c: a run the counter segmenter can't split (NO counter samples) is no
    longer lost — the pose stream stands up a pose-attribution record, and the parked dock
    (room 2, flat area) is excluded while the cleaned room (room 1) is kept."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _EXT_ADAPTER)
    events: list[dict] = []
    unsub = hass.bus.async_listen(
        EVENT_EXTERNAL_RUN_PENDING, lambda ev: events.append(dict(ev.data))
    )
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id=_MAP)
        slot = manager.data["active_jobs"][_VAC][_MAP]
        slot["counter_samples"] = []   # no plateaus to segment — pose is the only signal
        slot["settings_samples"] = []
        slot["pose_samples"] = _pose_clean(1, 0, 14, 0.0, 0.2) + _pose_park(2, 28, 20, 2.6)
        slot["started_at"] = _BASE.isoformat()

        hass.states.async_set(_VAC, "docked")
        hass.states.async_set("sensor.alfred_task", "Charging")
        await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=EXTERNAL_FINALIZE_GRACE_S + 1)
        )
        await hass.async_block_till_done()

        assert manager.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)["status"] != "external"
        assert len(events) == 1
        record = json.loads(Path(events[0]["record_path"]).read_text(encoding="utf-8"))
        assert record["source"] == "pose_attribution"
        assert record["attribution_mode"] == "robust"
        assert [s["pose_room_id"] for s in record["segments"]] == [1]  # dock (room 2) excluded
        assert record["segments"][0]["shortlist"][0]["room_id"] == 1   # wizard pre-answered
        assert "counter_samples" not in record  # not counter-resegmentable
    finally:
        unsub()
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_finalize_clears_slot_on_build_error(manager, hass, monkeypatch):
    """[EXT-FIN-3] P1 (review): if record-building raises, the slot is STILL cleared — no zombie
    status='external' slot that the pose sampler keeps writing into and that wedges this
    (vacuum, map)'s future grace handling — and no pending event fires."""
    import custom_components.eufy_vacuum.learning.external_ingest as ei

    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _EXT_ADAPTER)

    def _boom(**kwargs):
        raise RuntimeError("build boom")

    monkeypatch.setattr(ei, "build_pending_record", _boom)  # _build_and_write imports it at call time
    events: list[dict] = []
    unsub = hass.bus.async_listen(
        EVENT_EXTERNAL_RUN_PENDING, lambda ev: events.append(dict(ev.data))
    )
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id=_MAP)
        slot = manager.data["active_jobs"][_VAC][_MAP]
        slot["counter_samples"] = [dict(s) for s in _COUNTER_SAMPLES]
        slot["started_at"] = _BASE.isoformat()

        hass.states.async_set(_VAC, "docked")
        hass.states.async_set("sensor.alfred_task", "Charging")
        await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=EXTERNAL_FINALIZE_GRACE_S + 1)
        )
        await hass.async_block_till_done()

        # The slot cleared despite the build error (no zombie), and nothing was advertised.
        assert manager.get_active_job(vacuum_entity_id=_VAC, map_id=_MAP)["status"] != "external"
        assert (_VAC, _MAP) not in manager._external_grace_timers()
        assert events == []
    finally:
        unsub()
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# _extract_return_overhead — the recorder walk in isolation. EXT-FIN-1 drives
# it indirectly through the finalize path (with no recorder, so it returns
# empty); these call it directly to pin both the bad-window guard and the
# state-walk accumulation. The recorder is never started — get_instance /
# history are monkeypatched so the production call wiring is preserved but runs
# inline against fixed synthetic rows (deterministic, no real time/network).
# ---------------------------------------------------------------------------


class _FakeState:
    """Minimal stand-in for a recorder State row: just .state + .last_changed.

    _extract_return_overhead reads only ``state`` and ``last_changed`` (falling
    back to ``last_updated``), so a tiny object matches what the walk consumes.
    """

    def __init__(self, state: str, last_changed: datetime) -> None:
        self.state = state
        self.last_changed = last_changed
        self.last_updated = last_changed


class _InlineRecorder:
    """get_instance(...) stand-in whose async_add_executor_job runs inline.

    The real path offloads history.state_changes_during_period to the recorder
    executor; running it inline keeps the test deterministic and recorder-free
    while still exercising the production call (func + args unchanged).
    """

    async def async_add_executor_job(self, func, *args):
        return func(*args)


@pytest.mark.parametrize("start_ts,end_ts", [
    ("not-a-timestamp", "also-bad"),                     # unparseable → empty
    ("2026-01-01T00:10:00Z", "2026-01-01T00:05:00Z"),    # end <= start → empty
])
async def test_return_overhead_empty_on_bad_window(manager, start_ts, end_ts):
    """[ERO-1] unparseable or out-of-order timestamps short-circuit to empty.

    This is the guard before any recorder read (lines 2658-2659): no executor
    job is dispatched, so the result is the canonical zero payload."""
    out = await manager._extract_return_overhead(_VAC, start_ts, end_ts)
    assert out == {"return_overhead_s": 0, "return_intervals": []}


async def test_return_overhead_books_mid_run_dock(manager, monkeypatch):
    """[ERO-2] a cleaning→docked→cleaning walk books the docked span as overhead.

    Three recorder rows 60s apart: only the middle (docked) interval is
    non-cleaning, so overhead == 60 and exactly one return-interval row is
    surfaced for it. The trailing cleaning row is the boundary that closes the
    docked interval, and is itself cleaning (not counted)."""
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    rows = [
        _FakeState("cleaning", t0),
        _FakeState("docked", t0 + timedelta(seconds=60)),
        _FakeState("cleaning", t0 + timedelta(seconds=120)),
    ]

    def _fake_state_changes(hass, start, end, entity_id):
        assert entity_id == _VAC  # the production call wiring is preserved
        return {_VAC: rows}

    # get_instance(...).async_add_executor_job runs the (real) history function
    # inline; history.state_changes_during_period is replaced with fixed rows.
    monkeypatch.setattr(_recorder, "get_instance", lambda hass: _InlineRecorder())
    monkeypatch.setattr(_history, "state_changes_during_period", _fake_state_changes)

    out = await manager._extract_return_overhead(
        _VAC,
        t0.isoformat(),
        (t0 + timedelta(seconds=120)).isoformat(),
    )

    assert out["return_overhead_s"] == 60
    assert len(out["return_intervals"]) == 1
    row = out["return_intervals"][0]
    assert row["state"] == "docked"
    assert row["seconds"] == 60
    assert row["start"] == (t0 + timedelta(seconds=60)).isoformat()


# ---------------------------------------------------------------------------
# confirm_external_run — graduate a pending record into a completed-job record.
# EXT-FIN-1 above writes the pending record; these pick it back up and confirm
# it. The pending record is the SAME 2-segment trace (order 0 area 6.0 m², order
# 1 area 2.0 m²) so the identity gate's pass/block is exact and deterministic.
# ---------------------------------------------------------------------------

# The map's room config the confirm loads on the loop (id -> room dict). The slug
# is the identity key both the learned-band lookup and the graduated profile use.
_CONFIRM_ROOMS = {
    "1": {
        "slug": "kitchen", "name": "Kitchen",
        "floor_type": "hardwood", "clean_mode": "vacuum_mop",
    }
}


def _write_pending(manager, vacuum_entity_id: str, pending_job_id: str) -> dict:
    """Build a real v2 pending record from the shared 2-segment trace and write it
    to external_jobs/<pending_job_id>.json (what confirm_external_run reads)."""
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id=_MAP,
        counter_samples=[dict(s) for s in _COUNTER_SAMPLES],
        settings_samples=[dict(s) for s in _SETTINGS_SAMPLES],
        rooms={}, baselines=[],
    )
    assert rec is not None and rec["segment_count"] == 2
    ext_dir = _external_jobs_dir(manager, vacuum_entity_id)
    (ext_dir / f"{pending_job_id}.json").write_text(json.dumps(rec), encoding="utf-8")
    return rec


def _write_room_band(manager, vacuum_entity_id: str, *, slug: str, avg_area_m2: float) -> None:
    """Seed a mature learned room_stats.json band for ``slug`` on map _MAP
    (>= 4 samples, tight stddev) so gate_segment_identity enforces it — used to
    drive the no-override block path (confirm reads bands by slug, 2804-2811)."""
    store = LearningHistoryStore(manager.hass)
    learned_dir = store.get_paths(vacuum_entity_id=vacuum_entity_id).learned_dir
    learned_dir.mkdir(parents=True, exist_ok=True)
    (learned_dir / "room_stats.json").write_text(
        json.dumps({
            "room_baselines": [
                {
                    "map_id": int(_MAP),
                    "room_slug": slug,
                    "avg_area_m2": avg_area_m2,
                    "area_sample_count": 10,
                    "area_m2_stddev": 1.0,
                }
            ]
        }),
        encoding="utf-8",
    )


def test_confirm_external_run_pending_not_found(manager):
    """[CXR-1] no external_jobs/<id>.json on disk → the open() raises OSError and
    confirm returns the pending_not_found sentinel without touching anything."""
    result = manager.confirm_external_run(
        _VAC, _MAP, "job_missing",
        room_assignments=[], rooms={}, rebuild_stats=False,
    )
    assert result == {
        "ok": False, "error": "pending_not_found", "pending_job_id": "job_missing",
    }


def test_confirm_external_run_graduates_with_override(manager):
    """[CXR-2] an override assignment bypasses the area gate, so the run graduates
    deterministically: a jobs/<id>.json is written, the pending file is removed,
    and the result reports ok / job_id (ext-) / rooms_learned / rebuilt."""
    pending_id = "job_cxr2_success"
    _write_pending(manager, _VAC, pending_id)

    store = LearningHistoryStore(manager.hass)
    paths = store.get_paths(vacuum_entity_id=_VAC)
    pending_path = paths.root / "external_jobs" / f"{pending_id}.json"
    assert pending_path.exists()  # precondition: the pending record is on disk

    result = manager.confirm_external_run(
        _VAC, _MAP, pending_id,
        room_assignments=[{"segment_orders": [0], "room_id": 1, "override": True}],
        rooms=_CONFIRM_ROOMS,
        rebuild_stats=False,
    )

    assert result["ok"] is True
    assert result["job_id"] == f"ext-{pending_id}"
    assert result["job_id"].startswith("ext-")
    assert result["rooms_learned"] == 1
    assert result["rebuilt"] is False  # rebuild_stats=False → no rebuild attempted

    # The pending external_jobs/ file was unlinked (manager 2831)...
    assert not pending_path.exists()
    # ...and the graduated completed-job record now exists under jobs/. [2827]
    job_path = paths.jobs_dir / f"{result['job_id']}.json"
    assert job_path.exists()
    assert result["job_path"] == str(job_path)
    saved = json.loads(job_path.read_text(encoding="utf-8"))
    assert saved["record_type"] == "completed_job"
    assert saved["origin"] == "external"
    assert [r["slug"] for r in saved["job_profile"]["rooms"]] == ["kitchen"]


def test_confirm_external_run_rebuilds_stats(manager):
    """[CXR-2b] the DEFAULT confirm path (rebuild_stats=True) rebuilds the learning
    aggregates after graduating the run, so the result reports rebuilt=True — this
    is the card's normal confirm (the service schema defaults rebuild_stats=True).
    CXR-2 covers the opted-out (rebuild_stats=False) variant; this drives the
    rebuild branch at manager.py 2835-2847."""
    pending_id = "job_cxr2b_rebuild"
    _write_pending(manager, _VAC, pending_id)

    result = manager.confirm_external_run(
        _VAC, _MAP, pending_id,
        room_assignments=[{"segment_orders": [0], "room_id": 1, "override": True}],
        rooms=_CONFIRM_ROOMS,
        rebuild_stats=True,
    )

    assert result["ok"] is True
    assert result["job_id"] == f"ext-{pending_id}"
    assert result["rebuilt"] is True  # the rebuild branch ran and succeeded


def test_confirm_external_run_blocked_without_override(manager):
    """[CXR-3] without override, an assignment whose segment area (6.0 m²) is far
    outside the room's mature learned band (avg 50 m²) fails the tier-1 identity
    gate, so build_graduated_job returns (None, blocked) and confirm returns
    {'ok': False, 'blocked': [...]} leaving the pending file intact."""
    pending_id = "job_cxr3_blocked"
    _write_pending(manager, _VAC, pending_id)
    # kitchen's learned area is ~50 m²; the assigned segment is 6.0 m² → mismatch.
    _write_room_band(manager, _VAC, slug="kitchen", avg_area_m2=50.0)

    store = LearningHistoryStore(manager.hass)
    paths = store.get_paths(vacuum_entity_id=_VAC)
    pending_path = paths.root / "external_jobs" / f"{pending_id}.json"

    result = manager.confirm_external_run(
        _VAC, _MAP, pending_id,
        room_assignments=[{"segment_orders": [0], "room_id": 1, "override": False}],
        rooms=_CONFIRM_ROOMS,
        rebuild_stats=False,
    )

    assert result["ok"] is False
    assert result["blocked"]  # at least one blocked assignment
    blocked = result["blocked"][0]
    assert blocked["room_id"] == 1
    assert blocked["reason"] == "area_mismatch"
    assert blocked["plausible"] is False
    assert result["pending_job_id"] == pending_id

    # A blocked confirm graduates nothing: the pending record stays put and no
    # completed-job record was written. [2824-2825]
    assert pending_path.exists()
    assert not (paths.jobs_dir / f"ext-{pending_id}.json").exists()


# ---------------------------------------------------------------------------
# resegment_external_run — the review wizard's server-side re-segment. The happy
# round trip is covered at the service level (test_learning_services
# .test_resegment_external_run_round_trip); these pin the three residual guard
# branches that route is too coarse to reach, driven directly against the real
# sync manager method with real on-disk pending records (reusing _write_pending /
# _external_jobs_dir from the confirm block — the SAME 2-segment v2 trace).
#
# [RXR-1]  missing/corrupt pending file -> {'ok': False, 'error':
#          'pending_not_found'} (the except at manager.py:2922-2923); no file made.
# [RXR-2]  a v1 record (samples stripped) -> {'ok': False, 'error':
#          'not_resegmentable', 'reason': 'no_samples'} (2924-2925); file untouched.
# [RXR-3]  a v2 record with NO room_stats.json on disk re-segments successfully ->
#          the baseline-read except falls back to baselines=[] (2929-2932) and the
#          record is rewritten in place with its samples preserved.
# [RXR-4]  a selection that yields no kept segment -> resegment_pending_record
#          returns (None, meta) -> {'ok': False, 'error': 'empty_segmentation',
#          **meta} (2942-2943) and the still-usable file is left UNCHANGED.
# ---------------------------------------------------------------------------


def _reseg_pending_path(manager, vacuum_entity_id: str, job_id: str):
    """The on-disk path resegment_external_run reads/writes for one record."""
    return _external_jobs_dir(manager, vacuum_entity_id) / f"{job_id}.json"


def test_resegment_missing_pending_returns_not_found(manager):
    """[RXR-1] no record on disk for the id -> the open() raises and the
    ``except (OSError, ValueError)`` (manager.py:2922-2923) returns
    pending_not_found WITHOUT creating any file."""
    _external_jobs_dir(manager, _VAC)  # dir exists; the record does not
    result = manager.resegment_external_run(
        _VAC, _MAP, "job_reseg_missing",
        expected_rooms=2, active_boundaries=None, rooms={},
    )
    assert result == {"ok": False, "error": "pending_not_found"}
    # the guard must not have written/created the file as a side effect.
    assert not _reseg_pending_path(manager, _VAC, "job_reseg_missing").exists()


def test_resegment_v1_record_not_resegmentable(manager):
    """[RXR-2] a legacy v1 record (samples stripped) is found but has no
    ``counter_samples`` -> not_resegmentable / no_samples (manager.py:2924-2925).
    The file is left intact (the guard returns before any write)."""
    pending_id = "job_reseg_v1"
    _write_pending(manager, _VAC, pending_id)
    path = _reseg_pending_path(manager, _VAC, pending_id)
    rec = json.loads(path.read_text(encoding="utf-8"))
    rec.pop("counter_samples", None)
    rec.pop("settings_samples", None)
    rec["schema_version"] = 1
    path.write_text(json.dumps(rec), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    result = manager.resegment_external_run(
        _VAC, _MAP, pending_id,
        expected_rooms=3, active_boundaries=None, rooms={},
    )
    assert result == {
        "ok": False, "error": "not_resegmentable", "reason": "no_samples",
    }
    # untouched: a v1 record stays exactly as written.
    assert path.read_text(encoding="utf-8") == before


def test_resegment_success_with_no_room_stats_on_disk(manager):
    """[RXR-3] a re-segment succeeds even though no ``room_stats.json`` exists ->
    the baseline read's ``except`` falls back to ``baselines = []``
    (manager.py:2929-2932) and the record is rewritten in place.

    Re-segmenting to the existing segment_count (2) is the minimal selection that
    still drives the full success path (segmenter + ``store.write_json``) without
    changing the segmentation, giving a stable structural assertion."""
    pending_id = "job_reseg_ok"
    rec = _write_pending(manager, _VAC, pending_id)
    path = _reseg_pending_path(manager, _VAC, pending_id)

    # The branch under test fires when the learned-bands file is absent. The phac
    # config_dir is SHARED across tests (see the confirm block + the suite's other
    # external tests), so a sibling test may have seeded room_stats.json; remove it
    # here so line 2930's except is the path taken deterministically regardless of
    # test order.
    store = LearningHistoryStore(manager.hass)
    learned_dir = store.get_paths(vacuum_entity_id=_VAC).learned_dir
    (learned_dir / "room_stats.json").unlink(missing_ok=True)
    assert not (learned_dir / "room_stats.json").exists()

    result = manager.resegment_external_run(
        _VAC, _MAP, pending_id,
        expected_rooms=rec["segment_count"], active_boundaries=None, rooms={},
    )
    assert result["ok"] is True
    assert result["segment_count"] == 2
    assert result["pending_job_id"] == pending_id
    # the response is sample-stripped (the card never needs the raw samples).
    assert "counter_samples" not in result
    # the on-disk record was rewritten and keeps its samples for the next pass.
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["segment_count"] == 2
    assert on_disk["counter_samples"]


def test_resegment_empty_segmentation_leaves_file_untouched(manager):
    """[RXR-4] a v2 record whose run never covered a full room (every segment is
    sub-``_MIN_ROOM_AREA_M2`` and is dropped) re-segments to nothing:
    ``resegment_pending_record`` returns ``(None, meta)`` so the manager returns
    ``{ok: False, error: 'empty_segmentation', **meta}`` (manager.py:2942-2943)
    and — critically — does NOT overwrite the still-usable file.

    The record is hand-built (a sub-room run can't come from build_pending_record,
    which drops it too) with truthy ``counter_samples`` so it clears the v1 guard
    and reaches the segmenter. ``active_boundaries=[]`` selects no cuts -> one
    merged segment whose ~0.3 m² area is below the room threshold -> dropped."""
    pending_id = "job_reseg_empty"
    sub_room = {
        "schema_version": 2,
        "status": "pending",
        "origin": "external",
        "detection_ts": _BASE.isoformat(),
        "map_id": _MAP,
        "segment_count": 1,
        "suggested_room_count": 1,
        "gap_transit_s": 60.0,
        "candidates": [],
        "active_boundaries": [],
        # truthy samples (passes the no_samples guard) but the whole run is < 0.5 m².
        "counter_samples": [_c(0, 0, 0), _c(30, 30, 0.1), _c(60, 60, 0.2), _c(90, 90, 0.3)],
        "settings_samples": [],
        "segments": [{"order": 0, "boundary_id": None, "area_m2": 0.3}],
    }
    path = _reseg_pending_path(manager, _VAC, pending_id)
    path.write_text(json.dumps(sub_room), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    result = manager.resegment_external_run(
        _VAC, _MAP, pending_id,
        expected_rooms=None, active_boundaries=[], rooms={},
    )
    assert result["ok"] is False
    assert result["error"] == "empty_segmentation"
    # the selection meta is spread into the result (explicit boundary mode).
    assert result["mode"] == "explicit"
    # fail-safe: the usable record on disk is left exactly as it was.
    assert path.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# get_external_pending_runs — list pending external_jobs/ records for the card,
# tagged with the adapter's brand label. Real manager, real on-disk records
# under the per-vacuum learning root (same dir the capture path writes to).
#
# [GEP-1] a pending job_*.json is listed (count >= 1, pending_job_id == stem)
#         and the result carries the registered adapter's brand label.
# [GEP-2] a vacuum with no external_jobs dir → count 0, pending [] (no crash).
# ---------------------------------------------------------------------------

# Minimal config: only the brand label is under test here; no mapping block (so
# _validate_adapter passes clean) and no entities (this method never reads them).
_GEP_ADAPTER = {"adapter_id": "t", "source": "t", "brand": "Eufy"}


def test_get_external_pending_runs_lists_record_with_brand(manager):
    """[GEP-1] a pending record is listed and tagged with the adapter brand.

    Register an adapter carrying ``brand: "Eufy"``, write one real
    external_jobs/job_*.json, then call get_external_pending_runs. The card-
    facing contract is observable end to end: ``count`` counts the record,
    the ``pending`` list contains the record dict with ``pending_job_id`` set
    to the file stem (load_pending_runs derives it from the filename), and
    ``brand`` is the adapter's label (sourced from the registry, kept out of
    the card itself).
    """
    register_adapter_config(_VAC, _GEP_ADAPTER)
    try:
        ext_dir = _external_jobs_dir(manager, _VAC)
        pending = ext_dir / "job_GEP1.json"
        pending.write_text(
            json.dumps({"record_type": "external_pending", "map_id": "6"}),
            encoding="utf-8",
        )
        assert pending.exists()  # precondition: the record is on disk

        out = manager.get_external_pending_runs(_VAC)

        # the result is the card's data envelope, keyed on this vacuum.
        assert out["vacuum_entity_id"] == _VAC
        assert out["count"] >= 1
        # the count must agree with the listed records (no off-by-one).
        assert out["count"] == len(out["pending"])
        # our record is present, identified by the filename stem.
        ids = {rec.get("pending_job_id") for rec in out["pending"]}
        assert "job_GEP1" in ids
        # and the embedded record payload survived the load.
        rec = next(r for r in out["pending"] if r.get("pending_job_id") == "job_GEP1")
        assert rec["record_type"] == "external_pending"
        # brand label comes from the registered adapter, not the card.
        assert out["brand"] == "Eufy"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


def test_get_external_pending_runs_empty_when_no_dir(manager):
    """[GEP-2] no external_jobs dir → an empty envelope, not an error.

    Without any registered adapter and without an external_jobs directory,
    load_pending_runs returns [] (the OSError-on-listdir path), so the card
    gets ``count == 0``, ``pending == []`` and ``brand is None`` (no adapter
    registered → the card falls back to generic phrasing). A different vacuum
    id keeps this isolated from any record the prior test seeded.
    """
    other = "vacuum.no_external"
    out = manager.get_external_pending_runs(other)

    assert out["vacuum_entity_id"] == other
    assert out["count"] == 0
    assert out["pending"] == []
    assert out["brand"] is None
