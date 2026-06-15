"""Roborock S6 maintenance component catalog.

Each consumable is a remaining-HOURS countdown sensor owned by the HA
``roborock`` integration (``sensor.{object_id}_{sensor_suffix}``) plus a reset
button owned by roborock core (``button.{object_id}_{entity_suffix}``). Reset
buttons are declared inline here (Roborock has no dock-action buttons, so no
separate ``buttons.py``). Rated lives confirmed from the integration diagnostics
(device percent x HA remaining-hours): main 35%/103h, filter 22%/33h, side
2%/3h, sensor ~30h.

SHAPE NOTE vs Eufy: Eufy's source sensor exposes a ``usage_hours`` accumulator
and the FRAMEWORK computes remaining + owns the reset. Roborock's ``*_time_left``
sensors are DEVICE-owned countdowns (no ``usage_hours`` / ``total_life_hours``);
the device counts down and resets itself when its own button is pressed. The
``remaining_is_state`` flag marks "the sensor STATE is remaining-hours; do not
recompute it." Replacement-status already reads the raw state as remaining hours,
so the maintenance status works natively; the flag is consumed by the
framework's parallel remaining model (core seam — Wave 1b) to suppress a stale
duplicate. ``default_interval_hours`` / ``max_interval_hours`` are advisory for
Roborock (the device, not the framework interval, drives the real countdown).
"""

from __future__ import annotations

MAINTENANCE_COMPONENTS: dict[str, dict] = {
    "main_brush": {
        "sensor_suffix": "main_brush_time_left",
        "remaining_is_state": True,
        "reset_button": {
            "entity_suffixes": ["reset_main_brush_consumable"],
            "token_sets": [["reset", "main", "brush"]],
        },
        "default_interval_hours": 300.0,
        "max_interval_hours": 450.0,
        "label": "Main Brush",
        "icon": "mdi:broom",
    },
    "side_brush": {
        "sensor_suffix": "side_brush_time_left",
        "remaining_is_state": True,
        "reset_button": {
            "entity_suffixes": ["reset_side_brush_consumable"],
            "token_sets": [["reset", "side", "brush"]],
        },
        "default_interval_hours": 200.0,
        "max_interval_hours": 300.0,
        "label": "Side Brush",
        "icon": "mdi:broom",
    },
    "filter": {
        # Note the reset button is "air_filter", not "filter".
        "sensor_suffix": "filter_time_left",
        "remaining_is_state": True,
        "reset_button": {
            "entity_suffixes": ["reset_air_filter_consumable"],
            "token_sets": [["reset", "filter"]],
        },
        "default_interval_hours": 150.0,
        "max_interval_hours": 200.0,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "sensor": {
        "sensor_suffix": "sensor_time_left",
        "remaining_is_state": True,
        "reset_button": {
            "entity_suffixes": ["reset_sensor_consumable"],
            "token_sets": [["reset", "sensor"]],
        },
        "default_interval_hours": 30.0,
        "max_interval_hours": 60.0,
        "label": "Sensor",
        "icon": "mdi:eye-outline",
    },
}
