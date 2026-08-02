"""Proof: RP-040 closing batch (.claude/notes/synthesis/RP-040-batch-table.md).

Table-driven — one case per BATCH:SMALL-CORRECTNESS / BATCH:SMALL-CORRECTNESS-
member (the behaviour-bearing ones; DOC-ONLY and DEAD-CODE members get no
case here per Stage M6's own instruction). Each case is named after its
finding id from the batch table so it can be cross-checked against that
table's "What"/"Impact" text directly.

BEFORE-state verification for this file was done via a throwaway worktree
pinned at the pre-Stage-M6 commit (5ad6b06) rather than per-case git
gymnastics in the main tree -- see the Stage M6 completion note in
_landed_packets.json for the exact command. Every case below is written to
assert BEFORE against that pinned commit's source and AFTER against
whatever is currently checked out here.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_closing_batch.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402


class _NoIOHass:
    """async_add_executor_job as a pure no-op -- battery's _process_sample
    offloads its JSONL append there; the proof cases below assert on the
    in-memory record only, so the append is dead weight we skip touching."""

    def async_add_executor_job(self, *a, **kw):
        return None


class _RuntimeStub:
    def __init__(self) -> None:
        self.data: dict = {}


def _make_battery_manager():
    from custom_components.eufy_vacuum.battery.manager import BatteryHealthManager

    mgr = BatteryHealthManager.__new__(BatteryHealthManager)
    mgr._hass = _NoIOHass()
    mgr._manager = _RuntimeStub()
    mgr._config_dir = "/tmp"
    mgr._listeners = []
    mgr._battery_to_vacuum = {}
    mgr._vacuum_unsubs = {}
    mgr._update_listeners = []
    mgr._pending_post_job = {}
    mgr._schedule_save = lambda: None
    return mgr


async def _case_dr_bat_2(proof: H.Proof) -> None:
    mgr = _make_battery_manager()

    t0 = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    mgr._process_sample(vacuum_entity_id=H.VAC, battery_level=50, charging=False, ts=t0)

    t_earlier = t0 - timedelta(minutes=5)
    mgr._process_sample(vacuum_entity_id=H.VAC, battery_level=45, charging=False, ts=t_earlier)

    record = mgr.ensure_record(H.VAC)

    proof.case(
        "battery/manager.py DR-BAT-2: an out-of-order sample (ts earlier than the "
        "last-seen sample) is correctly excluded from delta/rate accounting but "
        "must not move the anchor",
        before=(record["last_battery_level"] == 45),
        before_msg="the out-of-order sample's battery_level/ts overwrote the anchor "
                   "anyway, so the NEXT genuinely-newer sample will compute its delta "
                   "against this stale, wrong anchor",
        after=(record["last_battery_level"] == 50),
        after_msg="the anchor stays at the last genuinely-forward-in-time sample; the "
                  "out-of-order sample changed nothing but last_charging",
        detail=f"last_battery_level={record['last_battery_level']} "
               f"last_sample_ts={record['last_sample_ts']}",
    )


async def _case_dr_bat_3(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.battery.manager import SESSION_MAX_HOURS

    mgr = _make_battery_manager()

    t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    mgr._process_sample(vacuum_entity_id=H.VAC, battery_level=40, charging=False, ts=t0)
    mgr._process_sample(
        vacuum_entity_id=H.VAC, battery_level=45, charging=True, ts=t0 + timedelta(minutes=1)
    )
    record = mgr.ensure_record(H.VAC)
    session_opened = record["current_session"] is not None

    # Advance far past SESSION_MAX_HOURS while STILL charging -- forces the
    # stale-session discard path on a sample that never stopped charging.
    t_stale = t0 + timedelta(hours=SESSION_MAX_HOURS + 1)
    mgr._process_sample(vacuum_entity_id=H.VAC, battery_level=46, charging=True, ts=t_stale)
    session_after_discard = record["current_session"]

    proof.case(
        "battery/manager.py DR-BAT-3: a session force-closed as stale while "
        "charging never actually stopped must reopen immediately, not wait for "
        "the next charge cycle",
        before=(session_opened and session_after_discard is None),
        before_msg="the stale session was discarded and prev_charging was already "
                   "True, so the 'charging begins' branch never fires -- charging "
                   "stays untracked until charging goes false then true again",
        after=(session_opened and session_after_discard is not None),
        after_msg="the discard is detected and a fresh session opens on the same "
                  "sample that discarded the stale one -- no untracked gap",
        detail=f"session_opened={session_opened} "
               f"session_after_discard={session_after_discard}",
    )


async def _case_cb_3(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    mgr = EufyVacuumManager(H.make_hass("/tmp/_proof_hass_cb3"))
    await mgr.async_initialize()
    calls: list[dict] = []

    def cb(**kw):
        calls.append(kw)

    mgr.register_room_update_callback(cb)
    mgr.register_room_update_callback(cb)  # same callback registered twice
    mgr._notify_rooms_updated(vacuum_entity_id=H.VAC, map_id=H.MAP)

    proof.case(
        "core/manager.py CB-3: registering the same callback twice on a "
        "non-theme registry must not fire it twice",
        before=(len(calls) == 2),
        before_msg="register_room_update_callback appends unconditionally "
                   "(unlike the theme registry's own dedup), so a caller that "
                   "registers twice (e.g. a re-created platform entity) gets "
                   "double-fired notifications",
        after=(len(calls) == 1),
        after_msg="register_room_update_callback now dedupes like the theme "
                  "registry does, so the same callback registered twice "
                  "fires once",
        detail=f"calls={len(calls)}",
    )


async def _case_cb_4(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    mgr = EufyVacuumManager(H.make_hass("/tmp/_proof_hass_cb4"))
    await mgr.async_initialize()
    mgr.data["vacuums"][H.VAC] = {"detected_model": "x"}
    mgr.data.setdefault("maps", {})[H.VAC] = {H.MAP: {"rooms": {}}}
    room_calls: list[dict] = []
    mgr.register_room_update_callback(lambda **kw: room_calls.append(kw))

    mgr.remove_vacuum_record(vacuum_entity_id=H.VAC)

    proof.case(
        "core/manager.py CB-4: remove_vacuum_record must fire the room-update "
        "callback (and its 4 siblings) for every map it just wiped, like "
        "remove_map's callers already do",
        before=(len(room_calls) == 0),
        before_msg="remove_vacuum_record wipes every bucket the 5 callback "
                   "registries mirror and fires none of them -- live entities "
                   "(switch.py, number.py, sensor/__init__.py) keep stale "
                   "references until the next reload",
        after=(len(room_calls) == 1 and room_calls[0].get("map_id") == H.MAP),
        after_msg="remove_vacuum_record now fires the room-update callback "
                  "(and its siblings) once per map the vacuum had",
        detail=f"room_calls={room_calls}",
    )


async def _case_start_3(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    mgr = EufyVacuumManager(H.make_hass("/tmp/_proof_hass_start3"))
    await mgr.async_initialize()

    mgr._build_effective_start_plan = lambda **kw: {
        "queue_state": {"queue_room_ids": [1]},
        "payload_state": {"room_count": 1},
        "preflight": {
            "available": True, "blocked": False, "requires_confirmation": False,
            "confirm_token": None, "reason": "ready", "message": "Ready to start cleaning.",
            "selected_room_count": 1, "included_room_count": 1, "blocked_room_count": 0,
            "warnings": [],
        },
    }
    mgr.get_lifecycle_state = lambda **kw: {
        "lifecycle_state": "dock_drying", "message": "Dock is drying."
    }
    mgr.get_onboarding_state = lambda **kw: {
        "floor_types_complete": True, "enabled_rooms_needing_floor_type": []
    }
    mgr.get_active_job = lambda **kw: {"status": None}
    mgr.get_planned_job_estimate = lambda **kw: {"water_estimate": {}}
    mgr.ensure_runtime = lambda vid: SimpleNamespace(start_block_reason=None)

    result = mgr.get_start_status(vacuum_entity_id=H.VAC, map_id=H.MAP)

    proof.case(
        "core/manager.py START-3: a non-blocking lifecycle warning (dock_drying) "
        "must surface its OWN reason/message, not preflight's generic 'ready' text",
        before=(result["reason"] == "ready" and result["message"] == "Ready to start cleaning."),
        before_msg="preflight's 'ready'/'Ready to start cleaning.' sentinel always "
                   "wins the OR-chain, so the dock_drying warning's real reason and "
                   "message are never shown even though warning=True",
        after=(result["reason"] == "dock_drying" and "dry" in result["message"].lower()),
        after_msg="preflight's plain 'ready' sentinel is treated as having nothing "
                  "to say, so the lifecycle blocker's dock_drying reason/message "
                  "surface correctly",
        detail=f"reason={result.get('reason')!r} message={result.get('message')!r} "
               f"warning={result.get('warning')!r}",
    )


async def _case_dq_act_7(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.adapters.registry import (
        clear_registry, register_adapter_config,
    )
    from custom_components.eufy_vacuum.dispatch.manager import DispatchManager

    clear_registry()
    try:
        hass = H.make_hass()
        # A capitalized-option select -- the "future brand" case the finding
        # describes. No "off" among its options, so the OFF-fallback walk fires.
        hass.states.async_set(
            "select.alfred_mop_intensity", "Low",
            {"options": ["Low", "Medium", "High"]},
        )
        register_adapter_config(H.VAC, {
            "adapter_id": "test", "source": "code", "entities": {},
            "dispatch": {
                "template": "generic_room_ids", "service_domain": "vacuum",
                "service_name": "send_command",
                "global_pre_calls": [{
                    "field": "water_level",
                    "rank": ["off", "low", "medium", "high"],
                    "service": {
                        "domain": "select", "service": "select_option",
                        "value_key": "option",
                        "target_entity_id": "select.alfred_mop_intensity",
                    },
                }],
            },
        })

        dispatch = DispatchManager(manager=SimpleNamespace(hass=hass))
        resolved_rooms = [{"room_id": 1, "water_level": "off", "clean_mode": "mop"}]

        await dispatch._run_global_pre_calls(
            vacuum_entity_id=H.VAC, resolved_rooms=resolved_rooms
        )
        sent = hass.services.sent(domain="select", service="select_option")
        sent_value = sent[0]["data"].get("option") if sent else None

        proof.case(
            "dispatch/manager.py DQ-ACT-7: the OFF-fallback must send the "
            "select's own reported option string, not the lowercased rank "
            "word used only for the membership test",
            before=(sent_value == "low"),
            before_msg="the lowercased rank candidate ('low') is sent verbatim "
                       "-- the select's real option is 'Low', so the service "
                       "call silently no-ops on a capitalized-option select",
            after=(sent_value == "Low"),
            after_msg="the select's own reported option string ('Low') is "
                      "sent, matching what the entity actually exposes",
            detail=f"sent={sent}",
        )
    finally:
        clear_registry()


async def _case_io_5(proof: H.Proof) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = H.learning_store(tmp)
        jobs_dir = store.ensure_dirs(vacuum_entity_id=H.VAC).jobs_dir
        malicious_id = "../../../../etc/passwd"

        raised = False
        resolved = None
        try:
            path = store.get_completed_job_path(vacuum_entity_id=H.VAC, job_id=malicious_id)
            resolved = path.resolve()
        except ValueError:
            raised = True

        escaped = (not raised) and (not resolved.is_relative_to(jobs_dir.resolve()))

        proof.case(
            "learning/history_store.py IO-5: a crafted job_id must not be "
            "able to walk get_completed_job_path outside the jobs directory",
            before=escaped,
            before_msg="job_id is interpolated into the path unvalidated -- "
                       "the resolved path lands outside jobs_dir, giving "
                       "exclude/restore_learning_job an arbitrary *.json "
                       "overwrite primitive",
            after=raised,
            after_msg="an id that doesn't match job_finalizer's own "
                      "'job_<timestamp>' shape raises ValueError before a "
                      "Path is even built",
            detail=f"raised={raised} resolved={resolved} jobs_dir={jobs_dir}",
        )


async def _case_io_7(proof: H.Proof) -> None:
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmp:
        store = H.learning_store(tmp)
        target = Path(tmp) / "probe.json"

        with patch(
            "custom_components.eufy_vacuum.learning.history_store.os.fsync"
        ) as mock_fsync:
            store.write_json(target, {"a": 1})
            fsync_called = mock_fsync.called

        proof.case(
            "learning/history_store.py IO-7: write_json must fsync the temp "
            "file's contents before the atomic rename",
            before=(not fsync_called),
            before_msg="os.replace is rename-atomic but not durable on its "
                       "own -- nothing forces the written bytes to disk "
                       "before the rename, so a crash between write and OS "
                       "flush can leave a zero-length file that "
                       "read_json_outcome then reports as 'no data' rather "
                       "than an error",
            after=fsync_called,
            after_msg="the handle is flushed and fsync'd before os.replace, "
                      "so the rename always points at durably-written bytes",
            detail=f"fsync_called={fsync_called}",
        )


async def _case_common_5(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.adapters import registry as _registry_mod
    from custom_components.eufy_vacuum.listeners import _common

    # Structural, not behavioural -- the finding's own text says there is no
    # behavioural difference today. What matters is whether _common holds a
    # direct reference to the registry's own get_adapter_value (delegation)
    # or re-implements the identical lookup independently (duplication).
    delegate = getattr(_common, "_registry_get_adapter_value", None)
    delegates = delegate is _registry_mod.get_adapter_value

    proof.case(
        "listeners/_common.py COMMON-5: get_adapter_value must delegate to "
        "adapters/registry.py's own implementation, not reimplement the "
        "identical lookup a second time",
        before=(not delegates),
        before_msg="_common.get_adapter_value re-walks config itself with "
                   "no reference to the registry's own get_adapter_value -- "
                   "a fix applied to the registry's implementation would "
                   "silently miss every listener that routes through here",
        after=delegates,
        after_msg="_common.get_adapter_value holds a direct reference to "
                  "the registry's own get_adapter_value and calls through "
                  "to it",
        detail=f"delegate={delegate!r}",
    )


async def _case_pose_6(proof: H.Proof) -> None:
    import importlib

    from custom_components.eufy_vacuum.listeners import pose_sampler
    importlib.reload(pose_sampler)
    doc = pose_sampler.__doc__ or ""

    stale_claim = "nothing consumes" in doc.lower() and "inert" in doc.lower()

    proof.case(
        "listeners/pose_sampler.py POSE-6: the module docstring must not "
        "still claim pose_samples is an unconsumed, inert capture buffer",
        before=stale_claim,
        before_msg="the docstring says 'Capture-only / inert -- nothing "
                   "consumes pose_samples yet', understating blast radius "
                   "now that the W5c consumption wire has landed",
        after=(not stale_claim),
        after_msg="the docstring names the real W5c consumers instead of "
                  "claiming the buffer is inert",
        detail=f"doc_head={doc[:200]!r}",
    )


async def _case_dr_map_1(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.maps.map_manager import get_map_bucket

    data = {"maps": {H.VAC: {H.MAP: {
        "map_id": H.MAP, "metadata": {}, "rooms": {"1": {"name": "Kitchen"}}, "summary": {},
    }}}}

    bucket = get_map_bucket(data=data, vacuum_entity_id=H.VAC, map_id=H.MAP)
    bucket["rooms"]["1"]["name"] = "MUTATED"

    persisted = data["maps"][H.VAC][H.MAP]["rooms"]["1"]["name"] == "MUTATED"

    proof.case(
        "maps/map_manager.py DR-MAP-1: get_map_bucket must return a "
        "detached copy on a hit, not the live stored dict",
        before=persisted,
        before_msg="mutating the returned bucket wrote straight through "
                   "into storage when the map existed -- but the SAME "
                   "mutation on a miss (a fresh dict literal) would have "
                   "silently vanished, an inconsistent contract for any "
                   "caller",
        after=(not persisted),
        after_msg="the returned bucket is a deep copy; mutating it never "
                  "touches storage, present or absent",
        detail=f"persisted={persisted}",
    )


async def _case_dr_map_2(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.maps.map_manager import get_vacuum_maps_summary

    # rooms was updated (2 enabled, 1 disabled) but the cached summary block
    # was never recomputed -- still says 0/0 from before the rooms existed.
    data = {"maps": {H.VAC: {H.MAP: {
        "map_id": H.MAP,
        "metadata": {},
        "rooms": {
            "1": {"enabled": True},
            "2": {"enabled": True},
            "3": {"enabled": False},
        },
        "summary": {"enabled_count": 0, "disabled_count": 0},
    }}}}

    out = get_vacuum_maps_summary(data=data, vacuum_entity_id=H.VAC)
    m = out["maps"][0]
    agrees = (m["enabled_room_count"] + m["disabled_room_count"]) == m["room_count"]

    proof.case(
        "maps/map_manager.py DR-MAP-2: enabled/disabled room counts must "
        "agree with the live room_count in the same payload",
        before=(not agrees),
        before_msg="enabled/disabled counts came from the cached summary "
                   "block (stale: 0/0) while room_count is live (3) -- the "
                   "two disagree in one payload",
        after=agrees,
        after_msg="enabled/disabled counts are derived live from the same "
                  "rooms dict room_count uses, so they always agree",
        detail=f"room_count={m['room_count']} "
               f"enabled={m['enabled_room_count']} "
               f"disabled={m['disabled_room_count']}",
    )


async def _case_dr_onb_4(proof: H.Proof) -> None:
    from unittest.mock import patch

    from custom_components.eufy_vacuum.onboarding import manager as onboarding_mod

    data: dict = {}
    hass = H.make_hass()
    mgr = onboarding_mod.OnboardingManager(data, hass)

    sentinel_calls: list = []

    def _sentinel():
        sentinel_calls.append(1)
        return {"sentinel": True}

    # create=True: on the pinned (pre-fix) tree _default_map_onboarding
    # doesn't exist at all -- patch.object would otherwise raise instead of
    # cleanly reporting BEFORE.
    with patch.object(
        onboarding_mod, "_default_map_onboarding", side_effect=_sentinel, create=True
    ):
        mgr._get_map_onboarding(vacuum_entity_id=H.VAC, map_id=H.MAP)
        mgr.reset_onboarding(vacuum_entity_id=H.VAC, map_id=H.MAP)

    both_routed = sentinel_calls == [1, 1]

    proof.case(
        "onboarding/manager.py DR-ONB-4: _get_map_onboarding's lazy-create "
        "and reset_onboarding's explicit reset must build the 5-key default "
        "record from ONE shared source, not two hand-maintained copies",
        before=(not both_routed),
        before_msg="patching the shared default builder has no effect on "
                   "either call site -- each inlines its own independent "
                   "copy of the 5-key shape",
        after=both_routed,
        after_msg="both call sites route through the same "
                  "_default_map_onboarding() builder",
        detail=f"sentinel_calls={sentinel_calls}",
    )


async def _case_est_h2o_2(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager

    rp = RunPlanManager.__new__(RunPlanManager)
    # adapter declares measured rates but omits "off"
    rate = rp._water_rate_ml_per_minute("off", rate_override={"low": 2.0, "high": 6.0})

    proof.case(
        "planning/run_plan.py EST-H2O-2: a declared water_rates table that "
        "omits 'off' must still bill water-off rooms at 0 ml/min, not the "
        "generic 4.0 ml/min fallback",
        before=(rate == 4.0),
        before_msg="the declared table REPLACED the off=0 base wholesale, "
                   "so an adapter omitting 'off' falls through to the "
                   "generic 4.0 ml/min fallback for water-off mop rooms",
        after=(rate == 0.0),
        after_msg="the declared table overlays the off=0 base instead of "
                  "replacing it, so 'off' resolves to 0 unless the adapter "
                  "explicitly overrides it too",
        detail=f"rate={rate}",
    )


async def _case_est_clamp_1(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.planning.run_plan import RunPlanManager

    rp = RunPlanManager.__new__(RunPlanManager)
    rp._manager = SimpleNamespace(
        get_vacuum_capabilities=lambda **kw: {"entities": {}},
        hass=SimpleNamespace(states=SimpleNamespace(get=lambda *a, **k: None)),
    )
    rp._get_water_model_config = lambda **kw: {
        "available": True,
        "model_code": "x", "model_name": "x",
        "robot_internal_tank_ml": 0.0,
        "dock_clean_tank_capacity_ml": 200.0,
        "dock_wash_overhead_ml_per_cycle": 0.0,
        "water_rates": None,
        "low_clean_water_margin_ml": 300.0,
    }
    rp._derive_wash_frequency_config = lambda **kw: {
        "mode": "by_room", "mode_label": "x", "interval_minutes": 0,
    }
    rp._get_station_clean_water_percent = lambda **kw: 10.0  # 10% of 200ml = 20ml available

    # One mopping room whose estimated water use (240ml) far exceeds the
    # 20ml available -- forces a shortfall.
    resolved_rooms = [{"room_id": 1, "clean_mode": "mop", "water_level": "high"}]
    room_timeline = [{"room_id": 1, "slug": "r1", "minutes": 60, "source": "measured"}]

    out = rp.estimate_job_water_usage(
        vacuum_entity_id=H.VAC, resolved_rooms=resolved_rooms, room_timeline=room_timeline,
    )

    proof.case(
        "planning/run_plan.py EST-CLAMP-1: estimated_clean_tank_remaining_ml "
        "must floor at 0 like its own percent sibling already does",
        before=(out["estimated_clean_tank_remaining_ml"] < 0),
        before_msg="a shortfall rendered as a self-contradictory negative ml "
                   "figure alongside a percent already clamped to 0%",
        after=(out["estimated_clean_tank_remaining_ml"] == 0.0),
        after_msg="the ml figure floors at 0 like the percent does; "
                  "clean_water_shortfall_ml still carries how far short",
        detail=f"remaining_ml={out['estimated_clean_tank_remaining_ml']} "
               f"remaining_pct={out['estimated_clean_tank_remaining_percent']} "
               f"shortfall_ml={out['clean_water_shortfall_ml']}",
    )


CASES = [
    _case_dr_bat_2,
    _case_dr_bat_3,
    _case_cb_3,
    _case_cb_4,
    _case_start_3,
    _case_dq_act_7,
    _case_io_5,
    _case_io_7,
    _case_common_5,
    _case_pose_6,
    _case_dr_map_1,
    _case_dr_map_2,
    _case_dr_onb_4,
    _case_est_h2o_2,
    _case_est_clamp_1,
]


async def main() -> int:
    proof = H.Proof("RP-040", "closing batch — per-file one-line correctness fixes")
    for case_fn in CASES:
        await case_fn(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
