"""Phase 6 integration tests — ThemeManager direct operations.

Coverage targets
----------------
[TM-1]  get_theme_library() returns expected structure.
[TM-2]  save_theme_as_new() adds theme to library.
[TM-3]  save_theme_as_new(set_as_default=True) sets default_theme_id.
[TM-4]  overwrite_theme() succeeds for known theme.
[TM-5]  overwrite_theme() returns ok=False for unknown theme.
[TM-5b] RP-034/Q7: overwrite_theme() refuses an empty working draft.
[TM-5c] RP-034/Q7: overwrite_theme() resolves against the target, never the active theme.
[TM-6]  rename_theme() updates theme name.
[TM-7]  rename_theme() returns ok=False for unknown theme.
[TM-8]  delete_theme() removes theme from library.
[TM-9]  delete_theme() returns ok=False for unknown theme.
[TM-9b] RP-034/CRUD-3/INIT-3: a deleted core theme does not survive a restart (tombstone).
[TM-9c] RP-034: the tombstone is core-only — deleting a manual theme writes no tombstone.
[TM-10] set_active_theme(vacuum_entity_id=...) points vacuum at theme.
[TM-11] set_active_theme(vacuum_entity_id=None) sets global default.
[TM-12] set_active_theme() returns ok=False for unknown theme.
[TM-13] update_working_draft() patches tokens; sets draft_dirty.
[TM-14] revert_draft() clears draft_dirty.
[TM-15] export_theme() returns JSON-safe dict with expected keys.
[TM-16] export_theme() returns ok=False for unknown theme.
[TM-17] import_theme() adds theme to library.
[TM-18] import_theme() returns ok=False for invalid payload.
[TM-18b] RP-034/PORT-1: a key outside --evcc-* is dropped and named in `rejected`.
[TM-18c] a clean import carries no `rejected` key.
[TM-18d] rejects combine across tokens/colors/alpha, deduplicated.
[TM-19] source provenance: saved=manual, export/summary carry source, imported keeps
        its provenance, `core` reserved for seeded themes (an imported copy → manual).
[TM-20] vibe tags + author survive import/export/overwrite; set_theme_tags
[TM-30] D9: a mutation that drops part of its input SAYS SO. Submitting twenty tags
        and submitting sixteen used to produce byte-identical responses, so the card
        could not tell the user their last four did not save and an automation could
        not detect it at all.
[TM-31] D9: each drop reason is distinguishable — over-limit, too long, duplicate and
        empty are four different things to tell a user.
[TM-32] D9: a clean submission carries no `dropped_tags` key, so its presence is a
        reliable signal rather than a field that is always there and usually empty.
        trims/lowers/dedupes/stores (ok=False for an unknown theme).
"""

from __future__ import annotations


_VAC = "vacuum.alfred"


def _save_new_theme(manager, name="My Theme") -> str:
    """Save a new theme for _VAC and return the theme_id."""
    result = manager.save_theme_as_new(vacuum_entity_id=_VAC, name=name)
    assert result["ok"] is True
    return result["theme_id"]


# ---------------------------------------------------------------------------
# [TM-1] get_theme_library
# ---------------------------------------------------------------------------

def test_get_theme_library_returns_expected_keys(manager):
    """[TM-1] get_theme_library() returns default_theme_id, themes, library."""
    result = manager.get_theme_library()
    assert "default_theme_id" in result
    assert "themes" in result
    assert "library" in result
    assert isinstance(result["themes"], list)
    assert isinstance(result["library"], dict)


# ---------------------------------------------------------------------------
# [TM-2] — [TM-3] save_theme_as_new
# ---------------------------------------------------------------------------

def test_save_theme_as_new_adds_to_library(manager):
    """[TM-2] save_theme_as_new() creates a new entry in the theme library."""
    result = manager.save_theme_as_new(vacuum_entity_id=_VAC, name="Blue Scheme")
    assert result["ok"] is True
    theme_id = result["theme_id"]
    library = manager.get_theme_library()["library"]
    assert theme_id in library
    assert library[theme_id]["name"] == "Blue Scheme"


