"""Tests for core/capabilities.py — generic vacuum capability detection.

Pure HA state/registry probing driven by adapter-supplied candidate lists and
hints. Tests use the real ``hass`` fixture for the state machine + entity
registry; no manager is required.

Coverage targets
----------------
[CAP-1]  detect_capabilities: minimal (no adapter inputs) reads supported_features.
[CAP-2]  detect_capabilities: entity present → support + available flags True.
[CAP-3]  detect_capabilities: hint OR entity presence for mop/dust/path flags.
[CAP-4]  detect_capabilities: robot position needs both x and y.
[CAP-5]  _detect_maintenance_sources: suffix entity, None suffix, swivel proxy.
[CAP-6]  _find_registry_entity_by_tokens: prefix + token match.
[CAP-7]  get_vacuum_capabilities: newly-known model refreshes cached caps even with refresh=False.
[CAP-8]  detect_capabilities: an explicit supports_water_control hint wins over the
         mop-derived default (the Roborock S6 declares it False — water is unsettable).
[CAP-9]  detect_capabilities: has_attribute_rooms hint reports rooms/segments support
         WITHOUT a map entity (scalar/Tuya transport); supports_active_map stays False.
[CAP-10] refresh_vacuum_capabilities reproduces startup inputs: re-passes the adapter's
         stored model_family + capability_hints, so a refresh keeps model_family (not
         "generic") and keeps has_attribute_rooms (scalar supports_rooms).
[CAP-11] get_vacuum_capabilities self-heals a stale persisted model_family: re-detects
         (even refresh=False) when the adapter now declares a different family; idempotent.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.capabilities import (
    _detect_maintenance_sources,
    _find_registry_entity_by_tokens,
    detect_capabilities,
)
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

from homeassistant.helpers import entity_registry as er


_VAC = "vacuum.alfred"


def test_detect_minimal(hass):
    """[CAP-1] no adapter inputs → minimal map, supported_features from state."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 12})
    caps = detect_capabilities(hass, vacuum_entity_id=_VAC)
    assert caps["vacuum_entity_id"] == _VAC
    assert caps["supported_features"] == 12
    assert caps["model_family"] == "generic"
    assert caps["supports_rooms"] is False
    assert caps["supports_robot_position"] is False


def test_detect_entity_present(hass):
    """[CAP-2] declared entity in the state machine → support + available."""
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set("sensor.alfred_water", "80")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={
            "active_map": ["sensor.alfred_map"],
            "water_level": ["sensor.alfred_water"],
        },
        model_family="x10",
    )
    assert caps["model_family"] == "x10"
    assert caps["supports_active_map"] is True
    assert caps["active_map_available"] is True
    assert caps["supports_station_water"] is True
    assert caps["entities"]["active_map"] == "sensor.alfred_map"
    # mop features derive from water_level presence
    assert caps["supports_mop_features"] is True


def test_detect_hint_or_presence(hass):
    """[CAP-3] capability hints flip support True even without an entity."""
    hass.states.async_set(_VAC, "docked")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        capability_hints={
            "supports_mop_wash": True,
            "supports_empty_dust": True,
        },
    )
    assert caps["supports_mop_wash"] is True
    assert caps["supports_empty_dust"] is True
    # no path-control hint and no entity → False
    assert caps["supports_path_control"] is False


def test_detect_water_control_hint_wins(hass):
    """[CAP-8] an explicit supports_water_control=False hint overrides the mop default.

    Mop features are present (water_level entity → supports_mop_features True), which
    would otherwise derive supports_water_control True. The Roborock S6 declares
    supports_water_control False because SET_WATER_BOX/MOP_MODE are unsupported, and
    that explicit hint must win.
    """
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_water", "80")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"water_level": ["sensor.alfred_water"]},
        capability_hints={"supports_water_control": False},
    )
    # mop support is still derived from the water_level entity ...
    assert caps["supports_mop_features"] is True
    # ... but the explicit hint overrides the mop-derived water-control default.
    assert caps["supports_water_control"] is False


def test_detect_edge_mopping_hint_wins(hass):
    """[CAP-8a] REGRESSION: supports_edge_mopping / supports_passes were HARDCODED True,
    one line below the correctly hint-driven supports_water_control, so an adapter
    declaring edge mopping unsupported could not reach the gate at all. The room payload
    gate (queue_engine) reads this runtime-detected dict — not the adapter's config
    capabilities block — so Roborock's declared False was inert."""
    hass.states.async_set(_VAC, "docked")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        capability_hints={"supports_edge_mopping": False, "supports_passes": False},
    )
    assert caps["supports_edge_mopping"] is False
    assert caps["supports_passes"] is False


def test_detect_edge_mopping_defaults_true_without_a_hint(hass):
    """[CAP-8b] Eufy passes no such hint and must keep the permissive default."""
    hass.states.async_set(_VAC, "docked")
    caps = detect_capabilities(hass, vacuum_entity_id=_VAC)
    assert caps["supports_edge_mopping"] is True
    assert caps["supports_passes"] is True


def test_detect_water_control_defaults_to_mop_without_hint(hass):
    """[CAP-8] with no hint, supports_water_control still derives from mop support
    (the unchanged Eufy path)."""
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_water", "80")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"water_level": ["sensor.alfred_water"]},
    )
    assert caps["supports_mop_features"] is True
    assert caps["supports_water_control"] is True


def test_detect_attribute_rooms_hint(hass):
    """[CAP-9] has_attribute_rooms reports room/segment support without a map
    entity — the scalar/Tuya transport, where the room list lives in the vacuum's
    ``segments`` attribute and there is NO active_map sensor. supports_active_map
    must stay False: there is no map entity to dereference."""
    hass.states.async_set(_VAC, "docked")
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        capability_hints={"has_attribute_rooms": True},
    )
    assert caps["supports_rooms"] is True
    assert caps["supports_segments"] is True
    assert caps["supports_active_map"] is False
    assert caps["active_map_available"] is False


