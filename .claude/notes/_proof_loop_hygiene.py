"""Proof RP-037 (RF-29) -- event-loop hygiene across all 7 non-mkdir finding_ids.

The packet's reproducer_script names two things. The mkdir half ("32 mkdir calls per
snapshot" -> "0 mkdir on warm path") is driven by `_proof_ensure_dirs_memo.py`. This
file drives the other seven finding_ids as one case each:

  1. SNAP-2 (case_read_path_fires_and_persists / case_progress_composed_twice) --
     get_job_progress_snapshot used to mutate + fire events as a read-path side
     effect, and get_dashboard_snapshot composed it twice per poll.
  2. ROBORO-2 (case_roboro2_diagnostics_dispatch_via_executor) -- the diagnostics
     dump's plain-sync, CPU-heavy _vacuum_diagnostics ran directly on the event loop;
     it must be dispatched via hass.async_add_executor_job.
  3. GEO-2 (case_geo2_zone_membership_bbox_reject_before_loop) -- zone_membership's
     per-cell ray-cast loop iterated the WHOLE raster regardless of how small the
     zone's own bbox was; the bbox must be inverted into raster index bounds BEFORE
     the loop.
  4. ONB-5 (case_onb5_onboarding_sensor_summary_cached_per_cycle) --
     native_value/extra_state_attributes each independently recomputed the
     onboarding summary; one poll cycle must cost exactly one summary lookup.
  5. DRAFT-5 (case_draft5_storage_debounces_rapid_saves /
     case_draft5_service_handler_uses_debounce) -- handle_update_working_draft did
     one full immediate Store.async_save() per draft edit; rapid edits must
     coalesce into one write via HA's own Store.async_delay_save.
  6. TRK-7 (case_trk7_lifecycle_start_job_not_dispatched_via_executor) --
     listeners/lifecycle.py wrapped the now-I/O-free tracker.start_job in
     hass.async_add_executor_job based on a stale disk-I/O comment.

Each case either drives the REAL production function and asserts on call counts (GEO-2,
ONB-5, DRAFT-5's storage half), or reads the CURRENT source rather than asserting
against copied line numbers (ROBORO-2, TRK-7, DRAFT-5's service-handler half, and the
pre-existing case_progress_composed_twice) -- the same technique
`_proof_blocker_unavailable.py` uses, so it cannot quietly pass after a refactor moves
the calls.

RP-037 is marked `blocked_by RP-013c`. That block cleared when RP-013c landed
(0ff4a8a) -- the dependency was on RP-013's progress-path changes, which are now in.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_loop_hygiene.py
"""

from __future__ import annotations

import base64
import inspect
import re
import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.core import manager as manager_mod   # noqa: E402
from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker   # noqa: E402


# ---------------------------------------------------------------------------
# 1. SNAP-2 (pre-existing, unchanged)
# ---------------------------------------------------------------------------

def case_read_path_fires_and_persists(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)

    # A job whose current room is well past its timing estimate and whose rollover is
    # blocked by the bounds gate — the exact live condition a stall describes.
    job = H.active_job(queue_room_ids=[5], current_room_id=5, status="started")
    mgr.data.setdefault("active_jobs", {}).setdefault(H.VAC, {})[str(H.MAP)] = job

    tracker = ActiveJobTracker(mgr)
    result = tracker.detect_run_anomalies(
        vacuum_entity_id=H.VAC, map_id=H.MAP, active_job=job,
        # minutes=2.0 with low confidence -> threshold ~2.4 min; 30 min elapsed is
        # far past threshold * stall_ratio (2.0), so the stall branch is entered.
        raw_timeline=[{"room_id": 5, "minutes": 2.0, "confidence_score": 0.3,
                       "sample_count": 4}],
        current_room_id=5,
        current_room_elapsed_minutes=30.0,
        completed_room_ids=[],
        awaiting_bounds_exit=True,
    )

    fired = list(hass.bus.events)
    persisted = mgr.data["active_jobs"][H.VAC][str(H.MAP)].get("_stall_notified_room_ids")

    proof.case(
        "one card poll over a stalled room — a pure read by contract",
        before=bool(fired) and bool(persisted),
        before_msg="events fired from the read path, and the read wrote state — "
                   "whether an automation ever sees a stall depends on whether a card "
                   "was open and polling, and the card's poll CONSUMES the "
                   "once-per-room event",
        after=not fired and not persisted,
        after_msg="the snapshot is a pure read; the anomaly emit + notified-room "
                  "bookkeeping are hoisted to the tick path",
        detail=f"stall_detected={result.get('stall_detected')} · events fired="
               f"{[t for t, _ in fired]} · _stall_notified_room_ids persisted="
               f"{persisted!r}",
    )


