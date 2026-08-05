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
import re
import tempfile
import time
from typing import Any

# distinguishes "key not in cache" from "cached None" in the accuracy cache
_CACHE_MISS = object()

_LOGGER = logging.getLogger(__name__)

from homeassistant.core import HomeAssistant
from ..step_types import phase_capture_is_valid, is_dock_polled_phase_type
from ..timestamp_utils import parse_timestamp
from .utils import (
    _iso_now,
    _safe_bool,
    _safe_float,
    _safe_int,
    known_completed_room_ids,
)

DOMAIN = "eufy_vacuum"
LEARNING_ROOT = "eufy_vacuum/learning"


def _vacuum_slug(vacuum_entity_id: str) -> str:
    """Return vacuum slug from vacuum entity id."""
    if "." in vacuum_entity_id:
        return vacuum_entity_id.split(".", 1)[1].strip().lower()
    return str(vacuum_entity_id).strip().lower()


#: job_id round-trips through exclude_learning_job / restore_learning_job,
#: so on those service paths it is UNTRUSTED input -- get_completed_job_path
#: interpolates it directly into a filesystem path, and pathlib does not
#: normalise "..". job_finalizer.py generates ids shaped "job_<timestamp>",
#: but other producers (imports, tests, external tooling) use other shapes,
#: so this only excludes path separators and stays permissive otherwise --
#: mirrors external_run.py's _is_valid_pending_job_id: reject rather than
#: sanitise, since a malformed id can never be a real job's file.
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9._+-]+$")

#: Run outcomes that mean the LATER phases were torn down rather than simply never
#: reached. Both get `cancelled_upstream` at close; anything else gets `not_run`. The
#: distinction is user-facing: "you stopped it" reads differently from "it ended early".
_CANCEL_REASONS = frozenset({"cancelled", "interrupted", "stopped", "failed"})


def _is_valid_job_id(job_id: Any) -> bool:
    return bool(_JOB_ID_RE.fullmatch(str(job_id or "")))


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
        gap = _safe_int(seg.get("gap_before_s"), 0)
        idle = _idle_seconds(
            counter_samples, prev.get("cleaning_end"), cur.get("cleaning_start")
        )
        transitions.append(
            {
                "from_room_id": prev.get("room_id"),
                "from_slug": prev.get("slug"),
                "to_room_id": cur.get("room_id"),
                "to_slug": cur.get("slug"),
                # The robot was NOT CLEANING for this long. See _idle_seconds -
                # gap_before_s is the whole window and includes the cleaning that
                # happened inside it, which over-stated transit by 83% on the
                # 2026-08-05 measurements (66 s recorded, 36 s real).
                "transit_seconds": gap if idle is None else idle,
                # The raw window, kept alongside so the two are separable in a
                # record rather than one silently replacing the other.
                "gap_seconds": gap,
                # Which one the number came from, so a reader never has to guess
                # whether the counter was usable on this run.
                "transit_source": "gap_only" if idle is None else "counter_idle",
            }
        )

    return room_timings, transitions, valid


def _counter_at(counter_samples: Any, when_iso: Any) -> float | None:
    """``cleaning_time`` as of ``when_iso`` - the last sample at or before it."""
    if not when_iso:
        return None
    best: float | None = None
    for sample in counter_samples or []:
        if not isinstance(sample, dict):
            continue
        stamp = sample.get("t")
        value = sample.get("cleaning_time")
        if not stamp or value is None or str(stamp) > str(when_iso):
            continue
        try:
            best = float(value)
        except (TypeError, ValueError):
            continue
    return best


def _idle_seconds(counter_samples: Any, start_iso: Any, end_iso: Any) -> int | None:
    """Seconds in [start, end] during which the robot was NOT CLEANING.

    THE CORRECTION. ``transit_seconds`` was ``gap_before_s`` - the wall gap between
    one segment's last counter increment and the next segment's first. That window
    is not transit: the increment that OPENS the next segment carries cleaning that
    accrued inside the gap, so the gap contains real cleaning time and reports it
    as travel.

    Measured on two consecutive identical runs, 2026-08-05: Kitchen -> Entryway
    recorded transit_seconds 66 on both, while the counter advanced 30 s inside
    that window. Actual non-cleaning time: 36 s. An 83% over-count, feeding
    avg_ingress_transit_seconds on every multi-room run.

    ``cleaning_time`` only advances while the robot is cleaning - that is the
    device fact the whole measure rests on - so wall minus the counter's own
    progress IS the idle time, exactly, with no threshold and nothing to tune.

    Returns None when the counter cannot be read at both edges, so the caller can
    fall back to the raw gap rather than silently reporting a wrong zero.
    """
    if not start_iso or not end_iso:
        return None
    a = _counter_at(counter_samples, start_iso)
    b = _counter_at(counter_samples, end_iso)
    if a is None or b is None:
        return None
    try:
        wall = (
            datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))
            - datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        ).total_seconds()
    except (ValueError, TypeError):
        return None
    return int(max(0.0, wall - max(0.0, b - a)))


def clean_mode_of(rooms: Any) -> str | None:
    """The one mode a set of rooms shares, or "mixed". ONE derivation, two callers --
    the parent's PLANNED block (rooms from the plan) and its ACTUAL aggregate (rooms from
    the children). Two hand-rolled versions of this question is how vocabularies drift.

    Normalizes rather than trusts: room settings are stored as DISPLAY strings
    ("Vacuum and mop"), which is exactly what CLEAN_MODE_ALIASES exists for.

    "vacuum_mop" is a real single mode, not a mixture -- a run where every room mops while
    vacuuming is one thing the user chose. "mixed" means the rooms DISAGREED, the only
    case a single label cannot honestly describe.

    None when nothing is known. Absent is not "vacuum", and a review row that guesses is
    worse than one that says nothing.
    """
    modes: set[str] = set()
    for room in rooms if isinstance(rooms, list) else []:
        if not isinstance(room, dict):
            continue
        # A2: only a STRING is a mode. str() on a dict manufactures "{'a': 1}" and ships
        # it as a clean mode -- a value invented from malformed input, which is the same
        # class as int(3.7) becoming a real error code.
        value = room.get("clean_mode") or room.get("effective_clean_mode")
        raw = value.strip().lower() if isinstance(value, str) else ""
        if raw:
            modes.add(raw.replace(" and ", "_").replace(" ", "_"))
    modes.discard("")
    if not modes:
        return None
    return next(iter(modes)) if len(modes) == 1 else "mixed"


