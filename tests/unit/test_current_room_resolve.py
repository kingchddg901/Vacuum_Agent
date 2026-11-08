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
[CRR-7] a non-dict row in the stored registry is skipped, and a match AFTER it still
        resolves (junk rows FIRST, by position).
[CRR-8] a matched room whose stored room_id will not parse resolves to None, not to a
        raw string and not by raising -- both except arms driven.
"""

from __future__ import annotations

import pytest

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


# ---------------------------------------------------------------------------
# [CRR-7] - [CRR-8]  the managed-room registry is STORED data, so its rows are
# outside data even though its producer is in this repo.
#
# WHAT AN EXCEPTION OUT OF THIS RESOLVER ACTUALLY COSTS, measured at both call
# sites rather than assumed, because the two differ and the worse one is not the
# obvious one:
#
#   * `mapping/map_source_coordinator.py` calls it INSIDE the refresh's blanket
#     `except Exception:` whose handler logs and serves an ABSENT MARKER for the
#     whole frame. So the cost is not a missing highlight -- `_commit_result` is
#     skipped and the card's map goes dark entirely.
#   * `listeners/pose_sampler.py` calls it outside its own pose `try`, so the
#     exception rides up to POSE-5's per-vacuum except: that tick's sample is lost
#     and logged, and the next tick retries.
#
# One junk row in the stored registry therefore blanks a map rather than skipping a
# room, which is why these guards are tested and not classified as plumbing.
# ---------------------------------------------------------------------------


def test_crr7_a_corrupt_room_row_does_not_hide_a_later_match():
    """[CRR-7] A non-dict row in the managed-room registry is skipped, and the real
    room AFTER it still resolves.

    THE JUNK ROWS COME FIRST ON PURPOSE -- `continue` and `break` are
    indistinguishable when the bad row is last, so the matched room is what proves the
    walk resumed rather than quietly stopped.

    The registry is read back from `.storage`, so a row that is not a dict is what a
    hand-edited store, an interrupted write, or a build that keyed this bucket
    differently leaves behind -- not something an in-process producer would emit today.

    RED: delete the guard and `"corrupt".get("slug")` raises AttributeError, which
    reaches the map coordinator's blanket except and blanks the frame (see above).
    """
    rooms = {
        1: "corrupt",
        2: None,
        3: ["not", "a", "room"],
        4: 17,
        7: {"room_id": 7, "name": "Dining Room"},
    }
    assert _resolve("Dining Room", rooms) == 7, (
        "the match after four junk rows was not reached"
    )


@pytest.mark.parametrize("stored_id,arm", [
    pytest.param(None, "TypeError -- and NOT the CRR-6 key fallback: `.get` only "
                       "defaults on an ABSENT key, so a key present with a null "
                       "value yields None", id="null"),
    pytest.param("kitchen", "ValueError", id="word"),
    pytest.param("", "ValueError", id="empty"),
    pytest.param([3], "TypeError", id="list"),
])
def test_crr8_a_match_whose_room_id_will_not_parse_resolves_to_none(stored_id, arm):
    """[CRR-8] The slug matched, and the room's stored id is not a number.

    Both arms of the `except (TypeError, ValueError)` are driven, not whichever came to
    mind: a string and an empty string raise ValueError, None and a list raise
    TypeError. Narrowing the tuple to either reddens the other rows.

    This is the one failure mode where the room was FOUND -- the brand's live
    current-room name matched a managed room -- and the answer still has to be None.
    Returning the raw value instead would put a string into the render frame's
    `current_room`, which the card uses as a raster room id, and into the pose ring's
    per-room split key.

    `return` rather than `continue` is indistinguishable here and deliberately not
    asserted: RP-015 guarantees slugs are unique within a map, so there is no second
    room with this slug for a `continue` to reach. Pinning one spelling would assert a
    preference.

    RED: delete the `except` and this raises straight out of the resolver; narrow it to
    one error class and the other two rows go red.
    """
    rooms = {7: {"room_id": stored_id, "name": "Dining Room"}}
    assert _resolve("Dining Room", rooms) is None, f"expected the {arm} arm to answer"

    # CONTROL: same room, same name, a parseable id -- so "None" above is the except
    # answering and not a match that never happened.
    assert _resolve("Dining Room", {7: {"room_id": "7", "name": "Dining Room"}}) == 7
