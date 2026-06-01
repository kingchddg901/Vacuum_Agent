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
[ENT-1]  build_entity_id default strategy -> sensor.<obj><suffix>.
[ENT-2]  build_entity_id honors an explicit domain.
[ENT-3]  build_entity_id raises NotImplementedError for other strategies.
"""

from __future__ import annotations

import pytest

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
