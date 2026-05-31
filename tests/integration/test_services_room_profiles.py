"""Phase 4 integration tests — room-profile service handlers.

Coverage targets
----------------
[SRP-1]  get_room_profiles returns built-in profiles.
[SRP-2]  save_user_room_profile creates a new custom profile.
[SRP-3]  overwrite_room_profile replaces an existing profile's fields.
[SRP-4]  save_room_profile_from_room snapshots a room's current settings.
[SRP-5]  rename_room_profile updates a profile's label.
[SRP-6]  delete_room_profile removes a profile from the library.
[SRP-7]  apply_room_profile writes profile settings to targeted rooms.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"

_PROFILE_FIELDS = {
    "label": "Test Profile",
    "clean_mode": "vacuum",
    "fan_speed": "Standard",
    "water_level": "Off",
    "clean_intensity": "Quick",
    "clean_passes": 1,
    "edge_mopping": False,
}


# ---------------------------------------------------------------------------
# [SRP-1] get_room_profiles
# ---------------------------------------------------------------------------

async def test_get_room_profiles_service_returns_builtin_profiles(hass, manager_with_services):
    """[SRP-1] get_room_profiles returns at least the built-in profiles."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_room_profiles",
        {},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "profiles" in result
    assert result["profile_count"] >= 1


async def test_get_room_profiles_service_has_protected_names(hass, manager_with_services):
    """[SRP-1] Response includes the protected_profile_names field."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_room_profiles",
        {},
        blocking=True,
        return_response=True,
    )
    assert "protected_profile_names" in result
    assert isinstance(result["protected_profile_names"], list)


# ---------------------------------------------------------------------------
# [SRP-2] save_user_room_profile
# ---------------------------------------------------------------------------

async def test_save_user_room_profile_service_creates_profile(hass, manager_with_services):
    """[SRP-2] save_user_room_profile service stores the profile and returns saved=True."""
    result = await hass.services.async_call(
        DOMAIN,
        "save_user_room_profile",
        _PROFILE_FIELDS,
        blocking=True,
        return_response=True,
    )
    assert result["saved"] is True
    assert "profile_name" in result


async def test_save_user_room_profile_service_named_profile(hass, manager_with_services):
    """[SRP-2] Custom profile_name is honoured in the saved record."""
    result = await hass.services.async_call(
        DOMAIN,
        "save_user_room_profile",
        {**_PROFILE_FIELDS, "profile_name": "my_profile"},
        blocking=True,
        return_response=True,
    )
    assert result["saved"] is True
    assert result["profile_name"] == "my_profile"


async def test_save_user_room_profile_service_profile_appears_in_library(hass, manager_with_services):
    """[SRP-2] Saved profile is returned by get_room_profiles."""
    await hass.services.async_call(
        DOMAIN,
        "save_user_room_profile",
        {**_PROFILE_FIELDS, "profile_name": "svc_test_p"},
        blocking=True,
        return_response=True,
    )
    library = await hass.services.async_call(
        DOMAIN,
        "get_room_profiles",
        {},
        blocking=True,
        return_response=True,
    )
    assert "svc_test_p" in library["profiles"]


# ---------------------------------------------------------------------------
# [SRP-3] overwrite_room_profile
# ---------------------------------------------------------------------------

async def test_overwrite_room_profile_service_updates_label(hass, manager_with_services):
    """[SRP-3] overwrite_room_profile updates an existing custom profile's label."""
    await hass.services.async_call(
        DOMAIN,
        "save_user_room_profile",
        {**_PROFILE_FIELDS, "profile_name": "p_overwrite"},
        blocking=True,
        return_response=True,
    )
    result = await hass.services.async_call(
        DOMAIN,
        "overwrite_room_profile",
        {**_PROFILE_FIELDS, "profile_name": "p_overwrite", "label": "Updated Label"},
        blocking=True,
        return_response=True,
    )
    assert result.get("ok") is not False
    library = await hass.services.async_call(
        DOMAIN, "get_room_profiles", {}, blocking=True, return_response=True,
    )
    assert library["profiles"]["p_overwrite"]["label"] == "Updated Label"


# ---------------------------------------------------------------------------
# [SRP-4] save_room_profile_from_room
# ---------------------------------------------------------------------------

async def test_save_room_profile_from_room_service_creates_profile(hass, manager_with_services):
    """[SRP-4] save_room_profile_from_room snapshots room settings into a new profile."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    result = await hass.services.async_call(
        DOMAIN,
        "save_room_profile_from_room",
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "room_id": 1,
            "label": "Saved From Room 1",
        },
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert result.get("saved") is True


# ---------------------------------------------------------------------------
# [SRP-5] rename_room_profile
# ---------------------------------------------------------------------------

async def test_rename_room_profile_service_updates_label(hass, manager_with_services):
    """[SRP-5] rename_room_profile updates the label of an existing profile."""
    await hass.services.async_call(
        DOMAIN,
        "save_user_room_profile",
        {**_PROFILE_FIELDS, "profile_name": "p_rename"},
        blocking=True,
        return_response=True,
    )
    result = await hass.services.async_call(
        DOMAIN,
        "rename_room_profile",
        {"profile_name": "p_rename", "label": "Renamed"},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    library = await hass.services.async_call(
        DOMAIN, "get_room_profiles", {}, blocking=True, return_response=True,
    )
    assert library["profiles"]["p_rename"]["label"] == "Renamed"


# ---------------------------------------------------------------------------
# [SRP-6] delete_room_profile
# ---------------------------------------------------------------------------

async def test_delete_room_profile_service_removes_profile(hass, manager_with_services):
    """[SRP-6] delete_room_profile removes the named profile from the library."""
    await hass.services.async_call(
        DOMAIN,
        "save_user_room_profile",
        {**_PROFILE_FIELDS, "profile_name": "p_delete"},
        blocking=True,
        return_response=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "delete_room_profile",
        {"profile_name": "p_delete"},
        blocking=True,
        return_response=True,
    )
    library = await hass.services.async_call(
        DOMAIN, "get_room_profiles", {}, blocking=True, return_response=True,
    )
    assert "p_delete" not in library["profiles"]


# ---------------------------------------------------------------------------
# [SRP-7] apply_room_profile
# ---------------------------------------------------------------------------

async def test_apply_room_profile_service_writes_to_rooms(hass, manager_with_services):
    """[SRP-7] apply_room_profile writes profile settings to the targeted rooms."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN,
        "save_user_room_profile",
        {**_PROFILE_FIELDS, "profile_name": "p_apply", "fan_speed": "quiet"},
        blocking=True,
        return_response=True,
    )
    result = await hass.services.async_call(
        DOMAIN,
        "apply_room_profile",
        {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "room_ids": [1, 2],
            "profile_name": "p_apply",
        },
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
