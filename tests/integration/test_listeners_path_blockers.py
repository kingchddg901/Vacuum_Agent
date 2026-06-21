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
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
    manager = MagicMock()
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
    manager = MagicMock()
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