def test_save_theme_as_new_sets_active_theme_id(manager):
    """[TM-2] save_theme_as_new() sets active_theme_id equal to theme_id."""
    result = manager.save_theme_as_new(vacuum_entity_id=_VAC, name="Test")
    assert result["active_theme_id"] == result["theme_id"]


def test_save_theme_as_new_set_as_default(manager):
    """[TM-3] save_theme_as_new(set_as_default=True) updates default_theme_id."""
    result = manager.save_theme_as_new(
        vacuum_entity_id=_VAC, name="Default Scheme", set_as_default=True
    )
    assert manager.get_theme_library()["default_theme_id"] == result["theme_id"]


# ---------------------------------------------------------------------------
# [TM-4] — [TM-5] overwrite_theme
# ---------------------------------------------------------------------------

def test_overwrite_theme_succeeds_for_known_theme(manager):
    """[TM-4] overwrite_theme() updates an existing library entry."""
    theme_id = _save_new_theme(manager)
    manager.update_working_draft(vacuum_entity_id=_VAC, colors={"bg": "#123456"})
    result = manager.overwrite_theme(vacuum_entity_id=_VAC, theme_id=theme_id)
    assert result["ok"] is True
    assert result["theme_id"] == theme_id


def test_overwrite_theme_unknown_returns_not_ok(manager):
    """[TM-5] overwrite_theme() returns ok=False for unknown theme_id."""
    result = manager.overwrite_theme(
        vacuum_entity_id=_VAC, theme_id="nonexistent_theme"
    )
    assert result["ok"] is False
    assert result["reason"] == "theme_not_found"


def test_overwrite_theme_refuses_empty_draft(manager):
    """[TM-5b] RP-034/Q7: an empty working draft refuses rather than silently
    wiping the target to {} — save_theme_as_new already left the draft empty."""
    theme_id = _save_new_theme(manager)
    library_before = manager.get_theme_library()["library"][theme_id]
    result = manager.overwrite_theme(vacuum_entity_id=_VAC, theme_id=theme_id)
    assert result["ok"] is False
    assert result["reason"] == "empty_draft"
    assert manager.get_theme_library()["library"][theme_id] == library_before


def test_overwrite_theme_uses_target_not_active(manager):
    """[TM-5c] RP-034/Q7: overwrite resolves against the TARGET theme's own
    stored palette, not whatever theme happens to be active — a distinct active
    theme's values must never leak into a different theme being overwritten."""
    target_id = manager.import_theme(
        payload={"theme": {"name": "Target", "tokens": {"--evcc-bg": "#111111"}}}
    )["theme_id"]
    active_id = manager.import_theme(
        payload={"theme": {"name": "Active", "tokens": {
            "--evcc-bg": "#000000", "--evcc-warn": "#ff0000",
        }}}
    )["theme_id"]
    manager.set_active_theme(vacuum_entity_id=_VAC, theme_id=active_id)
    manager.update_working_draft(vacuum_entity_id=_VAC, tokens={"--evcc-fg": "#dddddd"})

    result = manager.overwrite_theme(vacuum_entity_id=_VAC, theme_id=target_id)

    assert result["ok"] is True
    tokens = manager.get_theme_library()["library"][target_id]["tokens"]
    assert tokens["--evcc-bg"] == "#111111"   # the target's own value, untouched
    assert "--evcc-warn" not in tokens         # never leaked in from the active theme
    assert tokens["--evcc-fg"] == "#dddddd"    # the actual draft edit still lands


# ---------------------------------------------------------------------------
# [TM-6] — [TM-7] rename_theme
# ---------------------------------------------------------------------------

def test_rename_theme_updates_name(manager):
    """[TM-6] rename_theme() changes the theme's name in the library."""
    theme_id = _save_new_theme(manager, name="Old Name")
    result = manager.rename_theme(theme_id=theme_id, name="New Name")
    assert result["ok"] is True
    assert manager.get_theme_library()["library"][theme_id]["name"] == "New Name"


def test_rename_theme_unknown_returns_not_ok(manager):
    """[TM-7] rename_theme() returns ok=False for unknown theme_id."""
    result = manager.rename_theme(theme_id="ghost_id", name="Anything")
    assert result["ok"] is False
    assert result["reason"] == "theme_not_found"


