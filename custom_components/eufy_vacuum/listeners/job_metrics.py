"""Job metrics listeners — push cleaning_time / cleaning_area / station water
sensor values into active_job_state as they update.

These sensors update during the run via DPS packets, but finalization fires on
a separate DPS packet (task_status → Completed) that may arrive before the
sensor values have landed in HA's state machine. By pushing the last-seen
value into active_job_state as each update arrives, finalization reads from
there instead of issuing a live HA state read at job-end.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager
from ..learning.utils import cleaning_area_to_m2

_LOGGER = logging.getLogger(__name__)

_JOB_METRICS_UNSUBS = "_job_metrics_unsubs"

_SECOND_UNIT_ALIASES = frozenset({"s", "sec", "secs", "second", "seconds"})
# METRICS-3: warn once per distinct unrecognized unit, not once per event —
# a plateau-sampling counter can fire this path many times a minute.
_WARNED_UNKNOWN_DURATION_UNITS: set[str] = set()


def _duration_state_to_seconds(raw: Any, unit: Any) -> int:
    """Convert a Home Assistant duration state to seconds."""
    value = float(raw)
    normalized_unit = str(unit or "").strip().lower()
    if normalized_unit in {"ms", "millisecond", "milliseconds"}:
        return int(round(value / 1000.0))
    if normalized_unit in {"min", "mins", "minute", "minutes"}:
        return int(round(value * 60.0))
    if normalized_unit in {"h", "hr", "hrs", "hour", "hours"}:
        return int(round(value * 3600.0))
    if normalized_unit and normalized_unit not in _SECOND_UNIT_ALIASES:
        # No d/w/µs handling — an unrecognized unit silently fell through to
        # "assume seconds" with no signal at all. A firmware reporting e.g.
        # days or microseconds would be silently off by up to ~6 orders of
        # magnitude; log it once so that's discoverable.
        if normalized_unit not in _WARNED_UNKNOWN_DURATION_UNITS:
            _WARNED_UNKNOWN_DURATION_UNITS.add(normalized_unit)
            _LOGGER.warning(
                "job_metrics: unrecognized duration unit %r — assuming seconds",
                unit,
            )
    return int(round(value))


def remove(hass: HomeAssistant) -> None:
    """Remove job metrics state listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_JOB_METRICS_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover - best-effort teardown
            _LOGGER.exception("Failed to remove job metrics listener")


