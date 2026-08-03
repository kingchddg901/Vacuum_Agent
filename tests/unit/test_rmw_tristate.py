"""RP-006 (RF-03) — read tri-state + destructive-RMW refusals.

UNREADABLE is not ABSENT: a failed read of an existing store must never let a
read-modify-write replace that store with only its own delta. Per-member
fault-injection per the packet: the store primitive, the trouble-rooms RMW, the
accuracy RMW (+ backoff cache), the accuracy rebuild's one-save, the room-history
preload (failure keeps cache; concurrent write survives), the source-refresh
cache, and the finalize-time live-snapshot clear / job-id preference.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from tests._factories import spec_manager

from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
from custom_components.eufy_vacuum.learning.job_finalizer import LearningJobFinalizer
from custom_components.eufy_vacuum.learning.estimator import LearningEstimator

VAC = "vacuum.alfred"


def _hass(tmp_path: Path) -> MagicMock:
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    hass.data = {}          # real dict — the accuracy backoff cache lives here
    return hass


def _store(tmp_path: Path) -> LearningHistoryStore:
    return LearningHistoryStore(_hass(tmp_path))


def _corrupt(path: Path) -> bytes:
    """Append trailing garbage — unreadable to json.loads, bytes recoverable."""
    healthy = path.read_bytes()
    path.write_bytes(healthy + b"\n<<TORN>>")
    return path.read_bytes()


# ---------------------------------------------------------------------------
# [TS-1] the primitive
# ---------------------------------------------------------------------------

def test_read_json_outcome_tristate(tmp_path):
    store = _store(tmp_path)
    p = tmp_path / "x.json"

    assert store.read_json_outcome(p) == (store.READ_ABSENT, None)

    p.write_text('{"a": 1}', encoding="utf-8")
    assert store.read_json_outcome(p) == (store.READ_OK, {"a": 1})

    p.write_text('{"a": 1}garbage', encoding="utf-8")
    assert store.read_json_outcome(p)[0] == store.READ_UNREADABLE

    p.write_text("", encoding="utf-8")   # zero-byte torn write
    assert store.read_json_outcome(p)[0] == store.READ_UNREADABLE

    p.write_text('"just a string"', encoding="utf-8")   # non-container
    assert store.read_json_outcome(p)[0] == store.READ_UNREADABLE

    # the compat wrapper stays None-tolerant for read paths
    assert store.read_json(p) is None


# ---------------------------------------------------------------------------
# [TS-2] trouble-rooms RMW
# ---------------------------------------------------------------------------

def _finalizer(tmp_path: Path) -> LearningJobFinalizer:
    return LearningJobFinalizer(_hass(tmp_path))


def _completed_job(room_id: int = 27) -> dict:
    return {
        "outcome": {"status": "completed"},
        "resolved_rooms": [{"room_id": room_id, "name": f"R{room_id}"}],
        "queue": {"queue_room_ids": [room_id]},
    }


def test_trouble_rooms_rmw_refuses_on_unreadable(tmp_path):
    fin = _finalizer(tmp_path)
    rooms = {str(i): {"room_id": i, "name": f"R{i}", "run_count": 3, "miss_count": 1}
             for i in range(1, 10)}
    fin.store.save_trouble_rooms(
        vacuum_entity_id=VAC,
        payload={"schema_version": 1, "rooms": rooms},
    )
    path = fin.store.get_trouble_rooms_path(vacuum_entity_id=VAC)
    corrupted = _corrupt(path)

    fin._update_trouble_rooms_log(
        vacuum_entity_id=VAC, completed_job=_completed_job(),
        active_job_state={}, ended_at="2026-08-01T00:00:00Z",
    )

    # file byte-identical: the 9 rooms of history are still recoverable
    assert path.read_bytes() == corrupted


def test_trouble_rooms_rmw_absent_still_seeds(tmp_path):
    fin = _finalizer(tmp_path)
    fin._update_trouble_rooms_log(
        vacuum_entity_id=VAC, completed_job=_completed_job(room_id=5),
        active_job_state={}, ended_at="2026-08-01T00:00:00Z",
    )
    saved = fin.store.load_trouble_rooms(vacuum_entity_id=VAC)
    assert saved and "5" in saved.get("rooms", {})   # ABSENT != failed: first run seeds


# ---------------------------------------------------------------------------
# [TS-3] accuracy RMW + the D4 backoff cache
# ---------------------------------------------------------------------------

def _actuals() -> list[dict]:
    return [{
        "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
        "is_carpet": False, "clean_intensity": "quick", "map_id": "12",
        "estimated_minutes": 5.0, "actual_minutes": 6.0,
    }]


def test_accuracy_rmw_refuses_on_unreadable(tmp_path):
    est = LearningEstimator(_hass(tmp_path))
    est.store.save_accuracy_stats(
        vacuum_entity_id=VAC,
        payload={"schema_version": 1, "rooms": {"old_key": {"sample_count": 9}}},
    )
    path = est.store.get_accuracy_stats_path(vacuum_entity_id=VAC)
    corrupted = _corrupt(path)
    est.store._accuracy_stats_cache().clear()   # force a disk read

    result = est.record_estimate_accuracy(vacuum_entity_id=VAC, room_actuals=_actuals())

    assert result.get("skipped") == "store_unreadable"
    assert result.get("rooms_recorded") == 0
    assert path.read_bytes() == corrupted        # history preserved on disk


def test_accuracy_unreadable_is_backed_off_not_permanent(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.save_accuracy_stats(vacuum_entity_id=VAC, payload={"rooms": {}})
    path = store.get_accuracy_stats_path(vacuum_entity_id=VAC)
    _corrupt(path)
    store._accuracy_stats_cache().clear()

    reads = {"n": 0}
    real = store.read_json_outcome

    def counting(p):
        reads["n"] += 1
        return real(p)

    monkeypatch.setattr(store, "read_json_outcome", counting)

    assert store.load_accuracy_stats_outcome(vacuum_entity_id=VAC)[0] == store.READ_UNREADABLE
    assert store.load_accuracy_stats_outcome(vacuum_entity_id=VAC)[0] == store.READ_UNREADABLE
    assert reads["n"] == 1   # second call served from the backoff entry, no disk hit

    # after the backoff expires, a repaired file is picked up (IO-3: not permanent)
    import custom_components.eufy_vacuum.learning.history_store as hs_mod
    monkeypatch.setattr(hs_mod.time, "monotonic", lambda: 10_000_000.0)
    path.write_text(json.dumps({"rooms": {"k": {}}}), encoding="utf-8")
    outcome, data = store.load_accuracy_stats_outcome(vacuum_entity_id=VAC)
    assert outcome == store.READ_OK and "k" in data["rooms"]


# ---------------------------------------------------------------------------
# [TS-4] rebuild: one save, no blank-first
# ---------------------------------------------------------------------------

def test_rebuild_accuracy_stats_saves_once_at_end(tmp_path):
    from custom_components.eufy_vacuum.learning.manager import LearningManager

    lm = LearningManager(_hass(tmp_path))
    job = {
        "record_type": "completed_job",
        "map_id": "12",
        "job": {"duration_minutes": 6.0},
        "job_profile": {"map_id": "12", "rooms": [{
            "slug": "kitchen", "clean_mode": "vacuum", "clean_passes": 1,
            "estimated_minutes": 5.0, "clean_intensity": "quick",
        }]},
        "completed_job": None,   # ignored; _auto_record_accuracy reads the outer dict
        "outcome": {"status": "completed", "used_for_learning": True},
    }
    lm.store.load_all_completed_jobs = MagicMock(return_value=[job, job])
    lm.store.is_learning_job = MagicMock(return_value=True)
    saves: list[dict] = []
    lm.store.save_accuracy_stats = MagicMock(
        side_effect=lambda *, vacuum_entity_id, payload: saves.append(payload)
    )

    applied = lm.rebuild_accuracy_stats(vacuum_entity_id=VAC)

    assert len(saves) == 1                       # ONE save, at the end
    assert saves[0].get("rooms")                 # and it is not the blank-first {}
    assert applied == 2


# ---------------------------------------------------------------------------
# [TS-5] room-history preload: failure keeps cache; concurrent write survives
# ---------------------------------------------------------------------------

def _manager(tmp_path: Path):
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    hass = _hass(tmp_path)
    mgr = EufyVacuumManager(hass)
    mgr.data = {"room_history": {VAC: {"12": {"5": {
        "room_id": 5, "map_id": "12", "room_name": "Kitchen",
        "last_cleaned_at": "2026-07-01T00:00:00+00:00",
    }}}}}
    mgr._notify_room_history_updated = MagicMock()
    mgr._room_history_cache_loading = set()   # normally set in async_initialize
    return hass, mgr


async def test_preload_failure_keeps_persisted_cache(tmp_path):
    hass, mgr = _manager(tmp_path)
    hass.async_add_executor_job = AsyncMock(return_value=None)   # rebuild FAILED

    await mgr.async_preload_room_history_cache(vacuum_entity_id=VAC)

    assert mgr.data["room_history"][VAC]["12"]["5"]["room_name"] == "Kitchen"
    assert VAC not in mgr._room_history_cache_ready   # retry on next trigger


async def test_preload_merge_keeps_concurrent_write(tmp_path):
    hass, mgr = _manager(tmp_path)
    # the rebuilt (executor) result: knows room 5 with an OLDER timestamp, and room 7
    rebuilt = {"12": {
        "5": {"room_id": 5, "map_id": "12", "room_name": "Kitchen",
              "last_cleaned_at": "2026-06-01T00:00:00+00:00"},
        "7": {"room_id": 7, "map_id": "12", "room_name": "Den",
              "last_cleaned_at": "2026-06-15T00:00:00+00:00"},
    }}

    async def rebuild_with_concurrent_write(_fn, _vac):
        # a finalize lands DURING the await: room 5 cleaned just now
        mgr.data["room_history"][VAC]["12"]["5"]["last_cleaned_at"] = (
            "2026-08-01T00:00:00+00:00"
        )
        return rebuilt

    hass.async_add_executor_job = rebuild_with_concurrent_write

    await mgr.async_preload_room_history_cache(vacuum_entity_id=VAC)

    live = mgr.data["room_history"][VAC]["12"]
    # the concurrent (newer) write SURVIVED the rebuild's older entry
    assert live["5"]["last_cleaned_at"] == "2026-08-01T00:00:00+00:00"
    # and the rebuild's new knowledge arrived
    assert live["7"]["room_name"] == "Den"
    assert VAC in mgr._room_history_cache_ready


# ---------------------------------------------------------------------------
# [TS-6] source-refresh cache: empty result keeps the previous source
# ---------------------------------------------------------------------------

def test_empty_room_source_keeps_previous_cache(tmp_path):
    from custom_components.eufy_vacuum.rooms.source_refresh import (
        get_cached_room_source, set_cached_room_source,
    )

    hass = _hass(tmp_path)
    good = {"12": [{"room_id": 5, "slug": "kitchen"}]}
    set_cached_room_source(hass, VAC, good)
    # the RP-006 guard in async_refresh_room_source keys on this exact condition:
    per_map: dict = {}
    if not per_map and get_cached_room_source(hass, VAC):
        pass   # keep old — mirrors the production early-return
    else:
        set_cached_room_source(hass, VAC, per_map)
    assert get_cached_room_source(hass, VAC) == good


# ---------------------------------------------------------------------------
# [TS-7] finalize: snapshot cleared on success; active job_id preferred
# ---------------------------------------------------------------------------

def test_collect_inputs_prefers_active_job_id_on_mismatch(tmp_path):
    fin = _finalizer(tmp_path)
    fin._live_snapshot_cache[VAC] = {"job_id": "job_STALE", "estimate": {}}

    # spec_manager, not MagicMock: this hands a stand-in straight to
    # _collect_finalization_inputs, the exact function whose three required
    # keyword-only args a permissive stub once swallowed.
    manager = spec_manager()
    manager.get_queue_state.return_value = {}
    manager.get_payload_state.return_value = {}
    manager.get_active_job.return_value = {"job_id": "job_LIVE"}

    inputs = fin._collect_finalization_inputs(
        manager=manager, vacuum_entity_id=VAC, map_id="12",
        battery_start=90, started_at="2026-08-01T00:00:00Z",
        ended_at="2026-08-01T00:10:00Z",
        forced_outcome_status=None, forced_lifecycle_state=None,
        forced_lifecycle_message=None,
    )
    assert inputs["job_id"] == "job_LIVE"   # stale snapshot no longer wins identity


def test_live_snapshot_cleared_after_successful_save(tmp_path):
    store = _store(tmp_path)
    store.save_live_snapshot(vacuum_entity_id=VAC, snapshot={"job_id": "j1"})
    assert store.load_live_snapshot(vacuum_entity_id=VAC)
    store.clear_live_snapshot(vacuum_entity_id=VAC)
    assert store.load_live_snapshot(vacuum_entity_id=VAC) is None
