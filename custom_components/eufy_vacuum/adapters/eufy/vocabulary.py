"""
Eufy-specific state vocabulary for the job lifecycle evaluator.

These are the raw string values emitted by the Eufy/robovac_mqtt
integration across the dock_status and task_status sensor entities.
They are matched case-insensitively after .strip().lower().

A port to a different vacuum brand must replace these sets with the
equivalent strings from that brand's HA integration.

See porting-guide.md § lifecycle state mapping for the full
mapping protocol.
"""

# Dock/task states that hard-block job start.
# The vacuum or dock is performing a service action that cannot be
# interrupted. These are Eufy firmware strings for wash, recycle,
# and dust empty cycles.
HARD_SERVICE_STATES: frozenset[str] = frozenset({
    "washing",
    "washing mop",
    "recycling waste water",
    "recycling wastewater",
    "emptying dust",
    "emptying dust bin",
    "dust emptying",
})

# Dock states that produce a warning but do not block job start.
# Drying is allowed to proceed — the dock continues drying after
# the job starts.
DRYING_STATES: frozenset[str] = frozenset({
    "drying",
    "drying mop",
    "drying pads",
    "mop drying",
})

# Task status strings that indicate the vacuum is actively running
# a job. Used to set has_observed_active_lifecycle and to detect
# vacuum_busy state.
# Note: "cleaning" and "returning" also appear in
# HA_ACTIVE_VACUUM_STATES below — both sources are checked.
ACTIVE_RUN_TASK_STATES: frozenset[str] = frozenset({
    "cleaning",
    "room cleaning",
    "spot cleaning",
    "returning",
    "resuming",
    "navigating",
})

# Vacuum entity states that indicate the vacuum is active or faulted.
# Values marked [HA standard] are part of the HA vacuum platform
# state machine and apply to all brands. Values marked [Eufy] are
# Eufy-specific and may not appear on other brands.
HA_ACTIVE_VACUUM_STATES: frozenset[str] = frozenset({
    "cleaning",   # [HA standard]
    "returning",  # [HA standard]
    "paused",     # [HA standard]
    "error",      # [HA standard]
})

# Mapping of framework event type keys to the raw dock_status strings
# that trigger them. The keys are framework-invented event type names
# used by record_dock_event() and get_dock_events(). The values are
# Eufy/robovac_mqtt dock_status sensor strings matched
# case-insensitively after .strip().lower().
#
# A port to a different brand replaces the trigger string sets with
# whatever dock_status values that brand's integration emits for the
# equivalent dock actions.
#
# A brand with no mop station omits "last_mop_wash" and "last_dry_start".
# A brand with no dust emptying omits "last_dust_empty".
# The framework iterates whatever keys are present — absent keys produce
# no events and no counters.
DOCK_EVENT_TRIGGERS: dict[str, frozenset[str]] = {
    "last_mop_wash": frozenset({"washing", "washing mop"}),
    "last_dust_empty": frozenset({
        "emptying dust",
        "emptying dust bin",
        "dust emptying",
    }),
    "last_dry_start": frozenset({
        "drying",
        "drying mop",
        "drying pads",
        "mop drying",
    }),
}

# === WATER LEVEL ALIASES =================================================
# Maps Eufy-specific water level string variants to the framework
# canonical water level keys: "off", "low", "medium", "high".
#
# Keys are the raw strings the Eufy integration may emit, normalized to
# .strip().lower() before lookup. Values are the framework canonical keys.
#
# The canonical keys themselves ("off", "low", "medium", "high") are not
# in this map — they pass through unchanged in the normalizer.
# A brand whose integration uses different water level strings provides
# its own alias map and passes it to _normalize_water_level_key().

WATER_LEVEL_ALIASES: dict[str, str] = {
    # Eufy-specific aliases
    "quiet": "low",
    "automatic": "medium",
    "auto": "medium",
    "strong": "high",
}

