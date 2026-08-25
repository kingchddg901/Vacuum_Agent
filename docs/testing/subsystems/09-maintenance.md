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