def _phased_clean_mode(children: list[dict[str, Any]]) -> str | None:
    """What a run ACTUALLY cleaned with, across its children.

    Prefers each child's ``battery_metrics.by_clean_mode`` -- already canonical -- and
    falls back to its per-room settings via ``clean_mode_of`` when a run was too short to
    compute shares.
    """
    modes: set[str] = set()
    for child in children:
        by_mode = ((child.get("job") or {}).get("battery_metrics") or {}).get("by_clean_mode")
        if isinstance(by_mode, dict) and by_mode:
            modes.update(str(k).strip().lower() for k in by_mode if str(k).strip())
            continue
        one = clean_mode_of(child.get("resolved_rooms"))
        if one:
            modes.add(one)
    modes.discard("")
    if not modes:
        return None
    return next(iter(modes)) if len(modes) == 1 else "mixed"


def phase_room_ids(phase: Any) -> list[int]:
    """Room ids a phase plans to clean.

    ``resolved_rooms`` is the authoritative per-phase source — it is what
    ``advance_active_job_phase`` derives the live queue from. ``queue_room_ids`` is only
    reliably present on the BREAK phases, which set it to ``[]`` defensively; reading it
    alone made the first live parent report ``room_count: 0`` and empty
    ``planned_room_ids`` on a run that cleaned three rooms. Both are read, resolved_rooms
    first, so neither shape is missed.
    """
    if not isinstance(phase, dict):
        return []
    out: list[int] = []
    for entry in phase.get("resolved_rooms") or []:
        if isinstance(entry, dict) and "room_id" in entry:
            rid = _safe_int(entry.get("room_id"), -1)
            if rid > 0 and rid not in out:
                out.append(rid)
    for raw in phase.get("queue_room_ids") or []:
        rid = _safe_int(raw, -1)
        if rid > 0 and rid not in out:
            out.append(rid)
    return out


