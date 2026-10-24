"""Roborock adapter — brand-specific tests.

The brand-AGNOSTIC contract (schema conformance, dispatch shape, registry
validation, entity-id format) is covered by
``tests/adapters/test_adapter_contract.py`` via the ``ADAPTER_BUILDERS`` entry —
adding Roborock there runs the whole suite against it. This file covers the
Roborock-SPECIFIC wiring: model detection, brand auto-detect, and the key
grounded config values (verified against the captured vacuum.ivy states + run
trace).

The device-registry lookup is monkeypatched (a tiny fake device) so the tests
don't depend on HA registry plumbing.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    get_adapter_config,
)
from custom_components.eufy_vacuum.adapters.roborock import adapter as rb
from custom_components.eufy_vacuum.adapters.roborock import dock as rb_dock
from custom_components.eufy_vacuum.adapters.roborock import model_catalog
from custom_components.eufy_vacuum.adapters.roborock import vocabulary as rbv
from custom_components.eufy_vacuum.adapters.roborock.entities import build_entity_id


_RVAC = "vacuum.ivy"


class _FakeDevice:
    def __init__(self, manufacturer: str | None, model: str | None) -> None:
        self.manufacturer = manufacturer
        self.model = model


def _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.s6"):
    monkeypatch.setattr(
        rb, "_device_for_vacuum", lambda h, v: _FakeDevice(manufacturer, model)
    )


# --- model catalog (pure) ---------------------------------------------------


def test_profile_for_known_s6():
    p = model_catalog.profile_for_model("roborock.vacuum.s6")
    assert p["family"] == "s6"
    assert p["display_name"] == "Roborock S6"
    assert p["has_dock"] is False
    assert p["has_mop"] is True


def test_profile_for_unknown_falls_back():
    assert model_catalog.profile_for_model("roborock.vacuum.s99") is model_catalog.DEFAULT_PROFILE
    assert model_catalog.profile_for_model(None) is model_catalog.DEFAULT_PROFILE


# --- entity builder ---------------------------------------------------------


def test_build_entity_id():
    assert build_entity_id("vacuum.ivy", "_status") == "sensor.ivy_status"
    assert (
        build_entity_id("vacuum.ivy", "_charging", "binary_sensor")
        == "binary_sensor.ivy_charging"
    )


# --- brand identity is DATA, not a detector ---------------------------------
#
# The four tests that lived here exercised `is_roborock_vacuum`, which asked the device
# registry "is this vacuum a Roborock?" and which core called once per brand. That is
# `if brand:` with a function pointer — brand knowledge back inside core's control flow,
# the exact arrangement the adapter seam exists to remove. The function is gone; this
# package now DECLARES which integration provides it and core compares.
#
# The resolution rules themselves are tested in tests/adapters/test_brand_selection.py.
# What belongs here is only this package's own claim.


def test_this_package_declares_the_integration_that_provides_it():
    from custom_components.eufy_vacuum.adapters.roborock.const import UPSTREAM_PLATFORMS

    assert UPSTREAM_PLATFORMS == ("roborock",), (
        "Roborock ships in HA core under the `roborock` domain; `vacuum.ivy` reports "
        "exactly this as its entity-registry platform"
    )
    assert isinstance(UPSTREAM_PLATFORMS, tuple), (
        "declared as a tuple so an upstream rename or a second providing integration "
        "lands as DATA rather than as a code change"
    )


def test_the_detector_stays_deleted():
    """A regression pin, because re-adding it would look like a helpful convenience."""
    from custom_components.eufy_vacuum.adapters.roborock import adapter as _rb

    assert not hasattr(_rb, "is_roborock_vacuum"), (
        "is_roborock_vacuum is back. Identity is declared in const.UPSTREAM_PLATFORMS; "
        "a per-brand detector puts core in the business of judging brands again."
    )


# --- assembled config (S6 model) --------------------------------------------


@pytest.fixture
def s6_config(monkeypatch, hass):
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.s6")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    return get_adapter_config(_RVAC)


def test_identity(s6_config):
    assert s6_config["adapter_id"] == "roborock"
    assert s6_config["source"] == "code"
    assert s6_config["display_name"] == "Roborock S6"
    assert s6_config["brand"] == "Roborock"


def test_entities(s6_config):
    e = s6_config["entities"]
    assert e["task_status"] == "sensor.ivy_status"
    assert e["active_cleaning_target"] == "sensor.ivy_current_room"
    assert e["cleaning_time"] == "sensor.ivy_cleaning_time"
    assert e["battery"] == "sensor.ivy_battery"
    assert e["error_message"] == "sensor.ivy_vacuum_error"
    assert e["charging"] == "binary_sensor.ivy_charging"
    # recharge-resume completion disambiguator (forward hook).
    assert e["job_active"] == "binary_sensor.ivy_cleaning"
    # Wave 2a: active_map = the selected-map SELECT (reports the map name).
    assert e["active_map"] == "select.ivy_selected_map"


def test_the_live_pose_is_declared(s6_config):
    """THE REGRESSION PIN. Deleting this block is what broke the stall capture.

    The brand-agnostic contract suite checks that a DECLARED live_pose names a readable
    backend — but it skips a brand that declares none, which is exactly the state this bug
    was in. So the capability is pinned here, for the brand that has it: Roborock's position
    rides its in-memory parsed MapData, `async_get_map_live_pose` can read that, and every
    consumer of it (the stall capture's dot, the pose sampler's anchor) depends on this
    block existing.

    The cadence is measured, not chosen: 17 distinct anchors over ~8 minutes on Ivy
    (2026-08-09) is one new position per ~28s, and it sizes the capture's trail window.
    """
    from custom_components.eufy_vacuum.mapping.map_source_coordinator import (
        POSE_BACKEND_PARSED_MAPDATA,
    )

    live_pose = s6_config["map_state_source"]["live_pose"]

    assert live_pose["backend"] == POSE_BACKEND_PARSED_MAPDATA
    assert live_pose["pose_refresh_s"] == 30.0
    # No fork attr lists: needing none of them is why `backend` is a declaration rather
    # than core sniffing which keys happen to be present.
    assert "robot_pixel_attrs" not in live_pose


def test_discovery_service_response(s6_config):
    # Wave 2a: rooms come from the roborock.get_maps service RESPONSE (not an
    # attribute), flattened + cached by the framework. map identity = name.
    disc = s6_config["discovery"]
    assert disc["source"] == "service_response"
    assert disc["maps_service"] == {"domain": "roborock", "service": "get_maps"}
    assert disc["maps_rooms_key"] == "rooms"
    assert disc["map_name_key"] == "name"
    assert disc["room_id_key"] == "segment_id"
    assert disc["room_name_key"] == "name"
    # Named rooms are deliberate (no phantom segments) -> surface immediately.
    assert disc["new_room_confirmation_passes"] == 1


def test_dispatch(s6_config):
    d = s6_config["dispatch"]
    assert d["template"] == "roborock_segment_clean"
    assert d["service_domain"] == "vacuum"
    assert d["service_name"] == "send_command"
    # command MUST be explicit — absent defaults to Eufy's room_clean.
    assert d["command"] == "app_segment_clean"
    assert d["rooms_field"] == "segments"
    assert d["clean_passes_field"] == "repeat"
    assert d["passes_max"] == 3
    # passes is ONE whole-run scalar (repeat), not per-room -> editor notes it.
    assert d["passes_is_global"] is True
    # Wave 2b: ids renumber on re-segment -> resolve slug->live id at send.
    assert d["resolve_live_ids_by_slug"] is True


def test_per_room_live_fan(s6_config):
    # fan_speed is settable MID-RUN on the S6 -> per-room LIVE (set as current_room
    # advances), NOT a global pre-call. passes stays global; mop is unsettable.
    live = {p["field"]: p for p in s6_config["dispatch"]["per_room_live_settings"]}
    assert set(live) == {"fan_speed"}
    assert live["fan_speed"]["service"]["domain"] == "vacuum"
    assert live["fan_speed"]["service"]["service"] == "set_fan_speed"
    # No global pre-call anymore (fan moved to per-room live; mop removed).
    assert "global_pre_calls" not in s6_config["dispatch"]


def test_native_rollover_enabled(s6_config):
    # Wave 3: rollover follows the native current_room signal (filtered to job
    # targets), not Eufy's counter-plateau.
    lt = s6_config["live_transition"]
    assert lt["native_transition_source"] is True
    assert lt["enabled"] is True


def test_completion_keys_on_job_active(s6_config):
    # Wave 2b: current_room reverts to the dock room (never a sentinel), so
    # completion keys on the cleaning binary clearing, not a current_room sentinel.
    comp = s6_config["completion"]
    assert comp["task_status_value"] == "charging"
    assert comp["require_job_active_clear"] is True
    # current_room is no longer the completion secondary signal.
    assert "secondary_clear_entity" not in comp


def test_completion_charging_error(s6_config):
    assert s6_config["completion"]["task_status_value"] == "charging"
    # No low_battery_return_task_status: returning_home is emitted for both a
    # low-battery and a user/finish return, so we rely on the battery gate.
    assert "low_battery_return_task_status" not in s6_config["charging"]
    assert s6_config["charging"]["low_battery_threshold_percent"] == 20
    assert s6_config["error_tracking"]["task_status_error_value"] == "error"


def test_engines_are_noop(s6_config):
    assert s6_config["mapping"]["segmenter_engine"] == "noop_fallback"
    assert s6_config["mapping"]["segmenter_tuning"] == {}
    # MUST be explicit — an absent block falls back to eufy_counter_v1.
    assert s6_config["job_segmenter"]["engine"] == "noop_job_fallback"
    assert "tuning" not in s6_config["job_segmenter"]


def test_no_dock(s6_config):
    caps = s6_config["capabilities"]
    assert caps["supports_mop_features"] is True
    # Only per-room field is fan -> reusable profiles would be degenerate; hide.
    assert caps["supports_room_profiles"] is False
    # app_segment_clean path-optimizes -> order is advisory (run-start note).
    assert caps["honors_clean_order"] is False
    # Mops (tank) but the mop is NOT programmatically controllable on the S6
    # (SET_WATER_BOX_CUSTOM_MODE unsupported) -> no settable water control.
    assert caps["supports_water_control"] is False
    assert caps["supports_mop_wash"] is False
    assert caps["supports_mop_dry"] is False
    assert caps["supports_empty_dust"] is False
    assert caps["supports_station_water"] is False
    assert "dock_events" not in s6_config
    assert "post_job_wash_amendment" not in s6_config
    assert s6_config["vocabulary"]["hard_service_states"] == []
    assert s6_config["vocabulary"]["drying_states"] == []


def test_maintenance_components(s6_config):
    """SEVEN components. It was fourteen, and that was a parts inventory read as a card list.

    Four life-tracked robot consumables + three guide-only cleanables. Every removal below is
    Chris's ruling, not a tidy-up: cleaning_brush and strainer "should never have been gained"
    (dock parts, both inside the one washing-station trip); dustbin "only was ever in there
    because the filter is attached to it"; water_filter "not an item either"; dust_bag is
    install-and-forget; the two water tanks are parts of the tray job; main_wheel never had a
    job of its own and is still a "wipe these too" line inside the wheel card.
    """
    mc = s6_config["maintenance_components"]
    assert set(mc) == {
        "main_brush", "side_brush", "filter", "sensor",
        "mop", "omnidirectional_wheel", "cleaning_tray",
    }
    assert mc["main_brush"]["sensor_suffix"] == "main_brush_time_left"
    assert mc["main_brush"]["maintenance_only"] is False
    # `remaining_is_state` is PRUNED, not renamed — it was read by absolutely nothing.
    assert "remaining_is_state" not in mc["main_brush"]
    # Filter reset button is "air_filter", not "filter".
    assert mc["filter"]["reset_button"]["entity_suffixes"] == ["reset_air_filter_consumable"]
    # Guide-only cleanables: maintenance_only, no upstream sensor, no interval.
    for comp in ("mop", "omnidirectional_wheel", "cleaning_tray"):
        assert mc[comp]["maintenance_only"] is True, comp
        assert not mc[comp].get("sensor_suffix"), comp


# REMOVED 2026-09-12 — test_dock_consumables_declare_the_translation_key_not_the_id_suffix.
# Its subjects were `cleaning_brush` and `strainer`, the two dock components this port deleted,
# so it has nothing left to assert. THE LESSON IT CARRIED IS NOT LOST: the translation-key rung
# it guarded lives in adapters/entity_resolve.py (live:ENT-9) and is documented there, where it
# still fires for any adapter whose entity id diverges from its translation key. Deleting the
# test with its subject is right; deleting the reasoning with it would not have been.


def test_upkeep_catalog(s6_config):
    """The guide half, now KEY-routed: model -> regime -> card, and no families anywhere.

    The tier column this used to assert is DELETED rather than corrected. It was hand-assigned
    and wrong on 8 of 41 in both directions — four China-market machines shipped as `standard`
    when they carry a dock, four Q-series as `auto_empty` when the base SKU has none. Two of
    the old assertions here pinned exactly those wrong values (a38 Q7 Max as `auto_empty`), so
    this test was holding the defect in place.
    """
    cat = s6_config["upkeep_catalog"]
    assert set(cat) == {"model_names", "model_key_regimes", "key_guides"}, (
        "family routing must be gone: no model_guide_families, guide_family_names, "
        "guide_library or guide_translations"
    )
    assert cat["model_names"]["roborock.vacuum.s6"] == "S6"
    # The S6 is a charge-only cloth machine — its regime says so, in readable form.
    assert cat["model_key_regimes"]["roborock.vacuum.s6"] == "cloth|charge_only|no"
    assert len(cat["model_key_regimes"]) == 41

    # THE 8 THE OLD TIER COLUMN GOT WRONG, now measured per model. This is the walk-back.
    assert cat["model_key_regimes"]["roborock.vacuum.a29"] == "cloth|wash_only|yes"      # G10
    assert cat["model_key_regimes"]["roborock.vacuum.a46"] == "cloth|wash+empty|yes"     # G10S
    assert cat["model_key_regimes"]["roborock.vacuum.a26"] == "cloth|wash+empty|yes"     # G10S Pro
    assert cat["model_key_regimes"]["roborock.vacuum.a23"] == "cloth|auto_empty|no"      # T7S Plus
    for base_sku in ("a38", "a72", "a73", "ss07"):   # Q7 Max, Q5 Pro, Q8 Max, Q10
        assert cat["model_key_regimes"]["roborock.vacuum.%s" % base_sku].endswith(
            "|charge_only|no"
        ), "%s has no dock at base SKU — the tier column gave it the '+' variant's" % base_sku

    guide = cat["key_guides"][cat["model_key_regimes"]["roborock.vacuum.s6"]]
    for comp in ("main_brush", "side_brush", "filter", "sensor", "omnidirectional_wheel", "mop"):
        assert guide[comp]["steps"], comp
    assert "cleaning_tray" not in guide, "the S6 has no washing station"

def test_vocabulary(s6_config):
    vocab = s6_config["vocabulary"]
    # Fan chips in ascending suction order (gentle weakest -> max strongest).
    assert [o["value"] for o in vocab["fan_speed_options"]] == [
        "gentle", "quiet", "balanced", "turbo", "max"
    ]
    # water_level / clean_mode / clean_intensity options OMITTED -> pickers hidden.
    # The S6 mop is unsettable (SET_WATER_BOX_CUSTOM_MODE unsupported); mode = tank.
    assert "water_level_options" not in vocab
    assert "clean_mode_options" not in vocab
    assert "clean_intensity_options" not in vocab
    assert "segment_cleaning" in vocab["active_run_task_states"]


# --- error classification (RF-DOCK clauses 4/5) ------------------------------
#
# These pin INVARIANTS of the tables, not their contents: a table that grows is
# fine, a table that contradicts itself is not. Two of these caught real defects
# when first written -- robot_trapped was invalidating without being declared
# robot-sourced, and the 11 dock codes were transcribed into two separate lists.


def test_error_codes_reach_the_adapter_config(s6_config):
    """The sets are declared in vocabulary.py; core reads them from HERE."""
    cfg = s6_config["error_tracking"]
    assert "strainer_error" in cfg["dock_sourced_error_codes"]
    assert "wheels_jammed" in cfg["robot_sourced_error_codes"]
    assert "robot_trapped" in cfg["evidence_invalidating_error_codes"]
    assert "cannot_cross_carpet" in cfg["evidence_safe_error_codes"]


def test_invalidating_is_a_subset_of_robot_sourced():
    """A fault cannot invalidate the robot's evidence without being the robot's.

    robot_trapped was in INVALIDATING and absent from ROBOT_SOURCED, so
    error_source_for_code answered "unknown" for a fault we were confident enough
    about to subtract a run's seconds over.
    """
    assert (
        rbv.ROBOROCK_EVIDENCE_INVALIDATING_ERROR_CODES
        <= rbv.ROBOROCK_ROBOT_SOURCED_ERROR_CODES
    )


def test_safe_and_invalidating_are_disjoint():
    """The same code cannot both preserve and destroy a run's seconds."""
    assert not (
        rbv.ROBOROCK_EVIDENCE_SAFE_ERROR_CODES
        & rbv.ROBOROCK_EVIDENCE_INVALIDATING_ERROR_CODES
    )