def _calls_to(fn_name: str, source: str) -> int:
    return len(re.findall(rf"self\.{fn_name}\s*\(", source))


def case_progress_composed_twice(proof: H.Proof) -> None:
    """Read the shipped source; do not assert against copied line numbers."""
    cls = manager_mod.EufyVacuumManager
    dashboard = inspect.getsource(cls.get_dashboard_snapshot)
    control = inspect.getsource(cls.get_job_control_state)

    direct = _calls_to("get_job_progress_snapshot", dashboard)
    via_control = _calls_to("get_job_progress_snapshot", control)
    calls_control = _calls_to("get_job_control_state", dashboard)
    total = direct + (via_control * calls_control)

    proof.case(
        "how many times one get_dashboard_snapshot composes the progress payload",
        before=total >= 2,
        before_msg="progress composed twice — directly, and again inside "
                   "get_job_control_state; before clause (1) lands that is also two "
                   "runs of the side-effecting anomaly pass per poll",
        after=total == 1,
        after_msg="single compose — memoized within the call and shared by the "
                  "consumers that need it",
        detail=f"get_dashboard_snapshot calls it {direct}x directly and calls "
               f"get_job_control_state {calls_control}x, which calls it "
               f"{via_control}x -> {total} composes per poll",
    )


# ---------------------------------------------------------------------------
# 2. ROBORO-2 — diagnostics must dispatch the per-vacuum block via the executor
# ---------------------------------------------------------------------------

def case_roboro2_diagnostics_dispatch_via_executor(proof: H.Proof) -> None:
    """ROBORO-2: _vacuum_diagnostics is plain sync (no `await` anywhere in it) and,
    on a Roborock memory-backend device, walks roborock_geometry_drift_from_candidates
    -> geometry_drift -> raster_room_bboxes, a full width*height Python for-loop, with
    no executor dispatch anywhere in that chain. Read the CURRENT source of the
    diagnostics call site rather than asserting against copied line numbers."""
    from custom_components.eufy_vacuum import diagnostics as diag_mod

    source = inspect.getsource(diag_mod.async_get_config_entry_diagnostics)

    dispatches_via_executor = bool(re.search(
        r"async_add_executor_job\(\s*\n?\s*_vacuum_diagnostics\b", source,
    ))
    direct_inline_call = bool(re.search(
        r"\[\s*_vacuum_diagnostics\(hass,\s*manager,\s*vac\)\s*for\s+vac\s+in\s+vacuum_ids\s*\]",
        source,
    ))

    proof.case(
        "how async_get_config_entry_diagnostics invokes _vacuum_diagnostics per vacuum",
        before=direct_inline_call and not dispatches_via_executor,
        before_msg="a plain list comprehension calls the synchronous, potentially "
                   "CPU-heavy _vacuum_diagnostics directly on the event loop for "
                   "every vacuum — no executor dispatch anywhere in the "
                   "raster_room_bboxes chain it can reach on a Roborock device",
        after=dispatches_via_executor and not direct_inline_call,
        after_msg="each vacuum's block is dispatched via hass.async_add_executor_job",
        detail=f"dispatches_via_executor={dispatches_via_executor} · "
               f"direct_inline_call={direct_inline_call}",
    )


# ---------------------------------------------------------------------------
# 3. GEO-2 — zone_membership's bbox reject must precede the per-cell ray-cast
# ---------------------------------------------------------------------------

def case_geo2_zone_membership_bbox_reject_before_loop(proof: H.Proof) -> None:
    """GEO-2: the docstring claimed a cheap bbox reject precedes the per-cell
    ray-cast; the loop bounds were the WHOLE raster regardless — count
    normalize_rendered calls (one per visited raster cell) for a TINY zone bbox
    against a LARGE raster. Pure function, no hass needed; drives production
    directly."""
    from custom_components.eufy_vacuum.mapping import map_source as ms_mod

    w = h = 200  # 40,000 cells if the loop is unbounded
    room_px = bytes(w * h)  # contents irrelevant — this proof counts VISITS, not rids
    map_data = {
        "width": w, "height": h, "resolution": 5,
        "room_outline_width": w, "room_outline_height": h,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
        "room_pixels": base64.b64encode(room_px).decode(),
    }
    tiny_zone = [[0.10, 0.10], [0.12, 0.10], [0.12, 0.12], [0.10, 0.12]]

    calls = {"n": 0}
    _orig = ms_mod.normalize_rendered

    def _counting_normalize(*a, **kw):
        calls["n"] += 1
        return _orig(*a, **kw)

    ms_mod.normalize_rendered = _counting_normalize
    try:
        ms_mod.zone_membership(map_data, tiny_zone)
    finally:
        ms_mod.normalize_rendered = _orig

    total_cells = w * h

    proof.case(
        "normalize_rendered calls for a TINY zone bbox on a LARGE (200x200) raster",
        before=calls["n"] >= total_cells,
        before_msg="the loop visited (approximately) the WHOLE raster — the bbox "
                   "check ran only AFTER normalize_rendered already computed the "
                   "cell's rendered coordinate, tiny zone or not",
        after=0 < calls["n"] < total_cells // 10,
        after_msg="the zone's bbox was inverted into raster index bounds BEFORE the "
                  "loop, so normalize_rendered only runs for the small sub-rectangle "
                  "the tiny zone could possibly intersect",
        detail=f"raster={w}x{h}={total_cells} cells · "
               f"normalize_rendered calls={calls['n']}",
    )


