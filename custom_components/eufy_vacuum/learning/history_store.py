"""Learning history storage for Vacuum Agent.

This module stores completed-job JSON records and provides a clean file-backed
history layer for the optional learning system.

Design goals:
- JSON files are the source of truth
- CSV is optional export, not primary storage
- everything is scoped per vacuum
- safe to use even when the learning system is optional

Important learning rule:
- all finalized jobs may be archived to history
- only eligible completed jobs are used for learning
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import contextlib
import csv
import json
import logging
import os
import tempfile
from typing import Any

_LOGGER = logging.getLogger(__name__)

from homeassistant.core import HomeAssistant
from ..timestamp_utils import parse_timestamp
from .utils import _iso_now, _safe_bool, _safe_float, _safe_int

DOMAIN = "eufy_vacuum"
LEARNING_ROOT = "eufy_vacuum/learning"


def _vacuum_slug(vacuum_entity_id: str) -> str:
    """Return vacuum slug from vacuum entity id."""
    if "." in vacuum_entity_id:
        return vacuum_entity_id.split(".", 1)[1].strip().lower()
    return str(vacuum_entity_id).strip().lower()


def _build_transit_blocks(
    *,
    counter_samples: list[dict[str, Any]],
    queue_room_ids: list[Any],
    slug_by_id: dict[int, str | None],
    vacuum_entity_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Segment the counter-sample stream and map per-room segments onto the
    dispatched queue → per-room timings (with area) + inter-room transit gaps.

    Frame-invariant: the job segmenter reads the cleaning_time / cleaning_area
    counters only — never geometry (raw coordinates drift across sessions).
    Segmentation routes through the adapter's pluggable job-segmenter engine
    (``vacuum_entity_id`` resolves it; absent/unknown → the Eufy counter engine,
    byte-identical to the legacy ``segment_counters``). Returns (room_timings,
    transitions, transit_capture_valid).

    Internal jobs map segment K → dispatched queue room K. transit_capture_valid
    is True only when the segment count equals the queued room count; a glitchy
    run (missed sample / extra split) yields valid=False so it never poisons the
    learned aggregate, while the partial timings are still emitted for audit. A
    single-room job → one segment, no transitions, valid=True.
    """
    queue_ids = [_safe_int(r, -1) for r in (queue_room_ids or []) if _safe_int(r, -1) > 0]

    from .job_segmenter_engines import get_job_segmenter_engine

    engine_name = None
    tuning = None
    if vacuum_entity_id:
        from .brand_facts import brand_facts_for

        engine_name, tuning = brand_facts_for(vacuum_entity_id).job_segmenter
    segs = get_job_segmenter_engine(engine_name).segment_legacy(
        counter_samples or [], expected_rooms=len(queue_ids) or None, tuning=tuning
    )
    valid = bool(segs) and len(segs) == len(queue_ids)

    room_timings: list[dict[str, Any]] = []
    for idx, s in enumerate(segs):
        room_id = queue_ids[idx] if idx < len(queue_ids) else _safe_int(s.get("room_id"), -1)
        room_timings.append(
            {
                "room_id": room_id,
                "slug": slug_by_id.get(room_id),
                "cleaning_start": s.get("t_start"),
                "cleaning_end": s.get("t_end"),
                "cleaning_seconds": _safe_int(s.get("time_active_s"), 0),
                "cleaning_wall_seconds": _safe_int(s.get("time_wall_s"), 0),
                "area_m2": _safe_float(s.get("area_delta_m2"), 0.0),
                "battery_delta": s.get("battery_delta"),
                "boundary": s.get("boundary"),
            }
        )

    transitions: list[dict[str, Any]] = []
    for prev, cur, seg in zip(room_timings, room_timings[1:], segs[1:]):
        transitions.append(
            {
                "from_room_id": prev.get("room_id"),
                "from_slug": prev.get("slug"),
                "to_room_id": cur.get("room_id"),
                "to_slug": cur.get("slug"),
                "transit_seconds": _safe_int(seg.get("gap_before_s"), 0),
            }
        )

    return room_timings, transitions, valid


@dataclass(slots=True)
class LearningPaths:
    """Resolved filesystem paths for one vacuum."""

    root: Path
    jobs_dir: Path
    learned_dir: Path
    exports_dir: Path
    live_dir: Path


