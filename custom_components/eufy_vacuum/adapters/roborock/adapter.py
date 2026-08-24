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
``__init__.py`` via the brand-dispatch loop, which selects this registrar by matching
the vacuum's entity-registry ``platform`` against ``const.UPSTREAM_PLATFORMS``.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..entity_resolve import resolve_declared_entities

from ..registry import register_adapter_config
from .const import ADAPTER_ID, LOW_BATTERY_THRESHOLD_PERCENT
from .entities import (
    ALL_SUFFIXES,
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
    SUFFIX_LAST_CLEAN_END,
    SUFFIX_TOTAL_CLEANING_COUNT,
    SUFFIX_WATER_BOX,
    SUFFIX_MOP_INTENSITY,
    DOMAIN_BINARY_SENSOR,
    DOMAIN_SELECT,
)
from .dock import dock_profile
from .maintenance_components import MAINTENANCE_COMPONENTS
from .model_catalog import profile_for_model
from .upkeep_catalog import (
    ROBOROCK_GUIDE_FAMILY_NAMES,
    ROBOROCK_MODEL_GUIDE_FAMILIES,
    ROBOROCK_MODEL_NAMES,
)
from .roborock_upkeep_guides import ROBOROCK_UPKEEP_GUIDE_LIBRARY
from .upkeep_guides_i18n import ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS
from .vocabulary import (
    ACTIVE_RUN_TASK_STATES,
    NOT_ERROR_SENTINELS,
    CANCEL_DETECTION_STATES,
    CUSTOM_ROOM_PROFILE,
    FAN_SPEED_OPTIONS,
    PATH_TYPE_OPTIONS,
    FLOOR_TYPE_FAN_DEFAULTS as RB_FLOOR_TYPE_FAN_DEFAULTS,
    FLOOR_TYPE_WATER_DEFAULTS as RB_FLOOR_TYPE_WATER_DEFAULTS,
    ROOM_PROFILES,
    WATER_LEVEL_OPTIONS,
    CLEAN_MODE_OPTIONS,
    ROBOROCK_DOCK_SOURCED_ERROR_CODES,
    ROBOROCK_ROBOT_SOURCED_ERROR_CODES,
    ROBOROCK_EVIDENCE_INVALIDATING_ERROR_CODES,
    ROBOROCK_EVIDENCE_SAFE_ERROR_CODES,
    ROBOROCK_ERROR_LABEL_KEYS,
)

_LOGGER = logging.getLogger(__name__)


