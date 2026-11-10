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
[TS-11] set_theme_tags SERVICE stores tags and persists. The handler had no test;
        [TM-20] covers the manager METHOD and never enters services.py.
[TS-12] ...and raises ServiceValidationError for an unknown theme.
[TS-13] set_active_theme with vacuum_entity_id OMITTED skips the managed-vacuum
        guard -- a declared ruling, since refusing would break a library-wide call.
[TS-14] import_theme SCOPED to a vacuum does apply the guard: it passes for a
        managed one and raises for an unmanaged one.
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
    # INKV8ZQD: a service-layer fixture must MANAGE the vacuum it calls services
    # against. Production reaches this state through setup/workflow.py::add_vacuum,
    # which calls ensure_vacuum_record and whose own "already managed" check reads
    # data["vacuums"] -- the same dict require_managed_vacuum gates on. Derived from
    # the real function rather than a hand-built dict, so the fixture cannot drift
    # from what production actually produces.
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
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
    # RP-034/Q7: overwrite now refuses an empty draft (nothing to bracket a write
    # with) rather than silently no-op-succeeding, so this test — whose actual
    # goal is the save+return tail, not the refusal path — needs a real edit.
    await hass.services.async_call(
        DOMAIN, "update_working_draft",
        {"vacuum_entity_id": _VAC, "tokens": {"--evcc-accent": "#ff8800"}},
        blocking=True,
    )

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


# ---------------------------------------------------------------------------
# [TS-11]/[TS-12] set_theme_tags -- the one theme service with no handler test
# ---------------------------------------------------------------------------

async def test_ts11_set_theme_tags_service_stores_and_persists(hass, manager_with_theme_services):
    """[TS-11] The service handler, which [TM-20] does not reach.

    `set_theme_tags` is registered, documented in services.yaml, and called by the card
    for vibe tags -- and its HANDLER had no test. [TM-20] in test_themes_manager.py
    covers the manager METHOD thoroughly (six tests) by calling
    `manager.set_theme_tags` directly, so none of them executes a line of
    themes/services.py. That is the same shape as the `goto`/`start_zone_clean`
    closures: a live service nothing calls by its registered name.

    THE HANDLER DOES FOUR THINGS THE METHOD DOES NOT, which is why covering the method
    is not covering this: it resolves the manager, raises on a failed result, PERSISTS,
    and returns the result to the caller.

    THE SAVE TAIL NEEDS AN OBSERVABLE, AND A FIRST DRAFT GOT THAT WRONG. It read the
    tags back through a second service call and claimed that covered persistence -- it
    does not: `get_theme_library` reads the IN-MEMORY data, so ablating
    `await manager.async_save()` left the test GREEN. Measured, not assumed.

    IT IS A PLAIN CLOSURE, NOT A MOCK, for two reasons. The W0 ratchet holds this
    file's bare-mock total at 1 and raising it deliberately requires deleting the gate
    -- a second `AsyncMock` here was refused, correctly. And a counting wrapper is the
    better observable anyway: it states exactly what is being watched, still awaits the
    real save so persistence runs, and cannot answer an attribute the handler might
    start reading later. Restored in a `finally` either way.

    The tags are deliberately mixed-case with a blank, because the manager cleans
    (trim/lower/dedupe) and the cleaned form is what must reach the library: asserting
    the submitted form would pass against a handler that stored the raw input.
    """
    manager = manager_with_theme_services
    theme_id = await _save_theme(hass)

    saves: list[int] = []
    real_async_save = manager.async_save

    async def _counting_save(*args, **kwargs):
        saves.append(1)
        return await real_async_save(*args, **kwargs)

    manager.async_save = _counting_save
    try:
        result = await hass.services.async_call(
            DOMAIN,
            "set_theme_tags",
            {"theme_id": theme_id, "tags": ["Aurora", " aurora ", "Cosmic", ""]},
            blocking=True,
            return_response=True,
        )
    finally:
        manager.async_save = real_async_save

    assert result["ok"] is True
    assert len(saves) == 1, "the handler's save tail did not run"

    library = await hass.services.async_call(
        DOMAIN, "get_theme_library", {}, blocking=True, return_response=True
    )
    # The `themes` SUMMARY list carries only id/theme_id/name/source -- a first draft
    # read `tags` off it and got a KeyError. The tags live in the full `library` dict,
    # which is also where [TM-20] reads them. Worth knowing: the two differ, and the
    # summary deliberately does not carry everything.
    assert library["library"][theme_id]["tags"] == ["aurora", "cosmic"], (
        "the handler returned ok but the cleaned tags did not reach the library"
    )


