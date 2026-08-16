"""Roborock dock identification from the HA device registry.

Roborock splits one vacuum across TWO devices in a single config entry: the robot
(`identifiers={("roborock", duid)}`) and the dock
(`identifiers={("roborock", f"{duid}_dock")}`). The dock device carries
``model_id=str(dock_type.value)``, or the string ``"Unknown"`` when the robot's status
has no ``dock_type`` field at all. That integer is the only public, supported handle on
what the dock can do — everything else about it is private coordinator state.

WHY A TRUTH TABLE AND NOT A PROBE. Three cheaper-looking tests were tried against real
hardware and all three are wrong; the reasoning and the measurements are in
``.claude/notes/REFERENCE-roborock-dock-detection.md``. The short version:

1. **"a dock device exists"** — it exists iff at least ONE dock entity does, and on a
   charger-only S6 that is satisfied by a single drying binary_sensor admitted because
   the product SCHEMA declares DPS 134. Schema declaration, not hardware.
2. **"model_id != o0_dock"** — a dockless unit reports ``"Unknown"``, not ``"0"``. Both
   must be treated as no-dock.
3. **"probe for dock entities"** — entity presence over-reports in both directions: HA
   publishes ``cleaning_brush_time_left`` on any washable dock even where the vendor's
   own ``is_cleaning_brush_supported`` is false, and publishes the drying sensor on a
   bare charger.

So: read the integer, ask the vendor.

IMPORT STRATEGY. ``python-roborock`` is imported lazily and defensively. It is NOT in
our manifest and must not be added — this adapter only runs when the Roborock
integration is set up, and THAT manifest pins the library. If the import somehow fails
we return ``None`` ("unknown"), which leaves the caller on its pre-existing no-dock
default rather than guessing. The vendor's ``_NO_DOCK_TYPES`` is deliberately NOT
hand-copied here: a vendored copy of a vendor set goes stale silently, which is the
failure this module exists to avoid.

COLD START. The dock device may not be in the registry yet when this first runs. That
is expected and already handled: the ``async_at_started`` hook re-runs brand
registration and then ``refresh_vacuum_capabilities``, so a dock that appears late is
picked up on the second pass and written only if something changed.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import ADAPTER_ID

_LOGGER = logging.getLogger(__name__)

#: The literal the Roborock coordinator writes when ``status.dock_type`` is absent.
#: Not a number, so it can never be confused with a real dock type.
UNKNOWN_MODEL_ID = "Unknown"

#: Device-registry identifier domain used by the upstream Roborock integration.
ROBOROCK_DOMAIN = "roborock"

#: Suffix the upstream integration appends to the duid for the dock's identifier.
DOCK_IDENTIFIER_SUFFIX = "_dock"


def find_dock_device(hass: HomeAssistant, vacuum_entity_id: str) -> Any | None:
    """Return the dock device entry that belongs to this vacuum, or None.

    Matched by IDENTIFIER (``{duid}_dock``) rather than by name or model, because the
    name is user-renameable and the model is a free-text string. Scoped to the config
    entries the vacuum's own device belongs to, so a second Roborock on the account
    cannot contribute its dock.
    """
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(vacuum_entity_id)
    if entry is None or entry.device_id is None:
        return None

    dev_reg = dr.async_get(hass)
    vacuum_device = dev_reg.async_get(entry.device_id)
    if vacuum_device is None:
        return None

    duids = {
        ident
        for domain, ident in vacuum_device.identifiers
        if domain == ROBOROCK_DOMAIN
    }
    if not duids:
        return None

    wanted = {f"{duid}{DOCK_IDENTIFIER_SUFFIX}" for duid in duids}
    for config_entry_id in vacuum_device.config_entries:
        for device in dr.async_entries_for_config_entry(dev_reg, config_entry_id):
            for domain, ident in device.identifiers:
                if domain == ROBOROCK_DOMAIN and ident in wanted:
                    return device
    return None


def dock_type_value(device: Any | None) -> int | None:
    """Return the dock's numeric ``dock_type``, or None if it has none.

    ``"Unknown"`` and any non-numeric string both yield None — a dock we cannot
    identify is treated exactly like a dock that is not there.
    """
    if device is None:
        return None
    raw = getattr(device, "model_id", None)
    if raw is None or raw == UNKNOWN_MODEL_ID:
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        _LOGGER.debug(
            "%s: dock model_id %r is neither a number nor %r — treating as no dock",
            ADAPTER_ID,
            raw,
            UNKNOWN_MODEL_ID,
        )
        return None


def dock_profile(hass: HomeAssistant, vacuum_entity_id: str) -> dict[str, Any] | None:
    """Resolve this vacuum's dock capabilities, or None when they are unknowable.

    None means "could not determine" — NOT "no dock". The caller must keep its own
    conservative default in that case, so a missing library or an unrecognised code can
    never enable a control for hardware that is not there.

    A resolved profile always carries ``has_dock``; the finer flags come straight from
    the vendor and are never recomputed here.
    """
    device = find_dock_device(hass, vacuum_entity_id)
    value = dock_type_value(device)
    if value is None:
        # Either there is no dock device, or it reports "Unknown". Both are a real
        # answer — this vacuum has no identifiable dock.
        return {
            "has_dock": False,
            "dock_type": None,
            "dock_type_name": None,
            "reason": "no_dock_device" if device is None else "model_id_unknown",
        }

    try:
        from roborock.data.v1.v1_code_mappings import RoborockDockTypeCode
        from roborock.device_features import RoborockDockFeatures
    except ImportError:  # pragma: no cover — the roborock integration guarantees this
        _LOGGER.debug(
            "%s: python-roborock unavailable; leaving dock capabilities undetermined",
            ADAPTER_ID,
        )
        return None

    try:
        dock_type = RoborockDockTypeCode(value)
    except ValueError:
        # A dock newer than the installed library. Do NOT assume no-dock: the device
        # registry says a dock is there and reported a real code, so has_dock is True
        # and only the fine detail is unknown.
        _LOGGER.debug(
            "%s: dock_type %s not in this python-roborock; has_dock True, detail unknown",
            ADAPTER_ID,
            value,
        )
        return {
            "has_dock": True,
            "dock_type": value,
            "dock_type_name": None,
            "reason": "dock_type_newer_than_library",
        }

    features = RoborockDockFeatures.from_dock_type(dock_type)
    return {
        "has_dock": features.has_dock,
        "dock_type": value,
        "dock_type_name": dock_type.name,
        # ⚠ `has_am` is a SECOND vendor input, read from live status, which the device
        # registry does not carry. The two properties that depend on it
        # (`is_clean_fluid_auto_delivery_supported`, `is_water_updown_drain_supported`)
        # are therefore NOT exposed here — reporting their has_am=None reading as fact
        # would under-report on 11 of the 27 dock types.
        "is_washable": features.is_washable,
        "is_collectable": features.is_collectable,
        "is_dryable": features.is_dryable,
        "reason": None,
    }
