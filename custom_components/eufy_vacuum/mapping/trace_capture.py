"""In-memory capture session manager for raw robot position traces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..timestamp_utils import utc_now, utc_now_iso
from .trace_store import TRACE_SCHEMA_VERSION, write_trace_run


def _make_run_id(map_id: str, room_id: str | None) -> str:
    """Return a stable, sortable run ID for a new capture session."""
    ts = utc_now().strftime("%Y%m%dT%H%M%SZ")
    room_part = str(room_id).strip() if room_id else "unassigned"
    safe_map = str(map_id).strip().replace(".", "_")
    safe_room = room_part.replace(".", "_").replace(" ", "_")
    return f"trace_{ts}_{safe_map}_{safe_room}"


def _vacuum_slug(vacuum_entity_id: str) -> str:
    if "." in vacuum_entity_id:
        return vacuum_entity_id.split(".", 1)[1].strip().lower()
    return str(vacuum_entity_id).strip().lower()


class TraceCapture:
    """Manages in-memory capture sessions for raw robot position traces.

    One instance lives per MappingManager. All active sessions are held in
    memory; persistence is delegated to trace_store on stop().
    """

    def __init__(self, base_mapping_dir: Path) -> None:
        """Initialise with the mapping root; vacuum slug subdirs and traces/ folders live under it."""
        self._base_dir = base_mapping_dir
        # Keyed by (vacuum_entity_id, map_id); values are mutable session dicts.
        self._sessions: dict[tuple[str, str], dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: str | None = None,
    ) -> dict[str, Any]:
        """Start a new capture session.

        If a session is already active for this (vacuum, map) pair it
        is discarded without writing — the caller is informed via
        previous_cancelled so no data is silently lost.

        Parameters
        ----------
        vacuum_entity_id: full HA entity id, e.g. "vacuum.alfred"
        map_id:           map identifier string
        room_id:          optional room association — may be None if
                          the room is unknown at capture time
        """
        key = (vacuum_entity_id, str(map_id))
        previous_cancelled = False
        previous_run_id: str | None = None

        if key in self._sessions:
            previous_run_id = self._sessions[key].get("run_id")
            previous_cancelled = True
            del self._sessions[key]

        run_id = _make_run_id(map_id, room_id)
        started_at = utc_now_iso()

        self._sessions[key] = {
            "run_id": run_id,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": str(room_id) if room_id is not None else None,
            "started_at": started_at,
            "samples": [],
        }

        return {
            "started": True,
            "run_id": run_id,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": str(room_id) if room_id is not None else None,
            "started_at": started_at,
            "previous_cancelled": previous_cancelled,
            "previous_run_id": previous_run_id,
        }

    def append_sample(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        x: float,
        y: float,
    ) -> bool:
        """Append one position sample to the active session.

        Silent no-op if no session is active for this (vacuum, map) pair.
        Returns True if appended, False if no active session.
        """
        # WHY: timestamp is recorded at call time — sensor event timestamps
        # are not reliably available in all call paths.
        key = (vacuum_entity_id, str(map_id))
        session = self._sessions.get(key)
        if session is None:
            return False

        session["samples"].append({
            "x": round(float(x), 4),
            "y": round(float(y), 4),
            "ts": utc_now_iso(),
        })
        return True

    def stop(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Stop the active session, finalise and persist the TraceRun.

        Returns a summary dict. Returns an error dict if no session
        is active — callers must check the 'stopped' key.
        """
        key = (vacuum_entity_id, str(map_id))
        session = self._sessions.pop(key, None)

        if session is None:
            return {
                "stopped": False,
                "reason": "no_active_session",
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
            }

        ended_at = utc_now_iso()
        samples = session.get("samples", [])

        run: dict[str, Any] = {
            "run_id": session["run_id"],
            "schema_version": TRACE_SCHEMA_VERSION,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": session.get("room_id"),
            "started_at": session["started_at"],
            "ended_at": ended_at,
            "sample_count": len(samples),
            "samples": samples,
        }

        slug = _vacuum_slug(vacuum_entity_id)
        path = write_trace_run(self._base_dir, slug, run)

        return {
            "stopped": True,
            "run_id": run["run_id"],
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": run["room_id"],
            "started_at": run["started_at"],
            "ended_at": ended_at,
            "sample_count": run["sample_count"],
            "path": str(path),
        }

    def cancel(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Discard the active session without writing anything.

        Returns a summary dict. Returns an error dict if no session
        was active — callers must check the 'cancelled' key.
        """
        key = (vacuum_entity_id, str(map_id))
        session = self._sessions.pop(key, None)

        if session is None:
            return {
                "cancelled": False,
                "reason": "no_active_session",
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
            }

        return {
            "cancelled": True,
            "run_id": session["run_id"],
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "discarded_samples": len(session.get("samples", [])),
        }

    def is_active(self, *, vacuum_entity_id: str, map_id: str) -> bool:
        """Return True if a session is currently active."""
        return (vacuum_entity_id, str(map_id)) in self._sessions

    def active_session_summary(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any] | None:
        """Return a lightweight summary of the active session, or None."""
        key = (vacuum_entity_id, str(map_id))
        session = self._sessions.get(key)
        if session is None:
            return None
        return {
            "run_id": session["run_id"],
            "room_id": session.get("room_id"),
            "started_at": session["started_at"],
            "sample_count": len(session.get("samples", [])),
        }
