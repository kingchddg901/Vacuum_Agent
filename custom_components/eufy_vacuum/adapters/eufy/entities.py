"""
Eufy/robovac_mqtt entity name patterns and builder for the Eufy adapter.

The Eufy/robovac_mqtt integration names companion sensor entities by
appending a known suffix to the vacuum entity's object_id:

    sensor.{object_id}_task_status
    binary_sensor.{object_id}_charging
    select.{object_id}_wash_frequency_mode
    etc.

This is the "object_id_suffix" naming strategy. It is the only strategy
implemented here. A brand whose integration uses a different naming
convention (e.g. a prefix before the object_id, or a completely
different derivation) should implement its own builder and pass it
wherever build_entity_id is currently called.

The mapping subsystem's position entities (robot_position_x_raw,
robot_position_y_raw) are not included here — they are managed by the
mapping subsystem directly.
"""

# === LIFECYCLE / JOB =====================================================
# Core entities watched by the lifecycle listener and job finalizer.

SUFFIX_TASK_STATUS = "_task_status"
SUFFIX_DOCK_STATUS = "_dock_status"
SUFFIX_ACTIVE_MAP = "_active_map"
SUFFIX_ACTIVE_CLEANING_TARGET = "_active_cleaning_target"
SUFFIX_CLEANING_TIME = "_cleaning_time"
SUFFIX_CLEANING_AREA = "_cleaning_area"
SUFFIX_BATTERY = "_battery"
SUFFIX_ERROR_MESSAGE = "_error_message"

# binary_sensor domain — note the domain differs from the sensor group above.
SUFFIX_CHARGING = "_charging"

# === WATER / WASH ========================================================
# Entities used by the water estimation and wash frequency systems.

SUFFIX_WASH_FREQUENCY_MODE = "_wash_frequency_mode"        # select domain
SUFFIX_WASH_FREQUENCY_VALUE_TIME = "_wash_frequency_value_time"  # number domain
SUFFIX_DRY_DURATION = "_dry_duration"                      # select domain
SUFFIX_WATER_LEVEL = "_water_level"                        # sensor domain

# === LIFETIME TOTALS / DIAGNOSTIC (robovac_mqtt v1.11.0+) =================
# Device-reported lifetime usage totals + dock firmware. Absent on older
# integration versions and on models that don't report them — the snapshot
# reads each state and omits any that's missing, so the card degrades cleanly.

SUFFIX_TOTAL_CLEANING_AREA = "_total_cleaning_area"        # sensor (lifetime m²)
SUFFIX_TOTAL_CLEANING_TIME = "_total_cleaning_time"        # sensor (lifetime seconds)
SUFFIX_TOTAL_CLEANING_COUNT = "_total_cleaning_count"      # sensor (lifetime job count)
SUFFIX_DOCK_FIRMWARE_VERSION = "_dock_firmware_version"    # sensor (diagnostic)

# === ENTITY DOMAINS ======================================================
# HA entity domain prefixes used by build_entity_id().

DOMAIN_SENSOR = "sensor"
DOMAIN_BINARY_SENSOR = "binary_sensor"
DOMAIN_SELECT = "select"
DOMAIN_NUMBER = "number"
DOMAIN_BUTTON = "button"

# === NAMING STRATEGIES ===================================================
# Controls how build_entity_id() constructs the full entity ID from the
# vacuum entity ID and a suffix.
#
# STRATEGY_OBJECT_ID_SUFFIX — Eufy/robovac_mqtt convention:
#   {domain}.{object_id}{suffix}
#   e.g. sensor.alfred_task_status
#   This is the only implemented strategy.
#
# STRATEGY_PREFIX_OBJECT_ID — placeholder for brands whose integration
#   names entities as {prefix}_{object_id} rather than appending a suffix.
#   Not implemented. A port using this convention should replace
#   build_entity_id() with its own implementation and leave this constant
#   as documentation of the extension point.

STRATEGY_OBJECT_ID_SUFFIX = "object_id_suffix"
STRATEGY_PREFIX_OBJECT_ID = "prefix_object_id"  # extension point — not implemented

# === BUILDER =============================================================

def build_entity_id(
    vacuum_entity_id: str,
    suffix: str,
    domain: str = DOMAIN_SENSOR,
    *,
    strategy: str = STRATEGY_OBJECT_ID_SUFFIX,
) -> str:
    """Return the full HA entity ID for one companion entity.

    Parameters
    ----------
    vacuum_entity_id:
        The vacuum entity ID, e.g. ``"vacuum.alfred"``.
    suffix:
        The entity suffix constant, e.g. ``SUFFIX_TASK_STATUS``.
    domain:
        The HA entity domain, e.g. ``DOMAIN_SENSOR``. Defaults to
        ``"sensor"``.
    strategy:
        Naming strategy. Only ``STRATEGY_OBJECT_ID_SUFFIX`` is
        implemented. Pass a different value to surface the extension
        point — a ``NotImplementedError`` will be raised so the gap
        is visible rather than silent.

    Returns
    -------
    str
        Full entity ID, e.g. ``"sensor.alfred_task_status"``.

    Raises
    ------
    NotImplementedError
        If ``strategy`` is not ``STRATEGY_OBJECT_ID_SUFFIX``.
    """
    if strategy != STRATEGY_OBJECT_ID_SUFFIX:
        raise NotImplementedError(
            f"Entity naming strategy '{strategy}' is not implemented in the "
            f"Eufy adapter. To support a different naming convention, replace "
            f"build_entity_id() with your own implementation."
        )
    object_id = vacuum_entity_id.split(".", 1)[-1]
    return f"{domain}.{object_id}{suffix}"
