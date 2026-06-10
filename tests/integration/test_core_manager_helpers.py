"""Tests for core/manager.py module-level pure helpers.

These are stateless string/number coercion helpers used throughout the manager
to normalize untrusted attribute values and render enum-like values into
friendly labels. They take no ``hass``/manager state, so the tests import them
directly and assert observable return values — no fixture or full-boot harness
is required.

Coverage targets
----------------
[CMH-1]  _safe_int / _safe_float: unparseable value → default (TypeError/ValueError
         except branch); _normalize_path_block_action: unsupported value → 'event_only'
         fallback plus the in-set passthrough; _display_label: separator-only collapses
         to None, explicit lower-case map → canonical label, generic capitalize path.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.manager import (
    _display_label,
    _normalize_path_block_action,
    _safe_float,
    _safe_int,
)


def test_pure_value_helpers():
    """[CMH-1] safe coercion defaults, path-block fallback, label normalization."""
    # _safe_int: object() is not in the sentinel set, so it reaches int(float(...))
    # which raises TypeError -> default branch (lines 93-94).
    assert _safe_int(object()) == 0
    # "abc" reaches int(float("abc")) which raises ValueError -> explicit default.
    assert _safe_int("abc", 7) == 7
    # Parseable values still coerce through the happy path.
    assert _safe_int("12.9") == 12

    # _safe_float: unparseable value -> default via the except branch.
    assert _safe_float("abc", 1.5) == 1.5
    assert _safe_float("3.25") == 3.25

    # _normalize_path_block_action: unsupported string -> 'event_only' (line 111),
    # supported string passes through unchanged (the in-set path).
    assert _normalize_path_block_action("garbage") == "event_only"
    assert _normalize_path_block_action("pause_and_event") == "pause_and_event"

    # _display_label: a separator/whitespace-only value normalizes to '' -> None
    # (line 127 — "--" becomes "" after _/-/whitespace collapse).
    assert _display_label("  --  ") is None
    # Explicit lower-case map hit returns the canonical label (line 138).
    assert _display_label("vacuum_mop") == "Vacuum + Mop"
    assert _display_label("by room") == "By Room"
    # Unmapped value falls through to the generic per-word capitalize path.
    assert _display_label("quick boost") == "Quick Boost"
