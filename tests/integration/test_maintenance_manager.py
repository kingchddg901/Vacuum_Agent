"""Integration tests for maintenance/manager.py — MaintenanceManager + helpers.

Pure status helpers are tested directly; the manager methods run against the
real `manager` fixture with capabilities monkeypatched to map components to
source entities.

Coverage targets
----------------
[MNT-1]  _safe_int / _safe_float sentinel handling.
[MNT-2]  _display_label: explicit map + title case + None.
[MNT-3]  _hours_text: singular/plural/fractional/negative/None.
[MNT-4]  maintenance_status buckets.
[MNT-5]  replacement_status buckets.
[MNT-6]  get_maintenance_state creates/returns the per-vacuum dict.
[MNT-7]  reset_maintenance: success snapshots usage_hours.
[MNT-8]  reset_maintenance: no source / unavailable / invalid usage.
[MNT-9]  get_maintenance_remaining computes remaining from usage - reset.
[MNT-10] get_maintenance_remaining: no source → source_available False.
[MNT-11] get_upkeep_snapshot returns a structured dict (no components).
[MNT-12] get_upkeep_snapshot populates items from an adapter maintenance component.
[MNT-13] _get_upkeep_item_guide enriches a library entry with source model info + maintenance/replacement sub-dicts; display picks by item_kind.
[MNT-14] _get_replacement_reset_entity: token_sets registry fallback resolves a differently-named reset button when no entity_suffix matches.
[MNT-14c] _get_replacement_reset_entity: entity_suffixes primary route — states-table hit + unconfigured component → None.
[MNT-14d] _get_replacement_reset_entity: entity_suffixes primary route — registry-only hit (no live state).
[MNT-15] get_upkeep_snapshot surfaces v1.11.0 lifetime totals + dock firmware from device sensors.
[MNT-16] get_upkeep_snapshot: no lifetime sensors → device_totals/dock_firmware None.
[MNT-17] get_upkeep_snapshot: placeholder/absent sensor → that field None, the rest still surface.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.maintenance.manager import (
    MaintenanceManager,
    _display_label,
    _hours_text,
    _safe_float,
    _safe_int,
    maintenance_status,
    replacement_status,
)


_VAC = "vacuum.alfred"
_SRC = "sensor.alfred_main_brush"


@pytest.fixture
def mnt(manager) -> MaintenanceManager:
    return MaintenanceManager(manager)


def _caps(manager, monkeypatch, sources):
    monkeypatch.setattr(manager, "get_vacuum_capabilities",
                        lambda **kw: {"maintenance_sources": sources, "sources": {}})


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [(5, 5), ("3.9", 3), (None, 0), ("unknown", 0)])
def test_safe_int(value, expected):
    """[MNT-1]"""
    assert _safe_int(value) == expected


def test_safe_float():
    """[MNT-1]"""
    assert _safe_float("2.5") == pytest.approx(2.5)
    assert _safe_float("unavailable") == pytest.approx(0.0)


@pytest.mark.parametrize("value,expected", [
    ("replace_now", "Replace Now"), ("by_time", "By Time"),
    ("main_brush", "Main Brush"), ("", None),
])
def test_display_label(value, expected):
    """[MNT-2]"""
    assert _display_label(value) == expected


@pytest.mark.parametrize("value,expected", [
    (1, "1 hour"), (3, "3 hours"), (2.5, "2.5 hours"), (-1, None), (None, None),
])
def test_hours_text(value, expected):
    """[MNT-3]"""
    assert _hours_text(value) == expected


@pytest.mark.parametrize("remaining,interval,expected", [
    (100, 0, "unknown"), (0, 150, "replace_now"),
    (10, 150, "replace_soon"), (30, 150, "warning"), (100, 150, "good"),
])
def test_maintenance_status(remaining, interval, expected):
    """[MNT-4]"""
    assert maintenance_status(remaining_hours=remaining, interval_hours=interval) == expected


@pytest.mark.parametrize("value,expected", [
    (3, "replace_now"), (8, "replace_soon"), (12, "warning"), (50, "good"),
    (None, "unknown"), ("x", "unknown"),
])
def test_replacement_status(value, expected):
    """[MNT-5] Percentage-based buckets (issue #38) — a full-life part reads good."""
    assert replacement_status(remaining_percent=value) == expected


# ---------------------------------------------------------------------------
# state / reset / remaining
# ---------------------------------------------------------------------------

def test_get_maintenance_state(mnt):
    """[MNT-6]"""
    state = mnt.get_maintenance_state(vacuum_entity_id=_VAC)
    assert isinstance(state, dict)
    state["main_brush"] = {"x": 1}
    assert mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"] == {"x": 1}


def test_reset_success(mnt, manager, hass, monkeypatch):
    """[MNT-7]"""
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "100", {"usage_hours": 120})
    result = mnt.reset_maintenance(vacuum_entity_id=_VAC, component="main_brush")
    assert result["reset"] is True
    assert result["reset_at_usage_hours"] == pytest.approx(120.0)
    # snapshot persisted
    stored = mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"]
    assert stored["reset_at_usage_hours"] == pytest.approx(120.0)