async def test_ts12_set_theme_tags_service_raises_for_unknown_theme(hass, manager_with_theme_services):
    """[TS-12] A failed result is RAISED, not returned.

    The manager answers an unknown theme with `ok=False` -- [TM-20] pins that -- and the
    handler's `_raise_if_failed` is what turns it into a ServiceValidationError the
    caller sees. Without it the service would return `{"ok": False}` with a 200, and the
    card would show success for a write that did not happen.

    This is the arm [TS-11] does not take: together they cover both sides of
    `_raise_if_failed` for this handler.
    """
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_theme_tags",
            {"theme_id": "ghost_theme_id", "tags": ["aurora"]},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# [TS-13]/[TS-14] the conditional managed-vacuum guard, both arms
# ---------------------------------------------------------------------------

async def test_ts13_set_active_theme_without_a_vacuum_skips_the_guard(hass, manager_with_theme_services):
    """[TS-13] Omitting `vacuum_entity_id` must NOT be refused.

    `SET_ACTIVE_THEME_SCHEMA` makes the field `vol.Optional`, and the handler's comment
    states the ruling: "Omitted means no per-vacuum state is touched, so there is
    nothing to guard -- refusing there would break a full library import outright." So
    the guard is conditional ON PURPOSE, and the false arm is the library-wide call.

    [TS-6] always passes `_VAC`, so it only ever takes the true arm. This takes the
    other one, and asserts the call SUCCEEDS rather than merely not raising a specific
    error -- `ok is True` is what distinguishes "the guard was skipped" from "the guard
    was skipped and the handler then failed for another reason".
    """
    theme_id = await _save_theme(hass)

    result = await hass.services.async_call(
        DOMAIN,
        "set_active_theme",
        {"theme_id": theme_id},
        blocking=True,
        return_response=True,
    )
    assert result["ok"] is True


async def test_ts14_a_scoped_import_applies_the_managed_vacuum_guard(hass, manager_with_theme_services):
    """[TS-14] The TRUE arm of the same conditional, in the handler that had neither.

    `import_theme` is library-wide by default and SCOPED when a vacuum is named -- and
    no test ever named one, so the `require_managed_vacuum` call inside it had never
    run. The guard sits at the service boundary deliberately (comment INKV8ZQD): the
    manager's `_get_vacuum_theme` setdefaults a full draft record for ANY well-formed
    entity id, and it is also called during setup before the vacuum record exists, so
    the manager cannot be the one to refuse.

    BOTH OUTCOMES ARE DRIVEN. A scoped import against the fixture's MANAGED vacuum must
    pass the guard and succeed; one against a well-formed but unmanaged id must raise.
    The second is what gives the first its meaning -- a guard that let everything
    through would satisfy the success case alone.
    """
    exported = await hass.services.async_call(
        DOMAIN, "export_theme", {"theme_id": await _save_theme(hass, name="Scoped")},
        blocking=True, return_response=True,
    )
    payload = exported["payload"] if "payload" in exported else exported

    scoped = await hass.services.async_call(
        DOMAIN,
        "import_theme",
        {"payload": payload, "vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert scoped["ok"] is True

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "import_theme",
            {"payload": payload, "vacuum_entity_id": "vacuum.not_managed_here"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# RECORDED CEILING -- the four remaining partial branches in themes/services.py
#
# `save_theme_as_new`, `overwrite_theme`, `update_working_draft` and `revert_draft`
# each carry the same conditional guard, and for all four the FALSE arm is
# SCHEMA-UNREACHABLE: their schemas declare `vol.Required("vacuum_entity_id")`, so
# voluptuous rejects the call before the handler runs and `call.data.get(...)` can
# never be falsy. Verified by reading the four schemas, and the module's own comment
# says the same thing from the other side -- "two of these schemas make
# vacuum_entity_id OPTIONAL" -- which is SET_ACTIVE_THEME_SCHEMA and
# IMPORT_THEME_SCHEMA, the two [TS-13] and [TS-14] drive.
#
# So the conditional is uniform across six handlers while only two of them can take
# both arms. That is deliberate (one guard, written once, read the same way everywhere)
# and the cost is four partial branches that no input can close.
# ---------------------------------------------------------------------------