# ---------------------------------------------------------------------------
# [TM-8] — [TM-9] delete_theme
# ---------------------------------------------------------------------------

def test_delete_theme_removes_from_library(manager):
    """[TM-8] delete_theme() removes the entry from the theme library."""
    theme_id = _save_new_theme(manager)
    result = manager.delete_theme(theme_id=theme_id)
    assert result["ok"] is True
    assert theme_id not in manager.get_theme_library()["library"]


def test_delete_theme_clears_default_theme_id(manager):
    """[TM-8] Deleting the default theme resets default_theme_id to None."""
    result = manager.save_theme_as_new(
        vacuum_entity_id=_VAC, name="Default", set_as_default=True
    )
    theme_id = result["theme_id"]
    manager.delete_theme(theme_id=theme_id)
    assert manager.get_theme_library()["default_theme_id"] is None


def test_delete_theme_unknown_returns_not_ok(manager):
    """[TM-9] delete_theme() returns ok=False for unknown theme_id."""
    result = manager.delete_theme(theme_id="does_not_exist")
    assert result["ok"] is False
    assert result["reason"] == "theme_not_found"


def test_delete_core_theme_does_not_survive_restart(manager):
    """[TM-9b] RP-034/CRUD-3/INIT-3: deleting a bundled (source=='core') theme
    stays deleted across a restart — a second ThemeManager constructed over the
    same stored dict is that restart; the seeder must not re-add it."""
    from custom_components.eufy_vacuum.themes.manager import ThemeManager

    library = manager.get_theme_library()["library"]
    core_id = next(tid for tid, t in library.items() if t.get("source") == "core")

    result = manager.delete_theme(theme_id=core_id)
    assert result["ok"] is True
    assert core_id not in manager.get_theme_library()["library"]

    restarted = ThemeManager(manager.data)
    assert core_id not in restarted.get_theme_library()["library"]
    assert core_id in manager.data["theme"].get("deleted_core_ids", [])


def test_delete_manual_theme_does_not_tombstone(manager):
    """[TM-9c] the tombstone is core-only — deleting a user theme must not write
    a deleted_core_ids entry (nothing would ever consult it for a manual id, but
    a stray write would be dead state accumulating for no reason)."""
    theme_id = _save_new_theme(manager)
    manager.delete_theme(theme_id=theme_id)
    assert theme_id not in manager.data["theme"].get("deleted_core_ids", [])


# ---------------------------------------------------------------------------
# [TM-10] — [TM-12] set_active_theme
# ---------------------------------------------------------------------------

def test_set_active_theme_for_vacuum(manager):
    """[TM-10] set_active_theme() with vacuum_entity_id points vacuum at theme."""
    theme_id = _save_new_theme(manager)
    result = manager.set_active_theme(vacuum_entity_id=_VAC, theme_id=theme_id)
    assert result["ok"] is True
    assert result["active_theme_id"] == theme_id


def test_set_active_theme_global_default(manager):
    """[TM-11] set_active_theme(vacuum_entity_id=None) sets global default."""
    theme_id = _save_new_theme(manager)
    result = manager.set_active_theme(vacuum_entity_id=None, theme_id=theme_id)
    assert result["ok"] is True
    assert manager.get_theme_library()["default_theme_id"] == theme_id


def test_set_active_theme_unknown_returns_not_ok(manager):
    """[TM-12] set_active_theme() returns ok=False for unknown theme_id."""
    result = manager.set_active_theme(vacuum_entity_id=_VAC, theme_id="ghost")
    assert result["ok"] is False
    assert result["reason"] == "theme_not_found"


# ---------------------------------------------------------------------------
# [TM-13] — [TM-14] update_working_draft / revert_draft
# ---------------------------------------------------------------------------

def test_update_working_draft_patches_tokens(manager):
    """[TM-13] update_working_draft() merges tokens and sets draft_dirty=True."""
    result = manager.update_working_draft(
        vacuum_entity_id=_VAC, tokens={"primary": "#ff0000"}
    )
    assert result["ok"] is True
    assert result["draft_dirty"] is True


