"""One-shot repair: rebuild drain aggregates accumulated under the pre-C17 rule.

WHAT WAS WRONG. ``battery/manager.py::BatteryHealthManager._update_aggregate_bucket``
publishes three means as ratios. Until 2026-08-21 a single ``drain_pct_sum`` fed all
three numerators while each denominator accumulated over a different subset of jobs, so
a ratio's top and bottom counted different populations. C17 partnered them: each mean
now has its own numerator, gated on BOTH halves being present.

WHY THAT REPAIR IS NOT ENOUGH ON ITS OWN, WHICH IS THE WHOLE REASON THIS MODULE EXISTS.
The partnered numerators are NEW KEYS. An install that has been running accumulated
``duration_min_sum`` and ``area_m2_sum`` under the old rule and those keys survive the
upgrade, but ``drain_pct_sum_for_duration`` and ``drain_pct_sum_for_area`` start at 0.0.
So the first job folded in after the upgrade publishes

    (that one job's drain) / (every job ever recorded's duration)

and it does NOT wash out: both sums grow together from that point, so the historical
denominator is never diluted away. Measured against the real function — a bucket at
count 50 with ``duration_min_sum`` 1000.0 plus one post-upgrade job reads **0.0059**
where the honest figure over all 51 jobs is **0.30**, a factor of fifty.

Measured on a live install 2026-08-23, before C17 had been deployed to it: two vacuums,
every bucket carrying a populated denominator and NO partnered numerator — nine buckets,
with ``duration_min_sum`` at 544.45 and 448.83 minutes. The collapse had not happened
only because the code that triggers it had not shipped to that box. **This migration
must therefore land in the same release as C17, not after it.**

WHY A REBUILD RATHER THAN SEEDING THE MISSING NUMERATOR. Seeding
``drain_pct_sum_for_duration`` from the stored ``drain_pct_sum`` would preserve every
published mean exactly and needs no disk at all, which is genuinely tempting. It is also
precisely the defect being repaired: ``drain_pct_sum`` totals every job that reported a
drain, including the ones that reported no area, so seeding it as the area numerator
re-creates the mismatched population C17 removed and freezes the old inflated figure
into the record permanently. The archive is reconstructible by design, so the honest
sums are available; this replays them.

WHAT A REBUILD COSTS, STATED PLAINLY BECAUSE IT IS NOT NOTHING. ``count`` can fall.
``record_job_metrics`` does not deduplicate — it accepts a ``job_id`` and uses it only
for the ``last_job`` snapshot — so a duplicate finalize was counted twice and stayed
counted, and a run excluded later through ``exclude_learning_job`` stayed counted too.
The replay gate admits neither. On the same live install one vacuum replayed 47 jobs
against a stored count of 47, and the other replayed 23 against a stored count of 48.
A drop is the poison leaving rather than history being discarded — but it is a visible
change to a number the user can see, so this logs the before and after for every vacuum
it touches instead of repairing quietly.

The previous aggregates are snapshotted to ``job_aggregates_pre_c17`` on the record
before anything is replaced. A replay is not reversible on its own — the accumulated
sums exist nowhere else — and a one-shot that rewrites a user's derived history should
not be the only copy of it.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

MIGRATION_KEY = "battery_aggregates_c17_v1"

#: Where the pre-migration aggregates are kept so the rebuild is reversible.
BACKUP_FIELD = "job_aggregates_pre_c17"

#: Each mean's denominator and the numerator C17 partnered it with. A bucket is stale
#: when it has ACCUMULATED into a denominator but carries no partnered numerator, which
#: is exactly the upgraded-install shape and exactly the one that collapses.
#:
#: An EMPTY bucket is deliberately not a target: starting both halves of a ratio at 0.0
#: is correct. That is why the C17 tests pass and why they could not see this — all
#: three construct an empty bucket.
_PARTNERED: tuple[tuple[str, str], ...] = (
    ("duration_min_sum", "drain_pct_sum_for_duration"),
    ("area_m2_sum", "drain_pct_sum_for_area"),
)

_SUB_BUCKETS = ("by_clean_mode", "by_fan_speed", "by_water_level")

_MEAN_FIELDS = ("drain_per_min_mean", "drain_per_hour_mean", "drain_per_m2_mean")


def _is_stale_bucket(bucket: Any) -> bool:
    """Whether one aggregate bucket was accumulated under the pre-C17 rule."""
    if not isinstance(bucket, dict):
        return False
    for denominator, numerator in _PARTNERED:
        try:
            accumulated = float(bucket.get(denominator) or 0.0)
        except (TypeError, ValueError):
            continue
        # ABSENCE is the upgrade tell. A numerator PRESENT and 0.0 against a populated
        # denominator is the same arithmetic, but it is also what a legitimately
        # drain-less set of runs produces under the new rule — so keying on absence is
        # the test that cannot fire on honest post-C17 data.
        if accumulated > 0.0 and numerator not in bucket:
            return True
    return False


def _stale_buckets(aggregates: Any) -> list[str]:
    """Names of every stale bucket under one vacuum's ``job_aggregates``."""
    if not isinstance(aggregates, dict):
        return []
    found: list[str] = []
    if _is_stale_bucket(aggregates.get("all_jobs")):
        found.append("all_jobs")
    for sub in _SUB_BUCKETS:
        for key, bucket in (aggregates.get(sub) or {}).items():
            if _is_stale_bucket(bucket):
                found.append(f"{sub}[{key}]")
    return found