def test_reset_failure_modes(mnt, manager, hass, monkeypatch):
    """[MNT-8]"""
    _caps(manager, monkeypatch, {})  # no source mapping
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reason"] == "no_source_entity"

    _caps(manager, monkeypatch, {"main_brush": _SRC})  # source mapped but no state
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reason"] == "source_unavailable"

    hass.states.async_set(_SRC, "100", {"usage_hours": "abc"})  # invalid
    assert mnt.reset_maintenance(
        vacuum_entity_id=_VAC, component="main_brush")["reason"] == "invalid_usage_hours"


def test_remaining_computes(mnt, manager, hass, monkeypatch):
    """[MNT-9] remaining = interval - (current_usage - reset_snapshot)."""
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    hass.states.async_set(_SRC, "0", {"usage_hours": 120})
    mnt.get_maintenance_state(vacuum_entity_id=_VAC)["main_brush"] = {
        "reset_at_usage_hours": 100.0, "reset_at": "2026-01-01"}
    result = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=150.0)
    assert result["used_since_reset_hours"] == pytest.approx(20.0)
    assert result["remaining_hours"] == pytest.approx(130.0)
    assert result["source_available"] is True


def test_remaining_no_source(mnt, manager, monkeypatch):
    """[MNT-10]"""
    _caps(manager, monkeypatch, {})
    result = mnt.get_maintenance_remaining(
        vacuum_entity_id=_VAC, component="main_brush", interval_hours=150.0)
    assert result["source_available"] is False
    assert result["remaining_hours"] == pytest.approx(150.0)


def test_upkeep_snapshot(mnt, manager, monkeypatch):
    """[MNT-11]"""
    _caps(manager, monkeypatch, {})
    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert isinstance(snap, dict)
    assert snap["replacement_items"] == []
    assert snap["maintenance_items"] == []
    assert snap["highest_priority_status"] == "good"


def test_upkeep_snapshot_with_component(mnt, manager, hass, monkeypatch):
    """[MNT-12] an adapter maintenance component drives the replacement-item loop."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"label": "Main Brush"}},
    })
    _caps(manager, monkeypatch, {"main_brush": _SRC})
    # remaining-life 40 / 300 h total = 13% → replacement_status "warning" (%-based, issue #38)
    hass.states.async_set(_SRC, "40", {"usage_hours": 260, "total_life_hours": 300})

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    items = {i["component"]: i for i in snap["replacement_items"]}
    assert "main_brush" in items
    assert items["main_brush"]["status"] == "warning"
    assert snap["highest_priority_status"] in {"warning", "replace_soon", "replace_now"}


def test_maintenance_only_component_excluded_from_replacements(mnt, manager, hass, monkeypatch):
    """[MNT-12b] a maintenance_only component is surfaced ONLY as a Maintenance item,
    never a Replacement row, and contributes no Replacement status (issue #38 tray)."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {
            "cleaning_tray": {"label": "Cleaning Tray", "maintenance_only": True},
        },
    })
    _caps(manager, monkeypatch, {"cleaning_tray": _SRC})
    # Freshly reset (100%): the old absolute-hours bug would have flagged this warning.
    hass.states.async_set(_SRC, "30", {"usage_hours": 0, "total_life_hours": 30})

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    replacement = {i["component"] for i in snap["replacement_items"]}
    maintenance = {i["component"] for i in snap["maintenance_items"]}
    assert "cleaning_tray" not in replacement
    assert "cleaning_tray" in maintenance
    assert snap["attention_count"] == 0


def _caps_with_entities(manager, monkeypatch, entities):
    """Capabilities mock that also carries the adapter 'entities' map."""
    monkeypatch.setattr(
        manager, "get_vacuum_capabilities",
        lambda **kw: {"maintenance_sources": {}, "sources": {}, "entities": entities},
    )


def test_upkeep_snapshot_device_totals_and_firmware(mnt, manager, hass, monkeypatch):
    """[MNT-15]"""
    _caps_with_entities(manager, monkeypatch, {
        "total_cleaning_area": "sensor.alfred_total_cleaning_area",
        "total_cleaning_time": "sensor.alfred_total_cleaning_time",
        "total_cleaning_count": "sensor.alfred_total_cleaning_count",
        "dock_firmware_version": "sensor.alfred_dock_firmware_version",
    })
    hass.states.async_set("sensor.alfred_total_cleaning_area", "152.5")
    hass.states.async_set("sensor.alfred_total_cleaning_time", "36000")   # 10 h in seconds
    hass.states.async_set("sensor.alfred_total_cleaning_count", "42")
    hass.states.async_set("sensor.alfred_dock_firmware_version", "1.2.3")

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert snap["device_totals"] == {"area_m2": 152.5, "time_s": 36000.0, "count": 42}
    assert snap["dock_firmware"] == "1.2.3"


def test_upkeep_snapshot_device_totals_absent(mnt, manager, monkeypatch):
    """[MNT-16]"""
    _caps_with_entities(manager, monkeypatch, {})
    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert snap["device_totals"] is None
    assert snap["dock_firmware"] is None


