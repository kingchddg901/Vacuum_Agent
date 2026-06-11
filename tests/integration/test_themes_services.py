"""Phase 6 integration tests — theme HA service handlers.

Coverage targets
----------------
[TS-1]  get_theme_library service returns expected keys.
[TS-2]  save_theme_as_new service creates theme in library.
[TS-3]  overwrite_theme service raises ServiceValidationError for unknown theme.
[TS-4]  rename_theme service updates name; raises for unknown theme.
[TS-5]  delete_theme service removes theme; raises for unknown theme.
[TS-6]  set_active_theme service succeeds; raises for unknown theme.
[TS-7]  update_working_draft service returns ok=True dict.
[TS-8]  revert_draft service returns ok=True dict.
[TS-9]  export_theme service returns dict; raises for unknown theme.
[TS-10] import_theme service adds theme; raises for invalid payload.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.exceptions import ServiceValidationError

from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


@pytest.fixture
async def manager_with_theme_services(hass, manager):
    """Manager with theme services registered and cleaned up on teardown."""
    from custom_components.eufy_vacuum.themes.services import (
        async_register_theme_services,
        async_unregister_theme_services,
    )
    await async_register_theme_services(hass)
    yield manager
    await async_unregister_theme_services(hass)


async def _save_theme(hass, name="Test Theme") -> str:
    """Save a new theme via service and return its theme_id."""
    result = await hass.services.async_call(
        DOMAIN,
        "save_theme_as_new",
        {"vacuum_entity_id": _VAC, "name": name},
        blocking=True,
        return_response=True,
    )
    return result["theme_id"]


# ---------------------------------------------------------------------------
# [TS-1] get_theme_library
# ---------------------------------------------------------------------------

async def test_get_theme_library_service_returns_structure(hass, manager_with_theme_services):
    """[TS-1] get_theme_library service returns expected top-level keys."""
    result = await hass.services.async_call(
        DOMAIN, "get_theme_library", {}, blocking=True, return_response=True
    )
    assert "default_theme_id" in result
    assert "themes" in result
    assert "library" in result


# ---------------------------------------------------------------------------
# [TS-2] save_theme_as_new
# ---------------------------------------------------------------------------

async def test_save_theme_as_new_service_creates_theme(hass, manager_with_theme_services):
    """[TS-2] save_theme_as_new service creates a new theme in the library."""
    theme_id = await _save_theme(hass, "My New Theme")
    library = (await hass.services.async_call(
        DOMAIN, "get_theme_library", {}, blocking=True, return_response=True
    ))["library"]
    assert theme_id in library
    assert library[theme_id]["name"] == "My New Theme"


# ---------------------------------------------------------------------------
# [TS-3] overwrite_theme
# ---------------------------------------------------------------------------

async def test_overwrite_theme_service_raises_for_unknown(hass, manager_with_theme_services):
    """[TS-3] overwrite_theme raises ServiceValidationError for unknown theme."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "overwrite_theme",
            {"vacuum_entity_id": _VAC, "theme_id": "does_not_exist"},
            blocking=True,
            return_response=True,
        )


async def test_overwrite_theme_service_saves_and_returns_result(hass, manager_with_theme_services):
    """[TS-3] overwrite_theme success path persists and returns the mutation result.

    Drives the handler past _raise_if_failed (themes/services.py:166) into the
    save+return tail (167-168): the existing-theme branch returns ok=True, so the
    handler must call manager.async_save() and return the real result dict.
    """
    manager = manager_with_theme_services
    theme_id = await _save_theme(hass, "Overwrite Me")

    # Spy on the real async_save (wraps -> persistence still runs) to confirm the
    # handler's save tail executed, while asserting the returned result too.
    real_async_save = manager.async_save
    spy = AsyncMock(wraps=real_async_save)
    manager.async_save = spy
    try:
        result = await hass.services.async_call(
            DOMAIN,
            "overwrite_theme",
            {"vacuum_entity_id": _VAC, "theme_id": theme_id},
            blocking=True,
            return_response=True,
        )
    finally:
        manager.async_save = real_async_save

    # Returned result is the manager's real overwrite mutation response (line 168).
    assert result["ok"] is True
    assert result["theme_id"] == theme_id
    assert result.get("active_theme_id") == theme_id
    assert result.get("draft_dirty") is False
    # The save tail (line 167) ran.
    spy.assert_awaited_once()


# ---------------------------------------------------------------------------
# [TS-4] rename_theme
# ---------------------------------------------------------------------------

