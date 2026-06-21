"""
Per-model water hardware configuration for the Eufy adapter.

Each entry maps a device model number to the physical water tank dimensions
measured on real hardware. These are not calculated values — they are the
actual physical characteristics of the dock and robot for that model.

A port to a different model must re-measure these values and add a new entry.
A model with no dock clean tank (no mop station) omits
dock_clean_tank_capacity_ml and dock_wash_overhead_ml_per_cycle.

The base constants (ROBOT_INTERNAL_TANK_ML etc.) are imported from
constants.py where they are documented with measurement methodology.
"""

from typing import Any

from .constants import (
    DOCK_CLEAN_TANK_CAPACITY_ML,
    DOCK_WASH_OVERHEAD_ML_PER_CYCLE,
    ROBOT_INTERNAL_TANK_ML,
)

WATER_MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "T2351": {
        "robot_internal_tank_ml": ROBOT_INTERNAL_TANK_ML,
        "dock_clean_tank_capacity_ml": DOCK_CLEAN_TANK_CAPACITY_ML,
        "dock_wash_overhead_ml_per_cycle": DOCK_WASH_OVERHEAD_ML_PER_CYCLE,
        # Floor-application water rate (ml/min) per canonical water level, measured on the
        # X10 dock. Lives HERE (brand-owned), not as a default in the planning core — the
        # core reads it via water_model_configs[...]["water_rates"] and otherwise applies a
        # generic neutral rate, so these Eufy numbers never leak onto an unconfigured brand.
        "water_rates": {"off": 0.0, "low": 3.2, "medium": 4.0, "high": 5.3},
    },
}
