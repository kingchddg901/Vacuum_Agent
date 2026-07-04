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
[NPS-1] _normalize_profile_setting resolves an aliased display string ("Vacuum
        and mop") to its canonical code ("vacuum_mop") via the alias map.
[NPS-2] alias lookup is case/punctuation/whitespace-insensitive: "vacuum & mop",
        "VACUUM AND MOP", "  Vacuum   and  mop " all resolve to "vacuum_mop", and
        "BoostIQ" resolves to "boost".
[NPS-3] a value that already slugs to its canonical code passes through unchanged
        (e.g. "vacuum"/"Vacuum" → "vacuum", "Standard" → "standard").
[NPS-4] an un-aliased multi-word value slugs to underscores gracefully
        ("Some New Mode" → "some_new_mode") with an empty alias map.
[NPS-5] empty/None stays falsy — "" → "" and None → None are preserved.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.eufy.vocabulary import (
    CLEAN_MODE_ALIASES,
    FAN_SPEED_ALIASES,
)
from custom_components.eufy_vacuum.learning.manager import (
    _normalize_profile_setting,
    _profile_name_label,
    _settings_profile_label,
)


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


# ---------------------------------------------------------------------------
# _normalize_profile_setting — display-string -> canonical-code normalizer.
#
# Room-profile settings are stored as un-normalized display strings; the card's
# vocab is keyed on canonical codes. The learning manager normalizes through the
# adapter's alias maps before emitting so the card never gets a raw display
# string (which would slug to a missing vocab key and leak English).
# ---------------------------------------------------------------------------


def test_normalize_profile_setting_aliased_to_canonical():
    """[NPS-1] an aliased display string resolves to its canonical code."""
    assert _normalize_profile_setting("Vacuum and mop", CLEAN_MODE_ALIASES) == "vacuum_mop"


def test_normalize_profile_setting_alias_variants_all_resolve():
    """[NPS-2] case + punctuation + whitespace variants normalize identically."""
    for raw in ("vacuum & mop", "VACUUM AND MOP", "  Vacuum   and  mop "):
        assert _normalize_profile_setting(raw, CLEAN_MODE_ALIASES) == "vacuum_mop"
    assert _normalize_profile_setting("BoostIQ", FAN_SPEED_ALIASES) == "boost"


def test_normalize_profile_setting_canonical_passthrough():
    """[NPS-3] a value that already slugs to its canonical code is unchanged."""
    assert _normalize_profile_setting("vacuum", CLEAN_MODE_ALIASES) == "vacuum"
    assert _normalize_profile_setting("Vacuum", CLEAN_MODE_ALIASES) == "vacuum"
    assert _normalize_profile_setting("Standard", FAN_SPEED_ALIASES) == "standard"
    assert _normalize_profile_setting("turbo", FAN_SPEED_ALIASES) == "turbo"


def test_normalize_profile_setting_unaliased_slugs():
    """[NPS-4] an un-aliased multi-word value slugs to underscores (graceful)."""
    assert _normalize_profile_setting("Some New Mode", {}) == "some_new_mode"


def test_normalize_profile_setting_empty_passthrough():
    """[NPS-5] empty/None stays falsy — 'no setting configured' is preserved."""
    assert _normalize_profile_setting("", CLEAN_MODE_ALIASES) == ""
    assert _normalize_profile_setting(None, CLEAN_MODE_ALIASES) is None
