# 09 — Maintenance — Subsystem Test Map

The maintenance subsystem tracks consumable wear (main brush, side brush, filter,
sensors, mop) against adapter-declared components: it reads remaining-life
sources, computes status tiers, builds the upkeep snapshot, resolves the
care-guide metadata per component, and resets counters. Covered by **39 tests in 1 file**.

Source: `custom_components/eufy_vacuum/maintenance/`
Architecture reference: [docs/dev/13-maintenance-manager.md](../../dev/13-maintenance-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 250 | 93% | `test_maintenance_manager.py` | integration |

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

`manager.py` (93%) — the uncovered lines are almost all defensive
`(TypeError, ValueError)` coercion guards: the `_safe_int` / `_safe_float`
/ `_hours_text` sentinel fallbacks (50-51, 60-61, 92-93), the three
attribute-coercion `except` blocks in `get_upkeep_snapshot` for
`usage_hours` / `total_life_hours` / `remaining_hours` (307-308, 311-312,
315-316), the interval-override coercion fallback (387-388), and the
`usage_hours` coercion `pass` in `get_maintenance_remaining` (600-601).
The `_display_label` normalize-to-empty guard (71) is similarly a trivial
near-unreachable branch. The `device_totals` reader's `_device_total`
`(TypeError, ValueError)` coercion guard in `get_upkeep_snapshot` (a non-numeric,
non-placeholder sensor value) is the same kind of branch. All intentionally uncovered.

`_get_replacement_reset_entity`'s `entity_suffixes` primary
resolution path (247-252 — the states-table hit and the registry
fallback return) is now covered: MNT-14c exercises the live-state hit and
MNT-14d the registry-only hit in `test_maintenance_manager.py`. The
older reset-entity tests that set `entity_suffixes` to an absent value
still additionally exercise the `token_sets` fallback.
