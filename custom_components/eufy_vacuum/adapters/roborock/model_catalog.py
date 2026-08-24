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
        # V1 device protocol => RoborockCommand.SET_CLEAN_SEQUENCE applies.
        "supports_clean_sequence_write": True,
        # No path/route axis on this unit — owner-confirmed on hardware.
        "has_path_control": False,
    },
    # Same class as the S6, and catalogued for the same reason: the mop-intensity and
    # mop-mode selects EXIST (the unit ships with a pad + tank) but the SETs are rejected
    # on-device with RoborockUnsupportedFeature -- observed on every phase dispatch on
    # hardware. Without this entry an a72 falls through to DEFAULT_PROFILE (mop_settable
    # True) and is offered water pickers it can never honour.
    "roborock.vacuum.a72": {  # Q5 Pro
        "family": "q5",
        "display_name": "Roborock Q5 Pro",
        # Charge-only base. The core roborock integration creates no auto-empty / wash /
        # dry entities for this unit, so there is no station to model.
        "has_dock": False,
        # Carries a mop pad + water tank...
        "has_mop": True,
        # ...but SET_WATER_BOX_CUSTOM_MODE is rejected on-device, and
        # binary_sensor.<obj>_water_box_attached reads unavailable.
        "mop_settable": False,
        "supports_segments": True,
        # V1 device protocol => RoborockCommand.SET_CLEAN_SEQUENCE applies.
        "supports_clean_sequence_write": True,
        "has_path_control": False,
    },
    # Settable-mop models. device.model codes are best-effort from python-roborock's
    # model table; if a code is wrong the profile simply never matches and the unit
    # falls through to DEFAULT_PROFILE (also mop_settable), so mop controls still
    # appear — only the display name would read the generic "Roborock". UNVERIFIED
    # on-device (no S7/S8 on hand): the mop dispatch degrades gracefully (a rejected
    # select_option is caught + logged, never aborts the run — see _run_global_pre_calls).
    # ⚠ NOT TRUE FOR THE SAFEST-WATER ENTRY, which is the water pre-call this brand
    # declares. When ``mixed_mode_water_policy: "safest"`` is active,
    # ``dispatch/manager.py::_run_global_pre_calls`` RAISES and aborts the dispatch on
    # both a missing target entity (issue #51) and any exception from the select —
    # deliberately, because failing to push safe water before a batch containing dry
    # rooms is what wet-mops them.
    #
    # And that path is not an edge case: it activates whenever the batch contains ANY
    # non-mop room (``_any_dry_room = _mop_rooms < len(resolved_rooms)``), which
    # includes the plainest case of all, an all-vacuum batch. Since an uncatalogued
    # model defaults to mop-settable, this is reachable on any Roborock not in the
    # catalog whose mop set is actually rejected.
    #
    # "Caught + logged, never aborts" remains true for the BEST-EFFORT entries (fan,
    # single-mode water). Corrected 2026-08-23.
    "roborock.vacuum.a15": {  # S7
        "family": "s7",
        "display_name": "Roborock S7",
        "has_dock": False,
        "has_mop": True,
        "mop_settable": True,
        "supports_segments": True,
        # V1 device protocol => RoborockCommand.SET_CLEAN_SEQUENCE applies.
        "supports_clean_sequence_write": True,
        "has_path_control": False,
    },
    "roborock.vacuum.a70": {  # S8
        "family": "s8",
        "display_name": "Roborock S8",
        "has_dock": False,
        "has_mop": True,
        "mop_settable": True,
        "supports_segments": True,
        # V1 device protocol => RoborockCommand.SET_CLEAN_SEQUENCE applies.
        "supports_clean_sequence_write": True,
        "has_path_control": False,
    },
}

# ``has_dock`` IS NOT A LIVE VALUE — it is a FALLBACK, and it is False everywhere on
# purpose. The dock is a separate device that the same robot model ships with in several
# tiers, so a per-model table cannot answer the question; the live answer comes from the
# dock device's ``model_id`` run through the vendor's own capability table (``dock.py``).
# This entry is consulted only when that resolution returns None — "undetermined", e.g.
# python-roborock not importable — where a conservative False is the right degradation.
# Do NOT "fill these in" per model: a hand-maintained dock column would silently diverge
# from the hardware the moment a model ships with a different station, which is exactly
# the failure the vendor lookup exists to prevent.

# ``supports_zone_clean`` — OPTIONAL, defaults True. Draw-a-box zone cleaning via
#   ``app_zoned_clean``. Every catalogued model supports it, so no entry declares it
#   today; the key exists because the adapter passes it through as a capability hint
#   (D18), which means an entry declaring ``False`` is actually refused at dispatch
#   rather than silently ignored. Declare it only from evidence on the device.
#
# ``has_path_control`` — the per-room path/route axis (``path_type``: wide | narrow).
# The S6 does not have it; better models do, which is why the axis stays declared in
# ROOM_PROFILES rather than being deleted brand-wide. It is False on every entry above
# because no model here has been VERIFIED on hardware, and this flag does not degrade
# the way ``mop_settable`` does: mop_settable guessing wrong costs a rejected call that
# is caught and logged, whereas path control guessing wrong puts a picker in the UI for
# something the device cannot do. Offering a control that does nothing is the worse
# failure, so this one defaults conservatively and flips per model on evidence.

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
    "has_path_control": False,
    # ⚠ FAILS CLOSED, UNLIKE mop_settable ABOVE, AND THE ASYMMETRY IS DELIBERATE.
    #
    # `mop_settable` guesses True because a wrong guess is ABSORBED: the device rejects
    # the call, we catch and log it, and the user sees nothing. The clean-sequence write
    # has no such absorber. `set_clean_sequence` is the **V1** device protocol; newer
    # Qrevo/B01 models answer a DIFFERENT transport entirely (`service.set_room_order`
    # on `RoborockB01Q7Methods`). On one of those the write cannot land and the user is
    # left with a control that is permanently amber -- a control that LOOKS BROKEN is
    # worse than a control that is absent.
    #
    # Proven end to end on the S6 (2026-08-19, Ivy): read, write, replace, clear, all
    # verified, with the vendor app rendering our write as numbered badges on its own
    # Sequence screen. The other three catalogued entries share the V1 command namespace,
    # which is INFERENCE, not measurement -- but the ack check means a wrong inference
    # degrades to "could not confirm" rather than to a false green.
    #
    # Promoting an unknown model is a one-line catalog entry once someone confirms it.
    "supports_clean_sequence_write": False,
}


def profile_for_model(model: str | None) -> dict:
    """Return the capability profile for a device-registry model string."""
    if model and model in MODEL_PROFILES:
        return MODEL_PROFILES[model]
    return DEFAULT_PROFILE
