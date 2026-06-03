"""Unit tests for learning/manager.py::_settings_profile_label.

Pure display-label builder for the card's room-profile cards (its output feeds
``profile_subtitle`` which the frontend renders). Covers the optional subtitle
bits — water level, multi-pass, edge mopping — which only appear under
non-default settings and were previously untested.

Coverage targets
----------------
[SPL-1] non-default settings → water level, "N Passes", and "Edge Mopping"
        all appear in the subtitle, alongside intensity + fan.
[SPL-2] default settings (water off, single pass, no edge) → those optional
        bits are omitted.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.learning.manager import _settings_profile_label


def test_settings_profile_label_full_subtitle():
    """[SPL-1]"""
    out = _settings_profile_label(
        room_slug="kitchen",
        clean_mode="vacuum_mop",
        clean_intensity="Deep",
        fan_speed="Max",
        water_level="High",
        clean_passes=2,
        edge_mopping=True,
    )
    sub = out["profile_subtitle"]
    assert sub
    assert "High" in sub          # water_label branch (water != off)
    assert "2 Passes" in sub      # passes_value > 1 branch
    assert "Edge Mopping" in sub  # edge_enabled branch
    assert "Deep" in sub and "Max" in sub  # intensity + fan


def test_settings_profile_label_defaults_omit_optional_bits():
    """[SPL-2]"""
    out = _settings_profile_label(
        room_slug="kitchen",
        clean_mode="vacuum",
        clean_intensity="Quick",
        fan_speed="Standard",
        water_level="Off",
        clean_passes=1,
        edge_mopping=False,
    )
    sub = out["profile_subtitle"] or ""
    assert "Passes" not in sub        # single pass omitted
    assert "Edge Mopping" not in sub  # edge off omitted
    assert "Off" not in sub           # water "off" omitted
