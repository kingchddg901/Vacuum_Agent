"""PhaseRunner — strict-order (sequenced) phase execution + per-phase timing capture.

A path-optimizing brand (Roborock S6) re-routes a multi-room batch, so strict order is
honored by dispatching ONE room per phase (the sequenced job model). This subsystem owns the
two halves of that:

- **Watchdog** (``_run_advanced_phase`` → settle / dispatch / verify / retry, with
  ``_await_phase_started`` / ``_dispatch_active_phase`` / ``_clear_phase_dispatch_pending`` /
  ``_vacuum_started_cleaning``): the device finishes a room, docks + starts charging, and
  IGNORES an app_segment_clean sent at that instant — so each next room is dispatched from a
  background task that settles, sends, verifies the robot actually started THIS room, and
  re-sends if not. The retry cap is the per-phase watchdog.
- **Per-phase timing capture** (``_capture_finishing_phase_timing`` → ``_phase_room_timing`` /
  ``_wall_seconds`` / ``_learned_room_area_m2``): snapshot each finishing phase's room timing
  from ITS OWN counter slice before advance resets the queue, so finalization reconstructs
  per-phase timings instead of mis-attributing the whole run to the last phase's room.

``maybe_advance_phase`` is the public entry point (the completion hook calls it via the
manager delegator). The watchdog TIMING (the ``_PHASE_*`` in-core defaults + the adapter
``dispatch.phase_timing`` overrides) stays on the core manager — ``_phase_timing`` is the
single resolver and is read here via ``self._manager._phase_timing``; this subsystem owns only
the orchestration, keeping the brand-tuned defaults a core-level surface.

Extracted from core/manager.py (the orchestrator delegates ``maybe_advance_phase`` and spawns
``_run_advanced_phase`` for the initial phase from ``start_selected_rooms``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError

from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..queue.queue_engine import advance_active_job_phase
from ..timestamp_utils import parse_timestamp, utc_now_iso
from ..step_types import is_dock_polled_phase, is_dock_polled_phase_type

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


def _iso_now() -> str:
    """Return current UTC timestamp in stable format."""
    return utc_now_iso()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return float value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _elapsed_seconds(start_t: str, end_t: str) -> int:
    """Whole seconds between two stamps, 0 when either is unreadable or out of order.

    Clamped at zero: a clock skew must never hand the parent a NEGATIVE hold to
    subtract from a boundary.
    """
    a = parse_timestamp(start_t or None)
    b = parse_timestamp(end_t or None)
    if a is None or b is None:
        return 0
    return int(max(0.0, (b - a).total_seconds()))


def _safe_int(value: Any, default: int = 0) -> int:
    """Return int value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _distribute_int(total: int, n: int) -> list[int]:
    """Split ``total`` into ``n`` non-negative parts that sum EXACTLY to ``total``.

    Used to apportion a group phase's measured totals across its members without
    losing or fabricating a fraction — the base share plus one remainder unit each
    to the first ``total % n`` members (RP-013b: total preservation is asserted,
    not assumed)."""
    base, rem = divmod(total, n)
    return [base + 1 if i < rem else base for i in range(n)]


