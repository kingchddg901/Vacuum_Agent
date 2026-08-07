# 12 — Profiles — Subsystem Test Map

The profiles subsystem owns reusable per-room cleaning profiles (fan speed, water
level, mop mode, etc.): the user library, the protected built-in profiles,
applying a profile to a room, and saving/overwriting a profile from a room's
current settings. Covered by **102 tests across 3 files**.

Source: `custom_components/eufy_vacuum/profiles/`
Architecture reference: [docs/dev/16-profile-manager.md](../../dev/16-profile-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `manager.py` | 521 | 96% | `test_profiles_manager.py` | integration | spec'd |
| `room_profiles.py` | 196 | 95% | `test_profiles_room_profiles.py` (unit), `test_profile_catalog.py` (unit) | unit | clean |

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

`manager.py` (96%, grown from 414 to 521 statements this campaign) is still
diffuse — single-line defensive returns and not-found guards scattered across
the CRUD methods (non-dict `continue` guards at 554, 741, 1061, 1404, 1447,
1524, 1562; a `wait_minutes` parse-except guard at 907-909; the legacy
trailing-break trim log branch at 980; misc single lines at 557, 1450);
line numbers have shifted with the file's growth but the shape is the
same — no contiguous untested behavior block.

`room_profiles.py` (95%, grown from 179 to 196 statements) is likewise
defensive: the `TypedDict` ImportError fallback shim (10–11), an empty-name
`continue` guard (264), the double-fallback when even `default_profile` is
missing (322–323), the `vacuum_mop_standard` alias fallback (401), and a
capability-gating branch (529). New this campaign: a `clean_passes = 1`
fallback when the adapter doesn't support passes (622), not previously
itemized. All intentionally left uncovered.
