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

The SECOND copy of this resolver lives in `adapters/eufy/adapter.py`
(`_registry_model_code`), whose docstring states it mirrors the one above. It had
no tests at all and its device-lookup half had never executed:

[CMR-4]  the adapter copy returns the stripped device model, and AGREES with the
         original.
[CMR-5]  ...normalizes a blank model to None, not `""`.
[CMR-6]  ...answers None for an unregistered entity and for one with no device,
         rather than raising during adapter registration.
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


# ---------------------------------------------------------------------------
# [CMR-4] - [CMR-6]  the SECOND copy of this resolver.
#
# `adapters/eufy/adapter.py::_registry_model_code` is a deliberate copy of
# `_get_registry_model_code` above -- its docstring says so: "Mirrors
# core/manager._get_registry_model_code (kept local to keep the adapter
# self-contained)." The original had three tests and the copy had NONE, and its
# device-lookup half had never executed: coverage put the whole body after the
# first guard in the missing set, so every call in the suite returned None at the
# `entity_entry is None or not device_id` line.
#
# That is the half that matters. The copy exists because the scalar/Tuya transport
# does NOT set the `detected_model` vacuum-entity attribute, so reading only the
# attribute "pinned scalar devices to model_family generic" -- the registry is what
# carries the code on that path. The fix for that bug was the untested part.
#
# Tested HERE rather than under tests/adapters/eufy/ on purpose: the claim is that
# the two copies AGREE, and the helper plus the original's cases already live in
# this file. A replica whose copies drift is the failure this repo keeps finding.
# ---------------------------------------------------------------------------


def _adapter_copy(hass, entity_id):
    """The adapter's local copy of the resolver, imported at call time."""
    from custom_components.eufy_vacuum.adapters.eufy.adapter import (
        _registry_model_code,
    )
    return _registry_model_code(hass, entity_id)


def test_cmr4_the_adapter_copy_resolves_a_populated_model(
    manager, hass, mock_config_entry
):
    """[CMR-4] The adapter's copy returns the stripped device model.

    Same input as [CMR-1], and the answers are asserted to MATCH -- that agreement
    is the point, not the value on its own. The whitespace in the model is
    deliberate: both copies end in `str(...).strip() or None`, so a copy that
    dropped the strip would return `"  RoboVac X8  "` and only a padded fixture
    can see it.

    RED: delete the device lookup from the adapter copy and it returns None while
    the original still answers.
    """
    entity_id = _link_vacuum_to_device(
        hass,
        mock_config_entry,
        model="  RoboVac X8  ",
        device_identifier="cmr4bot",
        object_id="cmr4bot",
        unique_id="uid-cmr4",
    )

    assert _adapter_copy(hass, entity_id) == "RoboVac X8"
    assert _adapter_copy(hass, entity_id) == manager._get_registry_model_code(
        vacuum_entity_id=entity_id
    ), "the two copies of this resolver disagree on a populated model"


def test_cmr5_the_adapter_copy_normalizes_a_blank_model(
    manager, hass, mock_config_entry
):
    """[CMR-5] A blank device model becomes None in the copy too, not `""`.

    `model_family` lookups are keyed on this value; an empty string is a key that
    matches nothing and reads as "a model we do not know" rather than "no model",
    which is a different diagnosis.

    RED: drop the `or None` from the copy and it returns `""`.
    """
    entity_id = _link_vacuum_to_device(
        hass,
        mock_config_entry,
        model="   ",
        device_identifier="cmr5bot",
        object_id="cmr5bot",
        unique_id="uid-cmr5",
    )

    assert _adapter_copy(hass, entity_id) is None
    assert _adapter_copy(hass, entity_id) == manager._get_registry_model_code(
        vacuum_entity_id=entity_id
    ), "the two copies disagree on a blank model"


