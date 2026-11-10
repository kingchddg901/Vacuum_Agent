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
[VI-10] a non-dict bucket contributes NOTHING to a delete plan — the filter that makes
       the sweep loop's own type re-check unreachable.
[VI-11] `hass=None` — the bare-manager fallback the docstring promises: a stored record
       is still proof, an unknown id is still rejected, and neither raises.
[VI-12] a `hass` with no `states` at all is tolerated rather than dereferenced.
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


def test_vi_10_a_non_dict_bucket_never_reaches_the_sweep_loop():
    """[VI-10] WHY `sweep_orphaned_vacuums`' OWN `isinstance(node, dict)` IS UNREACHABLE.

    The type check exists TWICE: once in `orphaned_vacuum_keys`, which [VI-8] pins, and
    once again inside the sweep's own delete loop. The second can never see a non-dict,
    because every (bucket, key) it iterates came from the first -- which returns `[]`
    for a bucket that is not a dict, so such a bucket contributes no keys to plan. The
    only way to reach the re-check would be for `data[bucket]` to change type between
    planning and deleting, and the plan is built four lines above the loop over the same
    dict.

    That makes the re-check's unreachability a PROPERTY OF THE FILTER rather than of
    the loop, so the filter is what gets pinned. Recorded instead of
    `pragma: no cover`d, because an unreachable guard whose reason is undocumented is
    the one that gets "simplified" away later.

    A LIST, NOT A STRING, AND THAT IS THE DIFFERENCE FROM [VI-8]. [VI-8] passes the
    bucket `"corrupt"`; iterating that string yields single characters, none of which
    start with `vacuum.`, so it answers `[]` with the filter REMOVED as well -- that
    assertion cannot see this guard at all, and [VI-8] bites only through its second
    row, where `for key in None` raises. A list of entity-id-shaped strings is the
    shape that would silently produce PLAUSIBLE orphan keys, which is what a sweep
    that DELETES USER DATA must not be handed.

    RED: relax the filter from `isinstance(node, dict)` to a None check and the list's
    entry is planned for deletion. [VI-8] stays green on that ablation, which is the
    measurement that says this test is not a duplicate of it.
    """
    data = _data(
        vacuums={_REAL: {}},
        onboarding=[_FAKE],               # a LIST where a per-vacuum dict belongs
        setup_progress={_TYPO: {}},       # control: a real orphan, in a real dict
    )

    planned = plan_orphan_sweep(_hass([_REAL]), data)

    assert planned == [("setup_progress", _TYPO)], (
        f"a non-dict bucket contributed keys to a delete plan: {planned}"
    )

    # And the sweep over that same data removes the control and leaves the list alone.
    result = sweep_orphaned_vacuums(_hass([_REAL]), data)
    assert result["removed"] == [("setup_progress", _TYPO)]
    assert data["onboarding"] == [_FAKE], "the unreadable bucket was mutated"


# ---------------------------------------------------------------------------
# NOT TESTED -- `vacuum_identity.py::is_real_vacuum`'s `if hass is None: return False`
#
# SUBSUMED, red set deliberately EMPTY. With the guard ablated, `getattr(None,
# "states", None)` skips the state arm and `er.async_get(None)` raises inside the
# try below it, whose blanket except returns False -- the same answer, by a longer
# road. Measured over 8 inputs (hass None with and without a stored record, with a
# bad prefix, a maps-only record, a hass with no `.states`, `.states` None, a hass
# that knows the entity, one that does not): every answer identical, no exception
# escaping either way. No input can make a test of it red, so writing one would
# assert a preference and read as coverage.
#
# NOT TESTED -- the FALSE arm of `if getattr(hass, "states", None) is not None:`
#
# DEFENSIVE, and its only producer is a test harness. A real `HomeAssistant` sets
# `.states` in its constructor and never clears it, and both call sites pass one:
# `onboarding/manager.py` its `self._hass` and `setup/drift.py` the hass it was
# handed. The docstring is explicit that the fallback is for "tests constructing a
# bare manager", so a test of it would be a test of `_hass()`. Not subsumed -- with
# the guard removed a `.states`-less object raises AttributeError outside the try
# below -- but the input cannot arrive from anywhere this integration runs.
#
# NOT TESTED -- the FALSE arm of `isinstance(node, dict)` inside
# `sweep_orphaned_vacuums`
#
# UNREACHABLE; see [VI-10] above, which pins the filter that makes it so.
#
# THE ARITHMETIC THESE THREE LEAVE: 1 statement and 3 branch arms uncovered of 64
# units, so the file measures 93.75% and cannot honestly reach 95% -- closing even
# one would take a vacuous test or a pragma on a non-logger line. Stated here rather
# than papered over.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# [VI-11]/[VI-12] the two harness-tolerance guards. The module's own docstring
# promises an "unknown hass" falls back to the stored record "rather than rejecting
# everything", and both guards are written with that in mind.
# ---------------------------------------------------------------------------

def test_vi_11_a_none_hass_falls_back_to_the_stored_record():
    """[VI-11] `hass=None`, asserted as the asymmetry the docstring describes.

    The promise is not "returns False"; it is that the stored record ALONE still
    decides. So the pair is what matters: with no hass at all a vacuum we have
    records for is still real, and one we do not is still rejected. Asserting only
    the False half would be satisfied by a function that rejected everything, which
    is precisely the behaviour the guard exists to avoid.

    THE GUARD'S EXISTENCE IS UNOBSERVABLE; ITS VERDICT IS NOT. Measured: replacing
    `if hass is None: return False` with `if False` keeps this green, because
    `getattr(None, "states", None)` is None and the registry lookup below then raises
    into the broad `except` and returns False anyway -- the same answer by a longer
    road. So the named red input is the guard answering WRONGLY: `return True` in
    place of `return False` reddens the unknown-id assertion while leaving the
    stored-record one untouched, which is the asymmetry this test exists for.

    Worth being exact about, because the obvious candidate does not reach: narrowing
    the `except Exception` below cannot affect this test at all, since a None hass
    returns two lines ABOVE the try and never enters it.
    """
    stored = _data(vacuums={_GONE: {}})
    assert is_real_vacuum(None, stored, _GONE) is True, (
        "a stored record stopped being proof once hass was unknown"
    )
    assert is_real_vacuum(None, stored, _FAKE) is False
    assert is_real_vacuum(None, _data(), _REAL) is False


def test_vi_12_a_hass_with_no_states_is_tolerated_not_dereferenced():
    """[VI-12] The `getattr(hass, "states", None)` guard, which is not decoration.

    Every other test in this file passes a `SimpleNamespace` carrying `states`, so
    the FALSE arm of that guard -- a hass object without the attribute at all -- had
    never been taken. It is the shape a partially-built harness or a stand-in object
    has, and the guard is why it gets a verdict instead of an AttributeError.

    THE STORED-RECORD HALF IS THE CONTROL: the same stateless hass still resolves a
    vacuum we have records for, which separates "tolerated the missing attribute"
    from "gave up on everything". Removing the guard (`if True:`) reddens this by
    raising on `hass.states`, which is the named red input.
    """
    stateless = SimpleNamespace()

    assert is_real_vacuum(stateless, _data(maps={_GONE: {}}), _GONE) is True
    assert is_real_vacuum(stateless, _data(), _FAKE) is False