class PhaseRunner:
    """Owns strict-order phase execution. Constructed with the core manager (the
    bundled-subsystem pattern); reads/writes ``manager.data['active_jobs']`` and uses
    ``manager.hass`` + the manager's dispatch/save helpers + ``manager._phase_timing``."""

    def __init__(self, *, manager: "EufyVacuumManager") -> None:
        self._manager = manager
        # Per-(vac, map, phase_index) "a dock-phase poller is live" guard. A charge_wait /
        # wait phase's driver is an in-memory asyncio task; a normal advance spawns it once,
        # but a pause+resume or an HA-restart re-arm (rearm_dock_phase_if_needed) could
        # otherwise spawn a SECOND concurrent poller for the SAME phase. This key is set
        # before a poller task is created and cleared in its finally, so a re-arm can't
        # double-drive a phase a live poller already owns. Keyed by phase_index (not just
        # vac/map) so a poller advancing to the NEXT dock phase can still spawn that phase's
        # poller before its own finally clears the old key. In-memory only (like the task).
        self._dock_poller_active: set[tuple[str, str, int]] = set()
        # RP-003/INIT-1: ledger of live dock-poller tasks (both normal-advance and
        # re-arm spawned — re-arm is a subset), so a manager shutdown (reload) can
        # cancel every one it started rather than leaving them to keep driving a
        # job on a manager that no longer owns the store.
        self._dock_poller_tasks: dict[tuple[str, str, int], asyncio.Task] = {}

    def cancel_all(self) -> list[asyncio.Task]:
        """Cancel every live dock-poller task; return the cancelled tasks so the
        caller can await their unwind. Clears both ledgers — a cancelled poller's
        own finally would clear _dock_poller_active too, but shutdown does not wait
        for that to happen before this returns."""
        tasks = list(self._dock_poller_tasks.values())
        for task in tasks:
            task.cancel()
        self._dock_poller_tasks.clear()
        self._dock_poller_active.clear()
        return tasks

    def _spawn_dock_poller(
        self, *, vacuum_entity_id: str, map_id: str, phase_type: str, phase_index: int
    ) -> bool:
        """Spawn the charge_wait / wait poller for one phase, guarded against a
        double-spawn. Returns True when a poller was started, False when one is already
        live for this (vac, map, phase) — the shared guard the normal advance AND the re-arm
        both route through, so they can never both drive the same dock phase. The poller
        clears the guard in its own finally (via ``_run_charge_wait_phase`` / ``_run_wait_phase``)."""
        key = (vacuum_entity_id, str(map_id), int(phase_index))
        if key in self._dock_poller_active:
            return False
        self._dock_poller_active.add(key)
        coro = (
            self._run_charge_wait_phase(
                vacuum_entity_id=vacuum_entity_id, map_id=str(map_id), phase_index=phase_index
            )
            if phase_type == "charge_wait"
            else self._run_wait_phase(
                vacuum_entity_id=vacuum_entity_id, map_id=str(map_id), phase_index=phase_index
            )
        )
        task = self._manager.hass.async_create_task(coro)
        # Real hass.async_create_task always returns a Task; some tests stub it to
        # close the coroutine and return None to skip running the poller body while
        # still exercising the guard — nothing to ledger in that case.
        if task is not None:
            self._dock_poller_tasks[key] = task
            task.add_done_callback(lambda _t, _k=key: self._dock_poller_tasks.pop(_k, None))
        return True

    def rearm_dock_phase_if_needed(self, *, vacuum_entity_id: str, map_id: str) -> bool:
        """Re-arm a phase whose in-memory driver was lost (pause+resume or HA restart).

        A ``charge_wait`` / ``wait`` phase is driven ONLY by an in-memory asyncio task spawned
        from ``maybe_advance_phase``. A pause+resume (status flips back to 'started' but re-arms
        nothing) or an HA restart (the task is gone and ``async_initialize`` force-clears the
        ``_phase_dispatch_pending`` guard) leaves the dock phase with NO live driver — the run
        wedges in 'started' forever. When the active job is 'started' and its CURRENT phase is a
        dock phase, re-spawn the matching poller. Guarded via ``_spawn_dock_poller`` so a normal
        advance and a re-arm can't both spawn. The poller's own already-at-target / deadline /
        _still_ours logic makes a fresh spawn idempotent; the wait poller recomputes its deadline
        from the persisted ``wait_started_at`` so a restart mid-wait doesn't restart the full timer.

        RP-011/RF-07 (WD-4/CAN-4): a ``room_group`` / ``zone`` phase's ONLY driver is ALSO an
        in-memory asyncio task — ``_run_advanced_phase``'s watchdog — and loses it exactly the
        same way. Previously nothing re-armed those, so a restart/resume mid-strict-order left
        the run wedged with no dispatcher at all. Spawns a fresh watchdog attempt
        (``initial=False`` — the original initial send, if any, is long gone, so this one must
        actually dispatch) and clears any liveness marking a previous crashed watchdog left.

        Either branch re-asserts ``_phase_dispatch_pending`` (the restart cleared it) so the
        intentional dock/dispatch isn't read as a completion while the re-armed driver runs.
        Returns True when re-armed."""
        job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=str(map_id))
        if not isinstance(job, dict) or job.get("status") != "started":
            return False
        phases = job.get("phases")
        if not isinstance(phases, list):
            return False
        idx = _safe_int(job.get("current_phase_index"), -1)
        if not (0 <= idx < len(phases)) or not isinstance(phases[idx], dict):
            return False
        phase_type = str(phases[idx].get("phase_type") or "")
        # Re-assert the dispatch guard the restart cleared, so the intentional
        # dock/dispatch the driver is about to (re)drive isn't finalized by the
        # completion gate. No-op if already set.
        if not job.get("_phase_dispatch_pending"):
            job["_phase_dispatch_pending"] = True
            self._manager.data.setdefault("active_jobs", {}).setdefault(
                vacuum_entity_id, {}
            )[str(map_id)] = job
        if is_dock_polled_phase_type(phase_type):
            return self._spawn_dock_poller(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                phase_type=phase_type,
                phase_index=idx,
            )
        self._reset_phase_watchdog_liveness(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id), phase_index=idx,
        )
        self._manager.hass.async_create_task(
            self._run_advanced_phase(
                vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
                phase_index=idx, initial=False,
            )
        )
        return True

    async def maybe_advance_phase(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> bool:
        """For a sequenced job at phase completion, advance + re-dispatch instead
        of finalizing.

        Returns True when the job advanced to a next phase (the caller must skip
        finalization); False for an atomic job or the final phase (the caller
        finalizes exactly as today). The completion hook calls this right before
        it would finalize.
        """
        active_job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        # RP-010/RF-06: a cancel's own return-to-base dock can read as phase
        # completion (_phase_dispatch_pending is released before the terminal
        # confirm, by design — see async_cancel_active_job). While a cancel is in
        # flight the cancel path owns finalization; do not advance or snapshot
        # timing for a phase the cancel is about to tear down.
        if active_job.get("_cancel_in_flight"):
            return False
        # ...and refuse once the cancel has FINISHED. `_cancel_in_flight` above only covers
        # the window while it runs: mark_active_job_finalized deliberately clears that latch,
        # so after a cancel completes the flag is False again while `status` is "completed"
        # and `finalized` is True — neither of which this function used to read.
        #
        # A cancel therefore MARKED the job without stopping the phase machine. Any late
        # caller could still advance it and DISPATCH THE NEXT PHASE: a wait poller that
        # passes its deadline in the same tick the cancel lands, or the completion event
        # from the cancel's own return_to_base dock. The robot starts cleaning again after
        # you cancelled it, and the run writes phases past its own finalize.
        #
        # Mirrors the pollers' `_still_ours` predicate — a job is advanceable only while it
        # is genuinely live. A paused job is excluded too: resume re-arms the phase.
        if active_job.get("finalized") or str(active_job.get("status") or "") != "started":
            _LOGGER.debug(
                "maybe_advance_phase: refusing to advance %s map %s — job is %s"
                "%s; a finished run must not dispatch another phase.",
                vacuum_entity_id, map_id, active_job.get("status"),
                " (finalized)" if active_job.get("finalized") else "",
            )
            return False
        # Snapshot the FINISHING phase's room_timing from its OWN counter slice BEFORE advance
        # resets the queue/timing. Without this, strict-order finalization segments the whole
        # accumulated counter stream against only the LAST phase's queue (the per-room dock trips
        # break the segmenter) and records one room with the whole run's battery/area. Captures
        # the final phase too — advance returns None just below, but this already ran.
        self._capture_finishing_phase_timing(vacuum_entity_id, str(map_id), active_job)
        # Phased Jobs wave 1: attach the FINISHING phase to its parent, and give a break
        # phase the record it never had. Must run after the capture (it reads the
        # ``_timing_end_t`` the capture just stamped) and before the advance (it reads
        # ``current_phase_index``, which the advance moves). Runs for the final phase too:
        # the advance returns None just below, but this has already recorded it.
        self._record_phase_to_parent(vacuum_entity_id, str(map_id), active_job)
        advanced = advance_active_job_phase(active_job)
        if advanced is None:
            return False

        advanced["current_room_started_at"] = _iso_now()
        self._manager.data.setdefault("active_jobs", {})
        self._manager.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self._manager.data["active_jobs"][vacuum_entity_id][str(map_id)] = advanced

        # Re-dispatch the next phase from a background task (spawned, not awaited, so
        # the completion listener returns promptly). A room_group phase goes to the
        # settle/dispatch/verify watchdog; a charge_wait phase goes to the charge
        # poller, which docks + waits for the battery target before advancing.
        _next_idx = int(advanced.get("current_phase_index", 0))
        _next_phases = advanced.get("phases") or []
        _next_phase = (
            _next_phases[_next_idx]
            if 0 <= _next_idx < len(_next_phases) and isinstance(_next_phases[_next_idx], dict)
            else {}
        )
        _next_type = str(_next_phase.get("phase_type") or "")
        if is_dock_polled_phase_type(_next_type):
            # Route through the guarded spawn so a normal advance and a re-arm
            # (rearm_dock_phase_if_needed) can't both drive the same dock phase.
            self._spawn_dock_poller(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                phase_type=_next_type,
                phase_index=_next_idx,
            )
        else:
            self._manager.hass.async_create_task(
                self._run_advanced_phase(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    phase_index=_next_idx,
                )
            )
        return True

    def _learned_room_area_m2(
        self, vacuum_entity_id: str, map_id: str, room_id: Any
    ) -> float | None:
        """The room's learned area (m²) from the map registry, for the strict-order per-phase
        AREA fallback when the live cleaning_area delta is unusable. None when unknown."""
        rid = _safe_int(room_id, -1)
        if rid <= 0:
            return None
        rooms = (
            self._manager.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
            .get("rooms", {})
        )
        room = rooms.get(str(rid)) or rooms.get(rid)
        if not isinstance(room, dict):
            return None
        for key in ("learned_area_m2", "area_m2"):
            try:
                val = float(room.get(key))
            except (TypeError, ValueError):
                continue
            if val > 0:
                return val
        return None

    def _record_phase_to_parent(
        self, vacuum_entity_id: str, map_id: str, active_job: dict[str, Any]
    ) -> None:
        """Attach the finishing phase to its Phased Job parent.

        A BREAK phase gets its own record here — the gap this whole design exists to
        close. A wait is not a job and must never wear the completed_job schema: it
        contributes wall-clock and nothing else, so the parent can subtract a planned
        hold from a boundary instead of teaching it as travel time.

        A CLEAN phase records ``record_id: None``, which is the truth today — the phased
        run still finalizes as ONE merged record, so no per-phase child exists to point
        at. Wave 2 splits the children and fills this in; nothing else here changes.

        Best-effort by design: the parent is review telemetry, and failing to write it
        must never stop the next phase from dispatching.
        """
        phased_job_id = str(active_job.get("phased_job_id") or "")
        if not phased_job_id:
            return
        phases = active_job.get("phases")
        if not isinstance(phases, list):
            return
        idx = _safe_int(active_job.get("current_phase_index"), 0)
        if not (0 <= idx < len(phases)) or not isinstance(phases[idx], dict):
            return
        phase = phases[idx]
        phase_type = str(phase.get("phase_type") or "")
        try:
            from ..learning.history_store import LearningHistoryStore

            store = LearningHistoryStore(self._manager.hass)
            # The parent open is best-effort, so it may not be there. Check BEFORE
            # writing a break record: written anyway, it is an orphan file referenced by
            # nothing, which no reader will ever find and no close will ever account for.
            if store.load_phased_job(
                vacuum_entity_id=vacuum_entity_id, phased_job_id=phased_job_id
            ) is None:
                _LOGGER.warning(
                    "phase %s of %s finished with no parent record -- skipping, the "
                    "parent should have been opened at run start", idx, phased_job_id,
                )
                return
            # Per-phase battery bounds (invariant 3: one child must not inherit
            # another's counters). Stamped here because this runs once per finishing
            # phase; a phase starts where the previous one ended, and phase 0 at the
            # run's own start. Unreadable stays None — never 0, which would read as a
            # flat battery and teach a phase that drained nothing as draining everything.
            from ..core.charging import get_battery_level

            _b_end = get_battery_level(self._manager.hass, vacuum_entity_id)
            phase["_battery_end"] = _b_end
            _b_start = active_job.get("battery_start")
            for j in range(idx - 1, -1, -1):
                if isinstance(phases[j], dict) and "_battery_end" in phases[j]:
                    _b_start = phases[j]["_battery_end"]
                    break
            phase["_battery_start"] = _b_start

            record_id: str | None = None
            if is_dock_polled_phase(phase):
                record_id = f"{phased_job_id}.phase{idx}"
                store.save_phase_record(
                    vacuum_entity_id=vacuum_entity_id,
                    record_id=record_id,
                    payload=self._break_record_payload(
                        phased_job_id=phased_job_id,
                        map_id=map_id,
                        active_job=active_job,
                        phases=phases,
                        idx=idx,
                        phase=phase,
                        phase_type=phase_type,
                    ),
                )
            else:
                record_id = self._finalize_phase_as_child(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                    active_job=active_job,
                    phases=phases,
                    idx=idx,
                    phase=phase,
                )
            store.record_phase_outcome(
                vacuum_entity_id=vacuum_entity_id,
                phased_job_id=phased_job_id,
                phase_index=idx,
                phase_type=phase_type,
                outcome="completed",
                record_id=record_id,
            )
        except Exception:  # noqa: BLE001 - telemetry must not block the next phase
            _LOGGER.exception(
                "could not record phase %s of %s", idx, phased_job_id
            )

    def _finalize_phase_as_child(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
        phases: list[Any],
        idx: int,
        phase: dict[str, Any],
    ) -> str | None:
        """Option B: finalize ONE clean phase as its own completed_job record.

        Returns the child's record id, or None if nothing was written.

        **Not through the chokepoint.** ``async_finalize_completed_job`` sets
        ``finalized: True`` on the stored active job under its exactly-once claim; a
        per-phase call through it would mark the whole RUN finalized at phase 0 and every
        later phase — including the real final one — would return ``already_finalized``
        and write nothing. The run-level claim keeps guarding the run; this carries its
        own per-phase idempotency (``_child_record_id``).

        **The metric scope is the hard part.** ``job_finalizer`` derives
        ``cleaning_time_seconds`` by summing ``room_timing`` across EVERY phase on the
        active job (RP-013f: a stepped run resets the device counter per phase, so for a
        MERGED record the sum is the only correct total). Split the children and that
        same code hands each one its predecessors' seconds too. Rather than teach the
        finalizer a new parameter, this narrows a COPY of the active-job state to the one
        finishing phase — the sum then scopes itself. ``last_cleaning_area_m2`` is
        overridden on the same copy, because area ACCUMULATES across phases while time
        resets (the finalizer's own comment records this), so the raw counter is the whole
        run's no matter which phase is being written.

        The copy is essential: mutating the live active job would corrupt the run.
        """
        record_id = str(phase.get("_child_record_id") or "")
        if record_id:
            return record_id  # idempotent — a re-arm must not write a second child
        try:
            # NOT `self._manager.learning` — the core manager has no such attribute; the
            # learning manager is fetched from hass.data and can legitimately be absent.
            # The first live run proved the cost: AttributeError, swallowed by the handler
            # below, both clean phases silently recording record_id: null while every test
            # passed. The tests passed because their MagicMock manufactured `.learning`
            # on demand — a mock invents whatever accessor you ask it for, including a
            # wrong one.
            learning = self._manager._get_learning_manager()
            if learning is None:
                return None
            finalizer = learning.finalizer
            ended_at = str(phase.get("_timing_end_t") or _iso_now())
            started_at = str(active_job.get("started_at") or "")
            for j in range(idx - 1, -1, -1):
                if isinstance(phases[j], dict) and phases[j].get("_timing_end_t"):
                    started_at = str(phases[j]["_timing_end_t"])
                    break

            inputs = finalizer._collect_finalization_inputs(
                manager=self._manager,
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                battery_start=_safe_int(phase.get("_battery_start"), 0),
                started_at=started_at,
                ended_at=ended_at,
            )
            scoped = dict(inputs.get("active_job_state") or {})
            scoped["phases"] = [phase]
            # Drop the JOB-CUMULATIVE completed list. RP-013c added it so a merged record
            # could still see rooms the per-phase resets had wiped — correct while ONE
            # record had to describe the whole run. A child describes one phase, and
            # known_completed_room_ids unions that list, so phase 2's child was crediting
            # itself with the kitchen phase 0 already recorded ([5, 8, 4] instead of
            # [8, 4]): the same double-count the metric scope removes, on the ROOM axis.
            # The parent unions its children, so the run-level answer is unchanged.
            scoped["completed_room_ids_cumulative"] = []
            scoped["job_id"] = f"{active_job.get('job_id') or 'job'}.phase{idx}"
            # Area for THIS phase only: the within-phase per-room deltas the capture
            # already computed. Falls back to the run counter only when the phase
            # captured nothing, which is the same "we don't know" path an atomic job
            # takes rather than a fabricated zero.
            _areas = [
                _safe_float(rt.get("cleaning_area_m2"), 0.0)
                for rt in (phase.get("room_timing") or [])
                if isinstance(rt, dict)
            ]
            if _areas:
                scoped["last_cleaning_area_m2"] = round(sum(_areas), 3)
            # The phase identity the rebuilder gates on. Presence is the signal: a child
            # carries it, an atomic run does not.
            scoped["phased_job_id"] = str(active_job.get("phased_job_id") or "")
            scoped["phase_index"] = idx
            inputs["active_job_state"] = scoped

            result = finalizer.finalize_from_inputs(
                inputs=inputs,
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                battery_start=_safe_int(phase.get("_battery_start"), 0),
                battery_end=_safe_int(phase.get("_battery_end"), 0),
                started_at=started_at,
                ended_at=ended_at,
                used_for_learning=True,
                # A stats rebuild per phase would run N times per run for identical
                # output; the run's own finalize rebuilds once at the end.
                rebuild_stats=False,
            )
            if not isinstance(result, dict) or not result.get("completed_job"):
                return None
            # Stamp the phase identity ONTO THE SAVED RECORD. Setting it on the input
            # state is not enough — the record payload is built from named fields, so an
            # unrecognised key on active_job_state is silently dropped, and the rebuilder
            # gate below would then see an ordinary job. Re-saved rather than inferred:
            # a child that cannot be told apart from a standalone run is the whole defect.
            child = result["completed_job"]
            child["phase_key"] = {
                "phased_job_id": str(active_job.get("phased_job_id") or ""),
                "phase_index": idx,
                "phase_type": str(phase.get("phase_type") or ""),
            }
            learning.store.save_completed_job(
                vacuum_entity_id=vacuum_entity_id,
                job_id=scoped["job_id"],
                payload=child,
            )
            phase["_child_record_id"] = scoped["job_id"]
            return scoped["job_id"]
        except Exception:  # noqa: BLE001 - a child that fails must not stop the next phase
            _LOGGER.exception("could not finalize phase %s as a child", idx)
            return None

    def _break_record_payload(
        self,
        *,
        phased_job_id: str,
        map_id: str,
        active_job: dict[str, Any],
        phases: list[Any],
        idx: int,
        phase: dict[str, Any],
        phase_type: str,
    ) -> dict[str, Any]:
        """Build one break record: what was PLANNED beside what actually elapsed.

        Both are kept. A charge to 80 % has no planned duration at all, and a two-minute
        wait that actually ran 125 s is a different fact from the 120 s that was asked
        for — collapsing them is what made a planned hold indistinguishable from travel.
        """
        # The break's start is the previous phase's recorded end; for phase 0 (a run that
        # opens on a wait) it is the job's own start.
        start_t = str(active_job.get("started_at") or "")
        for j in range(idx - 1, -1, -1):
            if isinstance(phases[j], dict) and phases[j].get("_timing_end_t"):
                start_t = str(phases[j]["_timing_end_t"])
                break
        end_t = str(phase.get("_timing_end_t") or _iso_now())
        seconds = _elapsed_seconds(start_t, end_t)
        planned_seconds: int | None = None
        if phase_type == "wait":
            # A1/falsy-zero: a genuine 0-minute wait is a real plan, not "unplanned".
            raw = phase.get("wait_minutes")
            if raw is not None:
                planned_seconds = int(_safe_float(raw, 0.0) * 60)
        return {
            "record_type": "phase_break",
            "record_id": f"{phased_job_id}.phase{idx}",
            "phased_job_id": phased_job_id,
            "phase_index": idx,
            "phase_type": phase_type,
            "map_id": map_id,
            "vacuum_entity_id": str(active_job.get("vacuum_entity_id") or ""),
            "planned": {
                "hold_seconds": planned_seconds,
                "target_battery_percent": (
                    _safe_int(phase.get("target_battery_percent"), 0)
                    if phase_type == "charge_wait"
                    else None
                ),
            },
            "actual": {
                "started_at": start_t,
                "ended_at": end_t,
                "seconds": seconds,
            },
        }

    def _capture_finishing_phase_timing(
        self, vacuum_entity_id: str, map_id: str, active_job: dict[str, Any]
    ) -> None:
        """Strict-order recording fix: snapshot the FINISHING phase's ``room_timing`` from ITS
        OWN counter-sample slice and stash it on the phase, so finalization can reconstruct
        per-phase timings instead of mis-attributing the whole run to the last phase's room.

        The whole-run counter stream can't be segmented across the per-room dock trips (the
        segmenter's transit capture breaks → empty ``room_timings``), so each phase is segmented
        ALONE: its slice (the samples since the previous phase ended) holds exactly one room's
        cleaning rise. Idempotent. Per-room AREA is the within-phase ``cleaning_area`` delta, with
        the room's learned area as a fallback when that delta is unusable (a stale/flat sensor
        through the phase). A phase that never cleaned (empty slice) records an EMPTY timing so the
        run reads as not-fully-captured rather than a phantom room. Timestamps are all from
        ``_iso_now()`` so a lexical compare slices correctly. Atomic jobs (no ``phases``) → no-op."""
        phases = active_job.get("phases")
        if not isinstance(phases, list):
            return
        idx = _safe_int(active_job.get("current_phase_index"), 0)
        if not (0 <= idx < len(phases)) or not isinstance(phases[idx], dict):
            return
        if phases[idx].get("_timing_end_t"):
            return  # already attempted (idempotent — an empty capture must not re-run either)

        if is_dock_polled_phase(phases[idx]):
            # A charge_wait / wait phase never cleaned (its counter slice is flat while the
            # robot charges or idles on the dock). Record an EMPTY timing so finalize reads
            # it as a dock/hold interval, not a phantom zero-metric room.
            phases[idx]["room_timing"] = []
            phases[idx]["_timing_end_t"] = _iso_now()
            return

        if str(phases[idx].get("phase_type") or "") == "zone":
            # A zone phase = one saved-zone clean. Learn it as a WALL-CLOCK total (the phase's
            # start -> now, so a mop zone's dock-prep + post-wash count as the wait), keyed later
            # by (zone_id, mop|vacuum). Area is the zone's stored footprint (Wave 0), never the
            # counter stream — cleaning_area floors ~1 m² and is useless for a small zone. The
            # empty room_timing keeps the finalizer's ROOM path from misfiling a zone as a
            # phantom room (a zone has no room id to attribute to).
            self._capture_zone_phase_timing(
                vacuum_entity_id, str(map_id), active_job, phases, idx
            )
            phases[idx]["room_timing"] = []
            phases[idx]["_timing_end_t"] = _iso_now()
            return

        now_t = _iso_now()
        # Slice from the previous phase's recorded end (None for phase 0 → from the run start).
        start_t: str | None = None
        for j in range(idx - 1, -1, -1):
            if isinstance(phases[j], dict) and phases[j].get("_timing_end_t"):
                start_t = str(phases[j]["_timing_end_t"])
                break
        samples = active_job.get("counter_samples") or []
        if start_t:
            slice_samples = [
                s for s in samples
                if isinstance(s, dict) and str(s.get("t") or "") > start_t
            ]
        else:
            slice_samples = [s for s in samples if isinstance(s, dict)]

        slug_by_id: dict[int, str | None] = {}
        for r in active_job.get("resolved_rooms") or []:
            if isinstance(r, dict):
                rid = _safe_int(r.get("room_id", r.get("id")), -1)
                if rid > 0 and rid not in slug_by_id:
                    slug_by_id[rid] = str(r.get("slug") or "").strip().lower() or None

        # Phase-scoped ids — THIS phase's own resolved_rooms, not the job's whole-run
        # queue_room_ids (phase 0 would otherwise read the entire run's queue, so the
        # credited room need not even belong to the phase being captured — RP-013b/REC-2).
        group_ids: list[int] = []
        for r in phases[idx].get("resolved_rooms") or []:
            if isinstance(r, dict):
                rid_val = _safe_int(r.get("room_id", r.get("id")), -1)
                if rid_val > 0 and rid_val not in group_ids:
                    group_ids.append(rid_val)
        # A phase that never cleaned (watchdog gave up / a stale completion signal) leaves no
        # usable counter samples — record an EMPTY timing so finalize reads the run as not-fully-
        # captured (transit_capture_valid=False, excluded from learning) instead of a phantom room
        # with a fabricated learned area. A real delta needs >= 2 samples carrying a counter.
        usable = [
            s for s in slice_samples
            if s.get("cleaning_time") is not None or s.get("cleaning_area") is not None
        ]
        room_timings = (
            self._split_group_room_timing(group_ids, slug_by_id, slice_samples)
            if group_ids and len(usable) >= 2 else []
        )
        # AREA fallback: a within-phase cleaning_area delta of ~0 (a stale/flat sensor through
        # the phase) is unusable → use the room's learned area instead.
        for rt in room_timings:
            try:
                area_ok = float(rt.get("area_m2") or 0.0) > 0.0
            except (TypeError, ValueError):
                area_ok = False
            if not area_ok:
                learned = self._learned_room_area_m2(vacuum_entity_id, map_id, rt.get("room_id"))
                if learned:
                    rt["area_m2"] = learned
                    rt["area_source"] = "learned_fallback"
        phases[idx]["room_timing"] = room_timings
        phases[idx]["_timing_end_t"] = now_t

    def _capture_zone_phase_timing(
        self,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
        phases: list[dict[str, Any]],
        idx: int,
    ) -> None:
        """Snapshot a finishing ZONE phase's wall-clock total + area onto the phase as
        ``zone_timing``, for the completed-job zone recorder to fold into learned_zones.

        Wall = the phase's start -> now. Start is the PREVIOUS phase's recorded end (the moment
        the last room finished, ~when this zone dispatched), or the run start for a leading zone.
        Using the phase boundary — not the counter slice — is deliberate: it captures the mop
        prep/wash bounces that carry no cleaning-counter rise but are real wait time. Mode is the
        job's coarse mop/vacuum bucket; area is the summed stored footprint of the step's zones."""
        now_t = _iso_now()
        start_t: str | None = None
        for j in range(idx - 1, -1, -1):
            if isinstance(phases[j], dict) and phases[j].get("_timing_end_t"):
                start_t = str(phases[j]["_timing_end_t"])
                break
        if not start_t:
            start_t = str(active_job.get("started_at") or "") or None
        wall = self._wall_seconds(start_t, now_t) if start_t else 0

        zone_ids = [str(z) for z in (phases[idx].get("zone_ids") or [])]
        meta = active_job.get("job_metadata") or {}
        clean_mode = "mop" if (isinstance(meta, dict) and meta.get("has_mop_mode")) else "vacuum"
        area = self._saved_zone_area_sum(vacuum_entity_id, map_id, zone_ids)

        phases[idx]["zone_timing"] = {
            "zone_ids": zone_ids,
            # Snapshot the names at run time so the record/review stay readable even if a zone is
            # later renamed or deleted (the learning still keys on zone_id).
            "zone_names": self._saved_zone_names(vacuum_entity_id, map_id, zone_ids),
            "clean_mode": clean_mode,
            "wall_seconds": wall,
            "area_m2": area,
            "cleaning_start": start_t,
            "cleaning_end": now_t,
        }

    def _saved_zones_for_map(self, vacuum_entity_id: str, map_id: str) -> dict[str, Any]:
        """The map's ``saved_zones`` store ({} when absent)."""
        zones = (
            self._manager.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
            .get("saved_zones", {})
        )
        return zones if isinstance(zones, dict) else {}

    def _saved_zone_area_sum(
        self, vacuum_entity_id: str, map_id: str, zone_ids: list[str]
    ) -> float | None:
        """Summed stored ``area_m2`` of the given saved zones (Wave 0 keeps it populated). None
        when no zone carries a usable size — a zone the backfill couldn't reach yet."""
        zones = self._saved_zones_for_map(vacuum_entity_id, map_id)
        total = 0.0
        seen = False
        for zid in zone_ids:
            zone = zones.get(str(zid))
            if not isinstance(zone, dict):
                continue
            try:
                area = float(zone.get("area_m2"))
            except (TypeError, ValueError):
                continue
            if area > 0:
                total += area
                seen = True
        return round(total, 2) if seen else None

    def _saved_zone_names(
        self, vacuum_entity_id: str, map_id: str, zone_ids: list[str]
    ) -> list[str]:
        """Display names for the given saved-zone ids (id itself as the fallback)."""
        zones = self._saved_zones_for_map(vacuum_entity_id, map_id)
        out: list[str] = []
        for zid in zone_ids:
            zone = zones.get(str(zid))
            name = zone.get("name") if isinstance(zone, dict) else None
            out.append(str(name) if name else str(zid))
        return out

    @staticmethod
    def _wall_seconds(t0: str, t1: str) -> int:
        """Whole seconds between two ISO timestamps (best-effort; 0 on parse failure)."""
        try:
            from datetime import datetime

            a = datetime.fromisoformat(str(t0).replace("Z", "+00:00"))
            b = datetime.fromisoformat(str(t1).replace("Z", "+00:00"))
            return int(max(0.0, (b - a).total_seconds()))
        except (ValueError, TypeError):
            return 0

    def _phase_room_timing(
        self, room_id: Any, slug: str | None, slice_samples: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """One strict-order phase = one room. Compute its timing/area directly from the phase's
        counter slice as WITHIN-slice deltas — cleaning_time / cleaning_area are CUMULATIVE across
        the run, so the per-phase figure is last − first. No segmenter: a single-room slice needs
        no segmentation, and the direct delta avoids the segmenter's cumulative-from-zero area
        accounting (which would report a later phase's cumulative total, not its own area)."""
        def _vals(key: str) -> list[float]:
            out: list[float] = []
            for s in slice_samples:
                v = s.get(key)
                if v is None:
                    continue
                try:
                    out.append(float(v))
                except (TypeError, ValueError):
                    pass
            return out

        cas = _vals("cleaning_area")
        cts = _vals("cleaning_time")
        bats = _vals("battery")
        ts = [str(s.get("t")) for s in slice_samples if s.get("t")]
        area = max(0.0, cas[-1] - cas[0]) if len(cas) >= 2 else 0.0
        secs = int(max(0.0, cts[-1] - cts[0])) if len(cts) >= 2 else 0
        bat_delta = int(bats[0] - bats[-1]) if len(bats) >= 2 else None
        wall = self._wall_seconds(ts[0], ts[-1]) if len(ts) >= 2 else secs
        return {
            "room_id": room_id,
            "slug": slug,
            "cleaning_start": ts[0] if ts else None,
            "cleaning_end": ts[-1] if ts else None,
            "cleaning_seconds": secs,
            "cleaning_wall_seconds": wall,
            "area_m2": round(area, 3),
            "battery_delta": bat_delta,
            "boundary": "phase",
            "allocated": False,
        }

    def _split_group_room_timing(
        self,
        group_ids: list[int],
        slug_by_id: dict[int, str | None],
        slice_samples: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """One timing entry PER room in a group phase.

        A single-room group is the exact, unapportioned case (RP-013b:
        ``_phase_room_timing`` directly, ``allocated=False``). A multi-room group's
        measured cleaning_seconds / area_m2 / battery_delta are the WHOLE group's —
        no per-room boundary exists inside a strict-order-off batch dispatch, so
        fabricating one is forbidden (killed-premise guard). They are instead split
        evenly across members with ``allocated=True`` and ``allocation_group_size``
        recorded, using an exact-sum-preserving distribution so the group's measured
        totals are neither lost nor duplicated (RP-013f's phase-sum derivation
        depends on this). cleaning_start/cleaning_end/cleaning_wall_seconds are
        shared verbatim across members — the whole group was in progress for the
        same wall-clock span; only the apportionable resource fields are split."""
        n = len(group_ids)
        if n == 1:
            rid = group_ids[0]
            return [self._phase_room_timing(rid, slug_by_id.get(rid), slice_samples)]

        whole = self._phase_room_timing(None, None, slice_samples)
        secs_parts = _distribute_int(int(whole["cleaning_seconds"]), n)
        area_milli_total = round(float(whole["area_m2"]) * 1000)
        area_parts = [p / 1000 for p in _distribute_int(area_milli_total, n)]
        bat_total = whole.get("battery_delta")
        bat_parts = (
            _distribute_int(int(bat_total), n) if bat_total is not None else [None] * n
        )

        return [
            {
                "room_id": rid,
                "slug": slug_by_id.get(rid),
                "cleaning_start": whole["cleaning_start"],
                "cleaning_end": whole["cleaning_end"],
                "cleaning_seconds": secs_parts[i],
                "cleaning_wall_seconds": whole["cleaning_wall_seconds"],
                "area_m2": round(area_parts[i], 3),
                "battery_delta": bat_parts[i],
                "boundary": "phase",
                "allocated": True,
                "allocation_group_size": n,
            }
            for i, rid in enumerate(group_ids)
        ]

    def _phase_target_is_dock_room(
        self, vacuum_entity_id: str, map_id: str, room_id: int | str | None
    ) -> bool:
        """True when ``room_id`` is the room the charging dock physically sits in
        (the map's per-room is_dock_room flag). Used to extend the post-dock settle
        for a dock-room strict-order phase. Safe on missing data → False."""
        if room_id in (None, ""):
            return False
        rooms = (
            self._manager.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
            .get("rooms", {})
        )
        room = rooms.get(str(room_id))
        if room is None:
            room = rooms.get(room_id)
        return bool(isinstance(room, dict) and room.get("is_dock_room", False))

    async def _run_advanced_phase(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        phase_index: int,
        initial: bool = False,
    ) -> None:
        """Dispatch/confirm a sequenced phase: settle, send, verify, retry.

        ADVANCED phase: a path-optimizing device (Roborock S6) returns to the dock
        + starts charging at the end of each single-room phase and ignores an
        app_segment_clean sent at that instant — so we settle, send the room,
        verify it actually started THIS room, and re-send if not. When the target
        IS the dock room (the robot is parked + charging right on it) the settle is
        extended (_PHASE_DOCK_SETTLE_SECONDS) so the longer ignore-transient passes
        before the first dispatch.

        INITIAL phase (``initial=True``): phase 0 was already dispatched by
        start_selected_rooms, so we skip the settle and the first dispatch and just
        VERIFY, then clear the dispatch-pending guard. The device may sit parked on
        the dock at start (its current_room == the dock room, which can itself be a
        target), so until it is confirmed ACTUALLY cleaning room 0 the completion
        gate must not finalize it. A retry re-dispatches only if it ignored the
        initial send.

        Either way the retry cap is the per-phase watchdog — after it the run is
        left stalled (recoverable via Cancel Run) rather than silently hung.
        """
        try:
            pt = self._manager._phase_timing(vacuum_entity_id)
            # A fresh watchdog attempt (a normal advance, or a restart/resume
            # re-arm) starts with a clean liveness slate -- a stale dead-flag
            # from a PREVIOUS crashed watchdog on this same phase must not
            # immediately exclude the reaper again before this attempt even runs.
            self._reset_phase_watchdog_liveness(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index,
            )
            if not initial:
                job0 = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
                settle = pt["settle_seconds"]
                if self._phase_target_is_dock_room(
                    vacuum_entity_id, map_id, (job0 or {}).get("current_room_id")
                ):
                    settle = pt["dock_settle_seconds"]
                    _LOGGER.info(
                        "Strict-order: phase %s on %s targets the dock room — extending "
                        "the post-dock settle to %ss before dispatch so the device's "
                        "ignore-transient passes.",
                        phase_index, vacuum_entity_id, settle,
                    )
                await asyncio.sleep(settle)
            for attempt in range(1, pt["max_attempts"] + 1):
                job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
                # The job advanced past this phase, finalized, paused (status flips), or is
                # being cancelled — async_cancel sets _cancel_in_flight up front, BEFORE the
                # status flips, so the watchdog stops before it can re-dispatch during the
                # return-to-base window. In every case the phase is no longer ours, so bail.
                # NOT a watchdog failure — no liveness marking (a different/no phase now
                # owns _phase_dispatch_pending; marking here would poison it).
                if (
                    not job
                    or job.get("status") != "started"
                    or int(job.get("current_phase_index", -1)) != phase_index
                    or job.get("_cancel_in_flight")
                ):
                    _LOGGER.info(
                        "Strict-order: phase %s on %s not (re)dispatched — the job is no "
                        "longer on this phase (status=%s, phase=%s); it finalized, "
                        "advanced, was cancelled, or the guard was released.",
                        phase_index, vacuum_entity_id,
                        (job or {}).get("status"), (job or {}).get("current_phase_index"),
                    )
                    return
                # The initial phase's first send already happened at job start — just
                # verify it; a re-dispatch only happens on a retry (device ignored it).
                if not (initial and attempt == 1):
                    try:
                        await self._dispatch_active_phase(
                            vacuum_entity_id=vacuum_entity_id, map_id=map_id, job=job, attempt=attempt
                        )
                    except HomeAssistantError as err:
                        # RP-007 step 6: a live-resolution REFUSAL (the room no longer
                        # exists on the current map, or freshness could not be
                        # established) is not a transient — retrying the same phase
                        # cannot succeed. Log, record the skip on the stored job
                        # (cumulative evidence for RF-11), release the guard and
                        # advance to the next phase instead of wedging the run.
                        _LOGGER.warning(
                            "Strict-order: phase %s on %s refused by live resolution "
                            "(%s); marking its room(s) skipped and advancing",
                            phase_index, vacuum_entity_id, err,
                        )
                        _stored = (
                            self._manager.data.get("active_jobs", {})
                            .get(vacuum_entity_id, {})
                            .get(str(map_id))
                        )
                        if isinstance(_stored, dict):
                            skipped = _stored.setdefault("skipped_rooms", [])
                            for _rid in (job.get("phases", [])[phase_index].get("queue_room_ids", [])
                                         if 0 <= phase_index < len(job.get("phases", [])) else []):
                                entry = {"room_id": _rid, "phase_index": phase_index,
                                         "reason": "live_resolution_refused",
                                         "at": utc_now_iso()}
                                if entry not in skipped:
                                    skipped.append(entry)
                        self._clear_phase_dispatch_pending(
                            vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index
                        )
                        await self.maybe_advance_phase(
                            vacuum_entity_id=vacuum_entity_id, map_id=map_id
                        )
                        return
                if await self._await_phase_started(
                    vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index
                ):
                    # Confirmed the device started THIS room — clear the dispatch-pending
                    # guard so its real completion can finalize/advance normally.
                    self._clear_phase_dispatch_pending(
                        vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index
                    )
                    return  # the target room actually started — phase under way
                if attempt < pt["max_attempts"]:
                    _LOGGER.warning(
                        "Strict-order: phase %s on %s hadn't started %ss after dispatch; "
                        "retrying (%s/%s)",
                        phase_index, vacuum_entity_id, pt["verify_seconds"],
                        attempt + 1, pt["max_attempts"],
                    )
            # RP-011/RF-07 (WD-2): every attempt exhausted without confirming — the
            # watchdog is giving up. Convert _phase_dispatch_pending from an
            # unconditional reaper exclusion into a DEAD one: stamp the liveness
            # fields instead of clearing pending (the phase may still start late;
            # clearing would let the completion gate advance on a half-dispatched
            # phase).
            _LOGGER.warning(
                "Strict-order: phase %s on %s failed to start after %s attempts; run "
                "stalled — Cancel Run to recover",
                phase_index, vacuum_entity_id, pt["max_attempts"],
            )
            self._mark_phase_watchdog_dead(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index,
            )
        except Exception:  # noqa: BLE001 - a crashed watchdog must be REAPABLE, not
            # silently dead and invisible (WD-1). Logged with the phase context so
            # it is diagnosable, then marked dead the same as an exhausted retry.
            _LOGGER.exception(
                "Strict-order: phase %s on %s watchdog crashed unexpectedly",
                phase_index, vacuum_entity_id,
            )
            self._mark_phase_watchdog_dead(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index,
            )

    def _mark_phase_watchdog_dead(
        self, *, vacuum_entity_id: str, map_id: str, phase_index: int
    ) -> None:
        """Stamp the liveness fields the reaper consults (RP-011/RF-07: WD-2/STR-3)
        so a dead watchdog's phase becomes reapable without clearing
        _phase_dispatch_pending itself -- the phase may still start late; only the
        reaper's exclusion should lift, not the completion gate's."""
        stored = (
            self._manager.data.get("active_jobs", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id))
        )
        if not isinstance(stored, dict) or int(stored.get("current_phase_index", -1)) != phase_index:
            return  # the job moved on -- this watchdog's phase is no longer current
        stored["_phase_watchdog_dead"] = True
        stored.setdefault("_phase_dispatch_pending_since", _iso_now())

    def _reset_phase_watchdog_liveness(
        self, *, vacuum_entity_id: str, map_id: str, phase_index: int
    ) -> None:
        """Clear any liveness marking left by a PREVIOUS crashed/exhausted
        watchdog on this phase before a fresh attempt begins (normal advance or
        a restart/resume re-arm) -- a stale dead-flag must not immediately
        exclude the reaper again before this new attempt even runs."""
        stored = (
            self._manager.data.get("active_jobs", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id))
        )
        if not isinstance(stored, dict) or int(stored.get("current_phase_index", -1)) != phase_index:
            return
        stored.pop("_phase_watchdog_dead", None)
        stored.pop("_phase_dispatch_pending_since", None)

    async def _run_charge_wait_phase(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        phase_index: int,
    ) -> None:
        """Drive a ``charge_wait`` phase: dock, wait until battery >= target, advance.

        A charge_wait phase has no rooms — its "work" is parking on the dock and
        charging, so no room-finish event can advance it; THIS coroutine owns its
        lifecycle. It keeps ``_phase_dispatch_pending`` set (which the completion gate
        already honours — the same guard that stops a Roborock's between-phase dock
        from finalizing), so the intentional charge-dock is never read as a
        cancel/completion, then advances via ``maybe_advance_phase`` once the target
        is reached.

        - Already at/above target on entry -> advance immediately (no charge).
        - Timeout (``charge_wait_timeout_minutes``, default 180) -> finalize like a
          cancel, so the un-cleaned remaining rooms are reported missed.
        - A genuine user Cancel (``_cancel_in_flight``), pause, or advance -> bail;
          the phase is no longer ours.

        The ``_dock_poller_active`` guard (set by ``_spawn_dock_poller``) is released in the
        finally so a later re-arm can spawn a fresh poller once this one has exited.
        """
        try:
            await self._run_charge_wait_phase_impl(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index
            )
        finally:
            self._dock_poller_active.discard(
                (vacuum_entity_id, str(map_id), int(phase_index))
            )

    async def _run_charge_wait_phase_impl(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        phase_index: int,
    ) -> None:
        """Body of ``_run_charge_wait_phase`` (poller-guard release lives in the wrapper)."""
        from ..core.charging import get_battery_level

        poll_s = 30.0  # battery updates are slow; adapter-tunable later via dispatch.charge

        def _still_ours(job: dict[str, Any] | None) -> bool:
            return bool(
                job
                and job.get("status") == "started"
                and _safe_int(job.get("current_phase_index"), -1) == phase_index
                and not job.get("_cancel_in_flight")
            )

        job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if not _still_ours(job):
            return
        phases = job.get("phases") or []
        phase = (
            phases[phase_index]
            if 0 <= phase_index < len(phases) and isinstance(phases[phase_index], dict)
            else {}
        )
        target = _safe_int(phase.get("target_battery_percent"), 100)
        timeout_min = _safe_int(phase.get("charge_wait_timeout_minutes"), 180)

        # Already charged enough -> skip the charge entirely, keep going.
        # RP-042 pre-guard: once get_battery_level can return None for a genuinely
        # unreadable battery, an unguarded `None >= int` raises TypeError and wedges the
        # job mid-charge. `is not None and` (NOT `is None or`) is the safe direction —
        # unreadable must mean "keep waiting", never "charged enough, skip the charge".
        # Waiting cannot hang: the poll loop below carries its own timeout.
        _level = get_battery_level(self._manager.hass, vacuum_entity_id)
        if _level is not None and _level >= target:
            _LOGGER.info(
                "Charge-wait phase %s on %s: battery already >= %s%% — advancing without charging.",
                phase_index, vacuum_entity_id, target,
            )
            await self.maybe_advance_phase(vacuum_entity_id=vacuum_entity_id, map_id=str(map_id))
            return

        # Record the charge start on the phase (Wave 4 observability): the from-battery
        # + when, so the live snapshot shows the full "X% -> target%" picture and the
        # finalized run reflects the charge. The RATE learning itself is passive — the
        # battery-health manager already tracks this charge as a session.
        _rec = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        _recp = (_rec or {}).get("phases") or []
        if 0 <= phase_index < len(_recp) and isinstance(_recp[phase_index], dict):
            _recp[phase_index]["charge_from_battery"] = get_battery_level(
                self._manager.hass, vacuum_entity_id
            )
            _recp[phase_index]["charge_started_at"] = _iso_now()
            self._manager.data.setdefault("active_jobs", {}).setdefault(
                vacuum_entity_id, {})[str(map_id)] = _rec

        # Send it home to charge (a no-op if it is already docked + charging).
        await self._manager.hass.services.async_call(
            "vacuum", "return_to_base", {"entity_id": vacuum_entity_id}, blocking=True,
        )
        _LOGGER.info(
            "Charge-wait phase %s on %s: charging to %s%% (timeout %sm, poll %ss).",
            phase_index, vacuum_entity_id, target, timeout_min, poll_s,
        )

        deadline = self._manager.hass.loop.time() + timeout_min * 60.0
        while True:
            await asyncio.sleep(poll_s)
            job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            if not _still_ours(job):
                _LOGGER.info(
                    "Charge-wait phase %s on %s abandoned — no longer on this phase "
                    "(cancel/pause/advance).",
                    phase_index, vacuum_entity_id,
                )
                return
            # RP-042 pre-guard, same direction as the skip check above: an unreadable
            # battery keeps polling until the deadline below, rather than breaking out
            # of the charge as though the target had been reached.
            _poll_level = get_battery_level(self._manager.hass, vacuum_entity_id)
            if _poll_level is not None and _poll_level >= target:
                break
            if self._manager.hass.loop.time() >= deadline:
                _LOGGER.warning(
                    "Charge-wait phase %s on %s timed out after %sm below %s%% — finalizing "
                    "as cancelled; remaining rooms reported missed.",
                    phase_index, vacuum_entity_id, timeout_min, target,
                )
                await self._manager.active_job.async_cancel_active_job(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    cancel_reason="charge_timeout",
                    forced_lifecycle_state="charge_timeout",
                    forced_lifecycle_message=(
                        f"Charging to {target}% timed out after {timeout_min} min; "
                        "remaining rooms were not cleaned."
                    ),
                )
                return
        _rec2 = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        _recp2 = (_rec2 or {}).get("phases") or []
        if 0 <= phase_index < len(_recp2) and isinstance(_recp2[phase_index], dict):
            _recp2[phase_index]["charge_to_battery"] = get_battery_level(
                self._manager.hass, vacuum_entity_id
            )
            _recp2[phase_index]["charge_ended_at"] = _iso_now()
            self._manager.data.setdefault("active_jobs", {}).setdefault(
                vacuum_entity_id, {})[str(map_id)] = _rec2
        _LOGGER.info(
            "Charge-wait phase %s on %s reached %s%% — advancing to the next phase.",
            phase_index, vacuum_entity_id, target,
        )
        await self.maybe_advance_phase(vacuum_entity_id=vacuum_entity_id, map_id=str(map_id))

    async def _run_wait_phase(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        phase_index: int,
    ) -> None:
        """Drive a ``wait`` phase: dock and hold for ``wait_minutes``, then advance.

        The time-based twin of ``_run_charge_wait_phase`` (e.g. a mop-dry pause between a
        vacuum pass and a mop pass). Like charge it has no rooms and owns its own lifecycle;
        it KEEPS ``_phase_dispatch_pending`` set (inherited from the advance, never cleared)
        so the intentional idle dock is not read as a cancel/completion, then advances via
        ``maybe_advance_phase`` once the time has elapsed. A genuine user Cancel / pause /
        advance (status flip or ``_cancel_in_flight``) bails — the phase is no longer ours.

        The ``_dock_poller_active`` guard (set by ``_spawn_dock_poller``) is released in the
        finally so a later re-arm can spawn a fresh poller once this one has exited.
        """
        try:
            await self._run_wait_phase_impl(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id, phase_index=phase_index
            )
        finally:
            self._dock_poller_active.discard(
                (vacuum_entity_id, str(map_id), int(phase_index))
            )

    async def _run_wait_phase_impl(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        phase_index: int,
    ) -> None:
        """Body of ``_run_wait_phase`` (poller-guard release lives in the wrapper)."""
        poll_s = 15.0  # time-bound; poll tight enough that the live countdown feels current

        def _still_ours(job: dict[str, Any] | None) -> bool:
            return bool(
                job
                and job.get("status") == "started"
                and _safe_int(job.get("current_phase_index"), -1) == phase_index
                and not job.get("_cancel_in_flight")
            )

        job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if not _still_ours(job):
            return
        phases = job.get("phases") or []
        phase = (
            phases[phase_index]
            if 0 <= phase_index < len(phases) and isinstance(phases[phase_index], dict)
            else {}
        )
        wait_minutes = max(1, _safe_int(phase.get("wait_minutes"), 5))

        # Record the wait start so the live snapshot can count down "~N min left".
        # A re-arm after an HA restart mid-wait (rearm_dock_phase_if_needed) finds
        # wait_started_at ALREADY persisted — keep it, so the deadline is recomputed
        # from the ORIGINAL start below and the timer isn't restarted from full.
        _rec = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        _recp = (_rec or {}).get("phases") or []
        _persisted_started_at = (
            str(_recp[phase_index].get("wait_started_at") or "").strip()
            if 0 <= phase_index < len(_recp) and isinstance(_recp[phase_index], dict)
            else ""
        )
        if 0 <= phase_index < len(_recp) and isinstance(_recp[phase_index], dict):
            if not _persisted_started_at:
                _recp[phase_index]["wait_started_at"] = _iso_now()
                self._manager.data.setdefault("active_jobs", {}).setdefault(
                    vacuum_entity_id, {})[str(map_id)] = _rec

        # Park on the dock while waiting (a no-op if it is already docked).
        await self._manager.hass.services.async_call(
            "vacuum", "return_to_base", {"entity_id": vacuum_entity_id}, blocking=True,
        )
        _LOGGER.info(
            "Wait phase %s on %s: holding for %s min (poll %ss).",
            phase_index, vacuum_entity_id, wait_minutes, poll_s,
        )

        # Fresh start -> full window. Re-arm mid-wait (wait_started_at already persisted)
        # -> subtract the elapsed wall time so a restart doesn't restart the full timer;
        # an already-elapsed wait clamps to 0 (advances on the first poll).
        remaining_s = wait_minutes * 60.0
        if _persisted_started_at:
            _elapsed = self._wall_seconds(_persisted_started_at, _iso_now())
            remaining_s = max(0.0, wait_minutes * 60.0 - _elapsed)
        deadline = self._manager.hass.loop.time() + remaining_s
        while True:
            await asyncio.sleep(poll_s)
            job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            if not _still_ours(job):
                _LOGGER.info(
                    "Wait phase %s on %s abandoned — no longer on this phase "
                    "(cancel/pause/advance).",
                    phase_index, vacuum_entity_id,
                )
                return
            if self._manager.hass.loop.time() >= deadline:
                break
        _rec2 = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        _recp2 = (_rec2 or {}).get("phases") or []
        if 0 <= phase_index < len(_recp2) and isinstance(_recp2[phase_index], dict):
            _recp2[phase_index]["wait_ended_at"] = _iso_now()
            self._manager.data.setdefault("active_jobs", {}).setdefault(
                vacuum_entity_id, {})[str(map_id)] = _rec2
        _LOGGER.info(
            "Wait phase %s on %s: %s min elapsed — advancing to the next phase.",
            phase_index, vacuum_entity_id, wait_minutes,
        )
        await self.maybe_advance_phase(vacuum_entity_id=vacuum_entity_id, map_id=str(map_id))

    def _clear_phase_dispatch_pending(
        self, *, vacuum_entity_id: str, map_id: str, phase_index: int
    ) -> None:
        """Clear the dispatch-pending guard once the watchdog has confirmed this
        phase's room actually started, so its real completion can finalize/advance.
        Only clears when the job is still on this exact phase — a later advance owns
        its own pending flag. Writes straight to the stored record + best-effort save."""
        job = (
            self._manager.data.get("active_jobs", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id))
        )
        if (
            isinstance(job, dict)
            and job.get("status") == "started"
            and int(job.get("current_phase_index", -1)) == phase_index
            and job.get("_phase_dispatch_pending")
        ):
            job["_phase_dispatch_pending"] = False
            # RP-011/RF-07: a confirmed start proves the watchdog was alive after
            # all -- drop any liveness marking so it doesn't leak into whatever
            # phase runs next.
            job.pop("_phase_watchdog_dead", None)
            job.pop("_phase_dispatch_pending_since", None)
            self._manager.hass.async_create_task(self._manager._async_save_logged())

    async def _await_phase_started(
        self, *, vacuum_entity_id: str, map_id: str, phase_index: int
    ) -> bool:
        """Poll for the device to actually start — and stay on — THIS phase's TARGET
        room. True once it has been observed cleaning the target for
        _PHASE_CONFIRM_SECONDS cumulative (or if the phase advanced/finalized
        meanwhile); False once it has gone _PHASE_VERIFY_SECONDS with NO observed
        cleaning of the target — it ignored the dispatch / is still docked / is still
        finishing the previous room — which triggers a re-dispatch.

        The previous check ("is the vacuum cleaning at all" / the job-active binary)
        false-passed: the device's inCleaning flag stays on across the whole job, so
        a clean it IGNORED at the dock looked like success and the watchdog never
        retried (only ~1 room in 4 actually fired). The strong signal is the brand's
        NATIVE current-room matching the phase's target while actually cleaning,
        SUSTAINED:

          - vacuum.state == cleaning rules out the docked-in-the-target-room case
            (when the dock physically sits in a target room the device reports
            current_room == that room whenever parked).
          - We accumulate cleaning-of-the-target seconds rather than confirm on a
            single sample, because the live current-room signal dips in and out — a
            dip just doesn't add to the tally (we don't require strict continuity).
          - We bound an attempt by NO-PROGRESS time (idle), not a fixed overall
            window: a long cross-room transit merely delays when the tally starts,
            so it can't falsely fail a device that is genuinely on its way, while a
            device that never reaches the room accrues idle and retries promptly.

        Brands with no native current-room signal fall back to the coarse cleaning
        check (immediate, unchanged)."""
        # RP-011/RF-07 (WD-3): has_native gates on the SAME
        # live_transition.native_transition_source flag active_job.py already
        # trusts (:951) -- not on whether active_cleaning_target is merely
        # DECLARED. Both Eufy and Roborock declare that entity, but only
        # Roborock's is a genuinely native per-room signal (native_transition_
        # source=True); Eufy's declares False, so the always-truthy entity-id
        # check previously routed Eufy through the strong-confirmation path too,
        # making the coarse fallback below unreachable for it.
        has_native = bool(
            self._manager.active_job._live_transition_config(
                vacuum_entity_id
            ).get("native_transition_source")
        )
        pt = self._manager._phase_timing(vacuum_entity_id)
        _poll = float(pt["poll_seconds"])
        cleaning_in_target = 0.0  # cumulative seconds observed cleaning the target
        idle = 0.0                # consecutive seconds with NO cleaning of the target
        while True:
            job = self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            # Phase advanced / finalized / paused, or a cancel is in flight
            # (_cancel_in_flight set up front) — nothing to retry.
            if (
                not job
                or job.get("status") != "started"
                or int(job.get("current_phase_index", -1)) != phase_index
                or job.get("_cancel_in_flight")
            ):
                return True
            # A ZONE phase has NO target room, so the native current-room match below can
            # never confirm it (target current_room_id is None) — the guard would never clear
            # and the completed job would lock ACTIVE. Confirm a zone on SUSTAINED
            # vacuum.state==cleaning instead: the zone clean makes the device report cleaning,
            # and between phases it is docked/washing, so this only fires once the zone truly
            # starts. (Not the job-active binary — that stays on across the job and false-passes.)
            _phases = job.get("phases") or []
            _pidx = _safe_int(job.get("current_phase_index"), -1)
            _cur_phase = _phases[_pidx] if 0 <= _pidx < len(_phases) else {}
            if str(_cur_phase.get("phase_type") or "") == "zone":
                st = self._manager.hass.states.get(vacuum_entity_id)
                if st is not None and str(st.state).strip().lower() == "cleaning":
                    cleaning_in_target += _poll
                    if cleaning_in_target >= pt["confirm_seconds"]:
                        return True
                    idle = 0.0
                else:
                    idle += _poll
                if idle >= pt["verify_seconds"]:
                    # Small zone that finished within confirm_seconds -> treat as confirmed;
                    # a true no-show (never cleaned) -> False to retry.
                    return cleaning_in_target > 0
                await asyncio.sleep(_poll)
                continue
            progressed = False
            if has_native:
                target = job.get("current_room_id")
                signal = self._manager.active_job.native_current_room_target_id(
                    vacuum_entity_id, job
                )
                st = self._manager.hass.states.get(vacuum_entity_id)
                is_cleaning = (
                    st is not None and str(st.state).strip().lower() == "cleaning"
                )
                if (
                    is_cleaning
                    and signal is not None
                    and target is not None
                    and signal == target
                ):
                    cleaning_in_target += _poll
                    if cleaning_in_target >= pt["confirm_seconds"]:
                        return True
                    progressed = True
            elif self._vacuum_started_cleaning(vacuum_entity_id):
                return True
            # Reset the no-progress budget whenever we saw cleaning-of-the-target;
            # otherwise accrue it and give up the attempt (re-dispatch) once the
            # device has gone the whole budget without touching the target room.
            idle = 0.0 if progressed else idle + _poll
            if idle >= pt["verify_seconds"]:
                # No progress for the whole budget. If we DID observe genuine cleaning
                # of the target at some point (cleaning_in_target only accrues while
                # vacuum.state==cleaning AND the native current_room==target — a parked
                # robot can't accrue it), the device started this room and has since
                # finished/docked: a small room that completes in under confirm_seconds.
                # Treat that as confirmed, NOT a no-show — re-dispatching an already-
                # cleaned room is ignored by the device, which would leave the phase
                # stalled forever (_phase_dispatch_pending never clears). Only a true
                # no-show (never cleaned the target) returns False to retry.
                return cleaning_in_target > 0
            await asyncio.sleep(_poll)

    async def _dispatch_active_phase(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        job: dict[str, Any],
        attempt: int = 1,
    ) -> None:
        """Apply this phase's per-room live settings (fan) then dispatch its segment.

        Fan is set BEFORE the dispatch so the room starts at its own value with no
        current_room poll lag. Segment ids are live-resolved by slug per phase so a
        re-segment between rooms can't clean the wrong room (no-op without
        dispatch.resolve_live_ids_by_slug). Per-room passes already ride the phase
        payload.

        GLOBAL pre-calls (e.g. Roborock mop intensity, a device-global select) are
        re-run PER PHASE from THIS phase's own rooms, so a vacuum group then a mop
        group each apply their own water setting — the phase-0 pre-call fires in
        start_selected_rooms, phases 1+ fire here. No-op when the adapter declares no
        dispatch.global_pre_calls (Eufy, S6).
        """
        # A zone phase cleans saved-zone rects, not room segments: dispatch via the zone
        # path (its own per-brand coordinate conversion + caps live in dispatch_zone_clean)
        # and skip the room pre-calls / per-room settings / segment payload entirely.
        _phases = job.get("phases") or []
        _idx = _safe_int(job.get("current_phase_index"), 0)
        _phase = _phases[_idx] if 0 <= _idx < len(_phases) else {}
        if str(_phase.get("phase_type") or "") == "zone":
            zones = _phase.get("zones") or []
            if zones:
                await self._manager.dispatch_zone_clean(
                    vacuum_entity_id=vacuum_entity_id, zones=zones, map_id=str(map_id),
                )
            _LOGGER.info(
                "Strict-order advance: %s map %s -> zone phase %s/%s, %d zone(s) (attempt %s)",
                vacuum_entity_id, map_id,
                job.get("current_phase_index"), job.get("phase_count"),
                len(zones), attempt,
            )
            return

        await self._manager._run_global_pre_calls(
            vacuum_entity_id=vacuum_entity_id,
            resolved_rooms=list(job.get("resolved_rooms", [])),
        )
        await self._manager.active_job.apply_per_room_live_settings_awaited(
            vacuum_entity_id,
            list(job.get("resolved_rooms", [])),
            job.get("current_room_id"),
        )
        wire_payload = await self._manager._resolve_live_dispatch_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            payload=job.get("payload", {}),
            resolved_rooms=list(job.get("resolved_rooms", [])),
        )

        # RP-010/RF-06: the chokepoint. Four sequential awaits sit between the
        # top-of-attempt check and the wire send with no re-read in between — a
        # cancel/pause landing anywhere in that window still reached the send.
        # Re-read the STORED job (not the `job` parameter, which is this attempt's
        # stale snapshot) immediately before the send, after the last await.
        _stored = (
            self._manager.data.get("active_jobs", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id))
        )
        if not isinstance(_stored, dict) or _stored.get("_cancel_in_flight") or _stored.get("status") != "started":
            _LOGGER.info(
                "Strict-order advance: %s map %s -> dispatch aborted at the "
                "chokepoint (cancelled or no longer started, attempt %s)",
                vacuum_entity_id, map_id, attempt,
            )
            return

        await self._manager._dispatch_clean_payload(
            vacuum_entity_id=vacuum_entity_id, payload=wire_payload
        )
        # INFO so a strict-order run is diagnosable without enabling debug: shows
        # the exact payload re-dispatched (an empty segment list = the next room
        # was skipped, e.g. a slug that didn't resolve to a live id) + the attempt.
        _LOGGER.info(
            "Strict-order advance: %s map %s -> phase %s/%s, re-dispatched %s (attempt %s)",
            vacuum_entity_id, map_id,
            job.get("current_phase_index"), job.get("phase_count"),
            wire_payload, attempt,
        )

    def _vacuum_started_cleaning(self, vacuum_entity_id: str) -> bool:
        """Whether the vacuum is in an active cleaning session (a dispatch took).

        True when the vacuum entity reports ``cleaning`` OR the adapter's job-active
        binary (entities.job_active — the device 'inCleaning' flag) is on. Used to
        verify a re-dispatched phase actually started before retrying.
        """
        st = self._manager.hass.states.get(vacuum_entity_id)
        if st is not None and str(st.state).strip().lower() == "cleaning":
            return True
        job_active_entity = (
            (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {})
            .get("job_active")
        )
        if job_active_entity:
            js = self._manager.hass.states.get(job_active_entity)
            if js is not None and str(js.state).strip().lower() == "on":
                return True
        return False
