"""
Eufy adapter registration for the ha_vacuum_manager framework.

Assembles the Eufy X10 Pro Omni adapter config from the constants,
vocabulary, and entity patterns defined in the other adapter modules,
and registers it with the adapter registry for each managed vacuum.

This is the reference implementation of the adapter config schema.
Every field maps directly to a measured or observed value — see the
inline source references for provenance.

Called once per managed vacuum at startup from async_setup_entry in
__init__.py via register_eufy_adapter_for_vacuum().
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from ..registry import register_adapter_config
from .const import ADAPTER_ID, STORAGE_KEY
from .constants import (
    DOCK_EVENT_MOP_WASH_DEBOUNCE_SECONDS,
    LOW_BATTERY_THRESHOLD_PERCENT,
    POST_JOB_AMENDMENT_MIN_WASH_INTERVAL_SECONDS,
    POST_JOB_AMENDMENT_TIMEOUT_SECONDS,
)
from .vocabulary import (
    HARD_SERVICE_STATES,
    DRYING_STATES,
    ACTIVE_RUN_TASK_STATES,
    HA_ACTIVE_VACUUM_STATES,
    DOCK_EVENT_TRIGGERS,
    WATER_LEVEL_ALIASES,
    WASH_FREQUENCY_MODE_ALIASES,
    NOT_ERROR_SENTINELS,
    CANCEL_SERVICE_EXCLUSION_STATES,
)
from .entities import (
    build_entity_id,
    SUFFIX_TASK_STATUS,
    SUFFIX_DOCK_STATUS,
    SUFFIX_ACTIVE_MAP,
    SUFFIX_ACTIVE_CLEANING_TARGET,
    SUFFIX_CLEANING_TIME,
    SUFFIX_CLEANING_AREA,
    SUFFIX_BATTERY,
    SUFFIX_ERROR_MESSAGE,
    SUFFIX_CHARGING,
    SUFFIX_WASH_FREQUENCY_MODE,
    SUFFIX_WASH_FREQUENCY_VALUE_TIME,
    SUFFIX_DRY_DURATION,
    SUFFIX_WATER_LEVEL,
    DOMAIN_SENSOR,
    DOMAIN_BINARY_SENSOR,
    DOMAIN_SELECT,
    DOMAIN_NUMBER,
)
from .buttons import (
    DOCK_ACTION_CANDIDATES,
    DOCK_ACTION_TOKENS,
    RESET_CANDIDATES,
    RESET_TOKENS,
)
from .maintenance_components import MAINTENANCE_COMPONENTS
from .model_catalog import detect_model_family as _detect_model_family
from .upkeep_catalog import (
    UPKEEP_GUIDE_FAMILY_NAMES,
    UPKEEP_MODEL_GUIDE_FAMILIES,
    UPKEEP_MODEL_NAMES,
)
from .upkeep_guides import UPKEEP_GUIDE_LIBRARY
from .water_config import WATER_MODEL_CONFIGS
from ...profiles.room_profiles import (
    BUILT_IN_ROOM_PROFILES,
    DEFAULT_CUSTOM_ROOM_PROFILE,
    DEFAULT_ROOM_PROFILE_NAME,
    FLOOR_TYPE_FAN_DEFAULTS,
    FLOOR_TYPE_WATER_DEFAULTS,
    LEGACY_PROFILE_ALIASES,
)

_LOGGER = logging.getLogger(__name__)


def _strip_button_suffix(suffix: str) -> str:
    """Normalize a buttons.py candidate suffix to the framework convention.

    buttons.py suffixes are written to append to ``button.{object_id}`` and so
    carry a leading underscore (``"_wash_mop"``). The adapter config / resolver
    convention appends to ``button.{object_id}_``, so the leading underscore is
    dropped here.
    """
    return suffix[1:] if suffix.startswith("_") else suffix


def _build_button_block(
    key: str,
    candidates: dict[str, list[str]],
    tokens: dict[str, list[list[str]]],
) -> dict | None:
    """Build one ``{entity_suffixes, token_sets}`` block from buttons.py data.

    Returns ``None`` when the key is absent from both maps (e.g. a component
    with no reset button), so callers can store ``None`` for "no button".
    """
    if key not in candidates and key not in tokens:
        return None
    return {
        "entity_suffixes": [_strip_button_suffix(s) for s in candidates.get(key, [])],
        "token_sets": [list(t) for t in tokens.get(key, [])],
    }


def _build_button_blocks(
    candidates: dict[str, list[str]],
    tokens: dict[str, list[list[str]]],
) -> dict[str, dict]:
    """Build the full ``{action: block}`` map from buttons.py candidate/token data."""
    return {
        key: _build_button_block(key, candidates, tokens)
        for key in (set(candidates) | set(tokens))
    }


def register_eufy_adapter_for_vacuum(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> None:
    """Assemble and register the Eufy adapter config for one vacuum.

    Called once per managed vacuum at startup. Idempotent — re-calling
    for the same vacuum overwrites the previous registration.

    The capabilities dict is populated from entity presence detection
    (detect_capabilities) rather than hardcoded flags — this ensures
    the registered config reflects the actual HA entity surface for
    this specific installation, not just the model spec.
    """
    from ...core.capabilities import detect_capabilities

    vacuum_state = hass.states.get(vacuum_entity_id)
    detected_model = None
    if vacuum_state is not None:
        detected_model = vacuum_state.attributes.get("detected_model")

    # Compute model family using the Eufy model catalog.
    model_family = _detect_model_family(detected_model)

    # Build entity candidate lists from Eufy entity suffix conventions.
    # Each list is tried in order by detect_capabilities — first entity
    # present in the HA state machine or registry wins.
    object_id = vacuum_entity_id.split(".", 1)[1]
    entity_candidates: dict[str, list[str]] = {
        "task_status":            [build_entity_id(vacuum_entity_id, SUFFIX_TASK_STATUS)],
        "dock_status":            [build_entity_id(vacuum_entity_id, SUFFIX_DOCK_STATUS)],
        "active_map":             [build_entity_id(vacuum_entity_id, SUFFIX_ACTIVE_MAP)],
        "active_cleaning_target": [build_entity_id(vacuum_entity_id, SUFFIX_ACTIVE_CLEANING_TARGET)],
        "cleaning_time":          [build_entity_id(vacuum_entity_id, SUFFIX_CLEANING_TIME)],
        "cleaning_area":          [build_entity_id(vacuum_entity_id, SUFFIX_CLEANING_AREA)],
        "water_level":            [build_entity_id(vacuum_entity_id, SUFFIX_WATER_LEVEL)],
        # work_mode and position suffixes vary between robovac_mqtt versions;
        # list the known patterns so the prober finds whichever is present.
        "work_mode":              [f"sensor.{object_id}_work_mode"],
        "robot_position_x":       [f"sensor.{object_id}_robot_position_x_raw"],
        "robot_position_y":       [f"sensor.{object_id}_robot_position_y_raw"],
        # Dock action button candidates — robovac_mqtt exposes two naming
        # variants depending on firmware/integration version.
        "wash_mop_button":   [f"button.{object_id}_wash_mop",   f"button.{object_id}_mop_wash"],
        "dry_mop_button":    [f"button.{object_id}_dry_mop",    f"button.{object_id}_mop_dry"],
        "empty_dust_button": [f"button.{object_id}_empty_dust", f"button.{object_id}_empty_dust_bin"],
        "cleaning_intensity": [f"select.{object_id}_cleaning_intensity"],
    }

    # Model-based capability hints — confirmed hardware support regardless
    # of whether the entity happens to be present right now. Entity presence
    # detection in detect_capabilities() is the fallback for unrecognised
    # model codes that still expose the relevant entities.
    capability_hints: dict[str, bool] = {
        "supports_mop_features": model_family in {"x10", "x8", "l60", "l50"},
        "supports_mop_wash":     model_family in {"x10", "x8"},
        "supports_mop_dry":      model_family in {"x10", "x8"},
        "supports_empty_dust":   model_family in {"x10", "x8", "l60", "l50"},
        "supports_path_control": model_family in {"x10", "x8"},
    }

    caps = detect_capabilities(
        hass,
        vacuum_entity_id=vacuum_entity_id,
        detected_model=detected_model,
        entity_candidates=entity_candidates,
        model_family=model_family,
        capability_hints=capability_hints,
        maintenance_components=MAINTENANCE_COMPONENTS,
    )

    # Build entity ID map from adapter entity patterns.
    # Each entity ID is constructed using build_entity_id() which applies
    # the object_id_suffix naming strategy for Eufy/robovac_mqtt.
    entities = {
        "task_status": build_entity_id(vacuum_entity_id, SUFFIX_TASK_STATUS),
        "dock_status": build_entity_id(vacuum_entity_id, SUFFIX_DOCK_STATUS),
        "active_map": build_entity_id(vacuum_entity_id, SUFFIX_ACTIVE_MAP),
        "active_cleaning_target": build_entity_id(
            vacuum_entity_id, SUFFIX_ACTIVE_CLEANING_TARGET
        ),
        "cleaning_time": build_entity_id(vacuum_entity_id, SUFFIX_CLEANING_TIME),
        "cleaning_area": build_entity_id(vacuum_entity_id, SUFFIX_CLEANING_AREA),
        "battery": build_entity_id(vacuum_entity_id, SUFFIX_BATTERY),
        "error_message": build_entity_id(vacuum_entity_id, SUFFIX_ERROR_MESSAGE),
        "charging": build_entity_id(
            vacuum_entity_id, SUFFIX_CHARGING, DOMAIN_BINARY_SENSOR
        ),
        "wash_frequency_mode": build_entity_id(
            vacuum_entity_id, SUFFIX_WASH_FREQUENCY_MODE, DOMAIN_SELECT
        ),
        "wash_frequency_value_time": build_entity_id(
            vacuum_entity_id, SUFFIX_WASH_FREQUENCY_VALUE_TIME, DOMAIN_NUMBER
        ),
        "dry_duration": build_entity_id(
            vacuum_entity_id, SUFFIX_DRY_DURATION, DOMAIN_SELECT
        ),
        "water_level": build_entity_id(vacuum_entity_id, SUFFIX_WATER_LEVEL),
        # Position entities sourced from capability detection — these use
        # robovac_mqtt-specific suffixes that are already resolved by
        # detect_capabilities().
        "robot_position_x": caps.get("entities", {}).get("robot_position_x"),
        "robot_position_y": caps.get("entities", {}).get("robot_position_y"),
        "work_mode": caps.get("entities", {}).get("work_mode"),
        "cleaning_intensity": caps.get("entities", {}).get("cleaning_intensity"),
    }

    # Remove None values — absent entities degrade gracefully per the schema.
    entities = {k: v for k, v in entities.items() if v is not None}

    config = {
        "adapter_id": ADAPTER_ID,
        "source": "code",
        "display_name": "Eufy X10 Pro Omni",
        # Short brand/app name the card uses in copy ("Clean from the Eufy
        # app"); the card falls back to generic phrasing when absent.
        "brand": "Eufy",

        "entities": entities,

        # External-run capture: the global select entities that reflect the
        # CURRENT room's per-room settings while the app runs a job. We dispatch
        # these for internal jobs (never reading them back), but for an app-started
        # EXTERNAL run they are our only window into what was set per room. The
        # capture layer snapshots them per tick; value_map normalizes raw firmware
        # strings to the canonical room-setting vocabulary (clean_mode only — fan/
        # water/intensity are stored raw and normalized downstream). edge_mopping
        # has no readback entity, so it is absent here (the user supplies it in
        # review). Entries whose entity_id is None are skipped by the capture.
        "settings_selects": {
            "clean_mode": {
                "entity_id": f"select.{object_id}_cleaning_mode",
                "value_map": {
                    "vacuum and mop": "vacuum_mop",
                    "vacuum & mop": "vacuum_mop",
                    "vacuum": "vacuum",
                    "mop": "mop",
                },
            },
            "fan_speed":       {"entity_id": f"select.{object_id}_suction_level",      "value_map": None},
            "water_level":     {"entity_id": f"select.{object_id}_water_level",        "value_map": None},
            "clean_intensity": {"entity_id": f"select.{object_id}_cleaning_intensity", "value_map": None},
            "mop_intensity":   {"entity_id": f"select.{object_id}_mop_intensity",      "value_map": None},
        },

        # task_status values that mean "docked mid-run, will resume" (mop prewash,
        # dust empty, recharge-resume). The external-run finalizer HOLDS the run open
        # while task_status is one of these, instead of closing it at the dock — so a
        # vacuum->mop run stays one multi-segment record. Source strings:
        # robovac_mqtt/api/parser.py::_map_task_status — VERIFIED against robovac_mqtt
        # 1.10.0 (jeppesens/eufy-clean); re-check this list when that integration
        # updates. An unrecognized value just falls back to the time-based grace, so a
        # string drift DEGRADES (loses the long-wash hold) rather than crashing.
        "external_mid_run_statuses": [
            "Returning to Wash",
            "Washing Mop",
            "Returning to Empty",
            "Emptying Dust",
            "Returning to Charge",
            "Charging (Resume)",
        ],

        "vocabulary": {
            # Dock/task states — sourced from vocabulary.py
            # See prompts 3 and 4 for extraction provenance.
            "hard_service_states": sorted(HARD_SERVICE_STATES),
            "drying_states": sorted(DRYING_STATES),
            "active_run_task_states": sorted(ACTIVE_RUN_TASK_STATES),
            "not_error_sentinels": sorted(NOT_ERROR_SENTINELS),
            # Raw (non-normalized) block states — sourced from queue_engine.py
            # audit. These are title-cased firmware strings, not normalized.
            "blocked_work_mode_states": ["Smart Follow", "Auto", "Room"],
            "blocked_task_status_states": ["Cleaning", "Returning", "Washing Mop"],
            "blocked_dock_status_states": ["Washing", "Recycling waste water"],
            # Cancel detection exclusions — normalized task_status strings that
            # explain a short early return as a service event, not a manual cancel.
            # Sourced from vocabulary.py CANCEL_SERVICE_EXCLUSION_STATES.
            "cancel_service_exclusion_states": sorted(CANCEL_SERVICE_EXCLUSION_STATES),
            # Normalized task_status transition strings for cancel detection.
            # Eufy normalizes to the HA-standard activity terms.
            "cancel_detection_states": {
                "active": "cleaning",
                "returning": "returning",
                "paused": "paused",
            },
            # Alias maps — normalize brand-specific display strings to canonical keys.
            # Sourced from vocabulary.py WATER_LEVEL_ALIASES / WASH_FREQUENCY_MODE_ALIASES.
            "water_level_aliases": dict(WATER_LEVEL_ALIASES),
            "wash_frequency_mode_aliases": dict(WASH_FREQUENCY_MODE_ALIASES),

            # User-facing dropdown option lists. The card reads these to
            # populate clean_mode / fan_speed / water_level / clean_intensity
            # selectors in the room editor and rule editor. The framework
            # never reads them — purely a card-facing vocabulary surface.
            # See docs/dev/adapter-config-reference.md §6.
            "clean_mode_options": [
                {"value": "vacuum",     "label": "Vacuum"       },
                {"value": "mop",        "label": "Mop"          },
                {"value": "vacuum_mop", "label": "Vacuum & Mop" },
            ],
            "fan_speed_options": [
                {"value": "Quiet",    "label": "Quiet"    },
                {"value": "Standard", "label": "Standard" },
                {"value": "Boost",    "label": "Boost"    },
                {"value": "Max",      "label": "Max"      },
            ],
            "water_level_options": [
                {"value": "Off",    "label": "Off"    },
                {"value": "Low",    "label": "Low"    },
                {"value": "Medium", "label": "Medium" },
                {"value": "High",   "label": "High"   },
            ],
            "clean_intensity_options": [
                {"value": "Quick",  "label": "Quick"  },
                {"value": "Narrow", "label": "Narrow" },
                {"value": "Deep",   "label": "Deep"   },
            ],
        },

        "completion": {
            # Primary completion signal — task_status must equal this value
            # (after .strip().lower()) for the framework to consider the job done.
            "task_status_value": "completed",
            # Secondary completion signal — active_cleaning_target must be in
            # this sentinel set simultaneously with task_status_value.
            "secondary_clear_entity": "active_cleaning_target",
            "secondary_clear_sentinels": [
                "", "unknown", "unavailable", "none", "null"
            ],
        },

        "charging": {
            # Charging state is read from the dedicated entities.charging
            # binary sensor (robovac_mqtt) by core/charging.py — no config
            # needed here for that. This block only configures the
            # low-battery mid-job return classifier (consumed by core/charging.py).
            "low_battery_return_task_status": "returning to charge",
            "low_battery_threshold_percent": LOW_BATTERY_THRESHOLD_PERCENT,
        },

        "error_tracking": {
            # Secondary error channel — task_status flips to this value
            # on the same upstream condition as vacuum.state == "error".
            # Empirical observation (recorder trace 2026-05-10): stuck/trapped
            # events flip both channels while error_message stays empty.
            "task_status_error_value": "error",
            # Grace window — how long to wait for error_message after the
            # secondary channel fires before finalizing as unknown error.
            # Some firmware emits state DPS before message DPS.
            "grace_window_seconds": 5,
            # Attribute keys checked when reading error code.
            # Tried in order — first non-zero int wins.
            "error_code_attribute_names": ["error_code", "code", "errorCode"],
            "unknown_error_message": "Unknown error during run",
        },

        "dock_events": {
            # Dock event recording enabled — X10 Pro Omni dock supports
            # wash, empty, and dry cycles observable via dock_status sensor.
            "enabled": True,
            # Trigger mapping — sourced from vocabulary.py DOCK_EVENT_TRIGGERS.
            # Keys are framework event type names; values are normalized
            # dock_status strings that trigger each event.
            "triggers": {
                event_type: sorted(trigger_states)
                for event_type, trigger_states in DOCK_EVENT_TRIGGERS.items()
            },
            # Noisy dock states flip 1-2x within ~30s per actual cycle; the
            # cooldown collapses them into one counted event. Also gates the
            # active-job mop-wash observation. See constants.py.
            "debounce_seconds": {
                "last_mop_wash": DOCK_EVENT_MOP_WASH_DEBOUNCE_SECONDS,
            },
            # Upstream button resolution per dock action — sourced from
            # buttons.py. entity_suffixes are tried first (appended to
            # 'button.{object_id}_'); token_sets are all-tokens-must-match
            # registry fallbacks for firmware naming drift.
            "action_buttons": _build_button_blocks(
                DOCK_ACTION_CANDIDATES, DOCK_ACTION_TOKENS
            ),
        },

        "post_job_wash_amendment": {
            # The X10 Pro Omni dock washes the mop ~2s after docking from
            # a mop job. The amendment watcher patches water actuals after
            # finalization. See core/water_amendment.py.
            "enabled": True,
            # States that increment the post-job wash count.
            "trigger_states": sorted({"washing", "washing mop"}),
            # State that signals the wash cycle is complete.
            "commit_state": "drying",
            # Debounce — prevents double-counting multi-state wash sequence.
            # The X10 wash cycle averages ~46s; 60s provides buffer.
            # See adapters/eufy/constants.py MOP_WASH_DEBOUNCE_SECONDS.
            "debounce_seconds": POST_JOB_AMENDMENT_MIN_WASH_INTERVAL_SECONDS,
            # Timeout — safety valve if drying never fires.
            "timeout_seconds": POST_JOB_AMENDMENT_TIMEOUT_SECONDS,
        },

        "discovery": {
            # Room segments are exposed as the 'segments' attribute on the
            # vacuum entity by robovac_mqtt. Each segment is a dict with
            # 'id' (int) and 'name' (str) keys.
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
            # Auto-discovery cadence. The framework runs discovery on each
            # listed event plus once every interval as a safety net.
            "auto_refresh_on": [
                "vacuum_docked",
                "active_map_changed",
                "config_entry_reload",
            ],
            "auto_refresh_interval_seconds": 21600,  # 6 hours
            # Drift confirmation windows — see core/setup/drift.py.
            # Eufy's robovac_mqtt is generally stable; N=3 catches firmware
            # hiccups without delaying genuine removals by more than a day
            # at typical clean cadence.
            "removal_confirmation_passes": 3,
            "new_room_confirmation_passes": 1,
        },

        "setup": {
            # Eufy needs an explicit import_active_map step because
            # robovac_mqtt only surfaces one map at a time and requires a
            # fetch operation. Brands with always-on map exposure should
            # drop "import_active_map" from this list.
            "steps": [
                "add_vacuum",
                "import_active_map",
                "save_rooms",
            ],
        },

        "dispatch": {
            # Eufy room_clean payload template.
            # Service: vacuum.send_command with command=room_clean.
            # Payload: {map_id: int, rooms: [{id, clean_times, ...}]}
            "template": "eufy_room_clean",
            "service_domain": "vacuum",
            "service_name": "send_command",
            "command": "room_clean",
            # Ad-hoc free-form zone clean (smcneece eufy-clean fork). Same
            # vacuum.send_command service, command=zone_clean, bare payload
            # {zones:[[x0,y0,x1,y1],...], clean_times}. manager.dispatch_zone_clean
            # reads this verb; absence => zone cleaning unsupported for the brand.
            "zone_command": "zone_clean",
            "map_id_field": "map_id",
            "map_id_type": "int",
            "room_id_field": "id",
            "clean_passes_field": "clean_times",
            "rooms_field": "rooms",
            # Per-room field rename + value vocabulary. Eufy uses the
            # canonical framework names and values verbatim, so every
            # entry is an identity rename with no value_map. This block
            # is technically optional for Eufy (defaults match), but it
            # serves as the reference example a port to another brand
            # copies from. See docs/dev/adapter-config-reference.md.
            "room_fields": {
                "fan_speed":       {"field_name": "fan_speed",       "value_map": None},
                "clean_mode":      {"field_name": "clean_mode",      "value_map": None},
                "clean_intensity": {"field_name": "clean_intensity", "value_map": None},
                "water_level":     {"field_name": "water_level",     "value_map": None},
                "edge_mopping":    {"field_name": "edge_mopping",    "value_map": None},
                "path_type":       {"field_name": "path_type",       "value_map": None},
            },
        },

        "mapping": {
            # Selects the pluggable map segmenter engine. The framework
            # looks the name up in mapping.segmenter_engines._SEGMENTER_ENGINES;
            # unknown names degrade to noop_fallback with a warning.
            #
            # eufy_cv_v1 wraps the Pillow + NumPy + SciPy pipeline in
            # adapters/eufy/segmentor.py. Adapters without a usable image
            # asset should declare "noop_fallback" here so the card stops
            # trying to render polygonal overlays while the trace tracker
            # keeps working off vacuum-space coordinates.
            "segmenter_engine": "eufy_cv_v1",
            "segmenter_tuning": {
                # All keys map to detect_room_segments() kwargs. The
                # engine's validate_tuning() rejects unknown keys at
                # registration time.
                "min_area_pixels": 1200,
                # simplify_epsilon: None means "no polygon simplification"
                # (default from detect_room_segments). Set a small positive
                # float (e.g. 2.5) to merge near-collinear vertices.
                "simplify_epsilon": None,
                # expected_room_count: None lets the engine infer; set an
                # int to bias the candidate-scoring pass toward that count.
                "expected_room_count": None,
            },
            # Best-effort live-map backdrop for installs running the eufy-clean fork
            # (smcneece) that exposes a camera.<device>_map live-map entity. Core fills
            # {object_id} from the vacuum entity's object_id (the Eufy vacuum and that
            # camera usually share the device slug) and EXISTENCE-CHECKS the result, so
            # plain eufy-clean / non-fork installs resolve to None and are unaffected.
            # If the vacuum entity was renamed and this guess misses, the per-vacuum
            # override set from the Setup tab wins (see manager.get_dashboard_snapshot).
            "live_map_image_entity_pattern": "camera.{object_id}_map",
        },

        "job_segmenter": {
            # Selects the pluggable JOB (run) segmenter engine — the brand-specific
            # detection of per-room boundaries from a run's progress signal. The
            # framework looks the name up in
            # learning.job_segmenter_engines._JOB_SEGMENTER_ENGINES; an absent or
            # unknown engine falls back to eufy_counter_v1 (NOT noop), so live rollover
            # + external ingest + learned history keep working. eufy_counter_v1 reads
            # the cleaning_time / cleaning_area counters (no geometry; coordinates
            # drift). `tuning` is the SINGLE source of the gap/area/cadence thresholds —
            # live rollover, external ingest, AND learned history all read it. A brand
            # with native room-transition telemetry registers its own engine here.
            "engine": "eufy_counter_v1",
            "tuning": {
                "gap_delayed_s": 35.0,
                "gap_transit_s": 60.0,
                "gap_plateau_s": 90.0,
                "area_jump_m2": 2.0,
                "cadence_s": 30.0,
            },
        },

        "live_transition": {
            # LIVE current-room rollover orchestration. The gap/area/cadence thresholds
            # now live in job_segmenter.tuning (the single source); this block carries
            # only the live-specific knobs: the kill-switch, which boundary kinds advance
            # the live queue (the "transit" band is the only behavior change vs the
            # legacy path), and the reserved native_transition_source. See
            # ActiveJobTracker._live_transition_config.
            "enabled": True,
            "rollover_kinds": ["wash_plateau", "transit", "area_jump"],
            "native_transition_source": False,
        },

        "anomaly": {
            # Live anomaly tuning. Defaults match the manager fallbacks, so Eufy is
            # unchanged. running_long is the soft tier (>=1.5x estimate) below the 2x
            # stall; both ratios are adapter-tunable.
            "running_long_ratio": 1.5,
            "stall_ratio": 2.0,
        },

        "room_profiles": {
            # Default room-profile vocabulary. The in-code catalog
            # (profiles/room_profiles.py) is the framework DEFAULT + the
            # _PROTECTED_ROOM_PROFILE_NAMES source; Eufy declares it here BY REFERENCE
            # (no duplication, byte-identical) so room resolution is adapter-sourced and
            # a future brand can inline its own catalog / vocabulary. The framework's
            # resolve_profile_catalog() merges this block over the in-code constants per
            # key, so any subset can be overridden; an absent block uses the defaults.
            "default_profile": DEFAULT_ROOM_PROFILE_NAME,
            "builtins": BUILT_IN_ROOM_PROFILES,
            "custom_template": DEFAULT_CUSTOM_ROOM_PROFILE,
            "legacy_aliases": LEGACY_PROFILE_ALIASES,
            "floor_type_water_defaults": FLOOR_TYPE_WATER_DEFAULTS,
            "floor_type_fan_defaults": FLOOR_TYPE_FAN_DEFAULTS,
            "normalize_defaults": DEFAULT_CUSTOM_ROOM_PROFILE,
        },

        "capabilities": {
            # Sourced from detect_capabilities() above — reflects actual
            # HA entity surface for this installation rather than model spec.
            "supports_mop_features": caps.get("supports_mop_features", False),
            "supports_water_control": caps.get("supports_water_control", False),
            "supports_path_control": caps.get("supports_path_control", False),
            "supports_edge_mopping": caps.get("supports_edge_mopping", True),
            "supports_mop_wash": caps.get("supports_mop_wash", False),
            "supports_mop_dry": caps.get("supports_mop_dry", False),
            "supports_empty_dust": caps.get("supports_empty_dust", False),
            "supports_robot_position": caps.get("supports_robot_position", False),
            "supports_station_water": caps.get("supports_station_water", False),
            # Ad-hoc free-form zone cleaning (draw a box on the live map, clean it).
            # No runtime probe distinguishes the smcneece fork (which accepts
            # zone_clean — see dispatch.zone_command) from stock eufy-clean, so this
            # is True for Eufy and the card gates the zone-draw control on a RESOLVED
            # live-map image: the fork that adds zone_clean is the same one exposing
            # camera.<device>_map, so stock installs (no live map) never see it.
            "supports_zone_clean": True,
            # Eufy firmware re-bases the raw coordinate frame every session, so
            # cross-session bounds geometry is unusable for room detection. The
            # room detector only trusts position/bounds when this is True (core
            # stays neutral); a brand with a stable localization lock can set True.
            "position_lock_reliable": False,
            # Eufy has no "vacuum-then-mop" whole-home mode, so a room is cleaned
            # at most once per job → external-run room picks are unique per job
            # (the card hard-blocks an already-picked room). A brand with a
            # vac-then-mop pass visits each room twice → set False there.
            "rooms_unique_per_job": True,
        },

        "maintenance_components": {
            # Sourced from adapters/eufy/maintenance_components.py.
            # Each entry defines the firmware replacement counter sensor,
            # display metadata, and interval configuration.
            component_id: {
                "sensor_suffix": component.get("sensor_suffix"),
                "proxy_for": component.get("proxy_for"),
                # Reset-button resolution sourced from buttons.py (single source
                # for all button discovery). None when the component has no
                # reset button.
                "reset_button": _build_button_block(
                    component_id, RESET_CANDIDATES, RESET_TOKENS
                ),
                "default_interval_hours": component["default_interval_hours"],
                "max_interval_hours": component["max_interval_hours"],
                "label": component["label"],
                "icon": component["icon"],
            }
            for component_id, component in MAINTENANCE_COMPONENTS.items()
        },

        "upkeep_catalog": {
            # Sourced from adapters/eufy/upkeep_catalog.py and upkeep_guides.py.
            # model_names, model_guide_families, and guide_family_names map
            # device registry model codes to guide family keys and display names.
            # guide_library maps guide family keys to per-component upkeep data.
            "model_names": UPKEEP_MODEL_NAMES,
            "model_guide_families": UPKEEP_MODEL_GUIDE_FAMILIES,
            "guide_family_names": UPKEEP_GUIDE_FAMILY_NAMES,
            "guide_library": UPKEEP_GUIDE_LIBRARY,
        },

        "water_model_configs": WATER_MODEL_CONFIGS,
    }

    register_adapter_config(vacuum_entity_id, config)
    _LOGGER.debug(
        "eufy_adapter: registered config for %s (adapter_id=%s)",
        vacuum_entity_id,
        ADAPTER_ID,
    )
