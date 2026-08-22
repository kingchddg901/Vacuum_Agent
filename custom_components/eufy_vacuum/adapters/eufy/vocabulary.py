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

# The RETIRED intensity names, mapped to what they MEANT.
#
# "Standard" was not a phantom. The original YAML system declared
# vacuum_clean_intensity as Fast / Standard / Deep with Standard as the INITIAL
# value — it was the middle pass density, deliberately chosen. robovac_mqtt still
# accepts it: CLEAN_EXTENT_MAP maps "standard" -> CleanExtent.NORMAL (0), the middle,
# and lists fast/standard/deep together as "legacy keys" precisely because they are
# that original vocabulary.
#
# A 2026-07-26 commit folded Standard/Normal to "quick" on the premise that they
# "were never real Eufy cleaning-path values". That premise was wrong, and the fold
# moved every affected room from the MIDDLE density to the FASTEST one — a real
# reduction in cleaning, chosen by nobody.
#
# Today's names reach those same three device values as:
#     Quick  -> quick  -> QUICK  (2)   the original "Fast"
#     Narrow -> normal -> NORMAL (0)   the original "Standard"
#     Deep   -> narrow -> NARROW (1)   the original "Deep"
# so a retired "standard"/"normal" belongs on "narrow", not "quick".
CLEAN_INTENSITY_ALIASES: dict[str, str] = {
    "fast": "quick",
    "standard": "narrow",
    "normal": "narrow",
}

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
    # 5014 was HERE, on upstream's "DOCKING STATION POWER OFF". Eufy's own protos
    # say otherwise -- it is a ROBOT battery shutdown. Moved; see the 501x block.
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
    # 5014 -- upstream robovac_mqtt calls this "DOCKING STATION POWER OFF" and we
    # mirrored it, which put a ROBOT battery shutdown in the dock set and therefore
    # in EVIDENCE_SAFE ("the robot can be cleaning normally throughout"). It cannot:
    # the run ended because the pack died, so its cleaning evidence is truncated by
    # definition. Corrected against Eufy's OWN error protos (robovac_mqtt/proto/
    # cloud/error_code_list_{standard,t2080}.proto), which BOTH declare
    #   E5014_LOW_BATTERY_SHUTDOWN = 5014;  // 电量低关机
    # Three further confirmations: every neighbour 5010-5018 is a battery code;
    # 5015 ("low battery, cannot schedule") upstream got RIGHT, so the block is
    # unambiguous; and the real station-has-no-power concept lives at 7035
    # (E7035_RIDING_FAILURE_BASE_STATION_NOT_POWERED_ON), which we already map.
    # NOT evidence-safe -- unlike 5015, this one interrupts a run in progress.
    5014,    # LOW BATTERY SHUTDOWN (upstream mislabels it; see above)
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


# ---------------------------------------------------------------------------
# ⚠ NO PRODUCTION CALLER YET, AND THAT IS DELIBERATE — DO NOT DELETE.
#
# `eufy_error_source`, `eufy_error_invalidates_cleaning` and their `_exact_error_code`
# helper are complete, tested (tests/adapters/eufy/test_error_source.py) and reached
# from nowhere in the shipped tree. They are waiting on their DATA SOURCE, not on a
# consumer decision:
#
#     jeppesens/eufy-clean PR #161 — "feat: capture and persist the full ErrorCode
#     proto" — opened 2026-07-26, OPEN as of 2026-08-21.
#
# Until that lands upstream the fork does not surface the fault detail these tables
# classify, so wiring a caller now would classify data that does not arrive. The seam
# is built ahead of the source on purpose (build the expansion-ready seam, ship the
# tiny surface); the tables and their reasoning were authored while the codes were
# fresh in hand, which is the only time that reasoning is cheap to write down.
#
# ⚠ WHY THIS NOTE EXISTS AT ALL. A reachability sweep on 2026-08-21 found these three
# functions callerless and queued them for deletion alongside a genuinely dead
# int-coercion island in core (ledger C18, correctly removed). Nothing in the code
# said the difference. The two cases are indistinguishable to any tool — same zero
# callers, same green suite when broken — and only the upstream PR separates them.
# Ledger C20 records the same observation and must be read WITH this note, not
# against it.
#
# WHEN #161 LANDS: wire the consumer, delete this banner, and C20 closes by becoming
# false rather than by anyone deciding anything.
# ---------------------------------------------------------------------------


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


# The two sets CORE consumes. Core asks exactly one question -- "does this fault mean the
# run's cleaning evidence cannot be trusted?" -- and the adapter answers it. Core never
# learns an Eufy code [[feedback_eufy_ism_leak_layers]]; the derivation lives here.
#
# Declared as two sets rather than one so a code in NEITHER is visibly unclassified. With
# a single set, an unrecognised fault would be indistinguishable from a deliberately-safe
# one, and the whole point of this table is that unknown must be a real answer.