def register(hass: HomeAssistant) -> None:
    """Register listeners that push job-metric sensor values into active_job_state.

    Tracks cleaning_time, cleaning_area, and station water level. These
    sensors update during the run via DPS packets, but finalization fires on
    a separate DPS packet (task_status → Completed) that may arrive before
    the sensor values have landed in HA's state machine. By pushing the
    last-seen value into active_job_state as each update arrives, finalization
    reads from there instead of issuing a live HA state read at job-end.
    """
    remove(hass)

    domain_data = hass.data.get(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    # Build a map of entity_id → (vacuum_entity_id, active_job_state_key, type,
    # unit_hint) for every vacuum whose adapter config exposes these entities.
    # METRICS-5: every writer below stores a 4-tuple (unit_hint trails, None
    # when the value type carries no unit ambiguity) and the unpack at
    # _handle_metrics_change matches — the annotation was a stale 3-tuple.
    watch_map: dict[str, tuple[str, str, str, str | None]] = {}
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        config = get_adapter_config(vacuum_entity_id)
        entities = (config or {}).get("entities", {})

        # Only watch entities the adapter explicitly declares. If an entity
        # key is absent the listener simply doesn't subscribe — finalization
        # falls through to its sensor and wall-clock fallbacks. Guessing at
        # a brand-specific name would silently subscribe to a nonexistent
        # entity on any adapter that doesn't expose it.
        ct_entity = entities.get("cleaning_time")
        if ct_entity:
            # Some brands' cleaning_time sensor reports a BARE number with no
            # unit_of_measurement — Roborock's is in MINUTES — so the seconds
            # conversion below can't tell and would store minutes as seconds (60x
            # low). An adapter declares the true unit via `cleaning_time_unit`; it's
            # a FALLBACK only (the entity's own unit_of_measurement still wins when
            # present). Absent → unchanged (treated as seconds, e.g. Eufy).
            ct_unit_hint = str((config or {}).get("cleaning_time_unit") or "").strip() or None
            watch_map[ct_entity] = (
                vacuum_entity_id,
                "last_cleaning_time_seconds",
                "duration_seconds",
                ct_unit_hint,
            )

        ca_entity = entities.get("cleaning_area")
        if ca_entity:
            # area_m2: normalize to canonical m² by the entity's unit (an imperial HA presents
            # Eufy's cleaning_area in ft²; Roborock's stays m²) — see cleaning_area_to_m2.
            watch_map[ca_entity] = (vacuum_entity_id, "last_cleaning_area_m2", "area_m2", None)

        # RP-013e/METRICS-2/REC-5: battery has NO writer today even though both
        # shipped adapters declare entities.battery — every counter sample reads
        # last_battery_percent, and with nothing ever setting it, every sample
        # carries battery=None, which is OBS-B-3's null per-room battery_delta
        # at source. Same declared-entity pattern as cleaning_time/cleaning_area.
        battery_entity = entities.get("battery")
        if battery_entity:
            watch_map[battery_entity] = (vacuum_entity_id, "last_battery_percent", "int", None)

        # Station water level — lives in capabilities entities, not the main
        # entities dict. METRICS-4: only wired when the vacuum's capability
        # snapshot explicitly declares support (previously wired on an entity
        # KEY GUESS alone, with no supports_station_water check, and any
        # lookup failure was silently swallowed with no log).
        try:
            caps = manager.get_vacuum_capabilities(
                vacuum_entity_id=vacuum_entity_id, refresh=False
            )
        except Exception:
            _LOGGER.warning(
                "job_metrics: capability lookup failed for %s — station-water "
                "watcher not wired for this vacuum",
                vacuum_entity_id,
                exc_info=True,
            )
        else:
            if caps.get("supports_station_water"):
                water_entity = (
                    caps.get("entities", {}).get("water_level")
                    or caps.get("entities", {}).get("station_water")
                )
                if water_entity:
                    watch_map[water_entity] = (
                        vacuum_entity_id, "last_station_water_percent", "float", None
                    )

    if not watch_map:
        domain_data[_JOB_METRICS_UNSUBS] = []
        return

    @callback
    def _handle_metrics_change(event: Event) -> None:
        entity_id = str(event.data.get("entity_id", ""))
        entry = watch_map.get(entity_id)
        if entry is None:
            return

        new_state_obj = event.data.get("new_state")
        if new_state_obj is None:
            return
        raw = new_state_obj.state
        if raw in ("unavailable", "unknown", None):
            return

        vacuum_entity_id, key, value_type, unit_hint = entry
        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        try:
            if value_type == "duration_seconds":
                # Entity's own unit wins; the adapter's declared unit is the fallback
                # for a bare-number sensor (Roborock cleaning_time = minutes, no unit).
                value = _duration_state_to_seconds(
                    raw,
                    getattr(new_state_obj, "attributes", {}).get("unit_of_measurement")
                    or unit_hint,
                )
            elif value_type == "area_m2":
                # Normalize to canonical m² by the entity's unit (imperial HA → Eufy in ft²).
                value = cleaning_area_to_m2(
                    raw, getattr(new_state_obj, "attributes", {}).get("unit_of_measurement")
                )
                if value is None:
                    return
            elif value_type == "int":
                value = int(float(raw))
            else:
                value = float(raw)
        except (TypeError, ValueError):
            return

        manager_local.record_active_job_sensor_value(
            vacuum_entity_id=vacuum_entity_id,
            key=key,
            value=value,
        )

        # cleaning_time / cleaning_area changes append a counter sample (carrying
        # the last-seen of both + battery) for counter-plateau room segmentation.
        if key in ("last_cleaning_time_seconds", "last_cleaning_area_m2"):
            manager_local.record_counter_sample(vacuum_entity_id=vacuum_entity_id)

    unsub = async_track_state_change_event(
        hass,
        list(watch_map.keys()),
        _handle_metrics_change,
    )

    domain_data[_JOB_METRICS_UNSUBS] = [unsub]
