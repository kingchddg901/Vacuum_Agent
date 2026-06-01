# 12 — Profiles — Subsystem Test Map

The profiles subsystem owns reusable per-room cleaning profiles (fan speed, water
level, mop mode, etc.): the user library, the protected built-in profiles,
applying a profile to a room, and saving/overwriting a profile from a room's
current settings. Covered by **47 tests across 3 files**.

Source: `custom_components/eufy_vacuum/profiles/`
Architecture reference: [docs/dev/16-profile-manager.md](../../dev/16-profile-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 315 | 88% | `test_profiles_manager.py` | integration |
| `room_profiles.py` | 169 | 95% | `test_profiles_room_profiles.py` (unit) | unit |

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

`manager.py` (88%) is diffuse — single-line defensive returns and not-found
guards scattered across the CRUD methods; no contiguous untested behavior block.