# === WASH FREQUENCY MODE ALIASES =========================================
# Maps Eufy-specific wash frequency mode string variants to the framework
# canonical mode keys: "by_room", "by_time", "off".
#
# Keys are the raw strings the Eufy select entity may emit, normalized to
# .strip().lower() with hyphens and underscores replaced by spaces before
# lookup. Values are the framework canonical keys.
#
# Used by both _derive_wash_frequency_config() in the manager and
# _normalize_wash_frequency_mode() in the estimator.
# A brand with different wash frequency mode strings provides its own
# alias map and passes it to those functions.

WASH_FREQUENCY_MODE_ALIASES: dict[str, str] = {
    # By-room variants
    "by room": "by_room",
    "room": "by_room",
    "byroom": "by_room",
    # By-time variants
    "by time": "by_time",
    "time": "by_time",
    "bytime": "by_time",
    # Off variants
    "off": "off",
    "disabled": "off",
    "none": "off",
}

# === PROFILE SETTING ALIASES =============================================
# Map Eufy clean-mode / clean-intensity / suction(fan-speed) DISPLAY strings to
# the canonical codes the card's vocab is keyed on (vocab.clean_mode.* etc.).
#
# Why these exist: room-profile settings are stored as un-normalized display
# strings (mixed case, spaces — e.g. "Vacuum and mop", "Standard", "BoostIQ"),
# so their card-side slug (lowercased, non-alnum -> "_") would miss the vocab
# key and fall back to English. The learning manager normalizes through these
# maps before emitting, so the card always receives a canonical code.
#
# Keys are normalized to .strip().lower() with non-alphanumerics collapsed to a
# single space before lookup (see _normalize_profile_setting). Canonical codes
# already equal their own slug, so they pass through unchanged and need no entry
# — only display variants that DON'T slug to the canonical code go here.
#
# A port to another brand provides its own maps (Roborock's Gentle/Balanced/
# Turbo/Max+/Custom, etc.) and exposes them under the same adapter_config keys.

# Canonical codes: vacuum, mop, vacuum_mop.
CLEAN_MODE_ALIASES: dict[str, str] = {
    "vacuum and mop": "vacuum_mop",
    "vacuum mop": "vacuum_mop",
    "vacuum & mop": "vacuum_mop",
    "vacuum plus mop": "vacuum_mop",
    "mop and vacuum": "vacuum_mop",
}

# Canonical cleaning-path codes: quick, narrow, deep. "standard" / "normal" are DEAD —
# they were never real Eufy device paths (the app offers Quick/Narrow/Deep), only a
# legacy default that rendered as an empty chip. Fold them to quick so a stored/observed
# "Standard" or "Normal" normalizes to a real path in learning keys too (the room-field
# resolver does the same for display/dispatch — see profiles/room_profiles.py).
CLEAN_INTENSITY_ALIASES: dict[str, str] = {
    "standard": "quick",
    "normal": "quick",
}

# Canonical codes: quiet, gentle, standard, boost, turbo, max.
# "BoostIQ" is Eufy's auto-boost label -> canonical "boost".
FAN_SPEED_ALIASES: dict[str, str] = {
    "boost iq": "boost",
    "boostiq": "boost",
}

# === ERROR SENTINEL VALUES ===============================================
# String values that the Eufy/robovac_mqtt error_message sensor may emit
# that mean "no error is present". Anything not in this set is treated as
# a real error string.
#
# Values marked [HA standard] appear across all HA integrations in
# unavailable/unknown states.
# Values marked [Eufy] are specific to the robovac_mqtt error vocabulary.
#
# A port to a different brand verifies whether its error sensor uses the
# same sentinel vocabulary or adds brand-specific values.

