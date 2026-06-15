"""Identity + tuning constants for the Roborock adapter.

Brand-level values only — everything else is framework-canonical. Mirrors
``adapters/eufy/const.py``. ``ADAPTER_ID`` is BRAND-level (``"roborock"``): per-
model differences are capability-gated at registration from the device-registry
model string + live entities + ``model_catalog`` (the Eufy technique), so one
adapter covers the S6 today and future Roborock models without a new adapter_id.
"""

from __future__ import annotations

# Framework domain is UNCHANGED — Roborock runs inside the same integration,
# storage, and HA platform as Eufy. const.py only varies identity strings.
DOMAIN = "eufy_vacuum"
NAME = "Vacuum Agent"

# The model this adapter was first authored + verified against.
SUPPORTED_TESTED_MODEL = "Roborock S6"

# Stable, BRAND-level adapter id stamped into every registered config. Immutable
# once shipped (persisted in stored configs). Per-model gating is done from live
# entities + the model catalog, NOT a per-model adapter_id.
ADAPTER_ID = "roborock"

# Roborock firmware auto-returns to the dock at this battery floor (observed:
# ``returning_home`` fires the same tick battery hits 19%). The framework uses
# this ONLY to classify a low-battery return vs a user/finish return — the device
# triggers the return itself; the framework observes it. Set just above the 19%
# floor so a return at the floor is classified as low-battery.
LOW_BATTERY_THRESHOLD_PERCENT = 20
