"""Phase 5 integration tests — listeners/_common.py pure helpers.

Coverage targets
----------------
[LC-1]  get_adapter_vocab returns fallback when no adapter is registered.
[LC-2]  get_adapter_vocab returns frozenset from registered adapter.
[LC-3]  get_adapter_vocab handles missing section gracefully.
[LC-4]  get_adapter_value returns fallback when no adapter is registered.
[LC-5]  get_adapter_value returns nested value from registered adapter.
[LC-6]  get_adapter_value returns fallback for missing intermediate key.
[LC-7]  get_lifecycle_watch_entities returns only vacuum when no adapter.
[LC-8]  get_lifecycle_watch_entities includes adapter-declared entities.
[LC-9]  completed_finalize_signals returns empty strings for absent states.
[LC-10] completed_finalize_signals reads live hass entity states.
[LC-11] job_finished_event_data returns correct vacuum/map fields.
[LC-12] job_finished_event_data defaults status to "completed".
[LC-13] job_finished_event_data reads outcome from nested structure.
[LC-14] job_finished_event_data tolerates None finalize_result.
[LC-15] L9: an UNAVAILABLE job_active binary is not a signal to trust. Built
        through completed_finalize_signals, not hand-assembled -- every existing
        test passes job_active_present as a dict literal, which is exactly why
        this survived three rounds of tightening the same gate.
[LC-16] L9: the trustworthy reading still short-circuits. A gate fixed by never
        being satisfied is a worse defect wearing the opposite sign.
[LC-17] L10: `_state` does NOT collapse indeterminates, and must not start.
        The docstring claimed it did; the fix was to correct the docstring and
        strengthen the ONE key that relied on the collapse -- not to collapse
        inside `_state`, which would silently retune four other keys whose
        adapters already name the indeterminate values themselves.
[LC-18] `unavailable_is_active` reads an UNREADABLE job_active binary as still
        active for the finalize gate and as strict not-on for the arming gate.
        The opposite answers ARE the claim.
[LC-19] a section whose value is not a dict still returns the fallback -- the
        input that actually tests `get_adapter_vocab`'s "Never raises" promise,
        which the missing-section cases do not.
[LC-20] `is_dock_trigger_edge` distinguishes NO READING from the word "none".
        A CONTRACT test: measured, no shipped dock_events.triggers vocabulary
        contains "none", so the guard is subsumed against every brand that ships
        today and only a vocabulary containing it can make the test bite.

⚠ [LC-1] / [LC-4] / [LC-7] SAID "no adapter registered" AND DID NOT MEAN IT.
All three asked about `_VAC` while taking the `manager` fixture, which registers
`TEST_ADAPTER_CONFIG` for `vacuum.alfred`. They passed on the missing-section and
missing-entities paths instead, so the genuine no-adapter path had no coverage at
all -- `_common.py` line 77 sat in coverage's missing lines and deleting that guard
reddened 0 of 33 tests here. They now use `_UNREGISTERED`, and [LC-1b] keeps the
registered-but-silent case they were really covering. Anything asserting
unregistered behaviour must use `_UNREGISTERED`, never `_VAC`.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.listeners._common import (
    completed_finalize_signals,
    completion_secondary_satisfied,
    get_adapter_value,
    get_adapter_vocab,
    get_lifecycle_watch_entities,
    is_dock_trigger_edge,
    is_job_active,
    job_finished_event_data,
)


_VAC = "vacuum.alfred"

#: A vacuum id NO fixture registers an adapter for. `_VAC` is not that id — the
#: `manager` fixture registers `TEST_ADAPTER_CONFIG` for `vacuum.alfred` — and three
#: tests named "no adapter registered" used `_VAC` and so never reached the path they
#: claimed. Anything asserting the unregistered behaviour must use this instead.
_UNREGISTERED = "vacuum.no_adapter_registered"

_FALLBACK: frozenset[str] = frozenset({"fallback"})

_MINIMAL_ADAPTER = {
    "adapter_id": "test",
    "source": "test",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "dock_status": "sensor.alfred_dock_status",
        "active_cleaning_target": "sensor.alfred_target",
        "active_map": "sensor.alfred_active_map",
    },
    "completion": {
        "task_status_value": "completed",
        "secondary_clear_sentinels": ["", "unknown", "unavailable"],
    },
}


# ---------------------------------------------------------------------------
# [LC-1] — [LC-3] get_adapter_vocab
# ---------------------------------------------------------------------------

def test_get_adapter_vocab_no_adapter_returns_fallback():
    """[LC-1] Returns fallback frozenset when no adapter is registered.

    ⚠ THIS TEST USED TO NAME A STATE IT DID NOT CREATE. It took the `manager`
    fixture and asked about `_VAC` — and that fixture REGISTERS an adapter for
    `vacuum.alfred` (tests/integration/conftest.py). So it passed because
    `TEST_ADAPTER_CONFIG` happens to declare no `completion` section, i.e. it was a
    duplicate of [LC-3] wearing [LC-1]'s name, and the no-adapter path was covered
    by nothing. Measured two ways: `_common.py` line 77 is in coverage's missing
    lines, and deleting that guard reddened 0 of 33 tests in this file.

    `_UNREGISTERED` is the fix — a vacuum id no fixture registers — and the fixture
    is dropped, because taking `manager` is what created the confusion.
    """
    result = get_adapter_vocab(
        _UNREGISTERED, "completion", "secondary_clear_sentinels", _FALLBACK)
    assert result == _FALLBACK


@pytest.mark.parametrize("section_value", [
    ["secondary_clear_sentinels"],   # a list has no .get
    "secondary_clear_sentinels",     # nor does a str
    7,                               # nor an int
])
def test_lc19_a_section_whose_value_is_not_a_dict_still_returns_the_fallback(
    monkeypatch, section_value
):
    """[LC-19] `get_adapter_vocab` promises "Never raises". This is the input that tests it.

    The existing missing-section and missing-key cases ([LC-3]) also return the
    fallback without raising, which is why they do not cover this: there the `.get`
    chain succeeds and finds nothing. Here `config.get(section)` returns a value with
    no `.get` of its own, so the expression itself raises and only the broad `except`
    can keep the promise.

    Reachable because adapter config shape is an adapter DECLARATION, and
    code-sourced adapters register warn-only rather than being rejected. The caller
    that matters is lifecycle's completion-gate evaluation: a raise there aborts
    finalization for the run.

    `get_adapter_config` is patched rather than registering a malformed adapter,
    because registration may validate or reject the block and then the test would be
    measuring the registry instead of this function.

    RED: delete `except Exception: return fallback` and every row raises
    AttributeError (TypeError for the int).
    """
    from custom_components.eufy_vacuum.listeners import _common

    monkeypatch.setattr(
        _common, "get_adapter_config",
        lambda _vid: {"completion": section_value},
    )
    result = get_adapter_vocab(
        _VAC, "completion", "secondary_clear_sentinels", _FALLBACK)
    assert result == _FALLBACK


def test_lc20_no_reading_is_not_the_string_none(monkeypatch):
    """[LC-20] `is_dock_trigger_edge` must distinguish "no reading" from the word "none".

    ⚠ THIS IS A CONTRACT TEST, AND NO SHIPPED BRAND REACHES IT. Measured: no
    shipped `dock_events.triggers` vocabulary contains `none` — Eufy ships
    washing/emptying/drying variants, Dreame ships washing and drying, and Roborock
    declares no dock_status role at all and goes through `extra_watches`. So against
    every vocabulary that ships today the `new_state_value is None` guard is
    SUBSUMED: without it `str(None).lower()` is `"none"`, which is in no trigger set,
    and the answer is False either way.

    It is still worth pinning, because the vocabulary is a PARAMETER. This is a pure
    public helper with two callers, and `lifecycle.py` passes
    `getattr(new_state_obj, "state", None)` — so None genuinely arrives when a
    dock_status entity is removed. A brand that ever declares `none` as a trigger
    state (an idle dock reporting the string) would, without the guard, have every
    entity removal recorded as a dock cycle.

    THE VOCABULARY CONTAINING `none` IS THE WHOLE RED INPUT. With an ordinary
    vocabulary such as {"washing"} this test passes identically with the guard
    deleted, which is exactly the trap it is written to avoid.

    RED: delete `if new_state_value is None: return False` and the first assertion
    returns True.
    """
    vocabulary = frozenset({"none"})

    assert is_dock_trigger_edge("washing", None, vocabulary) is False, (
        "a removed entity has no reading; it has not transitioned INTO anything"
    )
    # The positive control, and the thing being distinguished FROM: the literal
    # string "none" from a device that really does report it IS a reading, and an
    # edge into it is a real edge.
    assert is_dock_trigger_edge("idle", "none", vocabulary) is True


def test_get_adapter_vocab_registered_but_silent_section_returns_fallback(manager):
    """[LC-1b] The case [LC-1] was ACTUALLY covering, kept rather than lost.

    A registered adapter that declares nothing for the section asked about is a
    different state from no adapter at all, and it is the commoner one — every
    brand declares some sections and not others. Keeping it means the relabelling
    above removes a false claim without removing real coverage.
    """
    result = get_adapter_vocab(_VAC, "completion", "secondary_clear_sentinels", _FALLBACK)
    assert result == _FALLBACK


def test_get_adapter_vocab_returns_frozenset(manager):
    """[LC-2] Returns frozenset of lowercased, stripped strings from adapter."""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "completion": {"secondary_clear_sentinels": ["Unknown", "Unavailable", ""]},
    })
    result = get_adapter_vocab(_VAC, "completion", "secondary_clear_sentinels", _FALLBACK)
    assert isinstance(result, frozenset)
    assert "unknown" in result
    assert "unavailable" in result


def test_get_adapter_vocab_missing_section_returns_fallback(manager):
    """[LC-3] Returns fallback when the requested section does not exist."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_vocab(_VAC, "nonexistent_section", "key", _FALLBACK)
    assert result == _FALLBACK