# === CANCEL SERVICE EXCLUSION STATES =====================================
# Task status strings that, if seen in a transition during a very short job,
# explain why the vacuum returned early without it being a manual cancel.
# When any of these strings appears in the transition history the cancel
# detection check is suppressed.
#
# [Eufy firmware] strings observed in robovac_mqtt task_status recordings:
#   "returning to charge"  — low-battery return triggered by firmware
#   "charging (resume)"    — mid-job charging pause
#   "returning to wash"    — mop wash service cycle
#   "washing mop"          — mop wash underway
#   "returning to empty"   — dust empty service cycle
#   "emptying dust"        — dust empty underway
#
# A port to a different brand replaces these with equivalent strings from
# that brand's task_status vocabulary.

CANCEL_SERVICE_EXCLUSION_STATES: frozenset[str] = frozenset({
    "returning to charge",
    "charging (resume)",
    "returning to wash",
    "washing mop",
    "returning to empty",
    "emptying dust",
})


NOT_ERROR_SENTINELS: frozenset[str] = frozenset({
    "",            # [HA standard] empty state
    "unknown",     # [HA standard] HA unavailable sentinel
    "unavailable", # [HA standard] HA unavailable sentinel
    "none",        # [Eufy] error_code=0 → "NONE" branch in robovac_mqtt
    "normal",      # [Eufy] "Normal" state string from robovac_mqtt
})


# ---------------------------------------------------------------------------
# Fault policy (RF-DOCK) -- SOURCE, and whether the fault invalidates cleaning evidence
# ---------------------------------------------------------------------------
# WHY THIS EXISTS. total_error_seconds is subtracted from cleaning_time_seconds, so a
# fault that never stopped the robot cleaning silently zeroes a productive run. Observed
# live: alfred job_2026-08-01T23-23-35 cleaned 4 m2 for 360 s and recorded
# cleaning_time_seconds 0, because five STATION CLEAN WATER PUMP SHORT (6013) faults --
# the dock complaining while the robot was out on the floor -- were charged against it.
# used_for_learning was true, so the model learned that 4 m2 takes no time.
#
# TWO DIMENSIONS, BOTH STATIC. Source alone does not answer the question the defect
# poses. The failure was not a mislabel; it was a DOCK FAULT INVALIDATING A RUN'S
# LEARNING EVIDENCE. And the two dimensions genuinely diverge: STATION RETURN FAILED is
# robot-sourced but happens after the floor work, so the evidence stands.
#
# WHY NOT ASK THE TIMELINE. An earlier draft resolved the second dimension at runtime --
# "was the robot cleaning when this fired?". Rejected: the fault timestamp is when Eufy
# SURFACED the fault, not when it occurred, so the correlation is unsound at its base.
# It also fails when the timeline is absent or partial, and turns a deterministic adapter
# lookup into a state-dependent heuristic that cannot be audited. The finite code already
# names WHICH OPERATION FAILED; that is an administrative judgment, and administrative
# judgments belong in a table a human can read and correct.
#
# Codes and names are Eufy's own (robovac_mqtt const.EUFY_CLEAN_ERROR_CODES, 200 entries).
# Eufy prefixes most station faults "STATION", but the prefix is NOT the rule: 7031/7033/
# 7055 are STATION-named and robot-sourced, and several station faults carry no prefix at
# all (41 airdryer, 70 dust collector, 73/74 tanks, 79/82 tray, 81 sewage).
#
# BOTH SETS ARE DECLARED. A code in neither resolves to UNKNOWN, and unknown NEVER
# invalidates -- an unrecognised fault must not be subtracted, because that is the failure
# this table fixes. Eufy ships new codes; ours goes stale by design and degrades safely.

