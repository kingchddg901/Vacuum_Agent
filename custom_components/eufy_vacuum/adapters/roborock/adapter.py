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
    SUFFIX_CLEANING_TIME,
    SUFFIX_CLEANING_AREA,
    SUFFIX_BATTERY,
    SUFFIX_ERROR_MESSAGE,
    SUFFIX_CHARGING,
    SUFFIX_JOB_ACTIVE,
    SUFFIX_WATER_BOX,
    SUFFIX_MOP_INTENSITY,
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
    CLEAN_MODE_OPTIONS,
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

    # A device can carry a mop tank yet reject every mop command (the S6). mop_settable
    # gates the water picker (vocabulary) + supports_water_control + the mop
    # global_pre_calls dispatch — all no-ops when False, so the S6 stays byte-identical.
    mop_settable = bool(profile.get("mop_settable", False))

    # Mop dispatch (settable models only): water is a device-GLOBAL select, not a
    # per-room app_segment_clean field, so it rides dispatch.global_pre_calls — set the
    # mop intensity select BEFORE each group's segment clean. The engine re-runs pre-calls
    # PER PHASE (phase_runner._dispatch_active_phase) from that phase's own rooms, so a
    # vacuum group (water off) then a mop group (water high) each apply their own level.
    # rank ascending -> max-wins across the group; canonical off/low/medium/high map 1:1
    # onto select.<obj>_mop_intensity's options (no value_map). UNVERIFIED on-device: a
    # rejected select_option is caught + logged and never aborts the run
    # (_run_global_pre_calls), so this degrades safely on a model that turns out unsettable.
    # mop_mode (scrub depth) is a second GLOBAL select with no canonical per-group slot yet
    # -> left out until there's a card control to drive it per group.
    mop_pre_calls: list[dict] = []
    if mop_settable:
        mop_pre_calls = [
            {
                "field": "water_level",
                "rank": ["off", "low", "medium", "high"],
                # The water/mop-intensity select is device-GLOBAL, so a mixed mop +
                # vacuum-only batch (a single atomic dispatch) can't zero water per-room.
                # Max-wins would wet-mop the dry rooms; "safest" flips a MIXED batch to the
                # LOWEST requested water instead (a dry room is never wet-mopped — under-mop
                # is accepted over wet-mop). A single-mode batch (all-mop / all-vacuum) keeps
                # max-wins. Per-group stepped runs re-run this per phase from each group's own
                # rooms, so a single-mode group is unaffected. See manager._run_global_pre_calls.
                "mixed_mode_water_policy": "safest",
                "service": {
                    "domain": DOMAIN_SELECT,
                    "service": "select_option",
                    "value_key": "option",
                    "target_entity_id": build_entity_id(vid, SUFFIX_MOP_INTENSITY, DOMAIN_SELECT),
                },
            },
        ]

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
            # Card-facing dropdowns. fan_speed is always exposed; clean_mode +
            # water_level ride ONLY on mop_settable models (below). clean_intensity
            # stays OMITTED for ALL Roborock (no intensity axis).
            # On the S6 (mop_settable False) the mop is EMPIRICALLY UNSETTABLE
            # (SET_WATER_BOX_CUSTOM_MODE / SET_MOP_MODE -> RoborockUnsupportedFeature),
            # so its mop stays OBSERVE-ONLY (entities.mop_active) and both pickers hide.
            # A settable-mop model (S7/S8) exposes clean_mode (vacuum vs mop — the logical
            # switch that gates water + drives the mop pre-call; it never hits the wire)
            # and water_level (mop intensity), honored via the mop global_pre_calls below.
            "fan_speed_options": FAN_SPEED_OPTIONS,
            **(
                {
                    "clean_mode_options": CLEAN_MODE_OPTIONS,      # vacuum / mop / vacuum_mop
                    "water_level_options": WATER_LEVEL_OPTIONS,    # off/low/medium/high, canonical 1:1
                }
                if mop_settable
                else {}
            ),
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
            # Ad-hoc zone clean: Roborock's app_zoned_clean wants WORLD millimetres
            # ([[x0,y0,x1,y1,repeat], ...]) via stock vacuum.send_command — no fork/PR.
            # zone_coords="device_mm" makes dispatch_zone_clean invert the drawn 0-1 rects
            # to device-mm through the live map's own projection (mapping/zone_dispatch.py)
            # and REFUSE if it can't validate. The payload IS the params list, so dispatch
            # sets params_as_list_override=False (not the app_segment_clean single-wrap).
            "zone_command": "app_zoned_clean",
            "zone_coords": "device_mm",
            # Strict-order phase watchdog timing (seconds), tuned for the S6: it
            # finishes a room, re-docks + charges, and IGNORES an app_segment_clean
            # sent at that instant — so the watchdog settles, dispatches, verifies the
            # target room actually started (sustained), and re-dispatches if not.
            # dock_settle is longer because a target room that IS the dock has the
            # longest ignore-transient. These live HERE (not core) so a different
            # path-optimizing brand declares its own profile; core falls back to its
            # matching defaults for any key omitted. See manager._phase_timing.
            "phase_timing": {
                "settle_seconds": 10,
                "dock_settle_seconds": 45,
                "verify_seconds": 90,
                # Sustained cleaning-of-target needed to confirm a phase started. Kept
                # comfortably below the shortest real S6 per-room clean (a sub-15s room
                # is rare); the idle-exit weak-confirm in _await_phase_started backstops
                # any room that finishes even faster, so this never stalls — it only sets
                # how quickly a confirmed room releases the guard.
                "confirm_seconds": 15,
                "poll_seconds": 5,
                "max_attempts": 3,
            },
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
            # Passes is ONE batch scalar (repeat) for the whole run, not per-room:
            # the engine collapses the selected rooms to the MAX requested passes.
            # The editor keeps per-room passes chips but notes the strongest wins.
            "passes_is_global": True,
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
            # PER-ROOM LIVE fan: fan_speed is settable MID-RUN on the S6 and applies
            # to the room being cleaned, so the framework sets each room's suction AS
            # the robot enters it (driven by the native current_room rollover) — true
            # per-room fan without per-room re-dispatch, keeping the device's one
            # path-optimized run. The dispatch-time call seeds the first (guessed)
            # room's fan; the rollover corrects to the real first room (~30s poll
            # lag). passes stays GLOBAL (the app_segment_clean repeat — NOT
            # mid-run-settable). NO mop: SET_WATER_BOX_CUSTOM_MODE / SET_MOP_MODE are
            # RoborockUnsupportedFeature on the S6 (observe-only, app-controlled).
            # Mop intensity (settable models) — a device-GLOBAL select, re-applied per
            # phase from each group's water_level (see mop_pre_calls above). Omitted
            # entirely on the S6 (mop_pre_calls empty) so its dispatch is byte-identical.
            **({"global_pre_calls": mop_pre_calls} if mop_pre_calls else {}),
            "per_room_live_settings": [
                {
                    "field": "fan_speed",
                    # Only push values in the Roborock fan vocabulary; this skips
                    # the framework's Eufy-shaped default ("Max") so an unedited
                    # room leaves the device on its current fan rather than failing
                    # set_fan_speed with an invalid (capitalized) speed.
                    "options_key": "fan_speed_options",
                    "service": {
                        "domain": "vacuum",
                        "service": "set_fan_speed",
                        "value_key": "fan_speed",
                    },
                },
            ],
            # LEVER B — live current-room refresh during a CONTIGUOUS run. The S6's live
            # current_room + per-room fan ride the upstream coordinator's MAP cadence
            # (IMAGE_CACHE_INTERVAL ~30s), NOT the ~15s status poll — vacuum_room is
            # map-derived, refreshed only inside the 30s-gated update_map(). During a
            # contiguous run (state stays "cleaning", no per-room docking) the framework
            # pulses get_vacuum_current_position, which calls map_content.refresh() DIRECTLY
            # and OFF that 30s gate (and un-debounced), so the native rollover + per-room fan
            # track at ~interval_s (~15s) instead of ~30s. The map IMAGE backdrop stays 30s
            # (a separate refresh) — acceptable; this is about which room is live, not pixels.
            # Strict-order runs dock per room, so each room-start is a state flip that already
            # forces a free refresh — they're EXCLUDED (the pulse is skipped when the job has
            # phases). LOCAL-ONLY by design: the 30s map gate is a Roborock CLOUD rate-limit
            # guard, so local_gate restricts the pulse to a LAN connection, detected from the
            # ABSENCE of the upstream integration's "cloud_api_used" repair issue (present =>
            # cloud => skip), re-checked every pulse so a mid-run local->cloud flip disables it
            # within one interval. ALL brand-specific strings (service + gate) live HERE; core
            # evaluates them generically (manager._live_room_refresh / maybe_pulse_live_room_
            # refresh). Eufy omits this block (it already has a ~2s fork pose) -> no-op.
            "live_room_refresh": {
                "enabled": True,
                "interval_s": 15,
                # roborock.get_vacuum_current_position (NOT vacuum.*): registered under the
                # roborock domain via async_register_platform_entity_service (services.py),
                # targeting the vacuum entity. It is SupportsResponse.ONLY, so the call MUST
                # set return_response (returns_response) — we discard the x/y; we only want
                # its map_content.refresh() side effect. Its absence/unsupported raises
                # ServiceNotFound / ServiceNotSupported -> core sticky-disables the pulse.
                "service": {
                    "domain": "roborock",
                    "service": "get_vacuum_current_position",
                    "returns_response": True,
                },
                "local_gate": {
                    "device_identifier_domain": "roborock",
                    "issue_domain": "roborock",
                    "issue_id_template": "cloud_api_used_{duid_slug}",
                },
            },
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
            # ignored. Roborock's native signal is a live pointer and may revisit
            # rooms during an optimized route, so completion is left to the final job
            # snapshot instead of treating every pointer change as proof that the
            # previous room is permanently done. Eufy leaves native_transition_source
            # False (the default) and is untouched.
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
            # The Roborock core integration publishes a LIVE map image as an HA
            # `image` entity named image.{object_id}_{map-slug}. The entity-id
            # PATTERN lives HERE (not in core) so the `image.` domain + naming
            # convention stay brand-owned — core only substitutes the generic
            # {object_id} (vacuum object_id) + {map_slug} (slugified map name),
            # existence-checks the result, and surfaces it as
            # snapshot.live_map_image_entity for the card's live Map backdrop. A
            # camera-based brand could instead declare e.g. "camera.{object_id}_map".
            # Eufy omits this -> no live backdrop, byte-identical.
            "live_map_image_entity_pattern": "image.{object_id}_{map_slug}",
        },

        "map_state_source": {
            # MEMORY backend: unlike the Eufy fork (decoded map on disk), the HA-core
            # Roborock integration keeps the parsed map (vacuum-map-parser MapData,
            # rooms = Room bboxes) ONLY in memory — config-entry runtime_data /
            # hass.data["roborock"]. The exact attribute path varies across HA
            # versions and is NOT knowable offline, so the reader is a DEFENSIVE
            # runtime introspector that duck-types for a Room-like collection +
            # image dims and logs a diagnostics breadcrumb. The first live deploy's
            # log is what confirms/tunes the path (docs/dev/map-state-source.md,
            # Wave 1) — and reveals whether the no-dock S6 even produces in-memory
            # rooms (the .storage/roborock map content was empty for it).
            #
            # Presence-gated on the live map IMAGE entity (image.{object_id}_{map};
            # same gate as the live backdrop): no parsed map → no image → hidden.
            "backend": "memory",
            "identifier_domain": "roborock",
            "hass_data_domain": "roborock",
            "present_requires_live_map_image": True,
        },

        "map_render": {
            # Re-decode the raw map blob's SEGMENT layer to a per-pixel room-id raster so the
            # card renders per-room (colour / floor textures / hit-test) instead of the
            # overlapping bboxes the parser exposes. vacuum-map-parser reads the pixel layer
            # to colour rooms then DISCARDS it, but the raw bytes survive on the v1 MapContent
            # (`raw_api_response`, cached in HA memory). The render reader walks the same
            # `hass_data_domain` runtime_data roots as map_state_source, finds the MapContent,
            # and decodes it (mapping/roborock_raw_map.py). v1 (S6 / Q-class) only. NOTE: the
            # room raster is self-contained; the pose overlay's coord registration
            # (res/origin/flip vs the live robot) still needs calibrating on a real device.
            "format": "roborock_raw_map_v1",
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
            # Mops (tank-based). Whether the mop is PROGRAMMATICALLY controllable is
            # per-model: the S6 rejects SET_WATER_BOX_CUSTOM_MODE / SET_MOP_MODE
            # (RoborockUnsupportedFeature) so mop_settable is False -> water control
            # off, picker hidden, mop observed via the tank. A settable-mop model
            # (S7/S8) sets water control True -> the picker + the mop pre-call engage.
            "supports_mop_features": caps.get("supports_mop_features", profile["has_mop"]),
            "supports_water_control": mop_settable,
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
            "rooms_unique_per_job": False,
            # Reusable room PROFILES bundle multiple per-room settings (mode,
            # water, intensity, passes, edge). The S6 exposes only per-room fan
            # (everything else is global/unsettable), so a "profile" would be a
            # degenerate named fan speed — hide the profiles section entirely.
            "supports_room_profiles": False,
            # app_segment_clean path-optimizes and IGNORES the dispatched order
            # (confirmed on-device): order is honored only when set as a Sequence
            # in the Roborock app. So the card's queue order is advisory — surfaced
            # at run start. (Eufy honors order via send_command -> default True.)
            "honors_clean_order": False,
            # Zone clean (draw-a-box) via app_zoned_clean (device-mm; see dispatch.
            # zone_command). The S6 supports zoned cleaning through stock send_command; the
            # card un-rotates the drawn rect so it works at any display rotation.
            "supports_zone_clean": True,
            # app_zoned_clean device limits (S6, likely all Roborock): at most 5 zones per
            # call, each between 1 ft² and 32.8 ft². Count is enforced in the card (zoneMax
            # via the snapshot) + dispatch (defence-in-depth); size in dispatch_zone_clean
            # after the mm conversion (the card draws in % and can't know the mm size).
            "zone_max": 5,
            "zone_min_area_m2": 0.0929,   # 1 ft²
            "zone_max_area_m2": 3.05,     # 32.8 ft²
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
        # binary, not current_room). Per-room LIVE fan rides
        # dispatch.per_room_live_settings (set_fan_speed); dispatch.global_pre_calls
        # carries per-group mop intensity on settable-mop models (empty on the S6 —
        # passes are global, mop unsettable). Wave 3: live_transition.native_transition_source (native current_room
        # live rollover, filtered to job targets).
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
