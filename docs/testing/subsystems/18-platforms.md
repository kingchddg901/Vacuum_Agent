# 18 — Platforms & Entities — Subsystem Test Map

The platform layer is the HA-facing entity surface: the `sensor/` package, the
`binary_sensor` / `button` / `number` / `switch` platforms, room entities, the
config flow, and the small shared helpers (entity helpers, frontend URL,
timestamp utils, models, map manager). Covered by **~90 tests across many files**.

Source: `custom_components/eufy_vacuum/sensor/`, `binary_sensor.py`, `button.py`,
`number.py`, `switch.py`, `room_entities.py`, `config_flow.py`, `repairs.py`,
`entity_helpers.py`, `_frontend_url.py`, `timestamp_utils.py`, `models/`, `maps/`
Architecture reference: [docs/dev/02-ha-integration.md](../../dev/02-ha-integration.md), [docs/dev/17-map-manager.md](../../dev/17-map-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files |
|---------------|------:|----:|------------|
| `sensor/` (10 modules) | 572 | 94% | `test_sensor_entities.py`, `test_sensor_status.py`, `test_sensor_remaining.py` |
| `button.py` | 134 | 88% | `test_button_entity.py` |
| `number.py` | 121 | 94% | `test_number_entity.py` |
| `switch.py` | 63 | 92% | `test_switch_entity.py` |
| `binary_sensor.py` | 67 | 92% | `test_platform_files.py` |
| `room_entities.py` | 75 | 95% | `test_platform_files.py` |
| `config_flow.py` | 38 | 94% | `test_config_flow.py` |
| `repairs.py` | 15 | 100% | `test_platform_files.py` |
| `timestamp_utils.py` | 37 | 98% | `test_timestamp_utils.py` (unit) |
| `models/models.py` | 131 | 98% | `test_models.py` (unit) |
| `maps/map_manager.py` | 41 | 100% | `test_maps_map_manager.py` (unit) |
| `entity_helpers.py` | 24 | 88% | `test_platform_files.py` |
| `_frontend_url.py` | 10 | 100% | `test_platform_files.py` |

---

## What's tested

- **Sensors** — `native_value` / attributes for status, lifecycle, remaining-life,
  onboarding, theme, profile, room-history, room-rule-status, dock-event sensors.
- **Button** — maintenance-reset + saved-run-profile buttons; `unique_id`,
  `name`, `available`, `async_press`, and the **dynamic run-profile button
  reconciliation** (setup wires the update callback; exposing a profile builds +
  adds a button).
- **Number / Switch** — maintenance-interval number + the toggle switches:
  value read/write and bounds.
- **Config flow** — the entry creation flow.
- **Helpers + data layer** (unit) — timestamp parsing, the dataclass models, the
  map-manager persistence, device-info builder.

---

## How it's tested

Entity classes are constructed directly against a MagicMock or the real `manager`
and asserted on their properties (`native_value`, `available`, etc.). The button
platform's `async_setup_entry` is driven with a recording `async_add_entities`.
Pure helpers (`timestamp_utils`, `models`, `map_manager`) are unit-tested.

---

## Known gaps

`sensor/__init__.py` (81%) and `button.py` (88%) leave diffuse per-entity
`native_value` branches and the button stale-removal / existing-write paths,
which need a **full entity-platform registration** harness (a registered entity
with a real platform) rather than a recording `async_add_entities`. Display-only,
low severity.
