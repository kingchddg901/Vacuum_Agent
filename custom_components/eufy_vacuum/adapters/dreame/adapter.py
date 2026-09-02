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
    SUFFIX_CLEAN_WATER_TANK_STATUS,
    SUFFIX_DIRTY_WATER_TANK_STATUS,
    SUFFIX_DOCK_STATUS,
    SUFFIX_ERROR_MESSAGE,
    SUFFIX_TASK_STATUS,
    SUFFIX_TASK_TYPE,
    build_entity_id,
)
from .maintenance_components import MAINTENANCE_COMPONENTS
from .dreame_upkeep_guides import DREAME_UPKEEP_GUIDE_LIBRARY
from .upkeep_catalog import (
    DREAME_GUIDE_FAMILY_NAMES,
    DREAME_MODEL_GUIDE_FAMILIES,
    DREAME_MODEL_NAMES,
)
from .upkeep_guides_i18n import DREAME_UPKEEP_GUIDE_TRANSLATIONS
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
        "task_type": [build_entity_id(vid, SUFFIX_TASK_TYPE)],
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
        # Cruise-to-point button gate (frontend supports_goto). Tied to path control: the
        # `goto` dispatch block below IS a path-control command, so a model without path
        # control gets no button. Presentation-only; dispatch gates on supports_path_control.
        # This hint feeds detect_capabilities → the `capabilities` config block's
        # supports_goto → manager's snapshot copy → the card (all four must carry it).
        "supports_goto": profile.get("has_path_control", False),
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
        # The completion SECONDARY-clear signal (custom -> `unavailable` at end-of-run).
        "task_type": build_entity_id(vid, SUFFIX_TASK_TYPE),
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
        # Tank presence/level ENUMS. These satisfy the enum tank-status display, NOT the
        # numeric `station_water` role (see the capabilities note: Dreame publishes no water
        # FILL percent on any model). Declaring them is safe on a model that lacks them —
        # resolve_declared_entities drops a key whose entity does not exist, and the
        # maintenance snapshot then omits the field, so the card simply shows nothing.
        "clean_water_tank_status": build_entity_id(vid, SUFFIX_CLEAN_WATER_TANK_STATUS),
        "dirty_water_tank_status": build_entity_id(vid, SUFFIX_DIRTY_WATER_TANK_STATUS),
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
            # RANGE, not options: this brand's water is the fine 1..32 wetness scale,
            # so the card branches to a slider and water_level stores a numeric string.
            "water_level_range": vocabulary.WATER_LEVEL_RANGE,
            "clean_mode_options": vocabulary.CLEAN_MODE_OPTIONS,
            "clean_intensity_options": vocabulary.CLEAN_INTENSITY_OPTIONS,
            # Values of sensor.<obj>_error that mean NO fault. The error tracker fires on
            # ANY non-sentinel observation (not just transitions), so WITHOUT "no_error"
            # here the clear-to-"no_error" reads as a fresh error and latches a PHANTOM
            # fault every time a real error ends (observed live: one brush jam recorded as
            # TWO faults — the rise + the clear). Declaring the set REPLACES the generic
            # default, so the HA non-values are re-included. "no_error" is dreame_vacuum's
            # ERROR_NO_ERROR (dreame/const.py); every other ERROR_* slug is a real fault.
            "not_error_sentinels": ["no_error", "", "unknown", "unavailable"],
            # Task-status values that mean a clean is IN PROGRESS — read by the pose
            # sampler's parked check so an app-started (external) run's dock-sitting ticks
            # are not attributed to a room. (Dispatched runs already sampled correctly via
            # the no-pose fallback; this sharpens the EXTERNAL path.)
            "active_run_task_states": sorted(vocabulary.ACTIVE_RUN_TASK_STATES),
        },
        # An external (app-started) run must not finalize while the robot is docked for a
        # station cycle (mop wash / mop change / mid-run docking) — it will resume. These
        # task_status values hold the grace-finalize open. Eufy's "Washing Mop" analogue.
        "external_mid_run_statuses": sorted(vocabulary.EXTERNAL_MID_RUN_STATUSES),
        "external_run": {
            # active_segments (camera.<obj>_map attr) is the DEVICE'S OWN queue snapshot for an
            # app-started run — which rooms were selected + the TAP ORDER — persisted post-dock
            # (proven live: tap [3,1,7] came back exactly, executed in that order). Ground TRUTH
            # for the external record's queue + not_reached, vs. inferring the cleaned set from
            # swept area. Read at finalize (it is briefly None at run start). Dreame-only for now
            # (Eufy/Roborock expose no equivalent snapshot).
            "queue_from_active_segments": True,
        },
        "error_tracking": {
            # Dreame reports the live fault on sensor.<obj>_error whose STATE is the fault SLUG
            # itself (dreame_vacuum's ERROR_* value, e.g. "brush"), not a numeric code on an
            # attribute — so the code->label table can't name it. fault_label_from_message routes
            # the slug straight to fault.<brand>.<slug> (fault.dreame.brush); the strings are the
            # locale packs' fault.dreame.* keys, HARVESTED from dreame_vacuum's own 40-language
            # translations (MIT, Copyright (c) 2022 Tasshack — see ATTRIBUTIONS.md).
            "fault_label_from_message": True,
            # Dreame's faults are component-side (brush / wheel / sensor / dock), so "robot" is a
            # more honest source than "unknown" when the code-based source table (built for
            # numeric codes) can't place a slug fault.
            "default_error_source": "robot",
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
        # REPLICA RNQ433CB — every card-facing flag here is copied by hand into the
        # dashboard snapshot at core/manager.py; add a flag here AND there or the card
        # never sees it (silent, all-green). See docs/dev/00c-replicas.md.
        "capabilities": {
            "supports_mop_features": caps.get("supports_mop_features", profile["has_mop"]),
            "supports_water_control": mop_settable,
            "supports_mop_wash": caps.get("supports_mop_wash", station_washable),
            "supports_mop_dry": caps.get("supports_mop_dry", station_dryable),
            "supports_empty_dust": caps.get("supports_empty_dust", station_collectable),
            # Go-to (cruise-to-a-point) via dreame_vacuum.vacuum_goto — the `goto` block
            # below declares the service; enabled by default (standard on novel-protocol
            # Dreames), a model without it overrides has_path_control=False in its profile.
            "supports_path_control": profile.get("has_path_control", True),
            "supports_edge_mopping": False,
            "supports_zone_clean": caps.get("supports_zone_clean", False),
            # dreame_vacuum.vacuum_clean_zone accepts at most 10 zones per call (confirmed
            # on robin 2026-08-31). Declared so the card's draw + the dispatch count-cap
            # stop at the real limit rather than the framework default.
            "zone_max": 10,
            # Cruise-to-point button gate (snapshot supports_goto → card). The `goto` block
            # below is a path-control command, so this tracks supports_path_control. Copied
            # here AND forwarded in manager.py's snapshot — the two move together (a config
            # flag the snapshot omits never reaches the card).
            "supports_goto": caps.get("supports_goto", False),
            # Dreame cleans rooms in the DISPATCHED queue order — PROVEN 2026-08-30 on
            # robin: active_segments carried the tap order [3,1,7] and the robot executed
            # Kitchen->Entryway->Dining in exactly that order (FINDINGS-dreame-external-
            # attribution). Enables the phase-run per-room segmentation gate (job_segmenter
            # below), plus the running_long band and skipped_room_ids in active_job.
            "honors_clean_order": True,
            # supports_station_water is deliberately NOT declared (stays False). Dreame
            # exposes NO numeric clean-water percent — every water sensor is an ENUM
            # (clean_water_tank_status = not_available/not_installed/low_water/installed),
            # and this role is consumed as a float percent (job_metrics/run_plan). A
            # label-only display would need a separate enum role, not station_water.
        },

        "charging": {
            "low_battery_threshold_percent": LOW_BATTERY_THRESHOLD_PERCENT,
        },

        # Auto-finalization gate. Primary END signal: task_status -> "completed" (fires
        # for a finish AND a cancel; the finish/cancel split is the cleaning_history
        # discriminator — a follow-up). SECONDARY-clear signal: task_type, NOT the
        # default active_cleaning_target — Dreame's current_room reverts to the DOCK
        # ROOM at end-of-run (never a sentinel), while task_type clears
        # custom -> `unavailable` at the SAME instant task_status -> completed
        # (verified on-device 2026-08-29 from the recorder timeline). No job_active
        # binary, so require_job_active_clear does not apply.
        "completion": {
            "task_status_value": "completed",
            "secondary_clear_entity": "task_type",
            "secondary_clear_sentinels": ["", "unknown", "unavailable", "none", "null"],
        },

        # PRIMARY room dispatch: dreame_vacuum.vacuum_clean_segment. Verified against the
        # upstream services.yaml — the room field is `segments` (NOT segment_id). The
        # `dreame_room_clean` engine is registered at queue/dispatch_engines.py.
        #
        # ⚠ TWO-CALL DISPATCH. The per-room settings do NOT ride vacuum_clean_segment —
        # its suction/water/repeats params are DECORATIVE (the device uses its saved
        # custom-cleaning store; settled on hardware 2026-08-10, docstring at
        # dreame/device.py:6931). So the clean call goes BARE and the real per-room
        # control is a separate `settings_write` bulk call that runs WHILE PARKED just
        # before it (dispatch/manager.py::_run_settings_write).
        # Go-to: cruise the robot to one tapped point. dreame_vacuum.vacuum_goto takes x/y
        # in the DEVICE (vacuum-mm) frame directly (upstream services.yaml: fields x, y);
        # dispatch/manager.py::dispatch_goto converts the card's normalized tap to mm via the
        # live map's affine (offset-aware, matching the render alignment) and sends
        # {entity_id, x, y}. Gated by supports_path_control (declared above).
        "goto": {
            "service_domain": "dreame_vacuum",
            "service_name": "vacuum_goto",
            "x_field": "x",
            "y_field": "y",
        },
        # Ad-hoc zone clean (draw-a-box). Unlike Roborock/Eufy — whose zone rides the same
        # send_command verb as room-clean — Dreame's zone is its OWN service
        # (vacuum_clean_zone), distinct from room-clean's vacuum_clean_segment. So it needs a
        # dedicated block like `goto`, NOT a dispatch.zone_command verb override.
        # Upstream fields (live services.yaml): `zone` = [[x0,y0,x1,y1], ...] in DEVICE mm
        # (4-tuples, NOT Roborock's 5-tuple), `repeats` = a per-zone or single int. Coords
        # come from the card's normalized box → the live map's affine (offset-aware, same
        # frame as go-to). Gated by supports_zone_clean. suction_level/water_volume are
        # available upstream but deliberately not sent (v1 uses the device's saved settings).
        "zone": {
            "service_domain": "dreame_vacuum",
            "service_name": "vacuum_clean_zone",
            "zone_coords": "device_mm",
            "zone_field": "zone",
            "repeats_field": "repeats",
            "zone_passes_max": 2,
            # A zone clean is a GLOBAL clean: the device's global cleaning settings apply,
            # so the card's suction/water/mode/route are set on the global SELECT entities as
            # PRE-CALLS, verified by readback, then the bare zone executes (device uses the
            # globals). The globals are gated by switch.<obj>_customized_cleaning (per-room
            # custom cleaning): ON makes them `unavailable`, so the sequence flips it OFF
            # first and restores it after. suction is identity (select tokens == our
            # canonical), water → the coarse mop_pad_humidity, route/mode → their selects
            # (mode via CLEAN_MODE_VALUE_MAP). See dispatch/manager.py::dispatch_zone_clean.
            # Each setting resolves an entity `<domain>.<obj>_<entity_suffix>` and is applied
            # via <domain>.<service> with {value_field: <wire>}. Selects default (select /
            # select_option / option); water is the FINE wetness NUMBER. `value_map` folds
            # our canonical token to the wire (mode → cleaning_mode option; suction/route
            # tokens ARE the select options so identity; water → a wetness_level int). BEFORE
            # execute the sequence snapshots each entity's current value + the gate, and RIGHT
            # AT ZONE COMPLETION restores them (so a zone clean never persists its settings).
            "global_precall": {
                "gate_switch_suffix": "customized_cleaning",
                "restore_gate": True,
                "settings": [
                    {"key": "mode", "label": "Mode", "entity_suffix": "cleaning_mode",
                     "options": vocabulary.CLEAN_MODE_OPTIONS,
                     "value_map": vocabulary.CLEAN_MODE_VALUE_MAP, "default": "vacuum"},
                    {"key": "suction", "label": "Suction", "entity_suffix": "suction_level",
                     "options": vocabulary.FAN_SPEED_OPTIONS, "default": "standard"},
                    {"key": "route", "label": "Route", "entity_suffix": "cleaning_route",
                     "options": [
                         {"value": "quick", "label": "Quick"},
                         {"value": "standard", "label": "Standard"},
                         {"value": "intensive", "label": "Intensive"},
                         {"value": "deep", "label": "Deep"},
                     ], "default": "standard"},
                    # Water is the FINE global wetness (number.<obj>_wetness_level, 1..32),
                    # the app's "Mop Wetness" slider — NOT the coarse water_volume. The 3
                    # card states fold to representative points on the scale.
                    {"key": "water", "label": "Water", "entity_suffix": "wetness_level",
                     "domain": "number", "service": "set_value", "value_field": "value",
                     "options": vocabulary.WATER_LEVEL_OPTIONS,
                     "value_map": {"slightly_dry": 8, "moist": 16, "wet": 27},
                     "default": "moist"},
                ],
            },
        },
        "dispatch": {
            "template": "dreame_room_clean",
            "service_domain": "dreame_vacuum",
            "service_name": "vacuum_clean_segment",
            # DIRECT-MERGE envelope (data = {entity_id, **payload}). Declared NULL
            # explicitly because vacuum_clean_segment takes `segments` directly, not
            # the wrapped {command, params} shape. Omitting the key made
            # _dispatch_clean_payload default to command="room_clean" (DQ-DE-3) and
            # ship Eufy's wrapped envelope to a service with no command field.
            "command": None,
            "rooms_field": "segments",
            # BARE clean call: {segments:[...]}. Passes rides settings_write below, not
            # the clean payload (the wire param is ignored). None => engine emits no
            # passes array.
            "clean_passes_field": None,
            "passes_max": 3,
            "passes_is_global": False,
            # ── THE PER-ROOM SETTINGS WRITE (the real control surface) ──────────────
            # ONE bulk vacuum_set_custom_cleaning call, index-aligned INT arrays over
            # the queued rooms. The device honors every field regardless of the per-room
            # ENTITY's UI mode-gate (route is `unavailable` on a non-mopping room, but
            # the call sets mode+route in one aligned tuple, applied atomically). Fields
            # with `gate_room_suffix` emit only when select.<obj>_room_<id>_<suffix>
            # exists (capability by entity presence). Required fields always emit, with
            # `filler` for a room whose canonical value is empty. mop_temperature/
            # mop_pressure OMITTED — Robin lacks them and passing them RAISES; a model
            # that has them adds the field (gated on its per-room entity).
            "settings_write": {
                "domain": "dreame_vacuum",
                "service": "vacuum_set_custom_cleaning",
                "segment_id_field": "segment_id",
                "fields": [
                    {"canonical": "fan_speed", "wire": "suction_level",
                     "value_map": vocabulary.FAN_SPEED_WIRE_MAP,
                     "required": True, "filler": 0},
                    # Water: the FINE 1..32 wetness_level is the real per-room control
                    # (Robin declares wetness_level: True, so the device uses it over
                    # water_volume). water_volume stays schema-REQUIRED but the device
                    # ignores it when wetness is present, so it rides a constant filler.
                    # water_level is a numeric STRING ("16"); clamp coerces it to an int
                    # array. wetness is a NUMBER entity, so the capability gate probes
                    # the number domain, not select.
                    {"wire": "water_volume", "constant": 2, "required": True},
                    {"canonical": "water_level", "wire": "wetness_level",
                     "clamp": [1, 32], "filler": 16,
                     "gate_room_suffix": "wetness_level", "gate_domain": "number"},
                    {"canonical": "clean_passes", "wire": "repeats",
                     "required": True, "filler": 1, "clamp": [1, 3]},
                    {"canonical": "clean_mode", "wire": "cleaning_mode",
                     "value_map": vocabulary.CLEAN_MODE_WIRE_MAP,
                     "gate_room_suffix": "cleaning_mode", "filler": 0},
                    {"canonical": "clean_intensity", "wire": "cleaning_route",
                     "value_map": vocabulary.CLEAN_INTENSITY_WIRE_MAP,
                     "gate_room_suffix": "cleaning_route", "filler": 1},
                ],
            },
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
        # decoded the raw map). NEW core backend 'camera_attrs' reads
        # camera.<id>_map extra_state_attributes: as_dict() segment bboxes +
        # calibration_points (3 vacuum->pixel pairs) + vacuum_position/charger_position.
        # map_render (below) declares the shared room_pixels_v1 raster decode, so
        # supports_va_render is True and the card draws our OWN themed floor plan from the
        # decoded pixel_type (dreame_render_data_from_mapdata) instead of the device PNG.
        # map_pixel_size only matters to the camera-attr BBOX fallback (normalizing
        # projected pixels to 0..1); left None — the MapData path uses dimensions.grid_size.
        "map_state_source": {
            "backend": "camera_attrs",
            "identifier_domain": "dreame_vacuum",
            "present_requires_live_map_image": True,
            "map_pixel_size": None,
            # Frame-alignment tune ([x_mm, y_mm], vacuum frame; +x = EAST, +y = NORTH): the
            # dims-based raster projection sits south/west of Dreame's OWN render (the
            # authoritative frame the robot obeys), so shift the whole raster — rooms and
            # anchors together — onto theirs. Target = Dreame's DOCK DISC centre, NOT the robot
            # puck (vacuum_position == charger_position, verified {-553,132}, so the docked puck
            # is drawn FORWARD of the dock as pure style). Live tune 2026-08-30: 225 N landed on
            # the disc; centred at +30 E, +290 N (fine-tuned live; disc-gap measured against
            # the robot's ~350 mm diameter as the px->mm scale).
            "map_frame_offset_mm": [30, 290],
            # PHASE 4a.2 (deferred): a live_pose backend gives the FASTER robot-dot poll +
            # the stall-capture dot. The full-map result already carries robot_anchor /
            # dock_anchor (rendered like eufy's storage backend), so the dashboard map
            # shows the robot now; live_pose only speeds its refresh. Adding it is a second
            # core branch (a POSE_BACKEND_DREAME_CAMERA reader in async_get_map_live_pose)
            # — done after the map path is confirmed on the live device.
        },
        "map_render": {
            # Ride the shared frontend raster decode (Eufy/Roborock use it too). The
            # room_pixels raster is built from the decoded MapData pixel_type by the
            # camera_attrs backend branch in async_get_map_render_data. Reuses the
            # map_state_source pointer above (no duplicate schema).
            "format": "room_pixels_v1",
        },
        "job_segmenter": {
            # DROP the counter tool for Dreame (Chris, 2026-08-30: "it does not work on dreame").
            # The cleaning_time/cleaning_area counters are CUMULATIVE across rooms and the
            # inter-room transits are SUB-30 s, so counter-plateau detection cannot find the
            # boundary — it returns ONE segment for a multi-room run (the whole run lands on the
            # first queue room; the last room reads "Not reached"). noop is the explicit "no
            # counter stream to plateau-detect" (same declaration Roborock makes). finalize_source
            # routes the ATOMIC per-room timings through the NATIVE current_room boundaries the
            # pose sampler buffers instead (learning/history_store._build_native_room_timings) —
            # exact, and it captures the LAST room the live rollover structurally cannot.
            "engine": "noop_job_fallback",
            "finalize_source": "native_current_room",
        },
        "room_attribution": {
            "engine": "noop_room_attribution",
            "source": "native_current_room",
            "tuning": {},
        },
        "live_transition": {
            # NATIVE current-room rollover — the TWIN of the map-highlight wire. Dreame
            # reports the live room directly (sensor.<id>_current_room =
            # entities.active_cleaning_target), the SAME signal that now drives the map
            # highlight and that the pose sampler already banks. Follow it for room rollover
            # instead of Eufy's counter_plateau heuristic (the default), which on Dreame
            # mis-attributed the whole run's area to the FIRST room and dropped the LAST room
            # (counter_plateau can only roll a room when it detects the NEXT room's boundary,
            # so the final room never completes -> "Not reached"). Proven live: the native
            # signal split Entryway then Kitchen cleanly where counter_plateau could not.
            #
            # Dreame cleans in strict queue order and does not revisit rooms
            # (honors_clean_order=True), so a transition OFF a room is proof that room is done
            # -> rooms_unique_per_job stays at its default (True): complete-on-transition,
            # UNLIKE Roborock's path-optimized revisiting (rooms_unique_per_job=False, all
            # completion deferred to finalize). The LAST room is still resolved at finalize by
            # learning/external_ingest.reconcile_dispatched_identity, the same path Roborock
            # uses. Eufy leaves native_transition_source False (the default) and is untouched.
            "enabled": True,
            "native_transition_source": True,
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

        # Sourced from adapters/dreame/upkeep_catalog.py + dreame_upkeep_guides.py, mirroring
        # the eufy/roborock declaration. WITHOUT this block the authored guide families are
        # invisible: maintenance/manager.py resolves guides via _catalog["guide_library"], so
        # the families + their 17 language packs sat unreachable on disk until it was declared.
        "upkeep_catalog": {
            "model_names": DREAME_MODEL_NAMES,
            "model_guide_families": DREAME_MODEL_GUIDE_FAMILIES,
            "guide_family_names": DREAME_GUIDE_FAMILY_NAMES,
            "guide_library": DREAME_UPKEEP_GUIDE_LIBRARY,
            # Per-language step/note/frequency overlays on the English base, selected by the
            # HA instance language (see upkeep_guides_i18n/, one <lang>.py each).
            "guide_translations": DREAME_UPKEEP_GUIDE_TRANSLATIONS,
        },

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