#: Faults belonging to the STATION. The robot can be cleaning normally throughout.
EUFY_DOCK_SOURCED_ERROR_CODES: frozenset[int] = frozenset({
    41,      # AIRDRYER HEATER ABNORMAL -- the airdryer lives in the station
    70,      # CLEAN DUST COLLECTOR -- dust collector is the station's
    73,      # DIRTY TANK FULL -- station dirty-water tank
    74,      # CLEAN WATER LOW -- station clean-water supply (the ROBOT's own low water is 72)
    79,      # CLEAN TRAY NOT INSTALLED -- cleaning tray is the station's
    81,      # SEWAGE TANK LEAK -- station sewage tank
    82,      # CLEAN TRAY NEEDS CLEAN -- station cleaning tray
    83,      # POOR CHARGING CONTACT -- charging contacts -- only reachable while docked
    5014,    # DOCKING STATION POWER OFF -- the station's power, not the robot's
    6010,    # STATION CLEAN WATER TANK NOT CONNECTED
    6011,    # STATION LOW CLEAN WATER
    6012,    # STATION CLEAN WATER PUMP OPEN
    6013,    # STATION CLEAN WATER PUMP SHORT
    6014,    # STATION VALVE SHORT
    6020,    # STATION DIRTY TANK MISSING
    6021,    # STATION DIRTY TANK FULL
    6022,    # STATION DIRTY PUMP OPEN
    6023,    # STATION DIRTY PUMP SHORT
    6024,    # STATION DIRTY TANK LEAK
    6025,    # STATION FULL DIRTY WATER OR DIRTY WATER TANK NOT CONNECTED
    6030,    # STATION CLEANING TRAY NOT INSTALLED
    6031,    # STATION TRAY FULL
    6032,    # STATION TRAY MISSING/FULL
    6040,    # STATION DRYER OPEN
    6041,    # STATION DRYER SHORT
    6042,    # STATION HEATER OPEN
    6043,    # STATION NTC OPEN
    6110,    # STATION VOLTAGE ERROR
    6111,    # STATION DUST LEAK
    6112,    # STATION DUST AP DUCT BLOCKED
    6113,    # STATION NO DUST BAG INSTALLED
    6114,    # STATION FAN OVERHEAT
    6115,    # STATION BAROMETER ERROR
    6117,    # LOW BATTERY (NO AUTO EMPTY) -- station op blocked BY robot battery; labelled by the blocked function
    6118,    # LOW BATTERY (NO SELF CLEAN) -- as 6117
    6300,    # HAIR CUTTING IN PROGRESS -- station operation in progress; not a fault at all
    6301,    # LOW BATTERY (NO HAIR CUTTING) -- as 6117
    6310,    # POWER FAILURE -- station power
    6311,    # HAIR CUTTING MODULE STUCK -- station hair-cutting module
})