def test_safe_is_derived_so_dock_codes_are_written_once():
    """SAFE must stay DOCK | SAFE_ROBOT rather than a hand-copy of both.

    Every dock fault is evidence-safe by definition (the robot worked through it),
    so a dock code missing from SAFE is always a transcription slip -- which is
    exactly what a second literal list invites.
    """
    assert rbv.ROBOROCK_EVIDENCE_SAFE_ERROR_CODES == (
        rbv.ROBOROCK_DOCK_SOURCED_ERROR_CODES
        | rbv.ROBOROCK_EVIDENCE_SAFE_ROBOT_CODES
    )
    assert (
        rbv.ROBOROCK_DOCK_SOURCED_ERROR_CODES
        <= rbv.ROBOROCK_EVIDENCE_SAFE_ERROR_CODES
    )


def test_a_code_is_not_both_dock_and_robot_sourced():
    assert not (
        rbv.ROBOROCK_DOCK_SOURCED_ERROR_CODES
        & rbv.ROBOROCK_ROBOT_SOURCED_ERROR_CODES
    )


def test_codes_are_lowercase_enum_strings():
    """core/_code_key lowercases string codes, so an uppercase declaration here
    would silently never match. Numeric-looking strings would resolve to ints and
    land in Eufy's code space instead of ours."""
    for name in (
        "ROBOROCK_DOCK_SOURCED_ERROR_CODES",
        "ROBOROCK_ROBOT_SOURCED_ERROR_CODES",
        "ROBOROCK_EVIDENCE_INVALIDATING_ERROR_CODES",
        "ROBOROCK_EVIDENCE_SAFE_ERROR_CODES",
    ):
        for code in getattr(rbv, name):
            assert isinstance(code, str), f"{name}: {code!r}"
            assert code == code.lower(), f"{name}: {code!r}"
            assert not code.strip().lstrip("-").isdigit(), f"{name}: {code!r}"


# --- fault labels (CARD-3) ---------------------------------------------------


def test_error_label_keys_reach_the_adapter_config(s6_config):
    cfg = s6_config["error_tracking"]["error_label_keys"]
    assert cfg["bumper_stuck"] == "fault.roborock.bumper_stuck"
    # Slug written from MEANING, not from the vendor's token.
    assert cfg["visual_sensor"] == "fault.roborock.camera_error"
    assert cfg["check_clean_carouse"] == "fault.roborock.check_cleaning_carousel"


def test_every_label_key_is_ours_and_brand_scoped():
    """faultLabel() in src/state/faults.js splits fault.<brand>.<slug> and refuses
    anything else. A key in another shape silently renders the raw code instead."""
    for enum, key in rbv.ROBOROCK_ERROR_LABEL_KEYS.items():
        assert key.startswith("fault.roborock."), f"{enum} -> {key}"
        assert key == key.lower(), f"{enum} -> {key}"
        assert " " not in key, f"{enum} -> {key}"


def test_label_keys_are_lowercase_enum_strings():
    """core/_code_key lowercases string codes; an uppercase key never matches."""
    for enum in rbv.ROBOROCK_ERROR_LABEL_KEYS:
        assert isinstance(enum, str) and enum == enum.lower(), enum


def test_duplicate_meanings_share_one_key():
    """mopping_roller_1 and _2 are the same message. Same precedent as Eufy's
    106/114/3012 all being the robot's water pump -- one key, one translation."""
    keys = rbv.ROBOROCK_ERROR_LABEL_KEYS
    assert keys["mopping_roller_1"] == keys["mopping_roller_2"]


def test_contradictory_states_stay_unmapped():
    """HA's own strings for these three contradict their enum names -- a WATER
    FILTER message on a BRUSH enum, and so on. Unmapped falls through to the raw
    enum, which is honest; naming the wrong part sends someone to strip down
    hardware that is fine.

    This test exists so that 'filling the gap' has to confront the reason first.
    If the meanings ever get established, map them AND delete this test.
    """
    for enum in ("clear_brush_exception", "clear_brush_exception_2", "light_touch"):
        assert enum not in rbv.ROBOROCK_ERROR_LABEL_KEYS, enum