class LearningHistoryStore:
    """File-backed history store for the optional learning system."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize history store."""
        self.hass = hass
        self._base_dir = Path(hass.config.config_dir) / LEARNING_ROOT

    def get_paths(self, *, vacuum_entity_id: str) -> LearningPaths:
        """Return all learning paths for one vacuum."""
        vacuum = _vacuum_slug(vacuum_entity_id)
        root = self._base_dir / vacuum
        return LearningPaths(
            root=root,
            jobs_dir=root / "jobs",
            learned_dir=root / "learned",
            exports_dir=root / "exports",
            live_dir=root / "live",
        )

    def ensure_dirs(self, *, vacuum_entity_id: str) -> LearningPaths:
        """Ensure per-vacuum learning directories exist."""
        paths = self.get_paths(vacuum_entity_id=vacuum_entity_id)
        paths.jobs_dir.mkdir(parents=True, exist_ok=True)
        paths.learned_dir.mkdir(parents=True, exist_ok=True)
        paths.exports_dir.mkdir(parents=True, exist_ok=True)
        paths.live_dir.mkdir(parents=True, exist_ok=True)
        return paths

    def read_json(self, path: Path) -> dict[str, Any] | list[Any] | None:
        """Read a JSON file safely."""
        try:
            if not path.exists() or not path.is_file():
                return None
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                return None
            parsed = json.loads(raw)
            if isinstance(parsed, (dict, list)):
                return parsed
            return None
        except json.JSONDecodeError as err:
            # Corrupt/partial file — recoverable: callers treat None as "no data"
            # and derived stats rebuild from the job history. Warn (not a full
            # traceback) so it's actionable without alarming, and self-heal on the
            # next atomic write_json.
            _LOGGER.warning("Ignoring malformed JSON in %s: %s", path, err)
            return None
        except Exception:
            _LOGGER.exception("Failed to read JSON from %s", path)
            return None

    def write_json(self, path: Path, payload: Any) -> None:
        """Write JSON payload to file atomically.

        Writes to a temp file in the same directory and ``os.replace``s it into
        place, so a reader (or a restart mid-write) never sees a half-written or
        doubly-written file — the failure mode that left ``Extra data`` trailing
        bytes on the SMB-mounted config share.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    def append_csv_row(self, path: Path, header: list[str], row: list[Any]) -> None:
        """Append a row to CSV, writing header if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0

        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            if write_header:
                writer.writerow(header)
            writer.writerow(row)

    def write_csv_rows(self, path: Path, header: list[str], rows: list[list[Any]]) -> None:
        """Rewrite an entire CSV file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    def list_job_files(self, *, vacuum_entity_id: str) -> list[Path]:
        """Return all completed-job JSON files for one vacuum."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        files: list[Path] = []

        for child in paths.jobs_dir.iterdir():
            if child.is_file() and child.suffix.lower() == ".json":
                files.append(child)

        return sorted(files, key=lambda p: p.name.lower())

    def get_live_snapshot_path(self, *, vacuum_entity_id: str) -> Path:
        """Return live job snapshot path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.live_dir / "last_job_snapshot.json"

    # ------------------------------------------------------------------
    # Incomplete run log
    # ------------------------------------------------------------------
    # Single-overwrite file written by _write_incomplete_run_log() when a
    # job ends without cleaning all queued rooms (cancelled / failed /
    # interrupted).  Only the most recent incomplete job is kept — the file
    # is replaced on every write and deleted when a job completes normally
    # or when retry_missed_rooms successfully dispatches a retry.
    # ------------------------------------------------------------------

    def get_incomplete_run_path(self, *, vacuum_entity_id: str) -> Path:
        """Return the incomplete run log path (single overwrite file)."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.live_dir / "incomplete_run.json"

    def save_incomplete_run(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any],
    ) -> Path:
        """Write the incomplete run log, replacing any previous entry."""
        path = self.get_incomplete_run_path(vacuum_entity_id=vacuum_entity_id)
        self.write_json(path, payload)
        return path

    def load_incomplete_run(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Return the incomplete run log dict, or None if none exists."""
        path = self.get_incomplete_run_path(vacuum_entity_id=vacuum_entity_id)
        payload = self.read_json(path)
        return payload if isinstance(payload, dict) else None

    def clear_incomplete_run(self, *, vacuum_entity_id: str) -> None:
        """Delete the incomplete run log file.

        Called in two places:
        - job_finalizer when a job completes without missed rooms (full clean)
        - retry_missed_rooms service after a retry job is successfully started

        Errors are logged as warnings rather than raised — a missing or
        unreadable file is not fatal.
        """
        path = self.get_incomplete_run_path(vacuum_entity_id=vacuum_entity_id)
        try:
            if path.exists():
                path.unlink()
        except Exception:  # pragma: no cover - best-effort file unlink
            _LOGGER.warning(
                "Failed to clear incomplete run log for %s", vacuum_entity_id
            )

    # ------------------------------------------------------------------
    # Trouble rooms log
    # ------------------------------------------------------------------
    # Single-overwrite file updated by _update_trouble_rooms_log() after
    # every job finalization.  Tracks per-room miss counts and run counts
    # across all runs so the card can flag chronically missed rooms.
    # A room is flagged is_trouble when miss_count >= 2 AND miss_rate >= 0.33.
    # ------------------------------------------------------------------

    def get_trouble_rooms_path(self, *, vacuum_entity_id: str) -> Path:
        """Return the chronic trouble rooms log path (single overwrite file)."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.live_dir / "trouble_rooms.json"

    def save_trouble_rooms(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any],
    ) -> Path:
        """Write the trouble rooms log, replacing any previous entry."""
        path = self.get_trouble_rooms_path(vacuum_entity_id=vacuum_entity_id)
        self.write_json(path, payload)
        return path

    def load_trouble_rooms(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Return the trouble rooms log dict, or None if none exists."""
        path = self.get_trouble_rooms_path(vacuum_entity_id=vacuum_entity_id)
        payload = self.read_json(path)
        return payload if isinstance(payload, dict) else None

    def save_live_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        snapshot: dict[str, Any],
    ) -> Path:
        """Save the current live job snapshot."""
        path = self.get_live_snapshot_path(vacuum_entity_id=vacuum_entity_id)
        self.write_json(path, snapshot)
        return path

    def load_live_snapshot(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Load the current live job snapshot."""
        path = self.get_live_snapshot_path(vacuum_entity_id=vacuum_entity_id)
        payload = self.read_json(path)
        return payload if isinstance(payload, dict) else None

    def save_access_graph_debug(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Write access graph debug file to learning/mapping/{vacuum}/{map_id}."""
        vacuum = _vacuum_slug(vacuum_entity_id)
        path = self._base_dir / "mapping" / vacuum / f"access_graph_{map_id}.json"
        self.write_json(path, payload)

    def get_completed_job_path(
        self,
        *,
        vacuum_entity_id: str,
        job_id: str,
    ) -> Path:
        """Return completed-job path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.jobs_dir / f"{job_id}.json"

    def save_completed_job(
        self,
        *,
        vacuum_entity_id: str,
        job_id: str,
        payload: dict[str, Any],
    ) -> Path:
        """Save completed job JSON."""
        path = self.get_completed_job_path(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
        )
        self.write_json(path, payload)
        return path

    def load_completed_job(
        self,
        *,
        vacuum_entity_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        """Load one completed job JSON."""
        path = self.get_completed_job_path(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
        )
        payload = self.read_json(path)
        return payload if isinstance(payload, dict) else None

    def load_all_completed_jobs(
        self,
        *,
        vacuum_entity_id: str,
    ) -> list[dict[str, Any]]:
        """Load all completed job JSON payloads."""
        jobs: list[dict[str, Any]] = []

        for path in self.list_job_files(vacuum_entity_id=vacuum_entity_id):
            payload = self.read_json(path)
            if isinstance(payload, dict):
                jobs.append(payload)

        return jobs

    def is_learning_job(self, job: dict[str, Any]) -> bool:
        """Return whether a completed job should be used for learning."""
        if not isinstance(job, dict):
            return False
        if job.get("record_type") != "completed_job":
            return False

        outcome = job.get("outcome")
        if not isinstance(outcome, dict):
            return False

        if str(outcome.get("status", "")).strip().lower() != "completed":
            return False

        return bool(outcome.get("used_for_learning"))

    def get_job_stats_path(self, *, vacuum_entity_id: str) -> Path:
        """Return learned job stats path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.learned_dir / "job_stats.json"

    def get_room_stats_path(self, *, vacuum_entity_id: str) -> Path:
        """Return learned room stats path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.learned_dir / "room_stats.json"

    def get_jobs_index_path(self, *, vacuum_entity_id: str) -> Path:
        """Return derived jobs index path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.learned_dir / "jobs_index.json"

    def save_job_stats(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any],
    ) -> Path:
        """Save learned job stats JSON (and refresh the shared read cache)."""
        path = self.get_job_stats_path(vacuum_entity_id=vacuum_entity_id)
        self.write_json(path, payload)
        self._job_stats_cache()[str(path)] = payload if isinstance(payload, dict) else None
        return path

    def save_room_stats(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any],
    ) -> Path:
        """Save learned room stats JSON (and refresh the shared read cache)."""
        path = self.get_room_stats_path(vacuum_entity_id=vacuum_entity_id)
        self.write_json(path, payload)
        self._room_stats_cache()[str(path)] = payload if isinstance(payload, dict) else None
        return path

    def save_jobs_index(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any],
    ) -> Path:
        """Save derived jobs index JSON."""
        path = self.get_jobs_index_path(vacuum_entity_id=vacuum_entity_id)
        self.write_json(path, payload)
        return path

    def load_job_stats(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Load learned job stats JSON (cached; see _job_stats_cache)."""
        path = self.get_job_stats_path(vacuum_entity_id=vacuum_entity_id)
        cache = self._job_stats_cache()
        key = str(path)
        if key in cache:
            return cache[key]
        payload = self.read_json(path)
        data = payload if isinstance(payload, dict) else None
        cache[key] = data
        return data

    def _room_stats_cache(self) -> dict[str, "dict[str, Any] | None"]:
        """The shared room_stats read cache. Scoped to ``hass.data`` so it is shared
        across the many LearningHistoryStore instances (estimator, rebuilder, …) yet
        fresh per hass (so tests don't bleed). The dashboard-snapshot estimate reads
        room_stats on the event loop frequently — caching keeps that off disk —
        and ``save_room_stats`` (the SOLE writer of the file) refreshes it, so reads
        never go stale."""
        return self.hass.data.setdefault("_eufy_vacuum_room_stats_cache", {})

    def _accuracy_stats_cache(self) -> dict[str, "dict[str, Any] | None"]:
        """The shared accuracy_stats read cache — mirrors :meth:`_room_stats_cache`
        (the dashboard-snapshot estimate also reads accuracy_stats on the loop)."""
        return self.hass.data.setdefault("_eufy_vacuum_accuracy_stats_cache", {})

    def _job_stats_cache(self) -> dict[str, "dict[str, Any] | None"]:
        """The shared job_stats read cache — mirrors :meth:`_room_stats_cache`
        (the dashboard-snapshot estimate also reads job_stats on the loop)."""
        return self.hass.data.setdefault("_eufy_vacuum_job_stats_cache", {})

    def warm_estimate_caches(self, *, vacuum_entity_id: str) -> None:
        """Populate the read caches the (loop-bound) dashboard-snapshot estimate
        touches — room_stats, accuracy_stats, job_stats — so the first estimate
        after a restart never blocks on a disk read. Call from an executor."""
        self.load_room_stats(vacuum_entity_id=vacuum_entity_id)
        self.load_accuracy_stats(vacuum_entity_id=vacuum_entity_id)
        self.load_job_stats(vacuum_entity_id=vacuum_entity_id)

    def load_room_stats(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Load learned room stats JSON (cached; see _room_stats_cache)."""
        path = self.get_room_stats_path(vacuum_entity_id=vacuum_entity_id)
        cache = self._room_stats_cache()
        key = str(path)
        if key in cache:
            return cache[key]
        payload = self.read_json(path)
        data = payload if isinstance(payload, dict) else None
        cache[key] = data
        return data

    def load_jobs_index(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Load derived jobs index JSON."""
        payload = self.read_json(self.get_jobs_index_path(vacuum_entity_id=vacuum_entity_id))
        return payload if isinstance(payload, dict) else None


    def _build_jobs_index_entry(
        self,
        *,
        completed_job: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return a compact per-job index entry for room-history rebuilds."""
        if not isinstance(completed_job, dict):
            return None
        if str(completed_job.get("record_type", "")).strip().lower() != "completed_job":
            return None

        outcome = completed_job.get("outcome", {})
        if not isinstance(outcome, dict):
            return None
        if str(outcome.get("status", "")).strip().lower() != "completed":
            return None

        job_info = completed_job.get("job", {})
        if not isinstance(job_info, dict):
            job_info = {}

        ended_at = str(job_info.get("ended_at") or completed_job.get("finalized_at") or "").strip()
        if not ended_at:
            return None

        map_id = str(
            completed_job.get("job_profile", {}).get("map_id")
            or completed_job.get("queue", {}).get("map_id")
            or "unknown"
        )

        resolved_rooms = completed_job.get("resolved_rooms", [])
        if not isinstance(resolved_rooms, list):
            resolved_rooms = []

        rooms: list[dict[str, Any]] = []
        for room in resolved_rooms:
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room.get("id")), -1)
            if room_id <= 0:
                continue
            clean_mode = str(room.get("clean_mode", "")).strip().lower() or None
            room_name = str(room.get("name", f"Room {room_id}")).strip() or f"Room {room_id}"
            rooms.append(
                {
                    "room_id": room_id,
                    "room_name": room_name,
                    "clean_mode": clean_mode,
                    "last_cleaned_at": ended_at,
                    "last_vacuumed_at": ended_at if clean_mode and ("vacuum" in clean_mode or clean_mode in {"vacuum", "vacuum_mop"}) else None,
                    "last_mopped_at": ended_at if clean_mode and ("mop" in clean_mode or clean_mode in {"mop", "vacuum_mop"}) else None,
                }
            )

        return {
            "job_id": str(completed_job.get("job_id", "")).strip(),
            "ended_at": ended_at,
            "map_id": map_id,
            "rooms": rooms,
        }

    def rebuild_jobs_index_from_completed_jobs(
        self,
        *,
        vacuum_entity_id: str,
        completed_jobs: list[dict[str, Any]] | None = None,
    ) -> Path:
        """Rebuild the compact jobs index from completed-job payloads."""
        jobs = completed_jobs
        if jobs is None:
            jobs = self.load_all_completed_jobs(vacuum_entity_id=vacuum_entity_id)

        entries: list[dict[str, Any]] = []
        for job in jobs:
            entry = self._build_jobs_index_entry(completed_job=job)
            if entry is not None:
                entries.append(entry)

        entries.sort(
            key=lambda item: (
                str(item.get("ended_at", "")),
                str(item.get("job_id", "")),
            )
        )
        payload = {
            "schema_version": 1,
            "record_type": "jobs_index",
            "vacuum_entity_id": vacuum_entity_id,
            "rebuilt_at": _iso_now(),
            "job_count": len(entries),
            "jobs": entries,
        }
        return self.save_jobs_index(
            vacuum_entity_id=vacuum_entity_id,
            payload=payload,
        )

    def update_jobs_index_with_completed_job(
        self,
        *,
        vacuum_entity_id: str,
        completed_job: dict[str, Any],
    ) -> Path | None:
        """Incrementally merge one completed job into the compact jobs index."""
        new_entry = self._build_jobs_index_entry(completed_job=completed_job)
        if new_entry is None:
            return None

        payload = self.load_jobs_index(vacuum_entity_id=vacuum_entity_id) or {
            "schema_version": 1,
            "record_type": "jobs_index",
            "vacuum_entity_id": vacuum_entity_id,
            "rebuilt_at": _iso_now(),
            "job_count": 0,
            "jobs": [],
        }
        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            jobs = []

        job_id = str(new_entry.get("job_id", "")).strip()
        replaced = False
        merged_jobs: list[dict[str, Any]] = []
        for entry in jobs:
            if not isinstance(entry, dict):
                continue
            if job_id and str(entry.get("job_id", "")).strip() == job_id:
                merged_jobs.append(new_entry)
                replaced = True
            else:
                merged_jobs.append(entry)

        if not replaced:
            merged_jobs.append(new_entry)

        merged_jobs.sort(
            key=lambda item: (
                str(item.get("ended_at", "")),
                str(item.get("job_id", "")),
            )
        )
        payload["schema_version"] = 1
        payload["record_type"] = "jobs_index"
        payload["vacuum_entity_id"] = vacuum_entity_id
        payload["rebuilt_at"] = _iso_now()
        payload["job_count"] = len(merged_jobs)
        payload["jobs"] = merged_jobs
        return self.save_jobs_index(
            vacuum_entity_id=vacuum_entity_id,
            payload=payload,
        )

    def get_accuracy_stats_path(self, *, vacuum_entity_id: str) -> Path:
        """Return per-room estimate accuracy stats path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.learned_dir / "accuracy_stats.json"

    def save_accuracy_stats(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any],
    ) -> Path:
        """Save per-room estimate accuracy stats JSON (and refresh the read cache)."""
        path = self.get_accuracy_stats_path(vacuum_entity_id=vacuum_entity_id)
        self.write_json(path, payload)
        self._accuracy_stats_cache()[str(path)] = payload if isinstance(payload, dict) else None
        return path

    def load_accuracy_stats(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Load per-room estimate accuracy stats JSON (cached; see _accuracy_stats_cache)."""
        path = self.get_accuracy_stats_path(vacuum_entity_id=vacuum_entity_id)
        cache = self._accuracy_stats_cache()
        key = str(path)
        if key in cache:
            return cache[key]
        payload = self.read_json(path)
        data = payload if isinstance(payload, dict) else None
        cache[key] = data
        return data

    def jobs_csv_path(self, *, vacuum_entity_id: str) -> Path:
        """Return jobs export CSV path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.exports_dir / "jobs_flat.csv"

    def rooms_csv_path(self, *, vacuum_entity_id: str) -> Path:
        """Return room export CSV path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.exports_dir / "rooms_flat.csv"

    def append_job_csv_row(
        self,
        *,
        vacuum_entity_id: str,
        row: list[Any],
    ) -> Path:
        """Append one jobs CSV row."""
        path = self.jobs_csv_path(vacuum_entity_id=vacuum_entity_id)
        header = [
            "job_id",
            "started_at",
            "ended_at",
            "map_id",
            "room_count",
            "duration_minutes",
            "battery_start",
            "battery_end",
            "battery_used",
            "status",
            "used_for_learning",
            "sanity_passed",
            "sanity_flags",
            "learning_blockers",
            "job_drift_minutes",
            "job_abs_drift_minutes",
            "water_estimated_ml",
            "water_end_station_pct",
            "water_actual_used_ml",
        ]
        self.append_csv_row(path, header, row)
        return path

    def append_room_csv_rows(
        self,
        *,
        vacuum_entity_id: str,
        rows: list[list[Any]],
    ) -> Path:
        """Append multiple room CSV rows."""
        path = self.rooms_csv_path(vacuum_entity_id=vacuum_entity_id)
        header = [
            "job_id",
            "started_at",
            "ended_at",
            "map_id",
            "room_slug",
            "room_id",
            "room_order",
            "requested_mode",
            "effective_mode",
            "clean_times",
            "fan_speed",
            "water_level",
            "clean_intensity",
            "edge_mopping",
            "is_carpet",
            "job_room_count",
            "job_duration_minutes",
            "job_battery_used",
            "status",
            "used_for_learning",
            "sanity_passed",
            "sanity_flags",
            "learning_blockers",
            "allocated_room_minutes",
            "allocated_room_battery_used",
            "allocated_room_drift_minutes",
            "allocated_room_abs_drift_minutes",
        ]
        for row in rows:
            self.append_csv_row(path, header, row)
        return path

    def rebuild_jobs_csv(
        self,
        *,
        vacuum_entity_id: str,
        rows: list[list[Any]],
    ) -> Path:
        """Rewrite jobs export CSV."""
        path = self.jobs_csv_path(vacuum_entity_id=vacuum_entity_id)
        header = [
            "job_id",
            "started_at",
            "ended_at",
            "map_id",
            "room_count",
            "duration_minutes",
            "battery_start",
            "battery_end",
            "battery_used",
            "status",
            "used_for_learning",
            "sanity_passed",
            "sanity_flags",
            "learning_blockers",
            "job_drift_minutes",
            "job_abs_drift_minutes",
            "water_estimated_ml",
            "water_end_station_pct",
            "water_actual_used_ml",
        ]
        self.write_csv_rows(path, header, rows)
        return path

    def rebuild_rooms_csv(
        self,
        *,
        vacuum_entity_id: str,
        rows: list[list[Any]],
    ) -> Path:
        """Rewrite rooms export CSV."""
        path = self.rooms_csv_path(vacuum_entity_id=vacuum_entity_id)
        header = [
            "job_id",
            "started_at",
            "ended_at",
            "map_id",
            "room_slug",
            "room_id",
            "room_order",
            "requested_mode",
            "effective_mode",
            "clean_times",
            "fan_speed",
            "water_level",
            "clean_intensity",
            "edge_mopping",
            "is_carpet",
            "job_room_count",
            "job_duration_minutes",
            "job_battery_used",
            "status",
            "used_for_learning",
            "sanity_passed",
            "sanity_flags",
            "learning_blockers",
            "allocated_room_minutes",
            "allocated_room_battery_used",
            "allocated_room_drift_minutes",
            "allocated_room_abs_drift_minutes",
        ]
        self.write_csv_rows(path, header, rows)
        return path

    def build_completed_job_payload(
        self,
        *,
        vacuum_entity_id: str,
        job_id: str,
        started_at: str,
        ended_at: str,
        battery_start: int,
        battery_end: int,
        queue_state: dict[str, Any],
        payload_state: dict[str, Any],
        active_job_state: dict[str, Any],
        used_for_learning: bool = True,
        outcome_status: str = "completed",
        was_cancelled: bool = False,
        was_failed: bool = False,
        was_interrupted: bool = False,
        is_test_job: bool = False,
        extra_outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the canonical completed-job payload."""
        # The record's room identity is the JOB's OWN — taken from the active_job snapshot (frozen
        # at launch), NEVER the live payload/queue. The composer re-hydrates the live payload when
        # rooms are re-queued, and that must not be able to rewrite a RUNNING job's record: observed
        # a Kitchen+Hallway+zone run recorded as Dining+Kitchen+Hallway (zone dropped) after rooms
        # were re-queued on top of it (job_2026-07-13T07-50-49). Precedence:
        #   1. active_job.resolved_rooms — the launch snapshot (atomic + interior-ending stepped);
        #   2. the union of ALL phases' rooms when (1) is empty — a stepped job that ended on a
        #      roomless phase (a trailing ZONE) has its top-level list zeroed by advance_active_job_
        #      phase, so the room phases' rooms only survive on the phase list;
        #   3. the LIVE payload only as a last resort (a job snapshot carrying nothing);
        #   4. the queue (below).
        # This also fixes the earlier symptom: without (2) a rooms->zone run read as zero rooms →
        # invalid_room_count → shown "Unknown" + dropped from learning even though its rooms cleaned.
        resolved_rooms: list = []
        if isinstance(active_job_state, dict):
            _aj_rooms = active_job_state.get("resolved_rooms")
            if isinstance(_aj_rooms, list):
                resolved_rooms = list(_aj_rooms)
            if not resolved_rooms:
                _phases = active_job_state.get("phases")
                if isinstance(_phases, list):
                    _seen_rids: set = set()
                    for _phase in _phases:
                        if not isinstance(_phase, dict):
                            continue
                        for _room in _phase.get("resolved_rooms") or []:
                            if not isinstance(_room, dict):
                                continue
                            _rid = _room.get("room_id")
                            if _rid is not None and _rid not in _seen_rids:
                                _seen_rids.add(_rid)
                                resolved_rooms.append(_room)
        if not resolved_rooms:
            _payload_rooms = (
                payload_state.get("resolved_rooms") if isinstance(payload_state, dict) else None
            )
            if isinstance(_payload_rooms, list):
                resolved_rooms = list(_payload_rooms)

        queue_rooms = queue_state.get("queue_rooms", []) if isinstance(queue_state, dict) else []
        if not isinstance(queue_rooms, list):
            queue_rooms = []

        if resolved_rooms:
            room_count = len(resolved_rooms)
            room_slugs = [
                str(room.get("slug", "")).strip().lower()
                for room in resolved_rooms
                if isinstance(room, dict) and str(room.get("slug", "")).strip()
            ]
        elif queue_rooms:
            room_count = len(queue_rooms)
            room_slugs = [
                str(room.get("slug", "")).strip().lower()
                for room in queue_rooms
                if isinstance(room, dict) and str(room.get("slug", "")).strip()
            ]
        else:
            room_count = _safe_int(active_job_state.get("room_count"), 0)
            room_slugs = [
                str(room.get("slug", "")).strip().lower()
                for room in active_job_state.get("queue_rooms", [])
                if isinstance(room, dict) and str(room.get("slug", "")).strip()
            ]

        started_dt = self._parse_timestamp(started_at)
        ended_dt = self._parse_timestamp(ended_at)
        if started_dt is not None and ended_dt is not None:
            wall_clock_duration_minutes = round(
                max((ended_dt - started_dt).total_seconds() / 60.0, 0.0),
                2,
            )
        else:
            wall_clock_duration_minutes = 0.0

        paused_duration_seconds = max(
            _safe_int(active_job_state.get("paused_duration_seconds"), 0),
            0,
        )
        paused_at = str(active_job_state.get("paused_at", "")).strip()
        paused_dt = self._parse_timestamp(paused_at)
        if paused_dt is not None and ended_dt is not None:
            paused_duration_seconds += max(int((ended_dt - paused_dt).total_seconds()), 0)

        recharge_seconds_accumulated = max(
            _safe_int(active_job_state.get("recharge_seconds_accumulated"), 0),
            0,
        )

        duration_minutes = round(
            max(
                wall_clock_duration_minutes
                - (paused_duration_seconds / 60.0)
                - (recharge_seconds_accumulated / 60.0),
                0.0,
            ),
            2,
        )

        # For single-room jobs derive actual cleaning time from the Returning
        # transition so the return trip doesn't inflate per-room stats.
        actual_cleaning_minutes: float | None = None
        if room_count == 1 and started_dt is not None:
            transitions = active_job_state.get("state_transitions", []) if isinstance(active_job_state, dict) else []
            returning_at_str: str | None = None
            for t in reversed(transitions if isinstance(transitions, list) else []):
                if not isinstance(t, dict):
                    continue
                if str(t.get("to_state", "")).strip().lower() == "returning":
                    returning_at_str = str(t.get("changed_at", "")).strip() or None
                    break
            if returning_at_str:
                returning_dt = self._parse_timestamp(returning_at_str)
                if returning_dt is not None and returning_dt > started_dt:
                    raw = (
                        (returning_dt - started_dt).total_seconds()
                        - paused_duration_seconds
                        - recharge_seconds_accumulated
                    )
                    actual_cleaning_minutes = round(max(raw / 60.0, 0.0), 2)

        battery_used = max(_safe_int(battery_start, 0) - _safe_int(battery_end, 0), 0)
        water_estimate = active_job_state.get("water_estimate", {}) if isinstance(active_job_state, dict) else {}
        mid_job_recharge_observed = _safe_bool(active_job_state.get("observed_mid_job_recharge"), False)
        mid_job_recharge_started_at = str(
            active_job_state.get("observed_mid_job_recharge_started_at", "") or ""
        ).strip() or None
        mid_job_recharge_count = max(
            _safe_int(active_job_state.get("observed_mid_job_recharge_count"), 0),
            0,
        )

        status = str(outcome_status or "completed").strip().lower() or "completed"
        learning_blockers: list[str] = []
        sanity_flags: list[str] = []

        if room_count <= 0:
            sanity_flags.append("invalid_room_count")
            learning_blockers.append("invalid_room_count")

        if duration_minutes <= 0:
            sanity_flags.append("invalid_duration")
            learning_blockers.append("invalid_duration")

        if not resolved_rooms:
            learning_blockers.append("missing_resolved_rooms")

        if was_cancelled or status == "cancelled":
            status = "cancelled"
            learning_blockers.append("job_cancelled")

        if was_failed or status == "failed":
            status = "failed"
            learning_blockers.append("job_failed")

        if was_interrupted or status == "interrupted":
            status = "interrupted"
            learning_blockers.append("job_interrupted")

        if is_test_job or status == "test":
            status = "test"
            learning_blockers.append("test_job")

        sanity_passed = len(sanity_flags) == 0
        if learning_blockers:
            used_for_learning = False

        outcome = {
            "status": status,
            "used_for_learning": used_for_learning,
            "sanity_passed": sanity_passed,
            "sanity_flags": sorted(set(sanity_flags)),
            "learning_blockers": sorted(set(learning_blockers)),
            "was_cancelled": bool(status == "cancelled"),
            "was_failed": bool(status == "failed"),
            "was_interrupted": bool(status == "interrupted"),
            "is_test_job": bool(status == "test"),
        }
        if isinstance(extra_outcome, dict):
            outcome.update(extra_outcome)
            cancel_detection = extra_outcome.get("cancel_detection")
            if isinstance(cancel_detection, dict) and cancel_detection.get("cancel_likely"):
                learning_blockers.append(str(cancel_detection.get("reason", "cancel_likely")))
                used_for_learning = False
                outcome["used_for_learning"] = False
                outcome["was_cancelled"] = True
                outcome["status"] = "cancelled"

        # --- Transit / travel-time capture (frame-invariant, time-based) ------
        # Map cleaning_time segments (captured during the run) onto the dispatched
        # queue order to derive per-room cleaning windows + inter-room transit
        # gaps. Absent for adapters without cleaning_time and for jobs that predate
        # capture -> empty blocks + transit_capture_valid=False (graceful).
        slug_by_id: dict[int, str | None] = {}
        for _src in (
            resolved_rooms,
            queue_rooms,
            active_job_state.get("queue_rooms", []) if isinstance(active_job_state, dict) else [],
        ):
            for _r in (_src or []):
                if not isinstance(_r, dict):
                    continue
                _rid = _safe_int(_r.get("room_id", _r.get("id")), -1)
                if _rid > 0 and _rid not in slug_by_id:
                    slug_by_id[_rid] = str(_r.get("slug") or "").strip().lower() or None
        if isinstance(queue_state, dict) and queue_state.get("queue_room_ids"):
            _queue_ids_for_transit = queue_state.get("queue_room_ids", [])
        elif isinstance(active_job_state, dict):
            _queue_ids_for_transit = active_job_state.get("queue_room_ids", [])
        else:
            _queue_ids_for_transit = []
        # Strict-order (sequenced) jobs: each phase captured its OWN room_timing from its own
        # counter slice at advance time (manager._capture_finishing_phase_timing) — the only
        # reliable per-room attribution, because the whole-run stream can't be segmented across
        # the per-room dock trips against the single last-phase queue. Concatenate in phase order
        # instead of running the whole stream through _build_transit_blocks (which would credit
        # the entire run to one room). Atomic jobs leave `phases` absent → the legacy path.
        _phases = active_job_state.get("phases") if isinstance(active_job_state, dict) else None
        _phase_room_timings: list[dict[str, Any]] = []
        _every_phase_captured = isinstance(_phases, list) and bool(_phases)
        if isinstance(_phases, list):
            for _p in _phases:
                _rt = _p.get("room_timing") if isinstance(_p, dict) else None
                if _rt:
                    _phase_room_timings.extend(_rt)
                else:
                    _every_phase_captured = False
        if _phase_room_timings:
            room_timings = _phase_room_timings
            transitions = []  # inter-phase gaps are dock overhead, not room-to-room transit
            transit_capture_valid = _every_phase_captured
        else:
            room_timings, transitions, transit_capture_valid = _build_transit_blocks(
                counter_samples=(
                    active_job_state.get("counter_samples", [])
                    if isinstance(active_job_state, dict)
                    else []
                ),
                queue_room_ids=_queue_ids_for_transit,
                slug_by_id=slug_by_id,
                vacuum_entity_id=vacuum_entity_id,
            )
            # ATOMIC dispatched runs only: the K->K positional mapping above is the weak spot
            # (out-of-order / skipped / mis-split). CONSERVATIVELY reconcile each segment's
            # identity against the native current_room the pose sampler buffered — counter keeps
            # time/area, pose owns which room: confirm on agreement, rescue when positional is
            # already unreliable, FLAG (never override) a confident disagreement. No pose /
            # anchor-only -> byte-identical to the positional path. Strict-order (phase) jobs
            # take the branch above and never reach here (already per-phase accurate).
            _pose_samples = (
                active_job_state.get("pose_samples") if isinstance(active_job_state, dict) else None
            )
            if _pose_samples:
                from .external_ingest import reconcile_dispatched_identity

                reconcile_dispatched_identity(
                    room_timings=room_timings,
                    pose_samples=_pose_samples,
                    vacuum_entity_id=vacuum_entity_id,
                    positional_valid=transit_capture_valid,
                    slug_by_id=slug_by_id,
                )

        return {
            "schema_version": 1,
            "record_type": "completed_job",
            "job_id": job_id,
            "vacuum": {
                "entity_id": vacuum_entity_id,
                "name": _vacuum_slug(vacuum_entity_id),
            },
            "job": {
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_minutes": duration_minutes,
                "wall_clock_duration_minutes": wall_clock_duration_minutes,
                "paused_duration_seconds": paused_duration_seconds,
                "room_count": room_count,
                "actual_cleaning_minutes": actual_cleaning_minutes,
                "return_to_dock_minutes": round(
                    max(wall_clock_duration_minutes - (actual_cleaning_minutes or duration_minutes), 0.0), 2
                ) if actual_cleaning_minutes is not None else None,
                "room_cleaning_minutes": round(
                    max(
                        actual_cleaning_minutes
                        - max(wall_clock_duration_minutes - actual_cleaning_minutes, 0.0),
                        0.0,
                    ),
                    2,
                ) if actual_cleaning_minutes is not None else None,
                "room_timings": room_timings,
                "transitions": transitions,
                "transit_capture_valid": transit_capture_valid,
                # Job-level rollup of the atomic-finalize reconcile: True when the pose named a
                # DIFFERENT room than the positional K->K assignment on a VALID run (kept, not
                # overridden — see reconcile_dispatched_identity). A queryable hook for a future
                # review surface / diagnostic; False for strict-order + no-pose + confirmed runs.
                "has_attribution_disagreement": any(
                    bool(rt.get("attribution_disagreement")) for rt in room_timings
                ),
            },
            "battery": {
                "start": _safe_int(battery_start, 0),
                "end": _safe_int(battery_end, 0),
                "used": battery_used,
                "mid_job_recharge_observed": mid_job_recharge_observed,
                "mid_job_recharge_started_at": mid_job_recharge_started_at,
                "mid_job_recharge_count": mid_job_recharge_count,
                "recharge_seconds_accumulated": recharge_seconds_accumulated,
            },
            "water": water_estimate if isinstance(water_estimate, dict) else {},
            "queue": (
                queue_state
                if isinstance(queue_state, dict) and queue_state.get("queue_room_ids")
                else {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(active_job_state.get("map_id", "")) if isinstance(active_job_state, dict) else "",
                    "room_count": _safe_int(active_job_state.get("room_count"), 0) if isinstance(active_job_state, dict) else 0,
                    "queue_room_ids": list(active_job_state.get("queue_room_ids", [])) if isinstance(active_job_state, dict) else [],
                    "queue_rooms": list(active_job_state.get("queue_rooms", [])) if isinstance(active_job_state, dict) else [],
                }
            ),
            "payload": (
                # Brand-agnostic "is this payload populated?" check — room_count
                # is set by every dispatch engine, vs. the old literal "rooms"
                # key which only existed for the Eufy payload shape.
                payload_state.get("payload", {})
                if isinstance(payload_state, dict) and payload_state.get("payload") and payload_state.get("room_count")
                else (active_job_state.get("payload", {}) if isinstance(active_job_state, dict) else {})
            ),
            "resolved_rooms": resolved_rooms,
            "job_profile": {
                "map_id": _safe_int(active_job_state.get("map_id", queue_state.get("map_id")), 0),
                "room_count": room_count,
                "room_slugs": room_slugs,
                "rooms": resolved_rooms,
            },
            "outcome": outcome,
            "finalized_at": _iso_now(),
        }

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        """Parse known timestamp formats."""
        return parse_timestamp(value)
