"""Unit tests for planning/run_plan.py module-level display helpers (pure).

Coverage targets
----------------
[RP-1] _safe_int / _safe_float sentinel handling.
[RP-2] _display_label explicit map + title case.
[RP-3] _profile_name_label preset names.
[RP-4] _settings_profile_display: preset vs custom profile + subtitle bits.
[RP-5] _room_surface_labels floor label.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.planning.run_plan import (
    _display_label,
    _profile_name_label,
    _room_surface_labels,
    _safe_float,
    _safe_int,
    _settings_profile_display,
)


@pytest.mark.parametrize("value,expected", [(5, 5), ("3.9", 3), (None, 0), ("unknown", 0)])
def test_safe_int(value, expected):
    """[RP-1]"""
    assert _safe_int(value) == expected


def test_safe_float():
    """[RP-1]"""
    assert _safe_float("2.5") == pytest.approx(2.5)
    assert _safe_float("unavailable") == pytest.approx(0.0)


@pytest.mark.parametrize("value,expected", [
    ("vacuum_mop", "Vacuum + Mop"), ("by_time", "By Time"),
    ("main_brush", "Main Brush"), ("", None),
])
def test_display_label(value, expected):
    """[RP-2]"""
    assert _display_label(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("vacuum_quick", "Vacuum Quick"), ("user_1", "Custom"),
    ("vacuum_mop_deep", "Vacuum + Mop Deep"), ("", None),
])
def test_profile_name_label(value, expected):
    """[RP-3]"""
    assert _profile_name_label(value) == expected


def test_settings_profile_display_preset():
    """[RP-4] a matching preset → labelled profile, not custom."""
    out = _settings_profile_display(
        room_name="kitchen", selected_profile_name="vacuum_quick",
        resolved_profile_name="vacuum_quick", clean_mode="vacuum",
        fan_speed="Max", clean_passes=1)
    assert out["is_custom_profile"] is False
    assert "Vacuum Quick" in out["profile_label"]


def test_settings_profile_display_custom():
    """[RP-4] no selected profile + multi-pass → custom, passes in subtitle."""
    out = _settings_profile_display(
        room_name="kitchen", selected_profile_name="", clean_mode="vacuum",
        fan_speed="Max", water_level="High", clean_passes=2, edge_mopping=True)
    assert out["is_custom_profile"] is True
    assert "Custom" in out["profile_label"]
    assert "Edge Mopping" in out["profile_subtitle"]
    assert "2 Passes" in out["profile_subtitle"]


def test_settings_profile_display_path_type_in_subtitle():
    """[RP-4] a path_type label is appended to the profile subtitle (arc 144->145)."""
    out = _settings_profile_display(
        room_name="kitchen", selected_profile_name="", clean_mode="vacuum",
        fan_speed="Max", path_type="deep_clean", clean_passes=1)
    # path_type → _display_label → "Deep Clean", carried into the subtitle bits
    assert out["path_type_label"] == "Deep Clean"
    assert "Deep Clean" in out["profile_subtitle"]


def test_room_surface_labels():
    """[RP-5]"""
    out = _room_surface_labels(floor_type="carpet_low_pile")
    assert out["floor_type_label"] is not None
    assert _room_surface_labels(floor_type=None)["floor_type_label"] is None
