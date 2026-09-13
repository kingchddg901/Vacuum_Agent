"""Roborock maintenance component catalog — SEVEN components.

IT WAS FOURTEEN, and that was a PARTS INVENTORY read as a card list. A vendor enumerates
objects because that is how spares are sold and wear is tracked; a card is a JOB — one trip,
one set of hands — and a job touches several parts. Dreame came down the same way (14 -> 8)
six weeks after Roborock drifted up to 14 independently, which is what makes it drift rather
than a decision.

WHAT WENT, and why, per Chris's rulings 2026-09-12:
  cleaning_brush, strainer   "should never have been gained" — DOCK parts, and both fold into
                             the one washing-station trip.
  dustbin                    "it only was ever in there because the filter is attached to it";
                             the filter card already covers that trip. Same ruling Dreame
                             already had (DECISION-dustbin-folded-into-filter.md).
  water_filter               "not an item either".
  dust_bag                   install-and-forget: no procedure, and a vendor cadence that swings
                             tenfold.
  clean_water_tank,          parts of the washing-station job, now one `cleaning_tray` card.
  dirty_water_tank
  main_wheel                 never had a job of its own — it is a "wipe these too" line inside
                             the wheel card, which is exactly where it still is.

Chris: **"it really is 7, just 7 that covers the full daily use case of maintiance."** The
emitter, from the three measured fields, independently produces exactly those seven.



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
    # ---- Guide-only cleanables -------------------------------------------
    # Physical parts the user cleans on a schedule but that Roborock does NOT life-track (no
    # ``*_time_left`` sensor, no reset button). ``maintenance_only`` renders them as a guide
    # card with no replacement countdown. Their steps come from the SHARED emitter now, keyed
    # by the canonical component id — there is no per-brand guide library to look them up in.
    #
    # CANONICAL IDS. `mop_cloth` and `caster_wheel` were Roborock's own spellings; the shared
    # emitter names these panels `mop` and `omnidirectional_wheel`. Roborock declares no
    # `label_key`, so the card shows the canonical label, translated in all 18 languages.
    "mop": {
        "maintenance_only": True,
        "label": "Mop",
        "icon": "mdi:water",
    },
    "omnidirectional_wheel": {
        "maintenance_only": True,
        "label": "Omnidirectional Wheel",
        "icon": "mdi:tire",
    },
    # NEW HERE. Roborock had no tray component at all — it declared `clean_water_tank` and
    # `dirty_water_tank` instead, which are PARTS of the job, not the job. The washing station
    # is one trip: lift the board out, rinse it, wipe the tray under it.
    "cleaning_tray": {
        "maintenance_only": True,
        "label": "Cleaning Tray",
        "icon": "mdi:tray",
    },
}