#: Faults belonging to the ROBOT.
EUFY_ROBOT_SOURCED_ERROR_CODES: frozenset[int] = frozenset({
    1,       # CRASH BUFFER STUCK
    2,       # WHEEL STUCK
    3,       # SIDE BRUSH STUCK
    4,       # ROLLING BRUSH STUCK
    5,       # HOST TRAPPED CLEAR OBST
    6,       # MACHINE TRAPPED MOVE
    7,       # WHEEL OVERHANGING
    8,       # POWER LOW SHUTDOWN
    13,      # HOST TILTED
    14,      # NO DUST BOX
    17,      # FORBIDDEN AREA DETECTED
    18,      # LASER COVER STUCK
    19,      # LASER SENSOR STUCK
    20,      # LASER BLOCKED
    21,      # DOCK FAILED -- the ROBOT failed to dock
    26,      # POWER APPOINT START FAIL
    31,      # SUCTION PORT OBSTRUCTION
    32,      # WIPE HOLDER MOTOR STUCK
    33,      # WIPING BRACKET MOTOR STUCK
    39,      # POSITIONING FAIL CLEAN END
    40,      # MOP CLOTH DISLODGED
    50,      # MACHINE ON CARPET
    51,      # CAMERA BLOCK
    52,      # UNABLE LEAVE STATION -- the ROBOT could not leave
    55,      # EXPLORING STATION FAIL -- the ROBOT could not find the station
    71,      # WALL SENSOR FAIL
    72,      # ROBOVAC LOW WATER
    75,      # WATER TANK ABSENT
    76,      # CAMERA ABNORMAL
    77,      # 3D TOF ABNORMAL
    78,      # ULTRASONIC ABNORMAL
    80,      # ROBOVAC COMM FAIL
    101,     # BATTERY ABNORMAL
    102,     # WHEEL MODULE ABNORMAL
    103,     # SIDE BRUSH ABNORMAL
    104,     # FAN ABNORMAL
    105,     # ROLLER BRUSH MOTOR ABNORMAL
    106,     # HOST PUMP ABNORMAL
    107,     # LASER SENSOR ABNORMAL
    111,     # ROTATION MOTOR ABNORMAL
    112,     # LIFT MOTOR ABNORMAL
    113,     # WATER SPRAY ABNORMAL
    114,     # WATER PUMP ABNORMAL
    117,     # ULTRASONIC ABNORMAL
    119,     # WIFI BLUETOOTH ABNORMAL
    1010,    # LEFT WHEEL OPEN CIRCUIT
    1011,    # LEFT WHEEL SHORT CIRCUIT
    1012,    # LEFT WHEEL ABNORMAL
    1013,    # LEFT WHEEL OVERCURRENT
    1020,    # RIGHT WHEEL OPEN CIRCUIT
    1021,    # RIGHT WHEEL SHORT CIRCUIT
    1022,    # RIGHT WHEEL ABNORMAL
    1023,    # RIGHT WHEEL OVERCURRENT
    1030,    # BOTH WHEELS OPEN CIRCUIT
    1031,    # BOTH WHEELS SHORT CIRCUIT
    1032,    # BOTH WHEELS ABNORMAL
    1033,    # BOTH WHEELS OVERCURRENT
    2010,    # FAN OPEN CIRCUIT
    2011,    # FAN SHORT CIRCUIT
    2012,    # FAN ABNORMAL
    2013,    # FAN RPM ABNORMAL
    2020,    # LEFT FAN OPEN CIRCUIT
    2021,    # LEFT FAN SHORT CIRCUIT
    2022,    # LEFT FAN ABNORMAL
    2023,    # LEFT FAN RPM ABNORMAL
    2024,    # RIGHT FAN OPEN CIRCUIT
    2025,    # RIGHT FAN SHORT CIRCUIT
    2026,    # RIGHT FAN ABNORMAL
    2027,    # RIGHT FAN RPM ABNORMAL
    2110,    # ROLLER BRUSH OPEN CIRCUIT
    2111,    # ROLLER BRUSH SHORT CIRCUIT
    2112,    # ROLLER BRUSH OVERCURRENT
    2113,    # ROLLER BRUSH ABNORMAL
    2120,    # FRONT ROLLER BRUSH OPEN CIRCUIT
    2121,    # FRONT ROLLER BRUSH SHORT CIRCUIT
    2122,    # FRONT ROLLER BRUSH OVERCURRENT
    2123,    # REAR ROLLER BRUSH OPEN CIRCUIT
    2124,    # REAR ROLLER BRUSH SHORT CIRCUIT
    2125,    # REAR ROLLER BRUSH OVERCURRENT
    2210,    # SIDE BRUSH OPEN CIRCUIT
    2211,    # SIDE BRUSH SHORT CIRCUIT
    2212,    # SIDE BRUSH ABNORMAL
    2213,    # SIDE BRUSH OVERCURRENT
    2220,    # LEFT SIDE BRUSH OPEN CIRCUIT
    2221,    # LEFT SIDE BRUSH SHORT CIRCUIT
    2222,    # LEFT SIDE BRUSH ABNORMAL
    2223,    # LEFT SIDE BRUSH OVERCURRENT
    2224,    # RIGHT SIDE BRUSH OPEN CIRCUIT
    2225,    # RIGHT SIDE BRUSH SHORT CIRCUIT
    2226,    # RIGHT SIDE BRUSH ABNORMAL
    2227,    # RIGHT SIDE BRUSH OVERCURRENT
    2310,    # DUSTBIN OR FILTER MISSING
    2311,    # DUSTBIN FULL (10H REMINDER)
    3010,    # WATER PUMP OPEN CIRCUIT
    3011,    # WATER PUMP SHORT CIRCUIT
    3012,    # WATER PUMP ABNORMAL
    3013,    # WATER TANK EMPTY
    3020,    # WATER TANK REMOVED
    3110,    # LEFT MOP MISSING
    3111,    # RIGHT MOP MISSING
    3120,    # ROTATION MOTOR OPEN CIRCUIT
    3121,    # ROTATION MOTOR SHORT CIRCUIT
    3122,    # ROTATION MOTOR ABNORMAL
    3123,    # ROTATION MOTOR STUCK
    3130,    # LIFT MOTOR OPEN CIRCUIT
    3131,    # LIFT MOTOR SHORT CIRCUIT
    3132,    # LIFT MOTOR ABNORMAL
    3133,    # LIFT MOTOR STUCK
    4010,    # RADAR COMMUNICATION ERROR
    4011,    # RADAR BLOCKED
    4012,    # RADAR RPM ABNORMAL
    4020,    # GYROSCOPE ABNORMAL
    4030,    # TOF SENSOR ERROR
    4031,    # TOF SENSOR BLOCKED
    4040,    # CAMERA SENSOR ERROR
    4041,    # CAMERA BLOCKED
    4090,    # WALL SENSOR ERROR
    4091,    # WALL SENSOR BLOCKED
    4111,    # LEFT BUMPER STUCK
    4112,    # RIGHT BUMPER STUCK
    4120,    # ULTRASONIC ERROR (CLEANING)
    4121,    # ULTRASONIC ERROR (IDLE)
    4130,    # LIDAR COVER STUCK
    5010,    # BATTERY OPEN CIRCUIT
    5011,    # BATTERY SHORT CIRCUIT
    5012,    # CHARGING CURRENT TOO LOW
    5013,    # DISCHARGE CURRENT TOO HIGH
    5015,    # LOW BATTERY (NO SCHEDULED CLEAN)
    5016,    # CHARGING CURRENT TOO HIGH
    5017,    # CHARGING VOLTAGE ABNORMAL
    5018,    # BATTERY TEMP ABNORMAL
    5021,    # DISCHARGE TEMP HIGH
    5022,    # DISCHARGE TEMP LOW
    5023,    # CHARGE TEMP HIGH
    5024,    # CHARGE TEMP LOW
    5110,    # WIFI ERROR
    5111,    # BLUETOOTH ERROR
    5112,    # IR COMMUNICATION ERROR
    7000,    # SMALL SPACE TIMEOUT
    7001,    # MACHINE SUSPENDED
    7002,    # MACHINE PICKED UP
    7003,    # DROP SENSOR TRIGGERED
    7004,    # MACHINE STUCK
    7010,    # ENTERED NO-GO ZONE
    7011,    # ENTERED CARPET
    7020,    # GLOBAL POSITIONING FAILED
    7021,    # POSITIONING FAILED
    7031,    # STATION RETURN FAILED CLEAR AREA -- STATION-prefixed, but it is the robot that failed to return
    7033,    # STATION EXPLORATION FAILED -- as 7031
    7034,    # CANNOT FIND START POINT
    7035,    # DOCKING FAILED (NO POWER)
    7036,    # DOCKING FAILED (WHEEL STUCK)
    7037,    # DOCKING FAILED (IR REFLECTION)
    7040,    # UNDOCKING FAILED
    7050,    # UNREACHABLE TARGET
    7051,    # SCHEDULE FAILED
    7052,    # PATH PLANNING FAILED
    7053,    # MACHINE TILTED
    7054,    # FOLLOW TARGET LOST
    7055,    # STATION NOT FOUND -- as 7031 -- the robot cannot find the station
})

