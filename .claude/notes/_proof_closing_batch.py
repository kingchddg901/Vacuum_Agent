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


CASES = [
    _case_dr_bat_2,
    _case_dr_bat_3,
    _case_cb_3,
    _case_cb_4,
    _case_start_3,
]


async def main() -> int:
    proof = H.Proof("RP-040", "closing batch — per-file one-line correctness fixes")
    for case_fn in CASES:
        await case_fn(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