def test_get_adapter_vocab_missing_key_returns_fallback(manager):
    """[LC-3] Returns fallback when the key is absent inside a known section."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_vocab(_VAC, "completion", "nonexistent_key", _FALLBACK)
    assert result == _FALLBACK


# ---------------------------------------------------------------------------
# [LC-4] — [LC-6] get_adapter_value
# ---------------------------------------------------------------------------

def test_get_adapter_value_no_adapter_returns_fallback():
    """[LC-4] Returns fallback when no adapter is registered.

    Same relabelling as [LC-1]: it asked about `_VAC`, for which the `manager`
    fixture has registered an adapter, so it was exercising the missing-section
    path under the no-adapter name.
    """
    result = get_adapter_value(
        _UNREGISTERED, "completion", "task_status_value", fallback="default")
    assert result == "default"


def test_get_adapter_value_finds_nested_value(manager):
    """[LC-5] Returns the value at the requested nested path."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_value(_VAC, "completion", "task_status_value", fallback="fallback")
    assert result == "completed"


def test_get_adapter_value_missing_intermediate_key_returns_fallback(manager):
    """[LC-6] Returns fallback when an intermediate key in the path is missing."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_value(_VAC, "nonexistent", "task_status_value", fallback="fb")
    assert result == "fb"


def test_get_adapter_value_none_fallback(manager):
    """[LC-4] Fallback can be None and is returned correctly."""
    result = get_adapter_value(_VAC, "completion", "task_status_value", fallback=None)
    assert result is None


# ---------------------------------------------------------------------------
# [LC-7] — [LC-8] get_lifecycle_watch_entities
# ---------------------------------------------------------------------------

def test_get_lifecycle_watch_entities_no_adapter():
    """[LC-7] Returns only the vacuum entity when no adapter is registered.

    Same relabelling as [LC-1]. This one was the most misleading of the three:
    `TEST_ADAPTER_CONFIG` declares no `entities` key at all, so `_VAC` produced
    `[_VAC]` with an adapter registered — exactly the answer the no-adapter case
    gives, which is why the mislabelling was invisible.
    """
    assert get_lifecycle_watch_entities(_UNREGISTERED) == [_UNREGISTERED]


def test_get_lifecycle_watch_entities_includes_adapter_entities(manager):
    """[LC-8] Includes all declared lifecycle entities from the adapter."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_lifecycle_watch_entities(_VAC)
    assert _VAC in result
    assert "sensor.alfred_task_status" in result
    assert "sensor.alfred_dock_status" in result
    assert "sensor.alfred_target" in result
    assert "sensor.alfred_active_map" in result