def plan_battery_aggregates_migration(*, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the vacuums this migration would rebuild. Pure; mutates nothing.

    Reported per vacuum so a caller — or a dry run against a copy of a real store — can
    see which buckets are stale and what the published means currently are, before
    anything replaces them.
    """
    out: list[dict[str, Any]] = []
    vacuums = ((data.get("battery") or {}).get("vacuums") or {})
    for vacuum_entity_id, record in vacuums.items():
        if not isinstance(record, dict):
            continue
        aggregates = record.get("job_aggregates")
        stale = _stale_buckets(aggregates)
        if not stale:
            continue
        all_jobs = (aggregates or {}).get("all_jobs") or {}
        out.append({
            "vacuum_entity_id": vacuum_entity_id,
            "stale_buckets": stale,
            "count_before": all_jobs.get("count"),
            "means_before": {k: all_jobs.get(k) for k in _MEAN_FIELDS},
        })
    return out


async def migrate_battery_aggregates(
    *,
    hass: Any,
    manager: Any,
    force: bool = False,
) -> dict[str, Any]:
    """Replay the drain aggregates from the job archive, once. Idempotent.

    Returns ``{"ran": bool, "changes": [...], "deferred": [...]}``. The caller persists
    ``manager.data``; nothing here writes the HA store.
    """
    data = manager.data
    migrations = data.setdefault("migrations", {})
    if migrations.get(MIGRATION_KEY) and not force:
        return {"ran": False, "changes": [], "deferred": []}

    planned = plan_battery_aggregates_migration(data=data)
    if not planned:
        # Nothing accumulated under the old rule — a fresh install, or one already
        # rebuilt. Latch vacuously: there is no target to defer for, and rescanning on
        # every start would never terminate.
        migrations[MIGRATION_KEY] = True
        return {"ran": True, "changes": [], "deferred": []}

    from ..const import DATA_BATTERY, DATA_LEARNING, DOMAIN

    domain_data = (hass.data.get(DOMAIN, {}) or {})
    battery = domain_data.get(DATA_BATTERY)
    learning = domain_data.get(DATA_LEARNING)

    changes: list[dict[str, Any]] = []
    deferred: list[str] = []

    for target in planned:
        vacuum_entity_id = target["vacuum_entity_id"]
        # MISSING RUNTIME INFORMATION IS DEFERRED, NEVER SUCCESS — the rule the room
        # vocabulary repair had to learn on hardware. Both subsystems are needed to
        # replay: learning owns the archive, battery owns the aggregates. If either is
        # absent this run cannot judge the target, and latching would burn the one shot
        # on a vacuum whose numbers are about to collapse.
        if battery is None or learning is None:
            deferred.append(vacuum_entity_id)
            continue
        try:
            metrics = await hass.async_add_executor_job(
                lambda vid=vacuum_entity_id: learning.collect_archived_battery_metrics(
                    vacuum_entity_id=vid
                )
            )
            record = battery.ensure_record(vacuum_entity_id)
            # Snapshot BEFORE the rebuild replaces it. The accumulated sums exist
            # nowhere else, so without this the repair is one-way.
            record[BACKUP_FIELD] = copy.deepcopy(record.get("job_aggregates"))
            applied = battery.rebuild_job_aggregates(
                vacuum_entity_id=vacuum_entity_id, metrics_list=metrics
            )
        except Exception:
            # One vacuum failing must not abort the rest, and must not latch: an
            # untouched vacuum still holds the shape that collapses.
            _LOGGER.exception(
                "battery_aggregates_migration: replay failed for %s; its aggregates are "
                "unchanged and the migration will retry on the next start",
                vacuum_entity_id,
            )
            deferred.append(vacuum_entity_id)
            continue

        after = (record.get("job_aggregates") or {}).get("all_jobs") or {}
        change = {
            "vacuum_entity_id": vacuum_entity_id,
            "stale_buckets": target["stale_buckets"],
            "jobs_replayed": applied,
            "count_before": target["count_before"],
            "count_after": after.get("count"),
            "means_before": target["means_before"],
            "means_after": {k: after.get(k) for k in _MEAN_FIELDS},
        }
        changes.append(change)
        _LOGGER.info(
            "battery_aggregates_migration: rebuilt %s from %d archived job(s). "
            "count %s -> %s; drain/min mean %s -> %s. %d bucket(s) held a denominator "
            "accumulated under the old rule with no partnered numerator, which would "
            "have published roughly one job's drain over all-time duration on the next "
            "run. The previous aggregates are kept under %r.",
            vacuum_entity_id, applied, change["count_before"], change["count_after"],
            change["means_before"].get("drain_per_min_mean"),
            change["means_after"].get("drain_per_min_mean"),
            len(target["stale_buckets"]), BACKUP_FIELD,
        )
        if (change["count_before"] or 0) > (change["count_after"] or 0):
            _LOGGER.warning(
                "battery_aggregates_migration: %s replayed %s job(s) against a stored "
                "count of %s. The archive is the source of truth and its gate rejects "
                "duplicate finalizes and runs excluded from learning after the fact, "
                "neither of which the incremental counter could ever remove. The drain "
                "means now cover %s job(s).",
                vacuum_entity_id, change["count_after"], change["count_before"],
                change["count_after"],
            )

    latched = not deferred
    if latched:
        migrations[MIGRATION_KEY] = True
    else:
        _LOGGER.warning(
            "battery_aggregates_migration: %d vacuum(s) could not be replayed (%s); NOT "
            "recording the migration as done — it will retry on the next start",
            len(deferred), ", ".join(deferred),
        )
    return {"ran": True, "changes": changes, "deferred": deferred}
