"""Roborock lifecycle + dropdown vocabulary for the Roborock adapter.

Grounded in the captured ``vacuum.ivy`` enums (``sensor.ivy_status``,
``sensor.ivy_vacuum_error``, ``vacuum.ivy`` ``fan_speed_list``,
``select.ivy_mop_intensity`` / ``_mop_mode``) and the live run trace
(2026-06-14), which observed: cleaning, paused, error, returning_home, charging,
segment_cleaning, plus the two obstacle errors ``bumper_stuck`` /
``wheels_suspended``.
"""

from __future__ import annotations

# ``sensor.ivy_status`` values that mean "a job is actively running" — lets the
# framework mark active from the status string in addition to the HA-standard
# ``vacuum.state``. Dock/wash/dry states the no-dock S6 never emits are omitted.
ACTIVE_RUN_TASK_STATES: set[str] = {
    "starting",
    "cleaning",
    "spot_cleaning",
    "zoned_cleaning",
    "segment_cleaning",
    "segment_mopping",
    "going_to_target",
    "returning_home",
    "docking",
}

# ``sensor.ivy_vacuum_error`` sentinel values meaning "no error". The idle value
# is ``none``; ``normal`` is an Eufy-only sentinel and is intentionally excluded
# (a Roborock error code could legitimately contain it).
NOT_ERROR_SENTINELS: set[str] = {"", "unknown", "unavailable", "none"}

# Cancel-detection transition strings consumed by learning/job_finalizer.py
# (_detect_cancel_likely_run): a too-short active->returning (or paused->returning)
# run is flagged as a likely cancel so it doesn't pollute per-room learning
# estimates. Roborock's return state is ``returning_home`` (NOT the framework
# default ``returning``), and its "actively cleaning" status is mode-specific, so
# ``active`` is a LIST (the finalizer matches a pre-return transition from any of
# them). Confirmed in the run trace (status reaches returning_home, never bare
# returning).
CANCEL_DETECTION_STATES: dict = {
    "active": ["cleaning", "spot_cleaning", "zoned_cleaning", "segment_cleaning", "segment_mopping"],
    "returning": "returning_home",
    "paused": "paused",
}

# Card-facing dropdown option lists (the framework never reads these).
# fan_speed from ``vacuum.ivy`` ``fan_speed_list``, ordered ASCENDING SUCTION
# (Gentle weakest -> Max strongest) for the editor chip row — the device lists
# them in a different order (gentle last), but the user reads them low->high.
# This order also matches the dispatch global-pre-call rank.
FAN_SPEED_OPTIONS: list[dict] = [
    {"value": "gentle", "label": "Gentle"},
    {"value": "quiet", "label": "Quiet"},
    {"value": "balanced", "label": "Balanced"},
    {"value": "turbo", "label": "Turbo"},
    {"value": "max", "label": "Max"},
]

# water_level from ``select.ivy_mop_intensity`` (off/low/medium/high) — maps 1:1
# onto the canonical water_level vocabulary (locked decision).
WATER_LEVEL_OPTIONS: list[dict] = [
    {"value": "off", "label": "Off"},
    {"value": "low", "label": "Low"},
    {"value": "medium", "label": "Medium"},
    {"value": "high", "label": "High"},
]

# clean_mode is a FRAMEWORK-logical control on Roborock, not a device select: it
# never reaches the app_segment_clean wire (room_fields omits it). It gates whether
# water applies (the shared resolver forces water Off for "vacuum") and drives the
# per-group mop pre-call — so "vacuum" a group (mop intensity -> off, a dry pass) vs
# "mop"/"vacuum_mop" it (mop intensity -> the group's water_level). Only meaningful,
# and only exposed, on a mop_settable model.
CLEAN_MODE_OPTIONS: list[dict] = [
    {"value": "vacuum", "label": "Vacuum"},
    {"value": "mop", "label": "Mop"},
    {"value": "vacuum_mop", "label": "Vacuum & Mop"},
]

