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

IMPORT STRATEGY. ``python-roborock`` is loaded defensively by the selected registrar's
executor preparation before setup and post-start registration. Synchronous capability
reads only use prepared classes. Failed imports are retried on the next
preparation pass, since the provider may not have installed its package yet. It is NOT in
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

_DOCK_TYPES: tuple[Any, Any] | None = None


def load_dock_library() -> None:
    """Load optional SDK modules in the registrar's preparation executor."""
    global _DOCK_TYPES
    try:
        from roborock.data.v1.v1_code_mappings import RoborockDockTypeCode
        from roborock.device_features import RoborockDockFeatures
    except ImportError:
        # The provider may not have installed its dependency yet. Do not cache
        # failure: the post-start registration pass must be able to retry.
        _LOGGER.debug(
            "%s: python-roborock unavailable; leaving dock capabilities undetermined",
            ADAPTER_ID,
        )
    else:
        _DOCK_TYPES = RoborockDockTypeCode, RoborockDockFeatures


def find_dock_device(hass: HomeAssistant, vacuum_entity_id: str) -> Any | None:
    """Return the dock device entry that belongs to this vacuum, or None.

    Matched by IDENTIFIER (``{duid}_dock``) rather than by name or model, because the
    name is user-renameable and the model is a free-text string. The duid is the
    robot's own id, so the identifier ALREADY scopes the answer to this vacuum — a
    second Roborock on the account has a different duid and therefore a different dock
    identifier, and cannot be returned here.

    ISSUE #69. This used to walk ``vacuum_device.config_entries`` and scan every device
    in each entry for a matching identifier. That read is deprecated from HA 2026.8 and
    removed in 2027.10, and the config-entry scoping it bought was redundant: the duid
    already did that work. The registry indexes devices BY identifier, so the walk is
    replaced by the lookup it was hand-rolling — no deprecated attribute, no version
    shim, and an index hit instead of a scan over every device in the entry.

    HA 2026.10 then deprecated the unscoped ``async_get_device`` itself (removed in
    2027.8.0): identifiers are unique only WITHIN a config entry now, so a lookup must
    say whose entry it means. The scope here is the vacuum ENTITY's own config entry,
    read from the entity registry — the upstream dock is registered from the same
    entry as the robot (``roborock/coordinator.py::dock_device_info``, read at
    2026.10.1) — which is a live, non-deprecated source, unlike
    ``DeviceEntry.config_entries``. An entity with no config entry cannot be the
    upstream integration's, so it resolves to None rather than to an unscoped search.

    THE HA FLOOR IS 2025.6.0 (hacs.json) AND THE NEW METHOD IS 2026.8+. Measured in
    home-assistant/core: ``async_get_device_by_identifier`` is absent from
    ``device_registry.py`` at 2025.6.0 and 2026.7.0 and present from 2026.8.0. Called
    bare it is an AttributeError on every core from the floor through 2026.7, and the
    Roborock adapter would never register there — the 2.5.0 pre-release audit caught it
    shipped bare. So, the shape ``entity_helpers.device_config_entry_ids`` already uses:
    read the new name first (that is what silences the 2026.10 deprecation where it
    fires) and fall back to the unscoped ``async_get_device``, which exists at the floor
    and is not deprecated before 2026.10. [RD-6] holds the floor.

    ``async_get_device_by_identifier`` searches MAIN devices only; the upstream dock
    is registered with ``DeviceInfo``, not ``ChildDeviceInfo``, so it is reachable
    here. A future upstream move of the dock to a child device would need
    ``async_get_child_device_by_identifier`` instead.
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

    config_entry_id = entry.config_entry_id
    if config_entry_id is None:
        return None
    wanted = [(ROBOROCK_DOMAIN, f"{duid}{DOCK_IDENTIFIER_SUFFIX}") for duid in sorted(duids)]
    by_identifier = getattr(dev_reg, "async_get_device_by_identifier", None)
    if by_identifier is None:
        # A core older than 2026.8 — see the docstring. Not deprecated there.
        return dev_reg.async_get_device(identifiers=set(wanted))
    for ident in wanted:
        device = by_identifier(ident, config_entry_id)
        if device is not None:
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

    # Capability reads are synchronous and run in the event loop. Only use
    # prepared classes; never import here.
    if _DOCK_TYPES is None:
        _LOGGER.debug(
            "%s: python-roborock unavailable; leaving dock capabilities undetermined",
            ADAPTER_ID,
        )
        return None
    dock_type_class, features_class = _DOCK_TYPES

    try:
        dock_type = dock_type_class(value)
    except ValueError:
        dock_type = None

    if dock_type is None or dock_type.value != value:
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
            "is_washable": False,
            "is_collectable": False,
            "is_dryable": False,
            "reason": "dock_type_newer_than_library",
        }

    features = features_class.from_dock_type(dock_type)
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
