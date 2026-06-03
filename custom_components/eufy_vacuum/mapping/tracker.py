"""Listens to raw position sensors, feeds boundary traces, and drives room confidence tracking."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..timestamp_utils import datetime_to_utc_iso, utc_now
from .manager import BOUNDS_MARGIN, MULTI_ROOM_MIN_RUNS, MappingManager

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

    def __init__(self, hass: HomeAssistant, mapping_manager: MappingManager) -> None:
        """Initialize the tracker with the HA instance and a MappingManager reference."""
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
            _LOGGER.exception(
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
            _LOGGER.exception(
                "MappingTracker: failed to load samples from %s", path
            )
            return None

    def _delete_samples_tmp_file(self, vacuum_entity_id: str) -> None:
        """Delete the temp samples file once a job ends cleanly."""
        path = self._samples_tmp_path(vacuum_entity_id)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            _LOGGER.debug(
                "MappingTracker: could not delete temp file %s", path
            )

    RAW_SAMPLES_MAX_LINES = 1000

    def rebuild_room_bounds_from_archive(
        self,
        vacuum_entity_id: str,
        map_id: str,
        room_id: str,
    ) -> dict[str, Any]:
        """Replay archived raw samples to rebuild a room's bounds history.

        Reads the per-room JSONL archive, replays each non-excluded entry
        (oldest first) through the manager so job_bounds_history is
        reconstructed with original job_ids and recorded_at timestamps.
        Returns a summary of the rebuild.
        """
        path = self._find_raw_samples_path(vacuum_entity_id, str(room_id))
        if path is None:
            return {"success": False, "reason": "no_archive", "room_id": str(room_id)}

        try:
            lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        except Exception:
            _LOGGER.exception(
                "MappingTracker: failed to read archive for room %s (%s)",
                room_id, vacuum_entity_id,
            )
            return {"success": False, "reason": "read_error", "room_id": str(room_id)}

        archived_entries: list[dict] = []
        for line in lines:  # oldest first (append order)
            try:
                archived_entries.append(json.loads(line))
            except Exception:
                _LOGGER.exception(
                    "MappingTracker: failed to parse archive line for room %s (%s)",
                    room_id, vacuum_entity_id,
                )

        return self._manager.rebuild_room_bounds_from_archive(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            room_id=str(room_id),
            archived_entries=archived_entries,
        )

    def update_raw_samples_exclusion(
        self,
        vacuum_entity_id: str,
        room_id: str,
        job_id: str,
        excluded: bool,
    ) -> bool:
        """Set the excluded flag on the JSONL line matching job_id. Returns True if found."""
        if not job_id:
            return False
        path = self._find_raw_samples_path(vacuum_entity_id, str(room_id))
        if path is None:
            return False
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            updated = False
            result: list[str] = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("job_id") == job_id:
                        entry["excluded"] = excluded
                        line = json.dumps(entry)
                        updated = True
                except Exception:
                    pass
                result.append(line)
            if updated:
                tmp = path.with_suffix(".tmp")
                tmp.write_text("\n".join(result) + "\n", encoding="utf-8")
                tmp.replace(path)
            return updated
        except Exception:
            _LOGGER.exception(
                "MappingTracker: failed to update exclusion flag for job %s room %s (%s)",
                job_id, room_id, vacuum_entity_id,
            )
            return False

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

        Globs for raw_samples_room_{id}*.jsonl and returns the first match,
        or None if no archive exists yet.
        """
        vac_slug = re.sub(r"[^a-z0-9_]", "_", vacuum_entity_id.lower())
        directory = (
            Path(self.hass.config.config_dir)
            / "eufy_vacuum"
            / "mapping"
            / vac_slug
        )
        matches = sorted(directory.glob(f"raw_samples_room_{room_id}*.jsonl"))
        return matches[0] if matches else None

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
            _LOGGER.exception(
                "MappingTracker: failed to append raw samples for room %s (%s)",
                room_id, vacuum_entity_id,
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
        self._active_job[vacuum_entity_id] = {
            "map_id": map_id_str,
            "rooms": rooms,
        }
        self._last_recorded_pos.pop(vacuum_entity_id, None)
        if vacuum_entity_id in self._confidence:
            self._confidence[vacuum_entity_id].reset_job()

        # WHY: delete the stale file regardless of whether recovery matched —
        # the new job will write its own file at SAMPLES_FLUSH_INTERVAL cadence.
        recovered = self._load_samples_from_disk(vacuum_entity_id, map_id_str)
        self._delete_samples_tmp_file(vacuum_entity_id)
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

            try:
                self._manager.update_room_bounds(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    samples=samples,
                    rooms=rooms,
                )
            except Exception:
                _LOGGER.exception(
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
                        )
            except Exception:
                _LOGGER.exception(
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

        # Transition rooms are skipped — their presence is inferred subtractively
        # when no normal room boundary matches the current position.
        map_state = self._manager._load_map_data(vacuum_entity_id, map_id)
        map_rooms = map_state.get("rooms", {})
        current_room_id: str | None = None
        for room_id, room_data in rooms.items():
            if room_data.get("is_transition", False):
                continue
            bounds = map_rooms.get(str(room_id), {}).get("bounds")
            if bounds and self._manager._point_in_bounds(vx, vy, bounds, BOUNDS_MARGIN):
                current_room_id = room_id
                break

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

            if current_room_id is not None:
                conf_state.reset_room(current_room_id)
            else:
                conf_state.current_room_id = None

        # Update confidence for current room.
        if current_room_id is not None:
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
