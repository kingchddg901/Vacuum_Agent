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

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the tracker with the HA instance."""
        self.hass = hass
        self._confidence: dict[str, _RoomConfidenceState] = {}
        self._unsubs: dict[str, Callable[[], None]] = {}
        self._active_job: dict[str, dict[str, Any]] = {}
        self._sampling_paused: set[str] = set()
        # WHY: X and Y sensors each fire on the same movement event; tracking
        # the last recorded position deduplicates the resulting double-fire.
        self._last_recorded_pos: dict[str, tuple[float, float]] = {}
        # Last logged DOCKED position, for the dock-coordinate drift log (diagnostic).
        self._last_dock_pos: dict[str, tuple[float, float]] = {}
        # Serializes the dock-drift JSONL read-modify-write across executor threads —
        # appends rewrite the whole (rolled-off) file, so concurrent appends could
        # otherwise lose an update. Passive diagnostic; one lock is ample.
        self._dock_drift_lock = threading.Lock()

    DOCK_DRIFT_MAX_LINES = 5000

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
        """Initialise per-job confidence state for a new cleaning job.

        rooms is a {room_id: room_data} dict where room_data includes 'name' and
        'slug' — used to resolve the device's native current-room signal."""
        map_id_str = str(map_id)
        self._last_recorded_pos.pop(vacuum_entity_id, None)
        if vacuum_entity_id in self._confidence:
            self._confidence[vacuum_entity_id].reset_job()

        self._active_job[vacuum_entity_id] = {
            "map_id": map_id_str,
            "rooms": rooms,
        }

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
        self._active_job.pop(vacuum_entity_id, None)
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
        """Process a position state change event — a tick for confidence
        tracking (room detection reads the device's native current-room, not
        position) plus the passive dock-coordinate drift log."""
        pos = self._get_raw_position(vacuum_entity_id)
        if pos is None:
            return

        vx, vy = pos

        job = self._active_job.get(vacuum_entity_id)
        if job:
            # Skip during mid-job recharge (the robot is parked on the dock).
            if vacuum_entity_id not in self._sampling_paused:
                # Skip duplicate positions from the X and Y sensors firing
                # separately on the same movement event, so the confidence
                # movement count isn't double-advanced.
                last = self._last_recorded_pos.get(vacuum_entity_id)
                if last == (vx, vy):
                    return
                self._last_recorded_pos[vacuum_entity_id] = (vx, vy)
                self._update_confidence(vacuum_entity_id, vx, vy, job)
        else:
            # No active cleaning job. If the robot is parked on the dock, record
            # the reported position — the dock is fixed, so any change is pure
            # coordinate-frame drift. Diagnostic timeline only.
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
