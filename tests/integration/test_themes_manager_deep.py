"""Phase 8 integration tests — themes/manager.py deep paths.

Coverage targets
----------------
[TMD-1]  register_update_callback fires on mutation.
[TMD-2]  unregister_update_callback silences callback after removal.
[TMD-3]  Callback exception does not propagate to the calling mutation.
[TMD-4]  Duplicate register_update_callback is idempotent (no double-fire).
[TMD-5]  delete_theme clears active_theme_id for every vacuum using it.
[TMD-6]  revert_draft with no active theme returns ok=True, active_theme_id=None.
[TMD-7]  update_working_draft None value removes key from bucket.
[TMD-8]  update_working_draft empty-string value removes key from bucket.
[TMD-9]  import_theme deduplicates name with '(imported)' suffix.
[TMD-10] update_working_draft sets draft_dirty=True when draft is non-empty.
"""

from __future__ import annotations


_VAC = "vacuum.alfred"
_VAC2 = "vacuum.bob"


def _save_new_theme(manager, name: str, *, vacuum_entity_id: str = _VAC) -> str:
    """Save a new theme for a vacuum and return the theme_id."""
    result = manager.themes.save_theme_as_new(
        vacuum_entity_id=vacuum_entity_id,
        name=name,
    )
    return result["theme_id"]


# ---------------------------------------------------------------------------
# [TMD-1] register_update_callback fires on mutation
# ---------------------------------------------------------------------------

def test_register_update_callback_fires_on_save(manager):
    """[TMD-1] Registered callback is called when save_theme_as_new mutates state."""
    calls: list = []

    def cb(*, vacuum_entity_id):
        calls.append(vacuum_entity_id)

    manager.themes.register_update_callback(cb)
    manager.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="Test Theme")

    assert len(calls) == 1
    assert calls[0] == _VAC


def test_register_update_callback_fires_with_none_on_library_mutation(manager):
    """[TMD-1] Library-wide mutations (rename, delete) pass vacuum_entity_id=None."""
    theme_id = _save_new_theme(manager, "Library Theme")

    calls: list = []
    def cb(*, vacuum_entity_id):
        calls.append(vacuum_entity_id)

    manager.themes.register_update_callback(cb)
    manager.themes.rename_theme(theme_id=theme_id, name="Renamed")

    assert len(calls) == 1
    assert calls[0] is None


# ---------------------------------------------------------------------------
# [TMD-2] unregister_update_callback silences callback
# ---------------------------------------------------------------------------

def test_unregister_update_callback_stops_fires(manager):
    """[TMD-2] Callback is no longer called after unregister."""
    calls: list = []

    def cb(*, vacuum_entity_id):
        calls.append(vacuum_entity_id)

    manager.themes.register_update_callback(cb)
    manager.themes.unregister_update_callback(cb)
    manager.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="After Unregister")

    assert calls == []


def test_unregister_nonexistent_callback_is_safe(manager):
    """[TMD-2] Unregistering a callback that was never registered does not raise."""
    def cb(*, vacuum_entity_id):
        pass

    manager.themes.unregister_update_callback(cb)  # should not raise


# ---------------------------------------------------------------------------
# [TMD-3] Callback exception does not propagate
# ---------------------------------------------------------------------------

def test_callback_exception_does_not_propagate(manager):
    """[TMD-3] A raising callback does not prevent the mutation from completing."""
    def bad_cb(*, vacuum_entity_id):
        raise RuntimeError("test exception")

    manager.themes.register_update_callback(bad_cb)
    # Should not raise despite the callback raising.
    result = manager.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="Safe Theme")
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# [TMD-4] Duplicate registration is idempotent
# ---------------------------------------------------------------------------

def test_duplicate_register_fires_callback_only_once(manager):
    """[TMD-4] Registering the same callback twice only fires it once per mutation."""
    calls: list = []

    def cb(*, vacuum_entity_id):
        calls.append(vacuum_entity_id)

    manager.themes.register_update_callback(cb)
    manager.themes.register_update_callback(cb)  # duplicate
    manager.themes.save_theme_as_new(vacuum_entity_id=_VAC, name="Dup Test")

    assert len(calls) == 1


# ---------------------------------------------------------------------------
# [TMD-5] delete_theme clears active_theme_id for vacuum using it
# ---------------------------------------------------------------------------

