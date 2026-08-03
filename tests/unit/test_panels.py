"""Unit tests for panels.py — the pure sidebar-title + url helpers.

effective_panel_title decides each vacuum's sidebar entry name; the default
("Vacuum Agent") must hold for unset/blank/None records so existing single-vacuum
installs are unchanged, and a stored title wins (trimmed).

Also covers async_register_vacuum_panel's duplicate-url return value and the
append_to_panel_ledger helper (RP-039/RF-16) — both need ``hass``, so those two
tests are ``async def`` despite living in this otherwise-pure-logic file.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.panels import (
    DEFAULT_PANEL_TITLE,
    append_to_panel_ledger,
    async_register_vacuum_panel,
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


async def test_duplicate_registration_returns_existing_url_not_none(hass, monkeypatch):
    """RP-039/RF-16: a duplicate-registration ValueError must return the EXISTING
    url, not None -- __init__.py's own startup ledger loop does
    `if panel_url: registered_panels.append(...)`, so returning None here meant a
    panel that was already live (registered by one of the two orphan sites this
    packet fixes) never landed in ANY teardown ledger and could never be cleanly
    removed."""
    import homeassistant.components.panel_custom as panel_custom

    calls = {"n": 0}

    async def _fake_register(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        raise ValueError("already registered")

    monkeypatch.setattr(panel_custom, "async_register_panel", _fake_register)

    first = await async_register_vacuum_panel(hass, "vacuum.ivy", title="Ivy")
    second = await async_register_vacuum_panel(hass, "vacuum.ivy", title="Ivy")

    assert first == "eufy-vacuum-ivy"
    assert second == "eufy-vacuum-ivy"  # NOT None


async def test_append_to_panel_ledger_is_idempotent(hass):
    """RP-039/RF-16: append_to_panel_ledger resolves the singleton domain's one
    config entry and de-dupes repeat appends of the same url."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eufy_vacuum.const import DOMAIN

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    append_to_panel_ledger(hass, entry.entry_id, "eufy-vacuum-ivy")
    append_to_panel_ledger(hass, entry.entry_id, "eufy-vacuum-ivy")
    append_to_panel_ledger(hass, entry.entry_id, "eufy-vacuum-bertie")

    ledger = hass.data[DOMAIN][f"_panels_{entry.entry_id}"]
    assert ledger == ["eufy-vacuum-ivy", "eufy-vacuum-bertie"]
