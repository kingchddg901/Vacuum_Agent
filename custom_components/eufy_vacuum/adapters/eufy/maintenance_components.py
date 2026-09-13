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
                          component — it then falls back to `proxy_for` if declared,
                          and otherwise to the ONE clock entity the user picked for
                          this vacuum (capabilities.MAINTENANCE_CLOCK_ROLE).
    proxy_for           — component id whose sensor this one borrows when its own
                          suffix does not resolve. RESOLUTION ORDER IS
                          `own > proxy > clock`, so declaring BOTH a suffix and a
                          proxy is correct and deliberate: the real counter wins
                          wherever firmware provides one, the borrow covers the rest.
                          A component relying on a borrow must also set
                          `maintenance_only` — a borrowed counter cannot speak to
                          THIS part's wear, so it must not drive a Replacement row.
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
        # NO SENSOR OF ITS OWN. Eufy publishes no swivel-wheel counter at all --
        # `sensor.<obj>_swivel_wheel_remaining` does not exist -- MEASURED on a live X10:
        # six of Eufy's seven components resolve their own `*_remaining`, and this is the one
        # that does not. It is the whole reason `proxy_for` was invented.
        #
        # THE PROXY IS BACK, and the bug that killed it is not. Borrowing the filter's counter
        # used to zero this component whenever the filter was reset (46 -> 0, absorbed by the
        # old clamp, wheel reads brand new). The accumulator now treats that drop as a move
        # against expectation: it re-baselines and books NOTHING, so the wheel keeps its hours.
        # What Eufy publishes makes this better than a picked clock, not merely equal to one --
        # `sensor.<obj>_filter_remaining` carries a `usage_hours` attribute, so
        # `declared_direction` returns UP immediately and this component never spends a tick
        # learning which way its source moves.
        # BOTH ARE DECLARED, as they were at v2.1.0, and the precedence is `own > proxy`. No
        # Eufy firmware we have seen publishes `swivel_wheel_remaining`, but declaring it costs
        # nothing and buys a real fallback on one that does: a genuine per-part counter would
        # then drive the maintenance figure instead of a borrowed runtime clock. ⚠ THE ORDER
        # CHANGED DELIBERATELY. v2.1.0 resolved the PROXY first and fell back to the own suffix,
        # so a real counter could never win once a proxy was declared.
        "sensor_suffix": "swivel_wheel_remaining",
        "proxy_for": "filter",
        # ⚠ REQUIRED ALONGSIDE THE PROXY, and it was missing for the proxy's entire shipped
        # life. Without it this emits a REPLACEMENT row, which reads the borrowed sensor and
        # reports the FILTER's 360-hour service life as the WHEEL's -- v2.1.0 shipped that.
        # Doc 41: replacement is the DEVICE's question, and the device has no answer for this
        # part. A borrowed counter can honestly say how long the machine has run; it cannot say
        # how worn this wheel is.
        "maintenance_only": True,
        "default_interval_hours": 60.0,
        "max_interval_hours": 360,
        "label": "Swivel Wheel",
        "label_key": "swivel_wheel",
        "icon": "mdi:rotate-360",
    },
}
