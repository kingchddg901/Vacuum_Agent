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
                          ABSENT when the firmware publishes no counter for this
                          component — it then falls back to the ONE clock entity the
                          user picked for this vacuum (capabilities.MAINTENANCE_CLOCK_ROLE).
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
    "main_brush": {
        "sensor_suffix": "rolling_brush_remaining",
        "default_interval_hours": 30.0,
        "max_interval_hours": 360,
        "label": "Rolling Brush",
        # Component key is canonical (`main_brush`); Eufy keeps its display WORD via
        # the per-brand label_key -> the existing translated `rolling_brush` label.
        "label_key": "rolling_brush",
        "icon": "mdi:broom",
    },
    # CANONICAL `mop`, AND NO label_key. Eufy called this "Mopping Cloth", which is wrong on
    # FIVE of its ten mop-bearing models: S1, S1 Pro and E28 carry rollers, C20 and X10 Pro Omni
    # carry pads. `mop` is correct for all four mop shapes -- which is the whole point of the
    # split: the STEPS branch by shape, the PANEL NAME does not. So this is the one Eufy word
    # that does not survive as a label_key; the other two do, because their manual uses them.
    "mop": {
        "sensor_suffix": "mopping_cloth_remaining",
        "default_interval_hours": 20.0,
        "max_interval_hours": 120,
        "label": "Mop",
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
    # CANONICAL `omnidirectional_wheel` -- the id the shared emitter produces -- with Eufy's own
    # word kept via label_key. They are the same job and one panel serves both: Chris confirmed
    # the X10's wheel does come out ("it says use a screwdriver to lever it out but i can remove
    # it by hand"), and the step text was made object-free so the HEADING names the part. It is
    # NOT renamed the other way: `caster_wheel` and `omnidirectional_wheel` are distinct in the
    # packs (ru: Ролик vs Всенаправленное колесо), and merging them would be wrong in 17 languages.
    "omnidirectional_wheel": {
        # NO SENSOR AND NO PROXY. Eufy publishes no swivel-wheel counter at all --
        # `sensor.<obj>_swivel_wheel_remaining` does not exist -- which is why this carried
        # `proxy_for: "filter"`. That borrowed the FILTER's counter, and resetting the filter
        # dropped this component's source from 46 to 0, so the wheel silently read brand new.
        # It now falls back to the vacuum's chosen clock like every other uncounted component.
        "default_interval_hours": 60.0,
        "max_interval_hours": 360,
        "label": "Swivel Wheel",
        "label_key": "swivel_wheel",
        "icon": "mdi:rotate-360",
    },
}
