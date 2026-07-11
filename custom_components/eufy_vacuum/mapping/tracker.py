"""Listens to raw position sensors, feeds boundary traces, and drives room confidence tracking."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..timestamp_utils import datetime_to_utc_iso, utc_now
from ..adapters.registry import get_adapter_config
from .room_bounds import BOUNDS_MARGIN, MULTI_ROOM_MIN_RUNS, RoomBoundsStore

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum robot movement (vacuum units) to count as a movement sample.
MOVEMENT_DELTA_THRESHOLD = 10.0

# Seconds the robot must stay in a room polygon before confidence builds.
TIME_THRESHOLD_SECONDS = 30.0

# Number of movement samples required for full confidence.
MOVEMENT_THRESHOLD_COUNT = 10

# Minimum confidence score to fire room_completed.
CONFIDENCE_THRESHOLD = 0.85


# How often to flush accumulated samples to disk (number of new samples).
# 25 unique positions post-dedup fix — equivalent protection to 50 pre-fix.
SAMPLES_FLUSH_INTERVAL = 25

# HA event names.
EVENT_ROOM_COMPLETED = "eufy_vacuum_room_completed"
EVENT_BOUNDARY_SAVED = "eufy_vacuum_boundary_saved"

# Current-room name sentinels that mean "no usable signal" (hold, never a room exit).
_BLANK_ROOM_SENTINELS = frozenset({"", "unknown", "unavailable", "none", "null"})
_ROOM_NAME_SEP = re.compile(r"[\s_-]+")


def _norm_room_name(value: Any) -> str:
    """Normalize a room name/slug for comparison (lowercase, collapse separators)."""
    return _ROOM_NAME_SEP.sub(" ", str(value or "").strip().lower()).strip()


# ---------------------------------------------------------------------------
# Per-vacuum tracker state
# ---------------------------------------------------------------------------

class _RoomConfidenceState:
    """Tracks confidence for one room during a cleaning job."""

    def __init__(self) -> None:
        self.current_room_id: str | None = None
        self.entered_at: datetime | None = None
        self.last_position: tuple[float, float] | None = None
        self.movement_count: int = 0
        self.time_in_room_seconds: float = 0.0
        self.confidence: float = 0.0
        self.fired_rooms: set[str] = set()  # room_ids fired this job

    def reset_room(self, room_id: str) -> None:
        """Switch to a new room and reset counters."""
        self.current_room_id = room_id
        self.entered_at = utc_now()
        self.last_position = None
        self.movement_count = 0
        self.time_in_room_seconds = 0.0
        self.confidence = 0.0

    def reset_job(self) -> None:
        """Reset all state for a new job."""
        self.current_room_id = None
        self.entered_at = None
        self.last_position = None
        self.movement_count = 0
        self.time_in_room_seconds = 0.0
        self.confidence = 0.0
        self.fired_rooms = set()

    def update(self, vx: float, vy: float) -> None:
        """Update tracking state with a new position sample."""
        now = utc_now()

        if self.entered_at is not None:
            self.time_in_room_seconds = (now - self.entered_at).total_seconds()

        if self.last_position is not None:
            dx = vx - self.last_position[0]
            dy = vy - self.last_position[1]
            delta = (dx * dx + dy * dy) ** 0.5
            if delta >= MOVEMENT_DELTA_THRESHOLD:
                self.movement_count += 1

        self.last_position = (vx, vy)

        time_factor = min(self.time_in_room_seconds / TIME_THRESHOLD_SECONDS, 1.0)
        move_factor = min(self.movement_count / MOVEMENT_THRESHOLD_COUNT, 1.0)
        self.confidence = round(time_factor * move_factor, 4)


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class MappingTracker:
    """Listens to _raw position sensors and drives room confidence tracking.

    One tracker instance is created per integration setup and manages all
    vacuums. Position listeners are registered per vacuum when tracking
    is enabled.
    """

    def __init__(self, hass: HomeAssistant, mapping_manager: RoomBoundsStore) -> None:
        """Initialize the tracker with the HA instance and a RoomBoundsStore reference."""
        self.hass = hass
        self._manager = mapping_manager
        self._confidence: dict[str, _RoomConfidenceState] = {}
        self._unsubs: dict[str, Callable[[], None]] = {}
        self._active_job: dict[str, dict[str, Any]] = {}
        self._job_samples: dict[str, list[tuple[float, float]]] = {}
        self._sampling_paused: set[str] = set()
        self._samples_since_flush: dict[str, int] = {}
        # WHY: X and Y sensors each fire on the same movement event; tracking
        # the last recorded position deduplicates the resulting double-fire.
        self._last_recorded_pos: dict[str, tuple[float, float]] = {}
        # Last logged DOCKED position, for the dock-coordinate drift log (diagnostic).
        self._last_dock_pos: dict[str, tuple[float, float]] = {}
        # Serializes the dock-drift JSONL read-modify-write across executor threads —
        # appends rewrite the whole (rolled-off) file, so concurrent appends could
        # otherwise lose an update. Passive diagnostic; one lock is ample.
        self._dock_drift_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Temp-file persistence helpers
    # ------------------------------------------------------------------

    def _samples_tmp_path(self, vacuum_entity_id: str) -> Path:
        """Return the path for the active-samples temp file for this vacuum."""
        slug = re.sub(r"[^a-z0-9_]", "_", vacuum_entity_id.lower())
        config_dir = self.hass.config.config_dir
        return (
            Path(config_dir)
            / "eufy_vacuum"
            / "mapping"
            / slug
            / "_samples_active.json"
        )

    def _flush_samples_to_disk(
        self,
        vacuum_entity_id: str,
        map_id: str,
        rooms: dict[str, Any],
        samples: list[tuple[float, float]],
    ) -> None:
        """Write accumulated job samples to a temp file for crash/restart recovery."""
        path = self._samples_tmp_path(vacuum_entity_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "map_id": map_id,
                "rooms": rooms,
                "samples": samples,
            }
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            _LOGGER.exception(  # pragma: no cover
                "MappingTracker: failed to flush samples to %s", path
            )

    def _load_samples_from_disk(
        self,
        vacuum_entity_id: str,
        map_id: str,
    ) -> list[tuple[float, float]] | None:
        """Return flushed samples from disk if they match the current map_id, else None."""
        path = self._samples_tmp_path(vacuum_entity_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if str(payload.get("map_id")) != str(map_id):
                _LOGGER.debug(
                    "MappingTracker: stale temp file for %s (map mismatch), ignoring",
                    vacuum_entity_id,
                )
                return None
            raw = payload.get("samples", [])
            return [(float(s[0]), float(s[1])) for s in raw if len(s) == 2]
        except Exception:
            _LOGGER.exception(  # pragma: no cover
                "MappingTracker: failed to load samples from %s", path
            )
            return None

    def _delete_samples_tmp_file(self, vacuum_entity_id: str) -> None:
        """Delete the temp samples file once a job ends cleanly."""
        path = self._samples_tmp_path(vacuum_entity_id)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            _LOGGER.debug(  # pragma: no cover
                "MappingTracker: could not delete temp file %s", path
            )

    RAW_SAMPLES_MAX_LINES = 1000
    DOCK_DRIFT_MAX_LINES = 5000

    def _raw_samples_path(self, vacuum_entity_id: str, room_id: str, room_slug: str | None = None) -> Path:
        """Return the canonical path for a room's JSONL archive.

        When room_slug is supplied the filename is raw_samples_room_{id}_{slug}.jsonl.
        Without a slug it falls back to raw_samples_room_{id}.jsonl (used as a
        write target only when the slug is genuinely unknown).
        Prefer _find_raw_samples_path for reads so existing named files are found.
        """
        vac_slug = re.sub(r"[^a-z0-9_]", "_", vacuum_entity_id.lower())
        name_part = f"_{room_slug}" if room_slug else ""
        return (
            Path(self.hass.config.config_dir)
            / "eufy_vacuum"
            / "mapping"
            / vac_slug
            / f"raw_samples_room_{room_id}{name_part}.jsonl"
        )

    def _find_raw_samples_path(self, vacuum_entity_id: str, room_id: str) -> Path | None:
        """Return the existing archive path for a room, regardless of slug suffix.

        Globs for raw_samples_room_{id}*.jsonl and returns the MOST-RECENTLY-WRITTEN
        match, or None if no archive exists yet. A room can briefly have both a
        no-slug file (written before its slug was known) and a slugged file; the live
        archive is the newer one, so picking by mtime returns it — alphabetical-first
        would return the stale no-slug file (".jsonl" sorts before "_slug.jsonl").
        """
        vac_slug = re.sub(r"[^a-z0-9_]", "_", vacuum_entity_id.lower())
        directory = (
            Path(self.hass.config.config_dir)
            / "eufy_vacuum"
            / "mapping"
            / vac_slug
        )

        def _mtime(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:  # vanished between glob and stat — treat as oldest
                return -1.0

        return max(directory.glob(f"raw_samples_room_{room_id}*.jsonl"),
                   key=_mtime, default=None)

    def _append_raw_samples(
        self,
        vacuum_entity_id: str,
        map_id: str,
        room_id: str,
        job_id: str,
        recorded_at: str,
        samples: list[tuple[float, float]],
        room_slug: str | None = None,
        room_name: str | None = None,
        dock_anchor_start: list[float] | None = None,
        dock_anchor_end: list[float] | None = None,
    ) -> None:
        """Append one job's raw samples as a JSONL line, rolling off entries beyond RAW_SAMPLES_MAX_LINES."""
        path = self._raw_samples_path(vacuum_entity_id, room_id, room_slug)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            record: dict = {
                "job_id":      job_id,
                "map_id":      str(map_id),
                "room_id":     str(room_id),
                "recorded_at": recorded_at,
                "samples":     samples,
            }
            if room_name:
                record["room_name"] = room_name
            # Per-session dock anchors for cross-session re-anchoring (Wave 1).
            # Omitted when unavailable so legacy/older lines stay schema-compatible.
            if dock_anchor_start is not None:
                record["dock_anchor_start"] = dock_anchor_start
            if dock_anchor_end is not None:
                record["dock_anchor_end"] = dock_anchor_end
            entry = json.dumps(record)
            existing: list[str] = []
            if path.exists():
                existing = path.read_text(encoding="utf-8").splitlines()
            else:
                # First write: prepend a self-describing metadata header line.
                header = json.dumps({
                    "_meta":       "eufy_vacuum raw samples archive",
                    "room_id":     str(room_id),
                    "room_name":   room_name or "",
                    "vacuum":      vacuum_entity_id,
                    "map_id":      str(map_id),
                    "description": (
                        "Per-job raw position samples used to derive and rebuild "
                        "room mapping bounds. Each subsequent line is one job entry."
                    ),
                })
                existing = [header]
            existing.append(entry)
            # WHY: keep the _meta header (index 0) and the baseline/first job
            # entry (index 1) pinned; rolling falloff starts from index 2.
            if existing and '"_meta"' in existing[0]:
                job_lines = existing[1:]
                if len(job_lines) > self.RAW_SAMPLES_MAX_LINES and len(job_lines) > 1:
                    baseline = job_lines[0]
                    recent   = job_lines[1:][-( self.RAW_SAMPLES_MAX_LINES - 1):]
                    job_lines = [baseline] + recent
                existing = [existing[0]] + job_lines
            elif len(existing) > self.RAW_SAMPLES_MAX_LINES:
                existing = existing[-self.RAW_SAMPLES_MAX_LINES:]
            tmp = path.with_suffix(".tmp")
            tmp.write_text("\n".join(existing) + "\n", encoding="utf-8")
            tmp.replace(path)
        except Exception:
            _LOGGER.exception(  # pragma: no cover
                "MappingTracker: failed to append raw samples for room %s (%s)",
                room_id, vacuum_entity_id,
            )

    # ------------------------------------------------------------------
    # Dock-coordinate drift log (diagnostic)
    # ------------------------------------------------------------------
    # The dock is a physically fixed point, so any change in the robot's REPORTED
    # position while docked is pure coordinate-frame drift (the device re-localizes
    # per session). We log each distinct docked reading to a per-vacuum JSONL so the
    # drift timeline can be inspected — when it drifts, by how much, on which axis.
    # Passive: append-only, never feeds bounds or cleaning.

    def _dock_drift_path(self, vacuum_entity_id: str) -> Path:
        """Return the dock-drift log path for this vacuum."""
        slug = re.sub(r"[^a-z0-9_]", "_", vacuum_entity_id.lower())
        return (
            Path(self.hass.config.config_dir)
            / "eufy_vacuum" / "mapping" / slug / "_dock_drift.jsonl"
        )

    def _maybe_log_dock_drift(self, vacuum_entity_id: str, vx: float, vy: float) -> None:
        """Log a docked-position reading when it changes (each change = a drift event)."""
        state = self.hass.states.get(vacuum_entity_id)
        s = str(state.state).strip().lower() if state else ""
        if s not in ("docked", "charging"):
            return
        last = self._last_dock_pos.get(vacuum_entity_id)
        if last == (vx, vy):
            return  # unchanged -> nothing drifted
        self._last_dock_pos[vacuum_entity_id] = (vx, vy)
        dx = round(vx - last[0], 4) if last is not None else None
        dy = round(vy - last[1], 4) if last is not None else None
        self.hass.async_add_executor_job(
            self._append_dock_drift,
            vacuum_entity_id, round(vx, 4), round(vy, 4), s, dx, dy,
        )

    def _append_dock_drift(
        self,
        vacuum_entity_id: str,
        vx: float,
        vy: float,
        state: str,
        dx: float | None,
        dy: float | None,
    ) -> None:
        """Append one dock-drift reading as a JSONL line, rolling off beyond DOCK_DRIFT_MAX_LINES."""
        path = self._dock_drift_path(vacuum_entity_id)
        with self._dock_drift_lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                record: dict = {
                    "ts": datetime_to_utc_iso(utc_now()),
                    "vx": vx,
                    "vy": vy,
                    "state": state,
                }
                if dx is not None:
                    record["dx"] = dx
                    record["dy"] = dy
                existing: list[str] = []
                if path.exists():
                    existing = path.read_text(encoding="utf-8").splitlines()
                else:
                    existing = [json.dumps({
                        "_meta": "eufy_vacuum dock-coordinate drift log",
                        "vacuum": vacuum_entity_id,
                        "description": (
                            "One line per distinct docked position. The dock is a fixed "
                            "point, so any change is coordinate-frame drift. dx/dy = delta "
                            "from the previous logged reading."
                        ),
                    })]
                existing.append(json.dumps(record))
                if existing and '"_meta"' in existing[0]:
                    body = existing[1:]
                    if len(body) > self.DOCK_DRIFT_MAX_LINES:
                        body = body[-self.DOCK_DRIFT_MAX_LINES:]
                    existing = [existing[0]] + body
                elif len(existing) > self.DOCK_DRIFT_MAX_LINES:
                    existing = existing[-self.DOCK_DRIFT_MAX_LINES:]
                tmp = path.with_suffix(".tmp")
                tmp.write_text("\n".join(existing) + "\n", encoding="utf-8")
                tmp.replace(path)
            except Exception:
                _LOGGER.exception(  # pragma: no cover
                    "MappingTracker: failed to append dock-drift for %s", vacuum_entity_id,
                )

    # ------------------------------------------------------------------
    # Listener registration
    # ------------------------------------------------------------------

    def register_vacuum(
        self,
        *,
        vacuum_entity_id: str,
        position_x_entity_id: str,
        position_y_entity_id: str,
    ) -> None:
        """Register position listeners for one vacuum.

        Called during integration setup for each vacuum that has
        robot_position entities available.
        """
        if vacuum_entity_id in self._unsubs:
            return  # already registered

        self._confidence[vacuum_entity_id] = _RoomConfidenceState()

        entities_to_watch = [position_x_entity_id, position_y_entity_id]

        @callback
        def _on_position_change(event) -> None:
            self._handle_position_update(vacuum_entity_id)

        unsub = async_track_state_change_event(
            self.hass,
            entities_to_watch,
            _on_position_change,
        )
        self._unsubs[vacuum_entity_id] = unsub
        _LOGGER.debug(
            "MappingTracker: registered position listeners for %s",
            vacuum_entity_id,
        )

    def unregister_vacuum(self, vacuum_entity_id: str) -> None:
        """Remove position listeners for one vacuum."""
        unsub = self._unsubs.pop(vacuum_entity_id, None)
        if unsub is not None:
            try:
                unsub()
            except Exception:
                pass
        self._confidence.pop(vacuum_entity_id, None)
        self._active_job.pop(vacuum_entity_id, None)
        self._job_samples.pop(vacuum_entity_id, None)
        self._samples_since_flush.pop(vacuum_entity_id, None)
        self._last_recorded_pos.pop(vacuum_entity_id, None)
        self._last_dock_pos.pop(vacuum_entity_id, None)
        self._sampling_paused.discard(vacuum_entity_id)

    def unregister_all(self) -> None:
        """Remove all position listeners — called on integration unload."""
        for vacuum_entity_id in list(self._unsubs):
            self.unregister_vacuum(vacuum_entity_id)

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def start_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        rooms: dict[str, Any],
    ) -> None:
        """Initialise per-job state and recover any samples flushed during a previous HA restart.

        rooms is a {room_id: room_data} dict where room_data includes 'name'
        and boundary info available from the mapping manager.
        """
        map_id_str = str(map_id)
        self._last_recorded_pos.pop(vacuum_entity_id, None)
        if vacuum_entity_id in self._confidence:
            self._confidence[vacuum_entity_id].reset_job()

        # WHY: delete the stale file regardless of whether recovery matched —
        # the new job will write its own file at SAMPLES_FLUSH_INTERVAL cadence.
        recovered = self._load_samples_from_disk(vacuum_entity_id, map_id_str)
        self._delete_samples_tmp_file(vacuum_entity_id)

        # Per-session dock anchor (Wave 1, capture-only): the device re-localizes
        # its coordinate origin every session, so absolute coords aren't comparable
        # across sessions. At a FRESH job start the robot is at the dock, so this
        # snapshot is the session's origin in vacuum space — later used to re-anchor
        # cross-session bounds. On a mid-job HA restart `recovered` is truthy and the
        # live position is mid-run (not the dock), so we leave it None and that run
        # is treated as un-anchored.
        dock_anchor_start: list[float] | None = None
        if not recovered:
            pos = self._get_raw_position(vacuum_entity_id)
            if pos is not None:
                dock_anchor_start = [round(pos[0], 4), round(pos[1], 4)]

        self._active_job[vacuum_entity_id] = {
            "map_id": map_id_str,
            "rooms": rooms,
            "dock_anchor_start": dock_anchor_start,
        }

        if recovered:
            self._job_samples[vacuum_entity_id] = recovered
            self._samples_since_flush[vacuum_entity_id] = 0
            _LOGGER.info(
                "MappingTracker: recovered %d samples from disk for %s map %s",
                len(recovered), vacuum_entity_id, map_id_str,
            )
        else:
            self._job_samples.pop(vacuum_entity_id, None)
            self._samples_since_flush[vacuum_entity_id] = 0

        _LOGGER.debug(
            "MappingTracker: job started for %s map %s (%d rooms)",
            vacuum_entity_id, map_id, len(rooms),
        )

    def pause_sampling(self, vacuum_entity_id: str) -> None:
        """Stop accumulating position samples (mid-job recharge started)."""
        self._sampling_paused.add(vacuum_entity_id)

    def resume_sampling(self, vacuum_entity_id: str) -> None:
        """Resume accumulating position samples (recharge ended)."""
        self._sampling_paused.discard(vacuum_entity_id)

    def end_job(self, *, vacuum_entity_id: str) -> None:
        """Notify tracker that a cleaning job has ended."""
        job = self._active_job.pop(vacuum_entity_id, None)
        samples = self._job_samples.pop(vacuum_entity_id, [])
        self._samples_since_flush.pop(vacuum_entity_id, None)

        # If in-memory samples are empty (e.g. after an HA restart mid-job),
        # fall back to whatever was last flushed to disk.
        if not samples and job:
            recovered = self._load_samples_from_disk(
                vacuum_entity_id, job["map_id"]
            )
            if recovered:
                samples = recovered
                _LOGGER.info(
                    "MappingTracker: end_job using %d recovered samples for %s",
                    len(samples), vacuum_entity_id,
                )

        if samples and job:
            map_id   = job["map_id"]
            rooms    = job.get("rooms", {})
            now_iso  = datetime_to_utc_iso(utc_now())
            job_id   = "job_" + now_iso[:16].replace(":", "-")

            # Per-session dock anchors (Wave 1, capture-only). start = the session
            # origin captured at job start; end = the re-dock position now (robot is
            # docked/charging at finalization). The start→end delta is a per-run
            # within-run-drift signal. Stored on the history entry + archive only;
            # no bounds math consumes them yet (that is Wave 2).
            dock_anchor_start = job.get("dock_anchor_start")
            _end_pos = self._get_raw_position(vacuum_entity_id)
            dock_anchor_end = (
                [round(_end_pos[0], 4), round(_end_pos[1], 4)]
                if _end_pos is not None else None
            )

            try:
                self._manager.update_room_bounds(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    samples=samples,
                    rooms=rooms,
                    dock_anchor_start=dock_anchor_start,
                    dock_anchor_end=dock_anchor_end,
                )
            except Exception:
                _LOGGER.exception(  # pragma: no cover
                    "MappingTracker: failed to update room bounds for %s",
                    vacuum_entity_id,
                )

            # Archive raw samples per room for historical rebuild.
            try:
                non_transition = [
                    rid for rid, rdata in rooms.items()
                    if not rdata.get("is_transition", False)
                ]
                if len(non_transition) == 1:
                    rid = str(non_transition[0])
                    rdata = rooms.get(rid, {})
                    self._append_raw_samples(
                        vacuum_entity_id, map_id,
                        room_id=rid,
                        room_slug=rdata.get("slug"),
                        room_name=rdata.get("name"),
                        job_id=job_id,
                        recorded_at=now_iso,
                        samples=samples,
                        dock_anchor_start=dock_anchor_start,
                        dock_anchor_end=dock_anchor_end,
                    )
                else:
                    # Multi-room job: attribute samples using the same bounding-box
                    # logic as manager.update_room_bounds, then archive per room.
                    map_data  = self._manager._load_map_data(vacuum_entity_id, map_id)
                    map_rooms = map_data.get("rooms", {})
                    attributed: dict[str, list] = {}
                    for vx, vy in samples:
                        for rid in non_transition:
                            bounds = map_rooms.get(str(rid), {}).get("bounds")
                            if bounds and self._manager._point_in_bounds(
                                vx, vy, bounds, BOUNDS_MARGIN
                            ):
                                attributed.setdefault(str(rid), []).append([vx, vy])
                                break
                    for rid, room_samples in attributed.items():
                        # WHY: skip archive for rooms below the minimum-run confidence
                        # gate — they acted as attribution traps, not real boundaries.
                        room_history = map_rooms.get(str(rid), {}).get("job_bounds_history", [])
                        active_runs  = sum(1 for e in room_history if not e.get("excluded", False))
                        if active_runs < MULTI_ROOM_MIN_RUNS:
                            _LOGGER.debug(
                                "MappingTracker: skipping archive for low-confidence room %s "
                                "(%d active runs, need %d) in multi-room job",
                                rid, active_runs, MULTI_ROOM_MIN_RUNS,
                            )
                            continue
                        rdata = rooms.get(rid, {})
                        self._append_raw_samples(
                            vacuum_entity_id, map_id,
                            room_id=rid,
                            room_slug=rdata.get("slug"),
                            room_name=rdata.get("name"),
                            job_id=job_id,
                            recorded_at=now_iso,
                            samples=room_samples,
                            dock_anchor_start=dock_anchor_start,
                            dock_anchor_end=dock_anchor_end,
                        )
            except Exception:
                _LOGGER.exception(  # pragma: no cover
                    "MappingTracker: failed to archive raw samples for %s",
                    vacuum_entity_id,
                )

        self._sampling_paused.discard(vacuum_entity_id)

        if vacuum_entity_id in self._confidence:
            self._confidence[vacuum_entity_id].reset_job()

    # ------------------------------------------------------------------
    # Position handling
    # ------------------------------------------------------------------

    def _get_raw_position(
        self,
        vacuum_entity_id: str,
    ) -> tuple[float, float] | None:
        """Return the current (vx, vy) from the robot_position_x/y sensor states, or None."""
        capabilities = self.hass.data.get("eufy_vacuum", {}).get("runtime")
        if capabilities is None:
            return None

        caps = {}
        try:
            caps = capabilities.get_vacuum_capabilities(
                vacuum_entity_id=vacuum_entity_id,
                refresh=False,
            )
        except Exception:
            return None

        x_entity = caps.get("entities", {}).get("robot_position_x")
        y_entity = caps.get("entities", {}).get("robot_position_y")

        if not x_entity or not y_entity:
            return None

        x_state = self.hass.states.get(x_entity)
        y_state = self.hass.states.get(y_entity)

        if x_state is None or y_state is None:
            return None

        try:
            vx = float(x_state.state)
            vy = float(y_state.state)
            return (vx, vy)
        except (ValueError, TypeError):
            return None

    @callback
    def _handle_position_update(self, vacuum_entity_id: str) -> None:
        """Process a position state change event."""
        pos = self._get_raw_position(vacuum_entity_id)
        if pos is None:
            return

        vx, vy = pos

        job = self._active_job.get(vacuum_entity_id)
        if job:
            # Skip accumulation during mid-job recharge — the dock position would
            # corrupt room bounds with hundreds of identical dock coordinates.
            if vacuum_entity_id not in self._sampling_paused:
                # Skip duplicate positions that arise from X and Y sensors
                # firing separately on the same movement event.
                last = self._last_recorded_pos.get(vacuum_entity_id)
                if last == (vx, vy):
                    return
                self._last_recorded_pos[vacuum_entity_id] = (vx, vy)

                samples = self._job_samples.setdefault(vacuum_entity_id, [])
                samples.append((vx, vy))

                # Periodic flush so an HA restart mid-job can recover samples.
                count = self._samples_since_flush.get(vacuum_entity_id, 0) + 1
                self._samples_since_flush[vacuum_entity_id] = count
                if count >= SAMPLES_FLUSH_INTERVAL:
                    self._samples_since_flush[vacuum_entity_id] = 0
                    # Snapshot samples before handing off — the list grows on
                    # the event loop while the executor write is in flight.
                    # async_add_executor_job already schedules the write and
                    # returns a Future; fire-and-forget (don't wrap it in
                    # async_create_task, which expects a coroutine, not a Future).
                    self.hass.async_add_executor_job(
                        self._flush_samples_to_disk,
                        vacuum_entity_id,
                        job["map_id"],
                        job.get("rooms", {}),
                        list(samples),
                    )

            # Run confidence tracking.
            self._update_confidence(vacuum_entity_id, vx, vy, job)
        else:
            # No active cleaning job. If the robot is parked on the dock, record the
            # reported position — the dock is fixed, so any change in it is pure
            # coordinate-frame drift. Diagnostic timeline only; never feeds bounds.
            self._maybe_log_dock_drift(vacuum_entity_id, vx, vy)

    def _read_active_cleaning_target(self, vacuum_entity_id: str) -> str | None:
        """Return the device's native current-room NAME (the adapter's
        active_cleaning_target entity state), or None when unavailable."""
        entities = (get_adapter_config(vacuum_entity_id) or {}).get("entities", {})
        entity_id = entities.get("active_cleaning_target")
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state is not None else None

    def _detect_current_room(
        self, vacuum_entity_id: str, rooms: dict[str, Any]
    ) -> str | None:
        """Resolve the device's native current-room signal to a (non-transition)
        room id in ``rooms``, or None when there is no usable signal this tick
        (blank / sentinel / a room not in this job). None means HOLD — never a
        room exit. Replaces the old learned-bounds position test; the room now
        comes straight from the device (the same signal the card's mascot dwell
        reads)."""
        norm = _norm_room_name(self._read_active_cleaning_target(vacuum_entity_id))
        if norm in _BLANK_ROOM_SENTINELS:
            return None
        for room_id, room_data in rooms.items():
            if room_data.get("is_transition", False):
                continue
            if (
                _norm_room_name(room_data.get("slug")) == norm
                or _norm_room_name(room_data.get("name")) == norm
            ):
                return room_id
        return None

    def _update_confidence(
        self,
        vacuum_entity_id: str,
        vx: float,
        vy: float,
        job: dict[str, Any],
    ) -> None:
        """Advance the room-confidence state machine and fire room_completed when threshold is met."""
        conf_state = self._confidence.get(vacuum_entity_id)
        if conf_state is None:
            return

        map_id = job["map_id"]
        rooms = job.get("rooms", {})

        # Which room the device says it is cleaning right now (its native
        # current-room signal), resolved to a job room. None = no usable signal
        # this tick (blank / sentinel / a room not in this job): HOLD the current
        # room rather than read a momentary blank as leaving it.
        current_room_id = self._detect_current_room(vacuum_entity_id, rooms)

        if current_room_id is None:
            if conf_state.current_room_id is not None:
                conf_state.update(vx, vy)   # keep accruing dwell for the held room
            return

        if current_room_id != conf_state.current_room_id:
            prev_room_id = conf_state.current_room_id

            if (
                prev_room_id is not None
                and conf_state.confidence >= CONFIDENCE_THRESHOLD
                and prev_room_id not in conf_state.fired_rooms
            ):
                # Fire room_completed for the room just left.
                self._fire_room_completed(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    room_id=prev_room_id,
                    room_data=rooms.get(prev_room_id, {}),
                    confidence=conf_state.confidence,
                    duration_seconds=conf_state.time_in_room_seconds,
                    entered_at=conf_state.entered_at,
                )
                conf_state.fired_rooms.add(prev_room_id)

            conf_state.reset_room(current_room_id)

        conf_state.update(vx, vy)

    def _fire_room_completed(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: str,
        room_data: dict[str, Any],
        confidence: float,
        duration_seconds: float,
        entered_at: datetime | None,
    ) -> None:
        """Publish the eufy_vacuum_room_completed event on the HA event bus."""
        room_name = str(room_data.get("name", room_id))
        entered_at_str = datetime_to_utc_iso(entered_at)

        event_data = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": str(room_id),
            "room_name": room_name,
            "confidence": confidence,
            "duration_seconds": round(duration_seconds, 1),
            "entered_at": entered_at_str,
        }

        # WHY: this event is informational only — room completion is driven by
        # timing/lifecycle in core. Spatial confidence is not yet reliable enough
        # to drive queue decisions.
        self.hass.bus.async_fire(EVENT_ROOM_COMPLETED, event_data)
        _LOGGER.info(
            "eufy_vacuum_room_completed: %s %s (confidence=%.2f, duration=%.0fs)",
            vacuum_entity_id, room_name, confidence, duration_seconds,
        )
