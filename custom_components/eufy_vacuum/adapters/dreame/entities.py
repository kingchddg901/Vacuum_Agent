"""Dreame (Tasshack ``dreame_vacuum`` integration) entity name patterns + builder.

The ``dreame_vacuum`` integration names companion entities with an object_id-suffix
convention:

    sensor.{object_id}_task_status
    sensor.{object_id}_current_room
    binary_sensor.{object_id}_charging_state
    camera.{object_id}_map
    select.{object_id}_room_{n}_cleaning_mode
    ...

so ``build_entity_id`` is the generic object_id-suffix builder (kept local to keep
adapters independent — Eufy/Roborock own their own copies). Only the SUFFIX constants
are Dreame-specific. Suffixes verified against the live ``vacuum.robin`` entity set
(dreame.vacuum.r2469a, 216 entities) on 2026-08-29.

Dreame vs Roborock naming deltas worth flagging (each cost nothing here but a wrong
guess ships a silent unresolved role):
  * per-run area is ``_cleaned_area`` (Roborock: ``_cleaning_area``); lifetime is
    ``_total_cleaned_area``.
  * battery is ``_battery_level`` (Roborock: ``_battery``).
  * charging is a dedicated ``binary_sensor._charging_state`` (there is ALSO a
    ``sensor._charging_status`` enum; the binary is the lifecycle signal).
  * the lifecycle enum is ``sensor._task_status`` (there are also ``_state`` and
    ``_status`` human-facing enums — task_status is the machine one completion reads).
  * cleaning_time / total_cleaning_time are in MINUTES (declared via
    ``cleaning_time_unit='min'`` in the adapter config).
"""

from __future__ import annotations

# === LIFECYCLE / JOB =====================================================
SUFFIX_TASK_STATUS = "_task_status"              # sensor — machine lifecycle enum (completion reads this)
SUFFIX_STATUS = "_status"                        # sensor — human status enum (observability)
SUFFIX_STATE = "_state"                          # sensor — HA-mirrored state enum
SUFFIX_ACTIVE_CLEANING_TARGET = "_current_room"  # sensor — native live-room (segment cleans)
SUFFIX_ACTIVE_MAP = "_selected_map"              # select — multi-map pointer (options: ["Main"])
SUFFIX_CLEANING_TIME = "_cleaning_time"          # sensor — per-run MINUTES
SUFFIX_CLEANING_AREA = "_cleaned_area"           # sensor — per-run m2
SUFFIX_CLEANING_HISTORY = "_cleaning_history"    # sensor — timestamp; carries completed/cancelled
SUFFIX_CLEANING_COUNT = "_cleaning_count"        # sensor — lifetime completed runs
# Lifetime halves of the per-run pair — declared so they enter ALL_SUFFIXES and the
# live:ENT-4 exclusivity guard can tell a per-run metric from its lifetime namesake
# (``_cleaned_area`` matches ``_total_cleaned_area`` under an endswith test).
SUFFIX_TOTAL_CLEANING_AREA = "_total_cleaned_area"   # sensor — lifetime m2
SUFFIX_TOTAL_CLEANING_TIME = "_total_cleaning_time"  # sensor — lifetime minutes
SUFFIX_BATTERY = "_battery_level"                # sensor — %
SUFFIX_ERROR_MESSAGE = "_error"                  # sensor — enum error string

# station / dock
SUFFIX_DOCK_STATUS = "_self_wash_base_status"    # sensor — station wash/dry enum
                                                 # (idle/washing/drying/paused/returning/...)

# binary_sensor domain
SUFFIX_CHARGING = "_charging_state"              # binary_sensor — dedicated charging signal

# camera domain
SUFFIX_MAP = "_map"                              # camera — the live map (rooms/pose/calibration)

# === ENTITY DOMAINS ======================================================
DOMAIN_SENSOR = "sensor"
DOMAIN_BINARY_SENSOR = "binary_sensor"
DOMAIN_SELECT = "select"
DOMAIN_NUMBER = "number"
DOMAIN_BUTTON = "button"
DOMAIN_CAMERA = "camera"
DOMAIN_SWITCH = "switch"


#: Every entity suffix this adapter knows, derived from the ``SUFFIX_*`` constants
#: rather than hand-listed (a hand list drifts the moment a suffix is added, and the
#: two halves of a per-run/lifetime collision must be declared apart from each other).
#: Consumed as ``reserved_suffixes`` so sibling matching can tell when a LONGER
#: declared suffix already owns an entity (arms the live:ENT-4 guard).
ALL_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        {
            value
            for name, value in list(globals().items())
            if name.startswith("SUFFIX_") and isinstance(value, str) and value
        }
    )
)


def build_entity_id(
    vacuum_entity_id: str,
    suffix: str,
    domain: str = DOMAIN_SENSOR,
) -> str:
    """Return the full HA entity ID for one companion entity.

    Object_id-suffix strategy: ``{domain}.{object_id}{suffix}``, e.g.
    ``build_entity_id("vacuum.robin", "_task_status")`` -> ``"sensor.robin_task_status"``.
    """
    object_id = vacuum_entity_id.split(".", 1)[-1]
    return f"{domain}.{object_id}{suffix}"


def build_room_entity_id(
    vacuum_entity_id: str,
    room_index: int,
    field: str,
    domain: str = DOMAIN_SELECT,
) -> str:
    """Return a per-room companion entity ID.

    Dreame exposes per-room settings as ``{domain}.{object_id}_room_{n}_{field}``,
    e.g. ``select.robin_room_1_cleaning_mode`` / ``number.robin_room_2_wetness_level``.
    Room index is 1-based, matching the device's own ``_room_N_*`` numbering.
    """
    object_id = vacuum_entity_id.split(".", 1)[-1]
    return f"{domain}.{object_id}_room_{room_index}_{field}"
