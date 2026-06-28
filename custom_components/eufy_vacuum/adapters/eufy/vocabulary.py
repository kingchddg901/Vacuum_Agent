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

# Canonical codes: quick, narrow, deep, normal, standard.
# Eufy's stored values (Quick/Narrow/Deep/Standard/Normal) already slug to the
# canonical code; no display variants need remapping today.
CLEAN_INTENSITY_ALIASES: dict[str, str] = {}

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
