"""Dreame model catalog.

Maps the HA device-registry model string (``device.model``, e.g.
``"dreame.vacuum.r2469a"``) to a capability profile. The single ``dreame`` adapter
capability-gates per model from this catalog combined with live entity presence (the
Eufy/Roborock technique) — so one adapter covers the L10s Ultra Gen 2 today and future
Dreame/MOVA models without a new ``adapter_id``.

An unrecognised model falls back to ``DEFAULT_PROFILE`` and entity-presence detection
in ``adapter.py`` (the conservative baseline).

⚠ SINGLE SOURCE FOR NAMES (deliberate, addresses the Roborock two-table lesson):
``display_name`` is NOT stored per-profile here — ``profile_for_model`` reads it from
``upkeep_catalog.DREAME_MODEL_NAMES``, the same table that routes guide families. A
maintenance-catalog model table and a capability model table WILL diverge unless one
derives from the other; names are pinned here by import.

⚠ CAPABILITY BOOLEANS ARE PROVISIONAL. The r2469a profile below is verified from the
live ``vacuum.robin`` entity set (2026-08-29): its full wash/dry/auto-empty station
sensors, mop pad + settable ``wetness_level``, per-room selects and per-room
``cleaning_route``. The RIGHT long-term source is the DEVICE_INFO capability table
(AUTO_EMPTY / SELF_WASH / WATER_TANK / MOP_PAD|ROLLER ... per model) that
``upkeep_catalog`` already names; when it is decoded, derive these booleans from it and
add an equality test against ``DREAME_MODEL_NAMES`` so the two tables cannot drift.
"""

from __future__ import annotations

from .upkeep_catalog import DREAME_MODEL_GUIDE_FAMILIES, DREAME_MODEL_NAMES

# guide/maintenance tier -> station capability set. Only ``standard`` (no station) and
# ``auto_empty`` (collect only) REDUCE the station; every wash-station-class family
# (wash_station[/_track/_roller/_baseboard] and the authored families x50/l20/... that
# are all wash-station robots) falls through to DEFAULT_PROFILE's full-station flags.
# Over-claiming a station only turns on a card control that fails safe at dock/manager
# (``missing_action_entity`` when no button resolves); ``standard`` fails CLOSED.
_TIER_STATION: dict[str, dict] = {
    "standard": dict(has_station=False, station_collectable=False,
                     station_washable=False, station_dryable=False),
    "auto_empty": dict(has_station=True, station_collectable=True,
                       station_washable=False, station_dryable=False),
}

# device.model -> capability profile (display_name injected by profile_for_model).
#
# ``has_mop`` vs ``mop_settable`` are DISTINCT (a device may carry a mop yet reject
# programmatic mop SETs). ``station_*`` are the dock deltas the adapter maps to the
# supports_mop_wash / supports_mop_dry / supports_empty_dust hints; live entity
# presence (self_wash_base_status / auto_empty_status / drying_* sensors) is the
# authoritative gate — this table is the fallback and the display identity.
MODEL_PROFILES: dict[str, dict] = {
    "dreame.vacuum.r2469a": {  # L10s Ultra Gen 2 — the authored+verified device (Robin)
        "family": "l10s_gen2",
        "has_mop": True,
        # wetness_level (1-32) is a settable number, global AND per-room -> mop settable.
        "mop_settable": True,
        # Full station: self_wash_base_status + auto_empty_status + drying_* + tanks all
        # present on vacuum.robin.
        "has_station": True,
        "station_collectable": True,  # auto_empty_status + start_auto_empty button
        "station_washable": True,     # self_wash_base_status + mop_wash_level select
        "station_dryable": True,      # drying_progress/drying_left + drying_time select
        "supports_segments": True,    # per-room selects present
        # per-room cleaning_route (standard/intensive/deep) is the route axis.
        "has_path_control": True,
        # No zone-clean entity is exposed; zone cleaning is a service, verified in
        # dispatch (Phase 3), so leave it to the authoritative default until confirmed.
        "supports_zone_clean": False,
    },
}

# Unknown model -> conservative baseline that still ASSUMES a modern Dreame can mop and
# has a station (most current Dreame/MOVA models ship one), because these flags degrade
# safely: a device that can't honour a mop/station control simply has no matching live
# entity, and entity-presence detection in adapter.py is the real gate. ``has_path_control``
# fails CLOSED (False) — offering a route picker the device lacks is the worse failure.
DEFAULT_PROFILE: dict = {
    "family": "generic",
    "has_mop": True,
    "mop_settable": True,
    "has_station": True,
    "station_collectable": True,
    "station_washable": True,
    "station_dryable": True,
    "supports_segments": True,
    "has_path_control": False,
    "supports_zone_clean": False,
}


#: Every model with a hardware-verified override MUST also be in the tier table, so the
#: capability source and the guide/name source cannot drift (the two-table lesson).
assert set(MODEL_PROFILES) <= set(DREAME_MODEL_GUIDE_FAMILIES), (
    "MODEL_PROFILES has models absent from DREAME_MODEL_GUIDE_FAMILIES: "
    f"{sorted(set(MODEL_PROFILES) - set(DREAME_MODEL_GUIDE_FAMILIES))}"
)


def profile_for_model(model: str | None) -> dict:
    """Return the capability profile for a device-registry model string.

    Resolution order: (1) a hardware-verified override in ``MODEL_PROFILES``; else
    (2) derive ``family`` + station flags from the model's guide/maintenance TIER
    (``DREAME_MODEL_GUIDE_FAMILIES``) so every catalogued model gets its real family
    instead of falling to a flat ``generic`` with all-station-on; else (3) the
    conservative ``DEFAULT_PROFILE`` for a truly uncatalogued model. ``display_name`` is
    single-sourced from ``DREAME_MODEL_NAMES`` (never stored per-profile).
    """
    key = model or ""
    if key in MODEL_PROFILES:
        base = MODEL_PROFILES[key]
    else:
        tier = DREAME_MODEL_GUIDE_FAMILIES.get(key)
        if tier:
            base = {**DEFAULT_PROFILE, "family": tier, **_TIER_STATION.get(tier, {})}
        else:
            base = DEFAULT_PROFILE
    return {**base, "display_name": DREAME_MODEL_NAMES.get(key, "Dreame")}
