"""Tests for device-registry model resolution in core/manager.py.

``_get_registry_model_code`` is the seam the maintenance/upkeep surfaces use to
discover which physical RoboVac model a vacuum is, by reading the model string
off the *upstream* device-registry entry that the vacuum's HA integration
created. It walks entity entry -> device entry -> ``model``, normalizing a
missing device / missing-or-blank model to ``None`` so callers can fall back
cleanly. ``ensure_vacuum_record`` consumes that result to backfill a record.

These tests wire a real device entry and link a real ``vacuum.*`` entity to it
through the entity registry, then drive the manager's real lookup path. No
mocking of the registry; observable behaviour only.

Coverage targets
----------------
[CMR-1]  _get_registry_model_code: entity → device with a populated model →
         the stripped model code is returned (manager.py lines 818-823 happy path).
[CMR-2]  _get_registry_model_code: device model is blank → None (822-823 blank→None);
         and entity has no linked device → None (815-816 guard, no device lookup).
[CMR-3]  ensure_vacuum_record: existing record with detected_model=None +
         no detected_model arg + a resolvable registry model → record is
         backfilled with the registry model (manager.py line 887 elif).
"""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


def _link_vacuum_to_device(
    hass,
    mock_config_entry,
    *,
    model: str,
    device_identifier: str,
    object_id: str,
    unique_id: str,
) -> str:
    """Create an upstream device with ``model`` and link a vacuum entity to it.

    Mirrors what a real vacuum integration leaves behind at setup time: a device
    entry created against a config entry plus an entity-registry row pointing the
    vacuum entity at that device via ``device_id``. This is exactly the chain
    ``_get_registry_model_code`` reads (entity → device_id → device.model).
    Returns the resulting vacuum ``entity_id``.
    """
    mock_config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, device_identifier)},
        model=model,
    )
    entry = er.async_get(hass).async_get_or_create(
        "vacuum",
        "demo",
        unique_id,
        device_id=device.id,
        suggested_object_id=object_id,
    )
    return entry.entity_id


# ---------------------------------------------------------------------------
# _get_registry_model_code — the resolver itself (lines 815-823)
# ---------------------------------------------------------------------------

def test_registry_model_code_resolves_populated_model(manager, hass, mock_config_entry):
    """[CMR-1] a populated device model is returned, stripped, for the linked vacuum."""
    entity_id = _link_vacuum_to_device(
        hass,
        mock_config_entry,
        model="  RoboVac X8  ",  # surrounding whitespace is stripped (line 822)
        device_identifier="alfred",
        object_id="alfred",
        unique_id="uid-alfred",
    )
    assert entity_id == _VAC

    assert manager._get_registry_model_code(vacuum_entity_id=entity_id) == "RoboVac X8"


def test_registry_model_code_blank_model_returns_none(manager, hass, mock_config_entry):
    """[CMR-2] a blank device model normalizes to None, not an empty string (line 823)."""
    entity_id = _link_vacuum_to_device(
        hass,
        mock_config_entry,
        model="",  # blank -> None
        device_identifier="blankbot",
        object_id="blankbot",
        unique_id="uid-blank",
    )

    assert manager._get_registry_model_code(vacuum_entity_id=entity_id) is None


def test_registry_model_code_no_device_returns_none(manager, hass, mock_config_entry):
    """[CMR-2] an entity with no linked device yields None (the 815-816 guard).

    No device is created, so the resolver must short-circuit before the device
    lookup (lines 818-820) rather than raising.
    """
    mock_config_entry.add_to_hass(hass)
    entry = er.async_get(hass).async_get_or_create(
        "vacuum",
        "demo",
        "uid-nodevice",
        config_entry=mock_config_entry,
        suggested_object_id="nodevice",
    )
    assert entry.entity_id == "vacuum.nodevice"
    assert entry.device_id is None

    assert manager._get_registry_model_code(vacuum_entity_id=entry.entity_id) is None


# ---------------------------------------------------------------------------
# ensure_vacuum_record — the backfill consumer (line 887)
# ---------------------------------------------------------------------------

def test_ensure_vacuum_record_backfills_model_from_registry(
    manager, hass, mock_config_entry
):
    """[CMR-3] existing model-less record + resolvable registry model → backfill.

    Seed a record with detected_model=None (an early record created before the
    device/entity registry could resolve the model), then call
    ensure_vacuum_record with no detected_model. The elif branch must resolve the
    registry model and write it onto the existing record without replacing it.
    """
    _link_vacuum_to_device(
        hass,
        mock_config_entry,
        model="RoboVac X8",
        device_identifier="alfred",
        object_id="alfred",
        unique_id="uid-alfred",
    )

    # pre-existing record with no model — ensure_vacuum_record must NOT overwrite
    # an existing dict, only backfill the empty detected_model field.
    manager.data.setdefault("vacuums", {})[_VAC] = {
        "vacuum_entity_id": _VAC,
        "detected_model": None,
        "is_managed": True,
    }
    seeded = manager.data["vacuums"][_VAC]

    record = manager.ensure_vacuum_record(vacuum_entity_id=_VAC)

    # same record object, mutated in place — not a fresh replacement
    assert record is seeded
    assert record["detected_model"] == "RoboVac X8"
    # stored data reflects the backfill too
    assert manager.data["vacuums"][_VAC]["detected_model"] == "RoboVac X8"