# The DEFAULT policy is the source: a dock fault leaves the floor work valid, a robot
# fault compromises it. Only the exceptions are enumerated, so the judgment calls are
# visible and correctable instead of buried across 200 rows.
#
#: Robot-sourced faults that DO NOT invalidate cleaning evidence -- they happen before or
#: after the floor work, or describe a state rather than a failure.
EUFY_EVIDENCE_SAFE_ROBOT_CODES: frozenset[int] = frozenset({
    17,     # FORBIDDEN AREA DETECTED -- informational; the robot obeyed it
    21,     # DOCK FAILED -- after the clean
    26,     # POWER APPOINT START FAIL -- the run never began
    52,     # UNABLE LEAVE STATION -- before the clean
    55,     # EXPLORING STATION FAIL -- not floor work
    5012,   # CHARGING CURRENT TOO LOW -- docked
    5015,   # LOW BATTERY (NO SCHEDULED CLEAN) -- the run never began
    5016,   # CHARGING CURRENT TOO HIGH -- docked
    5017,   # CHARGING VOLTAGE ABNORMAL -- docked
    7010,   # ENTERED NO-GO ZONE -- informational
    7011,   # ENTERED CARPET -- informational
    7031,   # STATION RETURN FAILED CLEAR AREA -- after the clean
    7033,   # STATION EXPLORATION FAILED -- not floor work
    7035,   # DOCKING FAILED (NO POWER) -- after the clean
    7036,   # DOCKING FAILED (WHEEL STUCK) -- after the clean
    7037,   # DOCKING FAILED (IR REFLECTION) -- after the clean
    7040,   # UNDOCKING FAILED -- before the clean
    7051,   # SCHEDULE FAILED -- the run never began
    7055,   # STATION NOT FOUND -- after the clean
})


