"""Battery health sensors backed by BatteryHealthManager.

Sensors per vacuum:
- {object_id}_charge_cycles      — cumulative cycles (drain ÷ 100)
- {object_id}_charge_rate        — instantaneous %/min (overall, while charging)
- {object_id}_charge_rate_low_zone   — %/min while battery ≤ 29%
- {object_id}_charge_rate_high_zone  — %/min while battery ≥ 80%
- {object_id}_last_charge_duration   — minutes for the last completed session THAT
  GAINED BATTERY (a zero/negative-delta close never updates it — see
  ``LastChargeDurationSensor``)
- {object_id}_battery_health     — % vs install baseline (CV regime — resistance proxy), capped ≤100%
- {object_id}_cc_charge_speed    — % vs install baseline, CC regime (capacity proxy)
- {object_id}_cv_charge_speed    — % vs install baseline, CV regime (resistance proxy)
- {object_id}_last_job_drain_per_min / per_hour / per_m2 — last-job drain rates
- {object_id}_mid_job_recharge_rate  — rolling mean of mid-job recharge rates

All sensors pull from the same in-memory record.

⚠ THERE IS NO SINGLE UPDATE LISTENER, and a new sample is not the only trigger. This
paragraph said "a single update listener fans out state writes whenever the manager
processes a new sample" until 2026-08-24 and it is wrong in both halves. EVERY entity
built by ``build_battery_sensors`` registers its own callback via
``BatteryHealthManager.add_update_listener`` in its own ``async_added_to_hass`` — so
``_update_listeners`` holds ONE ENTRY PER ENTITY per vacuum (twelve, as
``build_battery_sensors`` stands) — and ``_notify`` iterates the whole list while each
entity filters on ``vacuum_entity_id`` itself. ``_notify`` is called from
``_process_sample``, ``rebaseline``, ``rebuild_job_aggregates``, ``record_job_metrics``
and ``_attach_post_job_charge_if_pending``, which is why the job-metric sensors update
outside charging. Anyone optimising the fan-out, or chasing a leaked listener after
entity removal, is looking for a registration per entity, not one for the set.

The CC/CV regimes age in opposite directions — capacity loss raises %/min
in the 50→80 CC region, resistance rise lowers %/min in the 80→90 CV taper —
so they're tracked separately. _battery_health is an alias of _cv_charge_speed
for entity_id continuity with installs that pre-date the regime split, but
capped at 100% (never "healthier than new") — the uncapped value stays on
_cv_charge_speed and the health sensor's uncapped_pct attribute.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from ..entity_helpers import build_vacuum_device_info
from .manager import BatteryHealthManager


def build_battery_sensors(
    *,
    manager: BatteryHealthManager,
    vacuum_entity_id: str,
) -> list[SensorEntity]:
    """Construct the full battery sensor set for one vacuum."""
    return [
        ChargeCyclesSensor(manager=manager, vacuum_entity_id=vacuum_entity_id),
        ChargeRateSensor(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            stat_key="rate_overall_per_min",
            translation_key="charge_rate",
            unique_suffix="charge_rate",
        ),
        ChargeRateSensor(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            stat_key="rate_low_zone_per_min",
            translation_key="charge_rate_low_zone",
            unique_suffix="charge_rate_low_zone",
        ),
        ChargeRateSensor(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            stat_key="rate_high_zone_per_min",
            translation_key="charge_rate_high_zone",
            unique_suffix="charge_rate_high_zone",
        ),
        LastChargeDurationSensor(manager=manager, vacuum_entity_id=vacuum_entity_id),
        BatteryHealthSensor(manager=manager, vacuum_entity_id=vacuum_entity_id),
        # Regime-split charge speed indices. CC = 50→80 (capacity proxy),
        # CV = 80→90 (resistance proxy). _battery_health above is an alias
        # of the CV index, kept under the legacy entity_id.
        RegimeChargeSpeedSensor(
            manager=manager, vacuum_entity_id=vacuum_entity_id,
            stat_key="cc_charge_speed_pct",
            baseline_key="cc_min_per_pct",
            translation_key="cc_charge_speed",
            unique_suffix="cc_charge_speed",
        ),
        RegimeChargeSpeedSensor(
            manager=manager, vacuum_entity_id=vacuum_entity_id,
            stat_key="cv_charge_speed_pct",
            baseline_key="cv_min_per_pct",
            translation_key="cv_charge_speed",
            unique_suffix="cv_charge_speed",
        ),
        # Job-level metrics — populated when a job completes.
        LastJobMetricSensor(
            manager=manager, vacuum_entity_id=vacuum_entity_id,
            stat_key="drain_per_min",
            translation_key="last_job_drain_rate",
            unique_suffix="last_job_drain_per_min",
            unit="%/min",
        ),
        LastJobMetricSensor(
            manager=manager, vacuum_entity_id=vacuum_entity_id,
            stat_key="drain_per_hour",
            translation_key="last_job_drain_per_hour",
            unique_suffix="last_job_drain_per_hour",
            unit="%/h",
        ),
        LastJobMetricSensor(
            manager=manager, vacuum_entity_id=vacuum_entity_id,
            stat_key="drain_per_m2",
            translation_key="last_job_drain_per_m2",
            unique_suffix="last_job_drain_per_m2",
            unit="%/m²",
        ),
        # Mid-job recharge rate. USUALLY high-quality — a firmware auto-recharge is
        # roughly a 15→75 window with no top-taper variance — but that window is a
        # property of the DEVICE, not a gate: any positive-delta charge taken while a
        # job was in flight moves the mean. See MidJobRechargeRateSensor.
        MidJobRechargeRateSensor(manager=manager, vacuum_entity_id=vacuum_entity_id),
    ]


class _BatteryBase(SensorEntity):
    """Shared boilerplate: pulls from manager record, subscribes to updates."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        manager: BatteryHealthManager,
        vacuum_entity_id: str,
        translation_key: str,
        unique_suffix: str,
    ) -> None:
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._attr_translation_key = translation_key
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{unique_suffix}"
        )
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        self._unsub = None

    async def async_added_to_hass(self) -> None:
        self._unsub = self._manager.add_update_listener(self._on_manager_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub is not None:
            try:
                self._unsub()
            except Exception:  # pragma: no cover
                pass
            self._unsub = None

    def _on_manager_update(self, vacuum_entity_id: str) -> None:
        """Schedule a state refresh.

        ``BatteryHealthManager`` notifies listeners from whatever context the
        triggering call happened on — including executor threads (the job
        finalizer runs there). ``async_write_ha_state`` is event-loop only,
        so we route through ``call_soon_threadsafe`` to make this callsafe
        from any thread. Mirrors the ``_request_entity_state_write`` helper
        used by the rest of the integration's sensor platform.
        """
        if vacuum_entity_id != self._vacuum_entity_id:
            return
        hass = getattr(self, "hass", None)
        if hass is None:
            return

        @callback
        def _write() -> None:
            try:
                self.async_write_ha_state()
            except Exception:  # pragma: no cover - defensive
                pass

        try:
            hass.loop.call_soon_threadsafe(_write)
        except Exception:  # pragma: no cover - defensive
            pass

    def _record(self) -> dict[str, Any]:
        return self._manager.get_record(self._vacuum_entity_id)


class ChargeCyclesSensor(_BatteryBase):
    """Cumulative charge cycles (drain ÷ 100). Monotonic; survives restarts."""

    _attr_state_class = "total_increasing"
    _attr_icon = "mdi:battery-sync"

    def __init__(self, *, manager: BatteryHealthManager, vacuum_entity_id: str) -> None:
        super().__init__(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            translation_key="charge_cycles",
            unique_suffix="charge_cycles",
        )

    @property
    def native_value(self) -> float | None:
        rec = self._record()
        cycles = rec.get("cycles")
        return float(cycles) if cycles is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rec = self._record()
        return {
            "cumulative_drain_pct": rec.get("cumulative_drain_pct"),
            "completed_sessions": len(rec.get("session_history_recent", [])),
        }


class ChargeRateSensor(_BatteryBase):
    """Generic %/min sensor reading one of the rate fields from stats."""

    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = "%/min"
    _attr_icon = "mdi:battery-charging"

    def __init__(
        self,
        *,
        manager: BatteryHealthManager,
        vacuum_entity_id: str,
        stat_key: str,
        translation_key: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            translation_key=translation_key,
            unique_suffix=unique_suffix,
        )
        self._stat_key = stat_key

    @property
    def native_value(self) -> float | None:
        stats = self._record().get("stats", {})
        value = stats.get(self._stat_key)
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rec = self._record()
        return {
            "battery_level": rec.get("last_battery_level"),
            "charging": rec.get("last_charging"),
            "last_sample_ts": rec.get("last_sample_ts"),
        }


class LastChargeDurationSensor(_BatteryBase):
    """Minutes the most recent completed charge session THAT GAINED BATTERY took.

    Reads ``stats["last_charge_duration_min"]``, which ``_close_session`` writes only
    under ``if delta_pct > 0 and duration_min > 0``.

    ⚠ This said "the most recent completed charge session" until 2026-08-24. A session
    with zero or negative net delta — the ordinary case of a vacuum already at 100%
    sitting on the dock and cycling charging on and off — closes normally, gets its
    ``sessions.csv`` row and its ``session_history_recent`` entry, and never touches
    these stats. This sensor then keeps showing an OLDER session's duration while newer
    sessions have completed since, so it will disagree with the newest CSV row; that is
    not a persistence or ordering bug. The paired ``last_charge_delta_pct`` attribute
    goes stale in lockstep, so the two agreeing with each other is not evidence that
    either is current.
    """

    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = "duration"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, *, manager: BatteryHealthManager, vacuum_entity_id: str) -> None:
        super().__init__(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            translation_key="last_charge_duration",
            unique_suffix="last_charge_duration",
        )

    @property
    def native_value(self) -> float | None:
        stats = self._record().get("stats", {})
        value = stats.get("last_charge_duration_min")
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self._record().get("stats", {})
        return {
            "last_charge_delta_pct": stats.get("last_charge_delta_pct"),
        }


