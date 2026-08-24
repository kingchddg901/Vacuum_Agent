"""Entity-rename detection (D4) — a managed vacuum's entity id is a storage address.

Renaming one strands seventeen store sections plus the learning tree, and until this
listener existed nothing noticed. These cover the DECISIONS, which is where the
behaviour is: what counts as a rename, whose rename we care about, and what is kept.

Coverage targets
----------------
[ER-1] a managed vacuum's rename is recorded, with BOTH ids — the old one exists
       nowhere else once the registry has moved on, so this is its only capture.
[ER-2] an update that did not touch entity_id is ignored — the common case by far.
[ER-3] a rename of something we do not manage is ignored.
[ER-4] create/remove are not renames.
[ER-5] two renames APPEND. A dict keyed by vacuum would let the second overwrite the
       first and leave a pair whose old half nothing can resolve.
[ER-6] the check is against the OLD id. By the time this fires the registry already
       holds the new one, and the new one is precisely what we have never seen.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.listeners import entity_rename

from .._factories import spec_manager


class _Bus:
    """The two things this listener asks of the bus, and nothing else.

    A real stub rather than a mock: the listener is production code being handed
    this, and a bare mock would agree with whatever it called — including a bus
    method that does not exist.
    """

    def __init__(self) -> None:
        self.subscribed: list[tuple[str, object]] = []
        self.unsubscribed = 0

    def async_listen(self, event_type, cb):
        self.subscribed.append((event_type, cb))

        def _unsub() -> None:
            self.unsubscribed += 1

        return _unsub


class _Hass:
    def __init__(self) -> None:
        self.data: dict = {}
        self.bus = _Bus()


def _wire(managed: list[str]) -> tuple[_Hass, object, dict]:
    """Register the listener and hand back the callback it subscribed."""
    hass = _Hass()
    data = {"vacuums": {v: {"vacuum_entity_id": v} for v in managed}}
    hass.data = {DOMAIN: {DATA_RUNTIME: spec_manager(data=data)}}
    entity_rename.register(hass)
    assert hass.bus.subscribed, "the listener subscribed to nothing"
    return hass, hass.bus.subscribed[-1][1], data


def _event(action="update", entity_id="vacuum.new", changes=None):
    return SimpleNamespace(
        data={"action": action, "entity_id": entity_id, **({"changes": changes} if changes is not None else {})}
    )


def test_er1_managed_rename_is_recorded_with_both_ids():
    """[ER-1] Once HA has renamed the entity the old id exists nowhere else. If this
    moment is not captured, a later repair pass cannot learn what the data was called."""
    hass, cb, data = _wire(["vacuum.alfred"])
    cb(_event(entity_id="vacuum.alfred_2", changes={"entity_id": "vacuum.alfred"}))

    pending = data[entity_rename.PENDING_RENAMES]
    assert len(pending) == 1
    assert pending[0]["old_entity_id"] == "vacuum.alfred"
    assert pending[0]["new_entity_id"] == "vacuum.alfred_2"
    assert pending[0]["applied"] is False
    assert pending[0]["detected_at"]


@pytest.mark.parametrize(
    "changes",
    [
        {"icon": "mdi:robot"},            # a cosmetic update
        {"name": "Alfred"},               # a friendly-name change
        {},                               # an update that moved nothing we can see
    ],
)
def test_er2_an_update_that_did_not_move_entity_id_is_ignored(changes):
    """[ER-2] `changes` carries the PREVIOUS value of each field that moved. Anything
    without entity_id in it is not a rename, and this is the overwhelmingly common event."""
    hass, cb, data = _wire(["vacuum.alfred"])
    cb(_event(entity_id="vacuum.alfred", changes=changes))
    assert entity_rename.PENDING_RENAMES not in data


def test_er3_a_rename_we_do_not_manage_is_ignored():
    """[ER-3] Every vacuum in the house fires this event. Only ours addresses our store."""
    hass, cb, data = _wire(["vacuum.alfred"])
    cb(_event(entity_id="vacuum.somebody_else_2", changes={"entity_id": "vacuum.somebody_else"}))
    assert entity_rename.PENDING_RENAMES not in data


@pytest.mark.parametrize("action", ["create", "remove"])
def test_er4_create_and_remove_are_not_renames(action):
    """[ER-4] A removal is a different event with a different repair; do not conflate."""
    hass, cb, data = _wire(["vacuum.alfred"])
    cb(_event(action=action, entity_id="vacuum.alfred", changes={"entity_id": "vacuum.alfred"}))
    assert entity_rename.PENDING_RENAMES not in data


def test_er5_two_renames_append_rather_than_overwrite():
    """[ER-5] a->b then b->c is TWO facts. Keyed by vacuum, the second would overwrite
    the first and `a` would become unresolvable — the exact loss this exists to prevent."""
    hass, cb, data = _wire(["vacuum.a"])
    cb(_event(entity_id="vacuum.b", changes={"entity_id": "vacuum.a"}))
    data["vacuums"]["vacuum.b"] = {"vacuum_entity_id": "vacuum.b"}   # HA moved on
    cb(_event(entity_id="vacuum.c", changes={"entity_id": "vacuum.b"}))

    pending = data[entity_rename.PENDING_RENAMES]
    assert [(p["old_entity_id"], p["new_entity_id"]) for p in pending] == [
        ("vacuum.a", "vacuum.b"),
        ("vacuum.b", "vacuum.c"),
    ]


def test_er6_the_managed_check_is_against_the_old_id():
    """[ER-6] RED IF THE CHECK MOVES TO THE NEW ID: the new id is by definition one we
    have never stored, so every real rename would be dropped as 'not ours'."""
    hass, cb, data = _wire(["vacuum.alfred"])          # only the OLD id is managed
    cb(_event(entity_id="vacuum.brand_new", changes={"entity_id": "vacuum.alfred"}))
    assert len(data[entity_rename.PENDING_RENAMES]) == 1


def test_remove_is_idempotent_and_unsubscribes():
    hass, _cb, _data = _wire(["vacuum.alfred"])
    assert "_entity_rename_unsub" in hass.data[DOMAIN]
    entity_rename.remove(hass)
    assert "_entity_rename_unsub" not in hass.data[DOMAIN]
    entity_rename.remove(hass)   # second call is a no-op, not an error