def test_detect_robot_position_needs_both(hass):
    """[CAP-4]"""
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.alfred_x", "1.0")
    # only x present → not supported
    caps = detect_capabilities(
        hass, vacuum_entity_id=_VAC,
        entity_candidates={"robot_position_x": ["sensor.alfred_x"],
                           "robot_position_y": ["sensor.alfred_y"]},
    )
    assert caps["supports_robot_position"] is False
    assert caps["robot_position_status"] == "inactive"
    # both present → supported + available
    hass.states.async_set("sensor.alfred_y", "2.0")
    caps2 = detect_capabilities(
        hass, vacuum_entity_id=_VAC,
        entity_candidates={"robot_position_x": ["sensor.alfred_x"],
                           "robot_position_y": ["sensor.alfred_y"]},
    )
    assert caps2["supports_robot_position"] is True
    assert caps2["robot_position_available"] is True
    assert caps2["robot_position_status"] == "available"


def test_detect_maintenance_sources(hass):
    """[CAP-5] full-suffix entity resolves; None suffix → None; proxy_for wins."""
    hass.states.async_set("sensor.alfred_main_brush_remaining", "90")
    hass.states.async_set("sensor.alfred_filter_remaining", "75")
    sources = _detect_maintenance_sources(
        hass,
        object_id="alfred",
        maintenance_components={
            "main_brush": {"sensor_suffix": "main_brush_remaining"},
            "side_brush": {"sensor_suffix": "side_brush_remaining"},  # no entity → None
            "no_suffix": {"sensor_suffix": None},                     # None suffix → None
            "filter": {"sensor_suffix": "filter_remaining"},
            # proxies filter when present
            "swivel_wheel": {"sensor_suffix": "swivel_wheel_remaining", "proxy_for": "filter"},
        },
    )
    assert sources["main_brush"] == "sensor.alfred_main_brush_remaining"
    assert sources["side_brush"] is None
    assert sources["no_suffix"] is None
    # swivel wheel proxies the filter entity when present
    assert sources["swivel_wheel"] == "sensor.alfred_filter_remaining"


def test_detect_maintenance_swivel_own_fallback(hass):
    """[CAP-5] proxy target absent → component falls back to its own sensor."""
    hass.states.async_set("sensor.alfred_swivel_wheel_remaining", "60")
    sources = _detect_maintenance_sources(
        hass, object_id="alfred",
        maintenance_components={
            "swivel_wheel": {"sensor_suffix": "swivel_wheel_remaining", "proxy_for": "filter"},
        },
    )
    assert sources["swivel_wheel"] == "sensor.alfred_swivel_wheel_remaining"


async def test_find_registry_entity_by_tokens(hass):
    """[CAP-6]"""
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor", "eufy_vacuum", "alfred_main_brush_life",
        suggested_object_id="alfred_main_brush_life",
    )
    found = _find_registry_entity_by_tokens(
        hass, domain="sensor", object_id_prefix="alfred",
        required_tokens=["main_brush", "life"],
    )
    assert found is not None and "main_brush_life" in found
    # a token that doesn't match → None
    miss = _find_registry_entity_by_tokens(
        hass, domain="sensor", object_id_prefix="alfred",
        required_tokens=["nonexistent_token"],
    )
    assert miss is None


def test_get_vacuum_capabilities_refreshes_when_model_newly_known(manager):
    """[CAP-7] cached caps with no detected_model + a now-known model triggers a
    refresh even with refresh=False (upgrades the cached snapshot on first detect)."""
    manager.data.setdefault("capabilities", {})[_VAC] = {"supports_rooms": True}
    out = manager.get_vacuum_capabilities(
        vacuum_entity_id=_VAC, detected_model="X8", refresh=False)
    assert out["detected_model"] == "X8"


def test_refresh_preserves_model_family_and_attribute_room_hint(hass, manager):
    """[CAP-10] A capability REFRESH must reproduce the SAME detect_capabilities
    inputs as startup by re-passing the adapter's stored model_family +
    capability_hints. Without that, refresh_vacuum_capabilities omits model_family
    (detect_capabilities defaults it to 'generic') and drops INPUT-ONLY hints like
    has_attribute_rooms — so an attribute-mode/scalar device silently loses
    supports_rooms on any refresh. Guards the live regression observed on an X10
    (detected_model 'T2351' but model_family 'generic')."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        # Attribute-mode shape: NO active_map entity at all.
        "entities": {"vacuum": _VAC},
        "model_family": "x10",
        "capability_hints": {"has_attribute_rooms": True, "supports_mop_wash": True},
        # The curated capabilities subset deliberately lacks model_family /
        # has_attribute_rooms — proving the fix reads capability_hints, not this.
        "capabilities": {"supports_path_control": True},
    })
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})

    caps = manager.refresh_vacuum_capabilities(
        vacuum_entity_id=_VAC, detected_model="T2351")

    assert caps["detected_model"] == "T2351"
    assert caps["model_family"] == "x10"          # preserved, NOT reverted to "generic"
    assert caps["supports_rooms"] is True          # via the has_attribute_rooms hint
    assert caps["supports_segments"] is True
    assert caps["supports_active_map"] is False    # no active_map entity to dereference
    assert caps["supports_mop_wash"] is True       # stored hint honored on refresh


def test_refresh_preserves_entity_overrides_and_reserved_suffixes(hass, manager):
    """[CAP-10b] The SAME rule as CAP-10, for the two inputs added after it was
    written. CAP-10 says "a refresh must reproduce the SAME detect_capabilities
    inputs as startup" and then checks model_family + capability_hints, because
    those were the only inputs that existed — a guard that EXISTS reads as
    complete, so the next two inputs were dropped in silence.

    entity_overrides is the user's explicit choice from the System tab. Dropped on
    refresh, `entity_augmentation.overrides_applied` is structurally always {} —
    so the picker never pre-selects, `system.source_override` ("Your choice") is
    unreachable in all 18 locales, and a stale override can never be reported.

    reserved_suffixes is the adapter's full suffix vocabulary. Dropped on refresh,
    the live:ENT-4 exclusivity guard runs disarmed and `cleaning_area` can rebind
    to `_total_cleaning_area` — the 17,975 ft² lifetime-counter bug — on any
    refresh of an install that was correct at startup."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"vacuum": _VAC},
        "_entity_candidates": {"cleaning_area": ["sensor.alfred_cleaning_area"]},
        "_entity_overrides": {"cleaning_area": "sensor.picked_by_the_user"},
        "_reserved_suffixes": ["_cleaning_area", "_total_cleaning_area"],
    })
    hass.states.async_set("sensor.picked_by_the_user", "3.5")
    hass.states.async_set(_VAC, "docked", {})

    caps = manager.refresh_vacuum_capabilities(vacuum_entity_id=_VAC)

    applied = (caps.get("entity_augmentation") or {}).get("overrides_applied") or {}
    assert applied.get("cleaning_area") == "sensor.picked_by_the_user", (
        "the refresh dropped entity_overrides, so the user's choice is invisible to "
        f"every consumer of the snapshot (overrides_applied={applied!r})"
    )
    assert caps["entities"].get("cleaning_area") == "sensor.picked_by_the_user"
    assert (caps.get("entity_sources") or {}).get("cleaning_area") == "override", (
        "the snapshot must attribute the binding to the user, or the System tab "
        "reports 'Name match' for an entity the user chose by hand"
    )


