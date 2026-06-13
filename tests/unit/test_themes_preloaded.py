"""Unit tests for themes/preloaded.py — built-in theme library seeding.

ensure_preloaded_theme_library builds every PRELOADED_THEME_SPEC via the
release-colour/token builders, so one call exercises the bulk of the module.

Coverage targets
----------------
[THM-1] populates the library + sets a default theme id.
[THM-2] idempotent — existing user themes + default are preserved.
[THM-3] a non-dict library value is replaced with a fresh dict.
[THM-4] Colorblind Safe theme ships the CVD-validated anchor hexes.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.themes.preloaded import (
    ensure_preloaded_theme_library,
)


def test_populates_library():
    """[THM-1]"""
    data: dict = {}
    ensure_preloaded_theme_library(data)
    assert isinstance(data["library"], dict) and data["library"]
    assert "theme_follow_ha" in data["library"]
    assert data["default_theme_id"] == "theme_follow_ha"
    # each entry is a structured theme with colours/tokens
    entry = data["library"]["theme_follow_ha"]
    assert "name" in entry


def test_idempotent_preserves_user():
    """[THM-2]"""
    data = {"library": {"theme_custom": {"name": "Mine"}}, "default_theme_id": "theme_custom"}
    ensure_preloaded_theme_library(data)
    assert data["library"]["theme_custom"] == {"name": "Mine"}  # untouched
    assert data["default_theme_id"] == "theme_custom"           # kept
    assert "theme_follow_ha" in data["library"]                 # built-ins added


def test_non_dict_library_replaced():
    """[THM-3]"""
    data = {"library": "corrupt"}
    ensure_preloaded_theme_library(data)
    assert isinstance(data["library"], dict)
    assert "theme_follow_ha" in data["library"]


def test_colorblind_safe_anchors():
    """[THM-4] the Colorblind Safe theme ships the CVD-validated anchors.

    These five hexes are validated to CIEDE2000 >= 15 across all ten group
    pairs under Machado 2009 protan/deutan + Brettel 1997 tritan
    (harness/bundles/cvd-safe.mjs + harness/tests/cvd.spec.mjs). Locked here
    so a backend edit can't silently regress the colorblind palette.
    """
    data: dict = {}
    ensure_preloaded_theme_library(data)
    theme = data["library"]["theme_colorblind_safe"]
    assert theme["name"] == "Colorblind Safe"
    colors = theme["colors"]
    assert colors["--evcc-sem-success"] == "#0C8F86"
    assert colors["--evcc-sem-warning"] == "#E9A100"
    assert colors["--evcc-sem-error"] == "#D6403A"
    assert colors["--evcc-sem-info"] == "#0F4C86"
    assert colors["--evcc-text-muted"] == "#BCC2C7"
    # the rest of the semantic palette cascades from those anchors
    assert colors["--evcc-color-error"] == "var(--evcc-sem-error)"
    assert colors["--evcc-status-dot-error"] == "var(--evcc-sem-error)"
