"""Run-active pose sampler (W5b) — records the per-tick pose time-series during an
EXTERNAL (app-started) run, for room auto-attribution.

This is the production version of the throwaway ``debug_log_live_room`` probe: it polls
the fork's in-memory pose (``async_get_map_live_pose``) at the adapter's room_attribution
cadence and buffers one ``{current_room, anchor, cleaning_area}`` sample per tick into the
external slot's ``pose_samples`` (via ``record_pose_sample``).

**Capture-only / inert** — nothing consumes ``pose_samples`` yet (the engine wiring is W5c).

Gating:
  - EXTERNAL runs only (dispatched runs already know their rooms).
  - Map-capable vacuums only: ``current_room`` is map-data-derived, so a vacuum whose adapter
    declares no ``map_state_source.live_pose`` is skipped (its pose would be all-``None``).
  - The sampling cadence ``interval_s`` comes from the adapter's ``room_attribution`` block —
    NEVER hardcoded here (the engine's ``dwell`` thresholds assume the same cadence; one
    adapter value drives both, mirroring ``job_segmenter.tuning``).

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager
from ..learning.room_attribution_engines import get_room_attribution_engine

_LOGGER = logging.getLogger(__name__)

_POSE_SAMPLER_UNSUBS = "_pose_sampler_unsubs"
# Absolute last-resort cadence — only if the resolved engine declares no interval_s default
# at all (e.g. the noop engine). The OPERATIVE default comes from the engine's DEFAULT_TUNING
# (single source, no duplicated literal); the OPERATIVE value from the adapter's tuning.
_FALLBACK_INTERVAL_S = 2.0


def _room_attribution_interval_s(vacuum_entity_id: str) -> float | None:
    """The sampling cadence for a vacuum, or None when its adapter declares no
    room_attribution (→ that vacuum is not sampled). Single-source resolution: the adapter's
    ``room_attribution.tuning.interval_s`` → else the resolved engine's
    ``DEFAULT_TUNING['interval_s']`` → else ``_FALLBACK_INTERVAL_S``."""
    cfg = get_adapter_config(vacuum_entity_id) or {}
    attr = cfg.get("room_attribution")
    if not isinstance(attr, dict):
        return None
    tuning = attr.get("tuning") if isinstance(attr.get("tuning"), dict) else {}
    value = tuning.get("interval_s")
    if value is None:
        engine = get_room_attribution_engine(attr.get("engine"))
        value = getattr(engine, "DEFAULT_TUNING", {}).get("interval_s")
    try:
        return float(value) if value is not None else _FALLBACK_INTERVAL_S
    except (TypeError, ValueError):
        return _FALLBACK_INTERVAL_S


def _has_live_map(vacuum_entity_id: str) -> bool:
    """Whether the adapter declares a live-pose map source. Without it, current_room is
    always None and sampling is pointless."""
    cfg = get_adapter_config(vacuum_entity_id) or {}
    src = cfg.get("map_state_source")
    return isinstance(src, dict) and isinstance(src.get("live_pose"), dict)


async def _sample_vacuum_once(hass, manager, vacuum_entity_id: str) -> int:
    """Sample one vacuum's active EXTERNAL run(s) this tick; returns samples recorded.

    Skips non-attribution / no-live-map vacuums, non-external maps, and ticks where the
    live pose isn't present. Extracted from the ticker so it's unit-testable."""
    if _room_attribution_interval_s(vacuum_entity_id) is None or not _has_live_map(vacuum_entity_id):
        return 0
    recorded = 0
    for map_id in manager.get_known_map_ids(vacuum_entity_id):
        map_id_str = str(map_id)
        if map_id_str.strip().lower() == "unknown":
            continue
        active = manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id_str)
        if active.get("status") != "external":
            continue
        try:
            pose = await manager.async_get_map_live_pose(vacuum_entity_id=vacuum_entity_id)
        except Exception:
            _LOGGER.exception(
                "eufy_vacuum: pose-sample tick failed for %s/%s", vacuum_entity_id, map_id_str
            )
            continue
        if not pose.get("present"):
            continue  # no live map this tick — skip, don't pollute the buffer

        # Read cleaning_area (the engine's robust clean-vs-park separator) from the adapter's
        # DECLARED entity — never a guessed sensor name (adapter discipline; a brand whose
        # entity is named differently would otherwise silently buffer None and demote the
        # engine to its false-positive anchor-only mode).
        cfg = get_adapter_config(vacuum_entity_id) or {}
        ca_id = cfg.get("entities", {}).get("cleaning_area")
        ca_state = hass.states.get(ca_id) if ca_id else None
        try:
            cleaning_area = float(ca_state.state) if ca_state is not None else None
        except (TypeError, ValueError):
            cleaning_area = None

        # While docked the fork anchors to the DOCK — current_room becomes the dock's room id
        # and anchor the dock pixel. Null both so a parked dock is a genuine None-run: that's
        # what excludes it in anchor-only mode (robust mode also excludes it via ~0 swept area).
        # current_room may also be None genuinely (off-raster transit) — recorded on purpose.
        docked = bool(pose.get("robot_docked"))
        if manager.record_pose_sample(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
            current_room=None if docked else pose.get("current_room"),
            anchor=None if docked else pose.get("robot_anchor"),
            cleaning_area=cleaning_area,
            heading=pose.get("robot_heading"),
        ):
            recorded += 1
    return recorded


def remove(hass: HomeAssistant) -> None:
    """Tear down the pose sampler."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_POSE_SAMPLER_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover
            pass


def register(hass: HomeAssistant) -> None:
    """Sample pose into external runs at the adapter's room_attribution cadence."""
    remove(hass)

    domain_data = hass.data.setdefault(DOMAIN, {})
    manager: EufyVacuumManager | None = domain_data.get(DATA_RUNTIME)
    if manager is None:
        return

    # Cadence = the smallest declared room_attribution.interval_s across configured vacuums;
    # one ticker samples all of them. Read from the adapter — never hardcoded. No adapter
    # wants room attribution → no sampler at all.
    # LIMITATION (F4, deferred): if a future 2nd brand declares a DIFFERENT interval, its
    # slower vacuums get over-sampled vs the engine's dwell = n*interval_s assumption. Each
    # sample already carries a wall-clock `t`, so the fix is per-vacuum tickers (or have the
    # engine derive dwell from `t` deltas). Unreachable while only Eufy declares attribution.
    intervals = [
        i for i in (_room_attribution_interval_s(vid) for vid in manager.get_known_vacuum_ids())
        if i is not None and i > 0
    ]
    if not intervals:
        return
    interval_s = min(intervals)

    async def _handle_pose_tick(_now) -> None:
        for vacuum_entity_id in manager.get_known_vacuum_ids():
            await _sample_vacuum_once(hass, manager, vacuum_entity_id)

    unsub = async_track_time_interval(hass, _handle_pose_tick, timedelta(seconds=interval_s))
    domain_data[_POSE_SAMPLER_UNSUBS] = [unsub]
