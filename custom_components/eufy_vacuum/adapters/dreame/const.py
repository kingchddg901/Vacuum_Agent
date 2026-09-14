"""Identity + tuning constants for the Dreame adapter.

Brand-level values only — everything else is framework-canonical. Mirrors
``adapters/roborock/const.py``. ``ADAPTER_ID`` is BRAND-level (``"dreame"``): per-
model differences are capability-gated at registration from the device-registry
model string + live entities + ``model_catalog`` (the Eufy/Roborock technique), so
one adapter covers the L10s Ultra Gen 2 today and future Dreame/MOVA models without
a new adapter_id.

LIVE since 2026-09-13 (v2.2.0): the ``BRAND_REGISTRARS`` row that reaches this package
is committed. These constants were inert until that row landed — see
``adapters/dreame/__init__.py`` for the gate and why it was retired.
"""

from __future__ import annotations

# Framework domain is UNCHANGED — Dreame runs inside the same integration, storage,
# and HA platform as Eufy/Roborock. const.py only varies identity strings.
DOMAIN = "eufy_vacuum"
NAME = "Vacuum Agent"

# The model this adapter was first authored + verified against: the live device
# ``vacuum.robin`` (dreame.vacuum.r2469a, "L10s Ultra Gen 2", fw 4.3.9_1636),
# probed 2026-08-29 from its Z:\ entity/device registry.
SUPPORTED_TESTED_MODEL = "Dreame L10s Ultra Gen 2"

# Stable, BRAND-level adapter id stamped into every registered config. Immutable
# once shipped (persisted in stored configs). Per-model gating is done from live
# entities + the model catalog, NOT a per-model adapter_id.
ADAPTER_ID = "dreame"

# The HA integration domain(s) that PROVIDE this brand's vacuum entity — read from
# the ENTITY registry (`entry.platform`), which is canonical and always populated,
# unlike the device registry's free-text manufacturer/model. Brand selection matches
# a vacuum's platform against this tuple. The Tasshack `dreame_vacuum` custom
# integration is the provider (confirmed: vacuum.robin platform == "dreame_vacuum",
# device identifier ["dreame_vacuum", "70:C9:32:8C:1B:61"]).
#
# A TUPLE by design though exactly one entry is planned: it absorbs an upstream rename
# or a second providing integration as DATA rather than a code change.
UPSTREAM_PLATFORMS: tuple[str, ...] = ("dreame_vacuum",)

# Battery floor for classifying a low-battery return vs a user/finish return. The
# device triggers its own return; the framework only observes and classifies it.
# PROVISIONAL — Dreame's real auto-return floor is not yet observed on hardware;
# 20 mirrors the Roborock default and is refined in Phase 3-4 against the live run.
LOW_BATTERY_THRESHOLD_PERCENT = 20
