"""INKV8ZQD — durable per-vacuum state is minted only for a MANAGED vacuum.

Coverage targets
----------------
[UV-1] A WRITE aimed at an unmanaged vacuum raises ServiceValidationError.
[UV-2] ...and mints NOTHING: the store is byte-identical after the refusal.
[UV-3] A READ aimed at an unmanaged vacuum returns the empty shape with a reason,
       and does NOT raise -- discovery must not become an error.
[UV-4] ...and mints nothing either. This is the one that used to fail: get_record's
       own docstring said "Public read accessor (creates if absent)".
[UV-5] The managed vacuum is unaffected -- the guard is not a blanket refusal.
[UV-6] get_pause_timeout_settings, a REGISTERED READ, no longer mints into
       data["vacuums"] -- the authority the guard itself gates on. Without this the
       guard is self-defeating: one read with a typo'd id makes it "managed".

WHY THESE ASSERT ON THE STORE, NOT THE RETURN VALUE. A phantom bucket is invisible
in the response -- the call succeeds either way. The defect was only ever observable
as durable state, so the store is the oracle.
"""
from __future__ import annotations

import copy

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN
from custom_components.eufy_vacuum.core.error_tracker import ErrorTracker

_MANAGED = "vacuum.alfred"
_GHOST = "vacuum.does_not_exist"


async def test_write_to_unmanaged_vacuum_refuses(hass, manager_with_services, managed_vacuum):
    """[UV-1] A mutation aimed at a vacuum we do not manage raises."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "clear_queue", {"vacuum_entity_id": _GHOST},
            blocking=True, return_response=True,
        )


async def test_refused_write_mints_nothing(hass, manager_with_services, managed_vacuum):
    """[UV-2] The refusal leaves the store byte-identical."""
    before = copy.deepcopy(manager_with_services.data)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "clear_queue", {"vacuum_entity_id": _GHOST},
            blocking=True, return_response=True,
        )
    assert manager_with_services.data == before, "a refused write mutated the store"


async def test_read_of_unmanaged_vacuum_answers_empty_without_raising(
    hass, manager_with_services
):
    """[UV-3] A read answers, with a reason, rather than raising."""
    result = await hass.services.async_call(
        DOMAIN, "get_recent_errors", {"vacuum_entity_id": _GHOST},
        blocking=True, return_response=True,
    )
    assert result["reason"] == "unmanaged_vacuum"
    assert result["vacuum_entity_id"] == _GHOST
    assert result["errors"] == []


async def test_read_of_unmanaged_vacuum_mints_nothing(hass, manager_with_services, managed_vacuum):
    """[UV-4] The read creates no durable record. This is the original defect.

    THE TRACKER MUST BE LOADED. The first version of this test asserted the same
    thing without one, and stayed GREEN when the guard was ablated: the handler
    returned `tracker_not_loaded` before ever reaching get_record, so it proved
    only that an unreached path mints nothing. Caught by ablation, not review.
    """
    hass.data[DOMAIN][DATA_ERROR_TRACKER] = ErrorTracker(
        hass, runtime_manager=manager_with_services
    )
    await hass.services.async_call(
        DOMAIN, "get_recent_errors", {"vacuum_entity_id": _GHOST},
        blocking=True, return_response=True,
    )
    tracker_root = manager_with_services.data.get("error_tracker") or {}
    assert _GHOST not in tracker_root, "a READ minted a durable error record"
    assert _GHOST not in (manager_with_services.data.get("vacuums") or {})


async def test_managed_vacuum_still_works(hass, manager_with_services, managed_vacuum):
    """[UV-5] The guard refuses the unmanaged case ONLY.

    Without this, [UV-1..4] would all pass against a guard that refused
    everything -- which is the cheapest way to make a refusal test green and
    the reason it is worth writing down.
    """
    result = await hass.services.async_call(
        DOMAIN, "get_recent_errors", {"vacuum_entity_id": _MANAGED},
        blocking=True, return_response=True,
    )
    assert result.get("reason") != "unmanaged_vacuum"


async def test_pause_timeout_read_does_not_mint_the_authority(
    hass, manager_with_services
):
    """[UV-6] The read that could have defeated the whole guard.

    CALLED DIRECTLY, ON PURPOSE. Going through the service would prove nothing:
    the handler carries its own read guard and returns before the manager method
    runs, so this test stayed GREEN with the manager fix reverted. Two guards, and
    the outer one hid whether the inner one existed -- the exact shape of
    SETUP-REJ-2, found here by ablation.
    """
    before = set(manager_with_services.data.get("vacuums") or {})
    manager_with_services.get_pause_timeout_settings(vacuum_entity_id=_GHOST)
    after = set(manager_with_services.data.get("vacuums") or {})
    assert after == before, (
        "a READ minted into data['vacuums'] -- the dict require_managed_vacuum "
        "gates on, so this would silently make the ghost 'managed'"
    )
