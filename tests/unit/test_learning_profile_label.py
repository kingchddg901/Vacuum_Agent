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
[SPL-3] preset selected != resolved → subtitle shows 'Selected via Resolved'
        bridge label (line 186).
[SPL-4] custom/no-selected path → subtitle shows resolved label alone (line 188).
[PNL-1] a replacement-keyed name maps to its curated label (replacements branch).
[PNL-2] a non-keyed name falls through to _display_label(normalized) (line 144).
[PNL-3] an empty value short-circuits to None (empty-text guard).
"""

from __future__ import annotations

from custom_components.eufy_vacuum.learning.manager import _profile_name_label, _settings_profile_label


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


def test_settings_profile_label_preset_selected_via_resolved():
    """[SPL-3] preset selected != resolved → subtitle shows 'Selected via Resolved' (line 186).

    selected='vacuum_quick' is a known preset (so is_custom stays False) but differs
    from the resolved preset 'vacuum_deep', so the first subtitle branch fires and
    emits the bridge label 'Vacuum Quick via Vacuum Deep'.
    """
    out = _settings_profile_label(
        selected_profile_name="vacuum_quick",
        resolved_profile_name="vacuum_deep",
        clean_mode="vacuum",
    )
    assert out["is_custom_profile"] is False
    sub = out["profile_subtitle"] or ""
    assert "Vacuum Quick via Vacuum Deep" in sub
    assert out["selected_profile_label"] == "Vacuum Quick"
    assert out["resolved_profile_label"] == "Vacuum Deep"


def test_settings_profile_label_custom_falls_back_to_resolved():
    """[SPL-4] custom/no-selected path → subtitle shows resolved label alone (line 188).

    selected='custom' forces is_custom True, skipping the preset branch; the elif
    appends the resolved label 'Vacuum Deep' on its own.
    """
    out = _settings_profile_label(
        selected_profile_name="custom",
        resolved_profile_name="vacuum_deep",
        clean_mode="vacuum",
    )
    assert out["is_custom_profile"] is True
    sub = out["profile_subtitle"] or ""
    assert "Vacuum Deep" in sub
    assert "via" not in sub  # bridge branch (line 186) did NOT fire


# ---------------------------------------------------------------------------
# _profile_name_label — friendly label for a preset/custom profile name.
#
# [PNL-1] a replacement-keyed name maps to its curated label (replacements
#         branch, lines 142-143).
# [PNL-2] a non-empty, non-keyed name falls through to _display_label(normalized)
#         (line 144 fallback) — e.g. 'morning_deep' -> 'Morning Deep'.
# [PNL-3] an empty value short-circuits to None (empty-text guard, lines 131-132).
# ---------------------------------------------------------------------------


def test_profile_name_label_replacement_keyed():
    """[PNL-1] curated replacement key wins over the generic fallback."""
    assert _profile_name_label("vacuum_quick") == "Vacuum Quick"


def test_profile_name_label_fallback_display_label():
    """[PNL-2] non-keyed name title-cases via _display_label (line 144)."""
    assert _profile_name_label("morning_deep") == "Morning Deep"


def test_profile_name_label_empty_is_none():
    """[PNL-3] empty value returns None (no label to build)."""
    assert _profile_name_label("") is None