def test_update_working_draft_writes_into_data(manager):
    """[TM-13] update_working_draft() stores the value in the working_draft bucket."""
    manager.update_working_draft(vacuum_entity_id=_VAC, colors={"bg": "#ffffff"})
    draft = manager.data["theme"]["vacuums"][_VAC]["working_draft"]
    assert draft["colors"]["bg"] == "#ffffff"


def test_revert_draft_clears_dirty_and_tokens(manager):
    """[TM-14] revert_draft() resets working_draft to empty and clears draft_dirty."""
    manager.update_working_draft(vacuum_entity_id=_VAC, tokens={"primary": "#ff0000"})
    result = manager.revert_draft(vacuum_entity_id=_VAC)
    assert result["ok"] is True
    assert result["draft_dirty"] is False
    draft = manager.data["theme"]["vacuums"][_VAC]["working_draft"]
    assert draft["tokens"] == {}


# ---------------------------------------------------------------------------
# [TM-15] — [TM-16] export_theme
# ---------------------------------------------------------------------------

def test_export_theme_returns_json_safe_dict(manager):
    """[TM-15] export_theme() returns version, exported_at, and theme sub-dict."""
    theme_id = _save_new_theme(manager, name="Export Me")
    result = manager.export_theme(theme_id=theme_id)
    assert result["ok"] is True
    assert result["version"] == 1
    assert "exported_at" in result
    assert result["theme"]["name"] == "Export Me"
    assert result["theme"]["id"] == theme_id


def test_export_theme_unknown_returns_not_ok(manager):
    """[TM-16] export_theme() returns ok=False for unknown theme_id."""
    result = manager.export_theme(theme_id="missing_id")
    assert result["ok"] is False
    assert result["reason"] == "theme_not_found"


# ---------------------------------------------------------------------------
# [TM-17] — [TM-18] import_theme
# ---------------------------------------------------------------------------

def test_import_theme_adds_to_library(manager):
    """[TM-17] import_theme() adds a new entry to the theme library."""
    payload = {"theme": {"name": "Imported Theme", "tokens": {}, "colors": {}, "alpha": {}}}
    result = manager.import_theme(payload=payload)
    assert result["ok"] is True
    assert result["theme_id"] in manager.get_theme_library()["library"]


def test_import_theme_invalid_name_returns_not_ok(manager):
    """[TM-18] import_theme() returns ok=False when name is empty."""
    result = manager.import_theme(payload={"theme": {"name": ""}})
    assert result["ok"] is False
    assert result["reason"] == "missing_name"


def test_import_theme_invalid_tokens_type_returns_not_ok(manager):
    """[TM-18] import_theme() returns ok=False when tokens is not a dict."""
    result = manager.import_theme(
        payload={"theme": {"name": "Bad Tokens", "tokens": "not_a_dict"}}
    )
    assert result["ok"] is False
    assert result["reason"] == "invalid_tokens"


def test_import_theme_rejects_keys_outside_evcc_namespace(manager):
    """[TM-18b] RP-034/PORT-1: a key outside the --evcc-* namespace is dropped
    from the stored theme AND named in the response — the import still
    succeeds (ok=True) with whatever valid tokens it carried."""
    result = manager.import_theme(payload={"theme": {"name": "Mixed Import", "tokens": {
        "--evcc-card-background": "#101014",
        "--totally-not-a-real-token": "url(javascript:0)",
    }}})
    assert result["ok"] is True
    assert result["rejected"] == ["--totally-not-a-real-token"]
    stored = manager.get_theme_library()["library"][result["theme_id"]]["tokens"]
    assert stored == {"--evcc-card-background": "#101014"}


def test_import_theme_no_rejects_key_omitted(manager):
    """[TM-18c] a fully-clean import carries no `rejected` key at all — the
    card can gate its warning banner on presence, not an always-empty list."""
    result = manager.import_theme(payload={"theme": {"name": "Clean Import", "tokens": {
        "--evcc-card-background": "#101014",
    }}})
    assert result["ok"] is True
    assert "rejected" not in result