# ---------------------------------------------------------------------------
# 4. ONB-5 — the onboarding sensor must cache the summary across both properties
# ---------------------------------------------------------------------------

def case_onb5_onboarding_sensor_summary_cached_per_cycle(proof: H.Proof) -> None:
    """ONB-5: native_value and extra_state_attributes each independently called
    get_rooms_onboarding_summary — HA reads both properties per state-write cycle,
    so it ran the lookup twice for one poll."""
    from custom_components.eufy_vacuum.sensor.onboarding import EufyVacuumOnboardingSensor

    calls = {"n": 0}

    class _Mgr:
        def get_rooms_onboarding_summary(self, *, vacuum_entity_id):
            calls["n"] += 1
            return {"maps": [], "all_complete": False}

    sensor = EufyVacuumOnboardingSensor(manager=_Mgr(), vacuum_entity_id=H.VAC)
    # One poll cycle's worth of work: refresh once (what async_update() /
    # async_added_to_hass() does), then read both properties HA reads per state write.
    sensor._refresh_summary()
    _ = sensor.native_value
    _ = sensor.extra_state_attributes

    proof.case(
        "one poll cycle: refresh + reading native_value + extra_state_attributes",
        before=calls["n"] >= 2,
        before_msg="native_value and extra_state_attributes EACH independently "
                   "called get_rooms_onboarding_summary again on top of the refresh "
                   "— redundant lookups for one state write",
        after=calls["n"] == 1,
        after_msg="both properties read the summary the one refresh already cached "
                  "— one poll cycle costs exactly one summary lookup",
        detail=f"get_rooms_onboarding_summary calls for refresh + reading both "
               f"properties = {calls['n']}",
    )


# ---------------------------------------------------------------------------
# 5. DRAFT-5 — draft edits must debounce through Store.async_delay_save
# ---------------------------------------------------------------------------

def case_draft5_storage_debounces_rapid_saves(proof: H.Proof) -> None:
    """DRAFT-5: manager.async_save_delayed() (what handle_update_working_draft now
    calls) must route through HA's own Store.async_delay_save with a real coalescing
    delay, never do an immediate Store.async_save() — a slider drag fires this
    repeatedly in quick succession."""
    from homeassistant.helpers.storage import Store
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager
    from custom_components.eufy_vacuum.core.storage import DRAFT_SAVE_DELAY_SECONDS

    hass = H.make_hass()
    mgr = EufyVacuumManager(hass)
    mgr.data = {"theme": {"library": {}, "vacuums": {}}}

    immediate_calls = {"n": 0}
    delayed_calls: list[tuple] = []

    async def _fake_async_save(self, data):
        immediate_calls["n"] += 1

    def _fake_async_delay_save(self, data_func, delay=0):
        delayed_calls.append((data_func, delay))

    orig_async_save = Store.async_save
    orig_async_delay_save = Store.async_delay_save
    Store.async_save = _fake_async_save
    Store.async_delay_save = _fake_async_delay_save
    try:
        # Simulate 3 rapid draft edits — the way a dragged slider fires the service.
        for _ in range(3):
            mgr.async_save_delayed()
    finally:
        Store.async_save = orig_async_save
        Store.async_delay_save = orig_async_delay_save

    proof.case(
        "3 rapid draft edits — how each is persisted",
        before=immediate_calls["n"] == 3,
        before_msg="each edit did a full, IMMEDIATE Store.async_save() — one "
                   "whole-integration-data disk write per slider tick",
        after=(
            immediate_calls["n"] == 0
            and len(delayed_calls) == 3
            and all(d == DRAFT_SAVE_DELAY_SECONDS for _, d in delayed_calls)
        ),
        after_msg="every edit routes through Store.async_delay_save with a "
                  f"{DRAFT_SAVE_DELAY_SECONDS}s coalescing delay — HA's own Store "
                  "collapses repeats within that window into one real write",
        detail=f"immediate Store.async_save calls={immediate_calls['n']} · "
               f"delayed Store.async_delay_save calls={len(delayed_calls)} "
               f"(delays={[d for _, d in delayed_calls]})",
    )


