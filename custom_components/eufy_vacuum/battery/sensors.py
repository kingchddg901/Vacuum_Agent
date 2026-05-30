"""Battery health sensors backed by BatteryHealthManager.

Sensors per vacuum:
- {object_id}_charge_cycles      — cumulative cycles (drain ÷ 100)
- {object_id}_charge_rate        — instantaneous %/min (overall, while charging)
- {object_id}_charge_rate_low_zone   — %/min while battery ≤ 29%
- {object_id}_charge_rate_high_zone  — %/min while battery ≥ 80%
- {object_id}_last_charge_duration   — minutes for the last completed session
- {object_id}_battery_health     — % vs install baseline (CV regime — resistance proxy)
- {object_id}_cc_charge_speed    — % vs install baseline, CC regime (capacity proxy)
- {object_id}_cv_charge_speed    — % vs install baseline, CV regime (resistance proxy)
- {object_id}_last_job_drain_per_min / per_hour / per_m2 — last-job drain rates
- {object_id}_mid_job_recharge_rate  — rolling mean of mid-job recharge rates

All sensors pull from the same in-memory record; a single update listener
fans out state writes whenever the manager processes a new sample.

The CC/CV regimes age in opposite directions — capacity loss raises %/min
in the 50→80 CC region, resistance rise lowers %/min in the 80→90 CV taper —
so they're tracked separately. _battery_health is an alias of _cv_charge_speed
for entity_id continuity with installs that pre-date the regime split.
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
        # Mid-job recharge rate — high-quality health signal (consistent
        # 15→75 zone, no top taper variance).
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
        # Pin the entity_id to match the unique_suffix so the card's state
        # lookup never drifts when a label is changed. Without this, HA
        # slugifies _attr_name to derive entity_id, which can diverge from
        # the suffix (e.g. label "Last Job Drain Rate" + suffix
        # "last_job_drain_per_min" produced two different ids).
        object_id = vacuum_entity_id.split(".", 1)[-1]
        self._attr_suggested_object_id = f"{object_id}_{unique_suffix}"
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
    """Minutes the most recent completed charge session took."""

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

    Headline alias of cv_charge_speed_pct (the resistance-proxy regime).
    Kept under the _battery_health entity_id for continuity with installs
    that pre-date the regime split. None until the baseline is anchored.
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
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rec = self._record()
        baseline = rec.get("baseline", {})
        history = rec.get("session_history_recent", [])
        return {
            # The headline tracks the CV regime, so surface that anchor by
            # default. cc_min_per_pct is also exposed for visibility.
            "baseline_cv_min_per_pct": baseline.get("cv_min_per_pct"),
            "baseline_cc_min_per_pct": baseline.get("cc_min_per_pct"),
            "baseline_session_count": baseline.get("session_count"),
            "baseline_anchored_at": baseline.get("anchored_at"),
            "completed_sessions": len(history),
        }


class RegimeChargeSpeedSensor(_BatteryBase):
    """Per-regime charge-speed % vs install baseline (CC or CV).

    Reads ``stats.<stat_key>`` and surfaces the matching baseline anchor
    in attributes. Returns None until the baseline is anchored. Two
    instances live side-by-side (CC and CV) so users can read the
    capacity and resistance signals independently.
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
        baseline = self._record().get("baseline", {})
        return {
            "baseline_min_per_pct": baseline.get(self._baseline_key),
            "baseline_session_count": baseline.get("session_count"),
            "baseline_anchored_at": baseline.get("anchored_at"),
        }


class LastJobMetricSensor(_BatteryBase):
    """Generic sensor exposing one of the last-job battery_metrics fields.

    State is the most recent completed job's metric (None if no job yet).
    Attributes also surface the running per-clean-mode / per-fan-speed /
    per-water-level aggregates so a card can chart trends without separate
    queries.
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
            # Per-bucket means — only populated from single-bucket jobs.
            "by_clean_mode_mean": _bucket_means(agg.get("by_clean_mode", {}), mean_field),
            "by_fan_speed_mean": _bucket_means(agg.get("by_fan_speed", {}), mean_field),
            "by_water_level_mean": _bucket_means(agg.get("by_water_level", {}), mean_field),
        }


class MidJobRechargeRateSensor(_BatteryBase):
    """Mean charge rate observed during mid-job recharges (the 15→75 window).

    The cleanest health signal available: tight start/end zone, pure CC
    charging region, consistent thermal load. A drop here is an early-warning
    indicator before either the 0→100 baseline or the high-zone metric move.
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


def _bucket_means(buckets: dict, mean_field: str | None) -> dict:
    """Compact projection of bucketed aggregates for sensor attributes."""
    if not isinstance(buckets, dict) or not mean_field:
        return {}
    out = {}
    for key, b in buckets.items():
        if not isinstance(b, dict):
            continue
        out[key] = {
            "count": b.get("count"),
            "mean": b.get(mean_field),
        }
    return out