def test_upkeep_snapshot_device_totals_partial(mnt, manager, hass, monkeypatch):
    """[MNT-17] a placeholder/absent sensor → that field None; present ones still surface."""
    _caps_with_entities(manager, monkeypatch, {
        "total_cleaning_area": "sensor.alfred_total_cleaning_area",
        "total_cleaning_time": "sensor.alfred_total_cleaning_time",
        "dock_firmware_version": "sensor.alfred_dock_firmware_version",
    })
    hass.states.async_set("sensor.alfred_total_cleaning_area", "200")
    hass.states.async_set("sensor.alfred_total_cleaning_time", "unavailable")  # placeholder
    hass.states.async_set("sensor.alfred_dock_firmware_version", "unknown")    # placeholder
    # no total_cleaning_count entity declared at all

    snap = mnt.get_upkeep_snapshot(vacuum_entity_id=_VAC)
    assert snap["device_totals"] == {"area_m2": 200.0, "time_s": None, "count": None}
    assert snap["dock_firmware"] is None


def test_upkeep_item_guide_builds_sub_dicts(mnt):
    """[MNT-13] _get_upkeep_item_guide enriches a library entry with source model
    info + maintenance/replacement sub-dicts; display picks by item_kind."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "upkeep_catalog": {
            "model_names": {"X8": "X8 Pro"},
            "model_guide_families": {"X8": "x_series"},
            "guide_family_names": {"x_series": "X Series"},
            "guide_library": {"x_series": {"main_brush": {
                "clean_frequency": "monthly",
                "replace_frequency": "yearly",
                "steps": ["pop the cover", "pull the brush"],
                "notes": ["watch for hair"],
            }}},
        },
    })
    guide = mnt._get_upkeep_item_guide(
        vacuum_entity_id=_VAC, model_code="X8",
        component="main_brush", item_kind="replacement")
    assert guide["available"] is True
    assert guide["source_model_name"] == "X8 Pro"
    assert guide["source_guide_family_name"] == "X Series"
    assert guide["maintenance"]["frequency"] == "monthly"
    assert guide["maintenance"]["available"] is True
    assert guide["replacement"]["frequency"] == "yearly"
    # item_kind=replacement → display mirrors the replacement sub-dict
    assert guide["display"] == guide["replacement"]
    # an unknown component has no library entry → None
    assert mnt._get_upkeep_item_guide(
        vacuum_entity_id=_VAC, model_code="X8",
        component="ghost", item_kind="maintenance") is None


def test_reset_entity_suffix_states_hit(mnt, hass):
    """[MNT-14c] the adapter-declared entity_suffixes list is the PRIMARY route:
    a live states-table entry at button.{object_id}_{suffix} resolves directly
    (no token fallback needed); an unconfigured component resolves to None."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush", "main_brush_reset"],
            "token_sets": [],
        }}},
    })
    # First declared suffix is present in the states table → returned as-is.
    hass.states.async_set("button.alfred_reset_main_brush", "idle")
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) == "button.alfred_reset_main_brush"
    # A component with no reset_button config falls through every route → None.
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="ghost",
    ) is None


def test_reset_entity_suffix_registry_hit(mnt, hass):
    """[MNT-14d] the entity_suffixes primary route also resolves via the entity
    registry when there is no live state (registry.async_get branch) — the
    suffix-built entity_id is returned even though hass.states has nothing."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush", "main_brush_reset"],
            "token_sets": [],
        }}},
    })
    # No hass.states set — only a registry entry whose entity_id matches the
    # suffix-built id button.alfred_reset_main_brush.
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_reset_main_brush",
        suggested_object_id="alfred_reset_main_brush",
    )
    assert hass.states.get("button.alfred_reset_main_brush") is None
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) == "button.alfred_reset_main_brush"


def test_reset_entity_token_fallback(mnt, hass):
    """[MNT-14] when no reset_button entity_suffix matches, the token_sets
    registry fallback resolves a differently-named reset button."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush"],   # absent
            "token_sets": [["reset", "main", "brush"]],
        }}},
    })
    # The real reset button, differently named, resolved via the token fallback.
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_reset_main_brush_counter",
        suggested_object_id="alfred_reset_main_brush_counter",
    )
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) == "button.alfred_reset_main_brush_counter"


def test_reset_entity_maintenance_filter_excludes(mnt, hass):
    """[MNT-14b] a token match whose id contains 'maintenance' is excluded
    (the reset button is the upstream counter-reset, not our own sensor)."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "maintenance_components": {"main_brush": {"reset_button": {
            "entity_suffixes": ["reset_main_brush"],   # absent
            "token_sets": [["reset", "main", "brush"]],
        }}},
    })
    # The only token match carries 'maintenance' → filtered out → None.
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_reset_main_brush_maintenance",
        suggested_object_id="alfred_reset_main_brush_maintenance",
    )
    assert mnt._get_replacement_reset_entity(
        vacuum_entity_id=_VAC, component="main_brush",
    ) is None
