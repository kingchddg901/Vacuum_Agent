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
the device counts down and resets itself when its own button is pressed.
Replacement-status already reads the raw state as remaining hours, so the
maintenance status works natively with no framework recompute.
``default_interval_hours`` / ``max_interval_hours`` are advisory for Roborock
(the device, not the framework interval, drives the real countdown).

REMOVED — ``remaining_is_state``. Every component carried it, and nothing read
it: the flag was documented as "consumed by the framework's parallel remaining
model (core seam — Wave 1b)", and that consumer never shipped. FOUR of the twelve
components declared it (main_brush, side_brush, filter, sensor); the adapter's
projection then defaulted it to False on all twelve, so it reached every component
whether or not its source asked for it. (R2-STALE-5: this said "Thirteen copies",
which was wrong twice — there are twelve components, and it conflated the four
DECLARATIONS with the twelve PROJECTED copies.) A declaration
defended by a comment rather than by a reader is the exact pattern
the 2026-07-30 adapter audit was looking for, so it is pruned rather than left to
read as working configuration. Re-add it WITH its consumer if Wave 1b lands; the
shape note above is the part that was actually load-bearing.
"""

from __future__ import annotations

MAINTENANCE_COMPONENTS: dict[str, dict] = {
    "main_brush": {
        "sensor_suffix": "main_brush_time_left",
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
        "reset_button": {
            "entity_suffixes": ["reset_sensor_consumable"],
            "token_sets": [["reset", "sensor"]],
        },
        "default_interval_hours": 30.0,
        "max_interval_hours": 60.0,
        "label": "Sensor",
        "icon": "mdi:eye-outline",
    },
    # ---- Dock consumables (wash-dock tiers only) ---------------------------
    # MEASURED, not guessed — see .claude/notes/REFERENCE-roborock-dock-detection.md.
    # These two live on the DOCK device, which is a second device in the same config
    # entry, so they are only reachable through the CONFIG-ENTRY scope of the sibling
    # sweep; a device-scoped sweep alone will never see them.
    #
    # They are SELF-GATING and need no capability check. `_resolve` yields None when
    # the sensor is absent, `button.py` skips any component whose source is None, and
    # the manager renders no row — so on a charger-only S6 these two entries are inert.
    # HA creates them exactly when `wash_towel_mode is not None`, i.e. when the vendor's
    # `RoborockDockFeatures.is_washable` is true: every dock type EXCEPT
    # {unknown(-9999), o0(0), o1(1), oc(5)}.
    #
    # ⚠ THE SUFFIX IS THE TRANSLATION KEY, AND THAT IS DELIBERATE. HA derives an
    # entity id from the DISPLAY NAME, not the translation key, and the two diverge
    # here — the real ids measured against HA 2026.8.1 are
    # `..._dock_maintenance_brush_time_left` and `..._dock_strainer_time_left`. So:
    #   * `strainer` resolves on the SUFFIX rung   (`endswith("_strainer_time_left")`)
    #   * `cleaning_brush` CANNOT — "cleaning_brush" never appears in its id at all,
    #     and it resolves only on the TRANSLATION_KEY rung (live:ENT-9), because
    #     `_rescue_maintenance_source` passes the declared suffix through as the wanted
    #     translation key.
    # Declaring the vendor's translation key is therefore the only value that works for
    # BOTH rungs, and it is the only one that survives a localized install — a display
    # name is translated, a translation_key never is.
    "cleaning_brush": {
        "sensor_suffix": "cleaning_brush_time_left",
        "reset_button": {
            # Registry-DISABLED by default upstream (`entity_registry_enabled_default
            # =False`), which is fine: `_replacement_reset_entity` falls through to
            # `registry.async_get` after `states.get` misses, so a disabled button
            # still resolves. It just cannot be pressed until the user enables it.
            "entity_suffixes": ["dock_reset_cleaning_brush_consumable"],
            "token_sets": [["reset", "cleaning", "brush"]],
        },
        # CLEANING_BRUSH_REPLACE_TIME, already in HOURS (see the unit note below).
        "default_interval_hours": 300.0,
        "max_interval_hours": 450.0,
        "label": "Dock Cleaning Brush",
        "icon": "mdi:brush",
    },
    "strainer": {
        "sensor_suffix": "strainer_time_left",
        "reset_button": {
            "entity_suffixes": ["dock_reset_strainer_consumable"],
            "token_sets": [["reset", "strainer"]],
        },
        # STRAINER_REPLACE_TIME, already in HOURS.
        "default_interval_hours": 150.0,
        "max_interval_hours": 200.0,
        "label": "Dock Strainer",
        "icon": "mdi:filter-variant",
    },
    # ⚠ UNIT DISCONTINUITY WITHIN THE BRAND. The four robot consumables above are
    # `native_unit_of_measurement=SECONDS` with `suggested=HOURS`; these two dock
    # sensors are `native=HOURS` with NO suggestion. The displayed state is hours
    # either way — but only because HA converts on one side and not the other. Do not
    # "simplify" by assuming one native unit across the brand, and note that a user who
    # overrides the display unit on one of the four changes what our reader sees while
    # these two cannot be overridden the same way.
    #
    # NOT DECLARED — `dust_collection`. The vendor tracks it
    # (`DUST_COLLECTION_REPLACE_TIME`) but HA publishes no `dust_collection_time_left`
    # sensor for it, so a component here would have nothing to resolve against. It is
    # absent because there is no source, not because it was overlooked.

    # ---- Guide-only cleanables --------------------------------------------
    # Physical parts the user cleans on a schedule but that Roborock does NOT
    # life-track (no ``*_time_left`` sensor, no reset button). Marked
    # ``maintenance_only`` so they render as a guide card WITHOUT a replacement
    # countdown (the manager suppresses the Replacement row for these — same as
    # Eufy's cleaning_tray). Their how-to lives in roborock_upkeep_guides.py under the
    # matching component key; the ``clean_frequency`` there is the real guidance.
    "dustbin": {
        "maintenance_only": True,
        "label": "Dustbin",
        "icon": "mdi:delete-outline",
    },
    "mop_cloth": {
        "maintenance_only": True,
        "label": "Mop Cloth",
        "icon": "mdi:water",
    },
    "water_filter": {
        "maintenance_only": True,
        "label": "Water Filter",
        "icon": "mdi:filter-outline",
    },
    "caster_wheel": {
        "maintenance_only": True,
        "label": "Caster Wheel",
        "icon": "mdi:tire",
    },
    "main_wheel": {
        "maintenance_only": True,
        "label": "Main Wheel",
        "icon": "mdi:tire",
    },
    # ---- Dock / station cleanables (station tiers only) -------------------
    # Present in maintenance_components for ALL Roborocks, but the manager shows a
    # guide-only component (maintenance_only + no sensor) ONLY when the model's guide
    # family documents it — so these appear on dock/station models and stay hidden on
    # a dockless base robot. Guides live in roborock_upkeep_guides.py under the
    # auto_empty / wash_station families.
    "dock_dust_bag": {
        "maintenance_only": True,
        "label": "Dock Dust Bag",
        "icon": "mdi:sack",
    },
    "clean_water_tank": {
        "maintenance_only": True,
        "label": "Clean Water Tank",
        "icon": "mdi:water-outline",
    },
    "dirty_water_tank": {
        "maintenance_only": True,
        "label": "Dirty Water Tank",
        "icon": "mdi:water-alert-outline",
    },
}
