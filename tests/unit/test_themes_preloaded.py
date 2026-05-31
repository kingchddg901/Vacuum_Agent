"""Unit tests for themes/preloaded.py — built-in theme library seeding.

ensure_preloaded_theme_library builds every PRELOADED_THEME_SPEC via the
release-colour/token builders, so one call exercises the bulk of the module.

Coverage targets
----------------
[THM-1] populates the library + sets a default theme id.
[THM-2] idempotent — existing user themes + default are preserved.
[THM-3] a non-dict library value is replaced with a fresh dict.
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
