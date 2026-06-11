# 14 — Themes — Subsystem Test Map

The themes subsystem owns the dashboard-card theme library: preloaded built-in
themes, the user library (save-as-new / overwrite / rename / delete), the active
theme + working draft, import/export, and the update-callback fan-out that
refreshes theme-bound entities. Covered by **64 tests across 5 files**.

Source: `custom_components/eufy_vacuum/themes/`
Architecture reference: [docs/dev/20-theme-system.md](../../dev/20-theme-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 251 | 95% | `test_themes_manager.py`, `test_themes_manager_deep.py`, `test_themes_import_scoped.py` | integration |
| `services.py` | 103 | 100% | `test_themes_services.py` | integration |
| `preloaded.py` | 25 | 94% | `test_themes_preloaded.py` (unit) | unit |

---

## What's tested

- **Library CRUD** — save-as-new, overwrite, rename, delete. Preloaded built-ins
  are re-seeded on restart but are not delete-protected at the manager/service
  layer.
- **Active theme + draft** — set active, update working draft, revert draft.
- **Import / export** — round-trip of a theme payload (legacy full import that
  adds a new library theme), plus **scoped per-floor-type import**
  (`manager.py` `_import_scoped`) that clear-then-applies an
  `--evcc-floor-{type}-*` namespace onto the vacuum's active theme and clears the
  matching working-draft overrides.
- **Service layer** — the theme services raise `ServiceValidationError` on bad
  input (HA Silver action-exception contract).

---

## How it's tested

`ThemeManager` over the `manager` fixture; the `_deep` file pushes the
less-common branches (draft revert, import validation). Services are driven
through the registry with `manager_with_services`.

---

## Known gaps

`manager.py` (95%) — the remaining uncovered lines are defensive input-validation
guards on the two import paths, not behavior gaps. `import_theme` rejects a
non-dict payload (444) and a non-dict `theme` (448), and rejects non-dict
`colors`/`alpha` (468, 470 — the parallel `tokens` guard at 466 *is* covered).
`_import_scoped` returns `empty_scope` when every scope name strips blank (518)
and re-inits a bucket that storage left as a non-dict (541-542). One normalize-
loop guard skips a blank theme id (142). All are the same skip-the-malformed
class — deliberately measured, not pragma'd. The update-callback fan-out except
(`_notify_updated`, 59-68) is now *covered* by the raising-callback test
([TMD-3]).

`services.py` (100%) — fully covered; every handler's failure path and success
path, including the `handle_overwrite_theme` `async_save` + return tail, is
exercised.

`preloaded.py` (94%) — one line: the idempotent re-seed skip
(`ensure_preloaded_theme_library`, 536) that leaves an already-present built-in
untouched on re-entry.