# ``select.ivy_mop_mode`` (standard/deep) is a Roborock-only GLOBAL axis with no
# canonical framework slot (locked decision: global-only, set pre-dispatch). Kept
# here for the card / future dispatch pre-call wiring, not exposed as a canonical
# vocabulary key yet.
MOP_MODE_OPTIONS: list[dict] = [
    {"value": "standard", "label": "Standard"},
    {"value": "deep", "label": "Deep"},
]


# --- room profiles -----------------------------------------------------------
#
# Roborock's own room-profile catalog. Declared rather than inherited: the framework's
# in-code catalog is Eufy's (Eufy declares it BY REFERENCE), so a brand that omits this
# block silently gets Eufy DISPLAY vocabulary — "Max", "Off", "Quick" — in its rooms.
#
# That was not theoretical. It is why `dispatch.per_room_live_settings` for fan_speed
# carries an `options_key` filter: a new room's "Max" is not in FAN_SPEED_OPTIONS, so the
# filter dropped it and an unedited Roborock room got NO suction applied at all, while the
# card's chip row (a strict `===` against option values) rendered nothing as selected.
#
# Values below come straight from FAN_SPEED_OPTIONS / WATER_LEVEL_OPTIONS /
# CLEAN_MODE_OPTIONS above, which are read off the live entities. Same profile KEYS as the
# framework catalog so stored rooms and the card's profile picker keep working across a
# brand switch; only the VALUES are Roborock's.
#
# clean_intensity is OMITTED from every profile on purpose — Roborock exposes no intensity
# axis (see the adapter's `clean_intensity_options`, deliberately absent). An omitted key
# means the room stores nothing for it, rather than an inert "Quick" nobody can act on.
ROOM_PROFILES: dict[str, dict] = {
    "vacuum_quick": {
        "label": "Vacuum Only Quick",
        "clean_mode": "vacuum",
        "fan_speed": "balanced",
        "water_level": "off",
        "path_type": "wide",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_deep": {
        "label": "Vacuum Only Deep",
        "clean_mode": "vacuum",
        "fan_speed": "max",
        "water_level": "off",
        "path_type": "narrow",
        "clean_passes": 2,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_mop_quick": {
        "label": "Quick",
        "clean_mode": "vacuum_mop",
        "fan_speed": "balanced",
        "water_level": "medium",
        "path_type": "wide",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": True,
    },
    "vacuum_mop_deep": {
        "label": "Deep",
        "clean_mode": "vacuum_mop",
        "fan_speed": "max",
        "water_level": "medium",
        "path_type": "narrow",
        "clean_passes": 2,
        # The adapter used to contradict itself here: this was the only one of the
        # five profiles in this file requesting edge_mopping, while adapter.py
        # declares supports_edge_mopping False brand-wide (:179 and :610). A
        # profile asking for a capability its own adapter says does not exist.
        #
        # WHAT WAS DELIBERATELY NOT DONE, because the obvious reading is backwards:
        # do NOT gate the card on supports_edge_mopping. That flag is a HARDCODED
        # brand-wide literal with no model gating — unlike the Eufy adapter, which
        # asks `model_family in {...}` for its per-model capabilities — so it is a
        # per-model fact frozen at brand level. Gating on it would hide the control
        # on EVERY Roborock, including models that can edge mop. Chris's S6 cannot;
        # that is a model fact, not a brand fact.
        #
        # So the declaration stays False and the request goes away, which is the
        # Q12 precedent: unsupported and unsurfaced until independently verified,
        # then add a real per-model declaration rather than widening a guess.
        "edge_mopping": False,
        "mop_required": True,
    },
}

CUSTOM_ROOM_PROFILE: dict = {
    "label": "User Profile 1",
    "clean_mode": "vacuum",
    "fan_speed": "balanced",
    "water_level": "off",
    "path_type": "wide",
    "clean_passes": 1,
    "edge_mopping": False,
    "mop_required": False,
}

# Carpet suppresses water and raises suction; hard floors get a per-surface water default.
# The resolver reads the carpet entry of FLOOR_TYPE_WATER_DEFAULTS as this brand's
# no-water value, so "off" here is load-bearing, not decorative.
FLOOR_TYPE_WATER_DEFAULTS: dict[str, str] = {
    "hardwood": "low",
    "laminate": "low",
    "tile": "medium",
    "marble": "low",
    "carpet_low_pile": "off",
    "carpet_high_pile": "off",
}