def eufy_error_source(code: object) -> str:
    """Return "dock", "robot", or "unknown" for one Eufy error code.

    Unknown is a real answer, not a fallback to the majority class: Eufy adds codes and
    this table will go stale, and a consumer that treated an unrecognised fault as
    robot-sourced would resume zeroing productive runs the moment that happens.
    """
    rid = _exact_error_code(code)
    if rid is None:
        return "unknown"
    if rid in EUFY_DOCK_SOURCED_ERROR_CODES:
        return "dock"
    if rid in EUFY_ROBOT_SOURCED_ERROR_CODES:
        return "robot"
    return "unknown"


def eufy_error_invalidates_cleaning(code: object) -> bool:
    """Does this fault mean the run's cleaning evidence cannot be trusted?

    THE question the learning consumer needs; ``eufy_error_source`` answers the other
    one (whose hardware to point the user at). Only a robot-sourced fault that is not on
    the evidence-safe list invalidates.

    Defaults to False for dock, unknown, and unclassified codes -- deliberately. Wrongly
    crediting a run adds noise that averages out; wrongly zeroing one destroys a real
    observation and teaches the model that area takes no time, which is the incident this
    table exists to prevent.
    """
    rid = _exact_error_code(code)
    if rid is None or rid in EUFY_EVIDENCE_SAFE_ROBOT_CODES:
        return False
    return rid in EUFY_ROBOT_SOURCED_ERROR_CODES


def _exact_error_code(code: object) -> int | None:
    """Coerce to an error code, or None. NEVER int(): int(3.7) is 3, a real code (SIDE
    BRUSH STUCK), so a malformed value would silently classify as a genuine robot fault
    and be subtracted. Same lying-coercion class as get_battery_level's ``-> int``.
    bool is an int subclass, so True would otherwise resolve to code 1."""
    if isinstance(code, bool):
        return None
    if isinstance(code, int):
        return code
    if isinstance(code, str):
        try:
            return int(code.strip())
        except (TypeError, ValueError):
            return None
    return None
