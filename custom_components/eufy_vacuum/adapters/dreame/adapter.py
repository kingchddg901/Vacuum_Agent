"""Dreame adapter — assembles + registers the adapter config for one vacuum.

⚠ NOT WIRED on master. There is deliberately no ``BRAND_REGISTRARS`` row for Dreame;
that row is the release and it is gated on a RELEASED upstream ``dreame_vacuum`` build
carrying Tasshack #1707. This module is inert until such a row selects it — see
``adapters/dreame/__init__.py``. A local build adds the row in its own deploy only.

Structure mirrors ``adapters/roborock/adapter.py`` (the other brand that wraps an
upstream integration). Values are verified against the live ``vacuum.robin``
(dreame.vacuum.r2469a) entity set + the upstream ``dreame_vacuum`` service/enum
definitions, probed 2026-08-29. Capability flags come from the model profile OR-ed with
live entity presence (``detect_capabilities``), so the registered config reflects this
installation's actual HA surface.

PHASE STATE (see the scoping plan): this is the Phase 0-1 skeleton — a schema-conformant
config wired to real entities + the real segment-clean service. Items that need the live
device to finalize are marked ``# PHASE 3/4`` and carry conservative provisional values.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..entity_resolve import resolve_declared_entities
from ..registry import register_adapter_config
from . import vocabulary
from .const import ADAPTER_ID, LOW_BATTERY_THRESHOLD_PERCENT
from .entities import (
    ALL_SUFFIXES,
    DOMAIN_BINARY_SENSOR,
    DOMAIN_SELECT,
    SUFFIX_ACTIVE_MAP,
    SUFFIX_BATTERY,
    SUFFIX_CHARGING,
    SUFFIX_CLEANING_AREA,
    SUFFIX_CLEANING_HISTORY,
    SUFFIX_CLEANING_TIME,
    SUFFIX_ACTIVE_CLEANING_TARGET,
    SUFFIX_DOCK_STATUS,
    SUFFIX_ERROR_MESSAGE,
    SUFFIX_TASK_STATUS,
    build_entity_id,
)
from .maintenance_components import MAINTENANCE_COMPONENTS
from .model_catalog import profile_for_model

_LOGGER = logging.getLogger(__name__)


def _device_for_vacuum(hass: HomeAssistant, vacuum_entity_id: str):
    """Return the device-registry entry backing this vacuum, or None.

    Reads the ENTITY registry for the vacuum's device_id, then the DEVICE registry —
    the same public path Roborock uses. ``device.model`` is the identity string
    (``dreame.vacuum.r2469a``) the model catalog keys on.
    """
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(vacuum_entity_id)
    if entry is None or entry.device_id is None:
        return None
    return dr.async_get(hass).async_get(entry.device_id)


def register_dreame_adapter_for_vacuum(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    *,
    entity_overrides: dict[str, str] | None = None,
) -> None:
    """Assemble and register the Dreame adapter config for one vacuum.

    Idempotent — re-calling for the same vacuum overwrites the previous registration.
    """
    from ...core.capabilities import detect_capabilities

    vid = vacuum_entity_id

    # --- model identity (device registry — the supported public source) -------
    device = _device_for_vacuum(hass, vid)
    detected_model = device.model if device is not None else None
    profile = profile_for_model(detected_model)

    mop_settable = bool(profile.get("mop_settable", False))
    # Dreame's station is INTEGRAL (one device), not a separate dock device the way
    # Roborock's is — so there is no dock.py resolution. The station capabilities come
    # from the model profile, and detect_capabilities OR-s them with live entity presence
    # (self_wash_base_status / auto_empty_status / drying_* sensors are the live gate).
    has_station = bool(profile.get("has_station", False))
    station_washable = bool(profile.get("station_washable", has_station))
    station_dryable = bool(profile.get("station_dryable", has_station))
    station_collectable = bool(profile.get("station_collectable", has_station))

    # --- capability gating ----------------------------------------------------
    entity_candidates: dict[str, list[str]] = {
        "task_status": [build_entity_id(vid, SUFFIX_TASK_STATUS)],
        "active_cleaning_target": [build_entity_id(vid, SUFFIX_ACTIVE_CLEANING_TARGET)],
        "active_map": [build_entity_id(vid, SUFFIX_ACTIVE_MAP, DOMAIN_SELECT)],
        "cleaning_time": [build_entity_id(vid, SUFFIX_CLEANING_TIME)],
        "cleaning_area": [build_entity_id(vid, SUFFIX_CLEANING_AREA)],
        "dock_status": [build_entity_id(vid, SUFFIX_DOCK_STATUS)],
    }

    capability_hints: dict[str, bool] = {
        "supports_mop_features": profile["has_mop"],
        "supports_mop_wash": station_washable,
        "supports_mop_dry": station_dryable,
        "supports_empty_dust": station_collectable,
        "supports_path_control": profile.get("has_path_control", False),
        # Declared False in the capabilities block below too — it must ALSO be a hint,
        # because the room-payload gate reads the runtime-detected capabilities payload,
        # not the config block (the D18 lesson from Roborock). Dreame HAS edge mopping on
        # some models; left False until confirmed per-model (PHASE 3, hardware).
        "supports_edge_mopping": False,
        # Authoritative + defaults True: to DISABLE, the key must be PRESENT as False
        # (capabilities._hint_wins). No zone-clean entity is exposed; zone is a service,
        # verified in dispatch (PHASE 3), so present it False until confirmed.
        "supports_zone_clean": profile.get("supports_zone_clean", False),
    }
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=vid,
        detected_model=detected_model,
        entity_candidates=entity_candidates,
        model_family=profile["family"],
        capability_hints=capability_hints,
        entity_overrides=entity_overrides or {},
        maintenance_components=MAINTENANCE_COMPONENTS,
        # Arms the live:ENT-4 exclusivity guard so a per-run metric (_cleaned_area) is
        # not claimed by its lifetime namesake (_total_cleaned_area).
        reserved_suffixes=ALL_SUFFIXES,
    )

    # --- entity ID map --------------------------------------------------------
    entities = {
        "task_status": build_entity_id(vid, SUFFIX_TASK_STATUS),
        "active_cleaning_target": build_entity_id(vid, SUFFIX_ACTIVE_CLEANING_TARGET),
        "active_map": build_entity_id(vid, SUFFIX_ACTIVE_MAP, DOMAIN_SELECT),
        "cleaning_time": build_entity_id(vid, SUFFIX_CLEANING_TIME),
        "cleaning_area": build_entity_id(vid, SUFFIX_CLEANING_AREA),
        "battery": build_entity_id(vid, SUFFIX_BATTERY),
        "error_message": build_entity_id(vid, SUFFIX_ERROR_MESSAGE),
        "charging": build_entity_id(vid, SUFFIX_CHARGING, DOMAIN_BINARY_SENSOR),
        # station wash/dry enum — drives dock-event counting + dock-action gating.
        "dock_status": build_entity_id(vid, SUFFIX_DOCK_STATUS),
        # timestamp sensor carrying completed/cancelled — the completion discriminator
        # (PHASE 4: confirm cleaning_history.completed semantics on a real run end).
        "last_clean_end": build_entity_id(vid, SUFFIX_CLEANING_HISTORY),
    }
    entities, entity_remaps = resolve_declared_entities(
        hass, vid, entities,
        overrides=entity_overrides,
        reserved_suffixes=ALL_SUFFIXES,
    )

    config = {
        "adapter_id": ADAPTER_ID,
        "source": "code",
        "display_name": profile["display_name"],
        "brand": "Dreame",

        # sensor.<id>_cleaning_time reports MINUTES (probe: number, unit "min"), like
        # Roborock — without this the metrics listener stores minutes as seconds (60x low).
        "cleaning_time_unit": "min",

        "entities": entities,

        "vocabulary": {
            "fan_speed_options": vocabulary.FAN_SPEED_OPTIONS,
            "water_level_options": vocabulary.WATER_LEVEL_OPTIONS,
            "clean_mode_options": vocabulary.CLEAN_MODE_OPTIONS,
            "clean_intensity_options": vocabulary.CLEAN_INTENSITY_OPTIONS,
        },

        # core owns the room-profile KEYS; the adapter owns every VALUE (doc 20). The
        # catalog shape (default_profile + builtins + custom_template + defaults) mirrors
        # Roborock; empty legacy_aliases says "supports the contract, has none" (absent
        # would read as an incomplete declaration).
        "room_profiles": {
            "default_profile": "vacuum_quick",
            "builtins": vocabulary.ROOM_PROFILES,
            "custom_template": vocabulary.CUSTOM_ROOM_PROFILE,
            "normalize_defaults": vocabulary.CUSTOM_ROOM_PROFILE,
            "floor_type_water_defaults": vocabulary.FLOOR_TYPE_WATER_DEFAULTS,
            "floor_type_fan_defaults": vocabulary.FLOOR_TYPE_FAN_DEFAULTS,
            "legacy_aliases": vocabulary.LEGACY_ALIASES,
        },

        # detect_capabilities OR-ed the profile hints with live entity presence; the
        # resolved payload is what the dispatch/queue gates actually read.
        "capabilities": {
            "supports_mop_features": caps.get("supports_mop_features", profile["has_mop"]),
            "supports_water_control": mop_settable,
            "supports_mop_wash": caps.get("supports_mop_wash", station_washable),
            "supports_mop_dry": caps.get("supports_mop_dry", station_dryable),
            "supports_empty_dust": caps.get("supports_empty_dust", station_collectable),
            "supports_path_control": profile.get("has_path_control", False),
            "supports_edge_mopping": False,
            "supports_zone_clean": caps.get("supports_zone_clean", False),
            # supports_station_water is deliberately NOT declared (stays False). Dreame
            # exposes NO numeric clean-water percent — every water sensor is an ENUM
            # (clean_water_tank_status = not_available/not_installed/low_water/installed),
            # and this role is consumed as a float percent (job_metrics/run_plan). A
            # label-only display would need a separate enum role, not station_water.
        },

        "charging": {
            "low_battery_threshold_percent": LOW_BATTERY_THRESHOLD_PERCENT,
        },

        # PRIMARY room dispatch: dreame_vacuum.vacuum_clean_segment. Verified against the
        # upstream services.yaml — the room field is `segments` (NOT segment_id) and the
        # passes field is `repeats` (NOT repeat). The `dreame_room_clean` engine is
        # registered at queue/dispatch_engines.py. Per-room suction_level/water_volume
        # arrays are also accepted inline (PHASE 3: wire per-room fan/water).
        "dispatch": {
            "template": "dreame_room_clean",
            "service_domain": "dreame_vacuum",
            "service_name": "vacuum_clean_segment",
            "rooms_field": "segments",
            "clean_passes_field": "repeats",
            "passes_max": 3,
            "passes_is_global": False,
        },

        # Dreame reports native per-room progress + native rooms, so the CV/counter/anchor
        # engines are declared OFF explicitly (omission silently runs Eufy's). Room
        # attribution rides the native current_room rollover.
        "mapping": {
            "segmenter_engine": "noop_fallback",
            "segmenter_tuning": {},
            # The live-map backdrop is the upstream camera PNG (single map -> no slug).
            "live_map_image_entity_pattern": "camera.{object_id}_map",
        },

        # Map geometry + pose from the decoded camera attributes (the upstream already
        # decoded the raw map). NEW core backend 'dreame_camera_attrs' reads
        # camera.<id>_map extra_state_attributes: as_dict() segment bboxes +
        # calibration_points (3 vacuum->pixel pairs) + vacuum_position/charger_position.
        # PHASE 4a: no map_render (supports_va_render stays False; the card uses the
        # device PNG as backdrop). map_pixel_size is the rendered-PNG size used to
        # normalize projected pixels to 0..1 — left None until confirmed on the live
        # device (the reader falls back to a pixel frame + logs a diagnostic meanwhile).
        "map_state_source": {
            "backend": "dreame_camera_attrs",
            "identifier_domain": "dreame_vacuum",
            "present_requires_live_map_image": True,
            "map_pixel_size": None,
            # PHASE 4a.2 (deferred): a live_pose backend gives the FASTER robot-dot poll +
            # the stall-capture dot. The full-map result already carries robot_anchor /
            # dock_anchor (rendered like eufy's storage backend), so the dashboard map
            # shows the robot now; live_pose only speeds its refresh. Adding it is a second
            # core branch (a POSE_BACKEND_DREAME_CAMERA reader in async_get_map_live_pose)
            # — done after the map path is confirmed on the live device.
        },
        "job_segmenter": {
            "engine": "noop_job_fallback",
        },
        "room_attribution": {
            "engine": "noop_room_attribution",
            "source": "native_current_room",
            "tuning": {},
        },

        # Rooms are a per-map mapping {map_name: [{id,name,icon}]} served as a LIVE
        # ATTRIBUTE on the vacuum entity — the exact 'entity_attribute'+'per_map_mapping'
        # case the discovery schema was extended for (config_schema.py names Dreame).
        # PHASE 4: confirm the `rooms` attribute shape against the live vacuum.robin
        # (restore_state was empty at probe time).
        "discovery": {
            "source": "entity_attribute",
            "room_list_shape": "per_map_mapping",
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "rooms",
            "room_id_key": "id",
            "room_name_key": "name",
            # Opt in to the single-map anchor: a one-map Dreame leaves
            # select.<id>_selected_map `unavailable` (the upstream integration only
            # makes it available with multi-floor mapping ON), so the import would
            # otherwise refuse at "no map could be identified". With this set, a single
            # per-map key with rooms anchors on that key. The VALUE is only the opt-in
            # flag; the real anchor is the live map name ("Main").
            "implicit_map_id": "Main",
        },

        "setup": {
            "steps": ["add_vacuum", "import_active_map", "save_rooms"],
        },

        "maintenance_components": MAINTENANCE_COMPONENTS,

        # Dock wash/dry cycle observation + the three dock action buttons. dock_status
        # (sensor.<id>_self_wash_base_status) reads idle/washing/drying/... — verified
        # HA states. Button suffixes verified in the live registry: self_clean /
        # manual_drying / start_auto_empty.
        #
        # ⚠ GAP (accepted): Dreame splits station state across THREE sensors —
        # self_wash_base_status (wash+dry), auto_empty_status (dust empty), and
        # drainage_status. So last_dust_empty cannot be trigger-counted from the single
        # dock_status role (the empty BUTTON still works; only auto-counting the event is
        # lost). Not a safety issue; revisit with a second lifecycle-watched role later.
        "dock_events": {
            "enabled": True,
            "triggers": {
                "last_mop_wash": ["washing"],
                "last_dry_start": ["drying"],
            },
            "debounce_seconds": {"last_mop_wash": 60},
            "action_buttons": {
                "wash_mop": {"entity_suffixes": ["self_clean"], "token_sets": [["self", "clean"]]},
                "dry_mop": {"entity_suffixes": ["manual_drying"], "token_sets": [["manual", "drying"]]},
                "empty_dust": {"entity_suffixes": ["start_auto_empty"], "token_sets": [["start", "auto", "empty"]]},
            },
        },

        # Bookkeeping so manager.refresh_vacuum_capabilities reproduces registration's
        # detect_capabilities INPUTS instead of a reduced re-derivation. Without
        # model_family + capability_hints stored, a refresh reverts model_family to
        # "generic" (the live r2469a symptom) and drops input-only hints; without the
        # full _entity_candidates it rebuilds a one-candidate-per-role set. Mirrors
        # adapters/eufy/adapter.py. Underscore keys are unknown-key-check exempt.
        "model_family": profile["family"],
        "capability_hints": dict(capability_hints),
        "_entity_candidates": entity_candidates,
        "_entity_remaps": entity_remaps,
        "_entity_overrides": dict(entity_overrides or {}),
        "_reserved_suffixes": list(ALL_SUFFIXES),
    }

    register_adapter_config(vid, config)
    _LOGGER.debug(
        "%s: registered adapter for %s (model=%s, family=%s)",
        ADAPTER_ID, vid, detected_model, profile["family"],
    )