def test_cmr6_the_adapter_copy_handles_a_missing_entity_and_device(
    manager, hass, mock_config_entry
):
    """[CMR-6] The copy's two refusals: no entity at all, and an entity with no device.

    Both must answer None rather than raising. This runs at adapter REGISTRATION, so
    an exception here takes the whole brand's registration down -- and registration
    happens for every vacuum on every start.

    The unregistered-entity row is the one worth having: `er.async_get(...).async_get`
    returns None for an id the registry has never seen, which is exactly what a
    vacuum being added for the first time looks like.
    """
    mock_config_entry.add_to_hass(hass)

    # (a) an entity the registry has never heard of
    assert _adapter_copy(hass, "vacuum.never_registered_at_all") is None
    assert _adapter_copy(hass, "vacuum.never_registered_at_all") == (
        manager._get_registry_model_code(vacuum_entity_id="vacuum.never_registered_at_all")
    )

    # (b) a registered entity with no linked device
    entry = er.async_get(hass).async_get_or_create(
        "vacuum",
        "demo",
        "uid-cmr6",
        config_entry=mock_config_entry,
        suggested_object_id="cmr6bot",
    )
    assert entry.device_id is None, "precondition: no device linked"

    assert _adapter_copy(hass, entry.entity_id) is None
    assert _adapter_copy(hass, entry.entity_id) == manager._get_registry_model_code(
        vacuum_entity_id=entry.entity_id
    ), "the two copies disagree on an entity with no device"


def test_cmr7_home_assistant_refuses_the_stale_device_link(
    manager, hass, mock_config_entry
):
    """[CMR-7] WHY both copies' `device_entry is None` arm is UNREACHABLE.

    Both resolvers guard it -- `if device_entry is None: return None` -- and neither
    arm has ever run. The obvious test is an entity whose `device_id` names a device
    the registry does not have, and **Home Assistant will not let you build that**:
    `async_update_entity` raises `ValueError: Device ... does not exist`. The entity
    and device registries are not independent stores here; the entity registry
    validates the link on write, and removing a device cleans up its entities rather
    than orphaning them.

    So the arm is defensive against a state HA's own registry refuses to create, and
    the honest thing is to pin THAT rather than reach into registry internals to
    manufacture it. Recorded as a test instead of a comment because it is
    falsifiable: if a future HA stops validating, this goes red and the arm becomes a
    real gap that wants a real test.

    RED: HA accepting an unknown device_id.
    """
    import pytest as _pytest

    entity_id = _link_vacuum_to_device(
        hass,
        mock_config_entry,
        model="RoboVac X9",
        device_identifier="cmr7bot",
        object_id="cmr7bot",
        unique_id="uid-cmr7",
    )
    registry = er.async_get(hass)
    assert _adapter_copy(hass, entity_id) == "RoboVac X9", (
        "precondition: it resolves while the link is real"
    )

    bogus = "deadbeefdeadbeefdeadbeef"
    assert dr.async_get(hass).async_get(bogus) is None, "precondition: no such device"
    with _pytest.raises(ValueError, match="does not exist"):
        registry.async_update_entity(entity_id, device_id=bogus)

    # The link is untouched, so both copies still agree on the real answer.
    assert _adapter_copy(hass, entity_id) == "RoboVac X9"
    assert _adapter_copy(hass, entity_id) == manager._get_registry_model_code(
        vacuum_entity_id=entity_id
    )


# ---------------------------------------------------------------------------
# NOT TESTED -- both copies' `if device_entry is None: return None`
#
# UNREACHABLE, red set deliberately EMPTY, and [CMR-7] pins the reason. Home
# Assistant's entity registry validates the device link on write:
# `async_update_entity(entity_id, device_id=<unknown>)` raises
# `ValueError: Device ... does not exist`, and removing a device cleans up its
# entities rather than orphaning them. So no test can put an entity in the state
# this guard defends against without reaching into registry internals, and
# manufacturing it that way would test the internals rather than the guard.
# Ablation confirms: deleting the guard from the adapter copy reddens nothing.
#
# Recorded rather than pragma'd -- the programme admits `pragma: no cover` for
# logger lines only, and an unreachable guard with no written reason is the one that
# gets "simplified" later.
# ---------------------------------------------------------------------------