async def test_rename_theme_service_updates_name(hass, manager_with_theme_services):
    """[TS-4] rename_theme service changes the theme name in the library."""
    theme_id = await _save_theme(hass, "Before Rename")
    result = await hass.services.async_call(
        DOMAIN,
        "rename_theme",
        {"theme_id": theme_id, "name": "After Rename"},
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is True
    library = (await hass.services.async_call(
        DOMAIN, "get_theme_library", {}, blocking=True, return_response=True
    ))["library"]
    assert library[theme_id]["name"] == "After Rename"


async def test_rename_theme_service_raises_for_unknown(hass, manager_with_theme_services):
    """[TS-4] rename_theme raises ServiceValidationError for unknown theme."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "rename_theme",
            {"theme_id": "ghost_id", "name": "Whatever"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [TS-5] delete_theme
# ---------------------------------------------------------------------------

async def test_delete_theme_service_removes_from_library(hass, manager_with_theme_services):
    """[TS-5] delete_theme service removes the theme from the library."""
    theme_id = await _save_theme(hass, "To Delete")
    await hass.services.async_call(
        DOMAIN, "delete_theme", {"theme_id": theme_id}, blocking=True, return_response=True
    )
    library = (await hass.services.async_call(
        DOMAIN, "get_theme_library", {}, blocking=True, return_response=True
    ))["library"]
    assert theme_id not in library


async def test_delete_theme_service_raises_for_unknown(hass, manager_with_theme_services):
    """[TS-5] delete_theme raises ServiceValidationError for unknown theme."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "delete_theme",
            {"theme_id": "nonexistent"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [TS-6] set_active_theme
# ---------------------------------------------------------------------------

async def test_set_active_theme_service_succeeds(hass, manager_with_theme_services):
    """[TS-6] set_active_theme service returns ok=True for known theme."""
    theme_id = await _save_theme(hass)
    result = await hass.services.async_call(
        DOMAIN,
        "set_active_theme",
        {"vacuum_entity_id": _VAC, "theme_id": theme_id},
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is True


async def test_set_active_theme_service_raises_for_unknown(hass, manager_with_theme_services):
    """[TS-6] set_active_theme raises ServiceValidationError for unknown theme."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_active_theme",
            {"vacuum_entity_id": _VAC, "theme_id": "ghost"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [TS-7] update_working_draft
# ---------------------------------------------------------------------------

async def test_update_working_draft_service_returns_dict(hass, manager_with_theme_services):
    """[TS-7] update_working_draft service returns ok=True and draft_dirty."""
    result = await hass.services.async_call(
        DOMAIN,
        "update_working_draft",
        {"vacuum_entity_id": _VAC, "tokens": {"primary": "#ff0000"}},
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is True
    assert "draft_dirty" in result


# ---------------------------------------------------------------------------
# [TS-8] revert_draft
# ---------------------------------------------------------------------------

async def test_revert_draft_service_returns_dict(hass, manager_with_theme_services):
    """[TS-8] revert_draft service returns ok=True and draft_dirty=False."""
    result = await hass.services.async_call(
        DOMAIN,
        "revert_draft",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is True
    assert result.get("draft_dirty") is False


# ---------------------------------------------------------------------------
# [TS-9] export_theme
# ---------------------------------------------------------------------------

async def test_export_theme_service_returns_dict(hass, manager_with_theme_services):
    """[TS-9] export_theme service returns ok=True with version and theme."""
    theme_id = await _save_theme(hass, "Exportable")
    result = await hass.services.async_call(
        DOMAIN,
        "export_theme",
        {"theme_id": theme_id},
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is True
    assert result["version"] == 1
    assert "theme" in result


async def test_export_theme_service_raises_for_unknown(hass, manager_with_theme_services):
    """[TS-9] export_theme raises ServiceValidationError for unknown theme."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "export_theme",
            {"theme_id": "missing"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [TS-10] import_theme
# ---------------------------------------------------------------------------

async def test_import_theme_service_adds_to_library(hass, manager_with_theme_services):
    """[TS-10] import_theme service adds the theme to the library."""
    payload = {"theme": {"name": "Imported", "tokens": {}, "colors": {}, "alpha": {}}}
    result = await hass.services.async_call(
        DOMAIN,
        "import_theme",
        {"payload": payload},
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is True
    library = (await hass.services.async_call(
        DOMAIN, "get_theme_library", {}, blocking=True, return_response=True
    ))["library"]
    assert result["theme_id"] in library


async def test_import_theme_service_raises_for_missing_name(hass, manager_with_theme_services):
    """[TS-10] import_theme raises ServiceValidationError when name is empty."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "import_theme",
            {"payload": {"theme": {"name": ""}}},
            blocking=True,
            return_response=True,
        )
