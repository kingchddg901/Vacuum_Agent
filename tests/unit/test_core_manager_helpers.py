"""Unit tests for the pure module-level helpers in core/manager.py.

These mirror (but are distinct module objects from) the planning helpers; they
carry their own coverage. Pure functions — no hass, no manager.

Coverage targets
----------------
[CMH-1] _safe_float: sentinel handling + numeric coercion + bad input.
[CMH-2] _hours_text: None for negatives, singular/plural integer, decimal.
[CMH-3] _settings_profile_display: custom-profile label with multi-pass + subtitle.
[CMH-4] _safe_int / _normalize_path_block_action / _display_label: coercion
        defaults, action fallback, separator/label normalization.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.manager import (
    _display_label,
    _hours_text,
    _normalize_path_block_action,
    _safe_float,
    _safe_int,
    _settings_profile_display,
)


@pytest.mark.parametrize("value,expected", [
    (None, 0.0), ("", 0.0), ("unknown", 0.0), ("unavailable", 0.0),
    ("2.5", 2.5), (3, 3.0), ("nope", 0.0),
])
def test_safe_float(value, expected):
    """[CMH-1]"""
    assert _safe_float(value) == pytest.approx(expected)


@pytest.mark.parametrize("value,expected", [
    (-1, None), ("unavailable", None),
    (1, "1 hour"), (2, "2 hours"), (2.0, "2 hours"),
    (2.5, "2.5 hours"),
])
def test_hours_text(value, expected):
    """[CMH-2]"""
    assert _hours_text(value) == expected


def test_settings_profile_display_custom_multipass():
    """[CMH-3] no preset + multi-pass + edge → Custom label, passes in subtitle."""
    out = _settings_profile_display(
        room_name="kitchen", selected_profile_name="", clean_mode="vacuum",
        fan_speed="Max", water_level="High", clean_intensity="Deep",
        clean_passes=2, edge_mopping=True, path_type="standard")
    assert out["is_custom_profile"] is True
    assert "Custom" in out["profile_label"]
    assert "2 Passes" in out["profile_subtitle"]
    assert "Edge Mopping" in out["profile_subtitle"]


def test_pure_value_helpers():
    """[CMH-4] _safe_int coercion defaults, path-block action fallback, and
    _display_label separator/label normalization."""
    # _safe_int: object() reaches int(float(...)) -> TypeError -> default branch.
    assert _safe_int(object()) == 0
    # "abc" reaches int(float("abc")) -> ValueError -> explicit default.
    assert _safe_int("abc", 7) == 7
    # Parseable values coerce through the happy path.
    assert _safe_int("12.9") == 12

    # _safe_float: unparseable value -> default via the except branch.
    assert _safe_float("abc", 1.5) == 1.5
    assert _safe_float("3.25") == 3.25

    # _normalize_path_block_action: unsupported -> 'event_only'; supported passes through.
    assert _normalize_path_block_action("garbage") == "event_only"
    assert _normalize_path_block_action("pause_and_event") == "pause_and_event"

    # _display_label: separator/whitespace-only -> '' -> None.
    assert _display_label("  --  ") is None
    # Explicit lower-case map hit returns the canonical label.
    assert _display_label("vacuum_mop") == "Vacuum + Mop"
    assert _display_label("by room") == "By Room"
    # Unmapped value falls through to the generic per-word capitalize path.
    assert _display_label("quick boost") == "Quick Boost"
