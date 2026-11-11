# 05 — Planning — Subsystem Test Map

The planning subsystem (`RunPlanManager`) is the authoritative rule-evaluation
point for a job start: it builds the effective start plan (queue + payload +
preflight), evaluates blocker/modifier rules and their fan-out, computes the
confirmation token for a reduced run, and produces the runtime path-block report
when a rule fires mid-job. Covered by **94 tests across 4 files**.

Source: `custom_components/eufy_vacuum/planning/`
Architecture reference: [18 — The Access Graph](../../dev/18-access-graph.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `run_plan.py` | 608 | 95% | `test_run_plan_start_plan.py`, `test_run_plan_manager.py`, `test_run_plan_helpers.py` (unit), `test_water_vocabulary_boundary.py` (unit) | int + unit | **bare x1** |

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
- **Canonical/provider vocabulary boundary** (`WV`, unit, added 2026-08-07) —
  `test_water_vocabulary_boundary.py` (15 tests). Core owns the canonical water
  KEY SPACE (`off/low/medium/high`) that the rate table is keyed on; it may not
  assume a provider's vocabulary equals it. Both shipped brands hide the
  difference — Roborock's declared values already ARE the canonical keys, and
  Eufy's `"Low"` reaches `"low"` through a generic case-folding rule — so
  neither exercises the declared-alias path, and it could regress unnoticed.
  These tests use a brand whose water words resemble nothing canonical
  (`SynthMist`, `SynthFlood`), so aliases are the only possible route, with a
  mutation control (WV-2) that withdraws them and requires the same values to
  stop resolving.

---

## How it's tested

`RunPlanManager(manager)` over the real `manager` fixture; `_seed(...)` lays down
managed rooms and merges per-room overrides, `_blocker(...)` / `_modifier(...)`
build rule dicts, and binary-sensor states drive rule matches.

---

## Known gaps

`run_plan.py` (93%) leaves two fan-out per-target guards (the `int()`-except on a
non-numeric target id and the not-selected `continue`), the module-level helper
except-paths (`_safe_int` / `_safe_float` `TypeError`/`ValueError` arms), the
`by_time` wash-cycle branch and other water-usage partial branches, and the
defensive early-returns / disabled-rule and non-dict-room skips inside
`get_runtime_path_block_report` (no-queue, no-remaining, structural-issue, and
unchanged-signature returns) — all defensive or low-value branch tails.

### Queuing room groups — `test_queued_room_groups.py` (issue #72, added 2026-10-20)

> *"I typically let it vacuum twice before mopping... if today I would like to execute
> this sequence for room A and room B, and tomorrow for room A and room C. Profile
> doesn't work well in this use case."*

N room groups in one run, each keeping its own per-room settings, with the set of rooms
changing day to day.

**This was HALF-BUILT, not missing, and that is what made it a fix rather than a
design.** `ProfileManager`'s `has_stops` already declared `len(room_group_steps) > 1` to
be a sequenced run; the card mirrored that rule, routed Start through the stepped path,
previewed *"Clean A → Clean B"* and shipped a chip that appends a second group. All
three gates that actually EXECUTE asked only "does this contain a charge_wait/wait/zone".
**A user could author exactly this issue, watch the card promise it, and watch the run
go flat with every group's settings discarded.**

The question is now asked once, by `step_types.py::plan_is_sequenced`, in all four
places. `plan_requires_stepped_execution` keeps its narrower meaning for callers that
genuinely want "does this contain a break" — `QRG-5` asserts both, because the shape
clause leaking into that vocabulary is the other way this drifts.

| id | what it holds |
|---|---|
| `QRG-1` | two groups with no break stay two phases |
| `QRG-2` | one group is still one atomic clean — the no-cost guard |
| `QRG-3` | **each group keeps its OWN settings**; ids alone would pass against the old behaviour |
| `QRG-4` | three groups stay three, in authored order |
| `QRG-5` | `has_stops` and the executing gates now agree — that disagreement WAS the bug |
| `QRG-6` | a single SURVIVING group is kept, not rebuilt |

**`QRG-6` exists because an ablation looked weak and wasn't.** Disabling the collapse
changed nothing for one group, which read as a soft test — the real answer was that the
collapse was doing something worse than nothing. It rebuilt the phase with
`managed_rooms=effective_rooms`, the GLOBAL view, discarding the per-group overlay the
builder had just merged and re-protected. That is #72's defect at N=1, and it is
reachable: one group plus a zone that resolves to nothing drops the zone and lands
exactly there, so a user whose saved zone went missing lost that group's settings too.

⚠ **`ZN-3`'s assertion changed with this.** A dropped zone used to fold the surrounding
groups into one atomic clean; two groups are a sequence whether or not a zone sits
between them, so it now removes the zone and nothing else. `ZN-3b` is the counter-arm.

**The collapse is the gate a partial patch would miss.** Opening only the two
stepped-path gates looks right, passes, and still runs flat.

