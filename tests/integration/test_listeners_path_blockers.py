"""Malformed-config / ignored-rule tests for the path_blockers listener.

The path-blocker listener builds its ``watch_map`` from user-authored room
rules (``register``) and reacts to blocker entity state changes mid-job
(``_handle_path_blocker_change``). Bad user config must NEVER poison listener
registration: a malformed room, a malformed rule, a disabled rule, a wrong
``kind``, or a rule with no ``entity_id`` must be silently skipped, leaving a
clean (possibly empty) ``watch_map`` and a single registered room-update
callback. Likewise the event handler must early-out (no manager call, no event,
no save) for irrelevant / unchanged / unwatched events.

These drive a ``MagicMock`` manager so the listener's OWN defensive guards are
exercised directly (the real manager normalizes rules first, which would strip
most of these shapes before ``register`` ever sees them). Each case asserts the
documented effect — what ends up in ``watch_map`` and which manager methods were
(not) called — not merely "doesn't crash".

Coverage targets
----------------
[PB-1]  room not a dict -> skipped, watch_map empty.
[PB-2]  rule not a dict -> skipped.
[PB-3]  rule disabled (enabled False) -> skipped.
[PB-4]  kind != "blocker" (modifier) -> skipped.
[PB-5]  rule missing entity_id (and blank entity_id) -> skipped.
[PB-6]  "unknown" map_id -> skipped before rooms are read.
[PB-7]  a valid blocker rule alongside the bad ones -> the ONLY watched entity.
[PB-8]  manager is None -> register no-ops, registers nothing.
[PB-9]  event entity not in watch_map -> handler early-outs (no active-job read).
[PB-10] new_state missing -> early-out.
[PB-11] state unchanged (old == new) -> early-out.
[PB-12] manager missing at event time -> early-out (no get_active_job).
[PB-13] report not a dict -> no event fired, no save.
[PB-14] no changes overall -> no save, no path-blocked event.
[PB-15] L15/GUARD-2: an edge on entity B while entity A is mid-evaluation is
        EVALUATED, not swallowed. The single-flight flag was one dict for the whole
        integration, and the rerun loop re-runs the CURRENT event's closure — so B's
        targets were never visited at all, with no report, no event and no log.
[PB-16] L15: a burst on ONE entity still coalesces. That is the property GUARD-2 was
        written for and the per-entity keying must not cost it.
[PB-17] L15: the per-entity state is dropped by remove(), or a stale `running: True`
        from a killed task wedges that entity off after a reload.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests._factories import spec_manager

from custom_components.eufy_vacuum.const import (
    DATA_RUNTIME,
    DOMAIN,
    EVENT_PATH_BLOCKED,
)
from custom_components.eufy_vacuum.listeners import path_blockers


_VAC = "vacuum.alfred"
_MAP = "6"
_BLOCKER_ENTITY = "binary_sensor.door_open"

_PATH_BLOCKER_UNSUBS = "_path_blocker_unsubs"
_PATH_BLOCKER_ROOM_CALLBACK = "_path_blocker_room_callback"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(rooms: dict) -> MagicMock:
    """A MagicMock manager that returns ``rooms`` verbatim for one vac/map.

    Returning the malformed shapes WITHOUT normalization is the whole point —
    it forces ``register`` to defend itself rather than relying on the real
    manager's rule normalizer.
    """
    manager = spec_manager()
    manager.get_known_vacuum_ids.return_value = [_VAC]
    manager.get_known_map_ids.return_value = [_MAP]
    manager._normalized_managed_rooms_with_automation.return_value = rooms
    return manager


def _install(hass, manager) -> None:
    """Seed hass.data so the listener resolves the manager via DATA_RUNTIME."""
    hass.data.setdefault(DOMAIN, {})
    if manager is None:
        hass.data[DOMAIN].pop(DATA_RUNTIME, None)
    else:
        hass.data[DOMAIN][DATA_RUNTIME] = manager


def _blocker_rule(entity_id: str = _BLOCKER_ENTITY, **overrides) -> dict:
    rule = {
        "id": "rule-1",
        "kind": "blocker",
        "enabled": True,
        "entity_id": entity_id,
        "operator": "is",
        "value": "on",
    }
    rule.update(overrides)
    return rule


def _room(rules: list) -> dict:
    return {"room_id": 1, "name": "Kitchen", "rules": rules}


def _state(value):
    """A minimal state-like object exposing only ``.state`` (what the handler reads)."""
    return SimpleNamespace(state=value)


# ---------------------------------------------------------------------------
# register() — malformed rule parsing
# ---------------------------------------------------------------------------

def _register_and_capture(hass, manager, monkeypatch):
    """Run register() with the state-tracker patched; return (captured_action,
    watched_entities, manager)."""
    captured = {}

    def _capture(_hass, entities, action):
        captured["action"] = action
        captured["entities"] = list(entities)
        return lambda: None

    monkeypatch.setattr(
        path_blockers, "async_track_state_change_event", _capture
    )
    _install(hass, manager)
    path_blockers.register(hass)
    return captured


@pytest.mark.parametrize(
    "rooms, expectation",
    [
        # [PB-1] room not a dict
        ({"1": ["not", "a", "dict"]}, set()),
        # [PB-1b] room is None
        ({"1": None}, set()),
        # [PB-2] rule not a dict
        ({"1": _room(["i-am-a-string", 42, None])}, set()),
        # [PB-3] disabled rule
        ({"1": _room([_blocker_rule(enabled=False)])}, set()),
        # [PB-4] kind != blocker
        ({"1": _room([_blocker_rule(kind="modifier")])}, set()),
        # [PB-4b] kind missing entirely
        ({"1": _room([{"id": "r", "enabled": True, "entity_id": _BLOCKER_ENTITY}])}, set()),
        # [PB-5] missing entity_id
        ({"1": _room([{"id": "r", "kind": "blocker", "enabled": True}])}, set()),
        # [PB-5b] blank/whitespace entity_id
        ({"1": _room([_blocker_rule(entity_id="   ")])}, set()),
        # [PB-7] valid blocker among bad rules -> the one watched entity
        (
            {
                "1": _room(
                    [
                        "garbage",
                        _blocker_rule(enabled=False),
                        _blocker_rule(kind="modifier"),
                        _blocker_rule(entity_id=""),
                        _blocker_rule(),  # the only good one
                    ]
                ),
                "2": "not-a-dict",
            },
            {_BLOCKER_ENTITY},
        ),
    ],
)
def test_register_skips_malformed_rules(hass, monkeypatch, rooms, expectation):
    """[PB-1..PB-5, PB-7] malformed rooms/rules are skipped; only real
    blocker entities end up watched, and registration always completes."""
    manager = _make_manager(rooms)
    captured = _register_and_capture(hass, manager, monkeypatch)

    if expectation:
        assert set(captured["entities"]) == expectation
        # exactly one unsub registered for the live watcher
        assert len(hass.data[DOMAIN][_PATH_BLOCKER_UNSUBS]) == 1
    else:
        # no entities -> no state tracker was created at all
        assert "entities" not in captured
        assert hass.data[DOMAIN][_PATH_BLOCKER_UNSUBS] == []

    # registration always wires the room-update callback exactly once
    assert _PATH_BLOCKER_ROOM_CALLBACK in hass.data[DOMAIN]
    manager.register_room_update_callback.assert_called_once()


def test_register_skips_unknown_map(hass, monkeypatch):
    """[PB-6] a map_id of 'unknown' is skipped before rooms are even read."""
    manager = _make_manager({"1": _room([_blocker_rule()])})
    manager.get_known_map_ids.return_value = ["unknown", "UNKNOWN", " Unknown "]

    captured = _register_and_capture(hass, manager, monkeypatch)

    # rooms never consulted for an unknown map -> empty watch_map
    manager._normalized_managed_rooms_with_automation.assert_not_called()
    assert "entities" not in captured
    assert hass.data[DOMAIN][_PATH_BLOCKER_UNSUBS] == []


def test_register_no_manager_is_noop(hass, monkeypatch):
    """[PB-8] manager absent -> register returns without registering anything."""
    # ensure clean slate
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].pop(_PATH_BLOCKER_UNSUBS, None)
    hass.data[DOMAIN].pop(_PATH_BLOCKER_ROOM_CALLBACK, None)

    tracker_called = {"n": 0}

    def _capture(_hass, entities, action):
        tracker_called["n"] += 1
        return lambda: None

    monkeypatch.setattr(path_blockers, "async_track_state_change_event", _capture)
    _install(hass, None)
    path_blockers.register(hass)

    assert tracker_called["n"] == 0
    assert _PATH_BLOCKER_ROOM_CALLBACK not in hass.data[DOMAIN]
    assert hass.data[DOMAIN].get(_PATH_BLOCKER_UNSUBS) in (None, [])


# ---------------------------------------------------------------------------
# _handle_path_blocker_change — event-handler early-outs
# ---------------------------------------------------------------------------

def _register_valid_and_get_handler(hass, manager, monkeypatch):
    """Register a single valid blocker rule and return the captured handler."""
    captured = _register_and_capture(hass, manager, monkeypatch)
    assert set(captured["entities"]) == {_BLOCKER_ENTITY}
    return captured["action"]


def _event(entity_id, old, new):
    """Build a state-change Event-like object the handler reads via event.data."""
    data = {
        "entity_id": entity_id,
        "old_state": _state(old) if old is not None else None,
        "new_state": _state(new) if new is not None else None,
    }
    return SimpleNamespace(data=data)


def test_event_unwatched_entity_ignored(hass, monkeypatch):
    """[PB-9] an event for an entity not in watch_map never reads the job."""
    manager = _make_manager({"1": _room([_blocker_rule()])})
    handler = _register_valid_and_get_handler(hass, manager, monkeypatch)

    handler(_event("binary_sensor.some_other", old="off", new="on"))

    manager.get_active_job.assert_not_called()
    manager.get_runtime_path_block_report.assert_not_called()


def test_event_missing_new_state_ignored(hass, monkeypatch):
    """[PB-10] new_state object missing -> early-out, no job read."""
    manager = _make_manager({"1": _room([_blocker_rule()])})
    handler = _register_valid_and_get_handler(hass, manager, monkeypatch)

    handler(_event(_BLOCKER_ENTITY, old="off", new=None))

    manager.get_active_job.assert_not_called()
    manager.get_runtime_path_block_report.assert_not_called()


def test_event_unchanged_state_ignored(hass, monkeypatch):
    """[PB-11] old_state == new_state -> early-out (no flap re-eval)."""
    manager = _make_manager({"1": _room([_blocker_rule()])})
    handler = _register_valid_and_get_handler(hass, manager, monkeypatch)

    handler(_event(_BLOCKER_ENTITY, old="on", new="on"))

    manager.get_active_job.assert_not_called()
    manager.get_runtime_path_block_report.assert_not_called()


async def test_event_manager_missing_at_event_time(hass, monkeypatch):
    """[PB-12] manager removed from hass.data after register -> handler bails
    before touching any job (it re-resolves DATA_RUNTIME live)."""
    manager = _make_manager({"1": _room([_blocker_rule()])})
    handler = _register_valid_and_get_handler(hass, manager, monkeypatch)

    # Manager disappears between registration and the event.
    hass.data[DOMAIN].pop(DATA_RUNTIME, None)

    handler(_event(_BLOCKER_ENTITY, old="off", new="on"))
    await hass.async_block_till_done()

    manager.get_active_job.assert_not_called()
    manager.get_runtime_path_block_report.assert_not_called()


async def test_event_report_not_dict_no_event_no_save(hass, monkeypatch):
    """[PB-13] report is None/not-a-dict -> nothing fired, nothing saved."""
    manager = _make_manager({"1": _room([_blocker_rule()])})
    manager.get_active_job.return_value = {"status": "started", "path_block_action": "event_only"}
    manager.get_runtime_path_block_report.return_value = None  # not a dict

    async def _save():
        return None

    manager.async_save.side_effect = _save

    handler = _register_valid_and_get_handler(hass, manager, monkeypatch)

    fired: list = []
    hass.bus.async_listen(EVENT_PATH_BLOCKED, lambda e: fired.append(e))

    handler(_event(_BLOCKER_ENTITY, old="off", new="on"))
    await hass.async_block_till_done()

    # the report WAS consulted...
    manager.get_runtime_path_block_report.assert_called_once()
    # ...but produced no actionable change.
    assert fired == []
    manager.async_save.assert_not_called()


async def test_event_no_changes_no_save(hass, monkeypatch):
    """[PB-14] every watched target returns a non-dict report -> any_changes
    stays False -> no save and no path-blocked event, even though a real,
    changed, watched event arrived."""
    # Two targets for the same entity, both returning junk reports.
    manager = spec_manager()
    manager.get_known_vacuum_ids.return_value = [_VAC]
    manager.get_known_map_ids.return_value = [_MAP, "7"]

    def _rooms(*, vacuum_entity_id, map_id):
        return {"1": _room([_blocker_rule()])}

    manager._normalized_managed_rooms_with_automation.side_effect = _rooms
    manager.get_active_job.return_value = {"status": "started", "path_block_action": "event_only"}
    manager.get_runtime_path_block_report.return_value = "not-a-dict"

    handler = _register_valid_and_get_handler(hass, manager, monkeypatch)

    fired: list = []
    hass.bus.async_listen(EVENT_PATH_BLOCKED, lambda e: fired.append(e))

    handler(_event(_BLOCKER_ENTITY, old="off", new="on"))
    await hass.async_block_till_done()

    # both watched (vac/map) targets were evaluated...
    assert manager.get_runtime_path_block_report.call_count == 2
    # ...yet nothing actionable -> no event, no save.
    assert fired == []
    manager.async_save.assert_not_called()


# ---------------------------------------------------------------------------
# L15 - the single-flight was integration-wide, not per entity
# ---------------------------------------------------------------------------

_BLOCKER_ENTITY_B = "binary_sensor.window_open"
_PATH_BLOCKER_INFLIGHT = "_path_blocker_inflight"


def _register_two_and_get_handler(hass, manager, monkeypatch):
    """Register with TWO watched entities and return the handler.

    Separate from `_register_valid_and_get_handler`, which asserts the watch_map holds
    exactly one entity — a good assertion for every other test here and the wrong one
    for the cross-entity case, which needs two by construction.
    """
    captured = _register_and_capture(hass, manager, monkeypatch)
    assert set(captured["entities"]) == {_BLOCKER_ENTITY, _BLOCKER_ENTITY_B}
    return captured["action"]


def _two_entity_manager() -> MagicMock:
    """Two rooms, each with a blocker rule on a DIFFERENT trigger entity."""
    return _make_manager({
        "1": {"room_id": 1, "name": "Kitchen",
              "rules": [_blocker_rule(_BLOCKER_ENTITY, id="rule-a")]},
        "2": {"room_id": 2, "name": "Study",
              "rules": [_blocker_rule(_BLOCKER_ENTITY_B, id="rule-b")]},
    })


async def test_pb15_an_edge_on_another_entity_is_not_swallowed(hass, monkeypatch):
    """[PB-15] RED BEFORE THE FIX.

    Entity A's evaluation is held open; while it is running, entity B fires. Under the
    integration-wide flag B set `rerun` and returned, A's loop then re-ran A a second
    time, and B was never evaluated — silently. Two door sensors on different maps is
    enough to reach it.

    Asserted on the TRIGGER ENTITY the manager was asked about, not on a call count:
    a count cannot tell "B was evaluated" from "A was evaluated twice", which is
    precisely the confusion the old flag produced.
    """
    manager = _two_entity_manager()
    handler = _register_two_and_get_handler(hass, manager, monkeypatch)

    seen: list[str] = []

    def _report(**kwargs):
        seen.append(kwargs.get("trigger_entity_id"))
        return {}

    manager.get_runtime_path_block_report.side_effect = _report

    handler(_event(_BLOCKER_ENTITY, old="off", new="on"))
    handler(_event(_BLOCKER_ENTITY_B, old="off", new="on"))
    await hass.async_block_till_done()

    assert _BLOCKER_ENTITY_B in seen, (
        f"the second entity's edge was never evaluated: {seen}"
    )
    assert _BLOCKER_ENTITY in seen


async def test_pb16_a_burst_on_one_entity_still_coalesces(hass, monkeypatch):
    """[PB-16] RED IF THE SINGLE-FLIGHT IS REMOVED RATHER THAN RE-KEYED.

    GUARD-2 exists because a burst of edges on one sensor used to spawn one unbounded
    task per event. Fixing the cross-entity drop by deleting the flag would trade this
    defect for the one it replaced, so this counts EVALUATIONS, not flag state — the
    first draft asserted `running is False` at the end, which is equally true when the
    flag is never consulted, and a "drop the single-flight" ablation sailed through it.

    Five edges are dispatched while the first evaluation is held open. Coalesced that
    is 2 evaluations (one running + one queued re-check); unbounded it is 5.
    """
    manager = _two_entity_manager()
    handler = _register_two_and_get_handler(hass, manager, monkeypatch)

    gate = asyncio.Event()
    evaluations = 0

    def _report(**kwargs):
        nonlocal evaluations
        evaluations += 1
        # A truthy report drives the blocked branch, which sets any_changes and makes
        # _process reach the `await async_save()` below -- the only yield point in the
        # whole evaluation. Without a yield the tasks never overlap and a single-flight
        # cannot be observed at all, which is what made the first draft of this test
        # pass against an ablated flag.
        return {"blocked": True, "rooms": [1]}

    manager.get_runtime_path_block_report.side_effect = _report

    async def _slow_save():
        await gate.wait()

    manager.async_save.side_effect = _slow_save

    for state in ("on", "off", "on", "off", "on"):
        handler(_event(_BLOCKER_ENTITY, old="off" if state == "on" else "on", new=state))
    await asyncio.sleep(0)          # let the queued tasks start and block on the gate
    gate.set()
    await hass.async_block_till_done()

    assert evaluations <= 2, (
        f"a burst on one entity spawned {evaluations} evaluations; GUARD-2's bound is "
        "one running plus one queued re-check"
    )
    assert evaluations >= 1


async def test_pb17_remove_drops_the_per_entity_state(hass, monkeypatch):
    """[PB-17] RED IF remove() FORGETS IT.

    The old form was one key, rewritten on every register, so leaving it behind cost
    nothing. A per-entity map grows per register/remove cycle — and a `running: True`
    left by a task killed mid-flight would wedge that entity's evaluations off for the
    rest of the session.
    """
    manager = _two_entity_manager()
    handler = _register_two_and_get_handler(hass, manager, monkeypatch)
    manager.get_runtime_path_block_report.return_value = {}
    handler(_event(_BLOCKER_ENTITY, old="off", new="on"))
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].get(_PATH_BLOCKER_INFLIGHT)

    path_blockers.remove(hass)

    assert _PATH_BLOCKER_INFLIGHT not in hass.data[DOMAIN]
