# 12 — Profiles — Subsystem Test Map

The profiles subsystem owns reusable per-room cleaning profiles (fan speed, water
level, mop mode, etc.): the user library, the protected built-in profiles,
applying a profile to a room, and saving/overwriting a profile from a room's
current settings. Covered by **203 tests across 5 files**.

Source: `custom_components/eufy_vacuum/profiles/`
Architecture reference: [docs/dev/16-profile-manager.md](../../dev/20-room-profiles.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `manager.py` | 535 | 96% | `test_profiles_manager.py`, `test_run_profile_strict_order.py`, `test_run_profile_step_leak.py` | integration | spec'd |
| `room_profiles.py` | 221 | 95% | `test_profiles_room_profiles.py` (unit), `test_profile_catalog.py` (unit) | unit | clean |

(The room-profile *services* are in [17 — services](17-services.md) via
`test_services_room_profiles.py`.)

**Run-profile start plumbing** has two dedicated files, both pinning things that fail
*silently* rather than loudly — a start that succeeds while quietly doing the wrong thing:

- `test_run_profile_strict_order.py` — **issue #50.** `SO-1..SO-5`: a profile's saved
  `strict_order` reaches dispatch; a legacy record with no such key dispatches `False`
  (the migration guarantee — existing profiles keep today's behaviour untouched); an
  explicit argument overrides the saved flag in both directions; and the read path
  normalises a pre-key record rather than raising. Before this, a saved profile's room
  order was discarded on every run for a path-optimising brand, and the exposed profile
  button — which carries no service data — had no route to opt in at all.
- `test_run_profile_step_leak.py` — `LEAK-1..LEAK-5`: a refused start must not leak its
  stashed step sequence, or the *next* plain start on that map silently becomes a
  charge/wait run.

---

## What's tested

- **Library CRUD** — save / overwrite / rename / delete user room profiles, the
  protected built-in set, and the apply-to-room path.
- **Save-from-room** — building a profile from a room's current settings,
  including the overwrite-from-room variant.
- **Pure normalization** (unit) — `room_profiles.py` field coercion, protected
  names, and the profile-match resolution used to label a room's current config.
- **Adapter-sourced catalog seam** (unit, `test_profile_catalog.py`) —
  `resolve_profile_catalog` carrying exactly what an adapter declared, catalog-driven
  resolution (`resolve_room_profile_for_room` honouring a catalog's floor-type water
  default, `default_profile` fallback, and a declared `builtins` entry), and an
  undeclared block resolving EMPTY rather than to a brand's words. Every catalog in
  that file is SYNTHETIC on purpose: if a core test needed a real brand's words to
  pass, core would still own them. See
  [16 — profile manager §1.1](../../dev/20-room-profiles.md), and
  `tests/adapters/test_declaration_contract.py` for the three declaration states.

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
