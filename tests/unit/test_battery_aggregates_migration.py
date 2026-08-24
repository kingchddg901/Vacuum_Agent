"""D2 — the one-shot replay of drain aggregates accumulated under the pre-C17 rule.

Context: C17 gave each drain mean its own numerator, gated on both halves of the ratio
being present. Those numerators are NEW KEYS, so an upgraded install keeps a
denominator holding all-time data while the numerator restarts at 0.0 — and the first
job folded in afterwards publishes roughly one job's drain over every job's duration.
Measured on the live install 2026-08-23: the next run would have published 0.0 and
0.0066 %/min against honest figures of 0.292 and 0.4613.

All three C17 tests construct an EMPTY bucket, which is the shape the repair is correct
for. That is precisely why none of them could see this.

Coverage targets
----------------
[BAM-1] the collapse this exists to prevent, driven through the REAL fold function —
        a stale bucket plus one new job publishes a mean two orders of magnitude low.
        Everything below is only worth having because of this.
[BAM-2] a stale bucket is detected: a populated denominator with no partnered numerator.
[BAM-3] an EMPTY bucket is NOT a target. It is the case C17 is already correct for, and
        rebuilding it would replace correct data with an archive replay for no reason.
[BAM-4] a bucket whose numerator is PRESENT and 0.0 is not a target — that is what an
        honest drain-less run set produces under the new rule, and keying on the value
        rather than on absence would fire on it.
[BAM-5] sub-buckets are examined, not just ``all_jobs``. On the live install every
        vacuum had six stale sub-buckets behind one stale ``all_jobs``.
[BAM-6] the planner is pure — planning alone changes nothing.
[BAM-7] the replay runs and the migration latches; a second run is a no-op.
[BAM-8] an install with nothing stale latches VACUOUSLY rather than rescanning forever.
[BAM-9] the previous aggregates are snapshotted before being replaced, because the
        accumulated sums exist nowhere else and a replay is otherwise one-way.
[BAM-10] a missing subsystem DEFERS and does NOT latch. Latching there would burn the
        one shot on a vacuum whose numbers are about to collapse.
[BAM-11] one vacuum failing does not abort the rest, and does not latch.
[BAM-12] ``force`` re-runs a latched migration.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.battery.manager import (
    BatteryHealthManager,
    _new_aggregate_bucket,
)
from custom_components.eufy_vacuum.const import DATA_BATTERY, DATA_LEARNING, DOMAIN
from custom_components.eufy_vacuum.core.battery_aggregates_migration import (
    BACKUP_FIELD,
    MIGRATION_KEY,
    migrate_battery_aggregates,
    plan_battery_aggregates_migration,
)


# --- the pre-C17 shape, as it actually appears on an upgraded install ---------------
# Taken from the live store 2026-08-23: a populated denominator, real accumulated
# sums, and NO partnered numerator key at all.
def _stale_bucket(count=47, drain=159.0, duration=544.45, area=191.0) -> dict:
    return {
        "count": count,
        "drain_pct_sum": drain,
        "duration_min_sum": duration,
        "area_m2_sum": area,
        "drain_per_min_mean": round(drain / duration, 4) if duration else None,
        "drain_per_hour_mean": round(drain / duration * 60.0, 4) if duration else None,
        "drain_per_m2_mean": round(drain / area, 4) if area else None,
    }


def _data(*, stale=True, subs=True) -> dict:
    bucket = _stale_bucket() if stale else _new_aggregate_bucket()
    aggregates = {
        "all_jobs": bucket,
        "by_clean_mode": {"vacuum": _stale_bucket(43, 131.0, 394.65, 150.0)} if subs else {},
        "by_fan_speed": {},
        "by_water_level": {},
    }
    return {"battery": {"vacuums": {"vacuum.alfred": {"job_aggregates": aggregates}}}}


def _metrics(n=3, drain=10.0, duration=20.0, area=5.0) -> list[dict]:
    return [
        {"battery_used_pct": drain, "duration_min": duration, "area_m2": area}
        for _ in range(n)
    ]


class _Learning:
    def __init__(self, metrics=None, raises=False):
        self._metrics = metrics if metrics is not None else _metrics()
        self._raises = raises

    def collect_archived_battery_metrics(self, *, vacuum_entity_id):
        if self._raises:
            raise RuntimeError("archive unreadable")
        return list(self._metrics)


class _Manager:
    def __init__(self, data):
        self.data = data


class _Hass:
    def __init__(self, data, *, battery=None, learning=None):
        self.data = {DOMAIN: {}}
        if battery is not None:
            self.data[DOMAIN][DATA_BATTERY] = battery
        if learning is not None:
            self.data[DOMAIN][DATA_LEARNING] = learning

    async def async_add_executor_job(self, func, *args):
        return func(*args)


def _battery(data) -> BatteryHealthManager:
    """A real BatteryHealthManager over `data`, with the loop-bound bits stubbed.

    Real rather than a mock on purpose: the migration's whole job is to drive
    ``rebuild_job_aggregates`` and the REAL fold, and a mock would agree with whatever
    it was called with — including a rebuild that never partnered anything.
    """
    bm = BatteryHealthManager.__new__(BatteryHealthManager)
    bm._manager = _Manager(data)
    bm._listeners = {}
    bm._schedule_save = lambda: None
    bm._notify = lambda *a, **k: None
    return bm


# --- [BAM-1] the collapse ----------------------------------------------------------


def test_bam1_the_collapse_this_prevents():
    """[BAM-1] Driven through the REAL `_update_aggregate_bucket`, not a restatement.

    A stale bucket keeps its all-time `duration_min_sum` while
    `drain_pct_sum_for_duration` restarts at 0.0, so the next job's mean is that ONE
    job's drain over 544 minutes. This is the failure the whole module exists for, and
    it is the assertion that would go red if the migration silently stopped running.
    """
    bm = _battery({})
    bucket = _stale_bucket()
    assert bucket["drain_per_min_mean"] == pytest.approx(0.292, abs=1e-3)

    bm._update_aggregate_bucket(bucket, {
        "battery_used_pct": 10.0, "duration_min": 20.0, "area_m2": 5.0,
    })
    # 10.0 / (544.45 + 20.0) -- two orders of magnitude below the honest 0.5
    assert bucket["drain_per_min_mean"] == pytest.approx(0.0177, abs=1e-3)
    assert bucket["drain_per_min_mean"] < 0.292 / 10


# --- detection ---------------------------------------------------------------------


def test_bam2_a_populated_denominator_with_no_partnered_numerator_is_stale():
    plan = plan_battery_aggregates_migration(data=_data())
    assert [p["vacuum_entity_id"] for p in plan] == ["vacuum.alfred"]
    assert plan[0]["count_before"] == 47
    assert plan[0]["means_before"]["drain_per_min_mean"] == pytest.approx(0.292, abs=1e-3)


def test_bam3_an_empty_pre_c17_bucket_is_not_a_target():
    """[BAM-3] RED IF DETECTION KEYS ON THE MISSING KEY ALONE.

    The shape here is the one that actually bites, and the first draft of this test got
    it wrong: a bucket built by `_new_aggregate_bucket` ALREADY carries the partnered
    keys, so absence-only detection never fires on it and the test passed against an
    ablated guard. The real case is a vacuum added before C17 that has never run — old
    format, so no partnered keys, and all sums at zero. `vacuum.robin` was in exactly
    this state on the live install 2026-08-23.

    Starting both halves of a ratio at 0.0 is correct, so there is nothing to repair —
    and replaying would hand it an archive it does not have.
    """
    empty_old_format = {
        "count": 0,
        "drain_pct_sum": 0.0,
        "duration_min_sum": 0.0,
        "area_m2_sum": 0.0,
        "drain_per_min_mean": None,
        "drain_per_hour_mean": None,
        "drain_per_m2_mean": None,
    }
    assert "drain_pct_sum_for_duration" not in empty_old_format
    data = {"battery": {"vacuums": {"vacuum.robin": {"job_aggregates": {
        "all_jobs": empty_old_format,
        "by_clean_mode": {}, "by_fan_speed": {}, "by_water_level": {},
    }}}}}
    assert plan_battery_aggregates_migration(data=data) == []

    # and the fresh-install shape is likewise not a target
    assert plan_battery_aggregates_migration(data=_data(stale=False, subs=False)) == []


def test_bam4_a_present_zero_numerator_is_not_a_target():
    """[BAM-4] RED IF DETECTION KEYS ON THE VALUE RATHER THAN ON ABSENCE. A bucket whose
    jobs all reported duration but no drain legitimately holds 0.0 here under the new
    rule — the arithmetic looks identical, but the data is honest and post-C17."""
    data = _data(subs=False)
    bucket = data["battery"]["vacuums"]["vacuum.alfred"]["job_aggregates"]["all_jobs"]
    bucket["drain_pct_sum_for_duration"] = 0.0
    bucket["drain_pct_sum_for_area"] = 0.0
    assert plan_battery_aggregates_migration(data=data) == []


def test_bam5_sub_buckets_are_examined_too():
    """[BAM-5] `all_jobs` clean and a sub-bucket stale is reachable: the sub-buckets
    take only single-config runs, so they are fed by a different subset."""
    data = _data()
    aj = data["battery"]["vacuums"]["vacuum.alfred"]["job_aggregates"]
    aj["all_jobs"] = _new_aggregate_bucket()          # healthy
    plan = plan_battery_aggregates_migration(data=data)
    assert plan[0]["stale_buckets"] == ["by_clean_mode[vacuum]"]


def test_bam6_the_planner_is_pure():
    data = _data()
    import copy

    before = copy.deepcopy(data)
    plan_battery_aggregates_migration(data=data)
    assert data == before


# --- application -------------------------------------------------------------------


async def test_bam7_the_replay_runs_and_latches():
    data = _data()
    bm = _battery(data)
    hass = _Hass(data, battery=bm, learning=_Learning(_metrics(3)))

    out = await migrate_battery_aggregates(hass=hass, manager=_Manager(data))
    assert out["ran"] is True and out["deferred"] == []
    change = out["changes"][0]
    assert change["jobs_replayed"] == 3
    assert change["count_before"] == 47 and change["count_after"] == 3

    aj = data["battery"]["vacuums"]["vacuum.alfred"]["job_aggregates"]["all_jobs"]
    # partnered now, and the mean is over the replayed jobs only
    assert aj["drain_pct_sum_for_duration"] == pytest.approx(30.0)
    assert aj["samples_duration"] == 3
    assert aj["drain_per_min_mean"] == pytest.approx(0.5)     # 30.0 / 60.0
    assert data["migrations"][MIGRATION_KEY] is True

    # idempotent
    again = await migrate_battery_aggregates(hass=hass, manager=_Manager(data))
    assert again["ran"] is False and again["changes"] == []


async def test_bam8_nothing_stale_latches_vacuously():
    """[BAM-8] RED IF THE EARLY RETURN FORGETS TO LATCH: a fresh install would replan
    on every single start, forever, for a repair it will never need."""
    data = _data(stale=False, subs=False)
    hass = _Hass(data, battery=_battery(data), learning=_Learning())
    out = await migrate_battery_aggregates(hass=hass, manager=_Manager(data))
    assert out["ran"] is True and out["changes"] == []
    assert data["migrations"][MIGRATION_KEY] is True


async def test_bam9_the_previous_aggregates_are_snapshotted():
    """[BAM-9] The accumulated sums exist nowhere else. Without this the replay cannot
    be undone, and it is a one-shot over a user's own derived history."""
    data = _data()
    bm = _battery(data)
    hass = _Hass(data, battery=bm, learning=_Learning(_metrics(3)))
    await migrate_battery_aggregates(hass=hass, manager=_Manager(data))

    backup = data["battery"]["vacuums"]["vacuum.alfred"][BACKUP_FIELD]
    assert backup["all_jobs"]["count"] == 47
    assert backup["all_jobs"]["duration_min_sum"] == pytest.approx(544.45)
    # a real copy, not a reference to the live tree
    live = data["battery"]["vacuums"]["vacuum.alfred"]["job_aggregates"]
    assert backup["all_jobs"] is not live["all_jobs"]


