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


# ---------------------------------------------------------------------------
# The SHARED suffix predicate (2026-08-15). It existed three times -- here, in
# capabilities.augment_candidates_from_device, and a weaker third copy in
# _rescue_maintenance_source with NO exclusivity guard at all. Fixes landed in
# one copy at a time (live:ENT-1, ENT-4, ENT-5, ENT-8, then arming ENT-4 on a
# second brand as its own commit), which is why the same hostile install kept
# finding the next unrepaired copy.
#
# These pin the SEMANTICS the copies must share, so a fifth consumer inherits
# every scar already paid for instead of inventing recovery slightly differently.
# ---------------------------------------------------------------------------

from custom_components.eufy_vacuum.adapters.entity_resolve import (  # noqa: E402
    build_suffix_universe,
    claimed_by,
    rescue_by_suffix,
)


def test_er10_longest_suffix_owns_the_id():
    """[ER-10] The collision that made this necessary: per-run vs lifetime.

    `_cleaning_area` also ends `..._total_cleaning_area`. Without longest-wins,
    a per-run metric binds to a LIFETIME TOTAL -- wrong data, not missing data,
    and it reads as working. Found live at 17,975 ft2 against a real sensor
    reading 0.0, feeding the learning store and battery metrics.
    """
    universe = {"_cleaning_area", "_total_cleaning_area"}
    assert claimed_by("alfred_total_cleaning_area", universe) == "_total_cleaning_area"
    assert claimed_by("alfred_cleaning_area", universe) == "_cleaning_area"


def test_er11_rescue_abstains_when_the_match_belongs_to_another_role():
    """[ER-11] A sibling whose rightful owner is a LONGER suffix is not a match."""
    siblings = ["sensor.dining_room_alfred_total_cleaning_area"]
    universe = {"_cleaning_area", "_total_cleaning_area"}
    assert rescue_by_suffix(
        siblings, wanted_suffix="_cleaning_area", domain="sensor", universe=universe
    ) is None


def test_er12_rescue_finds_the_single_safe_sibling():
    """[ER-12] The whole point: a renamed/dock-owned entity is recovered."""
    siblings = ["sensor.dining_room_alfred_dock_status", "sensor.other_thing"]
    assert rescue_by_suffix(
        siblings, wanted_suffix="_dock_status", domain="sensor",
        universe={"_dock_status"},
    ) == "sensor.dining_room_alfred_dock_status"


def test_er13_zero_and_multiple_matches_both_abstain():
    """[ER-13] Exactly-one or nothing (live:ENT-6).

    Two matches means we cannot tell which is right, and a confident wrong answer
    is worse than an absent one -- a component bound to the wrong consumable
    reports wrong remaining life without ever erroring.
    """
    universe = {"_dock_status"}
    assert rescue_by_suffix([], wanted_suffix="_dock_status", domain="sensor",
                            universe=universe) is None
    two = ["sensor.a_dock_status", "sensor.b_dock_status"]
    assert rescue_by_suffix(two, wanted_suffix="_dock_status", domain="sensor",
                            universe=universe) is None


def test_er14_domain_is_part_of_the_match():
    """[ER-14] A button never satisfies a sensor role, however well the name fits."""
    siblings = ["button.dining_room_alfred_dock_status"]
    assert rescue_by_suffix(
        siblings, wanted_suffix="_dock_status", domain="sensor",
        universe={"_dock_status"},
    ) is None


def test_er15_reserved_suffixes_protect_a_role_the_brand_never_binds():
    """[ER-15] A brand should not have to BIND a role to be protected from it.

    Roborock declares `_cleaning_area` and binds no lifetime role at all, so a
    universe derived from its bindings alone let the lifetime counter be accepted
    as the per-run sensor. The brand's full vocabulary closes it.
    """
    declared = ["sensor.ivy_cleaning_area"]
    universe = build_suffix_universe(
        declared, "ivy", reserved_suffixes=["_total_cleaning_area"]
    )
    assert universe == {"_cleaning_area", "_total_cleaning_area"}
    assert rescue_by_suffix(
        ["sensor.ivy_total_cleaning_area"], wanted_suffix="_cleaning_area",
        domain="sensor", universe=universe,
    ) is None


def test_er16_the_two_copies_now_agree_by_construction(monkeypatch):
    """[ER-16] The regression this refactor exists to prevent.

    capabilities.augment_candidates_from_device held an independently-written
    twin of this predicate. They are the SAME FUNCTION now; this asserts the
    import identity so a future 'local copy for convenience' fails loudly rather
    than drifting silently for months.
    """
    from custom_components.eufy_vacuum.core import capabilities

    assert capabilities.build_suffix_universe is build_suffix_universe
    assert capabilities.claimed_by is claimed_by
    assert capabilities.rescue_by_suffix is rescue_by_suffix


def test_er17_a_working_install_never_consults_the_rescue(monkeypatch):
    """[ER-17] THE NO-OP INVARIANT, asserted structurally rather than inferred.

    Chris: "a good test of the no op will be my own system i work now this cant
    break me." An unchanged suite is necessary evidence and not sufficient -- this
    pins the property directly: when every declared id resolves, the sibling
    search is never even reached, so there is no path by which a healthy install
    can be altered.
    """
    calls: list[str] = []

    def _boom(*a, **k):  # pragma: no cover - must never run
        calls.append("sibling_search")
        raise AssertionError("the rescue was consulted on a healthy install")

    monkeypatch.setattr(entity_resolve.er, "async_entries_for_config_entry", _boom)

    entities = {
        "battery": "sensor.alfred_battery",
        "dock_status": "sensor.alfred_dock_status",
    }
    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda eid: object()),   # everything resolves
    )
    out, report = resolve_declared_entities(hass, "vacuum.alfred", dict(entities))

    assert out == entities, "a healthy install must resolve byte-identically"
    assert report == {}, "nothing was rescued, so nothing is reported"
    assert not calls