def _planned_snapshot(
    estimate: dict[str, Any] | None,
    rooms: list[dict[str, Any]] | None,
    phases: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Scope the plan down to what a review row needs. Detail stays on the children."""
    est = estimate if isinstance(estimate, dict) else {}
    water = est.get("water_estimate") if isinstance(est.get("water_estimate"), dict) else {}
    room_ids: list[int] = []
    for ph in phases or []:
        for r in phase_room_ids(ph):
            if r not in room_ids:
                room_ids.append(r)
    def _num(value: Any) -> float | None:
        """A1: `x or None` turns a genuine 0 into "unknown". A zero-minute estimate is a
        real answer and must stay distinguishable from an absent one -- the same trap as
        an unreadable battery reporting 0 %."""
        return None if value is None else _safe_float(value, 0.0)

    return {
        "total_minutes": _num(est.get("total_minutes")),
        "eta_minutes": _num(est.get("job_eta_minutes")),
        "room_count": len(room_ids),
        "clean_mode": clean_mode_of(rooms),
        "water_ml": _num(water.get("estimated_total_dock_clean_water_used_ml")),
    }


@dataclass(slots=True)
class LearningPaths:
    """Resolved filesystem paths for one vacuum."""

    root: Path
    jobs_dir: Path
    learned_dir: Path
    exports_dir: Path
    live_dir: Path
    # Phased Jobs (synthesis/DESIGN-phased-jobs.md). `jobs_dir` keeps holding CHILDREN --
    # a child is a job in the full sense and every existing consumer of jobs/ keeps
    # working on it unchanged. These two are new record KINDS, not a new job kind.
    phases_dir: Path        # break records: a wait or charge is not a job
    phased_jobs_dir: Path   # parents: the run a user started


class LearningHistoryStore:
    """File-backed history store for the optional learning system."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize history store."""
        self.hass = hass
        self._base_dir = Path(hass.config.config_dir) / LEARNING_ROOT
        # RF-29: ensure_dirs is reached from 13 path-getter call sites in this file, one
        # per warm-path operation -- memoize per (process, vacuum slug) so only the FIRST
        # call for a given vacuum does the mkdir pass; every later call for that same
        # vacuum this process's lifetime is a no-op. Keyed on the slug (not the raw
        # vacuum_entity_id) so "vacuum.alfred" and any differently-cased caller collapse
        # onto the same entry -- get_paths already does the same normalization.
        self._ensured_vacuum_dirs: set[str] = set()

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
            phases_dir=root / "phases",
            phased_jobs_dir=root / "phased_jobs",
        )

    def ensure_dirs(self, *, vacuum_entity_id: str) -> LearningPaths:
        """Ensure per-vacuum learning directories exist.

        RF-29: memoized per (process, vacuum) -- see __init__. The mkdir pass runs once
        per vacuum per process; every repeat call just resolves the paths.
        """
        paths = self.get_paths(vacuum_entity_id=vacuum_entity_id)
        vacuum = _vacuum_slug(vacuum_entity_id)
        if vacuum in self._ensured_vacuum_dirs:
            return paths
        paths.jobs_dir.mkdir(parents=True, exist_ok=True)
        paths.learned_dir.mkdir(parents=True, exist_ok=True)
        paths.exports_dir.mkdir(parents=True, exist_ok=True)
        paths.live_dir.mkdir(parents=True, exist_ok=True)
        paths.phases_dir.mkdir(parents=True, exist_ok=True)
        paths.phased_jobs_dir.mkdir(parents=True, exist_ok=True)
        self._ensured_vacuum_dirs.add(vacuum)
        return paths

    # RP-006/RF-03 read tri-state. ABSENT and UNREADABLE are different facts:
    # absent means "no data has ever been written" (seeding {} is correct);
    # unreadable means "data exists but this read failed" (an RMW that proceeds
    # will REPLACE the store with only its own delta — the conflation that let a
    # corrupt 9-room trouble_rooms store be rewritten as a 1-room store).
    READ_OK = "ok"
    READ_ABSENT = "absent"
    READ_UNREADABLE = "unreadable"

    def read_json_outcome(
        self, path: Path
    ) -> tuple[str, dict[str, Any] | list[Any] | None]:
        """Read a JSON file, distinguishing ABSENT from UNREADABLE.

        Returns (READ_OK, payload) | (READ_ABSENT, None) | (READ_UNREADABLE, None).
        Destructive read-modify-write callers MUST refuse on UNREADABLE; read-only
        paths may keep treating both non-OK outcomes as "no data".
        """
        try:
            if not path.exists() or not path.is_file():
                return (self.READ_ABSENT, None)
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                # A zero-byte file is a torn write, not a store that never existed.
                _LOGGER.warning("Empty JSON file (torn write?) at %s", path)
                return (self.READ_UNREADABLE, None)
            parsed = json.loads(raw)
            if isinstance(parsed, (dict, list)):
                return (self.READ_OK, parsed)
            _LOGGER.warning("Non-container JSON in %s", path)
            return (self.READ_UNREADABLE, None)
        except json.JSONDecodeError as err:
            # Corrupt/partial file — recoverable for READERS (derived stats rebuild
            # from the job history), fatal for WRITERS (never rewrite over it).
            # Self-heals on the next atomic write_json.
            _LOGGER.warning("Ignoring malformed JSON in %s: %s", path, err)
            return (self.READ_UNREADABLE, None)
        except Exception:
            _LOGGER.exception("Failed to read JSON from %s", path)
            return (self.READ_UNREADABLE, None)

    def read_json(self, path: Path) -> dict[str, Any] | list[Any] | None:
        """Read a JSON file safely (None-tolerant compat wrapper over the
        tri-state — read paths keep their existing "no data" behaviour)."""
        return self.read_json_outcome(path)[1]

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
                # IO-7: os.replace is rename-atomic but not durable on its
                # own -- without this, a power loss between the write and
                # the OS lazily flushing dirty pages can leave a zero-length
                # file after the rename, which read_json_outcome then
                # reports as READ_UNREADABLE ("no data") rather than an error.
                handle.flush()
                os.fsync(handle.fileno())
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

    def load_trouble_rooms_outcome(
        self,
        *,
        vacuum_entity_id: str,
    ) -> tuple[str, dict[str, Any] | None]:
        """Tri-state read of the trouble rooms log — for the RMW writer (RP-006)."""
        path = self.get_trouble_rooms_path(vacuum_entity_id=vacuum_entity_id)
        outcome, payload = self.read_json_outcome(path)
        if outcome == self.READ_OK and not isinstance(payload, dict):
            return (self.READ_UNREADABLE, None)
        return (outcome, payload if isinstance(payload, dict) else None)

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

    def clear_live_snapshot(self, *, vacuum_entity_id: str) -> None:
        """Delete the live job snapshot file (RP-006 STATE-8: a consumed snapshot
        must not survive to describe the NEXT job — finalize clears it)."""
        path = self.get_live_snapshot_path(vacuum_entity_id=vacuum_entity_id)
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)

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
        """Return completed-job path.

        IO-5: job_id round-trips through exclude_learning_job /
        restore_learning_job as caller-supplied input and was interpolated
        here unvalidated -- pathlib does not normalise "..", so a crafted id
        gave those services an arbitrary *.json overwrite primitive. Raises
        on a shape that isn't job_finalizer's own "job_<timestamp>" id;
        load_completed_job (the only untrusted-input path) catches it.
        """
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        if not _is_valid_job_id(job_id):
            raise ValueError(f"invalid job_id: {job_id!r}")
        return paths.jobs_dir / f"{job_id}.json"

    # ------------------------------------------------------------------
    # Phased Jobs — the parent, and break records
    # See synthesis/DESIGN-phased-jobs.md. The governing principle: "we stop losing
    # good rooms because we stop treating each phase as a special thing." A CHILD is an
    # ordinary job in jobs/ and needs nothing here; only the two genuinely new record
    # kinds live below.
    # ------------------------------------------------------------------

    def phased_job_path(self, *, vacuum_entity_id: str, phased_job_id: str) -> Path:
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        if not _is_valid_job_id(phased_job_id):
            raise ValueError(f"invalid phased_job_id: {phased_job_id!r}")
        return paths.phased_jobs_dir / f"{phased_job_id}.json"

    def load_phased_job(
        self, *, vacuum_entity_id: str, phased_job_id: str
    ) -> dict[str, Any] | None:
        """Load one parent, or None when absent/unreadable."""
        try:
            path = self.phased_job_path(
                vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
            )
        except ValueError:
            return None
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a corrupt parent must not kill a run
            _LOGGER.warning("unreadable phased job %s for %s", phased_job_id, vacuum_entity_id)
            return None

    def open_phased_job(
        self,
        *,
        vacuum_entity_id: str,
        phased_job_id: str,
        map_id: str,
        started_at: str,
        battery_start: int | None,
        planned_phases: list[dict[str, Any]],
        learning_key: str | None = None,
        planned_estimate: dict[str, Any] | None = None,
        planned_rooms: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Write the parent at RUN START, status "running". Idempotent.

        WRITTEN AT START, NOT AT CLOSE (audit H2). Written at close, any abnormal end --
        HA restart, stranded job, power loss mid-phase -- leaves children carrying a
        phase_key that points at a parent which never existed. Written at start, an
        abnormal end leaves a parent stuck in "running", which the stranded-job reaper can
        find and close as interrupted. Orphans become impossible by construction.

        `planned_phases` records the SHAPE as planned, so a phase that never ran is still
        visible. Absence must never be how "did not happen" is expressed -- absence is
        indistinguishable from "was never planned", and that ambiguity is exactly what
        made a user's two-minute wait invisible.
        """
        existing = self.load_phased_job(
            vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
        )
        if existing is not None:
            # A7: the run's plan is fixed at start, so an existing parent WINS -- but a
            # differing plan means the run was re-planned or an id collided, and silently
            # discarding it hides both.
            was = [
                (str(p.get("type") or ""), list(p.get("planned_room_ids") or []))
                for p in (existing.get("phases") or [])
            ]
            now = [
                (str((ph or {}).get("phase_type") or "room_group"),
                 list((ph or {}).get("queue_room_ids") or []))
                for ph in (planned_phases or [])
            ]
            if was != now:
                _LOGGER.warning(
                    "phased job %s re-opened with a DIFFERENT plan (%d phases -> %d); "
                    "keeping the one recorded at run start",
                    phased_job_id, len(was), len(now),
                )
            return existing

        payload = {
            "schema_version": 1,
            "record_type": "phased_job",
            "phased_job_id": phased_job_id,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "learning_key": learning_key,
            "started_at": started_at,
            "ended_at": None,
            "status": "running",
            "battery": {"start": battery_start, "end": None, "used": None},
            # WHAT WAS INTENDED, snapshotted from the SAME source the card's estimate
            # panel renders (get_planned_job_estimate) -- not a second computation.
            # Deliberately scoped: the full water block and per-room detail live on the
            # children, and the parent restating them is the duplication we removed.
            #
            # Its whole value is the DELTA against `aggregate` at close. Chris: "if you
            # automate it and you come back -- I planned to do this, I did do this."
            # job_2026-08-02T11-15-51 estimated 3.61 min and ran 21, with nowhere to
            # record the miss, because the estimate was per-child and the run was merged.
            "planned": _planned_snapshot(planned_estimate, planned_rooms, planned_phases),
            # ONE array. An earlier draft carried planned_phases, outcome.phases,
            # children[], phase_records[] and phase_count -- five encodings of one
            # structure, four of which could disagree with the fifth. The parent's job is
            # to hold the STRUCTURE and point at records; the records hold everything
            # else. `record_id` is null until that phase finishes.
            "phases": [
                {
                    "index": i,
                    "type": str((ph or {}).get("phase_type") or "room_group"),
                    "planned_room_ids": phase_room_ids(ph),
                    "outcome": None,
                    "record_id": None,
                }
                for i, ph in enumerate(planned_phases or [])
            ],
        }
        self.write_json(
            self.phased_job_path(
                vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
            ),
            payload,
        )
        return payload

    def record_phase_outcome(
        self,
        *,
        vacuum_entity_id: str,
        phased_job_id: str,
        phase_index: int,
        phase_type: str,
        outcome: str,
        record_id: str | None,
    ) -> dict[str, Any] | None:
        """Attach one finished phase to its parent. Read-modify-write, idempotent per index.

        The parent is an AGGREGATE and its children are the SOURCE OF TRUTH (audit H4) --
        this appends an id and an outcome, never a recomputed number.
        """
        parent = self.load_phased_job(
            vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
        )
        if parent is None:
            _LOGGER.warning(
                "phase %s of %s finished with no parent record -- the parent should have "
                "been opened at run start", phase_index, phased_job_id,
            )
            return None

        slot = next(
            (p for p in (parent.get("phases") or [])
             if _safe_int(p.get("index"), -1) == int(phase_index)),
            None,
        )
        if slot is None:
            # A phase the plan never declared -- record it rather than drop it, and say so.
            _LOGGER.warning(
                "phase %s of %s was not in the planned structure", phase_index, phased_job_id
            )
            slot = {"index": int(phase_index), "type": str(phase_type),
                    "planned_room_ids": [], "outcome": None, "record_id": None}
            parent.setdefault("phases", []).append(slot)
            parent["phases"].sort(key=lambda p: _safe_int(p.get("index"), 0))
        # A3: the PLAN owns the type. Overwriting it let a caller's wrong argument rewrite
        # `wait` into `room_group`, and the type decides whether a phase counts toward
        # `completed` and whether its gap is a hold or transit -- so a typo silently
        # changed the run's meaning. Report the disagreement; never absorb it.
        planned_type = str(slot.get("type") or "")
        if planned_type and planned_type != str(phase_type):
            _LOGGER.warning(
                "phase %s of %s was planned as %s but reported as %s -- keeping the "
                "planned type", phase_index, phased_job_id, planned_type, phase_type,
            )
        elif not planned_type:
            slot["type"] = str(phase_type)
        slot["outcome"] = str(outcome)
        slot["record_id"] = record_id

        # A6: a phase reported AFTER close left `status` stale while the phase itself read
        # "completed" -- a record contradicting itself. A late report is legitimate (a
        # re-armed poller finishing after the reaper closed the run), so RE-OPEN rather
        # than reject; the caller closes again and the status recomputes from the phases.
        if str(parent.get("status") or "") not in ("running", ""):
            _LOGGER.warning(
                "phased job %s was closed as %s and phase %s reported afterwards -- "
                "re-opening; close again to recompute",
                phased_job_id, parent.get("status"), phase_index,
            )
            parent["status"] = "running"
            parent["ended_at"] = None

        self.write_json(
            self.phased_job_path(
                vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
            ),
            parent,
        )
        return parent

    def close_phased_job(
        self,
        *,
        vacuum_entity_id: str,
        phased_job_id: str,
        ended_at: str,
        battery_end: int | None,
        ended_reason: str | None = None,
        active_phase_index: int | None = None,
    ) -> dict[str, Any] | None:
        """Close the parent: final status, aggregate, boundaries.

        THE AGGREGATE IS A CACHE. Children are the source of truth (audit H4); this sums
        them for cheap reads and rebuild_learning_stats recomputes it, so excluding a
        child cannot leave a stale stored number.

        STATUS IS NEVER COLLAPSED. The label is a summary and the per-phase list beside
        it is the truth -- a run where the kitchen finished and the rest was cancelled
        must stay legible as exactly that.
        """
        parent = self.load_phased_job(
            vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
        )
        if parent is None:
            return None

        phases = parent.get("phases") or []
        # SEAL THE UNREPORTED PHASES FIRST. A phase that never reported carries
        # outcome None -- the SAME value it carries while in flight. On a closed parent
        # that is unreadable: nothing distinguishes "this phase never ran" from "this
        # phase is still going", on a run that is over.
        #
        # Chris's directive 1 (a cancel on any phase propagates to the later phases)
        # lands here rather than in the cancel path: the cancel path returns early by
        # design (it owns finalization and must not advance), so it never visits the
        # phases it cancelled. Close is the one place that sees them all.
        _cancelled = str(ended_reason or "").strip().lower() in _CANCEL_REASONS
        _active = _safe_int(active_phase_index, -1)
        for _ph in phases:
            if _ph.get("outcome") not in (None, ""):
                continue
            if not _cancelled:
                _ph["outcome"] = "not_run"
            elif _active >= 0 and _safe_int(_ph.get("index"), -1) == _active:
                # The phase that was IN FLIGHT when the cancel landed. It is NOT
                # "cancelled_upstream" — nothing upstream cancelled it, the user did, and
                # it may have cleaned for minutes before it stopped. Labelling it the same
                # as a phase that never started loses the only thing a reader wants from a
                # cancelled run: how far it got. Observed on hardware
                # (pj_2026-08-02T17-38-07): a kitchen that ran 92 s read identically to a
                # phase that never dispatched.
                _ph["outcome"] = "cancelled"
            else:
                _ph["outcome"] = "cancelled_upstream"

        clean = [p for p in phases
                 if str(p.get("type")) not in ("charge_wait", "wait")]
        done = [p for p in clean if p.get("outcome") == "completed"]
        if clean and len(done) == len(clean):
            status = "completed"
        elif any(p.get("outcome") == "failed" for p in clean):
            status = "failed"
        elif done:
            status = "partial"
        elif str(ended_reason or "").strip().lower() == "interrupted":
            # NOT "cancelled". A run killed by a restart or a power loss telling the user
            # they cancelled it is a false statement about who did what -- and the two
            # have different repair paths (resume vs re-plan).
            status = "interrupted"
        else:
            status = "cancelled"

        # DERIVED, not stored -- a child list beside the phase list is a second source
        # of truth for the same fact.
        children, missing, unsplit = [], [], []
        for ph in clean:
            rid = ph.get("record_id")
            if not rid:
                # A clean phase that finished but produced NO record of its own. Distinct
                # from `missing` (a record that was promised and will not load): here none
                # was ever promised. Until wave 2 splits the children this is every clean
                # phase, so it must be NAMED -- skipped silently, the parent below closes
                # "completed" with 0 seconds and an empty missing list, which is the same
                # lie A4 removed, entering through a different door.
                unsplit.append(_safe_int(ph.get("index"), -1))
                continue
            loaded = self.load_completed_job(vacuum_entity_id=vacuum_entity_id, job_id=rid)
            (children if isinstance(loaded, dict) else missing).append(loaded or rid)
        rooms: list[int] = []
        for c in children:
            for rid in known_completed_room_ids(
                (c.get("queue") or {}), (c.get("job") or {}).get("room_timings")
            ):
                if rid not in rooms:
                    rooms.append(rid)

        parent["ended_at"] = ended_at
        parent["battery"]["end"] = battery_end
        start = parent["battery"].get("start")
        parent["battery"]["used"] = (
            _safe_int(start, 0) - _safe_int(battery_end, 0)
            if start is not None and battery_end is not None else None
        )
        # An explicit PRESENTATION CACHE (audit H4): the children are authoritative and
        # rebuild_learning_stats recomputes this. It exists so a card can show a run
        # without loading every child, not as a second record of the same numbers.
        parent["aggregate"] = {
            "cleaning_time_seconds": sum(
                _safe_int((c.get("job") or {}).get("cleaning_time_seconds"), 0)
                for c in children
            ),
            "cleaning_area_m2": round(sum(
                _safe_float((c.get("job") or {}).get("cleaning_area_m2"), 0.0)
                for c in children
            ), 3),
            "rooms_cleaned": rooms,
            "clean_mode": _phased_clean_mode(children),
            # A4: a phase that reported an outcome but whose record will not load. Without
            # this a parent read "completed" with 0 seconds and no rooms -- a record that
            # LIES, the exact class this design exists to remove. Empty is the normal case.
            "missing_children": missing,
            # Phase indices that finished with no child record of their own. While this is
            # non-empty the numbers above are NOT the run's totals, and a reader (card,
            # rebuild, review row) must treat them as partial rather than as zero.
            "unsplit_phases": unsplit,
        }
        if unsplit:
            _LOGGER.debug(
                "phased job %s: %d clean phase(s) have no child record yet (%s) -- "
                "its aggregate covers only the split phases",
                phased_job_id, len(unsplit), unsplit,
            )
        if missing:
            _LOGGER.warning(
                "phased job %s: %d recorded child record(s) could not be loaded (%s) -- "
                "its aggregate is INCOMPLETE",
                phased_job_id, len(missing), ", ".join(missing),
            )
        parent["boundaries"] = self._phased_boundaries(
            vacuum_entity_id=vacuum_entity_id, parent=parent, children=children
        )
        parent["status"] = status
        self.write_json(
            self.phased_job_path(
                vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
            ),
            parent,
        )
        return parent

    def _phased_boundaries(
        self,
        *,
        vacuum_entity_id: str,
        parent: dict[str, Any],
        children: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Split each gap between children into PLANNED HOLD and TRANSIT.

        Only transit is learnable. A planned hold is a constant the user chose -- folding
        it into overhead is how a two-minute pause taught a FLAT three-room run that it
        takes two minutes longer. Entry and return stay with the children, where they
        already are.

            boundary = child[n].ended_at -> child[n+1].started_at
            hold     = the break record's actual seconds (0 when there was no break)
            transit  = boundary - hold
        """
        holds: dict[int, int] = {}
        break_ids = [p["record_id"] for p in (parent.get("phases") or [])
                     if p.get("record_id") and str(p.get("type")) in ("charge_wait", "wait")]
        for rid in break_ids:
            rec = None
            try:
                path = self.get_paths(vacuum_entity_id=vacuum_entity_id).phases_dir / f"{rid}.json"
                if path.exists():
                    rec = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                rec = None
            if isinstance(rec, dict):
                holds[_safe_int(rec.get("phase_index"), -1)] = _safe_int(
                    (rec.get("actual") or {}).get("seconds"), 0
                )

        # Each boundary is between two ADJACENT CLEAN phases; it absorbs the holds whose
        # phase index falls strictly between them. Derived from the parent's own phase
        # list rather than assuming one hold per boundary -- two consecutive breaks
        # (a charge then a wait) share a single boundary.
        by_index = {
            _safe_int(p.get("index"), -1): p for p in (parent.get("phases") or [])
        }
        child_by_record = {
            str((c.get("job_id") or "")): c for c in children
        }
        clean_indices = sorted(
            i for i, p in by_index.items()
            if i >= 0 and str(p.get("type")) not in ("charge_wait", "wait")
        )

        out: list[dict[str, Any]] = []
        for a, b in zip(clean_indices, clean_indices[1:]):
            prev = child_by_record.get(str(by_index[a].get("record_id") or ""))
            nxt = child_by_record.get(str(by_index[b].get("record_id") or ""))
            if not prev or not nxt:
                continue
            end_ts = parse_timestamp(str((prev.get("job") or {}).get("ended_at") or ""))
            start_ts = parse_timestamp(str((nxt.get("job") or {}).get("started_at") or ""))
            if end_ts is None or start_ts is None:
                continue
            boundary = int(max(0.0, (start_ts - end_ts).total_seconds()))
            hold = sum(v for k, v in holds.items() if a < k < b)
            hold = min(hold, boundary)
            out.append({
                "after_phase": a,
                "seconds": boundary,
                "planned_hold_seconds": hold,
                # Clamped: clock skew, or a hold that outran its own boundary, must never
                # teach a NEGATIVE travel time.
                "transit_seconds": max(0, boundary - hold),
            })
        return out

    def save_phase_record(
        self, *, vacuum_entity_id: str, record_id: str, payload: dict[str, Any]
    ) -> Path:
        """Save one BREAK record. A wait or charge is not a job and must not wear the
        completed_job schema -- it contributes to the parent's wall-clock and to nothing
        else: never cleaning time, never learned cleaning overhead."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        if not _is_valid_job_id(record_id):
            raise ValueError(f"invalid phase record id: {record_id!r}")
        path = paths.phases_dir / f"{record_id}.json"
        self.write_json(path, payload)
        return path

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
        try:
            path = self.get_completed_job_path(
                vacuum_entity_id=vacuum_entity_id,
                job_id=job_id,
            )
        except ValueError:
            # IO-5: an invalid job_id can never be a real job's file --
            # callers already treat this the same as "job not found".
            return None
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

    def is_learning_phased_job(
        self, *, vacuum_entity_id: str, parent: dict[str, Any]
    ) -> bool:
        """Whether a phased-job PARENT may teach the phased pool.

        Chris's rule (2026-08-02): *"if any run that is keyed to a phased run, that
        phased run should be excluded by default — it lost part of its identity."* The
        parent's whole value is that it describes a COMPLETE orchestration: this shape,
        end to end, cost this much. Excluding one child leaves the total describing a run
        that never happened, so the parent stops being a sample of anything.

        DERIVED, never stored. A stored `used_for_learning` on the parent would be a
        second source of truth that goes stale the moment a child is excluded or
        restored, and `exclude_learning_job` would have to remember to update its parent —
        the partial-closure defect this codebase keeps producing. Deriving also makes
        RESTORE free: put the child back and its parent becomes eligible again with no
        second action, because nothing was written down to undo.

        Ineligible when ANY of:
          - the run did not complete (cancelled / interrupted / partial)
          - a clean phase produced no child (`unsplit_phases`) — the total is short by
            however long that phase took, which is invisible in the number itself
          - a promised child will not load (`missing_children`)
          - any child is not itself a learning job (manually excluded, held, anomalous)
        """
        if not isinstance(parent, dict) or parent.get("record_type") != "phased_job":
            return False
        if str(parent.get("status", "")).strip().lower() != "completed":
            return False

        aggregate = parent.get("aggregate")
        aggregate = aggregate if isinstance(aggregate, dict) else {}
        if aggregate.get("unsplit_phases") or aggregate.get("missing_children"):
            return False

        clean = [
            p for p in (parent.get("phases") or [])
            # The parent's slots key the type as `type`, not `phase_type`, so the
            # dict-level helper does not fit — the TYPE-level one is the same
            # vocabulary without the shape mismatch (step_types.py warns that the
            # neighbouring vocabularies are deliberately NOT this question).
            if isinstance(p, dict) and not is_dock_polled_phase_type(p.get("type"))
        ]
        if not clean:
            return False

        for phase in clean:
            record_id = str(phase.get("record_id") or "")
            if not record_id:
                return False
            child = self.load_completed_job(
                vacuum_entity_id=vacuum_entity_id, job_id=record_id
            )
            if not isinstance(child, dict) or not self.is_learning_job(child):
                return False
        return True

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

    # RP-006 step 3 (REVIEW D4): an UNREADABLE accuracy read is cached WITH a
    # retry-after stamp instead of a permanent None. Permanent caching poisoned
    # every estimate until the next save (IO-3); NOT caching would re-attempt the
    # blocking read on every loop-bound estimate() for the whole SMB outage.
    _UNREADABLE_RETRY_SECONDS = 60.0

    def load_accuracy_stats(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Load per-room estimate accuracy stats JSON (cached; see _accuracy_stats_cache)."""
        return self.load_accuracy_stats_outcome(vacuum_entity_id=vacuum_entity_id)[1]

    def load_accuracy_stats_outcome(
        self,
        *,
        vacuum_entity_id: str,
    ) -> tuple[str, dict[str, Any] | None]:
        """Tri-state read of accuracy stats, with the D4 unreadable-backoff cache."""
        path = self.get_accuracy_stats_path(vacuum_entity_id=vacuum_entity_id)
        cache = self._accuracy_stats_cache()
        key = str(path)
        cached = cache.get(key) if key in cache else _CACHE_MISS
        if isinstance(cached, dict) and "__unreadable_until" in cached:
            if time.monotonic() < cached["__unreadable_until"]:
                return (self.READ_UNREADABLE, None)
            # backoff expired — fall through to a fresh read
        elif cached is not _CACHE_MISS:
            data = cached if isinstance(cached, dict) else None
            return (self.READ_OK if data is not None else self.READ_ABSENT, data)

        outcome, payload = self.read_json_outcome(path)
        if outcome == self.READ_UNREADABLE or (
            outcome == self.READ_OK and not isinstance(payload, dict)
        ):
            cache[key] = {"__unreadable_until": time.monotonic() + self._UNREADABLE_RETRY_SECONDS}
            return (self.READ_UNREADABLE, None)
        data = payload if isinstance(payload, dict) else None
        cache[key] = data
        return (self.READ_OK if data is not None else self.READ_ABSENT, data)

    def jobs_csv_path(self, *, vacuum_entity_id: str) -> Path:
        """Return jobs export CSV path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.exports_dir / "jobs_flat.csv"

    def rooms_csv_path(self, *, vacuum_entity_id: str) -> Path:
        """Return room export CSV path."""
        paths = self.ensure_dirs(vacuum_entity_id=vacuum_entity_id)
        return paths.exports_dir / "rooms_flat.csv"

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
        # rooms are re-queued, and that must not rewrite a RUNNING job's record: observed a
        # Kitchen+Hallway+zone run recorded as Dining+Kitchen+Hallway (zone dropped) after rooms
        # were re-queued on top of it (job_2026-07-13T07-50-49). Precedence:
        #   1. a PHASED job -> the UNION of ALL phases' rooms (deduped, order preserved). Trusting
        #      the top-level list is wrong: advance_active_job_phase overwrites it with only the
        #      phase it moved INTO, so a stepped run ending on a ROOM phase (Kitchen->charge->
        #      Hallway) would record just Hallway and drop Kitchen from room_count + learning, and
        #      one ending on a roomless ZONE phase would record zero rooms (invalid_room_count,
        #      "Unknown", dropped) even though the room phases cleaned. The phase list survives
        #      advance, so it is the reliable full set;
        #   2. an ATOMIC job (no phases) -> the top-level resolved_rooms launch snapshot;
        #   3. the LIVE payload only as a last resort (a job snapshot carrying nothing);
        #   4. the queue (below).
        resolved_rooms: list = []
        _resolved_rooms_from_phases = False
        if isinstance(active_job_state, dict):
            _phases = active_job_state.get("phases")
            if isinstance(_phases, list) and _phases:
                _seen_rids: set = set()
                for _phase in _phases:
                    if not isinstance(_phase, dict):
                        continue
                    for _room in _phase.get("resolved_rooms") or []:
                        if not isinstance(_room, dict):
                            continue
                        _rid = _room.get("room_id", _room.get("id"))
                        if _rid is not None and _rid not in _seen_rids:
                            _seen_rids.add(_rid)
                            resolved_rooms.append(_room)
                _resolved_rooms_from_phases = bool(resolved_rooms)
            if not resolved_rooms:
                _aj_rooms = active_job_state.get("resolved_rooms")
                if isinstance(_aj_rooms, list):
                    resolved_rooms = list(_aj_rooms)
        if not resolved_rooms:
            _payload_rooms = (
                payload_state.get("resolved_rooms") if isinstance(payload_state, dict) else None
            )
            if isinstance(_payload_rooms, list):
                resolved_rooms = list(_payload_rooms)

        # RP-013d/A4-STATE-6: the queue block mirrors this SAME ladder — derived
        # alongside resolved_rooms rather than as a second hand-written walk,
        # per the centralize-the-QUESTION rule. A phased job's queue_room_ids/
        # queue_rooms ARE its unioned resolved_rooms (each room_group phase's
        # queue_room_ids and resolved_rooms are built from the same members —
        # confirmed against phase_runner/run_plan's phase construction), so
        # rung 1 reuses resolved_rooms rather than re-deriving it from each
        # phase's queue_room_ids ints (which advance_active_job_phase also
        # clobbers at the top level, the exact bug the original fix missed).
        # rung 2 (atomic) and rung 3 (live) mirror the ladder's own precedence:
        # the job's own frozen snapshot outranks the live queue, which only
        # wins when the job carries NEITHER phases NOR a top-level queue.
        if _resolved_rooms_from_phases:
            _queue_room_ids = [
                _r.get("room_id", _r.get("id"))
                for _r in resolved_rooms
                if isinstance(_r, dict) and _r.get("room_id", _r.get("id")) is not None
            ]
            _queue_rooms = list(resolved_rooms)
        elif isinstance(active_job_state, dict) and active_job_state.get("queue_room_ids"):
            _queue_room_ids = list(active_job_state.get("queue_room_ids", []))
            _queue_rooms = list(active_job_state.get("queue_rooms", []))
        elif isinstance(queue_state, dict) and queue_state.get("queue_room_ids"):
            _queue_room_ids = list(queue_state.get("queue_room_ids", []))
            _queue_rooms = list(queue_state.get("queue_rooms", []))
        else:
            _queue_room_ids = []
            _queue_rooms = []
        _queue_block = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": (
                str(active_job_state.get("map_id", ""))
                if isinstance(active_job_state, dict) else ""
            ),
            "room_count": len(_queue_room_ids),
            "queue_room_ids": _queue_room_ids,
            "queue_rooms": _queue_rooms,
            # RP-013c/RF-11: persist the completed evidence so the archived record is
            # reconstructible. It lived only on the in-memory active job, which is torn
            # down at finalize -- so after the fact there was no way to tell a room that
            # was cleaned before a cancel from one that never ran, and the incomplete-run
            # log (a separate, overwritten-per-run store) was the only witness. Filled in
            # below once room_timings exist, via the SAME helper the finalizer uses.
            # Additive: readers tolerate absence on records written before this landed.
            "completed_room_ids": [],
        }

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
        mid_job_recharge_started_at = str(
            active_job_state.get("observed_mid_job_recharge_started_at", "") or ""
        ).strip() or None
        mid_job_recharge_count = max(
            _safe_int(active_job_state.get("observed_mid_job_recharge_count"), 0),
            0,
        )
        # live:RECHARGE-FLAG-1. `observed_mid_job_recharge` is a LIVE "charging right
        # now" flag, and resolve_mid_job_recharge_resumed CLEARS it the moment the
        # robot goes back to work. Read straight, it answers "was the robot charging
        # at the instant we finalized" — so a run that recharged AND RESUMED, which is
        # every successful mid-job recharge, records that none happened.
        #
        # THE RECORD MUST ANSWER A DIFFERENT QUESTION: did a recharge occur during this
        # run. That is a fact about the past and the accumulators already hold it —
        # they are written on resume and never cleared. The live flag stays in the OR
        # only for the one case the accumulators cannot cover: finalizing while still
        # docked and charging, where the resume that would have accrued the seconds
        # has not happened yet.
        #
        # Proven both ways on two runs that each had exactly ONE real recharge:
        #   02-52-05  resumed -> flag cleared -> recorded False, count 1, accum 6059
        #   05-33-49  finalized while charging -> recorded True (right, wrong reason)
        # See live:RECHARGE-FLAG-2 for why that second one also over-counted.
        mid_job_recharge_observed = (
            mid_job_recharge_count > 0
            or recharge_seconds_accumulated > 0
            or _safe_bool(active_job_state.get("observed_mid_job_recharge"), False)
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
                # The cancel reason is appended AFTER outcome["learning_blockers"]
                # was snapshotted above, so re-publish the canonical list — else a
                # heuristic-detected cancel (was_cancelled not already set) persists
                # with an empty blockers list despite used_for_learning=False, and
                # the reason survives only in cancel_detection. Mirrors the idle-wall
                # guard, which writes outcome["learning_blockers"] the same way.
                outcome["learning_blockers"] = sorted(set(learning_blockers))

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
                # RP-013a: an empty room_timing is only a capture FAILURE for a
                # CLEANING phase (room_group) — a non-cleaning phase
                # (charge_wait/wait/zone) writes room_timing=[] on purpose
                # (phase_runner._capture_finishing_phase_timing), and that is
                # VALID-EMPTY, not evidence the segmenter failed. Conflating
                # the two flagged EVERY stepped run transit_capture_valid=False,
                # falling back to an even wall-time split that included dock
                # time the break phase exists to represent.
                elif not phase_capture_is_valid(_p):
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
                from .external_ingest import (
                    attribution_shift_blocks_learning,
                    reconcile_dispatched_identity,
                )

                reconcile_dispatched_identity(
                    room_timings=room_timings,
                    pose_samples=_pose_samples,
                    vacuum_entity_id=vacuum_entity_id,
                    positional_valid=transit_capture_valid,
                    slug_by_id=slug_by_id,
                )
                # live:RECHARGE-ATTR-1 (the net). FLAG is deliberately conservative —
                # it keeps a working positional assignment and leaves learning
                # inclusion alone, which is right for ONE ambiguous room. It is not
                # right for a MONOTONE SLIDE across consecutive rooms: that is a
                # dropped boundary, so the numbers are attached to the wrong rooms
                # and no amount of per-room caution makes them safe to learn.
                #
                # Applied here rather than in the blockers block above because
                # room_timings do not exist until this point. Same shape as the
                # cancel_detection amendment below: append, clear the flag, and
                # RE-PUBLISH the canonical list, since outcome["learning_blockers"]
                # was already snapshotted from a copy.
                if attribution_shift_blocks_learning(room_timings):
                    learning_blockers.append("attribution_shift")
                    used_for_learning = False
                    outcome["used_for_learning"] = False
                    outcome["learning_blockers"] = sorted(set(learning_blockers))

        # Zone phases carry their OWN zone_timing (phase_runner._capture_zone_phase_timing); the
        # room path drops them, so gather them in parallel — the record + review card show which
        # zones ran and their learned wall-clock (the zone learning keys on the same data).
        zone_timings: list[dict[str, Any]] = []
        if isinstance(_phases, list):
            for _p in _phases:
                _zt = _p.get("zone_timing") if isinstance(_p, dict) else None
                if isinstance(_zt, dict):
                    zone_timings.append(dict(_zt))

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
                # Zones cleaned in this run (name/mode/wall-clock/area snapshotted at run time),
                # so the review can show them alongside rooms. Empty for a rooms-only run.
                "zone_timings": zone_timings,
                "zone_count": len(zone_timings),
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
            "queue": {
                **_queue_block,
                # Filled HERE rather than where _queue_block is built, because the third
                # evidence source (room_timings) does not exist until further down. The
                # helper is shared with the finalizer's incomplete-run log on purpose:
                # when the two computed it separately they disagreed about the same job.
                "completed_room_ids": known_completed_room_ids(
                    active_job_state, room_timings
                ),
            },
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
