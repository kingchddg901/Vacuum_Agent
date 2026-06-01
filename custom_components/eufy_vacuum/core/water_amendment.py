"""
Post-job mop wash water amendment for the eufy_vacuum framework.

Some docks wash the mop pad after the robot docks from a mop job. This
begins a few seconds after job finalization — after the completed job file
has already been written with water actuals based on the state at that
moment.

This module registers a short-lived watcher that patches the completed
job file once the dock finishes its post-job wash cycle. The watcher:

  1. Subscribes to dock_status state changes.
  2. Counts wash cycles using the adapter's debounce interval to avoid
     double-counting a multi-state wash sequence.
  3. Commits corrected water actuals when dock_status transitions to the
     adapter's configured commit state.
  4. Times out after the adapter's configured timeout if the commit state
     never fires.

Entity IDs, trigger states, and commit state all come from the adapter
registry — no brand-specific knowledge lives here.

The watcher is idempotent on job_id — registering it twice for the same
job is a no-op.

To disable this for a brand that does not need it, set
post_job_wash_amendment.enabled = False in the adapter config, or simply
do not call register_post_job_water_amendment() from __init__.py.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from ..adapters.registry import get_adapter_config
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def register_post_job_water_amendment(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    job_id: str,
    job_path: str,
    water_start_percent: float,
    mop_wash_count_at_finalization: int,
    debounce_seconds: float = 60.0,
    timeout_seconds: int = 180,
) -> None:
    """Watch for post-job mop wash and patch completed job water actuals.

    Entity IDs, trigger states, and commit state are read from the adapter
    registry. debounce_seconds and timeout_seconds are passed by the caller
    (which reads them from adapter_config.post_job_wash_amendment); the
    defaults here are last-resort fallbacks only.

    Idempotent on ``job_id`` — the lifecycle handler that calls this can
    fire multiple times for the same finalized job, and each registration
    would otherwise leak its own set of listeners and timeout.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    registered_jobs: set[str] = domain_data.setdefault(
        "_water_amendment_jobs", set()
    )
    if job_id in registered_jobs:
        return
    registered_jobs.add(job_id)

    _adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
    _entities = _adapter_cfg.get("entities", {})
    _amendment_cfg = _adapter_cfg.get("post_job_wash_amendment", {})

    dock_status_entity = _entities.get("dock_status")
    water_level_entity = _entities.get("water_level")

    if not dock_status_entity:
        _LOGGER.debug(
            "post_job_water_amendment: no dock_status entity for %s — skipping",
            vacuum_entity_id,
        )
        registered_jobs.discard(job_id)
        return

    _raw_triggers = _amendment_cfg.get("trigger_states") or ["washing", "washing mop"]
    _trigger_states: frozenset[str] = frozenset(
        str(s).strip().lower() for s in _raw_triggers
    )
    _commit_state: str = str(
        _amendment_cfg.get("commit_state") or "drying"
    ).strip().lower()

    amendment_state: dict = {"wash_count": 0, "committed": False, "last_wash_at": 0.0}
    unsub_listener: list[Callable] = []
    unsub_timeout: list[Callable] = []

    def _cancel_all() -> None:
        for fn in unsub_listener:
            try:
                fn()
            except Exception:  # pragma: no cover - best-effort teardown
                pass
        for fn in unsub_timeout:
            try:
                fn()
            except Exception:  # pragma: no cover - best-effort teardown
                pass
        unsub_listener.clear()
        unsub_timeout.clear()

    def _write_amendment(end_percent: float | None, wash_count: int) -> None:
        path = Path(job_path)
        if not path.exists():
            return
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover - best-effort I/O, logs and swallows
            _LOGGER.exception("post_job_water_amendment: failed to read %s", job_path)
            return

        water = job.get("water")
        if not isinstance(water, dict):
            return

        total_wash_count = mop_wash_count_at_finalization + wash_count
        water["actual_mop_wash_count"] = total_wash_count
        water["actual_end_station_clean_water_percent"] = end_percent

        start_pct = water.get("station_clean_water_percent")
        # Hardware constants are carried in the job file at write time.
        # Use None as fallback — the None check below skips the calculation
        # cleanly rather than using a wrong brand-specific constant.
        capacity_ml = water.get("dock_clean_tank_capacity_ml")
        overhead_per_cycle = water.get("dock_wash_overhead_ml_per_cycle")

        tank_emptied = end_percent is not None and end_percent <= 0.0

        if (
            end_percent is not None
            and isinstance(start_pct, (int, float))
            and isinstance(capacity_ml, (int, float))
            and capacity_ml > 0
            and isinstance(overhead_per_cycle, (int, float))
            and start_pct >= end_percent
        ):
            actual_total_ml = round((start_pct - end_percent) / 100.0 * capacity_ml, 1)
            actual_wash_ml = round(total_wash_count * overhead_per_cycle, 1)
            actual_floor_ml = round(max(actual_total_ml - actual_wash_ml, 0.0), 1) if not tank_emptied else None
            estimated = water.get("estimated_total_dock_clean_water_used_ml") or 0.0
            water["actual_dock_water_used_ml"] = actual_total_ml
            water["actual_mop_wash_water_ml"] = actual_wash_ml
            water["actual_floor_water_ml"] = actual_floor_ml
            water["actual_vs_estimated_delta_ml"] = round(actual_total_ml - float(estimated), 1) if not tank_emptied else None
        else:
            water["actual_dock_water_used_ml"] = None
            water["actual_mop_wash_water_ml"] = None
            water["actual_floor_water_ml"] = None
            water["actual_vs_estimated_delta_ml"] = None

        water["actual_tank_emptied"] = tank_emptied

        from ..learning.utils import _iso_now
        water["water_amended_at"] = _iso_now()
        water["water_amendment_reason"] = "post_job_wash"
        job["water"] = water

        try:
            # Atomic write via temp file + rename. POSIX rename is atomic, so
            # any concurrent reader sees either the pre-patch or post-patch
            # file — never a half-written interleaved state.
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(job, indent=2), encoding="utf-8")
            os.replace(tmp, path)
            _LOGGER.debug(
                "post_job_water_amendment: patched %s wash_count=%d end_pct=%s",
                job_id, total_wash_count, end_percent,
            )
        except Exception:  # pragma: no cover - best-effort I/O, logs and swallows
            _LOGGER.exception("post_job_water_amendment: failed to write %s", job_path)

    @callback
    def _commit(reason: str) -> None:
        if amendment_state["committed"]:
            return
        amendment_state["committed"] = True
        _cancel_all()

        # Only write if something actually happened during the window.
        if amendment_state["wash_count"] == 0 and reason == "timeout":
            return

        end_pct: float | None = None
        if water_level_entity:
            water_state = hass.states.get(water_level_entity)
            if water_state and water_state.state not in ("unavailable", "unknown"):
                try:
                    end_pct = float(water_state.state)
                except (ValueError, TypeError):
                    pass

        wash_count = amendment_state["wash_count"]
        async def _flush_amendment() -> None:
            await hass.async_add_executor_job(
                _write_amendment, end_pct, wash_count
            )
        hass.async_create_task(_flush_amendment())

    _MIN_WASH_INTERVAL_SECONDS = debounce_seconds

    @callback
    def _on_dock_change(event: Event) -> None:
        import time as _time
        new_state_obj = event.data.get("new_state")
        new_state = str(getattr(new_state_obj, "state", "") or "").strip().lower()
        if new_state in _trigger_states:
            now = _time.monotonic()
            if now - amendment_state["last_wash_at"] >= _MIN_WASH_INTERVAL_SECONDS:
                amendment_state["wash_count"] += 1
                amendment_state["last_wash_at"] = now
        elif new_state == _commit_state:
            _commit("drying")

    @callback
    def _on_timeout(_now) -> None:
        _commit("timeout")

    unsub_listener.append(
        async_track_state_change_event(hass, [dock_status_entity], _on_dock_change)
    )
    unsub_timeout.append(async_call_later(hass, timeout_seconds, _on_timeout))