def test_entity_override_reaches_the_declared_entities_map(hass, manager):
    """[CAP-10c] An override must land in `config["entities"]` — the map the
    RUNTIME reads — not only in the capabilities snapshot the System tab reads.

    detect_capabilities only ever sees a 14-role candidate subset, so an override
    applied there alone was a no-op for the eleven declared-only roles (battery,
    error_message, charging, the totals, dock_firmware_version, scene_select…) and
    on Roborock, whose adapter sources none of its roles from that snapshot. The
    user picked an entity, the entry reloaded, and the binding did not move.

    Asserted through resolve_declared_entities because that is the ONE shared seam
    both brands funnel their declared map through — this file's twin is where the
    live:ENT-4 guard was fixed in one copy and not the other, and applying the
    override per-brand would rebuild exactly that hazard."""
    from custom_components.eufy_vacuum.adapters.entity_resolve import (
        resolve_declared_entities,
    )

    hass.states.async_set("sensor.alfred_battery", "82")
    hass.states.async_set("sensor.a_totally_different_battery", "77")

    declared = {"battery": "sensor.alfred_battery"}
    out, _report = resolve_declared_entities(
        hass, _VAC, dict(declared),
        overrides={"battery": "sensor.a_totally_different_battery"},
    )
    assert out["battery"] == "sensor.a_totally_different_battery", (
        "the override never reached the declared map, so the picker is a no-op for "
        "every role the runtime reads from config['entities']"
    )

    # ABLATION: the same call with no override must keep the derived binding, or
    # the assertion above would pass for a reason that has nothing to do with the
    # user's choice.
    out_plain, _ = resolve_declared_entities(hass, _VAC, dict(declared))
    assert out_plain["battery"] == "sensor.alfred_battery"

    # A role the brand never declared is still bindable: the System tab offers a
    # picker per ROLE, and refusing unknown roles here would silently drop the
    # choice for anything the adapter happens not to derive.
    out_new, _ = resolve_declared_entities(
        hass, _VAC, dict(declared),
        overrides={"mop_life": "sensor.a_totally_different_battery"},
    )
    assert out_new["mop_life"] == "sensor.a_totally_different_battery"


def test_get_vacuum_capabilities_self_heals_stale_model_family(hass, manager):
    """[CAP-11] A persisted snapshot with a stale model_family ("generic") is
    re-detected when the freshly-registered adapter now declares a better family
    ("x10") — so a detection fix lands on existing installs without a manual
    refresh, even with refresh=False. Idempotent: once healed, stored matches the
    adapter family so it does not re-detect again. (This is what made the live X10
    keep reading "generic" until the adapter began publishing model_family.)"""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "model_family": "x10",
        "capability_hints": {"supports_mop_wash": True},
        "capabilities": {},
    })
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    # Stale persisted snapshot (pre-fix): detected_model set, model_family generic.
    manager.data.setdefault("capabilities", {})[_VAC] = {
        "detected_model": "T2351", "model_family": "generic", "supports_rooms": True,
    }

    out = manager.get_vacuum_capabilities(vacuum_entity_id=_VAC, refresh=False)
    assert out["model_family"] == "x10"            # self-healed
    assert out["supports_mop_wash"] is True        # via the stored hint

    # The refresh wrote the adapter family back, so the mismatch is gone.
    assert manager.data["capabilities"][_VAC]["model_family"] == "x10"


def test_detect_zone_clean_hint_wins(hass):
    """[RC-5/CAP-2] The same shape as CAP-8a above, one finding later.

    `supports_zone_clean` was hardcoded `True` in BOTH shipped adapters' config dicts —
    not derived, not hinted, just asserted. Each had a good reason written beside it
    (no runtime probe distinguishes eufy-clean versions; the S6 zone-cleans via stock
    send_command), and both were right about their own brand. The defect is that a MODEL
    which categorically cannot zone-clean had nothing to declare against: a hardcoded
    default in the adapter config is unreachable by a model catalog entry, which is
    exactly how supports_edge_mopping stayed True for a brand declaring it False.

    True remains the default — both brands do support it — but it is now a hint.
    """
    hass.states.async_set(_VAC, "docked")

    # Default: unchanged from the hardcoded behaviour.
    caps = detect_capabilities(hass, vacuum_entity_id=_VAC)
    assert caps["supports_zone_clean"] is True

    # A model that cannot do it is now believed.
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        capability_hints={"supports_zone_clean": False},
    )
    assert caps["supports_zone_clean"] is False


# ---------------------------------------------------------------------------
# [CAP-11] live:ENT-1 — companions resolved by DEVICE as well as derived name
# ---------------------------------------------------------------------------