FLOOR_TYPE_FAN_DEFAULTS: dict[str, str] = {
    "carpet_low_pile": "max",
    "carpet_high_pile": "turbo",
}


# --- error classification ----------------------------------------------------
#
# RF-DOCK clauses 4/5, declared HERE rather than inline in adapter.py so both brands
# put the same concept in the same place -- Eufy's live in eufy/vocabulary.py and its
# adapter only references them. An earlier pass dumped these as string literals into
# the Roborock adapter's config dict; two brands declaring one concept in two shapes
# is how the pair goes stale.
#
# CODES ARE ENUM STRINGS, not the numbers Eufy uses: sensor.{id}_vacuum_error carries
# `bumper_stuck`, not 1. Core normalizes through `_code_key`, which lowercases string
# keys, so every string below must be lowercase to match.
#
# VERIFIED 2026-08-05 against the live instance (frontend/get_translations, category
# "entity", integration ["roborock"]): HA serves 53 vacuum_error enum states and all
# 60 strings declared below are real ones -- no typos, and a typo here would silently
# match nothing rather than fail. 44 of the 53 are classified; the 9 left out are
# listed at the bottom of this block.
#
# THE SOURCE SETS ARE READ, NOT MEASURED, AND THAT IS THE RIGHT BAR (Chris,
# 2026-08-05): "These are error states. I don't need to see them to know that certain
# errors would block a run." Hardware testing verifies BEHAVIOUR; this is a TAXONOMY.
# `dirty_water_box` cannot be robot hardware on any model that has ever shipped. Note
# Ivy is an S6 with NO dock (supports_base_station False), so the dock rows are
# unverifiable on this hardware by construction.

#: Faults raised by the station. Ivy has no dock, so none of these can ever fire here.
ROBOROCK_DOCK_SOURCED_ERROR_CODES: frozenset[str] = frozenset({
    "collect_dust_error_3",         # auto-empty
    "collect_dust_error_4",
    "dirty_water_box_hoare",        # waste tank -- station-side by construction
    "sink_strainer_hoare",          # wash basin
    "strainer_error",
    "up_water_exception",           # station plumbing
    "drain_water_exception",
    "filter_screen_exception",
    "clean_carousel_exception",     # mop-wash carousel
    "clean_carousel_water_full",
    "check_clean_carouse",          # vendor's spelling, not a typo of ours
})

#: Faults raised by the robot itself.
ROBOROCK_ROBOT_SOURCED_ERROR_CODES: frozenset[str] = frozenset({
    "lidar_blocked", "bumper_stuck", "vertical_bumper_pressed",
    "wheels_suspended", "wheels_jammed", "robot_trapped",
    "cliff_sensor_error", "main_brush_jammed", "side_brush_jammed",
    "side_brush_error", "fan_error", "no_dustbin", "filter_blocked",
    "compass_error", "battery_error", "robot_tilted", "wall_sensor_dirty",
    "optical_flow_sensor_dirt", "visual_sensor", "vibrarise_jammed",
})

#: Faults after which the run's cleaning evidence cannot be trusted. Core subtracts
#: these seconds.
#:
#: HAND-DECLARED, and deliberately NOT derived as ``ROBOT - SAFE_ROBOT`` the way Eufy
#: does it. That derivation is valid for Eufy because its table is CLOSED -- the full
#: ErrorCode proto was captured, so "robot-sourced and not explicitly safe" really does
#: mean invalidating. Roborock's is OPEN: a partial classification of a vendor enum with
#: the ambiguous states deliberately left out. Copying the derivation was checked and
#: would be wrong -- SAFE_ROBOT below is DISJOINT from ROBOT_SOURCED, so ``ROBOT -
#: SAFE_ROBOT`` returns all 20 robot codes and would start deducting for
#: `main_brush_jammed`, `fan_error`, `filter_blocked`.
#:
#: INVALIDATING is scoped to the robot being demonstrably IMMOBILE, not to every robot
#: fault. A jammed brush or blocked filter degrades quality while the robot keeps moving
#: and covering floor; deducting that time would destroy a real observation. That is the
#: asymmetry RF-DOCK turns on -- wrongly crediting adds noise that averages out, wrongly
#: zeroing does not.
ROBOROCK_EVIDENCE_INVALIDATING_ERROR_CODES: frozenset[str] = frozenset({
    "wheels_suspended", "wheels_jammed", "robot_trapped",
    "robot_tilted", "bumper_stuck", "vertical_bumper_pressed",
})