def test_import_theme_rejects_bad_keys_across_tokens_colors_alpha(manager):
    """[TM-18d] the namespace check applies to all three buckets, and rejects
    from every bucket are combined into one deduplicated response list."""
    result = manager.import_theme(payload={"theme": {"name": "Multi-bucket", "tokens": {
        "bad-token": "x",
    }, "colors": {
        "bad-color": "y",
    }, "alpha": {
        "bad-alpha": "0.5",
    }}})
    assert result["ok"] is True
    assert sorted(result["rejected"]) == ["bad-alpha", "bad-color", "bad-token"]


# ---------------------------------------------------------------------------
# [TM-19] source provenance — the Source facet driver
# ---------------------------------------------------------------------------

def test_save_theme_as_new_marks_source_manual(manager):
    """[TM-19] a user-saved theme carries source='manual'."""
    theme_id = _save_new_theme(manager, name="Mine")
    assert manager.get_theme_library()["library"][theme_id]["source"] == "manual"


def test_export_theme_carries_source(manager):
    """[TM-19] export_theme() includes the entry's source."""
    theme_id = _save_new_theme(manager, name="Exportable")
    result = manager.export_theme(theme_id=theme_id)
    assert result["theme"]["source"] == "manual"


def test_get_theme_library_summary_includes_source(manager):
    """[TM-19] the themes summary carries source (preloaded entries are core)."""
    summary = manager.get_theme_library()["themes"]
    core = [t for t in summary if t.get("source") == "core"]
    assert core, "expected at least one bundled (core) theme in the summary"


def test_import_theme_preserves_valid_source(manager):
    """[TM-19] an imported community theme keeps its provenance."""
    payload = {"theme": {"name": "From Community", "source": "community", "colors": {}}}
    result = manager.import_theme(payload=payload)
    entry = manager.get_theme_library()["library"][result["theme_id"]]
    assert entry["source"] == "community"


def test_import_theme_defaults_missing_source_to_manual(manager):
    """[TM-19] an import with no source is treated as user-added (manual)."""
    result = manager.import_theme(payload={"theme": {"name": "No Source", "colors": {}}})
    entry = manager.get_theme_library()["library"][result["theme_id"]]
    assert entry["source"] == "manual"


def test_import_theme_never_honors_core(manager):
    """[TM-19] `core` is reserved for seeded bundled themes — an imported copy of
    one is downgraded to manual, so the Source facet's `core` stays trustworthy."""
    payload = {"theme": {"name": "Fake Core", "source": "core", "colors": {}}}
    result = manager.import_theme(payload=payload)
    entry = manager.get_theme_library()["library"][result["theme_id"]]
    assert entry["source"] == "manual"


def test_overwrite_theme_preserves_source(manager):
    """[TM-19] overwriting rebuilds the entry but keeps the provenance (without
    the fix it would drop `source` entirely)."""
    theme_id = _save_new_theme(manager, name="Editable")  # source='manual', now active
    manager.overwrite_theme(vacuum_entity_id=_VAC, theme_id=theme_id)
    assert manager.get_theme_library()["library"][theme_id]["source"] == "manual"


def test_overwrite_theme_preserves_tags_and_author(manager):
    """[TM-20] overwriting an imported theme keeps its vibe tags + author credit
    (not just source) — editing must not strip the metadata import/export carry."""
    payload = {"theme": {"name": "Rich", "colors": {}, "tags": ["aurora", "cosmic"],
                         "author": "Ada", "author_url": "https://example.com", "source": "community"}}
    theme_id = manager.import_theme(payload=payload)["theme_id"]
    manager.set_active_theme(vacuum_entity_id=_VAC, theme_id=theme_id)
    manager.overwrite_theme(vacuum_entity_id=_VAC, theme_id=theme_id)
    entry = manager.get_theme_library()["library"][theme_id]
    assert entry["tags"] == ["aurora", "cosmic"]
    assert entry["author"] == "Ada"
    assert entry["author_url"] == "https://example.com"
    assert entry["source"] == "community"


# ---------------------------------------------------------------------------
# [TM-20] free-text vibe tags + attribution
# ---------------------------------------------------------------------------

def test_set_theme_tags_stores_cleaned(manager):
    """[TM-20] set_theme_tags cleans (trim/lower/dedupe) and stores vibe tags."""
    theme_id = _save_new_theme(manager, name="Taggable")
    result = manager.set_theme_tags(theme_id=theme_id, tags=["Aurora", " aurora ", "Cosmic", ""])
    assert result["ok"] is True
    assert manager.get_theme_library()["library"][theme_id]["tags"] == ["aurora", "cosmic"]


