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
    mc = s6_config["maintenance_components"]
    # 4 robot life-tracked consumables + 2 DOCK life-tracked consumables
    # + 5 base guide-only cleanables + 3 dock/station guide-only cleanables
    # (the guide-only station ones are family-gated at render time by the manager).
    assert set(mc) == {
        "main_brush", "side_brush", "filter", "sensor",
        "cleaning_brush", "strainer",
        "dustbin", "mop_cloth", "water_filter", "caster_wheel", "main_wheel",
        "dock_dust_bag", "clean_water_tank", "dirty_water_tank",
    }
    assert mc["main_brush"]["sensor_suffix"] == "main_brush_time_left"
    assert mc["main_brush"]["maintenance_only"] is False
    # `remaining_is_state` is PRUNED, not renamed. It was declared on four components,
    # projected onto all twelve with a False default, and read by absolutely nothing —
    # its documented consumer ("core seam — Wave 1b") never shipped. This assertion used
    # to check the flag was True, which proved the declaration existed rather than that
    # it did anything; asserting its absence is the honest version.
    assert "remaining_is_state" not in mc["main_brush"]
    # Filter reset button is "air_filter", not "filter".
    assert mc["filter"]["reset_button"]["entity_suffixes"] == ["reset_air_filter_consumable"]
    # Guide-only cleanables: maintenance_only, no upstream sensor, zero intervals.
    for comp in ("dustbin", "mop_cloth", "water_filter", "caster_wheel", "main_wheel",
                 "dock_dust_bag", "clean_water_tank", "dirty_water_tank"):
        assert mc[comp]["maintenance_only"] is True
        assert mc[comp]["sensor_suffix"] is None
        assert mc[comp]["default_interval_hours"] == 0.0
    for comp in mc.values():
        # label + icon are bare-deref'd by the platform consumers.
        assert comp["label"] and comp["icon"]


def test_dock_consumables_declare_the_translation_key_not_the_id_suffix(s6_config):
    """The dock two are keyed by TRANSLATION KEY, and that is load-bearing.

    HA derives a dock entity id from the DISPLAY NAME, not the translation key, and for
    these two the names diverge — measured against HA 2026.8.1 the real ids end
    `_dock_maintenance_brush_time_left` and `_dock_strainer_time_left`. So:

      * `strainer` also happens to resolve on the SUFFIX rung, since its id really does
        end `_strainer_time_left`;
      * `cleaning_brush` CANNOT — the string "cleaning_brush" appears nowhere in its
        entity id — and resolves only on the TRANSLATION_KEY rung.

    Declaring the vendor's translation key is the one value that serves both rungs and
    survives a localized install, because a display name is translated and a
    translation_key never is. Anyone "correcting" these to the observed id suffix
    silently breaks cleaning_brush on every install and both of them on every
    non-English one, so the check is spelled out rather than implied.
    """
    mc = s6_config["maintenance_components"]

    assert mc["cleaning_brush"]["sensor_suffix"] == "cleaning_brush_time_left"
    assert mc["strainer"]["sensor_suffix"] == "strainer_time_left"

    # The measured ids, and the asymmetry between them.
    measured_brush = "sensor.ivy_dock_maintenance_brush_time_left"
    measured_strainer = "sensor.ivy_dock_strainer_time_left"
    assert measured_strainer.endswith("_" + mc["strainer"]["sensor_suffix"]), (
        "strainer should still be reachable by plain suffix match"
    )
    assert not measured_brush.endswith("_" + mc["cleaning_brush"]["sensor_suffix"]), (
        "if this ever passes, cleaning_brush became suffix-reachable and the comment "
        "above is stale — re-measure before trusting it"
    )
    assert "cleaning_brush" not in measured_brush

    # Both are real life-tracked components, not guide-only, and carry a reset button.
    for comp in ("cleaning_brush", "strainer"):
        assert mc[comp].get("maintenance_only") is not True
        assert mc[comp]["default_interval_hours"] > 0
        suffixes = mc[comp]["reset_button"]["entity_suffixes"]
        # The reset buttons live on the DOCK device, so the suffix must carry the
        # `dock_` infix — `_replacement_reset_entity` builds `button.{vacuum}_{suffix}`
        # from the VACUUM's object_id and would otherwise never reach them.
        assert all(s.startswith("dock_") for s in suffixes), suffixes


