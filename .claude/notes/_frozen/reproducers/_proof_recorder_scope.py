"""Proof RP-013e (RF-11 part 5) — recorder predicates and scoped writes.

Both sample recorders on ActiveJobTracker share one guard:

    if job.get("started_at") and not job.get("ended_at"):

`dispatched_job_is_in_flight`'s own docstring records why that is wrong:
**nothing in this integration ever writes ``ended_at`` onto an active-job
record.** `mark_active_job_finalized` sets `status="completed"` and leaves
`started_at` in place, so the predicate is TRUE FOREVER after a run — until the
slot is overwritten. Two consequences, both reproduced below:

  A3-REC-4 / A4-AJ-2 — a FINISHED job keeps absorbing counters, and because the
    loop walks EVERY map bucket for the vacuum, the next run's samples are fanned
    into the previous run's record as well. The finished job's counter stream
    grows a second run's worth of time and area; its finalized record is already
    written, so nothing ever re-reads and corrects it.

  A5-METRICS-2 / A3-REC-5 — every counter sample carries
    `"battery": job.get("last_battery_percent")`, and **no writer for that key
    exists anywhere in the integration**. job_metrics subscribes cleaning_time,
    cleaning_area and station water; battery is not in the watch map even though
    BOTH adapters declare `entities["battery"]`. Every sample records
    battery=None, which is OBS-B-3's null per-room battery_delta at source.

Case 3 drives the REAL job_metrics.register() closure (captured by patching its
`async_track_state_change_event`, the RP-011 pattern) so the subscription set is
production's, not a restatement of it. The entity ids come from the Eufy
adapter's own `build_entity_id` + suffix constants rather than being typed out.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_recorder_scope.py
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.eufy.entities import (   # noqa: E402
    build_entity_id,
    SUFFIX_BATTERY,
    SUFFIX_CLEANING_AREA,
    SUFFIX_CLEANING_TIME,
)
from custom_components.eufy_vacuum.adapters import registry as adapter_registry   # noqa: E402
from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN   # noqa: E402
from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker   # noqa: E402
from custom_components.eufy_vacuum.listeners import job_metrics   # noqa: E402

MAP_DONE = "12"      # the run that already finished
MAP_LIVE = "13"      # the run happening now


def _two_bucket_manager() -> tuple[H.ManagerStub, ActiveJobTracker, dict, dict]:
    """One vacuum, two map buckets: a FINISHED job and a live one.

    The finished job is shaped exactly as `mark_active_job_finalized` leaves it —
    status completed, finalized True, started_at intact, ended_at absent (nothing
    writes it).
    """
    mgr = H.ManagerStub(hass=H.make_hass())
    done = H.active_job(
        map_id=MAP_DONE,
        job_id="job_yesterday",
        status="completed",
        finalized=True,
        finalized_at="2026-07-31T23:00:00Z",
        last_cleaning_time_seconds=1800,
        last_cleaning_area_m2=41.0,
        counter_samples=[],
    )
    live = H.active_job(
        map_id=MAP_LIVE,
        job_id="job_today",
        status="started",
        last_cleaning_time_seconds=120,
        last_cleaning_area_m2=3.0,
        counter_samples=[],
    )
    mgr.data["active_jobs"] = {H.VAC: {MAP_DONE: done, MAP_LIVE: live}}
    mgr.async_save = H.async_noop()
    return mgr, ActiveJobTracker(mgr), done, live


def case_finished_job_absorbs_sample(proof: H.Proof) -> None:
    mgr, aj, done, live = _two_bucket_manager()

    aj.record_counter_sample(vacuum_entity_id=H.VAC,
                             observed_at="2026-08-01T00:05:00Z")

    done_n = len(done.get("counter_samples") or [])
    live_n = len(live.get("counter_samples") or [])

    proof.case(
        "a counter sample arrives while YESTERDAY's finalized job still sits in "
        "its map bucket",
        before=done_n == 1 and live_n == 1,
        before_msg="the finished job absorbed the sample — started_at is still "
                   "set and ended_at is never written, so the guard stays true "
                   "for a completed run and the loop fans the write into every "
                   "map bucket",
        after=done_n == 0 and live_n == 1,
        after_msg="scoped — only the in-flight bucket was written",
        detail=f"finished bucket samples={done_n} · live bucket samples={live_n}",
    )


def case_finished_job_absorbs_sensor_value(proof: H.Proof) -> None:
    mgr, aj, done, live = _two_bucket_manager()

    aj.record_active_job_sensor_value(
        vacuum_entity_id=H.VAC, key="last_cleaning_time_seconds", value=999)

    done_v = done.get("last_cleaning_time_seconds")
    live_v = live.get("last_cleaning_time_seconds")

    proof.case(
        "the OTHER recorder — a sensor value lands while the finished job is "
        "still in its bucket",
        before=done_v == 999 and live_v == 999,
        before_msg="the finished job's recorded counters were overwritten by "
                   "the new run's — its finalized record is already written, so "
                   "nothing re-reads and corrects it",
        after=done_v == 1800 and live_v == 999,
        after_msg="scoped — the finished job kept its own final counters",
        detail=f"finished last_cleaning_time_seconds={done_v} "
               f"(its own run measured 1800) · live={live_v}",
    )


def case_battery_has_no_writer(proof: H.Proof) -> None:
    """Drive the REAL job_metrics subscription: does a battery change ever reach
    `last_battery_percent`, the key every counter sample reads?"""
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    job = H.active_job(status="started", counter_samples=[])
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}
    mgr.async_save = H.async_noop()
    aj = ActiveJobTracker(mgr)
    # the manager's real delegation (core/manager.py) — one line each
    mgr.record_active_job_sensor_value = aj.record_active_job_sensor_value
    mgr.record_counter_sample = aj.record_counter_sample
    mgr.get_known_vacuum_ids = lambda: [H.VAC]
    mgr.get_vacuum_capabilities = lambda **kw: {"entities": {}}
    hass.data[DOMAIN] = {DATA_RUNTIME: mgr}

    battery_entity = build_entity_id(H.VAC, SUFFIX_BATTERY)
    ct_entity = build_entity_id(H.VAC, SUFFIX_CLEANING_TIME)
    ca_entity = build_entity_id(H.VAC, SUFFIX_CLEANING_AREA)

    # The adapter config is DATA — the three entity ids above are the adapter's
    # own, built by its own helper. Both shipped adapters declare entities.battery
    # (eufy/adapter.py:252, roborock/adapter.py:201).
    adapter_registry.register_adapter_config(H.VAC, {
        "adapter_id": "proof_rp013e",
        "source": "proof",
        "entities": {
            "cleaning_time": ct_entity,
            "cleaning_area": ca_entity,
            "battery": battery_entity,
        },
    })

    captured: dict = {}
    real_track = job_metrics.async_track_state_change_event

    def _capture(_hass, entity_ids, action):
        captured["entity_ids"] = list(entity_ids)
        captured["cb"] = action
        return lambda: None

    job_metrics.async_track_state_change_event = _capture
    try:
        job_metrics.register(hass)
    finally:
        job_metrics.async_track_state_change_event = real_track
        adapter_registry.unregister_adapter_config(H.VAC)

    subscribed = captured.get("entity_ids", [])
    fire = captured.get("cb")

    def _change(entity_id: str, state: str, unit: str | None = None) -> None:
        if fire is None:
            return
        fire(SimpleNamespace(data={
            "entity_id": entity_id,
            "new_state": SimpleNamespace(
                entity_id=entity_id, state=state,
                attributes={"unit_of_measurement": unit} if unit else {}),
        }))

    # the robot reports 57 % ... then a cleaning_time tick appends a sample
    _change(battery_entity, "57")
    _change(ct_entity, "300", "s")

    samples = job.get("counter_samples") or []
    sampled_battery = samples[-1].get("battery") if samples else "NO SAMPLE"
    stored_battery = job.get("last_battery_percent")

    proof.case(
        "the battery sensor reports 57 % mid-run — does the counter sample "
        "record it?",
        before=len(samples) == 1 and sampled_battery is None
        and stored_battery is None and battery_entity not in subscribed,
        before_msg="battery=None — every sample reads last_battery_percent and "
                   "NOTHING writes that key: job_metrics never subscribes the "
                   "adapter-declared battery entity, so per-room battery "
                   "attribution is dead at source (OBS-B-3's null battery_delta)",
        after=len(samples) == 1 and sampled_battery == 57
        and battery_entity in subscribed,
        after_msg="battery=57 — the declared battery entity is watched and the "
                  "sample carries a real reading",
        detail=f"sample battery={sampled_battery!r} · "
               f"last_battery_percent={stored_battery!r} · "
               f"battery entity subscribed={battery_entity in subscribed} "
               f"(watched: {sorted(subscribed)})",
    )


def main() -> int:
    proof = H.Proof("RP-013e", "recorder predicates and scoped writes")
    case_finished_job_absorbs_sample(proof)
    case_finished_job_absorbs_sensor_value(proof)
    case_battery_has_no_writer(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
