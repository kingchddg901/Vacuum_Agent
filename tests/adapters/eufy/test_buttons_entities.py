"""Brand-specific tests for the Eufy button-candidate data and entity builder.

Covers two pure-data / pure-logic Eufy adapter modules:
  - ``adapters/eufy/buttons.py`` — candidate suffix lists and token fallback
    lists for dock-action and replacement-reset buttons. Pure module-level
    data; these tests assert its structural invariants (the manager iterates
    these blindly, so a malformed entry would silently break discovery).
  - ``adapters/eufy/entities.py`` — ``build_entity_id`` naming-strategy branch,
    including the unimplemented-strategy guard that must raise rather than
    silently mis-name an entity.

Coverage targets
----------------
[BTN-1]  dock-action candidates: every value is a list of "_"-prefixed strings.
[BTN-2]  dock-action tokens: every value is a list of non-empty token lists.
[BTN-3]  reset candidates/tokens: same structural invariants.
[BTN-4]  candidate and token action keys line up (no orphan action).
[BTN-5]  _build_button_block: absent from BOTH maps -> None, present in EITHER
         -> a block. The `and` is the claim; an `or` would return None for a
         component that has tokens but no suffix list.
[ENT-1]  build_entity_id default strategy -> sensor.<obj><suffix>.
[ENT-2]  build_entity_id honors an explicit domain.
[ENT-3]  build_entity_id raises NotImplementedError for other strategies.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.eufy.adapter import _build_button_block
from custom_components.eufy_vacuum.adapters.eufy import buttons
from custom_components.eufy_vacuum.adapters.eufy import entities


# --- buttons.py data shape --------------------------------------------------


def _assert_candidate_map(mapping):
    assert isinstance(mapping, dict) and mapping
    for action, suffixes in mapping.items():
        assert isinstance(action, str) and action
        assert isinstance(suffixes, list) and suffixes
        for suffix in suffixes:
            assert isinstance(suffix, str) and suffix.startswith("_")


def _assert_token_map(mapping):
    assert isinstance(mapping, dict) and mapping
    for action, token_lists in mapping.items():
        assert isinstance(action, str) and action
        assert isinstance(token_lists, list) and token_lists
        for tokens in token_lists:
            assert isinstance(tokens, list) and tokens
            for tok in tokens:
                assert isinstance(tok, str) and tok


def test_dock_action_candidates_shape():
    """[BTN-1]"""
    _assert_candidate_map(buttons.DOCK_ACTION_CANDIDATES)


def test_dock_action_tokens_shape():
    """[BTN-2]"""
    _assert_token_map(buttons.DOCK_ACTION_TOKENS)


def test_reset_candidates_shape():
    """[BTN-3]"""
    _assert_candidate_map(buttons.RESET_CANDIDATES)


def test_reset_tokens_shape():
    """[BTN-3]"""
    _assert_token_map(buttons.RESET_TOKENS)


def test_action_keys_align():
    """[BTN-4] every candidate action has a token entry and vice versa."""
    assert set(buttons.DOCK_ACTION_CANDIDATES) == set(buttons.DOCK_ACTION_TOKENS)
    assert set(buttons.RESET_CANDIDATES) == set(buttons.RESET_TOKENS)


# --- entities.build_entity_id ----------------------------------------------


def test_build_entity_id_default_strategy():
    """[ENT-1]"""
    assert (
        entities.build_entity_id("vacuum.alfred", entities.SUFFIX_TASK_STATUS)
        == "sensor.alfred_task_status"
    )


def test_build_entity_id_explicit_domain():
    """[ENT-2]"""
    assert (
        entities.build_entity_id(
            "vacuum.alfred",
            entities.SUFFIX_CHARGING,
            entities.DOMAIN_BINARY_SENSOR,
        )
        == "binary_sensor.alfred_charging"
    )


def test_build_entity_id_unimplemented_strategy_raises():
    """[ENT-3] the extension-point guard must surface, not silently mis-name."""
    with pytest.raises(NotImplementedError):
        entities.build_entity_id(
            "vacuum.alfred",
            entities.SUFFIX_TASK_STATUS,
            strategy=entities.STRATEGY_PREFIX_OBJECT_ID,
        )


def test_btn5_a_component_with_no_reset_button_yields_none():
    """[BTN-5] The declared contract of `_build_button_block`, and the `and` in it.

    Its docstring states the behaviour: "Returns ``None`` when the key is absent from
    both maps (e.g. a component with no reset button), so callers can store ``None``
    for 'no button'." That matters because a caller storing `None` can tell "this
    component has no reset button" from "this component's button could not be found",
    and the two want different handling.

    PRODUCTION CANNOT REACH THE None ARM TODAY, and saying so is the point rather than
    a caveat. Measured: all 7 `MAINTENANCE_COMPONENTS` appear in `RESET_CANDIDATES` or
    `RESET_TOKENS`, so `_build_button_blocks` never passes a key that is in neither,
    and the other caller iterates the same union. The arm is reachable the moment a
    catalog gains a component with no reset button -- the case the docstring itself
    names -- so this is a pure function tested at its own boundary, with the live
    unreachability recorded rather than implied.

    THE SECOND AND THIRD INPUTS ARE THE `and`. Present in EITHER map must yield a
    block, so an `or` in place of the `and` is what they catch: it would return None
    for a component declaring tokens but no suffix list, which is a shape
    `RESET_TOKENS` exists to express. Asserting the exact dicts also pins the
    suffix-stripping, so a falsy-but-present result cannot pass as None -- the trap
    would be `assert not result`, which `{'entity_suffixes': [], 'token_sets': []}`
    satisfies and `None` also satisfies.
    """
    assert _build_button_block(
        "ghost",
        {"filter": ["_reset_filter"]},
        {"filter": [["reset", "filter"]]},
    ) is None

    assert _build_button_block("filter", {"filter": ["_reset_filter"]}, {}) == {
        "entity_suffixes": ["reset_filter"],
        "token_sets": [],
    }
    assert _build_button_block("filter", {}, {"filter": [["reset", "filter"]]}) == {
        "entity_suffixes": [],
        "token_sets": [["reset", "filter"]],
    }


# ---------------------------------------------------------------------------
# RECORDED CEILING -- adapters/eufy/adapter.py, 94.29%, measured 2026-11-09
#
# [BTN-5] above takes the only testable unit. The module sits ONE unit short of 95%
# and both remaining units are unreachable, so it stays below deliberately.
#
# THE ARITHMETIC, MEASURED rather than estimated -- a first draft of this block said
# "3 statements and 3 branch arms of 105 units" and "[BTN-5] closes one of the three
# needed", and every one of those figures was invented:
#   70 units total (60 statements + 10 branches)
#   64/70 = 91.43% before [BTN-5]; 66/70 = 94.29% after, so it closed TWO units
#     (line 122 and the branch into it), not one
#   1 unit still needed to reach 95%, not three
#   what remains: lines 156 and 357, with the two branch arms into them
#
# NOT TESTED -- `_registry_model_code`'s `device_entry is None` guard
#
# UNREACHABLE, and ALREADY RECORDED ELSEWHERE: [CMR-7] in
# tests/integration/test_core_manager_registry.py pins that HA's entity registry
# refuses a dangling device_id -- `async_update_entity(device_id=<bogus>)` raises
# ValueError, and removing a device clears its entities' device_id. That file's own
# trailing note states the ablation reddens nothing. Reaching this arm means writing
# an inconsistent registry by hand, which tests the internals rather than the system.
#
# NOT TESTED -- `_rescue_select_block`'s `if not ids: return block`
#
# UNREACHABLE and SUBSUMED BOTH. The closure is only called with a block whose entries
# carry string entity_ids, so `ids` is never empty; and with it empty the fall-through
# returns the same `block` object anyway, so deleting the guard changes nothing
# observable. Neither half leaves an input that could redden a test.
#
# ONE UNIT SHORT IS THE UNCOMFORTABLE PART, and it is why this is stated rather than
# closed: a single mocked-registry test would cross the line, and it would be a test of
# the mock. A pragma would also cross it, on a non-logger line, which the programme's
# rule forbids precisely because it makes the percentage flattering by exactly as much
# as it hides.
# ---------------------------------------------------------------------------
