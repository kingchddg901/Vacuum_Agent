"""Unit tests for rooms/current_room.py — the native current-room NAME → managed id resolver.

ONE resolver now answers "which managed room is the robot's live native current-room?" for
BOTH the pose_sampler attribution path and the map render-frame highlight (previously the
highlight had no source for a camera_attrs brand and stayed dark). A third, deliberately
different variant lives on ActiveJobTracker (matches the job QUEUE) and is NOT unified here.

Coverage targets
----------------
[CRR-1] a native NAME matching a managed room resolves to its room_id.
[CRR-2] slug normalization: '&'/case/space differences still match (Heidi & Chris).
[CRR-3] a name not among managed rooms (dock / transit) -> None.
[CRR-4] no active_cleaning_target entity declared -> None.
[CRR-5] entity missing / unavailable / unknown / empty / sentinel -> None.
[CRR-6] room_id falls back to the dict KEY when the room lacks an explicit room_id.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.rooms.current_room import resolve_native_current_room_id

_ENT = "sensor.robin_current_room"
_CFG = {"entities": {"active_cleaning_target": _ENT}}


class _State:
    def __init__(self, state):
        self.state = state


class _States:
    def __init__(self, mapping):
        self._m = mapping

    def get(self, entity_id):
        return self._m.get(entity_id)


class _Hass:
    def __init__(self, states):
        self.states = _States(states)


class _Manager:
    def __init__(self, rooms):
        self._rooms = rooms

    def get_managed_rooms(self, *, vacuum_entity_id, map_id):
        return {"rooms": self._rooms}


def _resolve(state_value, rooms, cfg=_CFG):
    states = {_ENT: _State(state_value)} if state_value is not None else {}
    return resolve_native_current_room_id(
        _Hass(states), _Manager(rooms), "vacuum.robin", cfg, "Main"
    )


def test_matches_managed_room_by_name():
    """[CRR-1] Dining Room resolves to 7. BITE: rename the sensor to a name no managed room
    carries and this flips to None (see CRR-3)."""
    assert _resolve("Dining Room", {7: {"room_id": 7, "name": "Dining Room"}}) == 7


def test_slug_normalization_matches():
    """[CRR-2] '&' -> 'and', case and spacing folded, so the live name and the stored name
    reconcile on slug rather than exact string."""
    assert _resolve("heidi and chris", {5: {"room_id": 5, "name": "Heidi & Chris"}}) == 5


def test_unmatched_name_is_none():
    """[CRR-3] a name not among the managed rooms (the dock room, a transit room) -> None,
    which the highlight reads as 'draw nothing' and attribution reads as 'transit'."""
    assert _resolve("Garage", {7: {"room_id": 7, "name": "Dining Room"}}) is None


def test_no_entity_declared_is_none():
    """[CRR-4] a brand without a declared active_cleaning_target has no native signal -> None."""
    assert _resolve("Dining Room", {7: {"room_id": 7, "name": "Dining Room"}},
                    cfg={"entities": {}}) is None


def test_sentinel_states_are_none():
    """[CRR-5] a momentarily unavailable/unknown/empty/sentinel entity -> None (never a room)."""
    rooms = {7: {"room_id": 7, "name": "Dining Room"}}
    assert _resolve(None, rooms) is None            # entity absent from the state machine
    for sentinel in ("unavailable", "unknown", "", "None", "null"):
        assert _resolve(sentinel, rooms) is None


def test_room_id_falls_back_to_key():
    """[CRR-6] a managed room lacking an explicit room_id resolves to its dict KEY, so a
    registry that keys by id without repeating it inside the value still resolves."""
    assert _resolve("Dining Room", {7: {"name": "Dining Room"}}) == 7