def test_get_lifecycle_watch_entities_partial_adapter(manager):
    """[LC-8] Only declared entities are included; missing keys are skipped."""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "entities": {"task_status": "sensor.alfred_task_status"},
    })
    result = get_lifecycle_watch_entities(_VAC)
    assert _VAC in result
    assert "sensor.alfred_task_status" in result
    # dock_status not declared — must not appear
    assert "sensor.alfred_dock_status" not in result


def test_get_lifecycle_watch_entities_includes_job_active(manager):
    """[LC-8] job_active (the recharge-resume signal) is watched when declared,
    so its clear at the true finish re-triggers finalization."""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "entities": {
            **_MINIMAL_ADAPTER["entities"],
            "job_active": "binary_sensor.alfred_cleaning",
        },
    })
    assert "binary_sensor.alfred_cleaning" in get_lifecycle_watch_entities(_VAC)


# ---------------------------------------------------------------------------
# is_job_active — recharge-resume finalize guard
# ---------------------------------------------------------------------------

_JOB_ACTIVE_ADAPTER = {
    **_MINIMAL_ADAPTER,
    "entities": {
        **_MINIMAL_ADAPTER["entities"],
        "job_active": "binary_sensor.alfred_cleaning",
    },
}


async def test_is_job_active_not_declared(hass, manager):
    """No-op (False) when the adapter declares no job_active (e.g. Eufy) — even
    if some 'cleaning' binary sensor happens to be on."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    hass.states.async_set("binary_sensor.alfred_cleaning", "on")
    assert is_job_active(hass, _VAC) is False


async def test_is_job_active_declared_and_on(hass, manager):
    """Declared + on -> True (mid-job recharge dock; suppress finalize)."""
    register_adapter_config(_VAC, _JOB_ACTIVE_ADAPTER)
    hass.states.async_set("binary_sensor.alfred_cleaning", "on")
    assert is_job_active(hass, _VAC) is True


async def test_is_job_active_declared_and_off(hass, manager):
    """Declared but off -> False (job truly done; allow finalize)."""
    register_adapter_config(_VAC, _JOB_ACTIVE_ADAPTER)
    hass.states.async_set("binary_sensor.alfred_cleaning", "off")
    assert is_job_active(hass, _VAC) is False


async def test_is_job_active_declared_missing_state(hass, manager):
    """Declared but the entity has no state -> False."""
    register_adapter_config(_VAC, _JOB_ACTIVE_ADAPTER)
    assert is_job_active(hass, _VAC) is False


@pytest.mark.parametrize("unreadable", ["unavailable", "unknown"])
async def test_lc18_unreadable_binary_counts_as_active_only_when_asked(
    hass, manager, unreadable
):
    """[LC-18] `unavailable_is_active=True` — an UNREADABLE binary is not a clear.

    The recharge-resume guard asks "is the job still running?" before letting a
    completion finalize. A `job_active` binary that has gone `unavailable` or
    `unknown` does not answer, and the two callers want opposite readings of that
    silence: the finalize gate must treat it as STILL ACTIVE and refuse to finalize
    (losing a run's learning data is worse than deferring it), while the
    has_observed arming gate must treat it as strict `off` so an indeterminate
    binary at startup cannot arm the flag. That is the whole reason the flag exists.

    ⚠ FOUR ASSERTIONS, BECAUSE THE PARAMETER IS NOT THE POINT — the FLAG is. The
    same state is read with the flag on and off, and the opposite answers are the
    claim. Asserting only the True half would pass against a function that returned
    True for every input, which the `off` row then rules out.

    This covers what `test_lifecycle_recharge_guard_suppresses_on_unavailable_binary`
    in test_listeners_active.py NAMES but never reaches: that test leaves
    `active_cleaning_target` set to a room name, so the sentinel fallback fails and
    `should_finalize_completed` is already False before `is_job_active` is called.
    It passes with this arm deleted — measured, 0 of 70 tests reddened — and
    `_common.py` line 217 is in coverage's missing lines.

    RED: delete `if unavailable_is_active and raw in ("unavailable", "unknown")` and
    the first assertion returns False.
    """
    register_adapter_config(_VAC, _JOB_ACTIVE_ADAPTER)
    hass.states.async_set("binary_sensor.alfred_cleaning", unreadable)

    assert is_job_active(hass, _VAC, unavailable_is_active=True) is True, (
        "the finalize gate must not read silence as a finished job"
    )
    assert is_job_active(hass, _VAC) is False, (
        "the arming gate must read the same silence as strict not-on"
    )

    # And the flag must not be a blanket True: a binary that DOES answer, and
    # answers 'off', stays False under both readings.
    hass.states.async_set("binary_sensor.alfred_cleaning", "off")
    assert is_job_active(hass, _VAC, unavailable_is_active=True) is False
    assert is_job_active(hass, _VAC) is False


# ---------------------------------------------------------------------------
# completion_secondary_satisfied — completion-gate secondary requirement
# ---------------------------------------------------------------------------

_SENTINELS = frozenset({"", "unknown", "unavailable", "none", "null"})


def test_completion_secondary_default_target_cleared(manager):
    """Default (Eufy): active_target reading a clear sentinel satisfies it."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    assert completion_secondary_satisfied(_VAC, {"active_target": ""}, _SENTINELS) is True


def test_completion_secondary_default_target_not_cleared(manager):
    """Default: a non-sentinel active_target does NOT satisfy it."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    assert completion_secondary_satisfied(
        _VAC, {"active_target": "Dining Room"}, _SENTINELS
    ) is False


def test_completion_secondary_require_job_active_clear_bypasses(manager):
    """require_job_active_clear (Roborock): bypasses the sentinel check entirely
    (the is_job_active guard supplies the real signal), so a current_room that
    reverted to the dock-room name still satisfies the secondary. RP-033/COMMON-2:
    only bypasses when entities.job_active is actually declared -- this is the
    real Roborock shape (both set together)."""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "entities": {
            **_MINIMAL_ADAPTER["entities"],
            "job_active": "binary_sensor.alfred_cleaning",
        },
        "completion": {
            "task_status_value": "charging",
            "require_job_active_clear": True,
        },
    })
    assert completion_secondary_satisfied(
        _VAC, {"active_target": "Dining Room", "job_active_present": True}, _SENTINELS
    ) is True


def test_completion_secondary_requires_the_job_active_entity_to_EXIST(manager):
    """[COMMON-2b] issue #51: DECLARED is not PRESENT.

    RP-033/COMMON-2 tightened the bypass from "flag set" to "entity declared", one
    step short of what the flag actually promises. A declared id that resolves to no
    entity -- the normal state of a localized install, where Roborock's job_active is
    `binary_sensor.<vid>_reinigen` and our declaration is `_cleaning` -- still
    short-circuited to True. The gate reported its secondary satisfied on the strength
    of an entity that does not exist.

    That is not a cosmetic wrong answer. `require_job_active_clear` makes this entity
    the SINGLE arming signal, so with it unresolved every run on that install was
    reaped as `interrupted` about ten minutes after dispatch, sometimes mid-clean.

    Absent -> fall through to the sentinel check, which is what the docstring already
    promised for the un-declared case. Here the target reads a dock-room name rather
    than a sentinel, so the honest answer is False.
    """
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "entities": {
            **_MINIMAL_ADAPTER["entities"],
            "job_active": "binary_sensor.alfred_cleaning",
        },
        "completion": {
            "task_status_value": "charging",
            "require_job_active_clear": True,
        },
    })
    # No `job_active_present` -- build_completion_signals reports "" for an entity that
    # is absent or unavailable, so this is the shape a localized install produces.
    assert completion_secondary_satisfied(
        _VAC, {"active_target": "Dining Room"}, _SENTINELS
    ) is False

    # ...and with the entity genuinely gone, a real clear sentinel still finalizes:
    # losing the bypass must not cost a run that the default check can settle.
    assert completion_secondary_satisfied(
        _VAC, {"active_target": ""}, _SENTINELS
    ) is True


def test_completion_secondary_require_job_active_clear_without_entity_falls_back(manager):
    """RP-033/COMMON-2: require_job_active_clear set True WITHOUT entities.job_active
    declared used to bypass the sentinel check unconditionally with nothing backing
    it. It now has no effect -- falls through to the default sentinel check, i.e.
    behaves as if the flag were never set. (Registration separately warns on this
    combination; see adapters/registry.py._warn_completion_gate_orphan.)"""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "completion": {
            "task_status_value": "charging",
            "require_job_active_clear": True,
        },
    })
    assert completion_secondary_satisfied(
        _VAC, {"active_target": "Dining Room"}, _SENTINELS
    ) is False
    assert completion_secondary_satisfied(
        _VAC, {"active_target": ""}, _SENTINELS
    ) is True


# ---------------------------------------------------------------------------
# [LC-9] — [LC-10] completed_finalize_signals
# ---------------------------------------------------------------------------

async def test_completed_finalize_signals_no_entities_empty_strings(hass, manager):
    """[LC-9] Returns empty strings for all signals when entity states are absent."""
    signals = completed_finalize_signals(hass, _VAC)
    assert signals["vacuum_state"] == ""
    assert signals["task_status"] == ""
    assert signals["dock_status"] == ""
    assert signals["active_target"] == ""


async def test_completed_finalize_signals_reads_live_state(hass, manager):
    """[LC-10] Returns the live HA state for the vacuum entity."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    signals = completed_finalize_signals(hass, _VAC)
    assert signals["vacuum_state"] == "docked"


async def test_completed_finalize_signals_reads_adapter_entities(hass, manager):
    """[LC-10] Reads states for adapter-declared task_status and dock_status."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    hass.states.async_set("sensor.alfred_task_status", "Completed")
    hass.states.async_set("sensor.alfred_dock_status", "washing")
    await hass.async_block_till_done()
    signals = completed_finalize_signals(hass, _VAC)
    assert signals["task_status"] == "completed"
    assert signals["dock_status"] == "washing"


async def test_completed_finalize_signals_secondary_clear_entity_override(hass, manager):
    """[LC-10b] completion.secondary_clear_entity redirects active_target to a DIFFERENT
    entity than the default active_cleaning_target.

    Dreame's shape: current_room reverts to the DOCK ROOM at end-of-run (never a
    sentinel), while task_type clears custom -> `unavailable` at the same instant. Naming
    task_type as the secondary makes active_target read the entity that actually clears.
    Bite: revert the field to the hardcoded active_cleaning_target and active_target reads
    "dining room" (the dock room) — the exact reason Dreame never finalized. Also proves
    the field is no longer dead (declared-but-unread) config."""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "entities": {
            **_MINIMAL_ADAPTER["entities"],
            "task_type": "sensor.alfred_task_type",
        },
        "completion": {"secondary_clear_entity": "task_type"},
    })
    hass.states.async_set("sensor.alfred_target", "Dining Room")     # dock room, NOT sentinel
    hass.states.async_set("sensor.alfred_task_type", "unavailable")  # clears at completion
    await hass.async_block_till_done()
    signals = completed_finalize_signals(hass, _VAC)
    assert signals["active_target"] == "unavailable"  # from task_type, not the dock-room target


# ---------------------------------------------------------------------------
# [LC-11] — [LC-14] job_finished_event_data
# ---------------------------------------------------------------------------

def test_job_finished_event_data_has_vacuum_and_map(manager):
    """[LC-11] Payload always contains vacuum_entity_id and map_id."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC,
        map_id="1",
        finalize_result={},
    )
    assert payload["vacuum_entity_id"] == _VAC
    assert payload["map_id"] == "1"


