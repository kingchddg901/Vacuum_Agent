"""Roborock (HA core integration) entity name patterns + builder.

The HA ``roborock`` integration names companion entities with the same
object_id-suffix convention robovac_mqtt uses:

    sensor.{object_id}_status
    sensor.{object_id}_current_room
    binary_sensor.{object_id}_charging
    ...

so ``build_entity_id`` is the generic object_id-suffix builder (kept local to
keep adapters independent — the Eufy package owns its own copy). Only the SUFFIX
constants below are Roborock-specific. Suffixes verified against the live
``vacuum.ivy`` entity set (2026-06-14).
"""

from __future__ import annotations

# === LIFECYCLE / JOB =====================================================
SUFFIX_TASK_STATUS = "_status"                   # sensor — enum lifecycle string
SUFFIX_ACTIVE_CLEANING_TARGET = "_current_room"  # sensor — native live-room (segment cleans only)
SUFFIX_ACTIVE_MAP = "_selected_map"              # select — multi-map pointer / map identity
SUFFIX_MOP_INTENSITY = "_mop_intensity"          # select — GLOBAL water level (off/low/medium/high)
SUFFIX_CLEANING_TIME = "_cleaning_time"          # sensor — per-run minutes
SUFFIX_CLEANING_AREA = "_cleaning_area"          # sensor — per-run m2
# Clean-summary pair, OBSERVABILITY ONLY (issue #46) — never gates completion.
# Both are written by the same clean-summary fetch, so they agree by construction
# and one can never corroborate the other. Declared so the #46 observation trace
# and diagnostics can read them; see ../../job_active_signal.py.
SUFFIX_LAST_CLEAN_END = "_last_clean_end"        # sensor — timestamp, end of last clean
SUFFIX_TOTAL_CLEANING_COUNT = "_total_cleaning_count"  # sensor — lifetime completed runs
# The LIFETIME halves of the per-run pair above. Not roles this adapter binds —
# nothing here reads a lifetime total — but declared so they enter ALL_SUFFIXES
# and the live:ENT-4 exclusivity guard can tell them apart from their per-run
# namesakes. `_cleaning_area` also matches `..._total_cleaning_area` under an
# endswith test, so a vocabulary that omits the longer suffix lets a per-run
# metric bind to the counter.
#
# Both exist on real hardware: an S6 carries sensor.<obj>_total_cleaning_area
# and sensor.<obj>_total_cleaning_time next to the per-run pair, and the
# entity-resolution design doc records the total reaching the contest on that
# device (only the translation_key rung excluded it).
SUFFIX_TOTAL_CLEANING_AREA = "_total_cleaning_area"    # sensor — lifetime m2
SUFFIX_TOTAL_CLEANING_TIME = "_total_cleaning_time"    # sensor — lifetime minutes
SUFFIX_BATTERY = "_battery"                      # sensor (BATTERY feature bit unset -> this sensor is mandatory)
SUFFIX_ERROR_MESSAGE = "_vacuum_error"           # sensor — enum error-code string

# binary_sensor domain
SUFFIX_CHARGING = "_charging"                    # binary_sensor — dedicated charging signal
SUFFIX_JOB_ACTIVE = "_cleaning"                  # binary_sensor — device inCleaning (stays ON through a recharge dock)
SUFFIX_WATER_BOX = "_water_box_attached"         # binary_sensor — water tank present => mopping (no per-room clean_mode)

# === ENTITY DOMAINS ======================================================
DOMAIN_SENSOR = "sensor"
DOMAIN_BINARY_SENSOR = "binary_sensor"
DOMAIN_SELECT = "select"
DOMAIN_NUMBER = "number"
DOMAIN_BUTTON = "button"


#: Every entity suffix this adapter knows, derived rather than hand-listed.
#:
#: Consumed as ``reserved_suffixes`` so sibling matching can tell when a LONGER
#: declared suffix already owns an entity. Without it this brand shipped with the
#: live:ENT-4 guard UNARMED: replaying the guard's own predicate against this
#: adapter's real map returned ``_claimed_by("ivy_total_cleaning_area") ==
#: "_cleaning_area"`` — the lifetime counter accepted as the per-run sensor —
#: where the same predicate on Eufy correctly returns ``_total_cleaning_area``.
#:
#: Derived from this module's own ``SUFFIX_*`` constants, mirroring
#: adapters/eufy/entities.py: a hand-kept list drifts the moment a suffix is
#: added, and the two halves of the collision are declared apart from each other.
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

    Uses the object_id-suffix strategy: ``{domain}.{object_id}{suffix}``, e.g.
    ``build_entity_id("vacuum.ivy", "_status")`` -> ``"sensor.ivy_status"``.
    """
    object_id = vacuum_entity_id.split(".", 1)[-1]
    return f"{domain}.{object_id}{suffix}"