def _vacuum_on_device(hass, *, object_id="alfred", companions=()):
    """Register a vacuum plus companions on ONE device; return the registry."""
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain="eufy_vacuum", entry_id="cap11")
    entry.add_to_hass(hass)

    devices = dr.async_get(hass)
    registry = er.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("eufy_vacuum", "alfred-device")},
    )
    registry.async_get_or_create(
        "vacuum", "eufy_vacuum", f"{object_id}_vac",
        suggested_object_id=object_id, device_id=device.id,
    )
    for domain, obj in companions:
        registry.async_get_or_create(
            domain, "eufy_vacuum", f"uid_{domain}_{obj}",
            suggested_object_id=obj, device_id=device.id,
        )
    return registry


async def test_device_siblings_rescue_a_renamed_companion(hass):
    """[CAP-11] live:ENT-1 — an area-prefixed companion is found.

    Every companion is located by DERIVING a name from the vacuum's entity_id.
    HA does not guarantee companions are named after the vacuum: an area prefix,
    a rename, or an integration that names from the DEVICE all produce ids the
    derivation never generates. The role then reads as "this device has no such
    entity" — quietly absent rather than broken, which is the worst shape
    because nothing errors.

    PROVEN on the maintainer's own install (area-prefixed entities); issue #48
    is the reporter-facing version.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    # The device carries the entity under a DIFFERENT name than the derivation
    # would produce: downstairs_alfred_task_status, not alfred_task_status.
    _vacuum_on_device(hass, companions=[("sensor", "downstairs_alfred_task_status")])
    hass.states.async_set("sensor.downstairs_alfred_task_status", "cleaning")

    out = augment_candidates_from_device(
        hass, _VAC, {"task_status": ["sensor.alfred_task_status"]}
    )

    # The derived name is still FIRST — that is the safety property.
    assert out["task_status"][0] == "sensor.alfred_task_status"
    assert "sensor.downstairs_alfred_task_status" in out["task_status"]


async def test_derived_name_still_wins_when_it_resolves(hass):
    """[CAP-11b] live:ENT-1 — an install where derivation works is unchanged.

    This is the whole safety argument for the change: derived candidates stay
    first, and detect_capabilities' _find takes the first that EXISTS, so a
    working install never consults the device result. Only a role that would
    have resolved to nothing can now find something.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_on_device(hass, companions=[
        ("sensor", "alfred_task_status"),
        ("sensor", "downstairs_alfred_task_status"),
    ])
    out = augment_candidates_from_device(
        hass, _VAC, {"task_status": ["sensor.alfred_task_status"]}
    )
    assert out["task_status"][0] == "sensor.alfred_task_status"


async def test_augmentation_never_crosses_domains(hass):
    """[CAP-11c] live:ENT-1 — suffix alone is not enough; the DOMAIN must match.

    A `select.*_water_level` must never satisfy a role that needs the sensor.
    Matching on suffix alone would resolve the wrong entity and the failure
    would be silent — a control read as a reading.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_on_device(hass, companions=[("select", "downstairs_alfred_water_level")])
    out = augment_candidates_from_device(
        hass, _VAC, {"water_level": ["sensor.alfred_water_level"]}
    )
    assert out["water_level"] == ["sensor.alfred_water_level"], out


async def test_augmentation_degrades_rather_than_removing(hass):
    """[CAP-11d] live:ENT-1 — failing to ADD a fallback must never REMOVE one.

    No device, no registry entry, empty candidates: every degraded path returns
    what it was given. A fallback-finder that can drop candidates is worse than
    one that finds nothing.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    given = {"task_status": ["sensor.alfred_task_status"]}

    # vacuum not in the registry at all
    assert augment_candidates_from_device(hass, "vacuum.ghost", given) == given
    # no candidates to learn a suffix from
    assert augment_candidates_from_device(hass, _VAC, {}) == {}
    assert augment_candidates_from_device(hass, _VAC, None) == {}


async def test_detect_capabilities_actually_uses_the_device_fallback(hass):
    """[CAP-11e] live:ENT-1 — END TO END, through detect_capabilities.

    [CAP-11] proves the helper works; this proves it is WIRED. A helper that is
    correct and uncalled is the exact shape of a fix that looks done and changes
    nothing — and the audit's own lesson about call-site reachability.

    The vacuum's companion is named with an area prefix, so the derived id does
    not exist. Before the fix, task_status resolved to None and the capability
    read as unsupported.
    """
    _vacuum_on_device(hass, companions=[("sensor", "downstairs_alfred_task_status")])
    hass.states.async_set("sensor.downstairs_alfred_task_status", "cleaning")
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})

    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"task_status": ["sensor.alfred_task_status"]},
    )

    assert caps["entities"]["task_status"] == "sensor.downstairs_alfred_task_status", (
        "the device fallback is not wired into detect_capabilities — the role "
        "resolved to nothing even though the device exposes it"
    )


# ---------------------------------------------------------------------------
# [CAP-12] live:ENT-4 — exclusivity: a longer declared suffix owns its sibling
# ---------------------------------------------------------------------------

