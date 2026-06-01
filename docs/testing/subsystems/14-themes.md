# 14 — Themes — Subsystem Test Map

The themes subsystem owns the dashboard-card theme library: preloaded built-in
themes, the user library (save-as-new / overwrite / rename / delete), the active
theme + working draft, import/export, and the update-callback fan-out that
refreshes theme-bound entities. Covered by **55 tests across 4 files**.

Source: `custom_components/eufy_vacuum/themes/`
Architecture reference: [docs/dev/20-theme-system.md](../../dev/20-theme-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 207 | 96% | `test_themes_manager.py`, `test_themes_manager_deep.py` | integration |
| `services.py` | 103 | 98% | `test_themes_services.py` | integration |
| `preloaded.py` | 25 | 94% | `test_themes_preloaded.py` (unit) | unit |

---

## What's tested

- **Library CRUD** — save-as-new, overwrite, rename, delete; the preloaded
  built-ins are protected.
- **Active theme + draft** — set active, update working draft, revert draft.
- **Import / export** — round-trip of a theme payload.
- **Service layer** — the theme services raise `ServiceValidationError` on bad
  input (HA Silver action-exception contract).

---

## How it's tested

`ThemeManager` over the `manager` fixture; the `_deep` file pushes the
less-common branches (draft revert, import validation). Services are driven
through the registry with `manager_with_services`.

---

## Known gaps

`manager.py` (96%) leaves the update-callback fan-out except (the
skip-one-continue resilience class — deliberately measured, not pragma'd) and a
couple of draft-edge branches. `preloaded.py` (94%) leaves one built-in lookup
fallback.