@pytest.mark.parametrize("missing", [DATA_BATTERY, DATA_LEARNING])
async def test_bam10_a_missing_subsystem_defers_and_does_not_latch(missing):
    """[BAM-10] RED IF THE LATCH IS UNCONDITIONAL. async_at_started fires immediately on
    a config-entry reload, so being dispatched before a subsystem is in hass.data is
    reachable, not theoretical — and latching then would leave the collapse armed."""
    data = _data()
    kw = {"battery": _battery(data), "learning": _Learning()}
    kw[{DATA_BATTERY: "battery", DATA_LEARNING: "learning"}[missing]] = None
    hass = _Hass(data, **kw)

    out = await migrate_battery_aggregates(hass=hass, manager=_Manager(data))
    assert out["deferred"] == ["vacuum.alfred"]
    assert out["changes"] == []
    assert MIGRATION_KEY not in data.get("migrations", {})
    # and the aggregates were left exactly as stored
    aj = data["battery"]["vacuums"]["vacuum.alfred"]["job_aggregates"]["all_jobs"]
    assert aj["count"] == 47 and "drain_pct_sum_for_duration" not in aj


async def test_bam11_one_failure_does_not_abort_the_rest_and_does_not_latch():
    """[BAM-11] Two vacuums, one unreadable archive. The healthy one must still be
    repaired — it is the one about to publish a collapsed mean — and the run must not
    record itself as done while the other is still stale."""
    data = _data()
    data["battery"]["vacuums"]["vacuum.ivy"] = {
        "job_aggregates": {"all_jobs": _stale_bucket(48, 228.0, 448.83, 219.7),
                           "by_clean_mode": {}, "by_fan_speed": {}, "by_water_level": {}}
    }
    bm = _battery(data)

    class _SelectiveLearning:
        def collect_archived_battery_metrics(self, *, vacuum_entity_id):
            if vacuum_entity_id == "vacuum.ivy":
                raise RuntimeError("archive unreadable")
            return _metrics(3)

    hass = _Hass(data, battery=bm, learning=_SelectiveLearning())
    out = await migrate_battery_aggregates(hass=hass, manager=_Manager(data))

    assert [c["vacuum_entity_id"] for c in out["changes"]] == ["vacuum.alfred"]
    assert out["deferred"] == ["vacuum.ivy"]
    assert MIGRATION_KEY not in data.get("migrations", {})
    ivy = data["battery"]["vacuums"]["vacuum.ivy"]["job_aggregates"]["all_jobs"]
    assert ivy["count"] == 48                      # untouched
    assert BACKUP_FIELD not in data["battery"]["vacuums"]["vacuum.ivy"]


async def test_bam12_force_reruns_a_latched_migration():
    data = _data()
    data["migrations"] = {MIGRATION_KEY: True}
    hass = _Hass(data, battery=_battery(data), learning=_Learning(_metrics(2)))

    assert (await migrate_battery_aggregates(
        hass=hass, manager=_Manager(data)))["ran"] is False
    out = await migrate_battery_aggregates(
        hass=hass, manager=_Manager(data), force=True)
    assert out["ran"] is True and out["changes"][0]["jobs_replayed"] == 2