async def test_longer_declared_suffix_owns_the_sibling(hass):
    """[CAP-12] A per-run role must not borrow the LIFETIME TOTAL entity.

    `endswith` is unsafe when one declared suffix is a substring of another:
    `_area` also matches `..._total_area`. Both then land in the same candidate
    list and which one wins depends on entity-registry ORDER — so a per-run
    metric can silently resolve to a lifetime counter. That is wrong data, not
    missing data, which is the worse failure because it reads as working.

    CONFIRMED on real hardware: the issue #49 device carries both
    `..._cleaning_area` and `..._total_cleaning_area`.

    Deliberately brand-agnostic suffixes — the Eufy pair is asserted in
    tests/adapters/eufy/.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_on_device(
        hass,
        companions=[
            ("sensor", "downstairs_alfred_area"),
            ("sensor", "downstairs_alfred_total_area"),
        ],
    )

    given = {"area": ["sensor.alfred_area"]}
    out = augment_candidates_from_device(
        hass, _VAC, given, reserved_suffixes=("_area", "_total_area")
    )

    assert "sensor.downstairs_alfred_area" in out["area"]
    assert "sensor.downstairs_alfred_total_area" not in out["area"], (
        "the lifetime-total entity was offered to the per-run role — "
        "exclusivity is not holding"
    )


async def test_collision_ablation_without_the_vocabulary(hass):
    """[CAP-12b] The vocabulary must be load-bearing, not decorative.

    A test that passes with AND without the fix proves nothing, so withhold
    `reserved_suffixes` and assert the outcome genuinely differs.

    TWO INDEPENDENT DEFENCES now cover this collision, and the difference
    between them is the point:

      - WITHOUT the vocabulary, `_area` matches both entities, nothing can rank
        them, and live:ENT-6 refuses to guess — the role goes UNRESOLVED and is
        recorded as ambiguous. Safe, but the user gets nothing.
      - WITH it, the longer suffix claims its own entity and exactly one
        candidate survives, so the role resolves CORRECTLY.

    So the vocabulary is what converts "safely broken" into "right". Before
    live:ENT-6 landed this test asserted the collision still occurred; that is
    no longer true and asserting it would now be testing a bug we fixed twice.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_on_device(
        hass,
        companions=[
            ("sensor", "downstairs_alfred_area"),
            ("sensor", "downstairs_alfred_total_area"),
        ],
    )

    report: dict = {}
    out = augment_candidates_from_device(
        hass, _VAC, {"area": ["sensor.alfred_area"]}, report=report
    )

    assert out["area"] == ["sensor.alfred_area"], (
        "without the vocabulary neither entity can be ranked, so the role must "
        "stay unresolved rather than pick one"
    )
    assert "area" in report.get("ambiguous", {}), (
        "the competing pair must be recorded; without that the picker has "
        "nothing to offer and the user is simply stuck"
    )


# ---------------------------------------------------------------------------
# [CAP-13] live:ENT-2 — absent vs disabled are no longer the same answer
# ---------------------------------------------------------------------------

async def test_disabled_companion_is_reported_as_disabled(hass):
    """[CAP-13] A disabled entity is not a missing one, and needs the opposite fix.

    Both position sensors on the issue #49 device exist with exactly the ids we
    derive — they are switched off. A disabled entity has no state, so the role
    read as absent and we hunted a naming bug that was not there. The user fix
    is a toggle in their own UI; ours would have been code.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        REASON_ABSENT,
        REASON_DISABLED,
        REASON_RESOLVED,
        resolve_with_reason,
    )

    registry = _vacuum_on_device(hass)
    registry.async_get_or_create(
        "sensor", "eufy_vacuum", "uid_disabled",
        suggested_object_id="alfred_position_x",
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    entity_id, reason = resolve_with_reason(hass, ["sensor.alfred_position_x"])
    assert reason == REASON_DISABLED
    assert entity_id == "sensor.alfred_position_x", (
        "the id must still be reported — the user needs to know WHICH entity to enable"
    )

    assert resolve_with_reason(hass, ["sensor.alfred_nope"]) == (None, REASON_ABSENT)

    hass.states.async_set("sensor.alfred_works", "5")
    assert resolve_with_reason(hass, ["sensor.alfred_works"]) == (
        "sensor.alfred_works",
        REASON_RESOLVED,
    )


async def test_reporting_the_reason_does_not_change_resolution(hass):
    """[CAP-13b] live:ENT-2 adds explanation and NOTHING else.

    `entities` resolves each role as ``_find(...) or _find_reg(...)``, so a
    registered-but-disabled entity is deliberately still reported as the role's
    id — downstream wants to know WHICH entity, and a disabled entity can be
    enabled. That behaviour predates this change and must survive it.

    So the assertion is deliberately the unchanged value plus the new reason
    beside it. If a future refactor makes a disabled role resolve to None, that
    is a behaviour change to argue for on its own merits, not a side effect of
    adding diagnostics.
    """
    registry = _vacuum_on_device(hass)
    registry.async_get_or_create(
        "sensor", "eufy_vacuum", "uid_disabled_role",
        suggested_object_id="alfred_task_status",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})

    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"task_status": ["sensor.alfred_task_status"]},
    )

    assert caps["entities"]["task_status"] == "sensor.alfred_task_status", (
        "the registered-entity fallback stopped supplying disabled roles — that "
        "is a behaviour change, not a diagnostics change"
    )
    assert caps["entity_resolution_reasons"]["task_status"] == "disabled", (
        "the role resolved via the registry with no state; the reason must say "
        "so rather than leaving the reader to guess"
    )


# ---------------------------------------------------------------------------
# [CAP-14] live:ENT-3 — the rescue no longer fails silently
# ---------------------------------------------------------------------------

async def test_augmentation_reports_why_it_did_not_run(hass):
    """[CAP-14] "Died" and "ran and found nothing" must not look identical.

    Every early return here used to hand back the candidates unchanged with no
    log and no trace. Issue #49 cost a morning of elimination against a dump
    that could not say whether this code had executed at all.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    report: dict = {}
    given = {"task_status": ["sensor.ghost_task_status"]}
    assert augment_candidates_from_device(hass, "vacuum.ghost", given, report=report) == given
    assert report["ran"] is False
    assert report["reason"] == "vacuum_not_in_registry"


async def test_augmentation_reports_a_registry_failure(hass, monkeypatch):
    """[CAP-14b] The blanket except must leave evidence, not just a return.

    This is the path that most likely killed issue #49 on HA 2026.8.1, and it
    is unprovable precisely because it was silent.
    """
    from custom_components.eufy_vacuum.core import capabilities as cap

    _vacuum_on_device(hass, companions=[("sensor", "downstairs_alfred_task_status")])

    def _boom(*_a, **_k):
        raise RuntimeError("registry exploded")

    monkeypatch.setattr(cap.er, "async_entries_for_device", _boom)

    report: dict = {}
    given = {"task_status": ["sensor.alfred_task_status"]}
    out = cap.augment_candidates_from_device(hass, _VAC, given, report=report)

    assert out == given, "a failed augmentation must never REMOVE a candidate"
    assert report["reason"] == "registry_error"
    assert "registry exploded" in report["error"]


