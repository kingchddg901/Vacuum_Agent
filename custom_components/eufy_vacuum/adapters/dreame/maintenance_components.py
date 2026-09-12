"""Dreame maintenance component catalog (verified against vacuum.robin, r2469a).

Each consumable is a remaining-HOURS countdown sensor owned by the ``dreame_vacuum``
integration (``sensor.{object_id}_{sensor_suffix}``) plus a reset button owned by the
same integration (``button.{object_id}_{entity_suffix}``). Same SHAPE as Roborock:
the ``*_time_left`` sensors are DEVICE-owned countdowns (no ``usage_hours`` /
``total_life_hours`` accumulator), so the device counts down and resets itself when
its own reset button is pressed; the framework reads the raw state as remaining hours
and does not recompute. ``default_interval_hours`` / ``max_interval_hours`` are
therefore ADVISORY (the device, not a framework interval, drives the real countdown).

The USER-FACING upkeep GUIDES live separately in ``upkeep_keys.py`` as i18n KEY LISTS
keyed by REGIME; this map wires the live countdown sensors + reset buttons to the four
on-bot consumables the device exposes, and declares the guide-only cleanables that have
no sensor behind them.
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

    # ---- Guide-only cleanables ------------------------------------------------------
    # Parts the user services by hand that Dreame does NOT life-track: no ``*_time_left``
    # sensor, no reset button. ``maintenance_only`` so they render as a guide card with no
    # replacement countdown (same as Roborock's dustbin / Eufy's cleaning_tray).
    #
    # WITHOUT A ROW HERE A GUIDE CANNOT REACH A SCREEN. The manager iterates
    # maintenance_components, not the guide library — which is why the old family library's
    # mop/tank/wheel guides were authored, translated into 17 languages, and never rendered
    # once: Dreame declared only the four sensor-backed components above.
    #
    # WHICH OF THESE APPEAR IS NOT DECIDED HERE. Every one is listed for every Dreame; the
    # manager shows a guide-only component only when the model's REGIME documents it
    # (upkeep_keys.py), so a dockless robot gets `mop` and no `washboard`, and only a Matrix10
    # gets `mop_pad_holders`. Listing is declaration; the regime is the gate.
    #
    # LABELS ARE THE ENGLISH FALLBACK, not the shipped heading vocabulary. The card titles a
    # panel from ``vocab.maintenance_component.<component>`` and falls back to this label when
    # there is no vocab entry — the state main_brush is already in. Wording is taken from the
    # step text these panels render (src/i18n/guide-keys.js), so the heading and the first step
    # name the same object. No vendor part name is invented here: roller and track mops are both
    # "the mop assembly" in their own procedures, and they are never co-present on one model.
    "omnidirectional_wheel": {
        "maintenance_only": True,
        # Dreame's own procedure heading. NOT the caster: the old family library called this
        # `caster_wheel`, which named a different part (see upkeep_keys.py).
        "label": "Omnidirectional Wheel",
        "icon": "mdi:tire",
    },
    # ONE `mop` COMPONENT. It was four — mop_pad / mop_cloth / mop_roller / mop_track — which is
    # a PARTS INVENTORY wearing a card list. Exactly one fires per model and they are never
    # co-present (DUK-6 asserts it), so four names described one job. The label is the job;
    # which assembly it is, the steps say. Dreame's own procedures call roller and track alike
    # "the mop assembly".
    "mop": {
        "maintenance_only": True,
        "label": "Mop",
        "icon": "mdi:water",
    },
    # THE ONE GENUINE EXTRA TRIP. The Matrix10 dock parks spare mop assemblies in slots and swaps
    # them by room type; the holders MOUNT TO THE ROBOT and the dock only STORES them, so an owner
    # has a set on the robot AND spares in the station. Two sets to clean, two trips — which is
    # what makes this a job and not a part. 15 models.
    "mop_pad_holders": {
        "maintenance_only": True,
        # Dreame's own parts-list term ("Mop Pad Holder Mounting Holes").
        "label": "Mop Pad Holders",
        "icon": "mdi:water",
    },

    # ---- Base-station cleanables ----------------------------------------------------
    # ⛔ THREE WATER PANELS WERE REMOVED HERE, ALL BY RULING, 2026-09-12:
    #   water_tanks (479)          "card only is there if a sensor supports" — and Dreame's tank
    #                              sensors are ENUMS ("just installed or low"), which cannot back
    #                              a card. Its steps were already ruled pure narration.
    #   robot_used_water_box (111) "the act is rare per machine" — a job almost nobody performs.
    #   robot_water_tank (20)      folded into ONE clause on the filter card; clean tap water
    #                              down a sink does not earn its own trip.
    # Their nine `tank.*` keys retired with them, across all 18 language packs.
    "washboard": {
        "maintenance_only": True,
        "label": "Washboard",
        "icon": "mdi:tray",
    },
}