def test_every_label_key_has_an_english_string():
    """A key with no string renders the dotted key at the user. These are reached
    through a TEMPLATE (faultLabel builds `fault.${brand}.${slug}`), so check-i18n
    cannot see them and this is the only gate."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[3]
    en = (root / "src" / "i18n" / "en.js").read_text(encoding="utf-8")
    defined = set(re.findall(r'"(fault\.roborock\.[a-z0-9_]+)":', en))

    declared = set(rbv.ROBOROCK_ERROR_LABEL_KEYS.values())
    assert not (declared - defined), f"declared with no English string: {sorted(declared - defined)}"
    assert not (defined - declared), f"English string nothing maps to: {sorted(defined - declared)}"


def test_sentinel_none_is_never_classified():
    """`none` is the idle value, not a fault. Classifying it would attribute
    error seconds to every healthy run."""
    every = (
        rbv.ROBOROCK_DOCK_SOURCED_ERROR_CODES
        | rbv.ROBOROCK_ROBOT_SOURCED_ERROR_CODES
        | rbv.ROBOROCK_EVIDENCE_SAFE_ERROR_CODES
        | rbv.ROBOROCK_EVIDENCE_INVALIDATING_ERROR_CODES
    )
    assert not (every & rbv.NOT_ERROR_SENTINELS)


def test_cancel_detection_states(s6_config):
    # Without this, _detect_cancel_likely_run defaults to the Eufy "returning"
    # string and never fires for Roborock (which returns via returning_home),
    # silently letting a cancelled run pollute learning estimates.
    cds = s6_config["vocabulary"]["cancel_detection_states"]
    assert cds["returning"] == "returning_home"
    assert cds["paused"] == "paused"
    # active is a list covering both whole-clean and per-room (segment) modes.
    assert "cleaning" in cds["active"]
    assert "segment_cleaning" in cds["active"]


# ===========================================================================
# Settable-mop models (S7/S8): "not all Roborocks are the S6". has_mop (tank
# present) and mop_settable (mop mode/water is programmable) are DISTINCT — the S6
# has the former, not the latter, and baking that into the brand would deny per-group
# mop to capable models. These are UNVERIFIED on-device (no S7/S8 on hand); the
# dispatch degrades safely (a rejected select_option is caught + logged).
# ===========================================================================


def test_profile_mop_settable_distinct_from_has_mop():
    s6 = model_catalog.profile_for_model("roborock.vacuum.s6")
    s7 = model_catalog.profile_for_model("roborock.vacuum.a15")
    # S6: mops via a tank but the mop is UNSETTABLE.
    assert s6["has_mop"] is True and s6["mop_settable"] is False
    # S7: mop is settable.
    assert s7["family"] == "s7" and s7["has_mop"] is True and s7["mop_settable"] is True
    # Unknown Roborock -> best-effort settable (assume capable, degrade gracefully).
    assert model_catalog.DEFAULT_PROFILE["mop_settable"] is True


@pytest.fixture
def s7_config(monkeypatch, hass):
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a15")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    return get_adapter_config(_RVAC)


def test_s7_exposes_water_control(s7_config):
    assert s7_config["display_name"] == "Roborock S7"
    # Settable mop -> water control on + the water picker appears (canonical values).
    assert s7_config["capabilities"]["supports_water_control"] is True
    # A settable model has fan + mode + water per room, so a reusable room profile is
    # meaningful (not a degenerate named fan speed) -> the profiles section appears.
    # The S6 (fan-only) keeps supports_room_profiles False (see test_no_dock).
    assert s7_config["capabilities"]["supports_room_profiles"] is True
    vocab = s7_config["vocabulary"]
    assert [o["value"] for o in vocab["water_level_options"]] == ["off", "low", "medium", "high"]
    # clean_mode is the logical mop switch (vacuum/mop/vacuum_mop) — it gates water +
    # drives the mop pre-call; it never reaches the app_segment_clean wire.
    assert [o["value"] for o in vocab["clean_mode_options"]] == ["vacuum", "mop", "vacuum_mop"]
    # No clean_intensity axis on Roborock.
    assert "clean_intensity_options" not in vocab


def test_s7_mop_global_pre_call(s7_config):
    # Mop intensity is a device-GLOBAL select, set pre-dispatch (per phase). It ranks
    # each group's water_level max-wins and pushes it to the mop_intensity select via
    # select.select_option — canonical off/low/medium/high map 1:1 (no value_map).
    pre = s7_config["dispatch"]["global_pre_calls"]
    assert len(pre) == 1
    entry = pre[0]
    assert entry["field"] == "water_level"
    assert entry["rank"] == ["off", "low", "medium", "high"]
    assert entry["service"]["domain"] == "select"
    assert entry["service"]["service"] == "select_option"
    assert entry["service"]["value_key"] == "option"
    # BY ROLE, not a frozen id (issue #51). These blocks are built BEFORE
    # resolve_declared_entities runs, so an id baked in here is the PRE-RESCUE guess
    # and stays wrong forever on an install whose entity ids are localized: the real
    # select is `select.<vid>_wisch_intensitat`, the push named an entity that does
    # not exist, and HA logs a warning rather than raising — so it failed silently and
    # the robot mopped a room the user set to vacuum-only.
    assert entry["service"]["target_role"] == "mop_intensity"
    assert "target_entity_id" not in entry["service"]
    # ...and the role is DECLARED, so the rescue can reach it and the System screen
    # can show it. A role named by a pre-call but absent from `entities` would
    # resolve to nothing at dispatch time.
    assert s7_config["entities"]["mop_intensity"] == "select.ivy_mop_intensity"
    # No value_map: canonical values already match the select's wire options.
    assert "value_map" not in entry


# --- dock identification (dock.py) ------------------------------------------
#
# The vendor TRUTH TABLE itself is not re-asserted here. It was measured by driving all
# 27 dock types through the real HA integration against python-roborock's own simulator
# (`.claude/notes/harness/roborock-dock-sweep/`), and re-stating its outputs from a
# hand-written fake would only prove the fake agrees with whoever wrote it. What IS
# tested here is our side of the seam: reading the registry value, and — the part that
# actually protects users — degrading safely when the vendor library is not importable.


class _FakeDockDevice:
    def __init__(self, model_id):
        self.model_id = model_id


def test_dock_type_value_reads_the_integer():
    assert rb_dock.dock_type_value(_FakeDockDevice("7")) == 7
    assert rb_dock.dock_type_value(_FakeDockDevice(" 17 ")) == 17
    assert rb_dock.dock_type_value(_FakeDockDevice("0")) == 0


def test_dock_type_value_treats_unidentifiable_as_no_dock():
    """`"Unknown"` is what the coordinator writes when status has no dock_type at all.

    Chris's S6 reports exactly this — NOT `"0"` — which is why a `!= "0"` test was one of
    the three hypotheses that died on real hardware.
    """
    assert rb_dock.dock_type_value(None) is None
    assert rb_dock.dock_type_value(_FakeDockDevice("Unknown")) is None
    assert rb_dock.dock_type_value(_FakeDockDevice(None)) is None
    assert rb_dock.dock_type_value(_FakeDockDevice("o4_dock")) is None
    assert rb_dock.dock_type_value(_FakeDockDevice("")) is None


def test_dock_profile_reports_no_dock_without_needing_the_vendor_library(monkeypatch):
    """The no-dock answers resolve before the import, so they hold on every install."""
    monkeypatch.setattr(rb_dock, "find_dock_device", lambda h, v: None)
    prof = rb_dock.dock_profile(None, _RVAC)
    assert prof == {
        "has_dock": False, "dock_type": None,
        "dock_type_name": None, "reason": "no_dock_device",
    }

    monkeypatch.setattr(
        rb_dock, "find_dock_device", lambda h, v: _FakeDockDevice("Unknown")
    )
    prof = rb_dock.dock_profile(None, _RVAC)
    assert prof["has_dock"] is False
    assert prof["reason"] == "model_id_unknown"


async def test_dock_profile_returns_undetermined_when_vendor_library_is_absent(monkeypatch, hass):
    """A real dock code with no python-roborock must yield None — NOT a guess.

    None means "could not determine", and the adapter falls back to the model catalog's
    conservative default. This is the branch the repo suite actually runs: our manifest
    deliberately does not require python-roborock (the upstream Roborock integration
    pins it), so it is absent from the test image. If someone later vendors a copy of
    `_NO_DOCK_TYPES` to "fix" this, that copy goes stale silently the next time the
    vendor edits the set — which is the whole reason dock.py refuses to hold one.
    """
    pytest.importorskip  # noqa: B018 — documents the deliberate NON-use of importorskip
    monkeypatch.setattr(
        rb_dock, "find_dock_device", lambda h, v: _FakeDockDevice("7")
    )
    await hass.async_add_executor_job(rb_dock.load_dock_library)
    try:
        import roborock  # noqa: F401
    except ImportError:
        assert rb_dock.dock_profile(None, _RVAC) is None
    else:
        prof = rb_dock.dock_profile(None, _RVAC)
        assert prof is not None and prof["has_dock"] is True
        assert prof["dock_type"] == 7 and prof["dock_type_name"] == "o4_dock"


def _capture_hints(monkeypatch, hass, dock_result):
    """Register the adapter and return the capability_hints it handed the detector.

    The hints are not stored on the config (only `_entity_candidates` is), so the seam
    itself is the observable: intercept `detect_capabilities` and keep what it was
    called with. That tests the wiring this change actually touched, rather than
    re-deriving the detector's output.
    """
    seen: dict = {}

    def _spy(hass_, **kwargs):
        seen.update(kwargs.get("capability_hints") or {})
        return {}

    _patch_device(monkeypatch)
    monkeypatch.setattr(rb, "dock_profile", lambda h, v: dock_result)
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.core.capabilities.detect_capabilities", _spy
    )
    clear_registry()
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    assert seen, (
        "capability_hints were never captured — the spy did not intercept "
        "detect_capabilities, so every assertion downstream of this would pass "
        "vacuously on an empty dict"
    )
    return seen


def test_adapter_keeps_dock_controls_off_when_dock_is_undetermined(monkeypatch, hass):
    """The safety property: undetermined must never OFFER a control.

    Offering a mop wash on a dock that cannot wash is the worse failure — the same
    reasoning model_catalog gives for defaulting has_path_control to False.
    """
    hints = _capture_hints(monkeypatch, hass, None)
    assert hints["supports_mop_wash"] is False
    assert hints["supports_mop_dry"] is False
    assert hints["supports_empty_dust"] is False


def test_adapter_asks_the_vendor_a_separate_question_per_control(monkeypatch, hass):
    """wash / dry / collect are distinct vendor flags and must not ride one has_dock.

    An o1/oc auto-empty dock collects but cannot wash; an o2 washes but cannot collect.
    Keying all three off has_dock would offer a mop wash on a dock with no water — so a
    single blanket flag is not a simplification, it is a wrong answer on two dock types.
    """
    hints = _capture_hints(monkeypatch, hass, {
        "has_dock": True, "dock_type": 1, "dock_type_name": "o1_dock",
        "is_washable": False, "is_collectable": True, "is_dryable": False,
        "reason": None,
    })
    assert hints["supports_empty_dust"] is True
    assert hints["supports_mop_wash"] is False
    assert hints["supports_mop_dry"] is False


def test_adapter_enables_all_three_on_a_full_station(monkeypatch, hass):
    """The mirror of the test above — without it, "always False" would also pass."""
    hints = _capture_hints(monkeypatch, hass, {
        "has_dock": True, "dock_type": 7, "dock_type_name": "o4_dock",
        "is_washable": True, "is_collectable": True, "is_dryable": True,
        "reason": None,
    })
    assert hints["supports_mop_wash"] is True
    assert hints["supports_mop_dry"] is True
    assert hints["supports_empty_dust"] is True


# ---------------------------------------------------------------------------
# D18 - a model catalog entry declaring supports_zone_clean False is BELIEVED
# ---------------------------------------------------------------------------


def test_d18_a_catalog_entry_can_actually_refuse_zone_clean(monkeypatch, hass):
    """[D18] RED BEFORE THE FIX — the declaration had no wire.

    The config block reads `caps.get("supports_zone_clean", True)` under a comment
    saying a model catalog entry can declare it False "and be believed". Nothing passed
    it as a capability hint, and `capabilities._hint_wins` honours a declared False only
    when the key is PRESENT in the hints — so the entry resolved to the derived default
    True and was silently ignored. Open at the core end (dispatch DOES refuse on False)
    and unconnected at this one, which is the shape that reads as covered.

    Declared through a real catalog profile rather than by injecting a hint, because the
    hint is the half that already worked. What was missing is the path FROM the catalog,
    and that is what this drives.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.s6")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )

    zoneless = dict(model_catalog.profile_for_model("roborock.vacuum.s6"))
    zoneless["supports_zone_clean"] = False
    monkeypatch.setattr(model_catalog, "profile_for_model", lambda _m: zoneless)
    monkeypatch.setattr(rb, "profile_for_model", lambda _m: zoneless)

    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    config = get_adapter_config(_RVAC)

    assert config["capabilities"]["supports_zone_clean"] is False, (
        "a model catalog entry declared zone cleaning unsupported and the adapter "
        "ignored it — dispatch/manager.py gates on exactly this key, so the refusal "
        "never fires"
    )


