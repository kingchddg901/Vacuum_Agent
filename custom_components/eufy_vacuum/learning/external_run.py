"""ExternalRunManager — capture / grace-finalize / review-ingest of app-started runs.

This subsystem owns the EXTERNAL-RUN lifecycle: an app-started (not-dispatched) clean is
detected while cleaning with no dispatched job, captured into a status="external" slot, and —
once the robot reaches the dock and stays there past a grace window — segmented into a pending
review record under ``external_jobs/``. It also owns the review-wizard server side: listing the
pending records, re-segmenting one, discarding one, and graduating a confirmed one into a normal
completed-job record.

Owns:
- ``maybe_handle_external_run`` — detect + open/close the capture slot (the lifecycle listener
  calls it via the manager delegator).
- grace machinery (``_external_grace_timers`` / ``_external_grace_checks`` / ``_external_grace_cb``
  / ``_external_grace_finalize`` / ``_external_status_is_mid_run``) — defer the finalize until the
  robot has stayed docked, re-checking while task_status reports a mid-run station cycle.
- ``_extract_return_overhead`` + ``_finalize_external_run`` — book mid-run docks as overhead and
  segment the buffered samples into the pending record + fire ``EVENT_EXTERNAL_RUN_PENDING``.
- ``confirm_external_run`` / ``get_external_pending_runs`` / ``discard_external_run`` /
  ``resegment_external_run`` — the review-wizard server side (all sync — run on the executor).

Extracted from core/manager.py. The manager keeps thin delegators for every moved method
(the service layer ``learning/services.py``, the ``listeners/lifecycle.py`` hook, and the tests
reference ``manager.<method>`` — including the grace helpers — unchanged). SHARED helpers stay in
core: ``_ingest_completed_job_into_room_history`` / ``_ingest_jobs_index_entry_into_room_history``
(also driven by the normal completed-job finalize + the room-history cache preload) and
``resolve_active_map_id`` / ``start_external_capture`` (manager-level, reached here via
``self._manager.<...>``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from .constants import EXTERNAL_FINALIZE_GRACE_S, EXTERNAL_GRACE_MAX_RECHECKS

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


class ExternalRunManager:
    """Owns the external (app-started) run lifecycle. Constructed with the core manager (the
    bundled-subsystem pattern); reads ``manager.hass`` + the manager's active-job / map / save
    helpers via ``self._manager`` and holds the in-memory grace-timer / re-check state."""

    def __init__(self, *, manager: "EufyVacuumManager") -> None:
        self._manager = manager

    async def maybe_handle_external_run(self, *, vacuum_entity_id: str) -> bool:
        """Detect + capture an app-started (external) run.

        Internal starts are blocked while a run is in progress, so a vacuum that
        is cleaning with NO dispatched job (status started/paused on any map) is
        an external run. Open a capture-only slot (status="external") when it
        begins; when the robot returns home, segment the capture into a pending
        review record under external_jobs/ and clear the slot. Returns True when a
        slot was opened or finalized (the caller persists).
        """
        dispatched = False
        external_map_id: str | None = None
        for map_id in self._manager.get_known_map_ids(vacuum_entity_id):
            status = self._manager.get_active_job(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id
            ).get("status")
            if status in {"started", "paused"}:
                dispatched = True
            elif status == "external":
                external_map_id = str(map_id)
        if dispatched:
            return False  # internal owns this run

        state_obj = self._manager.hass.states.get(vacuum_entity_id)
        vacuum_state = str(getattr(state_obj, "state", "") or "").strip().lower()

        if external_map_id is not None:
            # In progress. External runs hide active_cleaning_target, so we key the
            # end on the vacuum entity — but NOT immediately: the robot may be
            # docking mid-run (mop prewash, recharge) and about to resume.
            key = (vacuum_entity_id, external_map_id)
            timers = self._external_grace_timers()
            if vacuum_state == "cleaning":
                # Resumed after a mid-run dock — cancel the pending grace finalize so
                # the whole run stays ONE record (the dock gap becomes a cleaning_time
                # plateau the segmenter splits into a room boundary => multi-segment).
                cancel = timers.pop(key, None)
                if cancel:
                    cancel()
                return False
            if vacuum_state in {"docked", "idle"}:
                # Defer the finalize by the grace window; if it resumes we cancel
                # above, otherwise the timer fires _external_grace_finalize.
                if key not in timers:
                    timers[key] = async_call_later(
                        self._manager.hass,
                        EXTERNAL_FINALIZE_GRACE_S,
                        self._external_grace_cb(vacuum_entity_id, external_map_id),
                    )
                return False
            return False

        if vacuum_state == "cleaning":
            active_map_id = self._manager.resolve_active_map_id(vacuum_entity_id)
            if active_map_id:
                self._manager.start_external_capture(
                    vacuum_entity_id=vacuum_entity_id, map_id=active_map_id
                )
                return True
        return False

    def _external_grace_timers(self) -> dict[tuple[str, str], Any]:
        """Pending grace-window finalize cancels, keyed by (vacuum, map). Lazily
        created so we needn't touch __init__; in-memory only (a restart drops them,
        and the next dock event reschedules)."""
        timers = getattr(self, "_ext_grace_timers", None)
        if timers is None:
            timers = {}
            self._ext_grace_timers = timers
        return timers

    def _external_grace_checks(self) -> dict[tuple[str, str], int]:
        """Per-(vacuum, map) count of grace re-checks while task_status stayed
        mid-run; capped by EXTERNAL_GRACE_MAX_RECHECKS. Lazily created."""
        checks = getattr(self, "_ext_grace_checks", None)
        if checks is None:
            checks = {}
            self._ext_grace_checks = checks
        return checks

    def _external_status_is_mid_run(self, vacuum_entity_id: str) -> bool:
        """True when the vacuum's task_status reports a mid-run station cycle (mop
        wash / dust empty / recharge-resume) — the robot is docked but WILL resume,
        so an external run must not be finalized. Values are adapter-declared
        (external_mid_run_statuses) and compared case-insensitively."""
        from ..adapters.registry import get_adapter_config

        cfg = get_adapter_config(vacuum_entity_id) or {}
        mid_run = cfg.get("external_mid_run_statuses") or []
        if not mid_run:
            return False
        entity_id = (cfg.get("entities", {}) or {}).get("task_status")
        if not entity_id:
            return False
        state_obj = self._manager.hass.states.get(entity_id)
        value = str(getattr(state_obj, "state", "") or "").strip().lower()
        return value in {str(s).strip().lower() for s in mid_run}

    def _external_grace_cb(self, vacuum_entity_id: str, map_id: str):
        @callback
        def _fire(_now) -> None:
            self._external_grace_timers().pop((vacuum_entity_id, map_id), None)
            self._manager.hass.async_create_task(
                self._external_grace_finalize(vacuum_entity_id, map_id)
            )

        return _fire

    async def _external_grace_finalize(self, vacuum_entity_id: str, map_id: str) -> None:
        """Grace window elapsed with the robot still home. Finalize the external run
        UNLESS task_status says it is mid-run (washing the mop / emptying dust /
        recharging to resume) — then it will come back, so re-check instead of
        closing it. We persist here ourselves (the listener path saves separately)."""
        key = (vacuum_entity_id, map_id)
        checks = self._external_grace_checks()
        slot = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if slot.get("status") != "external":
            checks.pop(key, None)
            return  # already resumed or cleared
        state_obj = self._manager.hass.states.get(vacuum_entity_id)
        state = str(getattr(state_obj, "state", "") or "").strip().lower()
        if state not in {"docked", "idle"}:
            checks.pop(key, None)
            return  # resumed (raced the cancel) — leave open for the next dock
        n = checks.get(key, 0)
        if self._external_status_is_mid_run(vacuum_entity_id) and n < EXTERNAL_GRACE_MAX_RECHECKS:
            # Still in a mid-run station cycle — keep the run open and re-check.
            checks[key] = n + 1
            self._external_grace_timers()[key] = async_call_later(
                self._manager.hass,
                EXTERNAL_FINALIZE_GRACE_S,
                self._external_grace_cb(vacuum_entity_id, map_id),
            )
            return
        checks.pop(key, None)
        await self._finalize_external_run(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id, slot=slot
        )
        await self._manager.async_save()

    async def _extract_return_overhead(
        self, vacuum_entity_id: str, start_ts: Any, end_ts: Any
    ) -> dict[str, Any]:
        """Sum the wall time the robot spent returning/docked/paused BETWEEN cleaning
        within an external run (mop prewash, recharge) by reading the recorder for the
        run window — so the merged run books that span as overhead, not cleaning.
        Best-effort: returns zero on any failure (the record still writes)."""
        empty = {"return_overhead_s": 0, "return_intervals": []}
        try:
            from homeassistant.components.recorder import get_instance, history

            from ..timestamp_utils import parse_timestamp

            start = parse_timestamp(start_ts)
            end = parse_timestamp(end_ts)
            if not start or not end or end <= start:
                return empty
            states = await get_instance(self._manager.hass).async_add_executor_job(
                history.state_changes_during_period,
                self._manager.hass,
                start,
                end,
                vacuum_entity_id,
            )
            rows = (states or {}).get(vacuum_entity_id, []) or []
            non_cleaning = {"returning", "returning_to_dock", "docked", "paused", "idle"}
            overhead = 0.0
            intervals: list[dict[str, Any]] = []
            for i, st in enumerate(rows):
                value = str(getattr(st, "state", "") or "").strip().lower()
                t0 = getattr(st, "last_changed", None) or getattr(st, "last_updated", None)
                t1 = (
                    getattr(rows[i + 1], "last_changed", None)
                    if i + 1 < len(rows)
                    else end
                )
                if value in non_cleaning and t0 and t1:
                    seconds = (t1 - t0).total_seconds()
                    if seconds > 0:
                        overhead += seconds
                        intervals.append(
                            {
                                "state": value,
                                "start": t0.isoformat(),
                                "seconds": round(seconds),
                            }
                        )
            return {"return_overhead_s": round(overhead), "return_intervals": intervals}
        except Exception:
            _LOGGER.exception("external finalize: return-overhead extraction failed")
            return empty

    async def _finalize_external_run(
        self, *, vacuum_entity_id: str, map_id: str, slot: dict[str, Any]
    ) -> None:
        """Segment a finished external capture into a pending record + clear the slot."""
        counter_samples = list(slot.get("counter_samples", []) or [])
        settings_samples = list(slot.get("settings_samples", []) or [])
        # W5c: the run-active pose stream (pose_sampler) — drives room attribution in
        # build_pending_record (pre-fills the wizard / stands up a pose-only record). Empty
        # for a non-map brand or a run with no live map → attribution is skipped downstream.
        pose_samples = list(slot.get("pose_samples", []) or [])
        detection_ts = slot.get("started_at")
        rooms = (
            self._manager.get_managed_rooms(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            or {}
        ).get("rooms", {})

        # Returning/dock overhead from the recorder, bounded to the last cleaning
        # tick so the final (true-end) dock isn't counted — books mid-run docks
        # (mop prewash / recharge) as overhead, not cleaning.
        last_t = counter_samples[-1].get("t") if counter_samples else detection_ts
        overhead = await self._extract_return_overhead(
            vacuum_entity_id, detection_ts, last_t
        )

        def _build_and_write() -> dict[str, Any] | None:
            import json

            from ..learning.external_ingest import build_pending_record
            from ..learning.history_store import LearningHistoryStore

            store = LearningHistoryStore(self._manager.hass)
            paths = store.get_paths(vacuum_entity_id=vacuum_entity_id)
            baselines: list[dict[str, Any]] = []
            try:
                with open(
                    paths.learned_dir / "room_stats.json", encoding="utf-8"
                ) as handle:
                    baselines = (json.load(handle) or {}).get("room_baselines", []) or []
            except (OSError, ValueError):
                baselines = []
            # The v2 record embeds the raw samples so the run can be re-segmented
            # (counter) and re-attributed (pose) server-side; both are stripped before
            # serving to the card. Bounded by _MAX_COUNTER_SAMPLES + _MAX_POSE_SAMPLES
            # (active_job.py) — a normal run is small (~50-150 KB); the pose worst case
            # is the 3000-sample cap (a long stall, which the stall-detector fix prevents).
            record = build_pending_record(
                detection_ts=detection_ts,
                map_id=map_id,
                counter_samples=counter_samples,
                settings_samples=settings_samples,
                rooms=rooms,
                baselines=baselines,
                vacuum_entity_id=vacuum_entity_id,
                pose_samples=pose_samples,
            )
            if record is None:
                return None
            record["return_overhead_s"] = overhead["return_overhead_s"]
            record["return_intervals"] = overhead["return_intervals"]
            safe_ts = (
                str(detection_ts or "unknown").split("+")[0].split(".")[0].replace(":", "-")
            )
            path = paths.root / "external_jobs" / f"job_{safe_ts}.json"
            store.write_json(path, record)
            return {"path": str(path), "segment_count": record.get("segment_count")}

        # Always clear the slot, even if the build raises — otherwise a build error leaves a
        # zombie status="external" slot that the pose sampler keeps writing into and that wedges
        # this (vacuum, map)'s future grace handling. (_attribute already degrades a failed
        # attribution to None on its own, so the common case still writes a counter record.)
        try:
            result = await self._manager.hass.async_add_executor_job(_build_and_write)
        except Exception:
            _LOGGER.exception(
                "eufy_vacuum: external-run finalize failed for %s/%s — clearing the slot",
                vacuum_entity_id, map_id,
            )
            result = None
        finally:
            self._manager.clear_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if result is not None:
            from ..const import EVENT_EXTERNAL_RUN_PENDING

            self._manager.hass.bus.async_fire(
                EVENT_EXTERNAL_RUN_PENDING,
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "record_path": result["path"],
                    "segment_count": result["segment_count"],
                    "detection_ts": detection_ts,
                },
            )

    def confirm_external_run(
        self,
        vacuum_entity_id: str,
        map_id: str,
        pending_job_id: str,
        room_assignments: list[dict[str, Any]],
        rooms: dict[str, Any],
        rebuild_stats: bool = True,
    ) -> dict[str, Any]:
        """Graduate a confirmed external pending record into a normal completed-job
        record (sync — runs on the executor; the caller loads ``rooms`` on the loop).

        Tier-1 gates each assignment's area vs the room's learned band; if any is
        implausible without override the whole confirm is blocked (returns
        ``{ok: False, blocked: [...]}``). On success: write jobs/<id>.json, delete
        the pending external_jobs/ file, and rebuild learned stats (the rebuilder's
        W3 area gate then handles per-room partial-exclusion for free).
        """
        import json

        from ..learning.external_ingest import build_graduated_job
        from ..learning.history_store import LearningHistoryStore
        from ..timestamp_utils import utc_now_iso

        store = LearningHistoryStore(self._manager.hass)
        paths = store.get_paths(vacuum_entity_id=vacuum_entity_id)
        pending_path = paths.root / "external_jobs" / f"{pending_job_id}.json"
        try:
            with open(pending_path, encoding="utf-8") as handle:
                pending = json.load(handle)
        except (OSError, ValueError):
            return {"ok": False, "error": "pending_not_found", "pending_job_id": pending_job_id}

        bands_by_slug: dict[str, Any] = {}
        try:
            with open(paths.learned_dir / "room_stats.json", encoding="utf-8") as handle:
                for entry in (json.load(handle) or {}).get("room_baselines", []) or []:
                    if str(entry.get("map_id")) == str(map_id):
                        bands_by_slug[str(entry.get("room_slug", "")).strip().lower()] = entry
        except (OSError, ValueError):
            pass

        ended_at = utc_now_iso()
        job_id = f"ext-{pending_job_id}"
        record, blocked = build_graduated_job(
            pending_record=pending,
            assignments=room_assignments,
            rooms=rooms,
            bands_by_slug=bands_by_slug,
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
            ended_at=ended_at,
        )
        if record is None:
            return {"ok": False, "blocked": blocked, "pending_job_id": pending_job_id}

        job_path = store.save_completed_job(
            vacuum_entity_id=vacuum_entity_id, job_id=job_id, payload=record
        )
        try:
            pending_path.unlink(missing_ok=True)
        except OSError:
            pass
        rebuilt = False
        if rebuild_stats:
            # The core manager owns no rebuilder (it lives on the LearningManager /
            # job finalizer); construct one directly here -- this is exactly what the
            # LearningManager does internally. Best-effort: the job is ALREADY
            # graduated (written + pending removed), so a rebuild hiccup must not fail
            # the confirm. Rerun eufy_vacuum.rebuild_learning_stats to pick it up.
            try:
                from ..learning.stats_rebuilder import LearningStatsRebuilder

                LearningStatsRebuilder(self._manager.hass).rebuild_all(
                    vacuum_entity_id=vacuum_entity_id, rebuild_csv=False
                )
                rebuilt = True
            except Exception:
                _LOGGER.exception(
                    "external confirm: stats rebuild failed (job %s graduated; "
                    "rerun eufy_vacuum.rebuild_learning_stats)",
                    job_id,
                )
        return {
            "ok": True,
            "job_id": job_id,
            "job_path": str(job_path),
            "rooms_learned": len(record["job_profile"]["rooms"]),
            "rebuilt": rebuilt,
        }

    def get_external_pending_runs(self, vacuum_entity_id: str) -> dict[str, Any]:
        """List pending external review records (external_jobs/) for the card."""
        from ..adapters.registry import get_adapter_config
        from ..learning.external_ingest import load_pending_runs
        from ..learning.history_store import LearningHistoryStore

        store = LearningHistoryStore(self._manager.hass)
        paths = store.get_paths(vacuum_entity_id=vacuum_entity_id)
        pending = load_pending_runs(str(paths.root / "external_jobs"))
        adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "pending": pending,
            "count": len(pending),
            # Adapter-provided brand label for the card's copy (None -> the
            # card uses generic phrasing). Keeps brand names out of the card.
            "brand": adapter_cfg.get("brand"),
        }

    def discard_external_run(self, vacuum_entity_id: str, pending_job_id: str) -> dict[str, Any]:
        """Delete a pending external review record (the user discarded it)."""
        from ..learning.history_store import LearningHistoryStore

        store = LearningHistoryStore(self._manager.hass)
        paths = store.get_paths(vacuum_entity_id=vacuum_entity_id)
        path = paths.root / "external_jobs" / f"{pending_job_id}.json"
        try:
            path.unlink(missing_ok=True)
        except OSError as err:
            return {"ok": False, "error": str(err)}
        return {"ok": True, "pending_job_id": pending_job_id}

    def resegment_external_run(
        self,
        vacuum_entity_id: str,
        map_id: str,
        pending_job_id: str,
        expected_rooms: int | None,
        active_boundaries: list[int] | None,
        rooms: dict[str, Any],
    ) -> dict[str, Any]:
        """Re-segment a pending external record server-side (the review wizard's
        room-count / per-boundary toggle) and rewrite it in place.

        Reads the embedded raw samples, re-runs the real segmenter for the requested
        count or boundary set, and returns the new (sample-stripped) record plus the
        selection ``meta`` (cap info). Returns an error WITHOUT touching the file when
        the record is missing, has no samples (a v1 record), or the selection yields
        no segment — so a usable record is never blanked."""
        import json

        from ..learning.external_ingest import resegment_pending_record, strip_samples
        from ..learning.history_store import LearningHistoryStore

        store = LearningHistoryStore(self._manager.hass)
        paths = store.get_paths(vacuum_entity_id=vacuum_entity_id)
        path = paths.root / "external_jobs" / f"{pending_job_id}.json"
        try:
            with open(path, encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            return {"ok": False, "error": "pending_not_found"}
        if not isinstance(record, dict) or not record.get("counter_samples"):
            return {"ok": False, "error": "not_resegmentable", "reason": "no_samples"}

        baselines: list[dict[str, Any]] = []
        try:
            with open(paths.learned_dir / "room_stats.json", encoding="utf-8") as handle:
                baselines = (json.load(handle) or {}).get("room_baselines", []) or []
        except (OSError, ValueError):
            baselines = []

        new_record, meta = resegment_pending_record(
            pending_record=record,
            expected_rooms=expected_rooms,
            active_ids=active_boundaries,
            rooms=rooms or {},
            baselines=baselines,
            vacuum_entity_id=vacuum_entity_id,
        )
        if new_record is None:
            return {"ok": False, "error": "empty_segmentation", **meta}
        store.write_json(path, new_record)
        out = strip_samples(dict(new_record))
        out["pending_job_id"] = pending_job_id
        return {"ok": True, **out, **meta}
