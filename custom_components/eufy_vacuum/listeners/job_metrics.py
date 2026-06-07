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

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

_JOB_METRICS_UNSUBS = "_job_metrics_unsubs"


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

    # Build a map of entity_id → (vacuum_entity_id, active_job_state_key, type)
    # for every vacuum whose adapter config exposes these entities.
    watch_map: dict[str, tuple[str, str, str]] = {}
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
            watch_map[ct_entity] = (vacuum_entity_id, "last_cleaning_time_seconds", "int")

        ca_entity = entities.get("cleaning_area")
        if ca_entity:
            watch_map[ca_entity] = (vacuum_entity_id, "last_cleaning_area_m2", "float")

        # Station water level — lives in capabilities entities, not the main
        # entities dict. Only added when the capability is exposed.
        try:
            caps = manager.get_vacuum_capabilities(
                vacuum_entity_id=vacuum_entity_id, refresh=False
            )
            water_entity = (
                caps.get("entities", {}).get("water_level")
                or caps.get("entities", {}).get("station_water")
            )
            if water_entity:
                watch_map[water_entity] = (
                    vacuum_entity_id, "last_station_water_percent", "float"
                )
        except Exception:
            pass

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

        vacuum_entity_id, key, value_type = entry
        manager_local: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager_local is None:
            return

        try:
            value = int(float(raw)) if value_type == "int" else float(raw)
        except (TypeError, ValueError):
            return

        manager_local.record_active_job_sensor_value(
            vacuum_entity_id=vacuum_entity_id,
            key=key,
            value=value,
        )

        # cleaning_time additionally drives per-room segmentation (transit times).
        if key == "last_cleaning_time_seconds":
            manager_local.record_cleaning_time_sample(
                vacuum_entity_id=vacuum_entity_id,
                value_seconds=value,
            )

    unsub = async_track_state_change_event(
        hass,
        list(watch_map.keys()),
        _handle_metrics_change,
    )

    domain_data[_JOB_METRICS_UNSUBS] = [unsub]
