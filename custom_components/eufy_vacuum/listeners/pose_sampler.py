"""Run-active pose sampler (W5b) — records the per-tick pose time-series during an
EXTERNAL (app-started) run, for room auto-attribution.

This is the production version of the throwaway ``debug_log_live_room`` probe: at the
adapter's room_attribution cadence it captures the live room via the adapter's declared
``room_attribution.source`` (Eufy fork pose ``async_get_map_live_pose``, or a brand's native
current-room NAME entity) and buffers one ``{current_room, anchor, cleaning_area}`` sample per
tick into the external slot's ``pose_samples`` (via ``record_pose_sample``).

**Consumed by the W5c engine wiring** (``learning/room_attribution_engines.py``) — the
buffered ``pose_samples`` drive which rooms an external (app-started) run is recorded as
having cleaned (``external_ingest.build_pending_record``), the per-room durations written
to the learning record, and — via ``reconcile_dispatched_identity``'s "rescued" branch —
the room identity stamped on a DISPATCHED run's timings. A defect in this file affects all
of that, not an inert capture buffer.

Gating:
  - Active runs only — an EXTERNAL (app-started) run OR a DISPATCHED (``started``) run. External
    runs recover their unknown cleaned-room set (external_ingest.build_pending_record); dispatched
    runs feed the ATOMIC-finalize identity reconcile (external_ingest.reconcile_dispatched_identity;
    strict-order phase jobs ignore it). Idle / paused maps are skipped.
  - Attribution-capable vacuums only: the adapter's ``room_attribution.source`` selects HOW
    ``current_room`` is captured — ``live_pose`` (Eufy fork: a raster-lookup of the robot pixel
    in the decoded map, ``async_get_map_live_pose``) or ``native_current_room`` (Roborock: the
    brand publishes the live room directly as a NAME entity, ``entities.active_cleaning_target``,
    which the sampler slugifies + matches to a managed room id). A vacuum missing its source's
    signal is skipped (its ``current_room`` would be all-``None``). ``source`` defaults to
    ``live_pose`` when the block predates the key. Note this selects how the ROOM is read,
    not whether a pose is recorded: ``native_current_room`` also banks an ``anchor`` when the
    adapter declares ``map_state_source.live_pose``, since where the robot is and which room
    it is in are separate facts with separate best sources.
  - The sampling cadence ``interval_s`` comes from the adapter's ``room_attribution`` block —
    NEVER hardcoded here. It is the single source: the sampler ticks at it, and the engine
    converts ticks→seconds with it. The engine's ``dwell`` gate is measured in TICKS
    (``DWELL_MIN_TICKS``), so the DECISION is cadence-independent — a brand tunes the tick
    count to its own cadence, mirroring ``job_segmenter.tuning``.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INFJXSM4  `listeners/path_blockers.py#INFJXSM4`
#       A4-POSE-3 (closed RP-008): _is_parked has no working fallback on the native_current_room path — when
#              task_status is unreadable it returns 'not parked', the opposite of what its own
#   INYA5T84  `adapters/config_schema.py#INYA5T84`
#       A4-POSE-4 (closed RP-033): A zero or negative interval_s survives adapter registration (warn-only) and then
#              splits the sampler in two: register() drops it, _sample_vacuum_once does not


from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import partial

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..core.manager import EufyVacuumManager
from ..learning.room_attribution_engines import get_room_attribution_engine
from .. import pose_store


def _iso_now() -> str:
    """UTC ISO seconds — the same shape read_range compares lexicographically."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
from ..learning.utils import cleaning_area_to_m2, read_cleaning_area_m2
from ..rooms.utils import slugify_room_name

_LOGGER = logging.getLogger(__name__)

_POSE_SAMPLER_UNSUBS = "_pose_sampler_unsubs"
# Active-run statuses whose pose we buffer: EXTERNAL (recover the unknown cleaned-room set) and
# dispatched (``started`` — reconcile the atomic finalize's positional room identity against the
# native current_room). A strict-order dispatched job still buffers here but ignores it at
# finalize (it already captures per-phase timings).
_SAMPLED_STATUSES = ("external", "started")
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
    """Thin alias — the implementation moved to learning/utils.read_cleaning_area_m2
    when the stuck watch became a second consumer. Kept as a local name because this
    module calls it in several places and the indirection is free."""
    return read_cleaning_area_m2(hass, cfg)


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


