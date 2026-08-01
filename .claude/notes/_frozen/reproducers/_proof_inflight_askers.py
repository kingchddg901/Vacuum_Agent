"""Proof RP-014 (RF-12) — every asker uses the owned in-flight helpers.

`jobs/active_job.py` defines two predicates side by side and its docstrings pin
which question each answers:

  * `dispatched_job_is_in_flight` — for questions that only make sense for a run
    WE commanded (queue, payload, resolved room identity).
  * `run_is_in_flight` — for questions about the ROBOT: is it out on the floor
    right now? "Observation belongs here... An app-started run is every bit as
    real to the hardware, and refusing to observe it is how evidence goes
    missing."

Five sites hand-inline `{"started", "paused"}` instead, answering ROBOT
questions with the QUEUE set. Three are observable and reproduced here — an
app-started (`status == "external"`) run on the floor:

  A5-METRICS-1  the 5 s progress ticker skips it entirely — no snapshot, no
    EVENT_JOB_PROGRESS_TICK, and no Lever B live-room pulse. Lever B exists
    BECAUSE external runs have no dispatched phases to refresh on; the one case
    it was built for is the one case the tick excludes.
  A6-VAC-1 (HIGH, actuating)  the dock gate reports every wash/dry/empty action
    ALLOWED while that run is going. Its own docstring names run_is_in_flight.
    The realistic trigger is a mid-run dock visit — recharge or mop wash — where
    `vacuum.state` is "docked" and the user presses Empty Dust from the card.
  DR-SENS-1  the active_job sensor reads "none" during a run the integration is
    itself tracking, so history and automations see idle.

Cases 1 and 2 drive the REAL closures/methods (the tick closure is captured by
patching `job_progress.async_track_time_interval` — the RP-011 pattern).

The packet's other two sites (COMMON-6 listener literals, COMMON-4 duplicated
completion vocabulary) are adjudication/derivation work with no distinct runtime
shape; they are covered by the packet's per-site table and its tests, not here.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_inflight_askers.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from homeassistant.helpers import entity_registry as er   # noqa: E402

from custom_components.eufy_vacuum.const import (   # noqa: E402
    DATA_RUNTIME, DOMAIN, EVENT_JOB_PROGRESS_TICK,
)
from custom_components.eufy_vacuum.dock.manager import DockManager   # noqa: E402
from custom_components.eufy_vacuum.listeners import job_progress   # noqa: E402
from custom_components.eufy_vacuum.sensor.lifecycle import (   # noqa: E402
    EufyVacuumActiveJobSensor,
)


class _EmptyEntityRegistry:
    """Inert stand-in for HA's entity registry: knows nothing about anything.

    A plain class rather than SimpleNamespace because HA's `singleton` decorator
    stores the value in `hass.data` and SimpleNamespace is unhashable.
    """

    def async_get(self, _entity_id):
        return None


def _external_run_manager(hass) -> H.ManagerStub:
    """A vacuum with an app-started run in flight — the shape
    `start_external_capture` leaves behind: status external, no queue, no phases."""
    mgr = H.ManagerStub(hass=hass)
    job = H.active_job(
        status="external",
        job_id="job_external",
        queue_room_ids=[],
        resolved_rooms=[],
        payload={},
    )
    mgr.data["active_jobs"] = {H.VAC: {H.MAP: job}}
    return mgr


def case_progress_tick_skips_external(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = _external_run_manager(hass)
    snapshots: list[tuple[str, str]] = []
    pulses: list[str] = []
    mgr.get_known_vacuum_ids = lambda: [H.VAC]
    mgr.get_known_map_ids = lambda _v: [H.MAP]
    mgr.get_job_progress_snapshot = lambda **kw: snapshots.append(
        (kw["vacuum_entity_id"], kw["map_id"])) or {}
    mgr.maybe_pulse_live_room_refresh = lambda v: pulses.append(v)
    hass.data[DOMAIN] = {DATA_RUNTIME: mgr}

    captured: dict = {}
    real_track = job_progress.async_track_time_interval

    def _capture(_hass, action, interval):
        captured["tick"] = action
        return lambda: None

    job_progress.async_track_time_interval = _capture
    try:
        job_progress.register(hass)
    finally:
        job_progress.async_track_time_interval = real_track

    tick = captured.get("tick")
    if tick is not None:
        tick(None)          # one 5 s tick, production's own closure

    ticks_fired = hass.bus.fired(EVENT_JOB_PROGRESS_TICK)

    proof.case(
        "an app-started run is on the floor — does the 5 s progress ticker see it?",
        before=snapshots == [] and pulses == [] and ticks_fired == [],
        before_msg="the tick skipped the run entirely — no snapshot, no "
                   "EVENT_JOB_PROGRESS_TICK, and no Lever B live-room pulse; "
                   "stall detection and the card's refresh are both dark for "
                   "exactly the run Lever B was built for",
        # The AFTER asserts only what the PACKET requires ("tick fired for
        # external"): the snapshot and the progress event. The Lever B pulse is
        # reported in `detail` but deliberately NOT asserted — the packet does
        # not mandate where that pulse is gated, and a correct repair that gated
        # it differently would report UNEXPECTED and invite someone to "fix" the
        # proof. A reproducer must not demand more than the spec it proves.
        after=len(snapshots) == 1 and len(ticks_fired) == 1,
        after_msg="the tick covered the external run — snapshot taken and "
                  "progress event fired",
        detail=f"snapshots={snapshots} · live-room pulses={pulses} · "
               f"progress events={len(ticks_fired)}",
    )


def case_dock_action_allowed_mid_external(proof: H.Proof) -> None:
    hass = H.make_hass()
    # an EMPTY entity registry — inert scaffolding only. get_dock_action_status
    # resolves button entities through er.async_get before it reaches the gate,
    # and this proof is about the GATE, so the buttons are supplied via
    # hass.states below (the resolver's first lookup) and never via the registry.
    hass.data[er.DATA_REGISTRY] = _EmptyEntityRegistry()
    mgr = _external_run_manager(hass)
    mgr.get_vacuum_capabilities = lambda **kw: {
        "supports_mop_wash": True, "supports_mop_dry": True,
        "supports_empty_dust": True, "entities": {},
    }
    mgr.get_lifecycle_state = lambda **kw: {
        "dock_status": "standby", "lifecycle_state": "running", "message": ""}

    # The robot is AT the dock mid-run — a recharge or a mop-wash stop. This is
    # the realistic moment a user reaches for a dock action from the card.
    hass.states.async_set(H.VAC, "docked")
    for suffix in ("wash_mop", "dry_mop", "stop_dry_mop", "empty_dust"):
        hass.states.async_set(f"button.alfred_{suffix}", "unknown")

    from custom_components.eufy_vacuum.adapters import registry as adapter_registry
    adapter_registry.register_adapter_config(H.VAC, {
        "adapter_id": "proof_rp014",
        "source": "proof",
        "dock_events": {
            "triggers": {},
            "action_buttons": {
                a: {"entity_suffixes": [a]}
                for a in ("wash_mop", "dry_mop", "stop_dry_mop", "empty_dust")
            },
        },
    })
    try:
        status = DockManager(mgr).get_dock_action_status(
            vacuum_entity_id=H.VAC, map_id=H.MAP)
    finally:
        adapter_registry.unregister_adapter_config(H.VAC)

    empty = status["actions"]["empty_dust"]
    wash = status["actions"]["wash_mop"]

    proof.case(
        "the robot is docked MID app-started run — is Empty Dust offered?",
        before=empty["allowed"] is True and empty["reason"] == "ready"
        and wash["allowed"] is True,
        before_msg="dock actions ALLOWED mid-external-run — the gate asks the "
                   "queue's question ({started, paused}) about the robot, so an "
                   "app-started run is invisible to it and a wash/dry/empty can "
                   "actuate under a live run (HIGH: this one fires hardware)",
        after=empty["allowed"] is False and empty["reason"] == "job_active"
        and wash["allowed"] is False,
        after_msg="dock actions refused: job_active — the gate asks "
                  "run_is_in_flight, as its own docstring says it should",
        detail=f"empty_dust allowed={empty['allowed']} reason={empty['reason']!r} · "
               f"wash_mop allowed={wash['allowed']} · "
               f"active_job_status={status['active_job_status']!r}",
    )


def case_sensor_reads_none(proof: H.Proof) -> None:
    hass = H.make_hass()
    mgr = _external_run_manager(hass)
    sensor = EufyVacuumActiveJobSensor(
        manager=mgr, vacuum_entity_id=H.VAC, map_id=H.MAP)
    value = sensor.native_value

    proof.case(
        "the active_job sensor during a run the integration IS tracking",
        before=value == "none",
        before_msg="sensor reads 'none' — the five-value enum has no arm for "
                   "external, so the recorder, history and any automation see "
                   "idle while a tracked run is in flight",
        after=value == "external",
        after_msg="sensor reads 'external' — the tracked app-started run is a "
                  "distinct, visible state",
        detail=f"native_value={value!r} while the stored job status is "
               f"{mgr.get_active_job(vacuum_entity_id=H.VAC, map_id=H.MAP).get('status')!r}",
    )


def main() -> int:
    proof = H.Proof("RP-014", "every asker uses the owned in-flight helpers")
    case_progress_tick_skips_external(proof)
    case_dock_action_allowed_mid_external(proof)
    case_sensor_reads_none(proof)
    return proof.finish()


if __name__ == "__main__":
    H.run(main)