def test_delete_theme_clears_vacuum_active_theme_id(manager):
    """[TMD-5] delete_theme sets active_theme_id=None for any vacuum using that theme."""
    theme_id = _save_new_theme(manager, "Active Theme")
    # Verify the vacuum has this as active
    vac_data = manager.data["theme"]["vacuums"][_VAC]
    assert vac_data["active_theme_id"] == theme_id

    manager.themes.delete_theme(theme_id=theme_id)

    vac_data = manager.data["theme"]["vacuums"][_VAC]
    assert vac_data["active_theme_id"] is None


def test_delete_theme_clears_multiple_vacuum_active_theme_ids(manager):
    """[TMD-5] delete_theme clears active_theme_id across all vacuums using it."""
    # Save theme from vac1, then set it active on vac2 as well.
    theme_id = _save_new_theme(manager, "Shared Theme")
    manager.themes.set_active_theme(vacuum_entity_id=_VAC2, theme_id=theme_id)

    manager.themes.delete_theme(theme_id=theme_id)

    vac1 = manager.data["theme"]["vacuums"][_VAC]
    vac2 = manager.data["theme"]["vacuums"][_VAC2]
    assert vac1["active_theme_id"] is None
    assert vac2["active_theme_id"] is None


# ---------------------------------------------------------------------------
# [TMD-6] revert_draft with no active theme
# ---------------------------------------------------------------------------

def test_revert_draft_no_active_theme_returns_ok(manager):
    """[TMD-6] revert_draft works even when no active theme is set."""
    # Vacuum has no active theme initially.
    result = manager.themes.revert_draft(vacuum_entity_id=_VAC)
    assert result["ok"] is True
    assert result.get("active_theme_id") is None
    assert result["draft_dirty"] is False


# ---------------------------------------------------------------------------
# [TMD-7] / [TMD-8] update_working_draft removes None / empty-string keys
# ---------------------------------------------------------------------------

def test_update_working_draft_none_value_removes_key(manager):
    """[TMD-7] Passing None for a token key removes it from the draft bucket."""
    manager.themes.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"bg_color": "#fff"},
    )
    manager.themes.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"bg_color": None},
    )
    draft = manager.data["theme"]["vacuums"][_VAC]["working_draft"]
    assert "bg_color" not in draft["tokens"]


def test_update_working_draft_empty_string_removes_key(manager):
    """[TMD-8] Passing '' for a token key removes it from the draft bucket."""
    manager.themes.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"accent": "#abc"},
    )
    manager.themes.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"accent": ""},
    )
    draft = manager.data["theme"]["vacuums"][_VAC]["working_draft"]
    assert "accent" not in draft["tokens"]


# ---------------------------------------------------------------------------
# [TMD-9] import_theme name deduplication
# ---------------------------------------------------------------------------

def test_import_theme_deduplicates_name(manager):
    """[TMD-9] Importing a theme whose name already exists appends '(imported)'."""
    _save_new_theme(manager, "My Theme")
    result = manager.themes.import_theme(
        payload={"name": "My Theme", "tokens": {"x": "1"}}
    )
    assert result["ok"] is True
    theme_id = result["theme_id"]
    saved_name = manager.data["theme"]["library"][theme_id]["name"]
    assert saved_name == "My Theme (imported)"


def test_import_theme_unique_name_not_modified(manager):
    """[TMD-9] Importing a theme with a unique name does not alter the name."""
    result = manager.themes.import_theme(
        payload={"name": "Brand New Theme", "tokens": {}}
    )
    assert result["ok"] is True
    theme_id = result["theme_id"]
    saved_name = manager.data["theme"]["library"][theme_id]["name"]
    assert saved_name == "Brand New Theme"


# ---------------------------------------------------------------------------
# [TMD-10] update_working_draft sets draft_dirty
# ---------------------------------------------------------------------------

def test_update_working_draft_sets_draft_dirty_when_nonempty(manager):
    """[TMD-10] draft_dirty becomes True when any draft bucket is non-empty."""
    manager.themes.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"color": "#f00"},
    )
    vac = manager.data["theme"]["vacuums"][_VAC]
    assert vac["draft_dirty"] is True


def test_update_working_draft_draft_dirty_false_when_all_removed(manager):
    """[TMD-10] draft_dirty is False after all keys are removed via None values."""
    manager.themes.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"color": "#f00"},
    )
    manager.themes.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"color": None},
    )
    vac = manager.data["theme"]["vacuums"][_VAC]
    assert vac["draft_dirty"] is False