async def _read_native_current_room_sample(
    hass, manager, vacuum_entity_id: str, cfg: dict, map_id_str: str
) -> dict:
    """``source: native_current_room`` — the brand publishes the live room as a NAME entity.

    TWO INDEPENDENT AXES, DELIBERATELY. ``current_room`` comes from the NAME entity and only
    from there: that path is recorder-verified on Ivy (it tracks the live room even on
    app-started runs) and a raster/pose lookup would be a worse answer to a question the
    brand already answers directly. ``anchor`` is a separate fact — WHERE, not WHICH — and
    is read from the pose when the adapter declares one.

    ``anchor`` used to be the literal ``None`` here, with the standing rationale that this
    source has "no pixel pose". True of the NAME entity; false of the brand. Roborock's
    position rides its parsed map, and once ``async_get_map_live_pose`` stopped being the
    Eufy fork reader (``live_pose.backend``) there was nothing left to be missing — the
    literal was the only thing keeping the pose ring anchor-less, which in turn is why a
    stall capture had no trail to draw. Absent a declared pose it stays None, and the
    engine's swept-area path attributes POSE-FREE as before.

    Always returns a sample — a momentarily unknown/unavailable entity is a genuine None
    current_room (transit / off-target), NOT a capture failure to skip. The parked signal is
    the MQTT task_status (``_is_parked`` with no pose flag), so a docked tick (Roborock reverts
    active_cleaning_target to the dock room, task_status → charging) is nulled to None — and
    nulls the anchor with it, so dock-sitting ticks never enter the ring as positions."""
    docked = _is_parked(hass, cfg, {})  # no pose flag — task_status is the parked signal
    room_id = None if docked else _resolve_managed_room_id(
        hass, manager, vacuum_entity_id, cfg, map_id_str
    )

    anchor = heading = None
    if not docked and isinstance(
        (cfg.get("map_state_source") or {}).get("live_pose"), dict
    ):
        try:
            pose = await manager.async_get_map_live_pose(vacuum_entity_id=vacuum_entity_id)
        except Exception:  # noqa: BLE001 - a pose miss must not cost the room sample
            _LOGGER.debug(
                "eufy_vacuum: pose read failed for %s; sampling room only",
                vacuum_entity_id, exc_info=True,
            )
            pose = {}
        if isinstance(pose, dict) and pose.get("present"):
            anchor = pose.get("robot_anchor")
            heading = pose.get("robot_heading")

    return {
        "current_room": room_id,
        "anchor": anchor,
        "cleaning_area": _read_cleaning_area(hass, cfg),
        "heading": heading,
    }


async def _sample_vacuum_once(hass, manager, vacuum_entity_id: str) -> int:
    """Sample one vacuum's active run(s) this tick; returns samples recorded.

    Skips non-attribution vacuums, vacuums missing their declared capture source's signal, maps
    with no active EXTERNAL or dispatched (``started``) run, and (live_pose only) ticks where the
    live pose isn't present. The capture path is chosen by the adapter's ``room_attribution.source``.
    Extracted so it's unit-testable."""
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
        if active.get("status") not in _SAMPLED_STATUSES:
            continue

        if source == "native_current_room":
            sample = await _read_native_current_room_sample(
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

        # 24-hour pose ring — a PARALLEL copy that outlives the job. The buffer
        # above is job-scoped: it lives until the next run on the same map
        # overwrites it, and it never reaches the finalized record, so the moment
        # a run ends its fine-grained history is gone. See pose_store's module
        # docstring for why 24 h and why chunked.
        #
        # Deliberately NOT gated on record_pose_sample's return: that guards the
        # live attribution buffer, and the ring wants the sample regardless of
        # whether a job slot accepted it.
        #
        # Offloaded because this coroutine runs on the event loop and direct file
        # I/O there trips HA's blocking-call detector — the same reason
        # battery/manager.py offloads its append. Failure here must never disturb
        # a run, so the store swallows its own I/O errors.
        try:
            hass.async_add_executor_job(
                partial(
                    pose_store.append_sample,
                    config_dir=hass.config.config_dir,
                    vacuum_entity_id=vacuum_entity_id,
                    sample={
                        "t": _iso_now(),
                        "map_id": map_id_str,
                        "current_room": sample["current_room"],
                        "anchor": sample["anchor"],
                        "cleaning_area": sample["cleaning_area"],
                        "heading": sample["heading"],
                    },
                )
            )
        except Exception:  # pragma: no cover - observability must not break a run
            _LOGGER.debug("pose ring: append could not be scheduled", exc_info=True)
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

    # RP-012/RF-31 (INNJ6SGC): per-vacuum cadence state (POSE-1) and in-flight guards
    # (POSE-2), persisting across ticks via this closure.
    _last_sample_ts: dict[str, float] = {}
    _in_flight: set[str] = set()

    async def _handle_pose_tick(_now) -> None:
        now_ts = hass.loop.time()
        for vacuum_entity_id in manager.get_known_vacuum_ids():
            # POSE-1: the shared ticker runs at min(intervals) across vacuums,
            # but each vacuum is sampled only at its OWN declared interval --
            # otherwise a slower vacuum's samples are valued at the ticker's
            # faster cadence by the engine's dwell=n*interval_s math,
            # over-weighting it (observed: a slower brand's samples counted
            # 2.5x against a faster one sharing the same ticker).
            own_interval = _room_attribution_interval_s(vacuum_entity_id)
            if own_interval is None:
                continue
            if now_ts - _last_sample_ts.get(vacuum_entity_id, 0.0) < own_interval:
                continue
            # POSE-2: skip this vacuum's tick if its previous sample is still
            # running (a slow live-pose await must not overlap with the next
            # tick for the SAME vacuum).
            if vacuum_entity_id in _in_flight:
                continue
            _in_flight.add(vacuum_entity_id)
            _last_sample_ts[vacuum_entity_id] = now_ts
            try:
                await _sample_vacuum_once(hass, manager, vacuum_entity_id)
            except Exception:
                # POSE-5: one vacuum's sampling failure must not stop the tick
                # from reaching the rest.
                _LOGGER.exception(
                    "eufy_vacuum: pose-sample tick failed for %s", vacuum_entity_id
                )
            finally:
                _in_flight.discard(vacuum_entity_id)

    unsub = async_track_time_interval(hass, _handle_pose_tick, timedelta(seconds=interval_s))
    domain_data[_POSE_SAMPLER_UNSUBS] = [unsub]