def test_d18_the_default_is_still_supported(monkeypatch, hass):
    """[D18] RED IF THE HINT IS HARDCODED FALSE, or sent as False by accident.

    No catalogued model declares the key, and every one of them zone-cleans. A wire that
    silently disabled zone clean for the whole brand would be a worse defect than the
    one being repaired, and it would look identical from the catalog.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.s6")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)

    assert get_adapter_config(_RVAC)["capabilities"]["supports_zone_clean"] is True
    assert "supports_zone_clean" not in model_catalog.profile_for_model(
        "roborock.vacuum.s6"
    ), "a catalogued model started declaring this — confirm it from device evidence"


# --- the mop ROUTE axis (issue #66) ------------------------------------------


def _route_pre_call(cfg):
    """The path_type entry in dispatch.global_pre_calls, or None."""
    for entry in (cfg.get("dispatch") or {}).get("global_pre_calls") or []:
        if entry.get("field") == "path_type":
            return entry
    return None


def test_rt_1_the_route_options_are_the_devices_own_vocabulary():
    """[RT-1] path_type is declared with values a Roborock actually has.

    It was wide/narrow, and no Roborock has ever had such a control. That mattered
    beyond being wrong: `room_manager` defaults the field, so every Roborock room was
    persisted carrying `path_type: "wide"` — measured on a reporter's install, all four
    rooms — on a picker that never rendered. Replacing the list is what lets
    rooms/vocabulary_migration RESET it, because it can only judge a value against a
    declared list.

    ABLATION: put wide/narrow back and this goes red.
    """
    values = [o["value"] for o in rbv.PATH_TYPE_OPTIONS]
    assert values == ["standard", "deep", "deep_plus"], values
    assert "wide" not in values and "narrow" not in values, (
        "wide/narrow are back; a stored 'wide' becomes judgeable-as-valid again and the "
        "migration will stop resetting it"
    )


def test_rt_2_no_route_axis_without_the_select(s6_config):
    """[RT-2] THE NO-REGRESSION GUARD: catalogue False and NO select state at all.

    model_catalog says `has_path_control: False` for the S6 and the comment records it as
    owner-confirmed on hardware. A usable select may only ADD, so a box with no select
    state must be byte-identical to before: capability off, and no route pre-call.

    ⚠ THE SHAPE HERE IS NOT THE REAL S6'S, AND THIS DOCSTRING CLAIMED IT WAS — it said
    "the S6 has no mop-route select". It has one: registered by the roborock platform,
    not disabled, permanently `unavailable` (measured on the live box 2026-10-18). This
    fixture sets no select state, so it exercises the `_route_state is None` arm. The
    real S6's arm — present, unavailable — is [RT-5], which does patch the s6 model and
    does publish the entity. Both arms are needed; only RT-5 is named for the hardware.
    """
    assert s6_config["capabilities"]["supports_path_control"] is False
    assert _route_pre_call(s6_config) is None


def test_rt_3_the_select_turns_the_axis_on_even_on_an_uncatalogued_model(monkeypatch, hass):
    """[RT-3] THE RED INPUT, from the report: "Vacuum Agent does not show any setting for
    the mop route or mop mode" — an S7, which is not in the catalogue.

    An uncatalogued model falls to DEFAULT_PROFILE, which declares has_path_control False,
    so the catalogue alone can never turn this on for the models that actually have it.
    The device publishing `select.<obj>_mop_mode` IS the capability.

    ABLATION: drop the entity-presence OR from `_route_axis` and this goes red — the model
    is uncatalogued, so the profile contributes False and nothing else would raise it.

    ⚠ THIS TEST CONFLATED TWO THINGS and ISSUE #71 separated them. It asserted the
    CAPABILITY (the device publishes the select, so the axis exists) and, in the same
    breath, that the PUSH is declared — and its name promises the user symptom, "does not
    show any setting for the mop route", which neither assertion could ever reach. The
    picker reads `clean_intensity_options`; Roborock declares `path_type_options`; the
    symptom survived #66 untouched while this test went green.

    The capability half is unchanged and still asserted here. The push half moved to
    [RT-10]/[RT-11], which gate it on the axis being USER-VISIBLE — because until it is,
    pushing it overwrites the route the owner set in the vendor app with a default they
    were never shown. The pre-call's SHAPE is still pinned below, under the same gate the
    product now uses, so none of #66's grounded detail is lost.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a15")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    hass.states.async_set(build_entity_id(_RVAC, "_mop_mode", "select"), "standard")
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    assert cfg["capabilities"]["supports_path_control"] is True, (
        "the device publishes the select, so the axis exists — #66's actual finding"
    )

    # The pre-call's SHAPE, under the user-visibility gate [RT-10] introduced. Asserting
    # it unconditionally is what this test used to do, and what #71 showed to be wrong.
    monkeypatch.setattr(
        rb.vocabulary, "CLEAN_INTENSITY_OPTIONS",
        [{"value": "standard", "label": "Standard"}], raising=False,
    )
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    entry = _route_pre_call(cfg)
    assert entry is not None, "the route pre-call was not declared"
    # BY ROLE, not a frozen id: both reporters run non-English installs where the derived
    # id does not exist, so a literal here would name an entity that is not there.
    assert entry["service"]["target_role"] == "mop_mode"
    assert entry["rank"] == ["standard", "deep", "deep_plus"]
    # No safest-water policy: over-scrubbing costs time, not damage, so the abort path
    # water needs has no counterpart here.
    assert "mixed_mode_water_policy" not in entry


def test_rt_4_the_route_select_is_declared_so_the_rescue_can_reach_it(monkeypatch, hass):
    """[RT-4] The select must be a DECLARED entity, not only a dispatch literal.

    This is issue #51's lesson applied to a second role: a target that exists only inside
    dispatch.global_pre_calls is somewhere `resolve_declared_entities` never looks, so on a
    localized install (`select.s7_modo_mopa`) the push names an entity that does not exist
    and nothing rescues it. Declared, it resolves on the upstream translation_key and
    becomes user-overridable.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a15")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    hass.states.async_set(build_entity_id(_RVAC, "_mop_mode", "select"), "standard")
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    assert cfg["entities"]["mop_mode"] == "select.ivy_mop_mode"


def test_rt_5_a_present_but_unavailable_select_does_not_turn_the_axis_on(monkeypatch, hass):
    """[RT-5] THE RED INPUT, falsified on the maintainer's own S6 before it shipped.

    The first version of this gate was `hass.states.get(...) is not None`. The S6
    PUBLISHES `select.<obj>_mop_mode` and that entity sits at `unavailable` forever,
    because its mop is observe-only — SET_MOP_MODE returns RoborockUnsupportedFeature.
    Mere presence would therefore have flipped supports_path_control True on the ONE
    model whose catalogue entry says False and records it as owner-confirmed on hardware,
    offering a Cleaning Path picker the device can only reject.

    Presence is not evidence; a usable value is. `is_blank_state` covers unavailable AND
    unknown, which is the stricter reading on purpose.

    ABLATION: go back to `is not None` and this goes red while RT-3 (a select carrying a
    real value) stays green — the asymmetry that let it through.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.s6")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    # Present, and useless — exactly what the S6 does.
    hass.states.async_set(build_entity_id(_RVAC, "_mop_mode", "select"), "unavailable")
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    assert cfg["capabilities"]["supports_path_control"] is False, (
        "an unavailable select turned the route axis on — the S6 is now offered a picker "
        "its firmware rejects"
    )
    assert _route_pre_call(cfg) is None, "a route pre-call was declared for a dead select"


