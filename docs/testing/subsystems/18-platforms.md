# 18 — Platforms & Entities — Subsystem Test Map

The platform layer is the HA-facing entity surface: the `sensor/` package, the
`binary_sensor` / `button` / `number` / `switch` platforms, room entities, the
config flow, and the small shared helpers (entity helpers, frontend URL,
timestamp utils, models, map manager). Covered by **142 tests across 13 files**.

Source: `custom_components/eufy_vacuum/sensor/`, `binary_sensor.py`, `button.py`,
`number.py`, `switch.py`, `room_entities.py`, `config_flow.py`,
`entity_helpers.py`, `_frontend_url.py`, `timestamp_utils.py`, `models/`, `maps/`
Architecture reference: [docs/dev/02-ha-integration.md](../../dev/02-ha-integration.md), [45 — The Shared Layer](../../dev/45-the-shared-layer.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Mocking |
|---------------|------:|----:|------------|-------|
| `sensor/error.py` | 82 | 96% | `test_sensor_status.py` | **bare x11** |
| `sensor/lifecycle.py` | 91 | 92% | `test_sensor_status.py` | **bare x11** |
| `sensor/maintenance.py` | 55 | 95% | `test_sensor_status.py` | **bare x11** |
| `sensor/onboarding.py` | 39 | 96% | `test_sensor_entities.py` | clean |
| `sensor/profile.py` | 30 | 100% | `test_sensor_entities.py` | clean |
| `sensor/theme.py` | 39 | 95% | `test_sensor_entities.py` | clean |
| `sensor/dock_event.py` | 24 | 100% | `test_sensor_remaining.py` | clean |
| `sensor/room_history.py` | 19 | 100% | `test_sensor_remaining.py` | clean |
| `sensor/room_rule_status.py` | 19 | 100% | `test_sensor_remaining.py` | clean |
| `sensor/map_overlays.py` | 57 | 99% | `test_sensor_map_overlays.py`, `test_map_overlays_sensor.py` (unit) | clean |
| `button.py` | 143 | 88% | `test_button_entity.py` | **bare x1** |
| `number.py` | 133 | 96% | `test_number_entity.py` | clean |
| `switch.py` | 95 | 84% | `test_switch_entity.py` | clean |
| `binary_sensor.py` | 65 | 91% | `test_platform_files.py` | **bare x8** |
| `room_entities.py` | 95 | 98% | `test_platform_files.py` | **bare x8** |
| `config_flow.py` | 90 | 98% | `test_config_flow.py` | clean |
| `timestamp_utils.py` | 38 | 98% | `test_timestamp_utils.py` (unit) | clean |
| `models/models.py` | 124 | 98% | `test_models.py` (unit) | clean |
| `maps/map_manager.py` | 93 | 94% | `test_maps_map_manager.py` (unit) | clean |
| `entity_helpers.py` | 72 | 99% | `test_platform_files.py` | **bare x8** |
| `_frontend_url.py` | 18 | 89% | `test_platform_files.py` | **bare x8** |

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
- **Config flow** (`CF-*`, `OF-*`) — the entry creation flow, and the options
  screen, which carries more than its name suggests. Two halves had no tests until
  2026-11-07 and they are the two that matter most to a user in trouble:
  - **The deferred install** (`OF-7`). Setup accepts a *blank* vacuum on purpose —
    [44 § 1](../../dev/44-onboarding-and-first-run.md) explains why, since the
    vacuum belongs to another integration that may not have set up yet — and this
    screen is where the deferral is resolved. `tests/conftest.py::mock_entry_no_vacuum`
    had existed for that install all along and only `test_init_setup.py` ever used
    it, so the recovery path itself was never opened. The arm it exercises is not
    cosmetic: give the blank entry's picker a `default=""` and voluptuous validates
    the default, so the recovery form becomes **unsubmittable** for exactly the user
    it exists for.
  - **The entity-override pickers** (`OF-8`..`OF-13`, live:ENT-7). One picker per
    role that failed to resolve, driven by `entity_resolution_reasons` and
    `entity_augmentation["ambiguous"]` from the stored capabilities snapshot
    (`config_flow.py#CNAYBZY3`). Tested against the **real** producer — the snapshot
    accessor is documented as reading `data["capabilities"]` as-is, so the tests
    seed that store rather than stubbing the method, and they import the real
    `REASON_*` constants. That last point is load-bearing: the gap predicate only
    compares against `resolved`, so an *invented* reason word still produces a gap
    and the test would pass by luck while being blind to a producer rename.
  `OF-10` is the one to read first if you touch this screen. It pins MERGE-NOT-REPLACE
  by pre-seeding an override for a role the submitted form does **not** carry; with
  an empty store a merge and a replace are byte-identical, so the obvious version of
  that test cannot bite. `OF-13` exists for the same class of reason — it is the
  positive control proving the debug record `OF-12` asserts the *absence* of is
  visible at all.
- **Helpers + data layer** (unit) — timestamp parsing, the dataclass models, the
  map-manager persistence, device-info builder.
- **HA-core compatibility** (`DCE-*`, unit, `test_device_config_entry_ids.py`) —
  `entity_helpers.device_config_entry_ids`, the one question whose answer moved
  between `DeviceEntry.config_entries` and `DeviceEntry.config_entry_id` in HA
  2026.8 ([37 §1a](../../dev/37-the-entity-surface.md), ISSUE #69). The installed
  core can only ever present ONE of the two shapes, so `DCE-1`–`DCE-4` pin the
  branches against hand-built doubles and `DCE-5` is the single case built from
  the real class. The doubles RECORD rather than raise: one caller
  (`dreame_coordinator`) wraps its body in a blanket `except Exception`, where a
  raising stub is swallowed and proves nothing.

---

## How it's tested

Entity classes are constructed directly against a MagicMock or the real `manager`
and asserted on their properties (`native_value`, `available`, etc.). The button
platform's `async_setup_entry` is driven with a recording `async_add_entities`.
Pure helpers (`timestamp_utils`, `models`, `map_manager`) are unit-tested.

---

## `../unit/test_orphan_active_job_sweep.py` — the sweep that reaches past a deleted map

8 tests, added 2026-08-15, all against the pure helper
`entity_helpers.orphaned_active_job_unique_ids()`.

The room-entity sync described under **Known gaps** below is scoped PER MAP: it
walks the rooms of each map that exists and drops what that map no longer wants.
Nothing iterates a map that is **gone**, so a deleted map's per-map active-job
sensor stayed in the registry forever, permanently `unavailable` — a guard that is
complete inside its window and blind one step past it. Found with two orphans on
the maintainer's box (maps `6` and `99`, of five active-job entities on one
vacuum) and independently reported against the 2.1.0 beta on issue #49
(*"2nd is 'no longer reporting' — so not sure where/how that's appeared"*).

**Most of this file is about what must SURVIVE**, because the sweep deletes
registry entries and the naive version of it has already done damage here:
RP-009/RF-04 records a prefix scan in setup/delete that was PROVEN to
registry-delete every entity of a *sibling* vacuum whose entity_id was the scanned
prefix plus a suffix (DR-SETUP-1).

| id | holds |
|---|---|
| `OAJ-1` | an orphan of a deleted map IS selected — the point of the sweep |
| `OAJ-2` | **DR-SETUP-1**: `vacuum.alfred` never selects `vacuum.alfred_2`'s entities |
| `OAJ-3` | a vacuum literally named `<x>_active_job` does not have its ids swallowed by `<x>`'s prefix |
| `OAJ-4` | room switches, orders and per-vacuum sensors are out of scope entirely |
| `OAJ-5` | non-numeric map ids survive — Ivy's real map is `Main floor` |
| `OAJ-6` | a healthy install loses nothing |
| `OAJ-7` | an UNMANAGED vacuum's orphan is left alone — that is teardown's job, and this sweep cannot tell "removed" from "temporarily absent" |
| `OAJ-8` | the measured live-registry input, pinned: exactly 2 of 161 selected |

`OAJ-3` earned its place by failing on first run. The guard tested the remainder
for `_active_job_`, but the prefix has already consumed that underscore — the
remainder is `active_job_5`, so the check matched nothing and the guard silently
did not fire. Review did not catch it; the adversarial case did.

The deletion set is the **complement of a forward-built set** (`built_active_job_map_ids`,
the pairs this run actually constructed), never a parse of a registry id — the rule
`make_room_unique_id` states: ownership is answered by re-building ids from stored
facts, never by string dissection.

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
(`_frontend_url.py` 47-48; `room_entities.py` 241;
`sensor/error.py` 67; `models/models.py` 11-12). Not worth covering.

`config_flow.py` used to be listed above as two "trivial leaf lines" at 144 and
167. Both numbers had rotted, and so had the claim — the file is at 98% and its
one uncovered statement is named, not trivial: the `return ()` under
`if not isinstance(caps, dict)` in `EufyVacuumOptionsFlow._resolution_gaps`. It is
one stage re-validating the stage before it. `get_vacuum_capabilities_snapshot`
ends in `return dict(...)`, so it cannot hand back a non-dict; reaching that arm
would mean faking the producer to disagree with its own signature, which asserts
the test author's reading of the contract rather than the contract. The
`manager is None` arm beside it *is* reachable and is pinned by `OF-12`. The
classification is recorded at the site, which is the half that does not rot.
