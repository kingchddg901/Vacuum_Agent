"""
Roborock adapter registration for the multi-brand vacuum framework.

Assembles the Roborock adapter config from the constants, vocabulary, entity
patterns, and maintenance catalog in the sibling modules, and registers it with
the adapter registry for one managed vacuum. Mirrors
``adapters/eufy/adapter.py`` (the reference implementation).

Capability-gated, BRAND-level (``adapter_id = "roborock"``): the config is shaped
by the device-registry model string (``device.model``) via ``model_catalog`` plus
live entity presence (``detect_capabilities``), so one adapter covers the S6 today
and future Roborock models. See README.md for the Wave 1 scope + deferrals.

Called once per managed vacuum at startup from ``async_setup_entry`` in
``__init__.py`` via the brand-dispatch loop (``is_roborock_vacuum`` selects this
registrar over the Eufy one).
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..registry import register_adapter_config
from .const import ADAPTER_ID, LOW_BATTERY_THRESHOLD_PERCENT
from .entities import (
    build_entity_id,
    SUFFIX_TASK_STATUS,
    SUFFIX_ACTIVE_CLEANING_TARGET,
    SUFFIX_ACTIVE_MAP,
    SUFFIX_MOP_INTENSITY,
    SUFFIX_CLEANING_TIME,
    SUFFIX_CLEANING_AREA,
    SUFFIX_BATTERY,
    SUFFIX_ERROR_MESSAGE,
    SUFFIX_CHARGING,
    SUFFIX_JOB_ACTIVE,
    SUFFIX_WATER_BOX,
    DOMAIN_BINARY_SENSOR,
    DOMAIN_SELECT,
)
from .maintenance_components import MAINTENANCE_COMPONENTS
from .model_catalog import profile_for_model
from .vocabulary import (
    ACTIVE_RUN_TASK_STATES,
    NOT_ERROR_SENTINELS,
    CANCEL_DETECTION_STATES,
    FAN_SPEED_OPTIONS,
    WATER_LEVEL_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def _device_for_vacuum(hass: HomeAssistant, vacuum_entity_id: str):
    """Return the HA device-registry entry for a vacuum entity, or None."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(vacuum_entity_id)
    if entry is None or entry.device_id is None:
        return None
    return dr.async_get(hass).async_get(entry.device_id)


def is_roborock_vacuum(hass: HomeAssistant, vacuum_entity_id: str) -> bool:
    """True if the vacuum's HA device is a Roborock.

    Used by the integration's brand-dispatch wiring to pick this registrar over
    the Eufy one. Auto-detects from the public device registry (manufacturer
    ``Roborock`` or a ``roborock.`` model prefix) — no private coordinator data.
    A future UI brand selector can override this.
    """
    device = _device_for_vacuum(hass, vacuum_entity_id)
    if device is None:
        return False
    if device.manufacturer and device.manufacturer.strip().lower() == "roborock":
        return True
    if device.model and str(device.model).lower().startswith("roborock."):
        return True
    return False