def test_upkeep_catalog(s6_config):
    """The guide half: model->family->guide wiring + the `standard` library shape."""
    cat = s6_config["upkeep_catalog"]
    # Guide families are maintenance PROFILES, not per-model. The S6 (and the whole
    # no-dock base lineup) resolves to `standard`.
    assert cat["model_guide_families"]["roborock.vacuum.s6"] == "standard"
    assert cat["model_names"]["roborock.vacuum.s6"] == "S6"
    assert cat["guide_family_names"]["standard"] == "Roborock"
    # Broad coverage: many models map to a family (not just the 3 capability models).
    assert len(cat["model_guide_families"]) >= 30
    # Station models resolve to their authored tier.
    assert cat["model_guide_families"]["roborock.vacuum.a70"] == "wash_station"   # S8 Pro Ultra
    assert cat["model_guide_families"]["roborock.vacuum.a38"] == "auto_empty"     # Q7 Max
    assert cat["model_guide_families"]["roborock.vacuum.a97"] == "wash_station"   # S8 MaxV Ultra (dual flat cloths)

    lib = cat["guide_library"]
    std = lib["standard"]
    # Every maintenance component the base profile exposes has a guide (4 tracked + 5 cleanables).
    for comp in (
        "main_brush", "side_brush", "filter", "sensor",
        "dustbin", "mop_cloth", "water_filter", "caster_wheel", "main_wheel",
    ):
        guide = std[comp]
        assert isinstance(guide["steps"], list) and guide["steps"], comp
        assert isinstance(guide["notes"], list), comp
        assert "clean_frequency" in guide and "replace_frequency" in guide, comp

    # Composed step-up tiers: base 9 inherited + dock deltas; base robot has none of them.
    assert "dock_dust_bag" not in std
    assert set(lib["auto_empty"]) == set(std) | {"dock_dust_bag"}
    assert set(lib["wash_station"]) == set(std) | {"dock_dust_bag", "clean_water_tank", "dirty_water_tank"}
    for comp in ("dock_dust_bag", "clean_water_tank", "dirty_water_tank"):
        assert lib["wash_station"][comp]["steps"], comp
    # Station mop_cloth is overridden (dock auto-washes) — differs from the base.
    assert lib["wash_station"]["mop_cloth"] != std["mop_cloth"]

    # Guide translations wired for all 17 languages (ar/he/ko/pl/cs/tr/id AI-draft, rest official).
    gt = cat["guide_translations"]
    assert set(gt) == {"de", "es", "fr", "it", "nl", "pt", "ru", "ja", "ko",
                       "zh-Hans", "zh-Hant", "ar", "he", "pl", "cs", "tr", "id"}
    # Every language covers the full standard set (9 comps) + the station dock deltas.
    _STD = {"main_brush", "side_brush", "filter", "sensor", "dustbin",
            "mop_cloth", "water_filter", "caster_wheel", "main_wheel"}
    _DOCK = {"dock_dust_bag", "clean_water_tank", "dirty_water_tank"}
    for lang in gt:
        assert _STD <= set(gt[lang]["standard"]), f"{lang} std missing {_STD - set(gt[lang]['standard'])}"
        assert _DOCK <= set(gt[lang]["wash_station"]), f"{lang} station missing {_DOCK - set(gt[lang]['wash_station'])}"
        for comp in _STD:
            assert gt[lang]["standard"][comp]["steps"], f"{lang}/{comp}"


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


def test_dock_profile_returns_undetermined_when_vendor_library_is_absent(monkeypatch):
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
