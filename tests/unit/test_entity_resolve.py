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


def _install(monkeypatch, *, present, registry_ids, config_entry_id="CE1", keys=None,
             classes=None):
    """Wire a fake state machine + entity registry into the module under test.

    ``classes`` maps entity_id -> device class, for the rung-4 (device_class) tests.
    Entries built without it carry ``device_class=None``, which is what a provider that
    declares none looks like — so the rung stays inert for every pre-existing test."""
    hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda eid: object() if eid in present else None)
    )
    vacuum_entry = SimpleNamespace(config_entry_id=config_entry_id, device_id="D1")
    reg = _FakeRegistry(registry_ids, vacuum_entry)
    monkeypatch.setattr(entity_resolve, "er", SimpleNamespace(
        async_get=lambda _h: reg,
        async_entries_for_config_entry=lambda _r, _ce: [
            SimpleNamespace(
                entity_id=e,
                translation_key=(keys or {}).get(e),
                device_class=None,
                original_device_class=(classes or {}).get(e),
            )
            for e in registry_ids
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
        # `via` records WHICH path rescued it. Additive (every consumer tests
        # `role in remaps`, none destructures), and it exists so a "why did this
        # bind?" surface can stop saying "matched by suffix" about a role that was
        # matched by an upstream translation key instead — the same manufactured
        # confidence the System tab was carrying before live:ENT-9.
        "via": "suffix",
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


# ---------------------------------------------------------------------------
# [TK] A LOCALIZED entity id cannot be matched by suffix.
#
# Home Assistant slugs an entity id from the TRANSLATED name at creation time, so a
# German install names the Roborock filter sensor `..._verbleibende_filterzeit` where
# the adapter declares `filter_time_left`. There is no shared suffix to find — this is
# a different failure from ER-2, where the prefix is wrong and the suffix still
# matches. Issue #51.
#
# `translation_key` is the provider's own untranslated word for the concept. Measured
# on the maintainer's install: ivy 29/32 entities carry one, robin 215/216, alfred
# 0/65 — so this is inert on Eufy by construction, which TK-4 pins.
# ---------------------------------------------------------------------------

_DE = {
    "sensor.rq_verbleibende_filterzeit": "filter_time_left",
    "sensor.rq_reinigungsbereich": "cleaning_area",
}


def test_tk1_a_localized_id_is_rescued_by_its_translation_key(monkeypatch):
    """[TK-1] The German id shares no suffix with the declaration, and still binds."""
    hass = _install(
        monkeypatch,
        present={"sensor.rq_verbleibende_filterzeit"},
        registry_ids=list(_DE),
        keys=_DE,
    )
    entities = {"filter_time_left": "sensor.alfred_filter_time_left"}

    resolved, report = resolve_declared_entities(hass, "vacuum.alfred", entities)

    assert resolved["filter_time_left"] == "sensor.rq_verbleibende_filterzeit"
    assert report["filter_time_left"]["via"] == "translation_key"


def test_tk1b_a_role_whose_upstream_key_is_not_its_slug(monkeypatch):
    """[TK-1b] issue #51: the wanted key may be DECLARED when it differs from the suffix.

    The rescue derives its wanted key from the declared suffix, on the reasoning that
    for every provider that sets one, the key IS the English slug we wrote the
    declaration from. Roborock's job_active breaks that by one word: we declare
    `_cleaning`, deriving `cleaning`; upstream publishes `in_cleaning`. On a localized
    install the id is `binary_sensor.<vid>_reinigen`, so no suffix reaches it either
    and the role resolves to nothing.

    It is not a missing sensor. `require_job_active_clear` makes that entity the single
    signal that arms completion, so unresolved it meant every run was reaped as
    `interrupted` about ten minutes after dispatch, sometimes mid-clean.

    The seam was anticipated in the source comment ("a brand whose key differs from its
    slug can declare one explicitly later") and never built. This is it.
    """
    ids = ["binary_sensor.rq_reinigen"]
    hass = _install(
        monkeypatch,
        present=set(ids),
        registry_ids=ids,
        keys={"binary_sensor.rq_reinigen": "in_cleaning"},
    )
    entities = {"job_active": "binary_sensor.alfred_cleaning"}

    # Without the declaration the derived key is "cleaning" -> no match, role unrescued.
    unrescued, _ = resolve_declared_entities(hass, "vacuum.alfred", dict(entities))
    assert unrescued["job_active"] == "binary_sensor.alfred_cleaning"

    # With it, the role binds to the German entity.
    resolved, report = resolve_declared_entities(
        hass, "vacuum.alfred", dict(entities),
        translation_keys={"job_active": "in_cleaning"},
    )
    assert resolved["job_active"] == "binary_sensor.rq_reinigen"
    assert report["job_active"]["via"] == "translation_key"


def test_tk1c_a_declared_key_only_covers_its_own_role(monkeypatch):
    """[TK-1c] the override is per-ROLE, and every other role keeps the suffix default.

    A blanket key would be worse than none: it would let one brand's exception rewrite
    the wanted key for roles that were resolving correctly.
    """
    ids = ["binary_sensor.rq_reinigen", "sensor.rq_verbleibende_filterzeit"]
    hass = _install(
        monkeypatch,
        present=set(ids),
        registry_ids=ids,
        keys={
            "binary_sensor.rq_reinigen": "in_cleaning",
            "sensor.rq_verbleibende_filterzeit": "filter_time_left",
        },
    )
    entities = {
        "job_active": "binary_sensor.alfred_cleaning",
        "filter_time_left": "sensor.alfred_filter_time_left",
    }

    resolved, _ = resolve_declared_entities(
        hass, "vacuum.alfred", entities,
        translation_keys={"job_active": "in_cleaning"},
    )
    assert resolved["job_active"] == "binary_sensor.rq_reinigen"
    # Untouched by the override, rescued by its own suffix-derived key.
    assert resolved["filter_time_left"] == "sensor.rq_verbleibende_filterzeit"


def test_tk2_the_suffix_path_still_wins(monkeypatch):
    """[TK-2] Ordering is the safety property: only a role that would resolve to
    NOTHING may reach the translation-key path, so no working install can move."""
    ids = ["sensor.dock_alfred_filter_time_left", "sensor.rq_verbleibende_filterzeit"]
    hass = _install(
        monkeypatch,
        present=set(ids),
        registry_ids=ids,
        keys={"sensor.rq_verbleibende_filterzeit": "filter_time_left"},
    )
    entities = {"filter_time_left": "sensor.alfred_filter_time_left"}

    resolved, report = resolve_declared_entities(hass, "vacuum.alfred", entities)

    assert resolved["filter_time_left"] == "sensor.dock_alfred_filter_time_left"
    assert report["filter_time_left"]["via"] == "suffix"


def test_tk3_two_entities_sharing_a_key_refuse(monkeypatch):
    """[TK-3] Exactly-one-or-nothing, as everywhere else. A wrong consumable reports
    confident, wrong remaining life and never errors."""
    ids = ["sensor.a_thing", "sensor.b_thing"]
    hass = _install(
        monkeypatch,
        present=set(ids),
        registry_ids=ids,
        keys={"sensor.a_thing": "filter_time_left", "sensor.b_thing": "filter_time_left"},
    )
    entities = {"filter_time_left": "sensor.alfred_filter_time_left"}

    resolved, report = resolve_declared_entities(hass, "vacuum.alfred", entities)

    assert resolved["filter_time_left"] == "sensor.alfred_filter_time_left"
    assert report == {}


def test_tk4_a_provider_setting_no_keys_is_untouched(monkeypatch):
    """[TK-4] Eufy sets no translation_key on any of 65 entities. The whole path must
    be inert there rather than degrading Eufy resolution in any way."""
    hass = _install(
        monkeypatch,
        present={"sensor.rq_verbleibende_filterzeit"},
        registry_ids=["sensor.rq_verbleibende_filterzeit"],
        keys={},
    )
    entities = {"filter_time_left": "sensor.alfred_filter_time_left"}

    resolved, report = resolve_declared_entities(hass, "vacuum.alfred", entities)

    assert resolved["filter_time_left"] == "sensor.alfred_filter_time_left"
    assert report == {}


def test_tk5_domain_is_part_of_the_match():
    """[TK-5] A button carrying the same key is not a sensor."""
    sibs = ["button.rq_filter_zurucksetzen"]
    keys = {"button.rq_filter_zurucksetzen": "filter_time_left"}

    assert entity_resolve.rescue_by_translation_key(
        sibs, translation_keys=keys, wanted_key="filter_time_left", domain="sensor"
    ) is None
    assert entity_resolve.rescue_by_translation_key(
        sibs, translation_keys=keys, wanted_key="filter_time_left", domain="button"
    ) == "button.rq_filter_zurucksetzen"


def test_tk6_an_empty_key_never_matches():
    """[TK-6] A role with no key must not bind every keyless sibling."""
    assert entity_resolve.rescue_by_translation_key(
        ["sensor.x"], translation_keys={"sensor.x": ""}, wanted_key="", domain="sensor"
    ) is None


# ---------------------------------------------------------------------------
# RUNG 4 — the DEVICE CLASS (issue #61)
#
# Rung 3 matches the provider's `translation_key`. Roborock sets NONE on battery or
# charging -- measured on the maintainer's box, not assumed:
#   sensor.ivy_battery          translation_key=None  original_device_class='battery'
#   binary_sensor.ivy_charging  translation_key=None  original_device_class='battery_charging'
# So a localized install resolves `active_map` (which HAS a key) and fails `battery`,
# and `get_battery_level` returns None for the whole session.
# ---------------------------------------------------------------------------

#: Issue #61's install, Spanish ids. Nothing here shares a suffix with our declarations
#: and nothing carries a translation_key -- rungs 1, 2 and 3 are all blind by construction.
_ES = {
    "sensor.alfred_bateria": "battery",
    "binary_sensor.alfred_cargando": "battery_charging",
}


def test_dc1_battery_is_rescued_by_its_device_class(monkeypatch):
    """[DC-1] issue #61. Localized id, no translation_key -- only the class is left."""
    hass = _install(
        monkeypatch,
        present={"sensor.alfred_bateria"},
        registry_ids=list(_ES),
        classes=_ES,
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.alfred_bateria"
    assert report["battery"]["via"] == "device_class"


def test_dc2_charging_proves_the_table_is_not_derivable_from_the_suffix(monkeypatch):
    """[DC-2] `charging` is declared `_charging` but its device class is
    `battery_charging`. Deriving the wanted class from the suffix -- the way rung 3
    derives its wanted key -- would miss this role entirely, which is why
    ROLE_DEVICE_CLASSES is a table."""
    hass = _install(
        monkeypatch,
        present={"binary_sensor.alfred_cargando"},
        registry_ids=list(_ES),
        classes=_ES,
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"charging": "binary_sensor.alfred_charging"}
    )
    assert out["charging"] == "binary_sensor.alfred_cargando"
    assert report["charging"]["via"] == "device_class"


def test_dc3_two_battery_sensors_rescue_nothing(monkeypatch):
    """[DC-3] THE safety property for this rung, and why it is last.

    Device classes are deliberately non-unique: a dock with its own pack publishes a
    second `battery` sensor on the same device. Reporting the dock's charge as the
    robot's is WRONG data, not missing data -- every consumer would believe it."""
    two = {
        "sensor.alfred_bateria": "battery",
        "sensor.base_alfred_bateria": "battery",
    }
    hass = _install(
        monkeypatch,
        present=set(two),
        registry_ids=list(two),
        classes=two,
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.alfred_battery", "must not guess between two packs"
    assert "battery" not in report


def test_dc4_translation_key_outranks_device_class(monkeypatch):
    """[DC-4] Rung order. The provider's own word for the concept is specific; a device
    class is coarse. When both could answer, rung 3 must win."""
    ids = ["sensor.alfred_bateria_dock", "sensor.alfred_nivel"]
    hass = _install(
        monkeypatch,
        present=set(ids),
        registry_ids=ids,
        keys={"sensor.alfred_nivel": "battery"},
        classes={"sensor.alfred_bateria_dock": "battery"},
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.alfred_nivel"
    assert report["battery"]["via"] == "translation_key"


def test_dc5_a_working_battery_is_never_re_pointed(monkeypatch):
    """[DC-5] Rung 4 is live on EVERY brand (unlike rung 3, which is inert without
    keys), so the never-touch-a-working-id property has to hold against it explicitly."""
    hass = _install(
        monkeypatch,
        present={"sensor.alfred_battery", "sensor.alfred_bateria"},
        registry_ids=["sensor.alfred_battery", "sensor.alfred_bateria"],
        classes={"sensor.alfred_battery": "battery", "sensor.alfred_bateria": "battery"},
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"}
    )
    assert out["battery"] == "sensor.alfred_battery"
    assert report == {}


def test_dc6_an_adapter_may_declare_its_own_class(monkeypatch):
    """[DC-6] The seam is the argument, not the table -- same shape as translation_keys."""
    hass = _install(
        monkeypatch,
        present={"sensor.alfred_deposito"},
        registry_ids=["sensor.alfred_deposito"],
        classes={"sensor.alfred_deposito": "moisture"},
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"water_tank": "sensor.alfred_water_tank"},
        device_classes={"water_tank": "moisture"},
    )
    assert out["water_tank"] == "sensor.alfred_deposito"
    assert report["water_tank"]["via"] == "device_class"


def test_dc7_domain_is_part_of_the_match():
    """[DC-7] Primitive-level, mirroring [TK-5]. `charging` is a binary_sensor; a
    `sensor` carrying device_class `battery_charging` is a different entity and must not
    satisfy it. Tested on the primitive because the resolver derives the domain from the
    declared id, so a domain bug there is invisible from the outside."""
    sibs = ["sensor.alfred_carga"]
    classes = {"sensor.alfred_carga": "battery_charging"}
    assert entity_resolve.rescue_by_device_class(
        sibs, device_classes=classes, wanted_class="battery_charging",
        domain="binary_sensor",
    ) is None
    assert entity_resolve.rescue_by_device_class(
        sibs, device_classes=classes, wanted_class="battery_charging", domain="sensor",
    ) == "sensor.alfred_carga"


def test_dc8_an_unknown_role_asks_for_nothing():
    """[DC-8] A role with no entry in ROLE_DEVICE_CLASSES derives an empty wanted class,
    and an empty wanted class must match NOTHING rather than the first sibling that
    happens to declare one. This is what keeps rung 4 inert for the ~40 roles it has no
    opinion about."""
    sibs = ["sensor.alfred_bateria"]
    classes = {"sensor.alfred_bateria": "battery"}
    assert entity_resolve.rescue_by_device_class(
        sibs, device_classes=classes, wanted_class="", domain="sensor",
    ) is None


# ---------------------------------------------------------------------------
# [ER-18]..[ER-21], [TK-7]/[TK-8], [DC-9]/[DC-10]
#
# WHY NO FIXTURE HERE CARRIES A TORN REGISTRY ROW, measured rather than assumed. The
# three rungs each guard their sibling walk with `not isinstance(sibling, str)` (lines
# 228, 494, 568), which reads as a tolerant reader worth covering. It is not reachable
# from this entry point: `resolve_declared_entities` builds its rung-1/2 candidate list
# at :804-805 with a BARE `e.entity_id.startswith(f"{domain}.")` and no such guard, so
# a non-string entity_id raises there first -- three of these tests were red on exactly
# that before the fixtures were corrected.
#
# And the shape cannot arrive at all: HA declares `RegistryEntry.entity_id: str`
# (attr.ib, read in the installed source), so the real producer never emits it. Those
# three guards are UNREACHABLE here, not subsumed, and :805 having no guard is
# consistent with that rather than being the short copy of a replica. Recorded as a
# ceiling.
#
# [ER-18] is the exception and it is a different argument: its non-string arrives as a
# DECLARED id, which `core/manager.py:1884-1894` builds from the adapter config with no
# isinstance filter and the schema never type-checks. That one is producible.
# ---------------------------------------------------------------------------

def test_er18_the_suffix_universe_rejects_a_non_string_candidate():
    """[ER-18] The tolerant-reader half of the shared suffix predicate.

    `build_suffix_universe` has two callers and only one of them pre-filters:
    `entity_resolve.py:723` passes `[v for v in entities.values() if isinstance(v, str)]`
    while `core/capabilities.py:761-765` flattens its candidate lists with no filter at
    all. A non-string reaching `_suffix_of` there raises OUTSIDE
    `augment_candidates_from_device`'s try, so capability detection aborts and every
    feature reads unsupported.

    THE NON-STRING IS THE ONLY DISCRIMINATING SHAPE, which is the trap in this one. The
    obvious bad input is a dotless STRING -- and it is subsumed: `_suffix_of` catches
    the IndexError and returns None, which `if suffix:` drops identically, so the
    assertion passes with the guard deleted. Dropping only the `isinstance` half is the
    named red input, and it needs a value with no `.split` at all.

    The good element is paired with it so the expectation is `{"_battery"}` and not the
    empty set, which is what an un-run function also returns.
    """
    assert entity_resolve.build_suffix_universe(
        [None, "sensor.alfred_battery"], "alfred"
    ) == {"_battery"}

    # the dotless string, for the record: tolerated, and tolerated one line lower
    assert entity_resolve.build_suffix_universe(
        ["alfred_battery", "sensor.alfred_battery"], "alfred"
    ) == {"_battery"}


def test_er19_a_reserved_suffix_must_be_a_non_empty_string():
    """[ER-19] The other half of the same predicate, on the argument that does the work.

    The module says so itself at :661-665 -- "WHAT ACTUALLY PROTECTS A COLLISION PAIR
    HERE IS reserved_suffixes, not the override." A junk element leaking into the
    universe is handed to `claimed_by`, where `sibling_object.endswith(None)` raises
    TypeError outside any try at `capabilities.py:812`, turning the ownership test into
    a crash.

    THE EXPECTATION IS AN EXACT SET, which is what makes the empty string observable:
    `""` would otherwise enter silently and `"_dock" in universe` would still pass.
    Dropping the truthiness half of `isinstance(reserved, str) and reserved` is the
    named red input for the empty string; replacing the whole condition with `if True:`
    is the one for `None`.
    """
    assert entity_resolve.build_suffix_universe(
        ["sensor.alfred_battery"], "alfred", reserved_suffixes=["_dock", "", None]
    ) == {"_battery", "_dock"}


def test_er20_an_empty_token_set_owns_nothing():
    """[ER-20] The ownership rule is not satisfied VACUOUSLY.

    The empty set is a proper subset of every non-empty rival, so without the early
    return every id a rival explains is reported "owned elsewhere" -- the guard inverts
    into a blanket exclusion and the token fallback (the last resort for a dock button,
    issue #49) can return nothing at all.

    THREE READINGS OF ONE RIVAL, asymmetric by construction. The vacuous case must be
    False; a strictly-more-specific rival over a shorter wanted set must be True; and
    the same wanted set against an id the rival does NOT explain must be False. A lone
    `is False` assertion is invariant under deleting the guard whenever the rival cannot
    match the id, which is why the True case shares the fixture.
    """
    rivals = [["stop", "dry", "mop"]]

    assert entity_resolve.tokens_owned_elsewhere(
        "button.alfred_stop_dry_mop", [], rivals
    ) is False, "an empty wanted set must own nothing, not everything"
    assert entity_resolve.tokens_owned_elsewhere(
        "button.alfred_stop_dry_mop", ["dry", "mop"], rivals
    ) is True
    assert entity_resolve.tokens_owned_elsewhere(
        "button.alfred_dry_mop", ["dry", "mop"], rivals
    ) is False


def test_er21_a_malformed_override_cannot_destroy_a_working_binding(monkeypatch):
    """[ER-21] An override is PINNED before anything else runs and REPLACES the
    declared id (entity_resolve.py:647-648, 678-681), so a value that is not an entity
    id must not be pinned -- the role's real derived id would be gone and there is no
    repair path back.

    THE CONTROL IS THAT THE DECLARED ID STILL RESOLVES. Asserting the override was
    ignored is only meaningful against a binding that works: `sensor.alfred_battery` is
    present, so the expected value is the one rung 1 returns, and a pinned
    `alfred_battery` is both wrong and unresolvable.

    Dropping the `"." in _chosen` half is the named red input. The `isinstance` half is
    crossed by the integer override in the same call and is not separately asserted --
    an int has no `.split`, so it would be refused one rung lower regardless.
    """
    hass = _install(
        monkeypatch,
        present={"sensor.alfred_battery"},
        registry_ids=["sensor.alfred_battery"],
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred", {"battery": "sensor.alfred_battery"},
        overrides={"battery": "alfred_battery", "charging": 7},
    )

    assert out["battery"] == "sensor.alfred_battery", (
        "a dotless override was pinned over a working binding"
    )
    assert "charging" not in out
    assert report == {}


def test_tk7_rung_three_never_repairs_a_role_onto_its_own_declared_id(monkeypatch):
    """[TK-7] The translation-key rung's `exclude`, on the rung the act path never had.

    A declared English id that is REGISTERED BUT DISABLED carries the provider's
    `translation_key` -- which is exactly the key this rung derives from the declared
    suffix (:819-823) -- so it is the likeliest self-match in the whole ladder.
    `async_entries_for_config_entry` applies no disabled filter, which this module's
    own docstring at :385-391 relies on, so the declared id really is in the sibling
    list while having no state.

    THE SECOND ROLE SUPPLIES THE ASYMMETRY. `report == {}` is what a never-run rescue
    returns, so the expectation is `{"mop_intensity"}` -- that proves rung 3 ran at all,
    and the ABSENCE of `filter_time_left` from it is then load-bearing. Without the
    exclude, the user is shown a repair that did not happen, pointing at an entity with
    no state; `entity_remaps` is persisted and surfaced on the System binding screen.

    NEITHER ROLE IS IN `ROLE_DEVICE_CLASSES` on purpose. It holds only `battery` and
    `charging`, so rung 4's `wanted_class` evaluates to "" here and
    `rescue_by_device_class` returns early -- otherwise rung 4 would fire underneath
    and mask the rung being measured.
    """
    hass = _install(
        monkeypatch,
        present={"select.alfred_wisch_intensitat"},
        registry_ids=[
            "sensor.alfred_filter_time_left",       # declared, registered, no state
            "select.alfred_wisch_intensitat",
        ],
        keys={
            "sensor.alfred_filter_time_left": "filter_time_left",
            "select.alfred_wisch_intensitat": "mop_intensity",
        },
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred",
        {
            "filter_time_left": "sensor.alfred_filter_time_left",
            "mop_intensity": "select.alfred_mop_intensity",
        },
    )

    assert out["mop_intensity"] == "select.alfred_wisch_intensitat"
    assert set(report) == {"mop_intensity"}, (
        "a role was reported repaired onto its own unresolvable declared id"
    )


def test_tk8_sibling_translation_keys_omits_a_sibling_that_declares_none(monkeypatch):
    """[TK-8] The documented contract: "entity_id -> translation_key, for the siblings
    that DECLARE one". Eufy carries a key on 0 of 65 entities (measured, stated at
    :481-483), so the keyless sibling is the common case and no test had one.

    THE EXPECTATION IS AN EXACT DICT, which is what makes the empty-string key
    observable: dropping the truthiness half of `isinstance(key, str) and key` admits
    `"select.alfred_c": ""` and the equality goes red. A membership assertion would not
    see it. The `None` key is the other shape, and the integer sibling crosses the
    non-string guard at :252 -- which is subsumed (its fallthrough reaches
    `registry.async_get(7)`, which this registry answers with None anyway) and is
    therefore not asserted.
    """
    entries = {
        "select.alfred_a": SimpleNamespace(translation_key="mop_intensity"),
        "select.alfred_b": SimpleNamespace(translation_key=None),
        "select.alfred_c": SimpleNamespace(translation_key=""),
    }
    registry = SimpleNamespace(async_get=lambda eid: entries.get(eid))

    assert entity_resolve.sibling_translation_keys(
        registry, ["select.alfred_a", "select.alfred_b", "select.alfred_c", 7]
    ) == {"select.alfred_a": "mop_intensity"}


def test_dc9_rung_four_binds_only_a_sibling_whose_class_matches(monkeypatch):
    """[DC-9] Rung 4's only discriminator, and the arm no test had taken.

    `_dc_map` is non-empty on every brand (:777-780), so rung 4 is the one rung live
    everywhere, and the class comparison is the single thing stopping a same-domain
    sibling being bound to a role it has nothing to do with. [DC-1]/[DC-2] filter their
    second sibling out by DOMAIN instead, so a same-domain sibling with a DIFFERENT
    class had never reached this line. Broken, a Spanish install binds
    `sensor.alfred_deposito` (moisture) as the battery and the card reports a tank
    reading as charge -- wrong data, not missing data.

    THE TWO ROLES' CORRECT ANSWERS CROSS, and that is the cure for a severe
    equals-the-fallback trap. The obvious assertion is the negative one ("the moisture
    sensor was refused", i.e. battery keeps its declared id) -- but the declared id is
    exactly what a wholly deleted rescue returns, so it passes either way. With battery
    -> bateria and water_tank -> deposito in ONE call, each role must reject the other's
    sibling by class alone; delete the comparison and both roles see two candidates,
    `len(matches) != 1`, and both assertions go red.

    This is the shoulder just after [DC-6]'s window: that test already uses
    deposito/moisture, but only in the positive direction.
    """
    hass = _install(
        monkeypatch,
        present={"sensor.alfred_bateria", "sensor.alfred_deposito"},
        registry_ids=["sensor.alfred_bateria", "sensor.alfred_deposito"],
        classes={
            "sensor.alfred_bateria": "battery",
            "sensor.alfred_deposito": "moisture",
        },
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred",
        {"battery": "sensor.alfred_battery", "water_tank": "sensor.alfred_water_tank"},
        device_classes={"water_tank": "moisture"},
    )

    assert out["battery"] == "sensor.alfred_bateria"
    assert out["water_tank"] == "sensor.alfred_deposito"
    assert {r: v["via"] for r, v in report.items()} == {
        "battery": "device_class", "water_tank": "device_class"
    }


def test_dc10_rung_four_never_repairs_a_role_onto_its_own_declared_id(monkeypatch):
    """[DC-10] The same refusal as [TK-7], one rung lower, where the self-match is by
    device class rather than translation key.

    A disabled or orphaned registry entry for the declared id keeps its
    `original_device_class`, so it is the single class match for its own role. Without
    the exclude, `report["battery"]` gains a row saying declared == resolved -- a repair
    that did not happen, written to `entity_remaps` and shown to the user, pointing at
    an entity with no state.

    THE REPORT IS THE OBSERVABLE, NOT THE ENTITY MAP. `out["battery"]` is UNCHANGED
    under the mutation -- the self-match writes the same string back -- so an assertion
    on the entities alone is a pure identity. And `report == {}` is the fallback, so the
    charging role is rescued in the same call to make the expected report the asymmetric
    `{"charging"}`.
    """
    hass = _install(
        monkeypatch,
        present={"binary_sensor.alfred_cargando"},
        registry_ids=["sensor.alfred_battery", "binary_sensor.alfred_cargando"],
        classes={
            "sensor.alfred_battery": "battery",          # the declared id itself
            "binary_sensor.alfred_cargando": "battery_charging",
        },
    )
    out, report = resolve_declared_entities(
        hass, "vacuum.alfred",
        {
            "battery": "sensor.alfred_battery",
            "charging": "binary_sensor.alfred_charging",
        },
    )

    assert out["charging"] == "binary_sensor.alfred_cargando"
    assert set(report) == {"charging"}, (
        "battery was reported repaired onto its own unresolvable declared id"
    )
