"""Dreame maintenance component catalog (verified against vacuum.robin, r2469a).

Each consumable is a remaining-HOURS countdown sensor owned by the ``dreame_vacuum``
integration (``sensor.{object_id}_{sensor_suffix}``) plus a reset button owned by the
same integration (``button.{object_id}_{entity_suffix}``). Same SHAPE as Roborock:
the ``*_time_left`` sensors are DEVICE-owned countdowns (no ``usage_hours`` /
``total_life_hours`` accumulator), so the device counts down and resets itself when
its own reset button is pressed; the framework reads the raw state as remaining hours
and does not recompute. ``default_interval_hours`` / ``max_interval_hours`` are
therefore ADVISORY (the device, not a framework interval, drives the real countdown).

The USER-FACING upkeep GUIDES (steps/notes/frequencies) live separately in
``dreame_upkeep_guides.py`` keyed by guide family; this map only wires the live
countdown sensors + reset buttons to the four on-bot consumables the device exposes.
Verified suffixes on vacuum.robin: sensor.robin_{main_brush,side_brush,filter,
sensor_dirty}_time_left and button.robin_reset_{main_brush,side_brush,filter,sensor}.
"""

from __future__ import annotations

MAINTENANCE_COMPONENTS: dict[str, dict] = {
    "main_brush": {
        "sensor_suffix": "main_brush_time_left",
        "reset_button": {
            "entity_suffixes": ["reset_main_brush"],
            "token_sets": [["reset", "main", "brush"]],
        },
        "default_interval_hours": 300.0,
        "max_interval_hours": 450.0,
        "label": "Main Brush",
        "icon": "mdi:broom",
    },
    "side_brush": {
        "sensor_suffix": "side_brush_time_left",
        "reset_button": {
            "entity_suffixes": ["reset_side_brush"],
            "token_sets": [["reset", "side", "brush"]],
        },
        "default_interval_hours": 200.0,
        "max_interval_hours": 300.0,
        "label": "Side Brush",
        "icon": "mdi:broom",
    },
    "filter": {
        "sensor_suffix": "filter_time_left",
        "reset_button": {
            "entity_suffixes": ["reset_filter"],
            "token_sets": [["reset", "filter"]],
        },
        "default_interval_hours": 150.0,
        "max_interval_hours": 200.0,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "sensor": {
        # Device suffix is "sensor_dirty_time_left"; reset button is "reset_sensor".
        "sensor_suffix": "sensor_dirty_time_left",
        "reset_button": {
            "entity_suffixes": ["reset_sensor"],
            "token_sets": [["reset", "sensor"]],
        },
        "default_interval_hours": 30.0,
        "max_interval_hours": 60.0,
        "label": "Sensors",
        "icon": "mdi:leak",
    },
}
