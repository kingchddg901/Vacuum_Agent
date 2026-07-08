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
    maintenance_only    — when True, surface the component ONLY as a Maintenance
                          item (integration-tracked interval), never as a
                          Replacement row. For cleanables with no service-life
                          replacement curve (e.g. the cleaning tray). Optional;
                          absent = False.

Replacement-counter reset buttons are resolved separately from
``buttons.py`` (RESET_CANDIDATES / RESET_TOKENS), which is the single
source for all button discovery (dock actions and resets alike).

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
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Filter",
        "icon": "mdi:air-filter",
    },
    "sensor": {
        "sensor_suffix": "sensor_remaining",
        "default_interval_hours": 60.0,
        "max_interval_hours": 720,
        "label": "Sensor",
        "icon": "mdi:eye-outline",
    },
    "side_brush": {
        "sensor_suffix": "side_brush_remaining",
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Side Brush",
        "icon": "mdi:broom",
    },
    "rolling_brush": {
        "sensor_suffix": "rolling_brush_remaining",
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Rolling Brush",
        "icon": "mdi:broom",
    },
    "mopping_cloth": {
        "sensor_suffix": "mopping_cloth_remaining",
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Mopping Cloth",
        "icon": "mdi:water",
    },
    "cleaning_tray": {
        "sensor_suffix": "cleaning_tray_remaining",
        "default_interval_hours": 30.0,
        "max_interval_hours": 90,
        "label": "Cleaning Tray",
        "icon": "mdi:wiper",
        # A cleanable, not a service-life wear part — Maintenance row only.
        "maintenance_only": True,
    },
    "swivel_wheel": {
        "sensor_suffix": "swivel_wheel_remaining",
        "proxy_for": "filter",
        "default_interval_hours": 60.0,
        "max_interval_hours": 360,
        "label": "Swivel Wheel",
        "icon": "mdi:rotate-360",
    },
}