def case_draft5_service_handler_uses_debounce(proof: H.Proof) -> None:
    """DRAFT-5: handle_update_working_draft specifically (not the other theme
    handlers, which still legitimately await manager.async_save() immediately) must
    call the debounced save. Isolate its own nested-function source rather than
    asserting against copied line numbers."""
    from custom_components.eufy_vacuum.themes import services as theme_services_mod

    source = inspect.getsource(theme_services_mod.async_register_theme_services)
    m = re.search(
        r"async def handle_update_working_draft.*?(?=\n    async def |\Z)",
        source, re.DOTALL,
    )
    handler_body = m.group(0) if m else ""

    uses_immediate_save = "await manager.async_save()" in handler_body
    uses_delayed_save = "manager.async_save_delayed()" in handler_body

    proof.case(
        "handle_update_working_draft's own save call",
        before=uses_immediate_save and not uses_delayed_save,
        before_msg="calls await manager.async_save() unconditionally on every "
                   "single draft update — a full synchronous write of the ENTIRE "
                   "integration data dict per edit",
        after=uses_delayed_save and not uses_immediate_save,
        after_msg="calls manager.async_save_delayed() instead — the write coalesces",
        detail=f"handler body found={bool(m)} · "
               f"uses_immediate_save={uses_immediate_save} · "
               f"uses_delayed_save={uses_delayed_save}",
    )


# ---------------------------------------------------------------------------
# 6. TRK-7 — tracker.start_job no longer needs executor dispatch (no disk I/O)
# ---------------------------------------------------------------------------

def case_trk7_lifecycle_start_job_not_dispatched_via_executor(proof: H.Proof) -> None:
    """TRK-7: tracker.start_job is pure in-memory bookkeeping today (confidence-state
    reset + an _active_job dict entry) — no disk I/O. listeners/lifecycle.py wrapped
    it in hass.async_add_executor_job based on a stale comment naming
    _load_samples_from_disk/_delete_samples_tmp_file, neither of which is defined
    anywhere in this codebase (grep-confirmed). Read the CURRENT module source rather
    than asserting against copied line numbers."""
    from custom_components.eufy_vacuum.listeners import lifecycle as lifecycle_mod

    module_source = inspect.getsource(lifecycle_mod)

    imports_functools = bool(re.search(r"^import functools\s*$", module_source, re.MULTILINE))
    wraps_via_executor = bool(re.search(
        r"async_add_executor_job\(\s*\n?\s*functools\.partial\(\s*\n?\s*tracker\.start_job",
        module_source,
    ))
    plain_call = bool(re.search(r"(?<!_job\()\btracker\.start_job\(\s*\n", module_source))

    proof.case(
        "how listeners/lifecycle.py calls tracker.start_job",
        before=imports_functools and wraps_via_executor,
        before_msg="start_job is dispatched via "
                   "hass.async_add_executor_job(functools.partial(tracker.start_job, "
                   "...)) — pure overhead now that start_job does zero disk I/O",
        after=(not imports_functools) and (not wraps_via_executor) and plain_call,
        after_msg="start_job is called directly and synchronously — no executor hop "
                  "for a function that only mutates in-memory dicts",
        detail=f"imports_functools={imports_functools} · "
               f"wraps_via_executor={wraps_via_executor} · plain_call={plain_call}",
    )


def main() -> None:
    proof = H.Proof(
        "RP-037",
        "event-loop hygiene — SNAP-2 / ROBORO-2 / GEO-2 / ONB-5 / DRAFT-5 / TRK-7",
    )
    case_read_path_fires_and_persists(proof)
    case_progress_composed_twice(proof)
    case_roboro2_diagnostics_dispatch_via_executor(proof)
    case_geo2_zone_membership_bbox_reject_before_loop(proof)
    case_onb5_onboarding_sensor_summary_cached_per_cycle(proof)
    case_draft5_storage_debounces_rapid_saves(proof)
    case_draft5_service_handler_uses_debounce(proof)
    case_trk7_lifecycle_start_job_not_dispatched_via_executor(proof)
    return proof.finish()


H.run(main)