# ---------------------------------------------------------------------------
# [CAP-15] live:ENT-5 — config-entry scope, the half with field evidence
# ---------------------------------------------------------------------------

def _vacuum_with_scopes(hass, *, device_companions=(), config_companions=(), with_device=True):
    """Register a vacuum whose companions may sit outside its DEVICE.

    `config_companions` are registered against the same config entry with NO
    device link, which is the arrangement device-scoped lookup cannot see.
    """
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain="robovac_mqtt", entry_id="cap15")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    device_id = None
    if with_device:
        device_id = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("robovac_mqtt", "cap15-device")},
        ).id

    registry.async_get_or_create(
        "vacuum", "robovac_mqtt", "cap15_vac",
        suggested_object_id="alfred", device_id=device_id, config_entry=entry,
    )
    for domain, obj in device_companions:
        registry.async_get_or_create(
            domain, "robovac_mqtt", f"dev_{domain}_{obj}",
            suggested_object_id=obj, device_id=device_id, config_entry=entry,
        )
    for domain, obj in config_companions:
        registry.async_get_or_create(
            domain, "robovac_mqtt", f"cfg_{domain}_{obj}",
            suggested_object_id=obj, config_entry=entry,
        )
    return registry


async def test_config_entry_scope_rescues_what_device_scope_misses(hass):
    """[CAP-15] The scope with field evidence behind it.

    On issue #49 the CONFIG-ENTRY search (entity_resolve) rescued battery and
    the dock counters while the DEVICE search rescued nothing — same install,
    same instant. Searching only the device is why ten roles stayed unresolved.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_with_scopes(
        hass, config_companions=[("sensor", "living_room_robot_task_status")]
    )

    report: dict = {}
    out = augment_candidates_from_device(
        hass, _VAC, {"task_status": ["sensor.alfred_task_status"]}, report=report
    )

    assert "sensor.living_room_robot_task_status" in out["task_status"]
    assert report["device_siblings"] == 1        # the vacuum itself
    assert report["config_entry_siblings"] >= 1


async def test_a_vacuum_with_no_device_can_still_be_rescued(hass):
    """[CAP-15b] A missing device_id used to end the search immediately.

    That was one of the three surviving suspects for #49. Falling back to the
    config entry removes it as a failure mode rather than diagnosing it.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_with_scopes(
        hass,
        config_companions=[("sensor", "living_room_robot_task_status")],
        with_device=False,
    )

    report: dict = {}
    out = augment_candidates_from_device(
        hass, _VAC, {"task_status": ["sensor.alfred_task_status"]}, report=report
    )

    assert "sensor.living_room_robot_task_status" in out["task_status"]
    assert report["device_siblings"] == 0


# ---------------------------------------------------------------------------
# [CAP-16] live:ENT-6 — competing candidates are refused, not guessed
# ---------------------------------------------------------------------------

async def test_two_vacuums_on_one_config_entry_are_not_guessed(hass):
    """[CAP-16] Registry ORDER must never be the tiebreaker.

    A config entry shared by two vacuums offers two equally good companions per
    role. Appending both and taking the first that exists makes entity-registry
    insertion order the decision — which nobody chose, and which can silently
    bind a card to the WRONG MACHINE.

    entity_resolve.resolve_declared_entities already refuses in this situation;
    this asserts the candidate path now matches that discipline.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_with_scopes(
        hass,
        config_companions=[
            ("sensor", "living_room_robot_task_status"),
            ("sensor", "hallway_robot_task_status"),
        ],
    )

    report: dict = {}
    out = augment_candidates_from_device(
        hass, _VAC, {"task_status": ["sensor.alfred_task_status"]}, report=report
    )

    assert out["task_status"] == ["sensor.alfred_task_status"], (
        "a competing pair was resolved anyway — the ambiguity guard is not holding"
    )
    assert sorted(report["ambiguous"]["task_status"]) == [
        "sensor.hallway_robot_task_status",
        "sensor.living_room_robot_task_status",
    ], "both competitors must be RECORDED — that list is what the picker pre-fills"


async def test_state_class_separates_per_run_from_lifetime(hass):
    """[CAP-16b] live:ENT-9 — `state_class` decides the collision that matters.

    `cleaning_area` and `total_cleaning_area` are not merely different entities,
    they are different QUANTITIES: on live hardware 2.9 m² against 11,814.2 m².
    Binding the wrong one feeds a ~4000x error into the learning store, counter
    segmentation and battery metrics, and it never throws — a cumulative counter
    just looks like a vacuum making no progress.

    `state_class` is HA's own semantics, declared by the upstream integration:
    `measurement` is the value right now, `total` is a cumulative counter. It
    lives in the entity REGISTRY, so it works during setup with no state at all —
    and therefore on a BRAND-NEW vacuum with zero runtime, where every
    value-based test is blind.

    Shape verified against the maintainer's real registry (robovac_mqtt sets
    state_class and no translation_key).
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    registry = _vacuum_with_scopes(hass)
    device_id = registry.async_get(_VAC).device_id
    registry.async_get_or_create(
        "sensor", "robovac_mqtt", "uid_area_run",
        suggested_object_id="downstairs_alfred_area",
        device_id=device_id,
        # UNSET, not "measurement" — Dreame's real shape, and the case that
        # broke a version of this guard that required `measurement`.
        capabilities={},
    )
    registry.async_get_or_create(
        "sensor", "robovac_mqtt", "uid_area_total",
        suggested_object_id="downstairs_alfred_lifetime_area",
        device_id=device_id,
        capabilities={"state_class": "total_increasing"},
    )

    out = augment_candidates_from_device(hass, _VAC, {"area": ["sensor.alfred_area"]})

    assert "sensor.downstairs_alfred_area" in out["area"]
    assert "sensor.downstairs_alfred_lifetime_area" not in out["area"], (
        "the cumulative counter was offered to a per-run role; state_class said "
        "`total` and was ignored"
    )


