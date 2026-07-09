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
#
# ``has_mop`` vs ``mop_settable`` are DISTINCT — a device can carry a mop tank
# (``has_mop``) yet reject every programmatic mop command (``mop_settable`` False),
# which is exactly the S6: it mops via the physical tank but
# ``SET_WATER_BOX_CUSTOM_MODE`` / ``SET_MOP_MODE`` raise ``RoborockUnsupportedFeature``.
# Baking the S6's limitation into the whole brand would wrongly deny per-group mop to
# capable models (S7/S8), so mop settability is per-profile. ``mop_settable`` gates
# ``supports_water_control`` + the mop vocab pickers (adapter.py) and the mop
# ``global_pre_calls`` dispatch (Wave 2) — all no-ops when False, so the S6 is
# byte-identical.
MODEL_PROFILES: dict[str, dict] = {
    "roborock.vacuum.s6": {
        "family": "s6",
        "display_name": "Roborock S6",
        # No auto-empty / wash / dry station (isSupportedDrying /
        # isWashThenChargeCmdSupported / isBackChargeAutoWashSupported all false).
        "has_dock": False,
        # Mop-capable: select.ivy_mop_intensity + binary_sensor water_box_attached.
        "has_mop": True,
        # ...but the mop is OBSERVE-ONLY: intensity/mode SETs are rejected on-device
        # (empirically, RoborockUnsupportedFeature). So no settable mop controls.
        "mop_settable": False,
        # Native segment / room cleaning (isOrderCleanSupported + isRoomNameSupported
        # + isReSegmentSupported). Multi-map capable (isMultiFloorSupported) even
        # though the current single-floor setting caps stored maps at 1.
        "supports_segments": True,
    },
    # Settable-mop models. device.model codes are best-effort from python-roborock's
    # model table; if a code is wrong the profile simply never matches and the unit
    # falls through to DEFAULT_PROFILE (also mop_settable), so mop controls still
    # appear — only the display name would read the generic "Roborock". UNVERIFIED
    # on-device (no S7/S8 on hand): the mop dispatch degrades gracefully (a rejected
    # select_option is caught + logged, never aborts the run — see _run_global_pre_calls).
    "roborock.vacuum.a15": {  # S7
        "family": "s7",
        "display_name": "Roborock S7",
        "has_dock": False,
        "has_mop": True,
        "mop_settable": True,
        "supports_segments": True,
    },
    "roborock.vacuum.a70": {  # S8
        "family": "s8",
        "display_name": "Roborock S8",
        "has_dock": False,
        "has_mop": True,
        "mop_settable": True,
        "supports_segments": True,
    },
}

# Unknown model -> conservative no-dock baseline, but ASSUME a modern Roborock can set
# its mop ("not all Roborocks are the S6"): mop_settable True is best-effort and
# degrades safely (a device that can't set mop rejects the call, which is caught +
# logged). A known no-op model (like the S6) is catalogued explicitly False above.
DEFAULT_PROFILE: dict = {
    "family": "generic",
    "display_name": "Roborock",
    "has_dock": False,
    "has_mop": True,
    "mop_settable": True,
    "supports_segments": True,
}


def profile_for_model(model: str | None) -> dict:
    """Return the capability profile for a device-registry model string."""
    if model and model in MODEL_PROFILES:
        return MODEL_PROFILES[model]
    return DEFAULT_PROFILE
