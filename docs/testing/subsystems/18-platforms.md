# 18 — Platforms & Entities — Subsystem Test Map

The platform layer is the HA-facing entity surface: the `sensor/` package, the
`binary_sensor` / `button` / `number` / `switch` platforms, room entities, the
config flow, and the small shared helpers (entity helpers, frontend URL,
timestamp utils, models, map manager). Covered by **134 tests across 13 files**.

Source: `custom_components/eufy_vacuum/sensor/`, `binary_sensor.py`, `button.py`,
`number.py`, `switch.py`, `room_entities.py`, `config_flow.py`,
`entity_helpers.py`, `_frontend_url.py`, `timestamp_utils.py`, `models/`, `maps/`
Architecture reference: [docs/dev/02-ha-integration.md](../../dev/02-ha-integration.md), [docs/dev/17-map-manager.md](../../dev/17-map-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Mocking |
|---------------|------:|----:|------------|-------|
| `sensor/error.py` | 82 | 96% | `test_sensor_status.py` | **bare x11** |
| `sensor/lifecycle.py` | 91 | 91% | `test_sensor_status.py` | **bare x11** |
| `sensor/maintenance.py` | 55 | 95% | `test_sensor_status.py` | **bare x11** |
| `sensor/onboarding.py` | 39 | 96% | `test_sensor_entities.py` | clean |
| `sensor/profile.py` | 27 | 100% | `test_sensor_entities.py` | clean |
| `sensor/theme.py` | 39 | 95% | `test_sensor_entities.py` | clean |
| `sensor/dock_event.py` | 24 | 100% | `test_sensor_remaining.py` | clean |
| `sensor/room_history.py` | 19 | 100% | `test_sensor_remaining.py` | clean |
| `sensor/room_rule_status.py` | 19 | 100% | `test_sensor_remaining.py` | clean |
| `sensor/map_overlays.py` | 57 | 99% | `test_sensor_map_overlays.py`, `test_map_overlays_sensor.py` (unit) | clean |
| `button.py` | 139 | 89% | `test_button_entity.py` | **bare x1** |
| `number.py` | 129 | 98% | `test_number_entity.py` | clean |
| `switch.py` | 64 | 98% | `test_switch_entity.py` | clean |
| `binary_sensor.py` | 65 | 91% | `test_platform_files.py` | **bare x10** |
| `room_entities.py` | 85 | 98% | `test_platform_files.py` | **bare x10** |
| `config_flow.py` | 48 | 94% | `test_config_flow.py` | clean |
| `timestamp_utils.py` | 38 | 98% | `test_timestamp_utils.py` (unit) | clean |
| `models/models.py` | 121 | 98% | `test_models.py` (unit) | clean |
| `maps/map_manager.py` | 93 | 94% | `test_maps_map_manager.py` (unit) | clean |
| `entity_helpers.py` | 43 | 98% | `test_platform_files.py` | **bare x10** |
| `_frontend_url.py` | 18 | 89% | `test_platform_files.py` | **bare x10** |

---

## What's tested

- **Sensors** — `native_value` / attributes for status, lifecycle, remaining-life,
  onboarding, theme, profile, room-history, room-rule-status, dock-event sensors.
- **Map overlays sensor** — the per-vacuum diagnostic sensor whose state is the
  current room name (or `unavailable` / `available` when the map cache is
  unwarmed). Its attributes mirror the normalized `map_state_source` layers
  (per-room bbox + area, dock/robot anchors + heading, no-go / no-mop / walls /
  zones / obstacles) plus the resolved per-map overlay visibility; the verbose
  geometry layers are recorder-excluded. Reads `manager._map_state_source_cache`
  only (a cheap sync property).
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
What remains uncovered is now concentrated on `button.py` (89%, missing lines
100, 111-120, 164, 169, 283) rather than spread evenly. Line 100 is the
run-profile **rename-detection** condition (`if existing.profile_name !=
entity.profile_name:`) as before. Lines 111-120 are new this campaign and
are the more interesting gap: the profile-**rename swap**
(`_swap_renamed`) — when a reconciled button's `profile_name` changed, the
platform removes the stale entity object and adds a fresh one instead of
writing state onto it (the comment identifies this as the button platform's
missing counterpart to the sensor platform's SN-4 rename fix). Lines 164 and
283 are non-dict `library`/`profile` guards. These all call `async_remove()` /
`async_write_ha_state()` / need a reconciled entity registry on **registered**
entities, so exercising them needs a **full entity-platform registration**
harness (a registered entity on a real platform) rather than the recording
`async_add_entities` the current tests use; only white-box spies are otherwise
possible. `number.py` (98%, missing 258-259) has a small residual gap;
`switch.py` and `entity_helpers.py` now have every *statement* covered (0
missing lines) — the `_on_rooms_updated` add-new-entities path and the
floor-guidance map previously described here are exercised now — but each
still carries one partial branch pair (`switch.py` 83->85 and 86->81;
`entity_helpers.py` 162->167) that keeps their combined Cov column at 98% in
the table above, not 100%. Display-only, low severity.

**Defensive guards and `# pragma: no cover` branches (intentional).** The rest
is defensive and deliberately uncovered: the `hass is None` / wrong-vacuum /
wrong-map early returns in the tracker/event callbacks
(`binary_sensor.py` 43, 101, 104; `sensor/lifecycle.py` 125, 128, 153, 164,
166), the `# pragma: no cover` `except` blocks and fallback branches in the
top-level `__init__.py` (92%, grown from 193 to 317 statements — exercised
end-to-end by `test_init_setup`, not per-unit), and trivial leaf lines
(`config_flow.py` 144, 167; `_frontend_url.py` 47-48; `room_entities.py` 241;
`sensor/error.py` 67; `models/models.py` 11-12). Not worth covering.
