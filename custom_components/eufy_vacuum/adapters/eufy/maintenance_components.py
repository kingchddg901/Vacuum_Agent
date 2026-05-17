"""
Maintenance component catalog for the Eufy adapter.

Defines the set of components the Eufy firmware exposes as replacement
counters, along with their display metadata and interval configuration.

Each component entry contains:
    label               — human-readable display name
    icon                — mdi icon string for the card
    sensor_suffix       — suffix used to locate the *_remaining sensor for
                          this component (None for swivel_wheel, which
                          proxies through the filter sensor)
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
        "sensor_suffix": "filter",
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "sensor": {
        "sensor_suffix": "sensor",
        "default_interval_hours": 60.0,
        "max_interval_hours": 720,
        "label": "Sensor",
        "icon": "mdi:eye-outline",
    },
    "side_brush": {
        "sensor_suffix": "side_brush",
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Side Brush",
        "icon": "mdi:broom",
    },
    "rolling_brush": {
        "sensor_suffix": "rolling_brush",
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Rolling Brush",
        "icon": "mdi:broom",
    },
    "mopping_cloth": {
        "sensor_suffix": "mopping_cloth",
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Mopping Cloth",
        "icon": "mdi:water",
    },
    "cleaning_tray": {
        "sensor_suffix": "cleaning_tray",
        "default_interval_hours": 30.0,
        "max_interval_hours": 90,
        "label": "Cleaning Tray",
        "icon": "mdi:wiper",
    },
    "swivel_wheel": {
        "sensor_suffix": None,
        "default_interval_hours": 60.0,
        "max_interval_hours": 360,
        "label": "Swivel Wheel",
        "icon": "mdi:rotate-360",
    },
}
