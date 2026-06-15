"""Roborock model catalog.

Maps the HA device-registry model string (``device.model``, e.g.
``"roborock.vacuum.s6"``) to a capability profile. The single ``roborock``
adapter capability-gates per model from this catalog combined with live entity
presence (the Eufy technique) — so one adapter covers the S6 today and future
models without a new ``adapter_id``.

An unrecognised model falls back to ``DEFAULT_PROFILE`` and entity-presence
detection in ``adapter.py`` (the conservative, no-dock baseline).

Provenance for the S6 profile: the Roborock integration diagnostics
``device_features`` map + the live ``vacuum.ivy`` entity set (2026-06-14).
``device_features`` is the Roborock integration's PRIVATE coordinator data (no
public API), so it is catalog reference only — the live gate is entity presence.
"""

from __future__ import annotations

# device.model -> capability profile.
MODEL_PROFILES: dict[str, dict] = {
    "roborock.vacuum.s6": {
        "family": "s6",
        "display_name": "Roborock S6",
        # No auto-empty / wash / dry station (isSupportedDrying /
        # isWashThenChargeCmdSupported / isBackChargeAutoWashSupported all false).
        "has_dock": False,
        # Mop-capable: select.ivy_mop_intensity + binary_sensor water_box_attached.
        "has_mop": True,
        # Native segment / room cleaning (isOrderCleanSupported + isRoomNameSupported
        # + isReSegmentSupported). Multi-map capable (isMultiFloorSupported) even
        # though the current single-floor setting caps stored maps at 1.
        "supports_segments": True,
    },
}

DEFAULT_PROFILE: dict = {
    "family": "generic",
    "display_name": "Roborock",
    "has_dock": False,
    "has_mop": True,
    "supports_segments": True,
}


def profile_for_model(model: str | None) -> dict:
    """Return the capability profile for a device-registry model string."""
    if model and model in MODEL_PROFILES:
        return MODEL_PROFILES[model]
    return DEFAULT_PROFILE
