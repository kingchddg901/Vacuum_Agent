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
