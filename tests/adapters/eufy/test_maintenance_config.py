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


def test_label_key_survives_config_build(hass):
    """The per-brand DISPLAY key survives the adapter's explicit-key reconstruction —
    SAME class as #38: a new field silently dropped by the fixed whitelist. Without it
    the canonical component key (main_brush) title-cases to "Main Brush" on the card
    instead of Eufy's translated "Rolling Brush" (caught live, not by the green suite).
    A canonicalized Eufy component carries its legacy display key; an unchanged one carries
    none (the card then uses the component key directly).

    IDS UPDATED 2026-09-12 with the regime/key port: `caster_wheel` -> `omnidirectional_wheel`
    and `mop_cloth` -> `mop`, which are the ids the shared emitter produces. The label_key
    CONTRACT is unchanged and is still what this test guards.

    `mop` deliberately carries NO label_key now. Eufy's word was "Mopping Cloth", which is
    wrong on five of its ten mop-bearing models (S1, S1 Pro and E28 are rollers; C20 and X10
    Pro Omni are pads). `mop` is correct for all four shapes."""
    mc = _maintenance_components(hass)
    assert mc["main_brush"]["label_key"] == "rolling_brush"
    assert mc["omnidirectional_wheel"]["label_key"] == "swivel_wheel"
    assert mc["mop"].get("label_key") is None
    assert mc["filter"].get("label_key") is None