def test_job_finished_event_data_default_status(manager):
    """[LC-12] Status defaults to 'completed' when absent."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id="1", finalize_result={}
    )
    assert payload["status"] == "completed"


def test_job_finished_event_data_reads_outcome_status(manager):
    """[LC-13] Reads status from nested completed_job.outcome."""
    finalize_result = {
        "completed_job": {
            "outcome": {"status": "cancelled"},
        }
    }
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id="1", finalize_result=finalize_result
    )
    assert payload["status"] == "cancelled"


def test_job_finished_event_data_none_finalize_result(manager):
    """[LC-14] Treats None finalize_result as empty — returns default values."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id="1", finalize_result=None
    )
    assert payload["vacuum_entity_id"] == _VAC
    assert payload["status"] == "completed"
    assert payload["job_id"] is None


def test_job_finished_event_data_map_id_coerced_to_string(manager):
    """[LC-11] map_id is coerced to a string in the payload."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id=42, finalize_result={}
    )
    assert payload["map_id"] == "42"


# ---------------------------------------------------------------------------
# [LC-15] - [LC-17] L9/L10: "unavailable" is a value, not an absence
# ---------------------------------------------------------------------------

_JOB_ACTIVE_ENTITY = "binary_sensor.alfred_cleaning"

_ROBOROCK_SHAPED_ADAPTER = {
    "adapter_id": "test",
    "source": "test",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "active_cleaning_target": "sensor.alfred_current_room",
        "job_active": _JOB_ACTIVE_ENTITY,
    },
    "completion": {"require_job_active_clear": True},
}


@pytest.mark.parametrize("blip", ["unavailable", "unknown"])
async def test_lc15_an_unreadable_job_active_is_not_present(hass, manager, blip):
    """[LC-15] RED BEFORE THE FIX.

    `job_active_present` was `bool(_state(...))`, and `_state` returns the literal
    string "unavailable" for an entity that exists but is unreachable -- so
    `bool("unavailable")` was True and the gate reported the completion secondary
    SATISFIED on a signal it could not read.

    Asserted through `completed_finalize_signals`, deliberately. Every existing test
    of this gate passes `job_active_present` in by hand, so none of them can see how
    the flag is actually computed -- which is how the same gate got tightened three
    times (flag-set -> entity-declared -> entity-resolves) and still shipped this.
    """
    register_adapter_config(_VAC, _ROBOROCK_SHAPED_ADAPTER)
    hass.states.async_set(_JOB_ACTIVE_ENTITY, blip)
    await hass.async_block_till_done()

    signals = completed_finalize_signals(hass, _VAC)

    assert signals["job_active_present"] is False, (
        f"job_active reading {blip!r} was treated as a trustworthy signal"
    )
    # ... and the gate must therefore NOT short-circuit. A run still in progress
    # (current_room naming a real room) must not be reported as complete.
    assert completion_secondary_satisfied(
        _VAC, {**signals, "active_target": "Dining Room"}, _SENTINELS
    ) is False


async def test_lc16_a_readable_job_active_still_short_circuits(hass, manager):
    """[LC-16] RED IF THE FIX IS WIDENED INTO A MUTE.

    `require_job_active_clear` exists because Roborock's current_room reverts to the
    DOCK ROOM'S NAME at the end of a run -- never a sentinel -- so the default check
    can never pass and the job would never finalize. Making `job_active_present`
    stricter must not reach the case the bypass was built for, or Roborock jobs stop
    finalizing entirely, which is a bigger bug than the one being fixed.
    """
    register_adapter_config(_VAC, _ROBOROCK_SHAPED_ADAPTER)
    hass.states.async_set(_JOB_ACTIVE_ENTITY, "on")
    await hass.async_block_till_done()

    signals = completed_finalize_signals(hass, _VAC)

    assert signals["job_active_present"] is True
    assert completion_secondary_satisfied(
        _VAC, {**signals, "active_target": "Dining Room"}, _SENTINELS
    ) is True


async def test_lc17_state_does_not_collapse_indeterminates(hass, manager):
    """[LC-17] RED IF SOMEONE 'FIXES' L10 BY COLLAPSING INSIDE `_state`.

    That is the tempting fix -- the docstring said `_state` returns "" for
    unavailable, so make it true -- and it is the wrong one. `_state` feeds five
    keys, and the other four are compared against adapter-declared sentinel sets
    that already NAME the indeterminate values (Eufy's `secondary_clear_sentinels`
    is `["", "unknown", "unavailable", "none", "null"]`). Collapsing would move that
    decision out of the adapter's declaration and into core, silently, for brands
    nobody has measured -- and core does not own a brand's vocabulary.

    So the invariant is: the helper reports what it read, and only the ONE key that
    asks "is this trustworthy" applies the stronger test.
    """
    register_adapter_config(_VAC, _ROBOROCK_SHAPED_ADAPTER)
    hass.states.async_set("sensor.alfred_task_status", "unavailable")
    hass.states.async_set("sensor.alfred_current_room", "unknown")
    await hass.async_block_till_done()

    signals = completed_finalize_signals(hass, _VAC)

    assert signals["task_status"] == "unavailable", (
        "a value-carrying key was collapsed to an absence"
    )
    assert signals["active_target"] == "unknown"
    # and "" still means genuinely absent, which is the half the docstring had right
    assert signals["dock_status"] == ""
