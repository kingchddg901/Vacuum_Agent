"""Per-vacuum state may only exist for a vacuum this install actually has.

Two records reached a live install because nothing ever asked whether the id referred
to anything:

  onboarding["vacuum.your_vacuum"]  the CARD'S OWN PLACEHOLDER (src/main.js), persisted
                                    because a status QUERY created the record it asked
                                    about — a read that writes
  setup_progress["vacuum.iv"]       a truncated entity id carrying a full
                                    completed_steps / room_drift_history record

Neither corrupted anything, which is exactly why they sat there. The defect is that the
set only ever grew: every typo, placeholder and renamed entity left a record nothing
reaps, and "which vacuums does this install have?" stopped having a single answer.

Coverage targets
----------------
[VI-1] a vacuum HA knows is real, even with no stored record (a NEW vacuum).
[VI-2] a vacuum with a stored record is real, even if HA no longer knows it (RENAMED
       or removed — its history must stay addressable).
[VI-3] a placeholder / typo is not real.
[VI-4] the sweep removes exactly the orphans and nothing else.
[VI-5] the sweep can never remove from `vacuums` itself — presence there IS the proof.
[VI-6] the sweep runs once.
[VI-7] planning is pure: it mutates nothing.
[VI-8] a bucket that is not a dict is skipped rather than raising on boot.
[VI-9] a REGISTERED vacuum with no state is real — an offline one must not be swept.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum.core.vacuum_identity import (
    SWEEP_KEY,
    is_real_vacuum,
    orphaned_vacuum_keys,
    plan_orphan_sweep,
    sweep_orphaned_vacuums,
)

_REAL = "vacuum.alfred"
_GONE = "vacuum.retired"
_FAKE = "vacuum.your_vacuum"      # the card's placeholder
_TYPO = "vacuum.iv"


class _States:
    """Minimal hass.states stand-in — only `.get` is consulted."""

    def __init__(self, known):
        self._known = set(known)

    def get(self, entity_id):
        return object() if entity_id in self._known else None


def _hass(known=()):
    return SimpleNamespace(states=_States(known))


def _data(**buckets):
    base = {"vacuums": {}, "maps": {}, "active_jobs": {}}
    base.update(buckets)
    return base


def test_vi_1_a_vacuum_hass_knows_is_real_even_with_no_record():
    """[VI-1] A brand-new vacuum has no stored record yet — it must still be addable.

    This is why the predicate is NOT "already known to the manager": that would make
    adding a vacuum impossible, since a new one is by definition not yet known.
    """
    assert is_real_vacuum(_hass([_REAL]), _data(), _REAL) is True


def test_vi_2_a_stored_record_is_proof_even_if_hass_forgot():
    """[VI-2] The reverse: an entity renamed or removed in HA keeps its history.

    Without this the sweep would delete a real vacuum's data the moment its entity id
    changed — turning a cosmetic rename into silent data loss.
    """
    assert is_real_vacuum(_hass([]), _data(vacuums={_GONE: {}}), _GONE) is True
    assert is_real_vacuum(_hass([]), _data(maps={_GONE: {}}), _GONE) is True


@pytest.mark.parametrize("bogus", [_FAKE, _TYPO, "not_an_entity", "", "sensor.alfred"])
def test_vi_3_a_placeholder_or_typo_is_not_real(bogus):
    """[VI-3] Nothing HA has and nothing we stored — the case that shipped."""
    assert is_real_vacuum(_hass([_REAL]), _data(vacuums={_REAL: {}}), bogus) is False


def test_vi_4_the_sweep_removes_exactly_the_orphans():
    """[VI-4] Both live orphans go; the real vacuum's records are untouched."""
    data = _data(
        vacuums={_REAL: {"x": 1}},
        onboarding={_REAL: {"1": {}}, _FAKE: {"1": {}}},
        setup_progress={_REAL: {"completed_steps": ["add_vacuum"]}, _TYPO: {"completed_steps": []}},
    )
    result = sweep_orphaned_vacuums(_hass([_REAL]), data)

    assert result["ran"] is True
    assert sorted(result["removed"]) == [
        ("onboarding", _FAKE), ("setup_progress", _TYPO),
    ]
    assert set(data["onboarding"]) == {_REAL}
    assert set(data["setup_progress"]) == {_REAL}
    assert data["vacuums"][_REAL] == {"x": 1}, "a real vacuum's data was touched"


