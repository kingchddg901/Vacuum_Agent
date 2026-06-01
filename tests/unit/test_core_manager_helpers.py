"""Unit tests for the pure module-level helpers in core/manager.py.

These mirror (but are distinct module objects from) the planning helpers; they
carry their own coverage. Pure functions — no hass, no manager.

Coverage targets
----------------
[CMH-1] _safe_float: sentinel handling + numeric coercion + bad input.
[CMH-2] _hours_text: None for negatives, singular/plural integer, decimal.
[CMH-3] _settings_profile_display: custom-profile label with multi-pass + subtitle.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.manager import (
    _hours_text,
    _safe_float,
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
