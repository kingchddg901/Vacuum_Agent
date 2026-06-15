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
from custom_components.eufy_vacuum.adapters.roborock import model_catalog
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


# --- brand auto-detect ------------------------------------------------------


def test_is_roborock_by_manufacturer(monkeypatch, hass):
    _patch_device(monkeypatch, manufacturer="Roborock", model="roborock.vacuum.s6")
    assert rb.is_roborock_vacuum(hass, _RVAC) is True


def test_is_roborock_by_model_prefix(monkeypatch, hass):
    # Manufacturer differs (rebadged), model prefix still identifies the brand.
    _patch_device(monkeypatch, manufacturer="Xiaomi", model="roborock.vacuum.a01")
    assert rb.is_roborock_vacuum(hass, _RVAC) is True


def test_is_not_roborock(monkeypatch, hass):
    _patch_device(monkeypatch, manufacturer="Eufy", model="T2351")
    assert rb.is_roborock_vacuum(hass, _RVAC) is False


def test_is_not_roborock_when_no_device(monkeypatch, hass):
    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: None)
    assert rb.is_roborock_vacuum(hass, _RVAC) is False


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
    assert set(mc) == {"main_brush", "side_brush", "filter", "sensor"}
    assert mc["main_brush"]["sensor_suffix"] == "main_brush_time_left"
    assert mc["main_brush"]["remaining_is_state"] is True
    # Filter reset button is "air_filter", not "filter".
    assert mc["filter"]["reset_button"]["entity_suffixes"] == ["reset_air_filter_consumable"]
    for comp in mc.values():
        # label + icon are bare-deref'd by the platform consumers.
        assert comp["label"] and comp["icon"]


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
