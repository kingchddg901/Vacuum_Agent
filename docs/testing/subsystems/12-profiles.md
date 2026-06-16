# 12 — Profiles — Subsystem Test Map

The profiles subsystem owns reusable per-room cleaning profiles (fan speed, water
level, mop mode, etc.): the user library, the protected built-in profiles,
applying a profile to a room, and saving/overwriting a profile from a room's
current settings. Covered by **46 tests across 2 files**.

Source: `custom_components/eufy_vacuum/profiles/`
Architecture reference: [docs/dev/16-profile-manager.md](../../dev/16-profile-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 315 | 95% | `test_profiles_manager.py` | integration |
| `room_profiles.py` | 180 | 95% | `test_profiles_room_profiles.py` (unit) | unit |

(The room-profile *services* are in [17 — services](17-services.md) via
`test_services_room_profiles.py`.)

---

## What's tested

- **Library CRUD** — save / overwrite / rename / delete user room profiles, the
  protected built-in set, and the apply-to-room path.
- **Save-from-room** — building a profile from a room's current settings,
  including the overwrite-from-room variant.
- **Pure normalization** (unit) — `room_profiles.py` field coercion, protected
  names, and the profile-match resolution used to label a room's current config.

---

## How it's tested

`ProfileManager` over the `manager` fixture for the library/apply paths; the pure
normalization + matching helpers are unit-tested in isolation.

---

## Known gaps

`manager.py` (94%) is diffuse — single-line defensive returns and not-found
guards scattered across the CRUD methods (the `_safe_int` empty/except path at
50–53, and `reason: ...` early-returns / `continue` skip-guards for non-dict
entries at 403, 474, 623, 756, 1014–1033); no contiguous untested behavior block.

`room_profiles.py` (94%) is likewise defensive: the `TypedDict` ImportError
fallback shim (10–11), empty-name `continue` guards (208), legacy-value
migrations and aliases ("carpet"→`carpet_low_pile` at 234, `vacuum_mop_standard`
at 342), the double-fallback when even `default_profile` is missing (263–264),
and a capability-gating branch (484). All intentionally left uncovered.
