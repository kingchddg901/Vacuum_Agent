# 13 — Onboarding — Subsystem Test Map

The onboarding subsystem tracks per-map setup completeness: whether rooms have
been discovered and whether every enabled room has a confirmed floor type. It
feeds the start-status `onboarding_required` gate and the onboarding sensor.
Covered by **5 tests in 1 file** (plus the onboarding sensor in
[18 — platforms](18-platforms.md)).

Source: `custom_components/eufy_vacuum/onboarding/`
Architecture reference: [docs/dev/18-onboarding-manager.md](../../dev/18-onboarding-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 73 | 95% | `test_onboarding_manager.py` | integration |

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

`OnboardingManager(data, hass)` over the `manager` fixture's data tree, with
managed rooms seeded via `setup_map(...)`.

---

## Known gaps

`manager.py` (95%) leaves two summary/aggregation branches in
`get_rooms_onboarding_summary` — low value.
