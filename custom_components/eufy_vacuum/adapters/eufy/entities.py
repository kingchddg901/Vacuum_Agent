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

⚠ "MANAGED BY THE MAPPING SUBSYSTEM" IS NOT THE WHOLE STORY, and the part it
omits is the part that bites. Those two entity ids are named in THREE places:

  1. here, as an exclusion (this paragraph);
  2. ``adapters/eufy/adapter.py``, which DOES declare them as the
     ``robot_position_x`` / ``robot_position_y`` roles — hardcoded f-strings,
     not built from a suffix constant;
  3. ``core/manager.py::_raw_robot_position``, a third hardcoded copy that
     rebuilds the same ids from the object id and reads them directly.

Copy 3 bypasses the declared role, the entity rescue, and any user override. On an
install where the rescue was what made the entity resolve, the declared role would
resolve and the core copy would still return nothing — the shorter copy is the bug,
and it is the one core reads.

Because those suffixes are not constants in this module, they are also outside
``ALL_SUFFIXES``, and therefore outside the sibling-matching guard that stops one
role's entity being handed to another.

Fixing copy 3 properly means resolving through the declared role, which needs a
vacuum entity id rather than the bare object id it takes today — a signature change,
not a comment. Recorded here so the exclusion above cannot be read as "core does not
touch these".
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


#: Every entity suffix this adapter knows, derived rather than hand-listed.
#:
#: Consumed as ``reserved_suffixes`` by ``detect_capabilities`` so that sibling
#: matching can tell when a LONGER declared suffix already owns an entity:
#: ``_cleaning_area`` also matches ``..._total_cleaning_area``, and without the
#: full vocabulary a per-run metric can silently resolve to the LIFETIME TOTAL
#: (live:ENT-4, confirmed on the issue #49 device).
#:
#: Derived from the module's own ``SUFFIX_*`` constants on purpose: the two
#: halves of that collision are declared in different places, and a hand-kept
#: list would drift the moment a suffix is added. A new ``SUFFIX_*`` constant
#: joins this tuple automatically.
ALL_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        {
            value
            for name, value in list(globals().items())
            if name.startswith("SUFFIX_") and isinstance(value, str) and value
        }
    )
)
