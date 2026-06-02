"""
Maintenance component catalog for the Eufy adapter.

Defines the set of components the Eufy firmware exposes as replacement
counters, along with their display metadata and interval configuration.

Each component entry contains:
    label               — human-readable display name
    icon                — mdi icon string for the card
    sensor_suffix       — full suffix appended to '{object_id}_' to form the
                          replacement-counter sensor entity ID (e.g.
                          'filter_remaining' -> sensor.{object_id}_filter_remaining).
                          None for components that source via proxy_for.
    proxy_for           — component ID whose sensor this component reuses when
                          the firmware shares a counter (swivel_wheel -> filter).
    default_interval_hours — Eufy's official guide recommendation.
                             This is the reference anchor. Never change
                             this value — it reflects the manufacturer
                             guidance for a standard installation.
    max_interval_hours  — ceiling for user-configured interval override.
                          Set above default to allow light-use extension
                          (no carpet, no animals, low dust environment).
                          The card uses this as the upper bound when
                          the user adjusts their usage profile.

The user's active interval is stored separately via the maintenance
storage bucket and adjusted through the card's usage profile settings
or the reset_maintenance service call.

A port to a different brand replaces this file with its own component
catalog. A brand whose firmware exposes no replacement counters returns
an empty dict — the maintenance view degrades gracefully.
"""

MAINTENANCE_COMPONENTS: dict[str, dict] = {
    "filter": {
        "sensor_suffix": "filter_remaining",
        "reset_button": {
            "entity_suffixes": ["reset_filter"],
            "token_sets": [["reset", "filter"]],
        },
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "sensor": {
        "sensor_suffix": "sensor_remaining",
        "reset_button": {
            "entity_suffixes": ["reset_sensors", "reset_sensor"],
            "token_sets": [["reset", "sensor"], ["reset", "sensors"]],
        },
        "default_interval_hours": 60.0,
        "max_interval_hours": 720,
        "label": "Sensor",
        "icon": "mdi:eye-outline",
    },
    "side_brush": {
        "sensor_suffix": "side_brush_remaining",
        "reset_button": {
            "entity_suffixes": ["reset_side_brush"],
            "token_sets": [["reset", "side", "brush"]],
        },
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Side Brush",
        "icon": "mdi:broom",
    },
    "rolling_brush": {
        "sensor_suffix": "rolling_brush_remaining",
        "reset_button": {
            "entity_suffixes": ["reset_rolling_brush"],
            "token_sets": [["reset", "rolling", "brush"]],
        },
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Rolling Brush",
        "icon": "mdi:broom",
    },
    "mopping_cloth": {
        "sensor_suffix": "mopping_cloth_remaining",
        "reset_button": {
            "entity_suffixes": ["reset_mopping_cloth"],
            "token_sets": [["reset", "mopping", "cloth"], ["reset", "mop", "cloth"]],
        },
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Mopping Cloth",
        "icon": "mdi:water",
    },
    "cleaning_tray": {
        "sensor_suffix": "cleaning_tray_remaining",
        "reset_button": {
            "entity_suffixes": ["reset_cleaning_tray"],
            "token_sets": [["reset", "cleaning", "tray"]],
        },
        "default_interval_hours": 30.0,
        "max_interval_hours": 90,
        "label": "Cleaning Tray",
        "icon": "mdi:wiper",
    },
    "swivel_wheel": {
        "sensor_suffix": "swivel_wheel_remaining",
        "proxy_for": "filter",
        "reset_button": {
            "entity_suffixes": ["reset_swivel_replacement", "reset_swivel_wheel"],
            "token_sets": [["reset", "swivel", "replacement"], ["reset", "swivel"]],
        },
        "default_interval_hours": 60.0,
        "max_interval_hours": 360,
        "label": "Swivel Wheel",
        "icon": "mdi:rotate-360",
    },
}
