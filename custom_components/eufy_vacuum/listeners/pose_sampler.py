"""Run-active pose sampler (W5b) — records the per-tick pose time-series during an
EXTERNAL (app-started) run, for room auto-attribution.

This is the production version of the throwaway ``debug_log_live_room`` probe: at the
adapter's room_attribution cadence it captures the live room via the adapter's declared
``room_attribution.source`` (Eufy fork pose ``async_get_map_live_pose``, or a brand's native
current-room NAME entity) and buffers one ``{current_room, anchor, cleaning_area}`` sample per
tick into the external slot's ``pose_samples`` (via ``record_pose_sample``).

**Capture-only / inert** — nothing consumes ``pose_samples`` yet (the engine wiring is W5c).

Gating:
  - EXTERNAL runs only (dispatched runs already know their rooms).
  - Attribution-capable vacuums only: the adapter's ``room_attribution.source`` selects HOW
    ``current_room`` is captured — ``live_pose`` (Eufy fork: a raster-lookup of the robot pixel
    in the decoded map, ``async_get_map_live_pose``) or ``native_current_room`` (Roborock: the
    brand publishes the live room directly as a NAME entity, ``entities.active_cleaning_target``,
    which the sampler slugifies + matches to a managed room id). A vacuum missing its source's
    signal is skipped (its ``current_room`` would be all-``None``). ``source`` defaults to
    ``live_pose`` when the block predates the key.
  - The sampling cadence ``interval_s`` comes from the adapter's ``room_attribution`` block —
    NEVER hardcoded here. It is the single source: the sampler ticks at it, and the engine
    converts ticks→seconds with it. The engine's ``dwell`` gate is measured in TICKS
    (``DWELL_MIN_TICKS``), so the DECISION is cadence-independent — a brand tunes the tick
    count to its own cadence, mirroring ``job_segmenter.tuning``.

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
from ..rooms.utils import slugify_room_name

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


def _room_attribution_source(vacuum_entity_id: str) -> str:
    """The declared capture source for a vacuum's room_attribution — how ``current_room`` is
    read this tick. Defaults to ``live_pose`` (back-compat: the block predates the key)."""
    cfg = get_adapter_config(vacuum_entity_id) or {}
    attr = cfg.get("room_attribution")
    if not isinstance(attr, dict):
        return "live_pose"
    return str(attr.get("source") or "live_pose").strip().lower()


def _can_sample(vacuum_entity_id: str) -> bool:
    """Whether the adapter declares the signal its ``room_attribution.source`` needs. Without
    it, ``current_room`` is always None and sampling is pointless:
      - ``live_pose``: a ``map_state_source.live_pose`` block (the fork's decoded pose).
      - ``native_current_room``: an ``entities.active_cleaning_target`` entity (the room NAME).
    """
    cfg = get_adapter_config(vacuum_entity_id) or {}
    if _room_attribution_source(vacuum_entity_id) == "native_current_room":
        return bool((cfg.get("entities", {}) or {}).get("active_cleaning_target"))
    src = cfg.get("map_state_source")
    return isinstance(src, dict) and isinstance(src.get("live_pose"), dict)


def _is_parked(hass, cfg: dict, pose: dict) -> bool:
    """True when the robot is parked / not floor-cleaning, so this tick's pose reflects the
    DOCK (or a station cycle) rather than a cleaned room → null current_room/anchor for it.

    Primary signal: the MQTT-backed ``task_status`` is present and NOT an active-run state
    (the adapter's ``vocabulary.active_run_task_states``) — i.e. Completed / Washing Mop /
    Emptying Dust / Charging / docked. That signal is reliable and flips on time, UNLIKE the
    fork's pose ``robot_docked`` flag, which can stay ``False`` through a real dock (observed
    live: it sat reporting the robot "in" the dock room for ~13 min after a ``Completed`` dock,
    so 100 dock-sitting ticks were recorded as that room). ``returning``/``navigating`` ARE
    active-run states, so they are NOT nulled here — their ~0 swept area lets the engine label
    them transit. We fall back to the pose flag only when task_status can't be read (no declared
    entity / unavailable state / no vocab — e.g. a future non-Eufy brand)."""
    vocab = cfg.get("vocabulary") or {}
    active = {str(s).strip().lower() for s in (vocab.get("active_run_task_states") or [])}
    ts_id = (cfg.get("entities", {}) or {}).get("task_status")
    if active and ts_id:
        state_obj = hass.states.get(ts_id)
        value = str(getattr(state_obj, "state", "") or "").strip().lower()
        if value and value not in {"unknown", "unavailable"}:
            return value not in active
    return bool(pose.get("robot_docked"))


def _read_cleaning_area(hass, cfg: dict) -> float | None:
    """The declared cleaning_area entity's value as a float, or None. Read from the adapter's
    DECLARED entity — never a guessed sensor name (adapter discipline; a brand whose entity is
    named differently would otherwise silently buffer None and demote the engine to its
    false-positive anchor-only mode). cleaning_area is the engine's robust clean-vs-park
    separator (FLAT while parked/washing, climbs while cleaning)."""
    ca_id = (cfg.get("entities", {}) or {}).get("cleaning_area")
    ca_state = hass.states.get(ca_id) if ca_id else None
    try:
        return float(ca_state.state) if ca_state is not None else None
    except (TypeError, ValueError):
        return None


def _resolve_managed_room_id(
    hass, manager, vacuum_entity_id: str, cfg: dict, map_id_str: str
) -> int | None:
    """Resolve the brand's NATIVE current-room NAME (``entities.active_cleaning_target``, e.g.
    Roborock ``sensor.<id>_current_room``) to a MANAGED room id on this map, by slug.

    Mirrors ``ActiveJobTracker._resolve_native_target_room_id`` but matches against ALL managed
    rooms (an external run has no job targets to match against), not the job queue. Returns None
    for the dock / a transit room / a sentinel / any name not among the managed rooms — recorded
    as a None current_room (transit), which the engine ignores."""
    entity_id = (cfg.get("entities", {}) or {}).get("active_cleaning_target")
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    name = str(getattr(state, "state", "") or "").strip()
    if not name or name.lower() in {"unknown", "unavailable", "none", "null"}:
        return None
    signal_slug = slugify_room_name(name)
    managed = manager.get_managed_rooms(vacuum_entity_id=vacuum_entity_id, map_id=map_id_str)
    rooms = managed.get("rooms", {}) if isinstance(managed, dict) else {}
    for key, room in rooms.items():
        if not isinstance(room, dict):
            continue
        room_slug = (
            str(room.get("slug") or "").strip().lower()
            or slugify_room_name(str(room.get("name") or room.get("room_name") or ""))
        )
        if room_slug and room_slug == signal_slug:
            try:
                return int(room.get("room_id", key))
            except (TypeError, ValueError):
                return None
    return None


async def _read_live_pose_sample(hass, manager, vacuum_entity_id: str, cfg: dict) -> dict | None:
    """``source: live_pose`` — the Eufy fork's decoded-map pixel pose. Returns a normalized
    sample, or None to SKIP this tick (no live map decoded → don't pollute the buffer).

    While parked/docked the fork anchors to the DOCK — current_room becomes the dock's room id
    and anchor the dock pixel. Null both so a parked dock is a genuine None-run (excluded in
    anchor-only mode; robust mode also excludes it via ~0 swept area). The parked signal is the
    MQTT task_status (reliable), NOT the pose's own robot_docked flag (which can stay False
    through a real dock) — see _is_parked. current_room may also be None genuinely (off-raster
    transit) — recorded on purpose."""
    try:
        pose = await manager.async_get_map_live_pose(vacuum_entity_id=vacuum_entity_id)
    except Exception:
        _LOGGER.exception("eufy_vacuum: pose-sample tick failed for %s", vacuum_entity_id)
        return None
    if not pose.get("present"):
        return None  # no live map this tick — skip, don't pollute the buffer
    docked = _is_parked(hass, cfg, pose)
    return {
        "current_room": None if docked else pose.get("current_room"),
        "anchor": None if docked else pose.get("robot_anchor"),
        "cleaning_area": _read_cleaning_area(hass, cfg),
        "heading": pose.get("robot_heading"),
    }


def _read_native_current_room_sample(
    hass, manager, vacuum_entity_id: str, cfg: dict, map_id_str: str
) -> dict:
    """``source: native_current_room`` — the brand publishes the live room as a NAME entity (no
    pixel pose). Resolve name→managed-room-id; anchor/heading stay None (the engine's swept-area
    path attributes it POSE-FREE; the pose-only spread/winding simply don't fire).

    Always returns a sample — a momentarily unknown/unavailable entity is a genuine None
    current_room (transit / off-target), NOT a capture failure to skip. The parked signal is
    the MQTT task_status (``_is_parked`` with no pose flag), so a docked tick (Roborock reverts
    active_cleaning_target to the dock room, task_status → charging) is nulled to None."""
    docked = _is_parked(hass, cfg, {})  # no pose flag — task_status is the parked signal
    room_id = None if docked else _resolve_managed_room_id(
        hass, manager, vacuum_entity_id, cfg, map_id_str
    )
    return {
        "current_room": room_id,
        "anchor": None,
        "cleaning_area": _read_cleaning_area(hass, cfg),
        "heading": None,
    }


async def _sample_vacuum_once(hass, manager, vacuum_entity_id: str) -> int:
    """Sample one vacuum's active EXTERNAL run(s) this tick; returns samples recorded.

    Skips non-attribution vacuums, vacuums missing their declared capture source's signal,
    non-external maps, and (live_pose only) ticks where the live pose isn't present. The capture
    path is chosen by the adapter's ``room_attribution.source``. Extracted so it's unit-testable."""
    if _room_attribution_interval_s(vacuum_entity_id) is None or not _can_sample(vacuum_entity_id):
        return 0
    cfg = get_adapter_config(vacuum_entity_id) or {}
    source = _room_attribution_source(vacuum_entity_id)
    recorded = 0
    for map_id in manager.get_known_map_ids(vacuum_entity_id):
        map_id_str = str(map_id)
        if map_id_str.strip().lower() == "unknown":
            continue
        active = manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id_str)
        if active.get("status") != "external":
            continue

        if source == "native_current_room":
            sample = _read_native_current_room_sample(
                hass, manager, vacuum_entity_id, cfg, map_id_str
            )
        else:
            sample = await _read_live_pose_sample(hass, manager, vacuum_entity_id, cfg)
        if sample is None:
            continue

        if manager.record_pose_sample(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
            current_room=sample["current_room"],
            anchor=sample["anchor"],
            cleaning_area=sample["cleaning_area"],
            heading=sample["heading"],
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