def test_rt_6_an_unknown_select_is_also_not_evidence(monkeypatch, hass):
    """[RT-6] The sibling case, so RT-5 cannot be satisfied by special-casing one word.

    `unknown` means the entity exists but has never reported. That is not a capability
    either, and treating it as one would make the picker appear and disappear with the
    robot's sleep cycle. It resolves on the next refresh once a real value arrives.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a15")
    hass.states.async_set(
        _RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    hass.states.async_set(build_entity_id(_RVAC, "_mop_mode", "select"), "unknown")
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    assert get_adapter_config(_RVAC)["capabilities"]["supports_path_control"] is False


def test_rt_7_every_builtin_profile_writes_a_route_value_the_picker_offers():
    """[RT-7] The shoulder RT-1 leaves open: the OPTION LIST was corrected, the profiles
    that WRITE into it were not.

    `PATH_TYPE_OPTIONS` became standard/deep/deep_plus for issue #66, but all five
    built-in profiles kept the old wide/narrow literals. A user applying "Vacuum Only
    Quick" therefore stored `path_type: "wide"` -- out of vocabulary the moment it was
    written -- and the route picker this release makes visible rendered with nothing
    selected. It also quietly undid the vocabulary reset, which can only judge a value
    against the declared list: the reset cleared the stale value, then the next profile
    application put it straight back.

    RT-1 could not catch this. It asserts the list is right and says nothing about who
    writes into it, which is why the two drifted apart in the first place.

    ABLATION: set any profile's path_type back to "wide" and this goes red.
    """
    offered = {o["value"] for o in rbv.PATH_TYPE_OPTIONS}

    writers = {name: prof.get("path_type") for name, prof in rbv.ROOM_PROFILES.items()}
    writers["CUSTOM_ROOM_PROFILE"] = rbv.CUSTOM_ROOM_PROFILE.get("path_type")

    # Every profile DECLARES one -- an absent key would silently dodge the check below.
    missing = [n for n, v in writers.items() if v is None]
    assert not missing, f"profiles with no path_type at all: {missing}"

    stale = {n: v for n, v in writers.items() if v not in offered}
    assert not stale, (
        f"these profiles write a route value the picker does not offer: {stale}. "
        f"Offered: {sorted(offered)}. A stored value outside the declared list renders "
        f"as nothing-selected and defeats the vocabulary reset."
    )


# --- mop_settable: the guess, narrowed (issue #67) ---------------------------


def _water_pre_call(cfg):
    """The safest-water global pre-call, or None when the adapter declared none."""
    for entry in (cfg.get("dispatch") or {}).get("global_pre_calls") or []:
        if entry.get("field") == "water_level":
            return entry
    return None


def _register_unknown(monkeypatch, hass, model="roborock.vacuum.zz99"):
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model=model)
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    return get_adapter_config(_RVAC)


def test_ms1_uncatalogued_mopless_declares_no_water_pre_call(monkeypatch, hass):
    """[MS-1] THE RED INPUT, from issue #67, reported on a plain Roborock Q5.

    An uncatalogued model takes DEFAULT_PROFILE's optimistic `mop_settable: True`. The
    catalogue justified that by saying a wrong guess costs "a rejected call that is
    caught and logged" -- true only when the select EXISTS. With no select at all the
    safest-water pre-call aborts the whole dispatch on a missing target (#51), so every
    clean failed with "global pre-call target 'select.<obj>_mop_intensity' does not
    exist", including an all-vacuum batch on a machine with no mop.

    ABLATION: drop the `_mop_control_exists` term and this goes red.
    """
    cfg = _register_unknown(monkeypatch, hass)

    assert _water_pre_call(cfg) is None, (
        "a device with no mop select has nothing to make safe; declaring the pre-call "
        "can only ever abort the dispatch"
    )
    assert cfg["capabilities"]["supports_water_control"] is False


def test_ms2_boot_window_keeps_the_guess_so_51_still_aborts(monkeypatch, hass):
    """[MS-2] THE MIDDLE STATE, and the branch that must NOT be collapsed.

    Registry-but-no-state means the entity exists and has not materialised yet -- a boot
    window on a device that really does mop. Treating that as "mopless" would drop the
    safe-water push and wet-mop dry rooms, which is the exact damage #51's abort exists
    to prevent. Absence of a STATE is not absence of a MOP.
    """
    from homeassistant.helpers import entity_registry as er

    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.zz98")
    reg = er.async_get(hass)
    # THE WATER BOX WAS MISSING FROM THIS FIXTURE and the signal swap exposed it. A real
    # mop device publishes `binary_sensor.<obj>_water_box_attached` — upstream gates it
    # on `device_features.is_support_water_mode`. MEASURED on a live Roborock: it is
    # there (reading `unavailable`) alongside `select.ivy_mop_intensity`. So this fixture
    # was describing a shape no mop device produces, not a boot window.
    reg.async_get_or_create(
        "binary_sensor", "roborock", "zz98_water_box",
        suggested_object_id="ivy_water_box_attached",
    )
    entry = reg.async_get_or_create(
        "select", "roborock", "zz98_mop_intensity", suggested_object_id="ivy_mop_intensity"
    )
    assert entry.entity_id == "select.ivy_mop_intensity", entry.entity_id
    assert hass.states.get("select.ivy_mop_intensity") is None, "no STATE, by design"

    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    assert _water_pre_call(cfg) is not None, (
        "registry-only is a boot window on a real mop device; the guess must stand so "
        "the missing-target abort still fires rather than silently skipping safe water"
    )


def test_ms3_uncatalogued_with_a_live_select_is_unchanged(monkeypatch, hass):
    """[MS-3] The no-regression guard: a mop select present in the state machine leaves
    the optimistic default exactly as it was, so every uncatalogued mop model that works
    today is byte-identical."""
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.zz97")
    # The water box is what makes this an uncatalogued MOP model rather than an
    # uncatalogued mopless one — see [MS-11]. Measured on a live Roborock, which carries
    # it reading `unavailable`; the state value is irrelevant here, its existence is the
    # `is_support_water_mode` claim.
    hass.states.async_set("binary_sensor.ivy_water_box_attached", "unavailable")
    hass.states.async_set(
        "select.ivy_mop_intensity", "off", {"options": ["off", "low", "medium", "high"]}
    )
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    pre = _water_pre_call(cfg)
    assert pre is not None and pre["mixed_mode_water_policy"] == "safest"
    assert cfg["capabilities"]["supports_water_control"] is True


def test_ms4_a_catalogued_mop_model_is_never_narrowed(monkeypatch, hass):
    """[MS-4] NARROW THE GUESS, NEVER A MEASUREMENT -- the dangerous direction.

    The S7 is catalogued `mop_settable: True` on evidence. If its select is missing we
    must keep declaring the pre-call so #51 aborts: on a device that genuinely mops,
    "entity absent" is a fault to refuse on, not permission to skip safe water. Only
    DEFAULT_PROFILE's guess may be narrowed, which is why the adapter identity-tests the
    profile rather than reading a flag any future catalogue row could reuse.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a15")
    assert hass.states.get("select.ivy_mop_intensity") is None
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    assert model_catalog.profile_for_model("roborock.vacuum.a15") is not model_catalog.DEFAULT_PROFILE
    assert _water_pre_call(cfg) is not None, (
        "a CATALOGUED mop model was narrowed by entity absence — that converts #51's "
        "safe abort into a silent skip, and wet-mops dry rooms"
    )


def test_ms5_uncatalogued_with_no_mop_signal_at_all_reports_no_mop(monkeypatch, hass):
    """[MS-5] The other optimistic guess. With neither the water tank nor the intensity
    select, an uncatalogued model claimed a mop it does not have. Nothing aborted on it
    — unlike mop_settable — but it reached the vacuum-list snapshot and diagnostics, and
    a self-check that describes an install confidently and wrongly has cost this project
    a release before.

    ABLATION: drop the `_any_mop_signal` term and this goes red.
    """
    cfg = _register_unknown(monkeypatch, hass, model="roborock.vacuum.zz96")
    assert cfg["capabilities"]["supports_mop_features"] is False


def test_ms6_a_mop_it_cannot_command_is_still_a_mop(monkeypatch, hass):
    """[MS-6] THE DISTINCTION THAT MUST NOT COLLAPSE, and the reason [MS-5] keys on two
    signals rather than one.

    `has_mop` and `mop_settable` are deliberately separate: the S6 carries a mop and
    rejects every command to it. So a device advertising the water tank but no intensity
    select is mop-HAVING and mop-UNSETTABLE, and narrowing `has_mop` on the absence of
    the CONTROL would erase a real capability. Only the absence of BOTH means no mop.

    ABLATION: key `has_mop` on `_mop_control_exists` alone and this goes red while
    [MS-5] stays green — which is exactly how the two would have been conflated.
    """
    from homeassistant.helpers import entity_registry as er

    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.zz95")
    hass.states.async_set("binary_sensor.ivy_water_box_attached", "on")
    assert hass.states.get("select.ivy_mop_intensity") is None, "no CONTROL, by design"
    assert er.async_get(hass).async_get("select.ivy_mop_intensity") is None

    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    assert cfg["capabilities"]["supports_mop_features"] is True, (
        "a water tank with no intensity select is the S6's own shape: it HAS a mop. "
        "Narrowing has_mop on the control signal erases that."
    )
    assert _water_pre_call(cfg) is not None, (
        "...AND THIS LINE USED TO ASSERT THE OPPOSITE. It read: it cannot be COMMANDED, "
        "so the pre-call must stay away. That is what sends a mop-HAVING device into a "
        "mixed run with no safe-water push — whatever the vendor app last set stays, and "
        "the vacuum-only rooms get wet-mopped, silently. The #67 narrowing bought a loud "
        "failure on mopless hardware by paying in a quiet one here. Only 'no mop module' "
        "is grounds to narrow now; an unreachable control on a mop device falls through "
        "to #51's abort, which is what that abort is for"
    )


def test_ms7_no_profile_declares_the_dead_segments_key(monkeypatch, hass):
    """[MS-7] `supports_segments` was declared True on every profile of two brands and
    read by nobody: core computes its own (`supports_segments = supports_rooms`) and the
    profile key was never consulted, never forwarded as a hint. A value that looks
    authoritative and is inert is worse than silence, because the next reader believes
    it. Removed from both catalogues; this stops it drifting back.

    The CORE capability is untouched and still reported — that is the one callers use.
    """
    from custom_components.eufy_vacuum.adapters.dreame import (
        model_catalog as dreame_catalog,
    )

    for name, catalog in (("roborock", model_catalog), ("dreame", dreame_catalog)):
        profiles = dict(getattr(catalog, "MODEL_PROFILES", {}))
        profiles["DEFAULT_PROFILE"] = catalog.DEFAULT_PROFILE
        offenders = [n for n, p in profiles.items() if "supports_segments" in p]
        assert not offenders, (
            f"{name}: {offenders} declare supports_segments, which nothing reads — "
            "wire it to a consumer or leave it out; do not re-add a dead authority"
        )


def test_rd1_find_dock_device_resolves_by_identifier_on_a_real_registry(hass):
    """[RD-1] ISSUE #69 — the lookup itself, against a REAL device registry.

    `find_dock_device` had no test. Every existing dock test stubs it out and asserts
    on what `dock_profile` does with the result, so the registry walk the deprecation
    warning pointed at was never executed by the suite — which is also why replacing
    it broke nothing and proved nothing.

    This builds the shape the upstream integration actually creates: one config entry
    holding TWO devices, the robot `(roborock, duid)` and its dock `(roborock,
    duid_dock)`, confirmed against `roborock/coordinator.py::dock_device_info` at
    2026.10.1.

    ABLATION: point the lookup at the robot's own identifier instead of the suffixed
    one and this goes red.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.roborock import dock as rb_dock

    entry = MockConfigEntry(domain="roborock", entry_id="rd1_entry")
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    robot = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd1_duid")},
    )
    dock = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("roborock", "rd1_duid_dock")},
        model_id="7",
    )
    vac = er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "rd1_uid",
        suggested_object_id="rd1", device_id=robot.id, config_entry=entry,
    )

    found = rb_dock.find_dock_device(hass, vac.entity_id)
    assert found is not None, "the dock device is in the registry and must be found"
    assert found.id == dock.id
    assert found.id != robot.id, "the ROBOT is not the dock"


def test_rd2_a_second_roborocks_dock_is_never_returned(hass):
    """[RD-2] ISSUE #69 — the scoping claim, now carried by the identifier alone.

    The old walk scoped the search to the vacuum's own config entries and the docstring
    credited THAT for keeping a second robot's dock out. It was never the load-bearing
    part: the duid is the robot's own id, so the suffixed identifier already excludes
    every other dock. This pins the claim directly rather than trusting the mechanism
    that used to be given credit for it — and it holds with both robots in the SAME
    entry, which the old scoping could not have managed.

    ABLATION: drop the duid from the identifier (search for a bare `_dock`) and this
    goes red.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.roborock import dock as rb_dock

    entry = MockConfigEntry(domain="roborock", entry_id="rd2_entry")
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    mine = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd2_mine")},
    )
    my_dock = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd2_mine_dock")},
    )
    theirs_dock = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd2_theirs_dock")},
    )
    vac = er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "rd2_uid",
        suggested_object_id="rd2", device_id=mine.id, config_entry=entry,
    )

    found = rb_dock.find_dock_device(hass, vac.entity_id)
    assert found is not None and found.id == my_dock.id
    assert found.id != theirs_dock.id, "the other robot's dock must never be returned"


