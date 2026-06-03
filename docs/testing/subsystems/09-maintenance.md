# 09 — Maintenance — Subsystem Test Map

The maintenance subsystem tracks consumable wear (main brush, side brush, filter,
sensors, mop) against adapter-declared components: it reads remaining-life
sources, computes status tiers, builds the upkeep snapshot, resolves the
care-guide metadata per component, and resets counters. Covered by **21 tests
across 2 files**.

Source: `custom_components/eufy_vacuum/maintenance/`
Architecture reference: [docs/dev/13-maintenance-manager.md](../../dev/13-maintenance-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `manager.py` | 233 | 92% | `test_maintenance_manager.py` | integration |

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

---

## How it's tested

`MaintenanceManager(manager)` over the real `manager` fixture; a `_caps(...)`
helper monkeypatches `get_vacuum_capabilities` to inject `maintenance_sources`,
and `register_adapter_config(...)` supplies the `maintenance_components` and
`upkeep_catalog` the loops read.

---

## Known gaps

`manager.py` (88%) leaves scattered `(TypeError, ValueError)` coercion guards in
the wear-math helpers and a few interval-clamp branches — defensive.
