# 12 — Profiles — Subsystem Test Map

The profiles subsystem owns reusable per-room cleaning profiles (fan speed, water
level, mop mode, etc.): the user library, the protected built-in profiles,
applying a profile to a room, and saving/overwriting a profile from a room's
current settings. Covered by **65 tests across 3 files**.

Source: `custom_components/eufy_vacuum/profiles/`
Architecture reference: [docs/dev/16-profile-manager.md](../../dev/16-profile-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 392 | 96% | `test_profiles_manager.py` | integration |
| `room_profiles.py` | 178 | 95% | `test_profiles_room_profiles.py` (unit), `test_profile_catalog.py` (unit) | unit |

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
- **Adapter-sourced catalog seam** (unit, `test_profile_catalog.py`) —
  `resolve_profile_catalog` per-key merge of an adapter `room_profiles` block over
  the in-code defaults, catalog-driven resolution (`resolve_room_profile_for_room`
  honouring a catalog's floor-type water default, `default_profile` fallback, and a
  custom `builtins` entry), and `None`/empty block staying byte-identical to the
  in-code defaults (see [16 — profile manager §1.1](../../dev/16-profile-manager.md)).

---

## How it's tested

`ProfileManager` over the `manager` fixture for the library/apply paths; the pure
normalization + matching helpers are unit-tested in isolation.

---

## Known gaps

`manager.py` (95%) is diffuse — single-line defensive returns and not-found
guards scattered across the CRUD methods (the `_safe_int` empty/except path at
50/52/53, and `continue` skip-guards for non-dict entries at 623, 756, and the
restore-profile not-dict guards at 1014/1018/1025/1028/1032/1033); no contiguous
untested behavior block.

`room_profiles.py` (95%) is likewise defensive: the `TypedDict` ImportError
fallback shim (10–11), empty-name `continue` guards (208), the
`vacuum_mop_standard` alias fallback (342), the double-fallback when even
`default_profile` is missing (263–264), and a capability-gating branch (484). All
intentionally left uncovered.
