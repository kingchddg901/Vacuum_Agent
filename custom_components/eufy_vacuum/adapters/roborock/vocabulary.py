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

# The per-room path/route axis — Roborock's name for pass density. This is the SAME kind
# of axis Eufy calls clean_intensity; each brand declares it under its own name and one
# name only. Whether a given unit OFFERS it is model_catalog.has_path_control; this list
# is what a stored value is judged against, which is what lets the store repair reset a
# value no brand declares (the literal "None" that core's old room backfill wrote).
PATH_TYPE_OPTIONS: list[dict] = [
    {"value": "wide", "label": "Wide"},
    {"value": "narrow", "label": "Narrow"},
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
#
# ⚠ CALLERLESS BY DESIGN, AND VERIFIED SO — do not "tidy" it (ledger C11).
# Twelve declaration surfaces were searched 2026-08-21: the parenthesised import in
# adapter.py, the vocabulary block including its conditional mop_settable spread, the
# mop_pre_calls list, per_room_live_settings (the only options_key literal in the tree
# is "fan_speed_options"), the entity_candidates role map, ADAPTER_CONFIG_SCHEMA (which
# declares five *_options keys and REJECTS undeclared ones), VOCABULARY_FIELDS and the
# generic f"{field}_options" path, both card surfaces, the registry, and dynamic access.
# Reachable by none of them. `git log -S` returns ONE commit: it has been callerless
# SINCE BIRTH — never wired, not unwired, which is a different thing from abandoned.
# The deferral is stated twice independently, here and at the consumption site
# (adapter.py, above mop_pre_calls): "a second GLOBAL select with no canonical
# per-group slot yet -> left out until there is a card control to drive it per group."
#
# ⚠ AND THE REAL RISK IS THE NEIGHBOUR, NOT THIS SYMBOL. A block-level tidy of "the
# unused option lists in this file" takes PATH_TYPE_OPTIONS with it, which IS live:
# rooms/vocabulary_migration.py judges a stored path_type against it. Wiring is not the
# one-line change "wire or delete" implies either — it touches five layers, starting
# with a schema that would reject the key today.
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
# clean_intensity is OMITTED from every profile on purpose — Roborock spells this axis
# `path_type` (below), so declaring both would be one property under two names, which is
# what the Eufy adapter had to be corrected for. An omitted key means the room stores
# nothing for it, rather than an inert "Quick" nobody can act on.
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
# RETIRED IN PRINCIPLE 2026-08-17 — see docs/dev/history/floor-type-cleaning-defaults.md
# The non-carpet rows are a PREFERENCE applied to users who never asked for it: floor_type
# is collected for the map render + the onboarding gate, and nothing ever told the user it
# would also pick a water level. They come out. The CARPET rows STAY — carpet-is-water-off
# is the framework's one guarantee (profiles/room_profiles.py::no_water_value) and is a
# safety property, not a taste. Do not add rows here; add a floor type to the picker only.
FLOOR_TYPE_WATER_DEFAULTS: dict[str, str] = {
    # CARPET ONLY -- this brand's word for "no water", read by
    # profiles/room_profiles.py::no_water_value. The per-surface rows were retired
    # 2026-08-17; see docs/dev/history/floor-type-cleaning-defaults.md.
    "carpet_low_pile": "off",
    "carpet_high_pile": "off",
}

# KEPT deliberately, ruled 2026-08-17 alongside the water-table retirement next
# door. This looks like the same shape and is not: boosting suction on carpet is
# what most vacuums do in firmware anyway, so it meets an expectation rather than
# imposing a preference. The hard-floor WATER rows went because nobody else held
# that opinion. Do not retire this by applying that reasoning mechanically --
# see docs/dev/history/floor-type-cleaning-defaults.md.
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

# --- fault labels -------------------------------------------------------------
#
# Roborock enum state -> OUR i18n key, the same seam Eufy uses. Core hands the card a
# key and never learns a brand's codes [[feedback_eufy_ism_leak_layers]]; the strings
# live in the frontend locale packs.
#
# WE SHIP OUR OWN KEYS RATHER THAN LEANING ON HA'S TRANSLATIONS, and the earlier draft
# of this block argued the opposite. It was wrong on both legs, measured 2026-08-05:
#
#  1. COVERAGE. HA does not have our languages. Probing the live instance for all 18
#     card locales: Arabic 0/53 translated (pure English fallback, inside an RTL layout
#     we do translate fully), Polish 10/53, Indonesian 18/53, and it/nl/ru/zh-Hans
#     83-87%. Only 11 of 18 are complete.
#  2. LANGUAGE RESOLUTION. hass.localize keys off the HA PROFILE language. The card
#     resolves its own via i18n/index.js resolveLang: per-user globe override, then a
#     dashboard config pin, then HA's language. The first two deliberately diverge, so
#     a user who picks German on an English HA would get a German card with English
#     fault names even where HA's German is complete. The per-user language store is
#     precisely what makes the upstream route unusable.
#
# The duplication it avoids is also smaller than claimed: the packs already carry 189
# fault.eufy.* strings each, verified 100% translated across all 17 (3213 strings), so
# these join an existing table rather than starting one.
#
# THREE STATES ARE DELIBERATELY UNMAPPED because HA's own table contradicts its enum
# names and there is no way to tell which side is wrong:
#     clear_brush_exception    -> HA: "Check that the water filter has been correctly
#                                 installed"  (a WATER FILTER message on a BRUSH enum)
#     clear_brush_exception_2  -> HA: "Positioning button error"
#     light_touch              -> HA: "Wall sensor error"
# An unmapped code falls through to the raw enum, which is honest and searchable.
# Naming the wrong part sends someone to disassemble hardware that is fine, so this
# follows the rule the Eufy table already states: never invent a label for a code whose
# meaning is not established.
#
# mopping_roller_1 and mopping_roller_2 SHARE a key -- identical meaning, same
# precedent as Eufy's 106/114/3012 all being the robot's water pump.
ROBOROCK_ERROR_LABEL_KEYS: dict[str, str] = {
    "audio_error": "fault.roborock.audio_error",
    "battery_error": "fault.roborock.battery_error",
    "bumper_stuck": "fault.roborock.bumper_stuck",
    "cannot_cross_carpet": "fault.roborock.cannot_cross_carpet",
    "charging_error": "fault.roborock.charging_error",
    # Vendor's own spelling is "carouse"; our slug is not obliged to inherit the typo.
    "check_clean_carouse": "fault.roborock.check_cleaning_carousel",
    "clean_carousel_exception": "fault.roborock.cleaning_carousel_error",
    "clean_carousel_water_full": "fault.roborock.cleaning_carousel_water_full",
    # "hoare" recurs across three vendor tokens and carries no meaning; slugs are
    # written from what the state MEANS, which is what the map exists to allow.
    "clear_water_box_exception": "fault.roborock.clean_water_tank_empty",
    "clear_water_box_hoare": "fault.roborock.check_clean_water_tank",
    "cliff_sensor_error": "fault.roborock.cliff_sensor_error",
    "collect_dust_error_3": "fault.roborock.clean_auto_empty_dock",
    "collect_dust_error_4": "fault.roborock.auto_empty_dock_voltage_error",
    "compass_error": "fault.roborock.strong_magnetic_field",
    "dirty_water_box_hoare": "fault.roborock.check_dirty_water_tank",
    "dock": "fault.roborock.dock_not_powered",
    "dock_locator_error": "fault.roborock.dock_locator_error",
    "drain_water_exception": "fault.roborock.water_drainage_error",
    "fan_error": "fault.roborock.fan_error",
    "filter_blocked": "fault.roborock.filter_blocked",
    "filter_screen_exception": "fault.roborock.clean_dock_water_filter",
    "internal_error": "fault.roborock.internal_error",
    "invisible_wall_detected": "fault.roborock.invisible_wall_detected",
    "lidar_blocked": "fault.roborock.lidar_blocked",
    "low_battery": "fault.roborock.low_battery",
    "main_brush_jammed": "fault.roborock.main_brush_jammed",
    "mopping_roller_1": "fault.roborock.wash_roller_may_be_jammed",
    "mopping_roller_2": "fault.roborock.wash_roller_may_be_jammed",
    "mopping_roller_error_2": "fault.roborock.wash_roller_not_lowered",
    "no_dustbin": "fault.roborock.dustbin_missing",
    "nogo_zone_detected": "fault.roborock.nogo_zone_detected",
    "optical_flow_sensor_dirt": "fault.roborock.optical_flow_sensor_dirty",
    "return_to_dock_fail": "fault.roborock.could_not_return_to_dock",
    "robot_on_carpet": "fault.roborock.robot_on_carpet",
    "robot_tilted": "fault.roborock.robot_tilted",
    "robot_trapped": "fault.roborock.robot_trapped",
    "side_brush_error": "fault.roborock.side_brush_error",
    "side_brush_jammed": "fault.roborock.side_brush_jammed",
    "sink_strainer_hoare": "fault.roborock.reinstall_water_filter",
    "strainer_error": "fault.roborock.filter_wet_or_blocked",
    "temperature_protection": "fault.roborock.temperature_protection",
    "up_water_exception": "fault.roborock.water_supply_error",
    "vertical_bumper_pressed": "fault.roborock.vertical_bumper_pressed",
    "vibrarise_jammed": "fault.roborock.vibrarise_jammed",
    "visual_sensor": "fault.roborock.camera_error",
    "wall_sensor_dirty": "fault.roborock.wall_sensor_dirty",
    "water_carriage_drop": "fault.roborock.water_carriage_dropped",
    "wheels_jammed": "fault.roborock.wheels_jammed",
    "wheels_suspended": "fault.roborock.wheels_suspended",
}
