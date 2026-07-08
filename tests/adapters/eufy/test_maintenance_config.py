"""Eufy adapter maintenance-component config tests.

Covers the ``maintenance_components`` block assembled by
``register_eufy_adapter_for_vacuum`` — specifically that per-component flags
survive the EXPLICIT-KEY reconstruction in ``adapters/eufy/adapter.py``.

Regression for issue #38: that reconstruction rebuilds each component dict from a
fixed whitelist of keys, and silently dropped the new ``maintenance_only`` flag —
so ``MAINTENANCE_COMPONENTS`` said the cleaning tray was maintenance-only but the
registered config didn't, and the card kept rendering it as a Replacement row.
The direct-``register_adapter_config`` unit tests couldn't catch this because they
bypass the adapter's reconstruction; these build the real config.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.eufy.adapter import (
    register_eufy_adapter_for_vacuum,
)
from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    get_adapter_config,
)

_VAC = "vacuum.alfred"


def _maintenance_components(hass) -> dict:
    """Build + register the real Eufy config and return its component catalog."""
    clear_registry()
    # A model the catalog recognises so the real build path runs.
    hass.states.async_set(_VAC, "docked", {"detected_model": "T2351"})
    register_eufy_adapter_for_vacuum(hass, _VAC)
    return (get_adapter_config(_VAC) or {}).get("maintenance_components", {})


def test_maintenance_only_flag_survives_config_build(hass):
    """The cleaning tray's maintenance_only=True survives the adapter's explicit-key
    reconstruction (regression for #38)."""
    mc = _maintenance_components(hass)
    assert mc["cleaning_tray"]["maintenance_only"] is True


def test_wear_parts_default_to_not_maintenance_only(hass):
    """A normal wear part (filter) defaults to maintenance_only=False, so it still
    renders as a Replacement item."""
    mc = _maintenance_components(hass)
    assert mc["filter"]["maintenance_only"] is False
