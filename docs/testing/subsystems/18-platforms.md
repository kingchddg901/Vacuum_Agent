# 18 — Platforms & Entities — Subsystem Test Map

The platform layer is the HA-facing entity surface: the `sensor/` package, the
`binary_sensor` / `button` / `number` / `switch` platforms, room entities, the
config flow, and the small shared helpers (entity helpers, frontend URL,
timestamp utils, models, map manager). Covered by **119 tests across 11 files**.

Source: `custom_components/eufy_vacuum/sensor/`, `binary_sensor.py`, `button.py`,
`number.py`, `switch.py`, `room_entities.py`, `config_flow.py`, `repairs.py`,
`entity_helpers.py`, `_frontend_url.py`, `timestamp_utils.py`, `models/`, `maps/`
Architecture reference: [docs/dev/02-ha-integration.md](../../dev/02-ha-integration.md), [docs/dev/17-map-manager.md](../../dev/17-map-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files |
|---------------|------:|----:|------------|
| `sensor/error.py` | 84 | 96% | `test_sensor_status.py` |
| `sensor/lifecycle.py` | 91 | 90% | `test_sensor_status.py` |
| `sensor/maintenance.py` | 55 | 93% | `test_sensor_status.py` |
| `sensor/onboarding.py` | 31 | 95% | `test_sensor_entities.py` |
| `sensor/profile.py` | 27 | 100% | `test_sensor_entities.py` |
| `sensor/theme.py` | 39 | 95% | `test_sensor_entities.py` |
| `sensor/dock_event.py` | 24 | 100% | `test_sensor_remaining.py` |
| `sensor/room_history.py` | 19 | 100% | `test_sensor_remaining.py` |
| `sensor/room_rule_status.py` | 19 | 100% | `test_sensor_remaining.py` |
| `button.py` | 134 | 88% | `test_button_entity.py` |
| `number.py` | 121 | 97% | `test_number_entity.py` |
| `switch.py` | 63 | 98% | `test_switch_entity.py` |
| `binary_sensor.py` | 67 | 92% | `test_platform_files.py` |
| `room_entities.py` | 74 | 98% | `test_platform_files.py` |
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

The remaining misses across the platform layer fall into two families.

**Callback-driven dynamic-entity sync (display-only, low severity).** The
`sensor/__init__.py` post-setup callbacks — the room-history / room-rule-status
**sync add-remove** paths (build desired set, drop stale registry entries, add
new entities), the per-vacuum **refresh** callbacks, the theme refresh, and the
hourly safety-net tick — are now exercised end-to-end by INIT-6/7/8 in
`tests/integration/test_init_setup.py` via the full-boot harness (adding a room
and firing the update callback registers new sensors; the rule-status + theme
refreshes push observable state; the hourly tick refreshes history sensors).
What remains uncovered is on the *other* platforms: `button.py` (88%, lines
95–101 / 107–108) leaves the twin run-profile **stale-removal** and
**existing-write** branches, and `number.py` (94%) / `switch.py` (92%) leave the
`_on_rooms_updated` add-new-entities path. These call `async_remove()` /
`async_write_ha_state()` on **registered** entities, so exercising them needs a
**full entity-platform registration** harness (a registered entity on a real
platform) rather than the recording `async_add_entities` the current tests use;
only white-box spies are otherwise possible. Display-only, low severity.

**Defensive guards and `# pragma: no cover` branches (intentional).** The rest
is defensive and deliberately uncovered: the `hass is None` / wrong-vacuum /
wrong-map early returns in the tracker/event callbacks
(`binary_sensor.py` 43/103/106, `sensor/lifecycle.py` 127/130/155/166/168),
the `# pragma: no cover` `except` blocks and fallback branches in the top-level
`__init__.py` (88% — exercised end-to-end by `test_init_setup`, not per-unit),
and trivial leaf lines (`entity_helpers.py` floor-guidance map, `config_flow.py`
119 options-flow no-vacuum branch, `models/models.py` 10–11, the `isinstance`
guards in `button.py` 152/157/247). Not worth covering.