def test_rd3_a_vacuum_with_no_dock_device_resolves_to_none(hass):
    """[RD-3] The no-dock answer must come from the registry, not from an exception.

    `dock_profile` reads `None` as "no dock device" and settles on the catalog default.
    A lookup that raised would be caught nowhere — `find_dock_device` has no try/except
    — so the dockless case has to be a clean miss.

    ABLATION: make the lookup return the robot when no dock exists and this goes red.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.roborock import dock as rb_dock

    entry = MockConfigEntry(domain="roborock", entry_id="rd3_entry")
    entry.add_to_hass(hass)
    robot = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd3_duid")},
    )
    vac = er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "rd3_uid",
        suggested_object_id="rd3", device_id=robot.id, config_entry=entry,
    )

    assert rb_dock.find_dock_device(hass, vac.entity_id) is None


def test_rd4_a_same_identifier_dock_under_another_entry_is_never_returned(hass):
    """[RD-4] The lookup is scoped to the vacuum's OWN config entry.

    HA 2026.10 deprecated the unscoped ``async_get_device`` (gone in 2027.8.0) because
    identifiers are unique only within a config entry: two Roborock entries can each
    hold a ``(roborock, duid_dock)`` — an account added twice, a re-added entry whose
    devices were never purged — and the unscoped call chose between them by insertion
    order. The dock registered by this vacuum's own entry is the only right answer.

    The foreign dock is registered FIRST so that insertion order favours it; that is
    what makes the unscoped lookup return the wrong device here.

    ABLATION: swap the scoped call back to ``async_get_device(identifiers=...)`` and
    this goes red.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.roborock import dock as rb_dock

    theirs = MockConfigEntry(domain="roborock", entry_id="rd4_theirs")
    theirs.add_to_hass(hass)
    mine = MockConfigEntry(domain="roborock", entry_id="rd4_mine")
    mine.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    foreign_dock = dev_reg.async_get_or_create(
        config_entry_id=theirs.entry_id, identifiers={("roborock", "rd4_duid_dock")},
    )
    robot = dev_reg.async_get_or_create(
        config_entry_id=mine.entry_id, identifiers={("roborock", "rd4_duid")},
    )
    my_dock = dev_reg.async_get_or_create(
        config_entry_id=mine.entry_id, identifiers={("roborock", "rd4_duid_dock")},
    )
    assert my_dock.id != foreign_dock.id, (
        "precondition: a 2026.10 registry holds one device per entry for the same "
        "identifier; if these merged, the ambiguity this test guards cannot exist"
    )
    vac = er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "rd4_uid",
        suggested_object_id="rd4", device_id=robot.id, config_entry=mine,
    )

    found = rb_dock.find_dock_device(hass, vac.entity_id)
    assert found is not None and found.id == my_dock.id
    assert found.id != foreign_dock.id, "another entry's dock must never be returned"


def test_rd5_the_lookup_trips_no_registry_deprecation(monkeypatch, hass):
    """[RD-5] The registry read must not be one HA has scheduled for removal.

    ``homeassistant.helpers.frame.report_usage`` is what printed "Detected that custom
    integration 'eufy_vacuum' calls `device_registry.async_get_device`, which is
    deprecated" at startup on a live 2026.10.1 box — the deprecated method calls it
    before doing anything else. This spies on the registry module's binding of it (the
    frame helper itself reports each call site only once per process, so a log-based
    check could be masked by an earlier test) and pins that the dock lookup makes no
    such call. The next registry read HA deprecates surfaces here first.

    ABLATION: swap the scoped call back to ``async_get_device(identifiers=...)`` and
    this goes red.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.roborock import dock as rb_dock

    entry = MockConfigEntry(domain="roborock", entry_id="rd5_entry")
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    robot = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd5_duid")},
    )
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd5_duid_dock")},
    )
    vac = er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "rd5_uid",
        suggested_object_id="rd5", device_id=robot.id, config_entry=entry,
    )

    reported: list[str] = []
    monkeypatch.setattr(dr, "report_usage", lambda what, **kw: reported.append(what))

    assert rb_dock.find_dock_device(hass, vac.entity_id) is not None
    assert not reported, reported


def test_rd6_a_core_without_the_scoped_lookup_still_resolves_the_dock(monkeypatch, hass):
    """[RD-6] The 2025.6.0 floor holds: no ``async_get_device_by_identifier``, still a dock.

    Measured in home-assistant/core: the scoped method is absent from device_registry.py
    at 2025.6.0 and 2026.7.0 and first present at 2026.8.0, while hacs.json declares a
    2025.6.0 floor. Called bare, the lookup is an AttributeError on every core in that
    span and the Roborock adapter never registers there. The 2.5.0 pre-release audit
    caught exactly that, shipped bare.

    The REAL registry stands in for an old core by losing the one method — delattr on
    the class — so the instance reads as a 2026.7 instance would. The fallback is the
    unscoped call, which on this core fires the 2026.10 deprecation; that is expected
    here and is why [RD-5] guards the main path separately.

    ABLATION: drop the getattr fallback and call ``async_get_device_by_identifier``
    directly, and this goes red with AttributeError.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.roborock import dock as rb_dock

    entry = MockConfigEntry(domain="roborock", entry_id="rd6_entry")
    entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    robot = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd6_duid")},
    )
    dock = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("roborock", "rd6_duid_dock")},
    )
    vac = er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "rd6_uid",
        suggested_object_id="rd6", device_id=robot.id, config_entry=entry,
    )

    monkeypatch.delattr(dr.DeviceRegistry, "async_get_device_by_identifier")
    assert not hasattr(dev_reg, "async_get_device_by_identifier"), (
        "precondition: the registry must look like a core older than 2026.8"
    )

    found = rb_dock.find_dock_device(hass, vac.entity_id)
    assert found is not None and found.id == dock.id


# ---------------------------------------------------------------------------
# [DD-*] ISSUE #69 follow-up — the dock dump records WHICH BRANCH ran
# ---------------------------------------------------------------------------

def _register_with_dock(monkeypatch, hass, dock_result):
    """Register the adapter with `dock_profile` forced, and return the stored config."""
    from custom_components.eufy_vacuum.adapters.registry import get_adapter_config

    _patch_device(monkeypatch)
    monkeypatch.setattr(rb, "dock_profile", lambda h, v: dock_result)
    clear_registry()
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    return get_adapter_config(_RVAC) or {}


def test_dd1_an_undetermined_dock_records_the_catalogue_fallback(monkeypatch, hass):
    """[DD-1] `dock_profile` declining must be visible AS a decline.

    ABLATION: hard-code `"resolved": True` in the fallback branch and this goes red.
    """
    dd = _register_with_dock(monkeypatch, hass, None).get("_dock_detection")

    assert dd, "the block must be recorded even when the live probe declined"
    assert dd["resolved"] is False
    assert dd["source"] == "model_catalog"
    assert dd["reason"] == "undetermined"
    assert dd["dock_type"] is None and dd["dock_type_name"] is None


def test_dd2_a_resolved_dock_carries_the_vendors_own_answer(monkeypatch, hass):
    """[DD-2] The vendor's code and name reach the dump verbatim.

    `dock_type_name` is the vendor's enum name, quoted as it is produced rather than
    prettified — it is what gets pasted into an upstream issue.

    ABLATION: drop `dock_type`/`dock_type_name` from the resolved branch -> red.
    """
    dd = _register_with_dock(monkeypatch, hass, {
        "has_dock": True, "dock_type": 7, "dock_type_name": "o4_dock",
        "is_washable": True, "is_dryable": True, "is_collectable": True,
    }).get("_dock_detection")

    assert dd["resolved"] is True
    assert dd["source"] == "device"
    assert dd["dock_type"] == 7
    assert dd["dock_type_name"] == "o4_dock"
    assert dd["reason"] is None, "a fully resolved profile carries no reason"


