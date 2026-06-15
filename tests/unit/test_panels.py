"""Unit tests for panels.py — the pure sidebar-title + url helpers.

effective_panel_title decides each vacuum's sidebar entry name; the default
("Vacuum Agent") must hold for unset/blank/None records so existing single-vacuum
installs are unchanged, and a stored title wins (trimmed).
"""

from __future__ import annotations

from custom_components.eufy_vacuum.panels import (
    DEFAULT_PANEL_TITLE,
    effective_panel_title,
    panel_url_for,
)


def test_effective_panel_title_defaults_when_unset():
    # None / empty / blank-only all fall back to the default (NOT hardcoded title).
    assert effective_panel_title(None) == DEFAULT_PANEL_TITLE
    assert effective_panel_title({}) == DEFAULT_PANEL_TITLE
    assert effective_panel_title({"panel_title": ""}) == DEFAULT_PANEL_TITLE
    assert effective_panel_title({"panel_title": "   "}) == DEFAULT_PANEL_TITLE
    assert effective_panel_title({"panel_title": None}) == DEFAULT_PANEL_TITLE


def test_effective_panel_title_uses_stored_title_trimmed():
    assert effective_panel_title({"panel_title": "Ivy"}) == "Ivy"
    assert effective_panel_title({"panel_title": "  Living Room Bot  "}) == "Living Room Bot"


def test_panel_url_for():
    assert panel_url_for("vacuum.ivy") == "eufy-vacuum-ivy"
    assert panel_url_for("vacuum.alfred") == "eufy-vacuum-alfred"