def test_set_theme_tags_empty_clears(manager):
    """[TM-20] an empty list clears the tags field."""
    theme_id = _save_new_theme(manager, name="Clearable")
    manager.set_theme_tags(theme_id=theme_id, tags=["aurora"])
    manager.set_theme_tags(theme_id=theme_id, tags=[])
    assert "tags" not in manager.get_theme_library()["library"][theme_id]


def test_set_theme_tags_unknown_returns_not_ok(manager):
    """[TM-20] set_theme_tags on an unknown theme returns ok=False."""
    result = manager.set_theme_tags(theme_id="missing_id", tags=["x"])
    assert result["ok"] is False
    assert result["reason"] == "theme_not_found"


def test_import_theme_preserves_tags_and_author(manager):
    """[TM-20] an upload's own vibe tags + author survive import."""
    payload = {"theme": {
        "name": "Rich Import", "colors": {},
        "tags": ["Aurora", "cosmic"], "author": "Ada L.", "author_url": "https://example.com",
    }}
    result = manager.import_theme(payload=payload)
    entry = manager.get_theme_library()["library"][result["theme_id"]]
    assert entry["tags"] == ["aurora", "cosmic"]
    assert entry["author"] == "Ada L."
    assert entry["author_url"] == "https://example.com"


def test_export_theme_carries_tags_and_author(manager):
    """[TM-20] export round-trips the vibe tags + author."""
    payload = {"theme": {"name": "Round Trip", "colors": {}, "tags": ["retro"], "author": "K"}}
    theme_id = manager.import_theme(payload=payload)["theme_id"]
    exported = manager.export_theme(theme_id=theme_id)["theme"]
    assert exported["tags"] == ["retro"]
    assert exported["author"] == "K"


def test_tm30_a_dropped_tag_is_reported(manager):
    """[TM-30] RED BEFORE THE FIX: the response was identical either way.

    Twenty submitted, sixteen is the cap. The response must carry what was APPLIED —
    not merely that something was — so a caller can diff it against what it sent
    without knowing the cleaning rules.
    """
    theme_id = _save_new_theme(manager, name="Overfull")
    submitted = [f"tag{n}" for n in range(20)]
    result = manager.set_theme_tags(theme_id=theme_id, tags=submitted)

    assert result["ok"] is True
    assert len(result["tags"]) == 16
    assert result["tags"] == submitted[:16]
    dropped = result["dropped_tags"]
    assert [d["tag"] for d in dropped] == submitted[16:]
    assert {d["reason"] for d in dropped} == {"limit_reached"}
    # and the store agrees with what the response claims
    assert manager.get_theme_library()["library"][theme_id]["tags"] == result["tags"]


def test_tm31_each_drop_reason_is_distinguishable(manager):
    """[TM-31] RED IF THE REASONS COLLAPSE TO ONE. "not saved" is not actionable;
    "too long" and "already in the list" ask the user for different things."""
    theme_id = _save_new_theme(manager, name="Messy")
    long_tag = "x" * 33
    result = manager.set_theme_tags(
        theme_id=theme_id, tags=["Aurora", " aurora ", long_tag, "   ", "cosmic"])

    assert result["tags"] == ["aurora", "cosmic"]
    by_reason = {d["reason"] for d in result["dropped_tags"]}
    assert by_reason == {"duplicate", "too_long", "empty"}
    # the offending value comes back with it, so the card can name it
    assert any(d["tag"] == long_tag for d in result["dropped_tags"])


def test_tm32_a_clean_submission_reports_no_drops(manager):
    """[TM-32] The key is ABSENT rather than an empty list, so `"dropped_tags" in
    result` is a reliable test. A field that is always present and usually empty gets
    read as noise and stops being checked."""
    theme_id = _save_new_theme(manager, name="Tidy")
    result = manager.set_theme_tags(theme_id=theme_id, tags=["aurora", "cosmic"])

    assert result["ok"] is True
    assert result["tags"] == ["aurora", "cosmic"]
    assert "dropped_tags" not in result