def test_dd3_two_no_dock_answers_with_opposite_causes_are_distinguishable(
    monkeypatch, hass
):
    """[DD-3] THE case the block exists for, and the one that forces `resolved`.

    A live probe that resolved a genuinely dockless machine and a probe that DECLINED
    and fell back to a catalogue default that also says no dock produce identical
    capabilities — `supports_mop_wash` / `_dry` / `_empty` all False either way. Before
    this block the dump could not tell them apart, and on ISSUE #69 establishing which
    had happened meant reading the model catalogue and reasoning backwards from the
    fact that the controls were populated at all. That only worked because the
    fallback happened to DISAGREE with the live answer; where they agree, as here,
    there was nothing to reason from.

    ABLATION: record only `dock_type`/`dock_type_name` and drop `resolved`/`source` —
    both sides become `{None, None}` and this goes red, which is precisely the dump
    that could not answer #69.
    """
    declined = _register_with_dock(monkeypatch, hass, None)
    live_no_dock = _register_with_dock(monkeypatch, hass, {
        "has_dock": False, "dock_type": None, "dock_type_name": None,
        "reason": "no_dock_device",
    })

    # The outcome really is identical — the premise of the test, asserted not assumed.
    assert declined["capabilities"]["supports_mop_wash"] is False
    assert live_no_dock["capabilities"]["supports_mop_wash"] is False
    assert not declined.get("dock_events", {}).get("action_controls")
    assert not live_no_dock.get("dock_events", {}).get("action_controls")

    a, b = declined["_dock_detection"], live_no_dock["_dock_detection"]
    assert a != b, "identical outcomes, opposite causes — the dump must separate them"
    assert (a["resolved"], a["source"]) == (False, "model_catalog")
    assert (b["resolved"], b["source"]) == (True, "device")
    assert b["reason"] == "no_dock_device"


def test_dd4_a_dock_newer_than_the_library_keeps_its_code(monkeypatch, hass):
    """[DD-4] The case where the fine detail is unknown but the dock is real.

    `dock.py` returns has_dock True with a numeric type and no NAME for a dock newer
    than the installed python-roborock. That integer is the whole lead for adding it,
    so losing it to the unnamed case would discard the one actionable value.

    ABLATION: blank `dock_type` whenever `dock_type_name` is None -> red.
    """
    dd = _register_with_dock(monkeypatch, hass, {
        "has_dock": True, "dock_type": 99, "dock_type_name": None,
        "reason": "dock_type_newer_than_library",
    }).get("_dock_detection")

    assert dd["dock_type"] == 99
    assert dd["dock_type_name"] is None
    assert dd["reason"] == "dock_type_newer_than_library"


# ---------------------------------------------------------------------------
# [MS-8..10] ISSUE #67 REOPENED — a DISABLED select is not a control
# ---------------------------------------------------------------------------

def _q5_water_precall_armed(hass, monkeypatch, make_select=None):
    """Register an uncatalogued mopless Q5 and report whether water pre-call is armed.

    The arming is the observable that matters: `mixed_mode_water_policy: "safest"` is the
    entry that ABORTS dispatch on a missing target, so "armed with no reachable target"
    is exactly the state in which every clean fails.
    """
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.registry import get_adapter_config

    monkeypatch.setattr(
        rb, "_device_for_vacuum",
        lambda h, v: type("D", (), {"model": "roborock.vacuum.a34",
                                    "manufacturer": "Roborock", "id": "d1"})(),
    )
    monkeypatch.setattr(rb, "dock_profile", lambda h, v: None)
    clear_registry()
    entry = MockConfigEntry(domain="roborock", entry_id="ms8")
    entry.add_to_hass(hass)
    if make_select is not None:
        make_select(er.async_get(hass), entry)
    hass.states.async_set(_Q5, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _Q5)
    cfg = get_adapter_config(_Q5) or {}
    pre = (cfg.get("dispatch") or {}).get("global_pre_calls") or []
    return cfg, any(p.get("field") == "water_level" for p in pre)


_Q5 = "vacuum.roborock_q5"


def test_ms8_a_mop_module_with_a_disabled_control_keeps_aborting(hass, monkeypatch):
    """[MS-8] A disabled control on a device that CAN mop must still refuse the run.

    THIS TEST ASSERTED THE OPPOSITE ONE COMMIT AGO, and the flip is the point. Its first
    form was built from ISSUE #67's second report and said: a disabled select is not a
    control, so do not arm the pre-call. True about the select — and the wrong conclusion
    once the water box is also read, because this fixture's water box means the hardware
    HAS a mop module.

    On such a device we cannot lower the water, and proceeding would let a mixed batch
    wet-mop the vacuum-only rooms. Refusing is the correct answer and the one #51 exists
    to give. The reporter's own Q5 is NOT this case: it claims no mop module, so it is
    narrowed by [MS-11] and never reaches here.

    What the disabled case gets instead is a better REFUSAL — see [DM-5]: "does not
    exist" is useless to someone looking at the entity they switched off themselves.

    ABLATION: narrow on the control's reachability again and this goes red, together
    with [MS-6] and [MS-10] — they are the same rule seen from three shapes.
    """
    from homeassistant.helpers import entity_registry as er

    def _disabled(registry, entry):
        registry.async_get_or_create(
            "binary_sensor", "roborock", "q5_water_box_status",
            suggested_object_id="roborock_q5_water_box_attached", config_entry=entry,
        )
        registry.async_get_or_create(
            "select", "roborock", "q5_water_box_mode",
            suggested_object_id="roborock_q5_mop_intensity", config_entry=entry,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )

    cfg, armed = _q5_water_precall_armed(hass, monkeypatch, _disabled)

    assert armed is True, (
        "the water box says this hardware mops; skipping the safe-water push because "
        "its control is switched off is how dry rooms get wet-mopped"
    )
    assert cfg["capabilities"]["supports_mop_features"] is True


def test_ms9_the_boot_window_still_keeps_the_guess(hass, monkeypatch):
    """[MS-9] A real mop device mid-startup must NOT be narrowed.

    Narrowing a device that really mops is the one branch that can wet-mop a dry room:
    `mop_settable` False means no safest-water pre-call, so a mixed batch never lowers
    the water. The boot window therefore has to survive, and #51 has to keep aborting.

    THE PREMISE OF THIS TEST CHANGED when the signal was swapped, and it is worth
    saying why rather than quietly editing it. It used to register the mop SELECT alone,
    stateless, and assert the guess survived — correct while the select was the only
    signal. It is not correct now: the select exists on every V1 Roborock, so "select
    registered, no water box" is not an unknown, it is positive evidence of a device
    with no mop module ([MS-11]). The boot window is the case where BOTH signals are
    registered and NEITHER has a state yet — the integration has created its entities
    and they have not materialised. That is what this asserts.

    ABLATION: require a STATE (rather than registered-or-stated) on either signal and
    this goes red.
    """
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.registry import get_adapter_config

    monkeypatch.setattr(
        rb, "_device_for_vacuum",
        lambda h, v: type("D", (), {"model": "roborock.vacuum.a34",
                                    "manufacturer": "Roborock", "id": "d1"})(),
    )
    monkeypatch.setattr(rb, "dock_profile", lambda h, v: None)
    clear_registry()
    entry = MockConfigEntry(domain="roborock", entry_id="ms9")
    entry.add_to_hass(hass)
    reg = er.async_get(hass)
    reg.async_get_or_create("binary_sensor", "roborock", "q5_water_box_status",
                            suggested_object_id="roborock_q5_water_box_attached",
                            config_entry=entry)
    reg.async_get_or_create("select", "roborock", "q5_water_box_mode",
                            suggested_object_id="roborock_q5_mop_intensity",
                            config_entry=entry)
    assert hass.states.get("select.roborock_q5_mop_intensity") is None, "stateless"
    assert hass.states.get("binary_sensor.roborock_q5_water_box_attached") is None

    hass.states.async_set(_Q5, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _Q5)
    cfg = get_adapter_config(_Q5) or {}
    pre = (cfg.get("dispatch") or {}).get("global_pre_calls") or []

    assert any(p.get("field") == "water_level" for p in pre), (
        "both signals registered and neither materialised is a boot window on a device "
        "that may really mop — the guess must survive so #51 still aborts"
    )


