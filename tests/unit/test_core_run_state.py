"""Unit tests for core/run_state.py — the brand-agnostic "is the robot cleaning
right now?" predicate that feeds the current-room non-cleaning accumulator.

Coverage targets
----------------
[RS-1] HA-standard non-cleaning states are recognised for any brand.
[RS-2] FAILS OPEN: unknown/unavailable/empty/None are NOT non-cleaning.
[RS-3] The deliberate exclusions (paused/idle/error) are NOT non-cleaning.
[RS-4] cleaning and any unrecognised string are NOT non-cleaning.
[RS-5] An adapter's declared vocabulary EXTENDS the standard set, never replaces it.
[RS-6] A malformed adapter declaration falls back to the standard set.
[RS-7] Declared values are matched case/whitespace-insensitively.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.core.run_state import (
    is_non_cleaning_vacuum_state,
    non_cleaning_vacuum_states,
)

_VAC = "vacuum.alfred"


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


@pytest.mark.parametrize("state", ["docked", "returning", "returning_to_dock",
                                   "Docked", "  RETURNING  "])
def test_standard_non_cleaning_states(state):
    """[RS-1] and [RS-7] — normalized before lookup."""
    assert is_non_cleaning_vacuum_state(state) is True


@pytest.mark.parametrize("state", [None, "", "   ", "unknown", "unavailable"])
def test_fails_open_on_unreadable(state):
    """[RS-2] An unreadable state must never open a subtraction window.

    This is the direction that matters: a False here subtracts nothing and
    leaves the room clock exactly as it was before the accumulator existed,
    whereas a True would subtract unboundedly for as long as the dropout lasts
    and stall the room forever.
    """
    assert is_non_cleaning_vacuum_state(state) is False


@pytest.mark.parametrize("state", ["paused", "idle", "error"])
def test_deliberate_exclusions(state):
    """[RS-3] Each is excluded for its own reason — see the module docstring.

    paused: already subtracted via current_room_paused_seconds (counting it here
    would double-subtract). idle: a mid-run idle is a stall we must surface to
    rollover, not hide. error: a dock fault fires while the robot is still
    cleaning the floor, so it is not evidence that cleaning stopped.
    """
    assert is_non_cleaning_vacuum_state(state) is False


@pytest.mark.parametrize("state", ["cleaning", "mopping", "wibble"])
def test_cleaning_and_unrecognised(state):
    """[RS-4]"""
    assert is_non_cleaning_vacuum_state(state) is False


def test_adapter_vocabulary_extends_not_replaces():
    """[RS-5] A declared set is ADDITIVE — the HA-standard states are part of the
    platform contract the brand already implements, so they survive."""
    register_adapter_config(_VAC, {
        "adapter_id": "brand_x", "source": "code",
        "vocabulary": {"non_cleaning_vacuum_states": ["going to wash"]},
    })
    assert is_non_cleaning_vacuum_state("going to wash", vacuum_entity_id=_VAC) is True
    # ...and the standard ones are NOT lost
    assert is_non_cleaning_vacuum_state("docked", vacuum_entity_id=_VAC) is True
    assert is_non_cleaning_vacuum_state("returning", vacuum_entity_id=_VAC) is True
    # The declaration does not leak to a vacuum that never declared it.
    assert is_non_cleaning_vacuum_state("going to wash") is False


def test_adapter_vocabulary_case_insensitive():
    """[RS-7]"""
    register_adapter_config(_VAC, {
        "adapter_id": "brand_x", "source": "code",
        "vocabulary": {"non_cleaning_vacuum_states": ["  Going To Wash  ", ""]},
    })
    assert is_non_cleaning_vacuum_state("going to wash", vacuum_entity_id=_VAC) is True


@pytest.mark.parametrize("declared", ["not-a-list", 42, {"a": 1}, None])
def test_malformed_declaration_falls_back(declared):
    """[RS-6]"""
    register_adapter_config(_VAC, {
        "adapter_id": "brand_x", "source": "code",
        "vocabulary": {"non_cleaning_vacuum_states": declared},
    })
    assert non_cleaning_vacuum_states(_VAC) == non_cleaning_vacuum_states()
    assert is_non_cleaning_vacuum_state("docked", vacuum_entity_id=_VAC) is True


def test_no_adapter_registered():
    """[RS-1] An unregistered vacuum still gets the standard set."""
    assert is_non_cleaning_vacuum_state("docked", vacuum_entity_id="vacuum.nope") is True
    assert is_non_cleaning_vacuum_state("cleaning", vacuum_entity_id="vacuum.nope") is False