#: Faults after which the run's cleaning evidence cannot be trusted. Core subtracts these.
EUFY_EVIDENCE_INVALIDATING_ERROR_CODES: frozenset[int] = (
    EUFY_ROBOT_SOURCED_ERROR_CODES - EUFY_EVIDENCE_SAFE_ROBOT_CODES
)

#: Faults that leave the floor work valid -- every station fault, plus the robot faults
#: that bracket the clean rather than interrupt it. Core preserves these.
EUFY_EVIDENCE_SAFE_ERROR_CODES: frozenset[int] = (
    EUFY_DOCK_SOURCED_ERROR_CODES | EUFY_EVIDENCE_SAFE_ROBOT_CODES
)


#: Eufy fault code -> i18n key. The STRINGS live in the frontend locale packs; this maps
#: the vendor's numbers onto them so core can hand the card a key without ever learning an
#: Eufy code [[feedback_eufy_ism_leak_layers]].
#:
#: Codes with identical MEANING deliberately share a key -- 106/114/3012 are all the
#: robot's water pump, and Eufy ships several strings twice across its legacy and
#: structured bands (78/117, 103/2212, 104/2012, 111/3122, 112/3132).
#:
#: A code absent from this map has NO label and the card falls back to the raw number,
#: which is also what a brand declaring nothing gets. NEVER invent a label for an unknown
#: code -- the raw number is honest, a guessed label is not.
EUFY_ERROR_LABEL_KEYS: dict[int, str] = {
    1: "fault.eufy.bumper_stuck",
    2: "fault.eufy.wheel_stuck",
    3: "fault.eufy.side_brush_stuck",
    4: "fault.eufy.roller_brush_stuck",
    5: "fault.eufy.robot_is_trapped_clear_the_obstacles_around",
    6: "fault.eufy.robot_is_trapped",
    7: "fault.eufy.wheel_overhanging",
    8: "fault.eufy.power_low_shutdown",
    13: "fault.eufy.robot_tilted",
    14: "fault.eufy.dust_bin_missing",
    17: "fault.eufy.forbidden_area_detected",
    18: "fault.eufy.laser_cover_stuck",
    19: "fault.eufy.laser_sensor_stuck",
    20: "fault.eufy.laser_blocked",
    21: "fault.eufy.dock_failed",
    26: "fault.eufy.scheduled_clean_could_not_start",
    31: "fault.eufy.suction_port_obstruction",
    32: "fault.eufy.wipe_holder_motor_stuck",
    33: "fault.eufy.wiping_bracket_motor_stuck",
    39: "fault.eufy.lost_position_cleaning_ended_early",
    40: "fault.eufy.mop_cloth_dislodged",
    41: "fault.eufy.base_station_mop_dryer_heater_fault",
    50: "fault.eufy.robot_on_carpet",
    51: "fault.eufy.camera_blocked",
    52: "fault.eufy.could_not_leave_the_base_station",
    55: "fault.eufy.could_not_find_the_base_station",
    70: "fault.eufy.clean_dust_collector",
    71: "fault.eufy.wall_sensor_fault",
    72: "fault.eufy.robot_low_water",
    73: "fault.eufy.dirty_tank_full",
    74: "fault.eufy.clean_water_low",
    75: "fault.eufy.water_tank_absent",
    76: "fault.eufy.camera_fault",
    77: "fault.eufy.depth_sensor_fault",
    78: "fault.eufy.ultrasonic_sensor_fault",
    79: "fault.eufy.clean_tray_not_installed",
    80: "fault.eufy.lost_connection_to_the_robot",
    81: "fault.eufy.sewage_tank_leak",
    82: "fault.eufy.clean_tray_needs",
    83: "fault.eufy.poor_charging_contact",
    101: "fault.eufy.battery_fault",
    102: "fault.eufy.wheel_module_fault",
    103: "fault.eufy.side_brush_fault",
    104: "fault.eufy.suction_fan_fault",
    105: "fault.eufy.roller_brush_motor_fault",
    106: "fault.eufy.robot_water_pump_fault",
    107: "fault.eufy.laser_distance_sensor_fault",
    111: "fault.eufy.mop_rotation_motor_fault",
    112: "fault.eufy.mop_lift_motor_fault",
    113: "fault.eufy.mop_water_spray_fault",
    114: "fault.eufy.robot_water_pump_fault",
    117: "fault.eufy.ultrasonic_sensor_fault",
    119: "fault.eufy.wi_fi_or_bluetooth_fault",
    1010: "fault.eufy.left_wheel_motor_not_responding",
    1011: "fault.eufy.left_wheel_motor_electrical_fault",
    1012: "fault.eufy.left_wheel_fault",
    1013: "fault.eufy.left_wheel_jammed_check_for_tangled_hair_or_debris",
    1020: "fault.eufy.right_wheel_motor_not_responding",
    1021: "fault.eufy.right_wheel_motor_electrical_fault",
    1022: "fault.eufy.right_wheel_fault",
    1023: "fault.eufy.right_wheel_jammed_check_for_tangled_hair_or_debris",
    1030: "fault.eufy.both_wheel_motors_not_responding",
    1031: "fault.eufy.both_wheel_motors_electrical_fault",
    1032: "fault.eufy.both_wheels_fault",
    1033: "fault.eufy.both_wheels_jammed_check_for_tangled_hair_or_debris",
    2010: "fault.eufy.suction_fan_not_responding",
    2011: "fault.eufy.suction_fan_electrical_fault",
    2012: "fault.eufy.suction_fan_fault",
    2013: "fault.eufy.suction_fan_not_spinning_correctly",
    2020: "fault.eufy.left_suction_fan_not_responding",
    2021: "fault.eufy.left_suction_fan_electrical_fault",
    2022: "fault.eufy.left_suction_fan_fault",
    2023: "fault.eufy.left_suction_fan_not_spinning_correctly",
    2024: "fault.eufy.right_suction_fan_not_responding",
    2025: "fault.eufy.right_suction_fan_electrical_fault",
    2026: "fault.eufy.right_suction_fan_fault",
    2027: "fault.eufy.right_suction_fan_not_spinning_correctly",
    2110: "fault.eufy.roller_brush_motor_not_responding",
    2111: "fault.eufy.roller_brush_motor_electrical_fault",
    2112: "fault.eufy.roller_brush_jammed_check_for_tangled_hair",
    2113: "fault.eufy.roller_brush_fault",
    2120: "fault.eufy.front_roller_brush_motor_not_responding",
    2121: "fault.eufy.front_roller_brush_motor_electrical_fault",
    2122: "fault.eufy.front_roller_brush_jammed_check_for_tangled_hair",
    2123: "fault.eufy.rear_roller_brush_motor_not_responding",
    2124: "fault.eufy.rear_roller_brush_motor_electrical_fault",
    2125: "fault.eufy.rear_roller_brush_jammed_check_for_tangled_hair",
    2210: "fault.eufy.side_brush_motor_not_responding",
    2211: "fault.eufy.side_brush_motor_electrical_fault",
    2212: "fault.eufy.side_brush_fault",
    2213: "fault.eufy.side_brush_jammed_check_for_tangled_hair",
    2220: "fault.eufy.left_side_brush_motor_not_responding",
    2221: "fault.eufy.left_side_brush_motor_electrical_fault",
    2222: "fault.eufy.left_side_brush_fault",
    2223: "fault.eufy.left_side_brush_jammed_check_for_tangled_hair",
    2224: "fault.eufy.right_side_brush_motor_not_responding",
    2225: "fault.eufy.right_side_brush_motor_electrical_fault",
    2226: "fault.eufy.right_side_brush_fault",
    2227: "fault.eufy.right_side_brush_jammed_check_for_tangled_hair",
    2310: "fault.eufy.dustbin_or_filter_missing",
    2311: "fault.eufy.dustbin_full_10h_reminder",
    3010: "fault.eufy.robot_water_pump_not_responding",
    3011: "fault.eufy.robot_water_pump_electrical_fault",
    3012: "fault.eufy.robot_water_pump_fault",
    3013: "fault.eufy.water_tank_empty",
    3020: "fault.eufy.water_tank_removed",
    3110: "fault.eufy.left_mop_missing",
    3111: "fault.eufy.right_mop_missing",
    3120: "fault.eufy.mop_rotation_motor_not_responding",
    3121: "fault.eufy.mop_rotation_motor_electrical_fault",
    3122: "fault.eufy.mop_rotation_motor_fault",
    3123: "fault.eufy.rotation_motor_stuck",
    3130: "fault.eufy.mop_lift_motor_not_responding",
    3131: "fault.eufy.mop_lift_motor_electrical_fault",
    3132: "fault.eufy.mop_lift_motor_fault",
    3133: "fault.eufy.lift_motor_stuck",
    4010: "fault.eufy.radar_communication_error",
    4011: "fault.eufy.radar_blocked",
    4012: "fault.eufy.lidar_not_spinning_correctly_check_for_a_blockage",
    4020: "fault.eufy.gyroscope_fault",
    4030: "fault.eufy.depth_sensor_fault",
    4031: "fault.eufy.depth_sensor_blocked",
    4040: "fault.eufy.camera_sensor_error",
    4041: "fault.eufy.camera_blocked",
    4090: "fault.eufy.wall_sensor_error",
    4091: "fault.eufy.wall_sensor_blocked",
    4111: "fault.eufy.left_bumper_stuck",
    4112: "fault.eufy.right_bumper_stuck",
    4120: "fault.eufy.ultrasonic_error_cleaning",
    4121: "fault.eufy.ultrasonic_error_idle",
    4130: "fault.eufy.lidar_cover_stuck",
    5010: "fault.eufy.battery_not_responding",
    5011: "fault.eufy.battery_electrical_fault",
    5012: "fault.eufy.charging_current_too_low",
    5013: "fault.eufy.discharge_current_too_high",
    # Was fault.eufy.base_station_power_off — it is the ROBOT's battery, not the
    # station's power (see the 501x block above). Points at the key code 8 already
    # uses: both are a low-battery shutdown, one per code generation, so this reuses
    # a string already translated in all 18 locales rather than inventing a
    # nineteenth. `fault.eufy.base_station_power_off` is left defined but is now
    # mapped by no code.
    5014: "fault.eufy.power_low_shutdown",
    5015: "fault.eufy.low_battery_no_scheduled",
    5016: "fault.eufy.charging_current_too_high",
    5017: "fault.eufy.charging_voltage_fault",
    5018: "fault.eufy.battery_temperature_out_of_range",
    5021: "fault.eufy.discharge_temp_high",
    5022: "fault.eufy.discharge_temp_low",
    5023: "fault.eufy.charge_temp_high",
    5024: "fault.eufy.charge_temp_low",
    5110: "fault.eufy.wi_fi_error",
    5111: "fault.eufy.bluetooth_error",
    5112: "fault.eufy.infrared_link_to_the_base_station_failed",
    6010: "fault.eufy.base_station_clean_water_tank_not_connected",
    6011: "fault.eufy.base_station_low_clean_water",
    6012: "fault.eufy.base_station_clean_water_pump_not_responding",
    6013: "fault.eufy.base_station_clean_water_pump_electrical_fault",
    6014: "fault.eufy.base_station_water_valve_electrical_fault",
    6020: "fault.eufy.base_station_dirty_tank_missing",
    6021: "fault.eufy.base_station_dirty_tank_full",
    6022: "fault.eufy.base_station_dirty_water_pump_not_responding",
    6023: "fault.eufy.base_station_dirty_water_pump_electrical_fault",
    6024: "fault.eufy.base_station_dirty_tank_leak",
    6025: "fault.eufy.base_station_full_dirty_water_or_dirty_water_tank",
    6030: "fault.eufy.base_station_cleaning_tray_not_installed",
    6031: "fault.eufy.base_station_tray_full",
    6032: "fault.eufy.base_station_tray_missing_or_full",
    6040: "fault.eufy.base_station_mop_dryer_not_responding",
    6041: "fault.eufy.base_station_mop_dryer_electrical_fault",
    6042: "fault.eufy.base_station_heater_not_responding",
    6043: "fault.eufy.base_station_temperature_sensor_not_responding",
    6110: "fault.eufy.base_station_power_fault",
    6111: "fault.eufy.base_station_dust_leak",
    6112: "fault.eufy.base_station_dust_duct_blocked",
    6113: "fault.eufy.base_station_no_dust_bag_installed",
    6114: "fault.eufy.base_station_fan_overheat",
    6115: "fault.eufy.base_station_pressure_sensor_fault",
    6117: "fault.eufy.low_battery_no_auto_empty",
    6118: "fault.eufy.low_battery_no_self",
    6300: "fault.eufy.hair_cutting_in_progress",
    6301: "fault.eufy.low_battery_no_hair_cutting",
    6310: "fault.eufy.power_failure",
    6311: "fault.eufy.hair_cutting_module_stuck",
    7000: "fault.eufy.took_too_long_in_a_small_space",
    7001: "fault.eufy.robot_suspended",
    7002: "fault.eufy.robot_picked_up",
    7003: "fault.eufy.drop_sensor_triggered",
    7004: "fault.eufy.robot_stuck",
    7010: "fault.eufy.entered_no_go_zone",
    7011: "fault.eufy.entered_carpet",
    7020: "fault.eufy.global_positioning_failed",
    7021: "fault.eufy.positioning_failed",
    7031: "fault.eufy.could_not_return_to_the_base_station_clear_the_area",
    7033: "fault.eufy.base_station_exploration_failed",
    7034: "fault.eufy.cannot_find_start_point",
    7035: "fault.eufy.docking_failed_no_power",
    7036: "fault.eufy.docking_failed_wheel_stuck",
    7037: "fault.eufy.could_not_dock_something_reflective_is_confusing",
    7040: "fault.eufy.undocking_failed",
    7050: "fault.eufy.unreachable_target",
    7051: "fault.eufy.schedule_failed",
    7052: "fault.eufy.path_planning_failed",
    7053: "fault.eufy.robot_tilted",
    7054: "fault.eufy.lost_the_target_it_was_following",
    7055: "fault.eufy.base_station_not_found",
}
