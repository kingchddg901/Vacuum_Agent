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