#: Robot-side events whose cleaning evidence still stands: navigation and
#: informational states that are not faults at all, plus faults that can only fire
#: AFTER the clean finished or DURING dock washing -- where timing settles the question
#: even when the hardware boundary does not.
ROBOROCK_EVIDENCE_SAFE_ROBOT_CODES: frozenset[str] = frozenset({
    "nogo_zone_detected", "invisible_wall_detected",     # obeyed, not failed
    "cannot_cross_carpet", "robot_on_carpet",
    "dock", "dock_locator_error", "return_to_dock_fail",  # after the clean
    "charging_error", "low_battery", "audio_error",
    "mopping_roller_1", "mopping_roller_2", "mopping_roller_error_2",
})

#: Faults that leave the floor work valid. Core preserves these seconds.
#: DERIVED, so the 11 dock codes are written once -- they were previously transcribed
#: into both this list and the dock list, and a transcribed block diverges silently.
ROBOROCK_EVIDENCE_SAFE_ERROR_CODES: frozenset[str] = (
    ROBOROCK_DOCK_SOURCED_ERROR_CODES | ROBOROCK_EVIDENCE_SAFE_ROBOT_CODES
)

# DELIBERATELY UNCLASSIFIED -- ambiguous by name, so left out rather than guessed:
#   clear_water_box_exception / clear_water_box_hoare  (both robot and dock carry a
#       clean-water tank, model-dependent)
#   clear_brush_exception / clear_brush_exception_2
#   light_touch, internal_error, temperature_protection, water_carriage_drop
# Plus `none`, the idle sentinel (see NOT_ERROR_SENTINELS). Omission lands on
# unclassified/unknown, which preserves the run's seconds and claims nothing -- the
# safe degradation this table relies on. NEVER widen one of these on a hunch; a wrong
# dock/robot call points the user at hardware that is fine.

# NO error_label_keys, and that is a decision rather than an omission.
#
# sensor.{id}_vacuum_error is an HA enum sensor whose 53 states Home Assistant already
# ships translations for, in every language it supports. Minting fault.roborock.* keys
# here would duplicate a table HA maintains and cost 18 packs of our own, which is the
# opposite of [[feedback_kiss_upstream_signals]]. Eufy needs its own table only because
# its codes are bare numbers with no upstream label at all.
#
# HOW THE CARD GETS THE STRING -- VERIFIED 2026-08-05, after an earlier draft asserted
# it as fact without checking. The trap: `hass.states.get(...).state` returns the RAW
# enum; HA translates entity states in the FRONTEND at display time, and the translation
# is not on the state object. This card had never translated an HA state (no
# formatEntityState / computeStateDisplay / hass.localize anywhere in src/).
#
# The key resolves. Probing the live instance in French returned all 53 states under
#     component.roborock.entity.sensor.vacuum_error.state.<enum>
# e.g. bumper_stuck -> "Pare-chocs coince", charging_error -> "Erreur de charge". So
# `hass.localize(...)` with that key is the route. Corroboration worth keeping: HA's
# French for bumper_stuck is byte-identical to our own fr.json fault.eufy.bumper_stuck.
#
# STILL REQUIRED WHEN BUILDING THE LABEL SURFACE -- a fallback. The frontend loads
# translations per integration, so those resources are only present if something has
# already caused them to load; asking for the key does not fetch it, and a miss returns
# EMPTY rather than the enum. So: hass.localize(key) first, then humanise the raw enum
# ("bumper_stuck" -> "Bumper stuck"). Never render an empty string where a fault name
# belongs.
