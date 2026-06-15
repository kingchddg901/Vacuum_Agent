"""Roborock lifecycle + dropdown vocabulary for the Roborock adapter.

Grounded in the captured ``vacuum.ivy`` enums (``sensor.ivy_status``,
``sensor.ivy_vacuum_error``, ``vacuum.ivy`` ``fan_speed_list``,
``select.ivy_mop_intensity`` / ``_mop_mode``) and the live run trace
(2026-06-14), which observed: cleaning, paused, error, returning_home, charging,
segment_cleaning, plus the two obstacle errors ``bumper_stuck`` /
``wheels_suspended``.
"""

from __future__ import annotations

# ``sensor.ivy_status`` values that mean "a job is actively running" — lets the
# framework mark active from the status string in addition to the HA-standard
# ``vacuum.state``. Dock/wash/dry states the no-dock S6 never emits are omitted.
ACTIVE_RUN_TASK_STATES: set[str] = {
    "starting",
    "cleaning",
    "spot_cleaning",
    "zoned_cleaning",
    "segment_cleaning",
    "segment_mopping",
    "going_to_target",
    "returning_home",
    "docking",
}

# ``sensor.ivy_vacuum_error`` sentinel values meaning "no error". The idle value
# is ``none``; ``normal`` is an Eufy-only sentinel and is intentionally excluded
# (a Roborock error code could legitimately contain it).
NOT_ERROR_SENTINELS: set[str] = {"", "unknown", "unavailable", "none"}

# Cancel-detection transition strings consumed by learning/job_finalizer.py
# (_detect_cancel_likely_run): a too-short active->returning (or paused->returning)
# run is flagged as a likely cancel so it doesn't pollute per-room learning
# estimates. Roborock's return state is ``returning_home`` (NOT the framework
# default ``returning``), and its "actively cleaning" status is mode-specific, so
# ``active`` is a LIST (the finalizer matches a pre-return transition from any of
# them). Confirmed in the run trace (status reaches returning_home, never bare
# returning).
CANCEL_DETECTION_STATES: dict = {
    "active": ["cleaning", "spot_cleaning", "zoned_cleaning", "segment_cleaning", "segment_mopping"],
    "returning": "returning_home",
    "paused": "paused",
}

# Card-facing dropdown option lists (the framework never reads these).
# fan_speed from ``vacuum.ivy`` ``fan_speed_list``.
FAN_SPEED_OPTIONS: list[dict] = [
    {"value": "quiet", "label": "Quiet"},
    {"value": "balanced", "label": "Balanced"},
    {"value": "turbo", "label": "Turbo"},
    {"value": "max", "label": "Max"},
    {"value": "gentle", "label": "Gentle"},
]

# water_level from ``select.ivy_mop_intensity`` (off/low/medium/high) — maps 1:1
# onto the canonical water_level vocabulary (locked decision).
WATER_LEVEL_OPTIONS: list[dict] = [
    {"value": "off", "label": "Off"},
    {"value": "low", "label": "Low"},
    {"value": "medium", "label": "Medium"},
    {"value": "high", "label": "High"},
]

# ``select.ivy_mop_mode`` (standard/deep) is a Roborock-only GLOBAL axis with no
# canonical framework slot (locked decision: global-only, set pre-dispatch). Kept
# here for the card / future dispatch pre-call wiring, not exposed as a canonical
# vocabulary key yet.
MOP_MODE_OPTIONS: list[dict] = [
    {"value": "standard", "label": "Standard"},
    {"value": "deep", "label": "Deep"},
]