def test_vi_5_the_sweep_can_never_empty_the_vacuums_bucket():
    """[VI-5] `vacuums` is self-protecting — presence there IS proof of realness.

    Worth pinning explicitly: `vacuums` is in the swept bucket list, so if the
    predicate ever stopped treating a stored record as proof, this sweep would delete
    every vacuum on the install. That is the worst thing this code could do.
    """
    data = _data(vacuums={_REAL: {}, _GONE: {}})
    sweep_orphaned_vacuums(_hass([]), data)
    assert set(data["vacuums"]) == {_REAL, _GONE}


def test_vi_6_the_sweep_runs_once():
    """[VI-6] A user who deliberately re-creates something must not have it re-reaped."""
    data = _data(vacuums={_REAL: {}}, onboarding={_FAKE: {}})
    first = sweep_orphaned_vacuums(_hass([_REAL]), data)
    assert first["ran"] is True and first["removed"]
    assert data["migrations"][SWEEP_KEY] is True

    data["onboarding"][_FAKE] = {}
    second = sweep_orphaned_vacuums(_hass([_REAL]), data)
    assert second["ran"] is False and second["removed"] == []
    assert _FAKE in data["onboarding"]


def test_vi_7_planning_mutates_nothing():
    """[VI-7] The dry run is how this gets reviewed before it deletes user data."""
    data = _data(vacuums={_REAL: {}}, onboarding={_FAKE: {}, _REAL: {}})
    before = {k: dict(v) for k, v in data.items() if isinstance(v, dict)}

    planned = plan_orphan_sweep(_hass([_REAL]), data)

    assert planned == [("onboarding", _FAKE)]
    assert {k: dict(v) for k, v in data.items() if isinstance(v, dict)} == before
    assert "migrations" not in data


def test_vi_8_a_bucket_that_is_not_a_dict_is_skipped():
    """[VI-8] Malformed storage must not raise during setup — an unreadable bucket is
    left alone rather than taking the integration down on boot."""
    assert orphaned_vacuum_keys(_hass([]), {"onboarding": "corrupt"}, "onboarding") == []
    assert orphaned_vacuum_keys(_hass([]), {}, "missing") == []


async def test_vi_9_a_registered_vacuum_with_no_state_is_real(hass):
    """[VI-9] An offline or disabled vacuum is real — the ENTITY REGISTRY arm.

    A vacuum that is powered off, unavailable, or simply not loaded yet has NO STATE
    while its entity is perfectly real. `hass.states.get` answers None for it, so the
    state check cannot decide, and the registry is the only thing standing between a
    sleeping vacuum and a sweep that deletes its records.

    ⚠ THE FIXTURE TRAP, and the reason the precondition below is an assertion rather
    than a comment: if this test also set a state for the entity, the state arm would
    return True first, the registry block would never execute, and the test would go on
    passing with that whole block DELETED. `hass.states.get(...) is None` is what forces
    the only path that can answer here.

    The second assertion is the discriminator: same hass, same empty data, an id the
    registry has never heard of. Without it, a registry lookup that returned something
    for every string would satisfy the first assertion.

    RED: delete the `er.async_get(hass).async_get(...)` block and the first assertion
    returns False.
    """
    from homeassistant.helpers import entity_registry as er

    # A real Eufy vacuum entity is created by `robovac_mqtt`; the platform is what a
    # genuine install carries, so the fixture is shaped like one rather than invented.
    asleep = er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "asleep_unique_id", suggested_object_id="asleep",
    ).entity_id

    assert hass.states.get(asleep) is None, (
        "precondition: NO state, or the state arm answers and the registry never runs"
    )

    assert is_real_vacuum(hass, _data(), asleep) is True
    assert is_real_vacuum(hass, _data(), "vacuum.never_registered") is False


# ---------------------------------------------------------------------------
# NOT TESTED — `vacuum_identity.py::is_real_vacuum`'s `if hass is None: return False`
#
# SUBSUMED, red set deliberately EMPTY. With the guard ablated, `getattr(None,
# "states", None)` skips the state arm and `er.async_get(None)` raises inside the
# try below it, whose blanket except returns False — the same answer, by a longer
# road. Measured over 8 inputs (hass None with and without a stored record, with a
# bad prefix, a maps-only record, a hass with no `.states`, `.states` None, a hass
# that knows the entity, one that does not): every answer identical, no exception
# escaping either way. No input can make a test of it red, so writing one would
# assert a preference and read as coverage.
# ---------------------------------------------------------------------------
