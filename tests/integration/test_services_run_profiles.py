"""Phase 4 integration tests — run-profile service handlers.

Coverage targets
----------------
[SRN-1]  get_saved_run_profiles returns empty profile list initially.
[SRN-2]  save_run_profile snapshots the current enabled rooms as a profile.
[SRN-3]  save_run_profile fails gracefully when no rooms are selected.
[SRN-4]  apply_run_profile restores room selections from a saved profile.
[SRN-5]  apply_run_profile raises ServiceValidationError for unknown profile_id.
[SRN-6]  rename_run_profile updates the profile name.
[SRN-7]  rename_run_profile raises ServiceValidationError for unknown profile_id.
[SRN-8]  overwrite_run_profile raises ServiceValidationError for unknown profile_id.
[SRN-9]  delete_run_profile removes the profile from the library.
[SRN-10] delete_run_profile raises ServiceValidationError for unknown profile_id.
"""

from __future__ import annotations

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


@pytest.mark.parametrize("service,method,data", [
    ("save_run_profile", "save_run_profile", {"name": "x"}),
    ("apply_run_profile", "apply_run_profile", {"profile_id": "p"}),
    ("rename_run_profile", "rename_run_profile", {"profile_id": "p", "name": "x"}),
    ("overwrite_run_profile", "overwrite_run_profile", {"profile_id": "p"}),
    ("delete_run_profile", "delete_run_profile", {"profile_id": "p"}),
])
async def test_run_profile_handler_wraps_manager_error(
    hass, manager_with_services, monkeypatch, service, method, data
):
    """[SRN-11] a manager-layer failure surfaces to the caller as HomeAssistantError
    (the HA Silver action-exception contract), not a raw traceback."""
    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(manager_with_services, method, _boom)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, service,
            {"vacuum_entity_id": _VAC, "map_id": _MAP, **data},
            blocking=True, return_response=True)


# ---------------------------------------------------------------------------
# Helper — save one profile and return its profile_id
# ---------------------------------------------------------------------------

async def _save_profile(hass, manager_with_services, name: str = "My Profile") -> str:
    """Set up a map, build a queue, save a run profile, and return profile_id."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    manager_with_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    result = await hass.services.async_call(
        DOMAIN,
        "save_run_profile",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": name},
        blocking=True,
        return_response=True,
    )
    assert result.get("saved") is True
    return result["profile_id"]


# ---------------------------------------------------------------------------
# [SRN-1] get_saved_run_profiles
# ---------------------------------------------------------------------------

async def test_get_saved_run_profiles_empty_initially(hass, manager_with_services):
    """[SRN-1] get_saved_run_profiles returns an empty profile list initially."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_saved_run_profiles",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result["profile_count"] == 0
    assert result["profiles"] == []


async def test_get_saved_run_profiles_returns_correct_keys(hass, manager_with_services):
    """[SRN-1] Response includes vacuum_entity_id and map_id."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_saved_run_profiles",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["map_id"] == _MAP


# ---------------------------------------------------------------------------
# [SRN-2] — [SRN-3] save_run_profile
# ---------------------------------------------------------------------------

async def test_save_run_profile_service_creates_profile(hass, manager_with_services):
    """[SRN-2] save_run_profile returns saved=True and a profile_id."""
    profile_id = await _save_profile(hass, manager_with_services, "Evening Run")
    assert isinstance(profile_id, str)
    assert len(profile_id) > 0


async def test_save_run_profile_service_appears_in_library(hass, manager_with_services):
    """[SRN-2] Saved profile is returned by get_saved_run_profiles."""
    await _save_profile(hass, manager_with_services, "Evening Run")
    result = await hass.services.async_call(
        DOMAIN,
        "get_saved_run_profiles",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result["profile_count"] == 1
    assert result["profiles"][0]["name"] == "Evening Run"


async def test_save_run_profile_no_rooms_returns_not_saved(hass, manager_with_services):
    """[SRN-3] save_run_profile returns saved=False when no rooms are enabled."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "save_run_profile",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Empty Run"},
        blocking=True,
        return_response=True,
    )
    assert result["saved"] is False
    assert result["reason"] in ("no_rooms_selected", "missing_name", "no_rooms")


# ---------------------------------------------------------------------------
# [SRN-4] — [SRN-5] apply_run_profile
# ---------------------------------------------------------------------------

async def test_apply_run_profile_service_succeeds(hass, manager_with_services):
    """[SRN-4] apply_run_profile restores room selections from a saved profile."""
    profile_id = await _save_profile(hass, manager_with_services, "Restore Test")
    result = await hass.services.async_call(
        DOMAIN,
        "apply_run_profile",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "profile_id": profile_id},
        blocking=True,
        return_response=True,
    )
    assert result.get("applied") is True


async def test_apply_run_profile_service_unknown_raises(hass, manager_with_services):
    """[SRN-5] apply_run_profile raises ServiceValidationError for unknown profile_id."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "apply_run_profile",
            {"vacuum_entity_id": _VAC, "map_id": _MAP, "profile_id": "nonexistent"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [SRN-6] — [SRN-7] rename_run_profile
# ---------------------------------------------------------------------------

async def test_rename_run_profile_service_updates_name(hass, manager_with_services):
    """[SRN-6] rename_run_profile returns renamed=True."""
    profile_id = await _save_profile(hass, manager_with_services, "Old Name")
    result = await hass.services.async_call(
        DOMAIN,
        "rename_run_profile",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "profile_id": profile_id, "name": "New Name"},
        blocking=True,
        return_response=True,
    )
    assert result.get("renamed") is True


async def test_rename_run_profile_service_unknown_raises(hass, manager_with_services):
    """[SRN-7] rename_run_profile raises ServiceValidationError for unknown profile_id."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "rename_run_profile",
            {"vacuum_entity_id": _VAC, "map_id": _MAP, "profile_id": "ghost", "name": "X"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [SRN-8] overwrite_run_profile
# ---------------------------------------------------------------------------

async def test_overwrite_run_profile_service_unknown_raises(hass, manager_with_services):
    """[SRN-8] overwrite_run_profile raises ServiceValidationError for unknown profile_id."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "overwrite_run_profile",
            {"vacuum_entity_id": _VAC, "map_id": _MAP, "profile_id": "ghost"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [SRN-9] — [SRN-10] delete_run_profile
# ---------------------------------------------------------------------------

async def test_delete_run_profile_service_removes_profile(hass, manager_with_services):
    """[SRN-9] delete_run_profile removes the profile from the library."""
    profile_id = await _save_profile(hass, manager_with_services, "To Delete")
    result = await hass.services.async_call(
        DOMAIN,
        "delete_run_profile",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "profile_id": profile_id},
        blocking=True,
        return_response=True,
    )
    assert result.get("deleted") is True

    library = await hass.services.async_call(
        DOMAIN,
        "get_saved_run_profiles",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert library["profile_count"] == 0


async def test_delete_run_profile_service_unknown_raises(hass, manager_with_services):
    """[SRN-10] delete_run_profile raises ServiceValidationError for unknown profile_id."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "delete_run_profile",
            {"vacuum_entity_id": _VAC, "map_id": _MAP, "profile_id": "ghost"},
            blocking=True,
            return_response=True,
        )
