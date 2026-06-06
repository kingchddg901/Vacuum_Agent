"""Phase 6 integration tests — scoped (per-floor-type) theme import.

Scoped import REPLACES a floor type's namespace (every --evcc-floor-{type}-*
key across tokens/colors/alpha) on the vacuum's ACTIVE theme via clear-then-
apply, leaving every other type and non-floor key untouched. The card range-
clamps values and validates type names before sending, so this layer only does
deterministic namespace replacement.

Coverage targets
----------------
[TIS-1] Scoped import replaces a namespace (clear-then-apply): stale key gone,
        import keys present.
[TIS-2] Scoped import leaves OTHER floor types untouched.
[TIS-3] carpet-low scope does not touch carpet-high (whole-name prefix).
[TIS-4] Scoped import clears a matching working-draft override.
[TIS-5] Scoped import with no active theme -> ok=False.
[TIS-6] Scoped import with no vacuum_entity_id -> ok=False.
[TIS-7] Full import (scope absent) still adds a NEW library theme.
"""

from __future__ import annotations

_VAC = "vacuum.alfred"


def _active_theme_with(manager, *, tokens=None, colors=None, alpha=None, name="Base"):
    """Create a theme, bake the given floor keys into it, leave it active."""
    theme_id = manager.save_theme_as_new(vacuum_entity_id=_VAC, name=name)["theme_id"]
    manager.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens=tokens or {},
        colors=colors or {},
        alpha=alpha or {},
    )
    manager.overwrite_theme(vacuum_entity_id=_VAC, theme_id=theme_id)
    return theme_id


def _entry(manager, theme_id):
    return manager.get_theme_library()["library"][theme_id]


# ---------------------------------------------------------------------------
# [TIS-1] clear-then-apply
# ---------------------------------------------------------------------------

def test_scoped_import_replaces_namespace(manager):
    """[TIS-1] import keys applied; a stale key absent from the file is cleared."""
    theme_id = _active_theme_with(
        manager,
        tokens={
            "--evcc-floor-marble-vein-opacity": 0.9,
            "--evcc-floor-marble-vein-minor-opacity": 0.3,  # stale — NOT in the import
        },
        colors={"--evcc-floor-marble-accent": "#111111"},
    )

    result = manager.import_theme(
        payload={
            "scope": ["marble"],
            "theme": {
                "tokens": {"--evcc-floor-marble-vein-opacity": 0.5},
                "colors": {"--evcc-floor-marble-accent": "#D4AF37"},
            },
        },
        vacuum_entity_id=_VAC,
    )

    assert result["ok"] is True
    entry = _entry(manager, theme_id)
    assert entry["tokens"]["--evcc-floor-marble-vein-opacity"] == 0.5
    assert entry["colors"]["--evcc-floor-marble-accent"] == "#D4AF37"
    # clear-then-apply, not patch: the stale override is gone (CSS falls back to default)
    assert "--evcc-floor-marble-vein-minor-opacity" not in entry["tokens"]


# ---------------------------------------------------------------------------
# [TIS-2] other floor types untouched
# ---------------------------------------------------------------------------

def test_scoped_import_leaves_other_types_untouched(manager):
    """[TIS-2] a marble import does not disturb tile keys."""
    theme_id = _active_theme_with(
        manager,
        tokens={
            "--evcc-floor-marble-vein-opacity": 0.9,
            "--evcc-floor-tile-opacity-card": 0.7,
        },
    )
    manager.import_theme(
        payload={"scope": ["marble"], "theme": {"tokens": {"--evcc-floor-marble-vein-opacity": 0.5}}},
        vacuum_entity_id=_VAC,
    )
    entry = _entry(manager, theme_id)
    assert entry["tokens"]["--evcc-floor-tile-opacity-card"] == 0.7


# ---------------------------------------------------------------------------
# [TIS-3] whole-name prefix — carpet-low vs carpet-high
# ---------------------------------------------------------------------------

def test_scoped_import_carpet_low_does_not_touch_carpet_high(manager):
    """[TIS-3] carpet-low scope must not bucket carpet-high keys."""
    theme_id = _active_theme_with(
        manager,
        tokens={
            "--evcc-floor-carpet-low-opacity-card": 0.4,
            "--evcc-floor-carpet-high-opacity-card": 0.8,
        },
    )
    manager.import_theme(
        payload={
            "scope": ["carpet-low"],
            "theme": {"tokens": {"--evcc-floor-carpet-low-opacity-card": 0.6}},
        },
        vacuum_entity_id=_VAC,
    )
    entry = _entry(manager, theme_id)
    assert entry["tokens"]["--evcc-floor-carpet-low-opacity-card"] == 0.6
    assert entry["tokens"]["--evcc-floor-carpet-high-opacity-card"] == 0.8


# ---------------------------------------------------------------------------
# [TIS-4] clears matching working-draft override
# ---------------------------------------------------------------------------

def test_scoped_import_clears_draft_override(manager):
    """[TIS-4] a live draft override on the namespace is dropped so the entry renders."""
    theme_id = _active_theme_with(
        manager,
        tokens={"--evcc-floor-marble-vein-opacity": 0.9},
    )
    manager.update_working_draft(
        vacuum_entity_id=_VAC,
        tokens={"--evcc-floor-marble-vein-opacity": 0.2},  # live override
    )
    manager.import_theme(
        payload={"scope": ["marble"], "theme": {"tokens": {"--evcc-floor-marble-vein-opacity": 0.5}}},
        vacuum_entity_id=_VAC,
    )
    vac = manager.themes._get_vacuum_theme(_VAC)
    assert "--evcc-floor-marble-vein-opacity" not in vac["working_draft"]["tokens"]
    assert _entry(manager, theme_id)["tokens"]["--evcc-floor-marble-vein-opacity"] == 0.5


# ---------------------------------------------------------------------------
# [TIS-5] / [TIS-6] guard rails
# ---------------------------------------------------------------------------

def test_scoped_import_no_active_theme(manager):
    """[TIS-5] no active theme on the vacuum -> ok=False."""
    result = manager.import_theme(
        payload={"scope": ["marble"], "theme": {"tokens": {"--evcc-floor-marble-vein-opacity": 0.5}}},
        vacuum_entity_id=_VAC,
    )
    assert result["ok"] is False
    assert result["reason"] == "no_active_theme"


def test_scoped_import_missing_vacuum(manager):
    """[TIS-6] no vacuum_entity_id -> ok=False."""
    result = manager.import_theme(
        payload={"scope": ["marble"], "theme": {"tokens": {}}},
        vacuum_entity_id=None,
    )
    assert result["ok"] is False
    assert result["reason"] == "missing_vacuum"


# ---------------------------------------------------------------------------
# [TIS-7] full import still works (regression)
# ---------------------------------------------------------------------------

def test_full_import_still_adds_new_theme(manager):
    """[TIS-7] scope absent -> legacy full import adds a new library theme."""
    before = len(manager.get_theme_library()["library"])
    result = manager.import_theme(
        payload={"theme": {"name": "Imported Full", "tokens": {"--evcc-accent": "#fff"}}},
    )
    assert result["ok"] is True
    after = len(manager.get_theme_library()["library"])
    assert after == before + 1