def _device_for_vacuum(hass: HomeAssistant, vacuum_entity_id: str):
    """Return the HA device-registry entry for a vacuum entity, or None."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(vacuum_entity_id)
    if entry is None or entry.device_id is None:
        return None
    return dr.async_get(hass).async_get(entry.device_id)


# REMOVED — ``is_roborock_vacuum``. It answered "is this vacuum mine?" from the device
# registry (manufacturer ``Roborock``, or a ``roborock.`` model prefix) and core called
# it, along with every other brand's equivalent, in table order. That is ``if brand:``
# with a function pointer, and moving brand knowledge back into core's control flow is
# the arrangement the adapter seam exists to remove.
#
# Identity is now DATA: this package declares ``UPSTREAM_PLATFORMS`` in const.py and
# core compares it against the entity registry's ``platform``. A brand can no longer
# express "probably me" because core no longer asks. It is also strictly better
# evidence — ``platform`` is set by HA from the providing integration's domain and is
# never blank, whereas the device-registry strings it replaced are free text and were
# routinely empty on real installs (which is why Eufy never had a detector at all).


def register_roborock_adapter_for_vacuum(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    *,
    entity_overrides: dict[str, str] | None = None,
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
    # rejected select_option is caught + logged and never aborts the run.
    # ⚠ NOT TRUE FOR THE SAFEST-WATER ENTRY, which is the water pre-call this brand
    # declares. When ``mixed_mode_water_policy: "safest"`` is active,
    # ``dispatch/manager.py::_run_global_pre_calls`` RAISES and aborts the dispatch on
    # both a missing target entity (issue #51) and any exception from the select —
    # deliberately, because failing to push safe water before a batch containing dry
    # rooms is what wet-mops them.
    #
    # And that path is not an edge case: it activates whenever the batch contains ANY
    # non-mop room (``_any_dry_room = _mop_rooms < len(resolved_rooms)``), which
    # includes the plainest case of all, an all-vacuum batch. Since an uncatalogued
    # model defaults to mop-settable, this is reachable on any Roborock not in the
    # catalog whose mop set is actually rejected.
    #
    # "Caught + logged, never aborts" remains true for the BEST-EFFORT entries (fan,
    # single-mode water). Corrected 2026-08-23.
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
                    # BY ROLE, not by frozen id. These pre-calls are built BEFORE
                    # `resolve_declared_entities` runs, so any id baked in here is the
                    # pre-rescue guess and stays wrong forever on an install whose
                    # entity ids are localized or renamed. Naming the role instead
                    # makes the dispatcher read the RESOLVED entity at call time.
                    "target_role": "mop_intensity",
                },
            },
        ]

    # anchor: CN1R6FC7  roborock entity candidates — the declared role->entity_id map the resolver starts from
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
    # --- dock identity (the SECOND device in this config entry) ---------------
    # `has_dock` is NOT a per-model constant. Roborock reports the dock separately, and
    # the same robot model ships with different stations, so the model catalog cannot
    # know — every profile there declares False and always did. The live answer is the
    # dock device's `model_id` run through the vendor's own truth table; see dock.py for
    # why the three cheaper tests are all wrong.
    #
    # `dock_profile` returning None means UNDETERMINED, not "no dock" — fall back to the
    # catalog's conservative default so a missing library can never enable a control for
    # hardware that is not there. Offering a control that does nothing is the worse
    # failure (the same reasoning model_catalog gives for has_path_control).
    dock = dock_profile(hass, vid)
    if dock is None:
        has_dock = bool(profile["has_dock"])
        dock_washable = dock_dryable = dock_collectable = has_dock
    else:
        has_dock = bool(dock["has_dock"])
        # Each control asks the vendor the question it actually depends on rather than
        # riding one blanket flag: an o1/oc auto-empty dock collects but cannot wash, and
        # an o2 washes but cannot collect. Keying all three off has_dock would offer a
        # mop wash on a dock with no water in it.
        dock_washable = bool(dock.get("is_washable", has_dock))
        dock_dryable = bool(dock.get("is_dryable", has_dock))
        dock_collectable = bool(dock.get("is_collectable", has_dock))
        _LOGGER.debug(
            "%s: dock resolved for %s — type=%s (%s) has_dock=%s wash=%s dry=%s collect=%s%s",
            ADAPTER_ID, vid, dock.get("dock_type"), dock.get("dock_type_name"),
            has_dock, dock_washable, dock_dryable, dock_collectable,
            f" reason={dock['reason']}" if dock.get("reason") else "",
        )

    capability_hints: dict[str, bool] = {
        "supports_mop_features": profile["has_mop"],
        "supports_mop_wash": dock_washable,
        "supports_mop_dry": dock_dryable,
        "supports_empty_dust": dock_collectable,
        # Per-model, not brand-wide: the S6 has no path/route axis, but better models
        # do — see model_catalog.has_path_control for why every entry is False today.
        "supports_path_control": profile.get("has_path_control", False),
        # Declared False in the config capabilities block too (see ~:571). It must ALSO be
        # a hint: the room payload gate reads the runtime-detected capabilities payload
        # (manager.get_vacuum_capabilities -> data["capabilities"]), not the config block,
        # so a config-only declaration never reaches queue_engine.
        "supports_edge_mopping": False,
        # D18: THE DECLARATION HAD NO WIRE. The config block below reads
        # `caps.get("supports_zone_clean", True)` under a comment saying a model catalog
        # entry can declare it False "and be believed" — but nothing passed it as a
        # hint, and `capabilities._hint_wins` only honours a declared False when the key
        # is PRESENT in the hints. So a catalog entry declaring False resolved to the
        # derived default True and was silently ignored: open at the core end (dispatch
        # DOES refuse on False, ZONE-2) and unconnected at this one.
        #
        # Defaults True, so no model in the catalog changes behaviour today. The point is
        # that the declaration surface now reaches the gate, which is what makes the
        # comment below true and what makes a future entry provable rather than hopeful.
        # Same shape as `has_path_control` directly above.
        "supports_zone_clean": profile.get("supports_zone_clean", True),
    }
    caps = detect_capabilities(
        hass,
        vacuum_entity_id=vid,
        detected_model=detected_model,
        entity_candidates=entity_candidates,
        model_family=profile["family"],
        capability_hints=capability_hints,
        # live:ENT-7 — the override mechanism is CORE's, not a brand's, so this
        # is the same three lines here as in the Eufy adapter and Roborock users
        # get the fix without a Roborock-specific code path.
        entity_overrides=entity_overrides or {},
        maintenance_components=MAINTENANCE_COMPONENTS,
        # live:ENT-4 — this brand shipped WITHOUT it, so sibling matching could
        # not tell that `_total_cleaning_area` is its own role: the guard's own
        # predicate replayed against this adapter's map returned
        # _claimed_by("ivy_total_cleaning_area") == "_cleaning_area", accepting a
        # lifetime counter as a per-run metric. Eufy passed this from the start,
        # which is exactly how a core fix reads as done while one brand runs
        # unguarded.
        # anchor: CNXD5V8Q  roborock reserved-suffixes at the capability probe
        reserved_suffixes=ALL_SUFFIXES,
    )

    # --- entity ID map --------------------------------------------------------
    # active_map (select.{id}_selected_map) reports the map NAME ("Main floor");
    # Wave 2a confirmed its id-space and wires it as the discovery active-map +
    # the multi-map alignment anchor (trivial at one map, load-bearing on a
    # multi-map flip). job_active is the recharge-resume disambiguator (see
    # completion block); harmless if unconsumed.
    entities = {
        "task_status": build_entity_id(vid, SUFFIX_TASK_STATUS),
        # anchor: CNTM7CWT  roborock live-name entity
        "active_cleaning_target": build_entity_id(vid, SUFFIX_ACTIVE_CLEANING_TARGET),
        "active_map": build_entity_id(vid, SUFFIX_ACTIVE_MAP, DOMAIN_SELECT),
        "cleaning_time": build_entity_id(vid, SUFFIX_CLEANING_TIME),
        "cleaning_area": build_entity_id(vid, SUFFIX_CLEANING_AREA),
        "battery": build_entity_id(vid, SUFFIX_BATTERY),
        "error_message": build_entity_id(vid, SUFFIX_ERROR_MESSAGE),
        "charging": build_entity_id(vid, SUFFIX_CHARGING, DOMAIN_BINARY_SENSOR),
        "job_active": build_entity_id(vid, SUFFIX_JOB_ACTIVE, DOMAIN_BINARY_SENSOR),
        # OBSERVABILITY ONLY (issue #46). HA 2026.7 stops creating job_active on
        # some devices; these two are the candidate discriminators for "recharge
        # dock or finish?" and are declared so the observation trace and
        # diagnostics can READ them. Nothing gates on them, and they are
        # deliberately NOT in the lifecycle watch list — see _common.py, which
        # only watches entities whose edges should re-trigger the completion
        # gate. A clean-summary edge must not do that.
        "last_clean_end": build_entity_id(vid, SUFFIX_LAST_CLEAN_END),
        "total_cleaning_count": build_entity_id(vid, SUFFIX_TOTAL_CLEANING_COUNT),
        # mop_active: the S6 has NO per-room clean_mode — mopping is driven by the
        # physical water tank. The card reads this (via snapshot.mop_active) to
        # surface mop state + the water-level field only when the tank is attached.
        "mop_active": build_entity_id(vid, SUFFIX_WATER_BOX, DOMAIN_BINARY_SENSOR),
        # DECLARED so the rescue can reach it (issue #51). This select is the target
        # of the mop global_pre_call, and it used to exist ONLY as a frozen literal
        # inside dispatch.global_pre_calls — a place `resolve_declared_entities` never
        # looks and no user override can reach. On a localized install the real select
        # is `select.<vid>_wisch_intensitat`, so every water push named an entity that
        # does not exist. Declared here it is rescued like any other role (its upstream
        # translation_key IS `mop_intensity`, so the suffix-derived key already
        # matches), it shows up on the System binding screen, and it becomes
        # overridable. Declared on EVERY model, including the S6 whose mop is
        # observe-only: the entity exists there too, and reading it is not setting it.
        "mop_intensity": build_entity_id(vid, SUFFIX_MOP_INTENSITY, DOMAIN_SELECT),
    }

    # Rescue derived IDs that do not match this install (renamed device/entity, or a
    # brand splitting entities across devices). Only touches IDs that FAIL to resolve
    # and refuses to guess when ambiguous, so a working install cannot be altered.
    # See adapters/entity_resolve.
    entities, entity_remaps = resolve_declared_entities(
        hass, vid, entities,
        overrides=entity_overrides,
        reserved_suffixes=ALL_SUFFIXES,
        # ROLES WHOSE UPSTREAM translation_key IS NOT THEIR SLUG.
        #
        # Only job_active, and it earns the whole seam. We declare the suffix
        # `_cleaning`, from which the rescue derives the wanted key `cleaning`;
        # Roborock publishes `in_cleaning`. One word, and on any install whose
        # entity ids are localized the role never resolves — the German id is
        # `binary_sensor.<vid>_reinigen`, which no suffix can reach either.
        #
        # It is not a missing sensor. Roborock declares
        # `completion.require_job_active_clear`, so this entity is the SINGLE signal
        # that arms completion; unresolved, `has_observed_active_lifecycle` stays
        # False for the whole run and `is_stranded_started` reaps it as `interrupted`
        # ~15 minutes after dispatch, possibly mid-clean, with nothing reaching
        # learning (issue #51).
        translation_keys={"job_active": "in_cleaning"},
    )

    config = {
        "adapter_id": ADAPTER_ID,
        "source": "code",
        "display_name": profile["display_name"],
        # Short brand/app name the card uses in copy ("Clean from the Roborock app").
        "brand": "Roborock",

        # sensor.<id>_cleaning_time reports a BARE number in MINUTES (no
        # unit_of_measurement — verified 2026-07-11 recorder export: 0.5, 0.83,
        # ... 4.52 over a ~4.5 min clean). Without this the metrics listener would
        # store minutes as seconds (60x low), which skews learning + false-trips the
        # idle-wall guard. Fallback only — a real unit on the entity still wins.
        "cleaning_time_unit": "min",

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
            # DECLARED UNCONDITIONALLY, even though no catalogued model sets
            # has_path_control yet. This is the option list for path_type, the axis
            # Roborock keeps and Eufy does not, and declaring it is what makes a stored
            # value JUDGEABLE: rooms/vocabulary_migration.py can only reset a value it
            # can check against a list, so while no list existed the fossil string
            # "None" was un-droppable (the field IS declared by the profiles) and
            # un-resettable (no options) — the exact gap that left it on every room.
            # Capability gating decides whether the axis is OFFERED; this decides
            # whether a value is VALID, and those are different questions.
            "path_type_options": PATH_TYPE_OPTIONS,
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
            # usually misses.
            #
            # live:RB-ERR-2 — that used to end "-> code None, message = the code string
            # (acceptable)". It was NOT acceptable: code None meant every seam below
            # (classify_error_code, error_source_for_code, error_label_key) returned
            # unclassified/unknown/None for every Roborock fault, so all five tables in
            # vocabulary.py were unreachable at runtime and the shipped fault labels
            # never resolved. message_is_code closes it: the tracker carries the entity
            # state into `code` when the attribute route yields nothing.
            "message_is_code": True,
            "task_status_error_value": "error",
            "grace_window_seconds": 5,
            "error_code_attribute_names": ["error_code", "code", "errorCode"],
            "unknown_error_message": "Unknown error during run",
            # RF-DOCK clauses 4/5 — DECLARED, as enum STRINGS (live:RB-ERR-1).
            #
            # The note that stood here said an int-keyed table "has nothing to
            # match", and warned that declaring int codes while the tracker sees
            # strings would silently match nothing. Right about the symptom, wrong
            # about the cause: the table was never the problem — CORE COULD NOT
            # CARRY A NON-NUMERIC CODE. classify_error_code / error_source_for_code
            # / error_label_key all opened with `_exact_int(code)` and bailed on
            # None, so ANY declaration here was dead on arrival. Core now normalizes
            # through `_code_key`, which keeps every int guard (never int(3.7); bool
            # is not code 1; numeric strings still resolve to ints) and lets an enum
            # brand declare its own code space. That is what the adapter seam is
            # for: Eufy surfaces numbers, Roborock surfaces strings, and the backend
            # deals with both.
            #
            # THE TABLES LIVE IN vocabulary.py, next to every other Roborock
            # declaration and in the same place Eufy keeps its own — read there for
            # what each set means, why INVALIDATING is hand-declared rather than
            # derived, and which states are deliberately left unclassified.
            "dock_sourced_error_codes": sorted(ROBOROCK_DOCK_SOURCED_ERROR_CODES),
            "robot_sourced_error_codes": sorted(ROBOROCK_ROBOT_SOURCED_ERROR_CODES),
            "evidence_invalidating_error_codes": sorted(
                ROBOROCK_EVIDENCE_INVALIDATING_ERROR_CODES
            ),
            "evidence_safe_error_codes": sorted(ROBOROCK_EVIDENCE_SAFE_ERROR_CODES),
            # CARD-3: enum string -> i18n key. OUR keys, not HA's translations —
            # HA has only 11 of our 18 languages complete (Arabic 0/53), and
            # hass.localize keys off the HA PROFILE language while the card resolves
            # its own through the per-user globe. vocabulary.py carries the measured
            # reasoning and the three states left unmapped on purpose.
            "error_label_keys": dict(ROBOROCK_ERROR_LABEL_KEYS),
        },

        "dispatch": {
            # Ad-hoc zone clean: Roborock's app_zoned_clean wants WORLD millimetres
            # ([[x0,y0,x1,y1,repeat], ...]) via stock vacuum.send_command — no fork/PR.
            # zone_coords="device_mm" makes dispatch_zone_clean invert the drawn 0-1 rects
            # to device-mm through the live map's own projection (dispatch/zone_dispatch.py)
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
            # anchor: CN8S81R0  mop intensity is a device-GLOBAL select, re-applied per phase; omitted entirely on the S6
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

        # DEVICE-SIDE CLEAN ORDER — Roborock calls it a "Sequence". A saved order
        # OVERRIDES the device's own path optimisation for EVERY start (ours and the
        # user's own app runs alike) and persists on the device until changed or
        # cleared, so it is not scoped to a single run. It ORDERS but never RESTRICTS:
        # the app states "the robot cleans unsequenced areas one by one at the end", so
        # a sequence can neither skip a room nor pull in one the dispatch omitted.
        #
        # Ids are OUR room_id space, no translation. Verified live 2026-08-19: wrote
        # [27, 25, 23, 22], read back identical, ack ['ok'], and the vendor app rendered
        # it as badges 1-2-3-4 on its own Sequence screen. `[]` means no order saved.
        #
        # READ + WRITE. The write landed 2026-08-24; until then this block was read-only
        # under the note "a declaration that promises a write nothing implements is worse
        # than an absent one", which is why the write half arrives WITH its implementation
        # rather than ahead of it.
        #
        # ⚠ THE WRITE IS MODEL-GATED, NOT BRAND-GATED. `set_clean_sequence` is the V1
        # device protocol. Newer Qrevo/B01 models answer `service.set_room_order` on a
        # DIFFERENT transport, so declaring the write brand-wide would hand those owners a
        # control that can never land. `supports_clean_sequence_write` comes from the model
        # catalog and is False for an unknown model. Core needs no branch for this: an
        # absent `write` key simply means `can_write` is False and the control never
        # appears — the declaration IS the gate.
        #
        # via: v1_debug_log — `vacuum.send_command` is SupportsResponse.NONE, so the
        # reply is observable ONLY on python-roborock's decode DEBUG line, captured for
        # a short window (clean_order/manager.py; needs no change to roborock and
        # nothing installed by a user). THIS IS THE REPOINT SEAM: when upstream
        # registers get_clean_sequence with SupportsResponse.ONLY — as
        # get_vacuum_current_position already is in that same integration — add a
        # `service_response` strategy and change `via` HERE. No core change, no sensor
        # change. An unimplemented `via` reads as unavailable, never as an empty order.
        "device_clean_order": {
            "enabled": True,
            "read": {
                "via": "v1_debug_log",
                "command": "get_clean_sequence",
                "service": {"domain": "vacuum", "service": "send_command"},
                "source_logger": "roborock.protocols.v1_protocol",
                "decoded_prefix": "Decoded V1 message result: ",
            },
            # The adapter declares the LITERAL payload with one named hole; core
            # substitutes `$order` WHOLESALE and knows nothing about the shape. Core owns
            # the key (`device_clean_order`); "sequence" is Roborock's word and stays HERE
            # (RULING, Chris 2026-08-20: core may own a closed set of SHAPE names, never a
            # BRAND name).
            #
            # `clear` is declared rather than derived from an empty `payload`, because
            # "the empty case" is a brand fact -- an empty list clears Roborock, another
            # brand might need an explicit null, a sentinel, or a different command.
            # Deriving it would be core inventing a brand's word.
            #
            # The ack is free: every write acks ['ok'] on the SAME decode line the read
            # already captures, so the write self-confirms through machinery that exists,
            # and it works before any upstream service lands.
            **(
                {
                    "write": {
                        "via": "v1_send_command",
                        "service": {"domain": "vacuum", "service": "send_command"},
                        "payload": {
                            "command": "set_clean_sequence",
                            "params": "$order",
                        },
                        "clear": {
                            "command": "set_clean_sequence",
                            "params": [],
                        },
                        "ack": {
                            "via": "v1_debug_log",
                            "equals": ["ok"],
                            "source_logger": "roborock.protocols.v1_protocol",
                            "decoded_prefix": "Decoded V1 message result: ",
                        },
                    }
                }
                if profile.get("supports_clean_sequence_write")
                else {}
            ),
        },

        "setup": {
            # add_vacuum -> import_active_map -> save_rooms. Roborock has no
            # Eufy-style one-at-a-time cloud-map "import", but the integration still
            # needs a map bucket built from the get_maps rooms before Configure Rooms
            # can show them. import_active_map is the brand-agnostic "discover +
            # create bucket" op (it refreshes the get_maps source first), so declare
            # it here to surface the rooms in setup. (Label is Eufy-flavored — a
            # per-brand step label is a later UX polish.)
            # anchor: CN0QXDWS  discovery source — Roborock's id<->name map lives ONLY in the service response
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
            # LIVE POSE. The parsed MapData carries `vacuum_position` already in the RENDERED
            # frame (vacuum-map-parser projects it through the same ImageDimensions.to_img the
            # room bboxes use), so there is nothing to load and nothing to calibrate — the
            # reader just finds the map and reads the pose. No attr lists: those describe the
            # Eufy fork's pixel coordinator, and needing none of them is the whole reason
            # `backend` is a declaration instead of core sniffing which keys are present.
            #
            # WHY THIS BLOCK DID NOT EXIST, since the absence looked deliberate. Two readers
            # of one map diverged: map_source_runtime.overlays_from_mapdata produced
            # robot_anchor for the CARD (live 2026-08-09: sensor.ivy_map_overlays carried
            # [0.694, 0.509] moving across a run), while async_get_map_live_pose — what the
            # stall capture and the pose sampler ask — required a declaration here and got
            # none, so it answered "not_configured". Same map, same refresh, one consumer
            # served and one told the brand had no position. A debug capture over that run
            # held 386 ivy log lines, none of them about pose.
            #
            # ~30s because that is the map REFRESH, not our sampling rate: 17 distinct
            # anchors over ~8 minutes on Ivy (2026-08-09) is one new position per ~28s.
            # Polling faster re-reads the same object, so the trail window derives from THIS
            # number, not from how often the sampler ticks.
            "live_pose": {
                "backend": "parsed_mapdata",
                "pose_refresh_s": 30.0,
            },
        },

        "map_render": {
            # Re-decode the raw map blob's SEGMENT layer to a per-pixel room-id raster so the
            # card renders per-room (colour / floor textures / hit-test) instead of the
            # overlapping bboxes the parser exposes. vacuum-map-parser reads the pixel layer
            # to colour rooms then DISCARDS it, but the raw bytes survive on the v1 MapContent
            # (`raw_api_response`, cached in HA memory). The render reader walks the same
            # `hass_data_domain` runtime_data roots as map_state_source, finds the MapContent,
            # and decodes it (mapping/roborock_raw_map.py). v1 (S6 / Q-class) only. The room
            # raster is self-contained, and the pose overlay's coord registration is no
            # longer outstanding: measured aligned on Ivy 2026-08-09 (max_center_delta
            # 0.0018, min_iou 0.949, 10/10 rooms) — see roborock_raw_map.roborock_render_data.
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

        "room_attribution": {
            # Recover WHICH managed rooms an EXTERNAL (app-started) run cleaned. Unlike Eufy
            # — which raster-looks-up the robot pixel in an on-disk decoded map (source:
            # live_pose) — Roborock PUBLISHES the live room directly as a NAME sensor
            # (sensor.<id>_current_room = entities.active_cleaning_target), so
            # `source: native_current_room` makes the pose sampler read that entity, slugify
            # the name, and match it to a managed room id (listeners/pose_sampler.py).
            #
            # ⚠ was: "No decoded-map pose is decoded here (anchor/heading stay None)." False
            # since the pose wiring landed; corrected 2026-08-24 (ledger L14). `source`
            # selects how the ROOM is read, NOT whether a position is recorded — the two are
            # separate facts with separate best sources.
            # pose_sampler._read_native_current_room_sample banks BOTH `anchor` and `heading`
            # from async_get_map_live_pose on every non-docked tick where the adapter declares
            # `map_state_source.live_pose` — which THIS adapter does, in its own
            # `map_state_source` block above:
            # `"live_pose": {"backend": "parsed_mapdata", "pose_refresh_s": 30.0}`. Its
            # own docstring records the change: the literal None "was the only thing keeping
            # the pose ring anchor-less, which in turn is why a stall capture had no trail to
            # draw". They stay None only when no pose is declared, when the robot is parked, or
            # when the pose read misses — and the engine's swept-area path attributes pose-free
            # in that case, as it always did. Read as authority the old sentence said Roborock
            # captures carry no position, which is exactly the "a brand having no dot for
            # months" state listeners/stall_capture.py now emits a receipt to detect.
            #
            # The engine is brand-AGNOSTIC despite the Eufy-flavoured name: eufy_anchor_winding_v1's
            # ROBUST clean-vs-transit decision keys on the cleaning_area (swept m²) delta over each
            # current-room segment, which needs NO pose — the pose-only spread/winding just degrade
            # to display labelling, which the swept-area path already covers. Recorder-verified on
            # Ivy (2026-07-11): current_room tracks the live room even on app-started runs and
            # reverts to the dock room when parked; task_status → charging on dock nulls it (the
            # dwell/swept-area separate cleaned from transit) — see reference_roborock_ivy_signals.
            #
            # LIVE. R2-STALE-4 sibling — not in the original finding, found by diffing this
            # claim against its Eufy copy: this said "DORMANT until the consumption wire (W3):
            # the sampler buffers pose_samples but nothing attributes them yet". They are
            # attributed — room_attribution_engines._segment_by_room consumes the buffer.
            "engine": "eufy_anchor_winding_v1",
            "source": "native_current_room",
            "tuning": {
                # current_room re-emits ON CHANGE only, so SAMPLE PERIODICALLY at a cadence fine
                # enough to resolve dwell (Eufy's fork pose is 2s; Ivy cleaning_area updates ~15s).
                # dwell_min_ticks × interval_s = 15s minimum hold to count a room.
                "interval_s": 5.0,
                "dwell_min_ticks": 3,
                "swept_area_min_m2": 0.5,
            },
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
            # The path/route axis is per-MODEL though, so read the catalog rather than
            # baking the S6's answer into the brand.
            "supports_path_control": profile.get("has_path_control", False),
            "supports_edge_mopping": False,
            # ⚠ "No dock" IS THE S6's ANSWER, DECLARED AT BRAND LEVEL, AND IT WINS.
            #
            # `dock.py::dock_profile` resolves the vendor's real answers and passes them
            # to `detect_capabilities` as hints (`dock_washable` / `dock_dryable` /
            # `dock_collectable`, ~600 lines above). These three literals then say False
            # regardless. The two dictionaries agree only when no dock is found.
            #
            # Worse, the hints cannot survive a refresh: this brand persists neither its
            # capability hints nor its model family, so a capability refresh re-derives
            # from THIS block. Dock support is then a hint OR a wash-entity presence, and
            # there is no wash entity among the declared candidates. The card hides the
            # Base Station tab on these same literals, so no amount of correct dock
            # detection can turn that tab on for a dock-having Roborock.
            #
            # Left as-is in a prose pass because the fix is a real change with a real
            # blast radius — either these read from `dock_profile` like
            # `supports_path_control` reads from the catalog directly above, or the
            # brand persists its hints so a refresh stops overwriting them. Both are
            # capability-surface decisions, not comment edits. Same family as D18:
            # resolved at one end, hardcoded at the other, and it reads as deliberate.
            "supports_mop_wash": False,
            "supports_mop_dry": False,
            "supports_empty_dust": False,
            "supports_station_water": False,
            "supports_robot_position": caps.get("supports_robot_position", False),
            # Conservative defaults pending a live segment-clean run (Wave 2).
            "position_lock_reliable": False,
            "rooms_unique_per_job": False,
            # Reusable room PROFILES bundle multiple per-room settings (mode, water,
            # intensity, passes, edge). Gated on mop_settable: the S6 exposes only
            # per-room fan (mode/water global/unsettable), so a "profile" would be a
            # degenerate named fan speed — hidden. A settable-mop model (S7/S8) also
            # exposes clean_mode + water_level per room, so a bundle is meaningful —
            # the profiles section appears, same as Eufy.
            "supports_room_profiles": mop_settable,
            # app_segment_clean path-optimizes and IGNORES the dispatched order
            # (confirmed on-device): order is honored only when set as a Sequence
            # in the Roborock app. So the card's queue order is advisory — surfaced
            # at run start. (Eufy honors order via send_command -> default True.)
            "honors_clean_order": False,
            # Zone clean (draw-a-box) via app_zoned_clean (device-mm; see dispatch.
            # zone_command). The S6 supports zoned cleaning through stock send_command; the
            # card un-rotates the drawn rect so it works at any display rotation.
            # Read from caps rather than hardcoded, so a model catalog entry can declare
            # supports_zone_clean False and be believed (see capabilities._hint_wins).
            "supports_zone_clean": caps.get("supports_zone_clean", True),
            # app_zoned_clean device limits (S6, likely all Roborock): at most 5 zones per
            # call, each between 1 ft² and 32.8 ft². Count is enforced in the card (zoneMax
            # via the snapshot) + dispatch (defence-in-depth); size in dispatch_zone_clean
            # after the mm conversion (the card draws in % and can't know the mm size).
            "zone_max": 5,
            "zone_min_area_m2": 0.0929,   # 1 ft²
            "zone_max_area_m2": 3.05,     # 32.8 ft²
        },

        "maintenance_components": {
            # Sourced from maintenance_components.py. Life-tracked consumables carry a
            # remaining-hours countdown sensor + an inline reset button; guide-only
            # cleanables (maintenance_only) carry neither and default their intervals
            # to 0. label/icon are mandatory (bare-deref'd).
            #
            # `remaining_is_state` used to be projected here with a False default, which
            # put it on all 12 components though only 4 declared it — and nothing read it
            # on any of them. Pruned with its source declarations; see
            # maintenance_components.py. (R2-STALE-5: said 13; there are 12.)
            component_id: {
                "sensor_suffix": component.get("sensor_suffix"),
                "proxy_for": component.get("proxy_for"),
                "maintenance_only": component.get("maintenance_only", False),
                "default_interval_hours": component.get("default_interval_hours", 0.0),
                "max_interval_hours": component.get("max_interval_hours", 0.0),
                "label": component["label"],
                "icon": component["icon"],
                # reset_button is omitted entirely for guide-only cleanables
                # (schema: dict-or-absent, "Absent = no reset button" — never None).
                **(
                    {"reset_button": component["reset_button"]}
                    if component.get("reset_button")
                    else {}
                ),
            }
            for component_id, component in MAINTENANCE_COMPONENTS.items()
        },

        "upkeep_catalog": {
            # The guide half of maintenance: per-model how-to steps / notes /
            # frequencies, mirroring the Eufy adapter's upkeep_catalog. The manager
            # picks guide_library[model_guide_families[device.model]][component] and
            # overlays a localized copy per field (guide_translations). Those are
            # POPULATED: adapters/roborock/upkeep_guides_i18n/ holds 17 language
            # modules (ar cs de es fr he id it ja ko nl pl pt ru tr zh_hans zh_hant),
            # transcribed from the vendor's own manuals. This said "Phase 2 — empty
            # today, so guides render in English" until 2026-08-23, at the exact site
            # someone checks to decide whether localization work is outstanding.
            # See adapters/roborock/
            # roborock_upkeep_guides.py + upkeep_catalog.py.
            "model_names": ROBOROCK_MODEL_NAMES,
            "model_guide_families": ROBOROCK_MODEL_GUIDE_FAMILIES,
            "guide_family_names": ROBOROCK_GUIDE_FAMILY_NAMES,
            "guide_library": ROBOROCK_UPKEEP_GUIDE_LIBRARY,
            "guide_translations": ROBOROCK_UPKEEP_GUIDE_TRANSLATIONS,
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
        #   dock_events, post_job_wash_amendment, water_model_configs,
        #   settings_selects, anomaly, live_transition.
        #
        # room_profiles is NO LONGER omitted. "Framework defaults suffice" was wrong for
        # this one: the in-code catalog is EUFY's (Eufy declares it by reference), so
        # omitting the block gave every Roborock room Eufy display vocabulary — "Max",
        # "Off", "Quick" — none of which is in this brand's own option lists. A new room's
        # "Max" was dropped by the per_room_live_settings options_key filter (no suction
        # applied at all) and rendered as no-chip-selected in the card's strict-equality
        # chip row. Same profile KEYS as the framework catalog so stored rooms and the
        # profile picker keep working; only the VALUES are Roborock's.
        "room_profiles": {
            "default_profile": "vacuum_quick",
            "builtins": ROOM_PROFILES,
            "custom_template": CUSTOM_ROOM_PROFILE,
            "normalize_defaults": CUSTOM_ROOM_PROFILE,
            "floor_type_water_defaults": RB_FLOOR_TYPE_WATER_DEFAULTS,
            "floor_type_fan_defaults": RB_FLOOR_TYPE_FAN_DEFAULTS,
            # DECLARED EMPTY, not absent. Roborock has no retired profile names of
            # its own to map, and there is no longer a framework catalog to inherit
            # Eufy's from. Empty says "this brand supports the contract and has
            # none"; ABSENT would say "the declaration is incomplete" and is a
            # validation error — the two must not be the same state.
            "legacy_aliases": {},
        },

        # RP-033/VAC-3: the FULL probe-candidate dict built above — a later
        # capabilities REFRESH (core/manager.refresh_vacuum_capabilities) reads
        # this back instead of rebuilding a reduced one-candidate-per-key dict
        # from `entities` alone. See the matching comment in
        # adapters/eufy/adapter.py for the full rationale. Leading underscore:
        # adapter-internal, not part of the user-facing schema surface.
        "_entity_candidates": entity_candidates,
        # live:ENT-12 — WHICH declared ids resolve_declared_entities had to
        # rescue. Discarded until now, which is why the System table labelled a
        # rescued entity "name match" when its name plainly does not match.
        "_entity_remaps": entity_remaps,
        # The user's explicit choices, so a capability REFRESH reproduces the same
        # detect_capabilities inputs as registration. See the matching comment in
        # adapters/eufy/adapter.py — the storage/options merge and its precedence
        # rule live in __init__.py and must not be re-derived downstream.
        "_entity_overrides": dict(entity_overrides or {}),
        "_reserved_suffixes": list(ALL_SUFFIXES),
    }

    register_adapter_config(vacuum_entity_id, config)
    _LOGGER.debug(
        "roborock_adapter: registered config for %s (adapter_id=%s, model=%s, family=%s)",
        vacuum_entity_id,
        ADAPTER_ID,
        detected_model,
        profile["family"],
    )
