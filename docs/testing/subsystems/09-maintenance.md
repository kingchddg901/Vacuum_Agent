# 09 — Maintenance — Subsystem Test Map

The maintenance subsystem tracks consumable wear (main brush, side brush, filter,
sensors, mop) against adapter-declared components: it reads remaining-life
sources, computes status tiers, builds the upkeep snapshot, resolves the
care-guide metadata per component, and resets counters. Covered by **52 tests in 1 file**.

Source: `custom_components/eufy_vacuum/maintenance/`
Architecture reference: [41 — Maintenance and the Dock](../../dev/41-maintenance-and-the-dock.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `manager.py` | 294 | 91% | `test_maintenance_manager.py` | integration | clean |

(The reset / set-interval *services* are in [17 — services](17-services.md) via
`test_services_maintenance_reset.py`; the remaining-life *sensors* are in
[18 — platforms](18-platforms.md).)

---

## What's tested

- **Upkeep snapshot** (`MNT`) — the replacement-item loop over adapter
  `maintenance_components`, status tiering (`good` / `warning` / `replace_soon` /
  `replace_now`) from a source entity's remaining-life + usage/total-life
  attributes, and `highest_priority_status`.
- **Care guide** (`MNT`) — `_get_upkeep_item_guide` enriches a library entry with
  source model/family info and the maintenance / replacement sub-dicts, picking
  the display sub-dict by `item_kind`; returns None when no guide exists.
- **Reset path** — counter reset given a source entity with usage hours.
- **Device totals + dock firmware** (`MNT`) — `get_upkeep_snapshot` surfaces the
  robovac_mqtt v1.11.0 lifetime sensors (`total_cleaning_area` / `_time` /
  `_count`) as a `device_totals` block and the `dock_firmware` string, covering
  the all-present, all-absent, and partial/placeholder paths.

---

## How it's tested

`MaintenanceManager(manager)` over the real `manager` fixture; a `_caps(...)`
helper monkeypatches `get_vacuum_capabilities` to inject `maintenance_sources`,
and `register_adapter_config(...)` supplies the `maintenance_components` and
`upkeep_catalog` the loops read.

---

## Known gaps

`manager.py` (91%) — most of the uncovered lines are still the same defensive
`(TypeError, ValueError)` coercion guards as before, just at shifted line
numbers after this campaign's growth (283→287 statements): the `_safe_int` /
`_safe_float` / `_hours_text` sentinel fallbacks (50-51, 60-61, 92-93), the
attribute-coercion `except` blocks for `usage_hours` / `total_life_hours` /
`remaining_hours` (401-410), the interval-override coercion fallback
(482-483), the `device_totals` reader's `_device_total` coercion guard
(586-587), and the `usage_hours` coercion `pass` inside
`get_maintenance_remaining` (758-759). The `_display_label`
normalize-to-empty guard (71) is similarly a trivial near-unreachable branch.
New this campaign: the localized-guide-translation overlay (255-262) — where
a translated guide's `steps`/`notes`/`clean_frequency`/`replace_frequency`
are spliced onto the English base field-by-field when present — has its
`if translated:` guard (254) covered but its entire body (255-262) never
executes under test: no test currently exercises a vacuum whose HA-instance
language has a translated guide for its model, so the splice itself is
untested, not just the "omits one field" edge case. All other lines here are
intentionally/incidentally uncovered defensive branches; none change
behavior.

`_get_replacement_reset_entity` (now at line 287) is covered: MNT-14c
exercises the live-state hit and MNT-14d the registry-only hit in
`test_maintenance_manager.py`. The older reset-entity tests that set
`entity_suffixes` to an absent value still additionally exercise the
`token_sets` fallback.

---

## `core/test_usage_accumulator.py` — the reset-detecting counter

12 test functions / 18 collected cases, added 2026-09-12. Covers `core/usage_accumulator.py`,
the pure fold that turns a device's reading into hours we own.

**Why it is pure and tested alone.** Doc 41 §1 states the rule the framework lives by — *the
device owns the state and we own a reference to it* — and the countdown half was never actually
built: `_consumed_hours` read a countdown as a POINT value (`default_interval_hours - state`),
so a device self-reset made the card read brand new while clamp 1 absorbed the difference.
Absorbing a reset is not counting it.

| id | what it holds |
| --- | --- |
| UAC-1 | the ordinary case — a decrease is hours. |
| UAC-2 | **a week of downtime books the whole drop in one reading.** The delta is against the last STORED value, not a live stream, so nothing is lost — and the cap must not mistake it for a glitch. |
| UAC-3 | a reset counts nothing **and** moves the baseline. |
| UAC-4 | **the freeze.** Skip the re-baseline and `baseline` stays at the old value forever, every later reading reads as another increase, and the counter never books another hour. "Ignore increases" is a plausible-sounding rule that silently dies without the re-baseline. |
| UAC-5 | the same branch from the other side — count the increase and the reset itself books as runtime. |
| UAC-6 / 6b | **`unavailable` / `unknown` touch nothing.** The failure most likely to happen first: a countdown goes unavailable on every HA restart. Coerced to 0 it books the whole countdown; treated as "no value" that writes a baseline it destroys the reference. |
| UAC-7 | the first reading establishes the baseline only — a fresh install must not book hours already on the part. |
| UAC-8 | an impossible delta is **rejected and reported**, never absorbed, and still re-baselines so the next reading recovers. |
| UAC-9 | the cap is **360 h — the longest device-declared part life**, not the longest declared interval (720 h, a user's reminder ceiling, which bounds nothing about runtime). |
| UAC-10 | **count-up is the same rule mirrored.** Eufy's `usage_hours` rises where Roborock's `time_left` falls; applied as written the spec would count nothing on Eufy. |
| UAC-11 | direction is inferred per **entity**, not per brand — keeping doc 41's "holds both without a brand check". A per-adapter declaration would be strictly weaker. |
| UAC-12 | **the one direction it drifts**, pinned as a decision: a reset inside an unobserved gap loses that gap (or books only the net). It fails LOW and SILENT, bounded by how long we can go unobserved. |

| UAC-13/14 | **the source teaches us its own direction** — no declaration, no metadata. Roborock publishes no `state_class` on any sensor, so this is the path its parts take. |
| UAC-15 | **a first movement that is a reset is OUTVOTED.** Locking on the first tick is right almost always and, when it is wrong, is wrong silently and permanently — it would book every later reset as runtime and ignore all real use. Majority self-corrects within two ordinary ticks. |
| UAC-16 | nothing is booked while the direction is unknown. Booking on a guess is worse than booking late: the guess is unbounded, the wait costs one movement. |
| UAC-17 | HA's `state_class` is a **head start where it exists** (`total`/`total_increasing` → up, `measurement` → down) and never a requirement — it covers two integrations of three. |

**The learning cost, as a number:** one movement per source, once. MNT-7c and MNT-8b both show
the tick explicitly rather than hiding it behind a fixture that declares `state_class`.
