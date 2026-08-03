"""Proof RP-038 (RF-30) — dock events are edges.

Six cases, covering all seven finding_ids (REG-1+GUARD-3 share one case,
same underlying check).

Case 6 (LIFE-3) exercises listeners/lifecycle.py's inline mop-wash detector
directly -- it now delegates its edge test to the SAME
is_dock_trigger_edge helper dock_events.py's own _handle_dock_event uses
(listeners/_common.py), instead of hand-rolling a weaker inline check (no
old_state guard at all, not even an old==new dedup) with a hardcoded
Eufy-literal vocabulary fallback ("washing"/"washing mop") for adapters
that declare none. NOTE: the packet text's claim that the vocabulary half
already landed in RP-025 is WRONG -- verified via `git show 71cc479
--stat --name-only`: that commit only touched profiles/room_profiles.py
and its two test files; its own message says the lifecycle/dock-vocab
half was "left for follow-up". Both halves (edge + vocabulary-fallback
removal) are fixed together here.

  REG-1 + GUARD-3 -- listeners/dock_events.py:72 `old_val = str(old_state.
    state)... if old_state else ""`. old_state=None (HA restart while the
    dock is mid-cycle) maps to "", which never equals the trigger value, so
    the CURRENT code treats "no known prior state" as a genuine transition
    INTO the trigger state -- a restart mid-dry is recorded as a brand-new
    dry cycle.
  DOCK-1 -- dock/manager.py:383 writes vacuum_events[event_type] = now
    UNCONDITIONALLY, before the debounce decision (385-424) even runs. A
    debounced (should_count=False) event still advances the "last seen at"
    timestamp with no corresponding counter increment -- the two fields
    disagree.
  DOCK-2 -- record_dock_event has no event_type validation at all; its
    sibling set_dock_event_count validates against the same counter_map
    and refuses an unknown type.
  DOCK-3 -- set_dock_event_count resets a counter but never clears
    f"{event_type}_last_counted_at" -- a legitimate post-reset event can
    still be suppressed by a debounce window measured from the marker the
    reset was supposed to clear.
  REG-4 -- config_schema.py declares dock_events.enabled ("Default: False")
    but listeners/dock_events.py:register() never reads it -- any adapter
    declaring a dock_status entity gets event recording regardless of the
    flag, including an adapter that explicitly sets enabled=False.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_dock_edges.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config   # noqa: E402
from custom_components.eufy_vacuum.dock.manager import DockManager   # noqa: E402
from custom_components.eufy_vacuum.listeners import dock_events   # noqa: E402
from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN   # noqa: E402

VAC = H.VAC

_ADAPTER = {
    "adapter_id": "eufy", "source": "code",
    "entities": {"dock_status": "sensor.alfred_dock"},
    "dock_events": {
        # REG-4: register() now gates on this per-adapter flag (default
        # False) -- cases 1 and 5 both go through dock_events.register(),
        # so the "enabled" baseline must be explicit True here for case 1
        # to still exercise a wired listener. Case 5 overrides it False.
        "enabled": True,
        "triggers": {"last_dry_start": ["drying"], "last_mop_wash": ["washing"]},
        "debounce_seconds": {"last_mop_wash": 300},
    },
}


def main() -> int:
    proof = H.Proof("RP-038", "dock events are edges")

    # -------------------------------------------------------------------
    # Case 1 (REG-1 + GUARD-3): old_state=None treated as a genuine edge.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    register_adapter_config(VAC, _ADAPTER)
    mgr = H.ManagerStub(hass=hass)
    mgr.get_known_vacuum_ids = lambda: [VAC]
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr

    recorded: list[str] = []
    mgr.record_dock_event = lambda **kw: recorded.append(kw["event_type"])
    mgr._async_save_logged = H.async_noop()

    # Capture the real registered closure by patching the CONSUMING module's
    # own imported name (per handoff Sec.5) -- `from ... import X` binds a
    # separate local name, so patching homeassistant.helpers.event's
    # attribute would not reach dock_events.py's already-bound reference.
    _orig_track = dock_events.async_track_state_change_event
    captured = {}
    dock_events.async_track_state_change_event = (
        lambda hass_arg, entity_ids, cb: captured.setdefault("cb", cb)
    )
    try:
        dock_events.register(hass)
    finally:
        dock_events.async_track_state_change_event = _orig_track

    # simulate an HA restart mid-dry: the entity's first-ever reported state
    # (old_state=None) already reads "drying".
    from types import SimpleNamespace
    from homeassistant.core import Event
    new_state = SimpleNamespace(state="drying")
    captured["cb"](Event("state_changed", {
        "entity_id": "sensor.alfred_dock", "old_state": None, "new_state": new_state,
    }))

    proof.case(
        "HA restarts while the dock is already mid-dry (old_state=None)",
        before=recorded == ["last_dry_start"],
        before_msg="old_state=None maps to '' (never equal to the trigger "
                   "value 'drying'), so the restart-time first sighting is "
                   "recorded as a BRAND NEW dry cycle -- counter++, "
                   "last_dry_start timestamp reset",
        after=recorded == [],
        after_msg="old_state None/unavailable/unknown is not a known prior "
                  "state -- the first sighting after a restart is NOT an "
                  "edge, nothing is recorded",
        detail=f"recorded event types={recorded}",
    )

    # -------------------------------------------------------------------
    # Case 2 (DOCK-1): a debounced event still moves the timestamp.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    register_adapter_config(VAC, _ADAPTER)
    mgr2 = H.ManagerStub(hass=hass2)
    dock = DockManager(manager=mgr2)
    # Seed a prior wash directly with a SENTINEL timestamp (utc_now_iso is
    # whole-second resolution -- two real calls a moment apart can produce
    # the SAME string and mask an unconditional overwrite; a sentinel that
    # can never collide with a freshly-generated timestamp is unambiguous).
    mgr2.data.setdefault("dock_events", {})[VAC] = {
        "last_mop_wash": "SENTINEL-PRIOR-WASH",
        "last_mop_wash_last_counted_at": "SENTINEL-PRIOR-WASH",
        "mop_wash_count": 1,
    }
    # a second wash-trigger fires -- SENTINEL-PRIOR-WASH is not a parseable
    # timestamp, so the debounce parse fails and falls through to should_count
    # =True (the code's own documented behaviour for an unparseable marker) --
    # use a REAL prior timestamp instead so the debounce genuinely engages.
    from custom_components.eufy_vacuum.timestamp_utils import utc_now_iso
    _real_prior = utc_now_iso()
    mgr2.data["dock_events"][VAC]["last_mop_wash_last_counted_at"] = _real_prior
    mgr2.data["dock_events"][VAC]["last_mop_wash"] = "SENTINEL-PRIOR-WASH"

    dock.record_dock_event(vacuum_entity_id=VAC, event_type="last_mop_wash")
    ts_after = mgr2.data["dock_events"][VAC]["last_mop_wash"]
    count_after = mgr2.data["dock_events"][VAC]["mop_wash_count"]

    proof.case(
        "a wash-trigger fires inside an already-active debounce window",
        before=count_after == 1 and ts_after != "SENTINEL-PRIOR-WASH",
        before_msg="the counter correctly did NOT increment (debounced), "
                   "but last_mop_wash's timestamp was overwritten anyway -- "
                   "the two fields now disagree about whether a wash happened",
        after=count_after == 1 and ts_after == "SENTINEL-PRIOR-WASH",
        after_msg="the timestamp write moves inside the debounce decision -- "
                  "a debounced event changes nothing at all",
        detail=f"count after={count_after} (started at 1) · "
               f"last_mop_wash after={ts_after!r} (started as the sentinel)",
    )

    # -------------------------------------------------------------------
    # Case 3 (DOCK-2): no event_type validation.
    # -------------------------------------------------------------------
    hass3 = H.make_hass()
    mgr3 = H.ManagerStub(hass=hass3)
    dock3 = DockManager(manager=mgr3)
    dock3.record_dock_event(vacuum_entity_id=VAC, event_type="not_a_real_event_type")
    junk_result = dock3.set_dock_event_count(
        vacuum_entity_id=VAC, event_type="not_a_real_event_type", count=5,
    )

    proof.case(
        "an unknown event_type reaches record_dock_event vs its sibling",
        before="not_a_real_event_type" in mgr3.data["dock_events"][VAC]
        and junk_result["updated"] is False,
        before_msg="record_dock_event writes the bogus key unconditionally "
                   "(no validation at all); its sibling set_dock_event_count "
                   "refuses the SAME unknown type via the counter_map check",
        after="not_a_real_event_type" not in mgr3.data["dock_events"][VAC],
        after_msg="record_dock_event validates event_type against the "
                  "counter map like its sibling and refuses/ignores an "
                  "unknown type",
        detail=f"dock_events keys after bogus record={sorted(mgr3.data['dock_events'][VAC])} "
               f"· set_dock_event_count on the same bogus type={junk_result}",
    )

    # -------------------------------------------------------------------
    # Case 4 (DOCK-3): counter reset doesn't clear the debounce marker.
    # -------------------------------------------------------------------
    hass4 = H.make_hass()
    register_adapter_config(VAC, _ADAPTER)
    mgr4 = H.ManagerStub(hass=hass4)
    dock4 = DockManager(manager=mgr4)
    dock4.record_dock_event(vacuum_entity_id=VAC, event_type="last_mop_wash")
    dock4.set_dock_event_count(vacuum_entity_id=VAC, event_type="last_mop_wash", count=0)
    marker_after_reset = mgr4.data["dock_events"][VAC].get("last_mop_wash_last_counted_at")
    # a legitimate wash 1s later -- well inside the debounce window measured
    # from the marker the reset was supposed to have cleared.
    dock4.record_dock_event(vacuum_entity_id=VAC, event_type="last_mop_wash")
    count_after_new_wash = mgr4.data["dock_events"][VAC]["mop_wash_count"]

    proof.case(
        "a counter reset, then a genuine wash inside the OLD debounce window",
        before=marker_after_reset is not None and count_after_new_wash == 0,
        before_msg="set_dock_event_count reset the counter but left the "
                   "debounce marker untouched -- the next genuine wash is "
                   "suppressed by a window measured from BEFORE the reset",
        after=count_after_new_wash == 1,
        after_msg="counter reset clears the debounce marker too -- the next "
                  "genuine wash counts",
        detail=f"marker survived reset={marker_after_reset is not None} · "
               f"count after the next wash={count_after_new_wash}",
    )

    # -------------------------------------------------------------------
    # Case 5 (REG-4): register() ignores dock_events.enabled.
    # -------------------------------------------------------------------
    hass5 = H.make_hass()
    register_adapter_config(VAC, {**_ADAPTER, "dock_events": {
        **_ADAPTER["dock_events"], "enabled": False,
    }})
    mgr5 = H.ManagerStub(hass=hass5)
    mgr5.get_known_vacuum_ids = lambda: [VAC]
    hass5.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr5

    _orig_track5 = dock_events.async_track_state_change_event
    dock_events.async_track_state_change_event = lambda hass_arg, entity_ids, cb: (lambda: None)
    try:
        dock_events.register(hass5)
    finally:
        dock_events.async_track_state_change_event = _orig_track5
    registered_listener = bool(hass5.data[DOMAIN].get(dock_events._DOCK_EVENT_UNSUBS))

    proof.case(
        "adapter explicitly declares dock_events.enabled=False",
        before=registered_listener is True,
        before_msg="register() never reads dock_events.enabled -- a "
                   "dock_status entity alone is enough to wire the listener, "
                   "even when the adapter explicitly opted out",
        after=registered_listener is False,
        after_msg="register() honors dock_events.enabled -- an opted-out "
                  "adapter gets no dock-event listener at all",
        detail=f"listener registered despite enabled=False: {registered_listener}",
    )

    # -------------------------------------------------------------------
    # Case 6 (LIFE-3): lifecycle.py's inline wash detector, driven directly.
    # Pre-fix: a bare new-state-in-vocab check with NO old_state guard at
    # all (not even old==new dedup) -- fires on a first sighting exactly
    # like dock_events' own pre-fix REG-1/GUARD-3 bug. Post-fix: delegates
    # to the same is_dock_trigger_edge helper, so old_state=None correctly
    # refuses.
    # -------------------------------------------------------------------
    from custom_components.eufy_vacuum.listeners import lifecycle

    hass6 = H.make_hass()
    _LIFECYCLE_ADAPTER = {
        "adapter_id": "eufy", "source": "code",
        "entities": {
            "task_status": "sensor.alfred_task",
            "dock_status": "sensor.alfred_dock",
            "active_cleaning_target": "sensor.alfred_target",
            "active_map": "sensor.alfred_map",
        },
        # Explicitly declared (matches Eufy's real adapter.py) so this case
        # isolates the OLD-STATE guard specifically, independent of the
        # separate vocabulary-fallback-removal question.
        "dock_events": {
            "triggers": {"last_mop_wash": ["washing", "washing mop"]},
        },
    }
    register_adapter_config(VAC, _LIFECYCLE_ADAPTER)
    mgr6 = H.ManagerStub(hass=hass6)
    mgr6.get_known_vacuum_ids = lambda: [VAC]
    mgr6.get_known_map_ids = lambda vacuum_entity_id: [H.MAP]
    mgr6.get_lifecycle_state = lambda **kw: {
        "lifecycle_state": "active_job_running", "dock_status": "",
    }
    mgr6.maybe_handle_external_run = H.async_noop(return_value=False)
    mgr6.data.setdefault("active_jobs", {}).setdefault(VAC, {})[H.MAP] = H.active_job(
        vacuum_entity_id=VAC, map_id=H.MAP, status="started",
    )
    wash_calls: list[dict] = []
    mgr6.update_active_job_mop_wash_observation = (
        lambda **kw: wash_calls.append(kw)
    )
    hass6.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr6

    _orig_track6 = lifecycle.async_track_state_change_event
    captured6 = {}
    lifecycle.async_track_state_change_event = (
        lambda hass_arg, entity_ids, cb: captured6.setdefault("cb", cb)
    )
    try:
        lifecycle.register(hass6)
    finally:
        lifecycle.async_track_state_change_event = _orig_track6

    # First-ever reading on the dock entity already lands on the wash
    # trigger -- old_state=None (HA restart mid-wash, or genuinely the
    # first sighting).
    new_state6 = SimpleNamespace(state="washing")
    captured6["cb"](Event("state_changed", {
        "entity_id": "sensor.alfred_dock", "old_state": None, "new_state": new_state6,
    }))
    # _handle_lifecycle_change schedules its real work via
    # hass.async_create_task -- run it to completion before asserting.
    H.drain_idle_loop()

    proof.case(
        "lifecycle's inline wash detector: old_state=None during an active job",
        before=len(wash_calls) == 1,
        before_msg="the pre-fix bare new-state check has no old_state guard "
                   "at all (worse than dock_events' own pre-fix bug -- it "
                   "doesn't even dedup old==new) -- a first sighting after "
                   "restart routes a mid-job mop-wash observation",
        after=wash_calls == [],
        after_msg="delegates to the same is_dock_trigger_edge helper -- "
                  "old_state=None is not a known prior state, so no "
                  "observation is routed",
        detail=f"wash observation calls={wash_calls}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