class BatteryHealthSensor(_BatteryBase):
    """Battery health % relative to the install baseline.

    Headline alias of ``cv_charge_speed_pct`` (the resistance-proxy regime).
    Kept under the ``_battery_health`` entity_id for continuity with installs
    that pre-date the regime split.

    ⚠ NONE HAS THREE CAUSES, NOT ONE. This said "None until the baseline is anchored"
    until 2026-08-24, which tells a reader that anchored-baseline-plus-unknown-state is
    impossible and sends them hunting a persistence or anchoring bug.
    ``BatteryHealthManager._compute_regime_pct`` returns None when the baseline is
    un-anchored (the documented case); when no retained qualifying session carries
    ``cv_min_per_pct`` DESPITE an anchored baseline; and when the computed ratio falls
    outside ``REGIME_PCT_MIN``..``REGIME_PCT_MAX`` (25.0–150.0). That last one can only
    happen WITH an anchored baseline — it logs a warning and sets
    ``health_unavailable_reason = "implausible_regime_ratio"``, the live:BATT-CV-1 /
    RP-045(iii) path. The ``health_unavailable_reason`` and
    ``health_unavailable_reason_text`` attributes below exist to tell those states
    apart; read them before concluding anything from the None.

    Capped at 100% — a battery is never "healthier than new". A raw reading
    above 100 (the cell charging faster than its install baseline, common
    while the baseline is young) is clamped for this headline; the uncapped
    value stays in the ``uncapped_pct`` attribute here and on the separate
    ``_cv_charge_speed`` entity.

    ⚠ ``_cv_charge_speed`` IS NOT A DIAGNOSTIC ENTITY. This docstring called it "the
    _cv_charge_speed diagnostic sensor" until 2026-08-24; nothing in this package sets
    ``_attr_entity_category``, so it registers as an ordinary sensor beside this one and
    NOT under the device page's Diagnostic section — a user sent looking there finds
    nothing and concludes the entity was never created. Do NOT "fix" the mismatch by
    adding ``EntityCategory.DIAGNOSTIC``: that would silently move a live entity off
    existing installs' default dashboards and out of recorder defaults. The wording was
    the bug.
    """

    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery-heart-variant"

    def __init__(self, *, manager: BatteryHealthManager, vacuum_entity_id: str) -> None:
        super().__init__(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            translation_key="battery_health",
            unique_suffix="battery_health",
        )

    @property
    def native_value(self) -> float | None:
        stats = self._record().get("stats", {})
        value = stats.get("health_pct")
        if value is None:
            return None
        # Health is capped at 100% (never "healthier than new"); the raw
        # >100 charge-speed signal stays on _cv_charge_speed + uncapped_pct.
        return min(float(value), 100.0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rec = self._record()
        stats = rec.get("stats", {})
        baseline = rec.get("baseline", {})
        history = rec.get("session_history_recent", [])
        return {
            # The headline state is capped at 100%; expose the raw (possibly
            # >100) value here so the underlying signal isn't hidden.
            "uncapped_pct": stats.get("health_pct"),
            # The headline tracks the CV regime, so surface that anchor by
            # default. cc_min_per_pct is also exposed for visibility.
            "baseline_cv_min_per_pct": baseline.get("cv_min_per_pct"),
            "baseline_cc_min_per_pct": baseline.get("cc_min_per_pct"),
            "baseline_session_count": baseline.get("session_count"),
            "baseline_anchored_at": baseline.get("anchored_at"),
            "completed_sessions": len(history),
            # RP-045(iii): set only when health_pct is genuinely unavailable
            # (None here whenever health_pct is present). Paired stable code
            # + plain-English fallback, matching the learning manager's
            # trust_reason/trust_reason_text convention.
            "health_unavailable_reason": stats.get("health_unavailable_reason"),
            "health_unavailable_reason_text": stats.get("health_unavailable_reason_text"),
        }


class RegimeChargeSpeedSensor(_BatteryBase):
    """Per-regime charge-speed % vs install baseline (CC or CV).

    Reads ``stats.<stat_key>`` and surfaces the matching baseline anchor
    in attributes. Two instances live side-by-side (CC and CV) so users can
    read the capacity and resistance signals independently.

    ⚠ "Returns None until the baseline is anchored" — this docstring until 2026-08-24 —
    made the None self-explanatory, so nobody looked further.
    ``BatteryHealthManager._compute_regime_pct`` also returns None with the baseline
    ANCHORED: when no retained session carries the regime field, and when the ratio
    lands outside ``REGIME_PCT_MIN``..``REGIME_PCT_MAX`` (25–150). In that second case
    the raw figure is deliberately preserved as
    ``stats["cc_charge_speed_rejected_pct"]`` / ``stats["cv_charge_speed_rejected_pct"]``
    ("kept so the failure is diagnosable") and surfaced here as the ``rejected_pct``
    attribute — see ``extra_state_attributes`` below. It is the only way to tell "no
    baseline yet" from "a number was computed and rejected".

    The CC and CV indices run in OPPOSITE directions;
    ``BatteryHealthManager._update_health`` carries the physics. Higher is WORSE on the
    CC instance.
    """

    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery-heart-variant"

    def __init__(
        self,
        *,
        manager: BatteryHealthManager,
        vacuum_entity_id: str,
        stat_key: str,
        baseline_key: str,
        translation_key: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            translation_key=translation_key,
            unique_suffix=unique_suffix,
        )
        self._stat_key = stat_key
        self._baseline_key = baseline_key

    @property
    def native_value(self) -> float | None:
        stats = self._record().get("stats", {})
        value = stats.get(self._stat_key)
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # B17: expose the `_rejected_pct` sibling that BatteryHealthManager
        # already preserves ("kept so the failure is diagnosable"). Without
        # this, a native_value of None had two indistinguishable causes — no
        # baseline yet, OR every recent read was rejected as an outlier — and
        # the docstring's "still waiting for the baseline" was the only account
        # the user got. A user seeing a rejected number knows a baseline exists
        # but recent charging is unusual; that is the diagnostic value the
        # rejection was preserved for.
        stats = self._record().get("stats", {})
        rejected_key = self._stat_key.replace("_pct", "_rejected_pct")
        baseline = self._record().get("baseline", {})
        return {
            "baseline_min_per_pct": baseline.get(self._baseline_key),
            "baseline_session_count": baseline.get("session_count"),
            "baseline_anchored_at": baseline.get("anchored_at"),
            "rejected_pct": stats.get(rejected_key),
        }


class LastJobMetricSensor(_BatteryBase):
    """Generic sensor exposing one of the last-job battery_metrics fields.

    State is the most recent completed job's value for ``stat_key``.
    Attributes also surface the running per-clean-mode / per-fan-speed /
    per-water-level aggregates so a card can chart trends without separate
    queries.

    ⚠ NONE DOES NOT MEAN "no job yet" — this said "(None if no job yet)" until
    2026-08-24, and the routine cause is the other one: a job WAS recorded and the
    metric itself is None.
    - ``drain_per_m2``: ``job_metrics.compute_job_battery_metrics`` computes
      ``drain / area`` only ``if drain is not None and area``, so the metric is None on
      every recorded job whose ``cleaning_area_m2`` was missing. Area is the read that
      goes missing in practice — it loses the same finalize-time race
      ``job_finalizer.py`` documents for ``cleaning_time``, and no learning-blocker
      stops such a job being recorded (``_update_aggregate_bucket`` says so too).
    - ``drain_per_min`` / ``drain_per_hour``: ``_safe_drain`` returns None whenever the
      job ended with MORE battery than it started, i.e. any mid-job-recharge run, and
      ``_positive_float`` returns None for a zero or absent duration.
    So a card, user or automation reading ``unavailable`` on ``last_job_drain_per_m2``
    as "no job has run since restart" will be wrong more often than right.
    """

    _attr_state_class = "measurement"

    def __init__(
        self,
        *,
        manager: BatteryHealthManager,
        vacuum_entity_id: str,
        stat_key: str,
        translation_key: str,
        unique_suffix: str,
        unit: str,
    ) -> None:
        super().__init__(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            translation_key=translation_key,
            unique_suffix=unique_suffix,
        )
        self._stat_key = stat_key
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:battery-clock"

    @property
    def native_value(self) -> float | None:
        last = self._record().get("last_job") or {}
        value = last.get(self._stat_key)
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rec = self._record()
        last = rec.get("last_job") or {}
        agg = rec.get("job_aggregates", {}) or {}
        all_jobs = agg.get("all_jobs", {}) or {}
        # Map the sensor's stat to the matching aggregate field.
        mean_field = {
            "drain_per_min":  "drain_per_min_mean",
            "drain_per_hour": "drain_per_hour_mean",
            "drain_per_m2":   "drain_per_m2_mean",
        }.get(self._stat_key)
        return {
            "job_id": last.get("job_id"),
            "recorded_at": last.get("recorded_at"),
            "duration_min": last.get("duration_min"),
            "area_m2": last.get("area_m2"),
            "battery_used_pct": last.get("battery_used_pct"),
            "single_clean_mode": last.get("single_clean_mode"),
            "single_fan_speed": last.get("single_fan_speed"),
            "single_water_level": last.get("single_water_level"),
            "weighted_by": last.get("weighted_by"),
            "post_job_charge": last.get("post_job_charge"),
            "all_jobs_mean": all_jobs.get(mean_field) if mean_field else None,
            "all_jobs_count": all_jobs.get("count"),
            # B4: this is the C17 repair applied to `all_jobs` — was missing when the
            # `by_*` buckets got it, so a reader auditing the fix by looking at the card
            # saw the original symptom ("mean over 6, Jobs: 10") on the very row the
            # comment on `_MEAN_SAMPLE_FIELD` cites. `all_jobs` is a `_new_aggregate_bucket`
            # and carries the same `samples_duration` / `samples_area` fields the
            # `by_*` buckets read from — this line just puts the honest denominator next
            # to the mean, using the same lookup.
            "all_jobs_samples": (
                all_jobs.get(_MEAN_SAMPLE_FIELD[mean_field])
                if mean_field and _MEAN_SAMPLE_FIELD.get(mean_field)
                else None
            ),
            # Per-bucket means — only populated from single-bucket jobs.
            "by_clean_mode_mean": _bucket_means(agg.get("by_clean_mode", {}), mean_field),
            "by_fan_speed_mean": _bucket_means(agg.get("by_fan_speed", {}), mean_field),
            "by_water_level_mean": _bucket_means(agg.get("by_water_level", {}), mean_field),
        }


class MidJobRechargeRateSensor(_BatteryBase):
    """Mean charge rate observed during mid-job recharges.

    A firmware auto-recharge mid-clean is TYPICALLY a roughly 15→75 window in the CC
    region with the pack hot from cleaning, and over charges like that a drop here would
    be an early-warning indicator before either the 0→100 baseline or the high-zone
    metric moves. That is the motive for the sensor and it still stands.

    ⚠ 15→75 IS AN OBSERVATION OF THE DEVICE, NOT A GATE. This read "(the 15→75 window)
    ... tight start/end zone, pure CC charging region, consistent thermal load" until
    2026-08-24, and those three guarantees are what justified calling it "the cleanest
    health signal available". Nothing enforces them:
    ``BatteryHealthManager._classify_session_kind`` tags a session ``"mid_job"`` purely
    because ``_has_active_job`` was true, and ``_update_mid_job_rate_stat`` is then
    called for any positive-delta charge at any start and end percentage. A user who
    docks a job-paused vacuum at 60% and undocks at 64% moves this mean exactly as a
    full 15→75 auto-resume cycle does.
    """

    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = "%/min"
    _attr_icon = "mdi:battery-charging-wireless"

    def __init__(self, *, manager: BatteryHealthManager, vacuum_entity_id: str) -> None:
        super().__init__(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            translation_key="mid_job_recharge_rate",
            unique_suffix="mid_job_recharge_rate",
        )

    @property
    def native_value(self) -> float | None:
        stats = self._record().get("mid_job_recharge_stats") or {}
        value = stats.get("rate_mean_per_min")
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self._record().get("mid_job_recharge_stats") or {}
        return {
            "sample_count": stats.get("count"),
            "last_rate_per_min": stats.get("last_rate_per_min"),
            "last_recorded_at": stats.get("last_recorded_at"),
        }


#: Which honest denominator belongs to which mean (C17). ``count`` counts every job
#: in the bucket; a mean is computed only over the jobs that carried BOTH of its
#: inputs. Publishing the pair without this was the second half of the defect — the
#: card showed "3.333 %/m2 — Jobs: 10" where the mean was over six.
_MEAN_SAMPLE_FIELD = {
    "drain_per_min_mean": "samples_duration",
    "drain_per_hour_mean": "samples_duration",
    "drain_per_m2_mean": "samples_area",
}


def _bucket_means(buckets: dict, mean_field: str | None) -> dict:
    """Compact projection of bucketed aggregates for sensor attributes.

    Emits ``samples`` beside ``mean``: the number of jobs the mean was actually
    computed over. ``count`` stays, because it is a true and separate fact about the
    bucket — but it is no longer the only number next to a mean it does not describe.
    """
    if not isinstance(buckets, dict) or not mean_field:
        return {}
    sample_field = _MEAN_SAMPLE_FIELD.get(mean_field)
    out = {}
    for key, b in buckets.items():
        if not isinstance(b, dict):
            continue
        out[key] = {
            "count": b.get("count"),
            "mean": b.get(mean_field),
            "samples": b.get(sample_field) if sample_field else None,
        }
    return out