def test_ms10_a_disabled_water_box_still_counts_as_HAVING_a_mop(hass, monkeypatch):
    """[MS-10] The disabled rule must NOT carry over to `has_mop`.

    `mop_settable` asks *can we send a command* — a disabled entity is a definite no.
    `has_mop` asks *does this hardware have a mop* — a water-box sensor the integration
    created and someone then switched off is still evidence that it does. Collapsing the
    two is the exact confusion the catalogue exists to prevent (the S6 HAS a mop and
    cannot be told to use it).

    ABLATION: reuse the mop_settable predicate for `_any_mop_signal` and this goes red.
    """
    from homeassistant.helpers import entity_registry as er

    def _disabled_water_box(registry, entry):
        registry.async_get_or_create(
            "binary_sensor", "roborock", "q5_water_box",
            suggested_object_id="roborock_q5_water_box_attached", config_entry=entry,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

    cfg, armed = _q5_water_precall_armed(hass, monkeypatch, _disabled_water_box)

    assert armed is True, (
        "a disabled water box still claims the mop module, and no control exists to "
        "lower the water — so this refuses rather than running dry rooms wet ([MS-6])"
    )
    assert cfg["capabilities"]["supports_mop_features"] is True, (
        "a disabled water-box sensor is still evidence the hardware has a mop; "
        "reporting no mop here would be the same conflation #67 came from"
    )


# ---------------------------------------------------------------------------
# [MS-11..13] The signal swap — the mop SELECT is a library default
# ---------------------------------------------------------------------------
#
# Measured in python-roborock 7.12.3: `get_water_modes()` can never return an empty
# list, and HA creates `select.<obj>_mop_intensity` on `if water_mode_options`. So the
# select is present on EVERY V1 Roborock. The water-box binary sensors are gated on
# `device_features.is_support_water_mode` instead — a real hardware claim — so their
# presence is the signal that actually answers "can this be told to mop".

def _q5_flags(hass, monkeypatch, *, water_box=None, mop_select=None):
    """Register an uncatalogued model with the two signals set independently."""
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.eufy_vacuum.adapters.registry import get_adapter_config

    monkeypatch.setattr(
        rb, "_device_for_vacuum",
        lambda h, v: type("D", (), {"model": "roborock.vacuum.a34",
                                    "manufacturer": "Roborock", "id": "d1"})(),
    )
    monkeypatch.setattr(rb, "dock_profile", lambda h, v: None)
    clear_registry()
    entry = MockConfigEntry(domain="roborock", entry_id="ms11")
    entry.add_to_hass(hass)
    reg = er.async_get(hass)
    if water_box:
        reg.async_get_or_create("binary_sensor", "roborock", "q5_water_box_status",
                                suggested_object_id="roborock_q5_water_box_attached",
                                config_entry=entry)
    if mop_select:
        reg.async_get_or_create("select", "roborock", "q5_water_box_mode",
                                suggested_object_id="roborock_q5_mop_intensity",
                                config_entry=entry)
    hass.states.async_set(_Q5, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _Q5)
    cfg = get_adapter_config(_Q5) or {}
    pre = (cfg.get("dispatch") or {}).get("global_pre_calls") or []
    return cfg, any(p.get("field") == "water_level" for p in pre)


def test_ms11_a_mop_select_without_a_mop_module_is_not_mop_settable(hass, monkeypatch):
    """[MS-11] The shape a CURRENT python-roborock produces on a mopless Q5.

    The select exists — it exists on every V1 device — and there is no water-box
    sensor, because `is_support_water_mode` is false. Keying on the select alone says
    "mop settable", arms the safest-water pre-call and aborts every clean: ISSUE #67
    returning by a different door as installs upgrade, with the earlier fixes silently
    degraded to no-ops.

    ABLATION: drop `_mop_module_claimed` from `_mop_control_exists` and this goes red.
    """
    cfg, armed = _q5_flags(hass, monkeypatch, water_box=False, mop_select=True)

    assert armed is False, (
        "a select with no mop module behind it is a library artifact, not a control"
    )
    assert cfg["capabilities"]["supports_water_control"] is False


def test_ms12_a_real_mop_device_is_untouched(hass, monkeypatch):
    """[MS-12] The no-regression guard: both signals present -> the guess survives.

    This is what stops [MS-11] from being a blanket "uncatalogued means mopless". A
    device claiming a mop module AND publishing a reachable control keeps
    `mop_settable`, so #51 still aborts when its entity goes missing mid-run.

    ABLATION: narrow unconditionally for DEFAULT_PROFILE and this goes red.
    """
    cfg, armed = _q5_flags(hass, monkeypatch, water_box=True, mop_select=True)

    assert armed is True
    assert cfg["capabilities"]["supports_water_control"] is True
    assert cfg["capabilities"]["supports_mop_features"] is True


def test_ms13_has_mop_follows_the_module_not_the_select(hass, monkeypatch):
    """[MS-13] `has_mop` keys on the water box ALONE.

    It used to be OR-ed with the mop select. On a current library that makes every V1
    Roborock report a mop it may not have — exactly the confident-and-wrong diagnostics
    this narrowing was added to stop.

    ABLATION: restore the `or` arm on the select and this goes red.
    """
    cfg, _armed = _q5_flags(hass, monkeypatch, water_box=False, mop_select=True)

    assert cfg["capabilities"]["supports_mop_features"] is False, (
        "a mop-intensity select exists on every V1 Roborock; it is not evidence of a mop"
    )


def _route_pre_call(cfg):
    """The route entry of the mop global_pre_calls, or None."""
    pre = (cfg.get("dispatch") or {}).get("global_pre_calls") or []
    return next((p for p in pre if p.get("field") == "path_type"), None)


def test_rt10_route_is_not_pushed_while_no_user_surface_exists(monkeypatch, hass):
    """[RT-10] ISSUE #71 — never set a route the user cannot see or change.

    #66 made the axis live: `_route_axis` is true whenever the device publishes
    `select.<obj>_mop_mode`, and the pre-call then pushes each group's `path_type`
    before dispatch. The other half never shipped, so on a Saros 10 we pushed
    `mop_mode = standard` before every clean, overwriting the owner's app setting from
    a value they were never shown. "Route is not offered" and "route is silently set"
    were one defect.

    THIS TEST'S SCENARIO CHANGED 2026-10-19 AND ITS ASSERTION FLIPPED — for the reason
    its own text predicted. It used to pin "a stock Roborock pushes nothing", because
    `path_type_options` reached no card surface. Core now RESOLVES the canonical
    `clean_intensity` across the brands' own field names, so Roborock's declaration
    does render a picker, and the old text said precisely that this would re-arm the
    push. [RT-11] is now the stock case; this one keeps the guard pointed at what is
    left of its job: an axis with NO declared vocabulary from either source.

    The gate must stay a SURFACE test and not a hard false, or a model shipping without
    that vocabulary would be pushed a value into a picker that cannot exist.

    ABLATION: restore the unconditional `if _route_axis:` and this goes red.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a147")
    # No vocabulary from EITHER source: the device publishes the select but lists no
    # options, and the brand declares no list to fall back to.
    #
    # Patched on the ADAPTER module, not `rbv`. adapter.py does
    # `from .vocabulary import PATH_TYPE_OPTIONS`, so it holds its OWN binding and
    # patching the vocabulary module leaves the fallback reading the real list — which
    # is how the first draft of this test passed a config it had not actually changed.
    monkeypatch.setattr(rb, "PATH_TYPE_OPTIONS", [], raising=True)
    hass.states.async_set("select.ivy_mop_mode", "standard", {"options": []})
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    assert cfg["capabilities"]["supports_path_control"] is True, (
        "the capability is unchanged — the device does publish the select"
    )
    assert _route_pre_call(cfg) is None, (
        "pushed a route into an axis with no option list, so no picker can exist"
    )


def test_rt11_route_is_pushed_once_the_axis_is_user_visible(monkeypatch, hass):
    """[RT-11] The other arm, and now the STOCK case: a shipped Roborock.

    Without this, [RT-10] is satisfied by deleting the feature. The gate is the user
    surface, so declaring the option list the card reads is what re-arms the push — and
    since core resolves `clean_intensity` across `("clean_intensity", "path_type")`,
    Roborock's own declaration IS that list. No monkeypatch: this is the config the
    adapter builds on a real device.

    ⚠ was: a monkeypatch of `rb.vocabulary.CLEAN_INTENSITY_OPTIONS` with
    `raising=False` — which only ever worked because that attribute is ABSENT from the
    module. The gate it exercised tested a name nothing defines, so it could never have
    become true on a real install, and the test passed while proving nothing about one.
    That is the defect this pair now pins.

    ABLATION: hard-code the gate to False and this goes red while [RT-10] stays green.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a147")
    hass.states.async_set(
        "select.ivy_mop_mode", "standard",
        {"options": ["standard", "deep", "deep_plus"]},
    )
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    pre = _route_pre_call(cfg)
    assert pre is not None, "the picker renders for this brand now, so apply the route"
    assert pre["service"]["target_role"] == "mop_mode"
    assert pre["rank"] == ["standard", "deep", "deep_plus"]


def test_rt12_the_field_this_brand_declares_is_one_core_resolves(monkeypatch, hass):
    """[RT-12] THE COUPLING THAT REPLACED AN IMPORT.

    The gate asks a LOCAL question — "did I declare a non-empty option list?" — and
    infers a rendered picker from it. That inference holds only while core's resolver
    still accepts this brand's field name. [ISO-1] forbids a brand package from
    importing `profiles.room_profiles` to ask directly, so the coupling is pinned here
    rather than assumed.

    Drop `path_type` from `AXIS_FIELD_CANDIDATES` and this goes red — where otherwise
    the gate would stay armed while the picker silently stopped rendering, which is the
    exact failure the gate exists to prevent.
    """
    from custom_components.eufy_vacuum.profiles.room_profiles import resolve_axis

    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a147")
    hass.states.async_set(
        "select.ivy_mop_mode", "standard",
        {"options": ["standard", "deep", "deep_plus"]},
    )
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    vocab = get_adapter_config(_RVAC)["vocabulary"]

    field, options = resolve_axis(vocab, "clean_intensity")

    assert field == "path_type", "core no longer resolves this brand's own field name"
    assert options == vocab["path_type_options"], "the picker would render a stale list"


def test_rt13_the_saros_route_ladder_is_ordered_not_published_order(monkeypatch, hass):
    """[RT-13] THE RANK TRAP, with the reporter's own tokens (issue #71).

    A Saros 10 publishes its mop-route options as
    `standard, deep, deep_plus, fast, smart_mode, custom` — where `fast`, the LEAST
    dense pass, is listed FOURTH. The route pre-call resolves max-wins, so ranking by
    publication order would make `fast` outrank `deep_plus` and a batch asking for the
    deepest scrub would get the shallowest.

    Water escapes this because its device list IS ascending; fan escapes it by having
    no rank at all. Route has a rank AND an unordered source, so the ladder is written
    down in `PATH_TYPE_RANK_ORDER` and the device's list is sorted onto it.

    `smart_mode` and `custom` are dropped from both — real device options and real
    answers, but not positions on a ladder.

    ABLATION: rank by read order and this goes red while [RT-11] stays green, because
    [RT-11]'s device publishes no `fast` and is already in ladder order — which is
    exactly how this trap would have shipped unnoticed.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a147")
    hass.states.async_set(
        "select.ivy_mop_mode", "standard",
        {"options": ["standard", "deep", "deep_plus", "fast", "smart_mode", "custom"]},
    )
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    values = [o["value"] for o in cfg["vocabulary"]["path_type_options"]]
    assert values == ["fast", "standard", "deep", "deep_plus"], (
        "the picker must read weakest-to-strongest, not in publication order"
    )
    assert _route_pre_call(cfg)["rank"] == ["fast", "standard", "deep", "deep_plus"], (
        "fast outranking deep_plus would turn the deepest scrub into the shallowest"
    )


def test_rt14_an_unknown_rung_is_offered_but_not_ranked(monkeypatch, hass):
    """[RT-14] The asymmetry route is allowed and water is NOT.

    A rung this adapter has never seen is a real thing the device can do, so it is
    OFFERED. It is not RANKED, because we do not know where it sits and guessing is
    precisely how `fast` would have outranked `deep_plus`. An unranked stored value
    makes the max-wins resolve find nothing and leave the device alone, which is the
    honest answer: we were told nothing we can order.

    Safe HERE and nowhere else on this brand — over-scrubbing costs time, while the
    water axis carries `mixed_mode_water_policy: "safest"` because over-watering costs
    a floor. Water therefore keeps picker and rank IDENTICAL; this one deliberately
    does not, and the difference is the point.
    """
    clear_registry()
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.a147")
    hass.states.async_set(
        "select.ivy_mop_mode", "standard",
        {"options": ["standard", "deep", "zz_new_rung"]},
    )
    hass.states.async_set(_RVAC, "docked", {"supported_features": 30524})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    cfg = get_adapter_config(_RVAC)

    values = [o["value"] for o in cfg["vocabulary"]["path_type_options"]]
    assert values == ["standard", "deep", "zz_new_rung"], "an unseen rung is offered"
    assert _route_pre_call(cfg)["rank"] == ["standard", "deep"], "but never ranked"
