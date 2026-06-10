# 05 — Planning — Subsystem Test Map

The planning subsystem (`RunPlanManager`) is the authoritative rule-evaluation
point for a job start: it builds the effective start plan (queue + payload +
preflight), evaluates blocker/modifier rules and their fan-out, computes the
confirmation token for a reduced run, and produces the runtime path-block report
when a rule fires mid-job. Covered by **53 tests across 3 files**.

Source: `custom_components/eufy_vacuum/planning/`
Architecture reference: [docs/dev/09-room-rules-system.md](../../dev/09-room-rules-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `run_plan.py` | 504 | 92% | `test_run_plan_start_plan.py`, `test_run_plan_manager.py`, `test_run_plan_helpers.py` (unit) | int + unit |

---

## What's tested

- **Start-plan gates** (`SP`) — `_build_effective_start_plan` across the
  state machine: ready blank graph, partial graph → `incomplete_access_graph`,
  rules without graph → `access_graph_required_for_rules`, single-dock without
  grants → `access_graph_required`, a matching direct blocker (→ blocked rooms +
  confirmation), a matching modifier (→ modified rooms), and access-dependency
  cascade (a blocked parent blocks its child).
- **Modifier fan-out** (`SP`) — a rule's `fan_out_room_ids` apply to a derived
  target, plus the per-target guard branches (non-numeric / unknown / self /
  not-selected / blocked targets dropped; no-entity / no-match / empty-changes
  early-continues).
- **Runtime path-block report** (`SP`) — `get_runtime_path_block_report`
  (the #11 regression guard): reachability propagation marks a room reachable via
  an accessible parent; remaining rooms are classified directly- vs
  indirectly-blocked; idle job → None.
- **Water-usage estimation + helpers** (unit) — `estimate_job_water_usage`,
  `_settings_profile_display`, water-rate/level math.

---

## How it's tested

`RunPlanManager(manager)` over the real `manager` fixture; `_seed(...)` lays down
managed rooms and merges per-room overrides, `_blocker(...)` / `_modifier(...)`
build rule dicts, and binary-sensor states drive rule matches.

---

## Known gaps

`run_plan.py` (91%) leaves two fan-out per-target guards (the `int()`-except on a
non-numeric target id and the not-selected `continue`), the module-level helper
except-paths (`_safe_int` / `_safe_float` `TypeError`/`ValueError` arms), the
`by_time` wash-cycle branch and other water-usage partial branches, and the
defensive early-returns / disabled-rule and non-dict-room skips inside
`get_runtime_path_block_report` (no-queue, no-remaining, structural-issue, and
unchanged-signature returns) — all defensive or low-value branch tails.
