"""
Eufy/robovac_mqtt button entity candidate lists for the Eufy adapter.

Button entity names are not consistent across robovac_mqtt firmware
versions. Each action has a list of candidate suffixes tried in order,
plus a token fallback list for registry-based discovery when no
candidate matches by name.

Structure per action:
    DOCK_ACTION_CANDIDATES[action] = list of suffix strings (tried in order)
    DOCK_ACTION_TOKENS[action]     = list of token lists (fallback)

A brand with no mop station omits "wash_mop", "dry_mop", "stop_dry_mop"
from its equivalent file. A brand with no dust emptying omits "empty_dust".
The manager iterates whatever keys are present.

Replacement reset buttons follow the same pattern under
RESET_CANDIDATES and RESET_TOKENS.

Note: the exclusion filter applied during reset button discovery
("maintenance" not in entity_id) is manager logic, not adapter data.
It is not represented here.
"""

# === DOCK ACTION BUTTONS =================================================
# Candidate suffix lists for dock action buttons.
# Each suffix is appended to "button.{object_id}" to form a candidate
# entity ID. Tried in order — first match wins.

DOCK_ACTION_CANDIDATES: dict[str, list[str]] = {
    "wash_mop": [
        "_wash_mop",
        "_mop_wash",
    ],
    "dry_mop": [
        "_dry_mop",
        "_mop_dry",
    ],
    "stop_dry_mop": [
        "_stop_dry_mop",
        "_stop_mop_dry",
    ],
    "empty_dust": [
        "_empty_dust",
        "_empty_dust_bin",
    ],
}

# Token fallback lists for dock action buttons.
# Used when no candidate suffix matches by exact entity ID lookup.
# Each entry is a list of tokens that must all appear in the entity ID
# (case-insensitive substring match). Multiple token lists per action
# are tried in order — first match wins.

DOCK_ACTION_TOKENS: dict[str, list[list[str]]] = {
    "wash_mop": [
        ["wash", "mop"],
    ],
    "dry_mop": [
        ["dry", "mop"],
        ["dry", "pad"],
    ],
    "stop_dry_mop": [
        ["stop", "dry", "mop"],
        ["stop", "dry", "pad"],
    ],
    "empty_dust": [
        ["empty", "dust"],
    ],
}

# === REPLACEMENT RESET BUTTONS ===========================================
# Candidate suffix lists for upstream replacement reset buttons.
# Same structure as dock action candidates above.

RESET_CANDIDATES: dict[str, list[str]] = {
    "filter": [
        "_reset_filter",
    ],
    "sensor": [
        "_reset_sensors",
        "_reset_sensor",
    ],
    "side_brush": [
        "_reset_side_brush",
    ],
    "rolling_brush": [
        "_reset_rolling_brush",
    ],
    "mopping_cloth": [
        "_reset_mopping_cloth",
        "_reset_mop_cloth",
    ],
    "cleaning_tray": [
        "_reset_cleaning_tray",
    ],
    "swivel_wheel": [
        "_reset_swivel_replacement",
        "_reset_swivel_wheel",
    ],
}

# Token fallback lists for replacement reset buttons.
# Same structure as dock action tokens above.

RESET_TOKENS: dict[str, list[list[str]]] = {
    "filter": [
        ["reset", "filter"],
    ],
    "sensor": [
        ["reset", "sensor"],
        ["reset", "sensors"],
    ],
    "side_brush": [
        ["reset", "side", "brush"],
    ],
    "rolling_brush": [
        ["reset", "rolling", "brush"],
    ],
    "mopping_cloth": [
        ["reset", "mopping", "cloth"],
        ["reset", "mop", "cloth"],
    ],
    "cleaning_tray": [
        ["reset", "cleaning", "tray"],
    ],
    "swivel_wheel": [
        ["reset", "swivel", "replacement"],
        ["reset", "swivel"],
    ],
}