def register_roborock_adapter_for_vacuum(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> None:
    """Assemble and register the Roborock adapter config for one vacuum.

    Idempotent — re-calling for the same vacuum overwrites the previous
    registration. The capability flags come from the model profile (device
    registry) OR-ed with live entity presence, so the registered config reflects
    this specific installation's actual HA surface.
    """
    from ...core.capabilities import detect_capabilities

    vid = vacuum_entity_id

    # --- model identity (device registry — the supported public source) -------
    device = _device_for_vacuum(hass, vid)
    detected_model = device.model if device is not None else None
    profile = profile_for_model(detected_model)

    # --- capability gating ----------------------------------------------------
    # Hints come from the model profile; detect_capabilities OR-s them with live
    # entity presence. Roborock's mop is a SELECT (mop_intensity), so we assert
    # supports_mop_features via the hint rather than mapping it to the detector's
    # water_level slot (which would falsely imply station water on a no-dock unit).
    entity_candidates: dict[str, list[str]] = {
        "task_status": [build_entity_id(vid, SUFFIX_TASK_STATUS)],
        "active_cleaning_target": [build_entity_id(vid, SUFFIX_ACTIVE_CLEANING_TARGET)],
        "active_map": [build_entity_id(vid, SUFFIX_ACTIVE_MAP, DOMAIN_SELECT)],
        "cleaning_time": [build_entity_id(vid, SUFFIX_CLEANING_TIME)],
        "cleaning_area": [build_entity_id(vid, SUFFIX_CLEANING_AREA)],
    }
    capability_hints: dict[str, bool] = {
        "supports_mop_features": profile["has_mop"],
        "supports_mop_wash": profile["has_dock"],
        "supports_mop_dry": profile["has_dock"],
        "supports_empty_dust": profile["has_dock"],
        "supports_path_control": False,  # no per-room fan/water on the wire
    }
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=vid,
        detected_model=detected_model,
        entity_candidates=entity_candidates,
        model_family=profile["family"],
        capability_hints=capability_hints,
        maintenance_components=MAINTENANCE_COMPONENTS,
    )

    # --- entity ID map --------------------------------------------------------
    # active_map (select.{id}_selected_map) reports the map NAME ("Main floor");
    # Wave 2a confirmed its id-space and wires it as the discovery active-map +
    # the multi-map alignment anchor (trivial at one map, load-bearing on a
    # multi-map flip). job_active is the recharge-resume disambiguator (see
    # completion block); harmless if unconsumed.
    entities = {
        "task_status": build_entity_id(vid, SUFFIX_TASK_STATUS),
        "active_cleaning_target": build_entity_id(vid, SUFFIX_ACTIVE_CLEANING_TARGET),
        "active_map": build_entity_id(vid, SUFFIX_ACTIVE_MAP, DOMAIN_SELECT),
        "cleaning_time": build_entity_id(vid, SUFFIX_CLEANING_TIME),
        "cleaning_area": build_entity_id(vid, SUFFIX_CLEANING_AREA),
        "battery": build_entity_id(vid, SUFFIX_BATTERY),
        "error_message": build_entity_id(vid, SUFFIX_ERROR_MESSAGE),
        "charging": build_entity_id(vid, SUFFIX_CHARGING, DOMAIN_BINARY_SENSOR),
        "job_active": build_entity_id(vid, SUFFIX_JOB_ACTIVE, DOMAIN_BINARY_SENSOR),
        # mop_active: the S6 has NO per-room clean_mode — mopping is driven by the
        # physical water tank. The card reads this (via snapshot.mop_active) to
        # surface mop state + the water-level field only when the tank is attached.
        "mop_active": build_entity_id(vid, SUFFIX_WATER_BOX, DOMAIN_BINARY_SENSOR),
    }

    config = {
        "adapter_id": ADAPTER_ID,
        "source": "code",
        "display_name": profile["display_name"],
        # Short brand/app name the card uses in copy ("Clean from the Roborock app").
        "brand": "Roborock",

        "entities": entities,

        "vocabulary": {
            # Status strings that mean "actively running" (verified in the run trace).
            "active_run_task_states": sorted(ACTIVE_RUN_TASK_STATES),
            "not_error_sentinels": sorted(NOT_ERROR_SENTINELS),
            # No dock -> no wash/empty/recycle/drying states.
            "hard_service_states": [],
            "drying_states": [],
            # Cancel detection: Roborock returns via `returning_home` (not the
            # framework default `returning`), and its active status is
            # mode-specific. Without this, _detect_cancel_likely_run never fires
            # for Roborock and a cancelled run pollutes learning estimates.
            "cancel_detection_states": CANCEL_DETECTION_STATES,
            # Card-facing dropdowns. fan_speed + water_level (mop_intensity 1:1).
            # clean_mode_options / clean_intensity_options are intentionally OMITTED:
            # Roborock has no clean_intensity axis, and clean_mode is DERIVED from
            # mop_intensity (off => vacuum) rather than a single select — the canonical
            # clean_mode taxonomy is a pending decision (revisited with room editing in
            # Wave 2). The card hides a picker whose options list is absent.
            "fan_speed_options": FAN_SPEED_OPTIONS,
            "water_level_options": WATER_LEVEL_OPTIONS,
        },

        "completion": {
            # Dock contact fires `charging` immediately (trace: returning_home ->
            # vacuum=docked + status=charging within ~48s; no charging_complete lag),
            # guarded by has_observed_active_lifecycle so a pre-run charge can't finalize.
            "task_status_value": "charging",
            # Completion keys on the job-active (cleaning) binary clearing, NOT a
            # current-room sentinel: sensor.{id}_current_room reverts to the DOCK
            # room's NAME at the end (never a sentinel), so the default secondary
            # check would never pass. require_job_active_clear bypasses it and the
            # is_job_active guard (entities.job_active = binary_sensor.{id}_cleaning)
            # supplies the real signal — it stays ON through a mid-job recharge dock
            # and clears only at the true finish (history(3).csv: ON through the 19%
            # recharge + resume, OFF only at completion when total_count incremented).
            "require_job_active_clear": True,
        },

        "charging": {
            # NO low_battery_return_task_status: Roborock emits `returning_home` for
            # BOTH a low-battery auto-return AND a user/finish return, so keying off
            # the string alone would misclassify a full-battery return. Rely on the
            # generic returning + battery<=threshold path instead. The device returns
            # at ~19% natively; threshold 20 classifies that as low-battery. (Charging
            # state itself is read from entities.charging by core/charging.py.)
            "low_battery_threshold_percent": LOW_BATTERY_THRESHOLD_PERCENT,
        },

        "error_tracking": {
            # Confirmed dual-channel (run trace): sensor.{id}_status AND vacuum.state
            # both flip to `error` on the same tick, with sensor.{id}_vacuum_error
            # carrying the code string (bumper_stuck, wheels_suspended). The code lives
            # in the enum string, not a numeric attr, so error_code_attribute_names
            # usually misses -> code None, message = the code string (acceptable).
            "task_status_error_value": "error",
            "grace_window_seconds": 5,
            "error_code_attribute_names": ["error_code", "code", "errorCode"],
            "unknown_error_message": "Unknown error during run",
        },

        "dispatch": {
            # Rich primary path: vacuum.send_command app_segment_clean
            # {segments:[ints], repeat:1-3}. `command` MUST be explicit — an absent
            # key defaults to Eufy's `room_clean`. Per-room is PASSES only (repeat);
            # fan + mop are GLOBAL (set out-of-band). map_id / room_fields are omitted
            # (this engine emits neither). Exercised in Wave 2 once discovery lands.
            "template": "roborock_segment_clean",
            "service_domain": "vacuum",
            "service_name": "send_command",
            "command": "app_segment_clean",
            "rooms_field": "segments",
            "clean_passes_field": "repeat",
            "passes_max": 3,
            # app_segment_clean wants params LIST-wrapped on the wire:
            # params=[{segments:[...], repeat:n}] (confirmed on the device via a
            # working Dev-Tools call + the HA Roborock docs). Without this the bare
            # dict would reach the device and the clean would not start.
            "params_as_list": True,
            # Segment ids RENUMBER on re-segment (identity = name slug), so the
            # framework re-resolves each target room's slug -> LIVE id from a fresh
            # get_maps right before send. A stored id could otherwise clean the
            # wrong room after a map edit. Cleaning correctness is decoupled from
            # the identity-reconciliation review (which is about data attribution).
            "resolve_live_ids_by_slug": True,
            # GLOBAL fan + mop pre-call: per-room fan/water can't ride
            # app_segment_clean (passes only), AND the S6 app stores NO per-room
            # settings on the map (user-confirmed 2026-06-15) — so global is the
            # FINAL design for this model, not an interim compromise. Before
            # dispatch the framework pushes ONE global fan + mop value, max-wins
            # across the selected rooms (strongest request applies — mirrors the
            # batch-passes max rule). Fan rank is ascending SUCTION (device list
            # order puts gentle last, but it is the weakest), so it's spelled out
            # explicitly. water_level maps 1:1 to the mop_intensity select (no
            # value_map). mop_mode (standard/deep) has no per-room source -> left
            # as the device has it.
            "global_pre_calls": [
                {
                    "field": "fan_speed",
                    "rank": ["gentle", "quiet", "balanced", "turbo", "max"],
                    "service": {
                        "domain": "vacuum",
                        "service": "set_fan_speed",
                        "value_key": "fan_speed",
                    },
                },
                {
                    "field": "water_level",
                    "rank": ["off", "low", "medium", "high"],
                    "service": {
                        "domain": "select",
                        "service": "select_option",
                        "value_key": "option",
                        "target_entity_id": build_entity_id(
                            vid, SUFFIX_MOP_INTENSITY, DOMAIN_SELECT
                        ),
                    },
                },
            ],
        },

        "setup": {
            # add_vacuum -> import_active_map -> save_rooms. Roborock has no
            # Eufy-style one-at-a-time cloud-map "import", but the integration still
            # needs a map bucket built from the get_maps rooms before Configure Rooms
            # can show them. import_active_map is the brand-agnostic "discover +
            # create bucket" op (it refreshes the get_maps source first), so declare
            # it here to surface the rooms in setup. (Label is Eufy-flavored — a
            # per-brand step label is a later UX polish.)
            "steps": ["add_vacuum", "import_active_map", "save_rooms"],
        },

        "discovery": {
            # SERVICE-RESPONSE source: Roborock's id<->name map lives ONLY in the
            # roborock.get_maps response ({segment_id_str: name} per map), never an
            # entity attribute. The framework refreshes + flattens it
            # (rooms/source_refresh.py) at the async discovery boundaries into the
            # list-of-dicts the normalizer expects. (Live room NAMES are also on
            # sensor.{id}_current_room.options, but the id<->name pairing — needed
            # for app_segment_clean ints — is get_maps-only.)
            "source": "service_response",
            "maps_service": {"domain": "roborock", "service": "get_maps"},
            "maps_rooms_key": "rooms",
            # select.{id}_selected_map reports the map NAME; the flattened cache is
            # keyed by name so the resolved active-map id lines up with a cache key.
            "map_name_key": "name",
            "room_id_key": "segment_id",
            "room_name_key": "name",
            # Roborock surfaces ONLY named rooms (unnamed/auto-split segments never
            # appear in get_maps) — no phantom-room noise, unlike Eufy's CV
            # segmentor — so a newly-named room is deliberate: surface immediately.
            "new_room_confirmation_passes": 1,
            "auto_refresh_on": [
                "vacuum_docked",
                "active_map_changed",
                "config_entry_reload",
            ],
        },

        "live_transition": {
            # NATIVE current-room rollover: the device reports the live room
            # directly (sensor.{id}_current_room = entities.active_cleaning_target),
            # so the framework follows that signal — filtered to the job's target
            # rooms, matched by name slug, order-agnostic (the device path-optimizes,
            # so clean order != queue order) — instead of Eufy's counter-plateau /
            # timing heuristic. Tracks the last confirmed target + completes the
            # previous one when the signal moves; transit rooms (not job targets) are
            # ignored. Assumes rooms_unique_per_job (no revisits) — true here. Eufy
            # leaves native_transition_source False (the default) and is untouched.
            "enabled": True,
            "native_transition_source": True,
        },

        "mapping": {
            # No map-image entity (MAP feature bit unset) -> no image to segment.
            # noop stops polygon rendering; trace tracking still runs off position.
            # The CV path short-circuits on the missing image anyway. tuning MUST be
            # empty (NoopSegmenter.validate_tuning rejects keys).
            "segmenter_engine": "noop_fallback",
            "segmenter_tuning": {},
        },

        "job_segmenter": {
            # Roborock reports per-room progress NATIVELY (sensor.{id}_current_room +
            # segment_cleaning status), so there is no counter stream to plateau-detect.
            # Declare noop EXPLICITLY — an absent block falls back to eufy_counter_v1,
            # which would fabricate phantom room boundaries on Roborock's counters
            # (empirically: the only area plateaus in the run trace were obstacle
            # stalls, not room boundaries). No `tuning` (noop rejects keys).
            "engine": "noop_job_fallback",
        },

        "capabilities": {
            "supports_mop_features": caps.get("supports_mop_features", profile["has_mop"]),
            "supports_water_control": caps.get("supports_water_control", profile["has_mop"]),
            # Per-room fan/water do not ride the app_segment_clean wire (global only).
            "supports_path_control": False,
            "supports_edge_mopping": False,
            # No dock.
            "supports_mop_wash": False,
            "supports_mop_dry": False,
            "supports_empty_dust": False,
            "supports_station_water": False,
            "supports_robot_position": caps.get("supports_robot_position", False),
            # Conservative defaults pending a live segment-clean run (Wave 2).
            "position_lock_reliable": False,
            "rooms_unique_per_job": True,
        },

        "maintenance_components": {
            # Sourced from maintenance_components.py. Each consumable is a
            # remaining-hours countdown sensor (remaining_is_state) + an inline reset
            # button. label/icon are mandatory (consumers bare-deref them).
            component_id: {
                "sensor_suffix": component.get("sensor_suffix"),
                "proxy_for": component.get("proxy_for"),
                "reset_button": component.get("reset_button"),
                "remaining_is_state": component.get("remaining_is_state", False),
                "default_interval_hours": component["default_interval_hours"],
                "max_interval_hours": component["max_interval_hours"],
                "label": component["label"],
                "icon": component["icon"],
            }
            for component_id, component in MAINTENANCE_COMPONENTS.items()
        },

        # Wave 2a: "discovery" (get_maps service source + active_map) + identity
        # reconciliation. Wave 2b: dispatch.resolve_live_ids_by_slug (live name->id
        # at send) + completion.require_job_active_clear (finalize on the cleaning
        # binary, not current_room) + dispatch.global_pre_calls (max-wins GLOBAL
        # fan + mop pre-call). Wave 3: live_transition.native_transition_source
        # (native current_room live rollover, filtered to job targets).
        # OMITTED (no dock / framework defaults suffice):
        #   dock_events, post_job_wash_amendment, water_model_configs, upkeep_catalog,
        #   settings_selects, room_profiles, anomaly, live_transition.
    }

    register_adapter_config(vacuum_entity_id, config)
    _LOGGER.debug(
        "roborock_adapter: registered config for %s (adapter_id=%s, model=%s, family=%s)",
        vacuum_entity_id,
        ADAPTER_ID,
        detected_model,
        profile["family"],
    )