async def test_translation_key_decides_when_state_class_is_absent(hass):
    """[CAP-16c] live:ENT-9 — the upstream's own name for the concept.

    Roborock sets `translation_key` and no `state_class`; robovac_mqtt does the
    opposite. Between the two signals both shipping brands are covered, which is
    why the ladder tries translation_key before state_class rather than picking
    one.

    Shape verified against the maintainer's real registry.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    registry = _vacuum_with_scopes(hass)
    device_id = registry.async_get(_VAC).device_id
    registry.async_get_or_create(
        "sensor", "robovac_mqtt", "uid_tk_run",
        suggested_object_id="downstairs_alfred_area",
        device_id=device_id, translation_key="area",
    )
    registry.async_get_or_create(
        "sensor", "robovac_mqtt", "uid_tk_total",
        suggested_object_id="downstairs_alfred_lifetime_area",
        device_id=device_id, translation_key="lifetime_area",
    )

    out = augment_candidates_from_device(hass, _VAC, {"area": ["sensor.alfred_area"]})

    assert "sensor.downstairs_alfred_area" in out["area"]
    assert "sensor.downstairs_alfred_lifetime_area" not in out["area"]


async def test_indistinguishable_candidates_still_go_to_a_human(hass):
    """[CAP-16d] live:ENT-9 — the ladder must still be able to give up.

    Two candidates with no translation_key, no state_class and no states are
    genuinely indistinguishable. Guessing there is how a card gets bound to the
    wrong machine; the honest answer is to leave the role unresolved and ask a
    question the user can actually answer.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_with_scopes(
        hass,
        config_companions=[
            ("sensor", "living_room_robot_task_status"),
            ("sensor", "hallway_robot_task_status"),
        ],
    )

    report: dict = {}
    out = augment_candidates_from_device(
        hass, _VAC, {"task_status": ["sensor.alfred_task_status"]}, report=report
    )

    assert out["task_status"] == ["sensor.alfred_task_status"]
    assert "task_status" in report.get("ambiguous", {})


# ---------------------------------------------------------------------------
# [CAP-17] live:ENT-7 — the user's override outranks everything we derived
# ---------------------------------------------------------------------------

async def test_override_beats_a_working_derived_candidate(hass):
    """[CAP-17] Ruled: "override wins — it's a user choice."

    Not a last-resort fallback. Auto-resolution can succeed and still be WRONG
    (the ENT-4 collision resolves a per-run role to a lifetime counter), and a
    fallback-only override could never correct that. So the override must beat
    a candidate that resolves perfectly well.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass.states.async_set("sensor.alfred_task_status", "cleaning")
    hass.states.async_set("sensor.the_one_i_actually_want", "docked")

    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"task_status": ["sensor.alfred_task_status"]},
        entity_overrides={"task_status": "sensor.the_one_i_actually_want"},
    )

    assert caps["entities"]["task_status"] == "sensor.the_one_i_actually_want", (
        "the derived candidate won despite an explicit user override — a user who "
        "sets one and sees nothing change is the silent failure we are removing"
    )


async def test_a_stale_override_falls_through_but_says_so(hass):
    """[CAP-17b] A user choice that stopped working must be VISIBLE.

    If the override target was renamed or deleted, pinning the dead id would
    break the role outright. Falling through keeps it working — but silently
    substituting our guess for their stated intent is exactly the failure mode
    this effort exists to remove, so the reason has to say `override_unresolved`.
    """
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    hass.states.async_set("sensor.alfred_task_status", "cleaning")

    caps = detect_capabilities(
        hass,
        vacuum_entity_id=_VAC,
        entity_candidates={"task_status": ["sensor.alfred_task_status"]},
        entity_overrides={"task_status": "sensor.deleted_last_tuesday"},
    )

    assert caps["entities"]["task_status"] == "sensor.alfred_task_status", (
        "a stale override must not pin a dead id; resolution continues"
    )
    assert caps["entity_resolution_reasons"]["task_status"] == "override_unresolved", (
        "the fall-through was reported as ordinary success, hiding a stale user "
        "decision behind a working-looking role"
    )


async def test_an_overridden_role_is_not_reported_as_ambiguous(hass):
    """[CAP-17c] Do not ask the user to decide something they already decided.

    The ambiguity list drives the picker. A role carrying an override belongs
    nowhere near it.
    """
    from custom_components.eufy_vacuum.core.capabilities import (
        augment_candidates_from_device,
    )

    _vacuum_with_scopes(
        hass,
        config_companions=[
            ("sensor", "living_room_robot_task_status"),
            ("sensor", "hallway_robot_task_status"),
        ],
    )

    report: dict = {}
    augment_candidates_from_device(
        hass,
        _VAC,
        {"task_status": ["sensor.alfred_task_status"]},
        overrides={"task_status": "sensor.hallway_robot_task_status"},
        report=report,
    )

    assert "task_status" not in report.get("ambiguous", {})
    assert report["overrides_applied"]["task_status"] == "sensor.hallway_robot_task_status"


async def test_both_brands_receive_overrides_from_the_tier(hass):
    """[CAP-17d] The mechanism is CORE's, so no brand may need its own code path.

    ISO-1 confines a brand package to the adapter SDK, so a brand must never
    import the storage key. The tier extracts it and passes the finished map —
    which is also what makes Roborock and any future brand inherit this for free.
    """
    import inspect

    from custom_components.eufy_vacuum.adapters import brands

    tier = inspect.getsource(brands.register_brand_adapter)
    assert "ENTITY_OVERRIDES_KEY" in tier, "the tier stopped resolving the overrides"
    assert "entity_overrides=" in tier, "the tier no longer passes them to the registrar"

    for registrar in brands.BRAND_REGISTRARS:
        params = inspect.signature(registrar.register).parameters
        assert "entity_overrides" in params, (
            f"{registrar.brand_id} cannot receive overrides; that brand's users "
            f"would have no way to correct a misresolved entity"
        )


# ---------------------------------------------------------------------------
# [CAP-18] live:ENT-14 — the binding table's provenance must actually arrive
# ---------------------------------------------------------------------------

async def test_entity_bindings_carry_decisions_and_overrides(hass, manager, monkeypatch):
    """[CAP-18] REGRESSION: _entity_bindings read `augmentation` one line BEFORE
    it was assigned.

    The UnboundLocalError was swallowed by the enclosing `except Exception`
    (DEBUG-logged), so the screen still rendered — just permanently stripped of
    the data that makes it worth having: the live:ENT-9 ladder rung behind
    "chosen by", the "Also matched" alternatives, the picker's pre-selection of a
    saved override, and every role the adapter PROBES rather than declares.

    Shipped in v2.1.0-beta.1. Found by the pre-release audit, not by me — I
    verified the screen visually and it looked right, because everything I
    checked came from `_entity_remaps`, computed OUTSIDE the try and therefore
    unaffected.

    THE ASSERTIONS HERE MUST DISCRIMINATE. My first version checked that the row
    KEYS existed, which passed against the bug: every one of those variables is
    pre-initialised to {} above the try, so a swallowed failure leaves an
    identical shape. Only values that can ONLY come from inside the try block
    prove it ran.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    register_adapter_config(_VAC, {
        "adapter_id": "test",
        # NOTE: task_status is deliberately NOT declared here — it must arrive
        # from the capabilities snapshot via the setdefault loop inside the try.
        "entities": {"battery": "sensor.alfred_battery"},
    })

    monkeypatch.setattr(
        manager, "get_vacuum_capabilities_snapshot",
        lambda **_: {
            "entities": {"task_status": "sensor.probed_task_status"},
            "entity_resolution_reasons": {"task_status": "resolved"},
            "entity_sources": {"task_status": "config_entry_sibling"},
            "entity_augmentation": {
                "decisions": {
                    "task_status": {
                        "by": "translation_key",
                        "rejected": {"sensor.other": "translation_key=other"},
                    },
                },
                "overrides_applied": {"task_status": "sensor.probed_task_status"},
            },
        },
        raising=False,
    )

    by_role = {r["role"]: r for r in manager._entity_bindings(_VAC)}

    # 1. a PROBED-only role reaching the table proves the setdefault loop ran
    assert "task_status" in by_role, (
        "a role that exists only in the capabilities snapshot never reached the "
        "table — the try block threw and was swallowed"
    )
    row = by_role["task_status"]
    # 2. the ladder rung proves `decisions` was populated
    assert row["chosen_by"] == "translation_key", (
        f"chosen_by={row['chosen_by']!r} — the ENT-9 ladder rung never arrived, "
        f"so 'Provided by the integration' is an unreachable label"
    )
    # 3. rejected alternatives prove the same dict carried its payload
    assert row["rejected"] == {"sensor.other": "translation_key=other"}
    # 4. the override flag proves overrides_applied was read AFTER assignment
    assert row["overridden"] is True, (
        "the picker would not pre-select the user's saved choice — they reopen "
        "the panel and see 'Automatic'"
    )


