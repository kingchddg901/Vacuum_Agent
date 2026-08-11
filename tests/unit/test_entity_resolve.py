"""[ER] Derived entity IDs that do not match the install get rescued — carefully.

Motivated by two live reports and one reproduction on our own hardware:

- Eufy's DOCK is a separate device, so four dock-owned roles resolve to nothing while
  the entities plainly exist (`sensor.alfred_total_cleaning_area` declared,
  `sensor.dining_room_alfred_total_cleaning_area` actual).
- HA 2026.8 removed `battery_level` from the vacuum entity, deleting the fallback that
  used to hide a missed battery sensor — so a derived ID is now load-bearing alone.

The rescue is only safe because of what it REFUSES to do, so most of these tests pin the
refusals rather than the repair.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum.adapters import entity_resolve
from custom_components.eufy_vacuum.adapters.entity_resolve import resolve_declared_entities


class _FakeRegistry:
    def __init__(self, entries, vacuum_entry):
        self._entries = entries
        self._vacuum_entry = vacuum_entry

    def async_get(self, entity_id):
        return self._vacuum_entry if entity_id == "vacuum.alfred" else None


def _install(monkeypatch, *, present, registry_ids, config_entry_id="CE1"):
    """Wire a fake state machine + entity registry into the module under test."""
    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda eid: object() if eid in present else None)
    )
    vacuum_entry = SimpleNamespace(config_entry_id=config_entry_id, device_id="D1")
    reg = _FakeRegistry(registry_ids, vacuum_entry)
    monkeypatch.setattr(entity_resolve, "er", SimpleNamespace(
        async_get=lambda _h: reg,
        async_entries_for_config_entry=lambda _r, _ce: [
            SimpleNamespace(entity_id=e) for e in registry_ids
        ],
    ))
    return hass


def test_er1_a_working_id_is_never_touched(monkeypatch):
    """[ER-1] THE safety property. A declared ID that resolves is returned verbatim,
    even when a same-suffix sibling exists that we could have "helpfully" preferred."""
    hass = _install(
        monkeypatch,
        present={"sensor.alfred_battery"},
        registry_ids=["sensor.alfred_battery", "sensor.dining_room_alfred_battery"],
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.alfred_battery"
    assert report == {}, "a working install must not be rewritten"


def test_er2_dock_owned_entity_is_rescued(monkeypatch):
    """[ER-2] The live Eufy case: declared on the robot, actual on the dock device."""
    hass = _install(
        monkeypatch,
        present={"sensor.dining_room_alfred_total_cleaning_area"},
        registry_ids=[
            "sensor.dining_room_alfred_total_cleaning_area",
            "sensor.alfred_task_status",
        ],
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred",
        {"total_cleaning_area": "sensor.alfred_total_cleaning_area"},
    )
    assert out["total_cleaning_area"] == "sensor.dining_room_alfred_total_cleaning_area"
    assert report["total_cleaning_area"] == {
        "declared": "sensor.alfred_total_cleaning_area",
        "resolved": "sensor.dining_room_alfred_total_cleaning_area",
    }, "a remap must be REPORTED, never silently applied"


def test_er3_ambiguity_refuses_to_guess(monkeypatch):
    """[ER-3] Two candidates neither of which carries the vacuum's object_id -> leave it.
    A wrong remap points the framework at another device's sensor, which is worse than
    the absence it was trying to fix."""
    hass = _install(
        monkeypatch,
        present=set(),
        registry_ids=["sensor.kitchen_dock_battery", "sensor.hall_dock_battery"],
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.alfred_battery"
    assert report == {}


def test_er4_ambiguity_broken_by_the_vacuum_object_id(monkeypatch):
    """[ER-4] Two candidates, exactly one containing the vacuum's own object_id -> that
    one. This is what makes Eufy's `<area>_<vacuum>_<suffix>` dock naming resolvable."""
    hass = _install(
        monkeypatch,
        present=set(),
        registry_ids=["sensor.other_vac_battery", "sensor.dining_room_alfred_battery"],
    )
    out, _ = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.dining_room_alfred_battery"


def test_er5_domain_must_match(monkeypatch):
    """[ER-5] A same-suffix entity in a DIFFERENT domain is not a candidate — a
    `select.*_active_map` must never be served for a declared `sensor.*_active_map`."""
    hass = _install(
        monkeypatch,
        present=set(),
        registry_ids=["select.dining_room_alfred_active_map"],
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"active_map": "sensor.alfred_active_map"}
    )
    assert out["active_map"] == "sensor.alfred_active_map"
    assert report == {}


def test_er6_no_config_entry_is_a_noop(monkeypatch):
    """[ER-6] Config-entry scoping IS the safety boundary — without one we do nothing
    rather than searching the whole registry and finding another integration's sensor."""
    hass = _install(
        monkeypatch,
        present=set(),
        registry_ids=["sensor.dining_room_alfred_battery"],
        config_entry_id=None,
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.alfred_battery"
    assert report == {}


def test_er7_registered_but_stateless_is_NOT_repaired(monkeypatch):
    """[ER-7] THE DOCUMENTED LIMIT (issue #46 shape). An entity whose ID is CORRECT but
    which has no state is not a naming problem, and this must not paper over it by
    "resolving" to the same ID and reporting a repair that did not happen."""
    hass = _install(
        monkeypatch,
        present=set(),                                   # no state
        registry_ids=["select.vlad_selected_map"],       # but registered
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.vlad", {"active_map": "select.vlad_selected_map"}
    )
    assert out["active_map"] == "select.vlad_selected_map"
    assert report == {}, "resolving an ID to itself is not a repair and must not be reported"


def test_er8_never_raises_on_a_broken_registry(monkeypatch):
    """[ER-8] Adapter config assembly must not be breakable by this. A registry that
    raises degrades to the declared IDs, never to an exception at startup."""
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda _e: None))

    def _boom(_h):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(entity_resolve, "er", SimpleNamespace(async_get=_boom))
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out == {"battery": "sensor.alfred_battery"}
    assert report == {}


def test_er9_non_derived_ids_are_left_alone(monkeypatch):
    """[ER-9] An ID not built from this vacuum's object_id has no suffix to match on,
    so there is nothing to search for and guessing would be unfounded."""
    hass = _install(
        monkeypatch,
        present=set(),
        registry_ids=["sensor.somethingelse_battery"],
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.handwritten_thing"}
    )
    assert out["battery"] == "sensor.handwritten_thing"
    assert report == {}
