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
SUFFIX_CLEANING_TIME = "_cleaning_time"          # sensor — per-run minutes
SUFFIX_CLEANING_AREA = "_cleaning_area"          # sensor — per-run m2
SUFFIX_BATTERY = "_battery"                      # sensor (BATTERY feature bit unset -> this sensor is mandatory)
SUFFIX_ERROR_MESSAGE = "_vacuum_error"           # sensor — enum error-code string

# binary_sensor domain
SUFFIX_CHARGING = "_charging"                    # binary_sensor — dedicated charging signal
SUFFIX_JOB_ACTIVE = "_cleaning"                  # binary_sensor — device inCleaning (stays ON through a recharge dock)

# === ENTITY DOMAINS ======================================================
DOMAIN_SENSOR = "sensor"
DOMAIN_BINARY_SENSOR = "binary_sensor"
DOMAIN_SELECT = "select"
DOMAIN_NUMBER = "number"
DOMAIN_BUTTON = "button"


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
