# 13 — Onboarding — Subsystem Test Map

The onboarding subsystem tracks per-map setup completeness: whether rooms have
been discovered and whether every enabled room has a confirmed floor type. It
feeds the start-status `onboarding_required` gate and the onboarding sensor.
Covered by **6 tests in 1 file** (plus the onboarding sensor in
[18 — platforms](18-platforms.md)).

Source: `custom_components/eufy_vacuum/onboarding/`
Architecture reference: [docs/dev/18-onboarding-manager.md](../../dev/18-onboarding-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 73 | 98% | `test_onboarding_manager.py` | integration |

---

## What's tested

- **State computation** — `get_onboarding_state`: `rooms_discovered`,
  `floor_types_complete`, the `enabled_rooms_needing_floor_type` list, and the
  overall status (`complete` / `floor_type_needed` / `rooms_needed`).
- **Mutations** — `mark_rooms_discovered`, `confirm_floor_type`, `reset_onboarding`.
- **New-room check** — `check_for_new_rooms` against the vacuum entity's segment
  attribute count.

> **Gotcha:** `save_managed_rooms` auto-confirms floor types. To exercise the
> incomplete-onboarding path you must clear
> `data["onboarding"][vac][map]["floor_types_confirmed"]` after seeding — see
> the core start-status gate test.

---

## How it's tested

`OnboardingManager(data, hass)` over a plain `data: dict = {}` with a local
`MagicMock` `hass` fixture, with rooms seeded via a local `_seed_rooms(data,
rooms)` helper that writes `data["maps"][vac][map]["rooms"]` directly. (The
shared `manager`/`setup_map` harness exists and is used by other integration
tests, but not this one.)

---

## Known gaps

`manager.py` (98%) has one uncovered line, narrow:

- **Non-list segments guard** (`check_for_new_rooms`, line 188) — the
  `return False` when the source entity's segments attribute isn't a list.
  The no-state path (line 184) is tested; this is the malformed-attribute
  defensive guard. Defensive-by-design, intentionally uncovered.

`get_rooms_onboarding_summary` is statement-covered (`test_summary`, OB-4) but
not 100% branch-covered — the all-complete loop continuation (`211->205`) is
unexercised because the test seeds only an incomplete map.