def test_binding_table_credits_an_override_on_a_declared_only_role(hass, manager):
    """[CAP-10d] A DECLARED-ONLY role that the user overrode must read as their
    choice, not as a name match.

    `overrides_applied` is written by the candidate-augmentation pass, so it only
    ever mentions roles in `entity_candidates` — 14 on Eufy, 5 on Roborock. Every
    other role (battery, the totals, dock_firmware_version, scene_select…) is
    overridden in `entities` and absent from that report. Reading only the report
    produced a row that showed the user's entity while labelling it "Name match"
    and leaving the picker on "Automatic": binding right, explanation wrong, on
    the one screen built to be trusted about exactly this.

    Verified live before it was fixed: overriding total_cleaning_count on a real
    Roborock moved `config["entities"]` but left `entity_augmentation` mentioning
    only the five candidate roles."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {
            "vacuum": _VAC,
            # Declared-only: not in _entity_candidates below.
            "total_cleaning_count": "sensor.picked_by_the_user",
        },
        "_entity_candidates": {"cleaning_area": ["sensor.alfred_cleaning_area"]},
        "_entity_overrides": {"total_cleaning_count": "sensor.picked_by_the_user"},
    })
    hass.states.async_set("sensor.picked_by_the_user", "12")
    hass.states.async_set(_VAC, "docked", {})

    rows = {r["role"]: r for r in manager._entity_bindings(vacuum_entity_id=_VAC)}
    row = rows["total_cleaning_count"]

    assert row["entity_id"] == "sensor.picked_by_the_user"
    assert row["overridden"] is True, (
        "the picker will render 'Automatic' for a role the user explicitly pinned"
    )
    assert row["chosen_by"] == "override", (
        "the Source column will claim 'Name match' for an entity chosen by hand "
        f"(got {row['chosen_by']!r})"
    )


def test_binding_table_does_not_credit_an_override_that_lost(hass, manager):
    """[CAP-10e] The other side of CAP-10d: a STALE override must not be credited.

    If the stored choice no longer matches what is actually bound, saying "Your
    choice" would be a plain falsehood — the user would read the row as proof
    their pick took effect while the runtime uses something else. Equality is the
    whole guard, so it gets its own test rather than riding on the one above."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {
            "vacuum": _VAC,
            "total_cleaning_count": "sensor.what_actually_won",
        },
        "_entity_overrides": {"total_cleaning_count": "sensor.long_gone"},
    })
    hass.states.async_set("sensor.what_actually_won", "12")
    hass.states.async_set(_VAC, "docked", {})

    rows = {r["role"]: r for r in manager._entity_bindings(vacuum_entity_id=_VAC)}
    row = rows["total_cleaning_count"]

    assert row["entity_id"] == "sensor.what_actually_won"
    assert row["overridden"] is False
    assert row["chosen_by"] != "override"
