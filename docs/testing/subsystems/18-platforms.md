# 18 — Platforms & Entities — Subsystem Test Map

The platform layer is the HA-facing entity surface: the `sensor/` package, the
`binary_sensor` / `button` / `number` / `switch` platforms, room entities, the
config flow, and the small shared helpers (entity helpers, frontend URL,
timestamp utils, models, map manager). Covered by **159 tests across 13 files**.

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
| `button.py` | 143 | 96% | `test_button_entity.py` | **bare x1** |
| `number.py` | 133 | 96% | `test_number_entity.py` | clean |
| `switch.py` | 95 | 98% | `test_switch_entity.py` | clean |
| `binary_sensor.py` | 65 | 96% | `test_platform_files.py` | **bare x8** |
| `room_entities.py` | 97 | 98% | `test_platform_files.py` | **bare x8** |
| `config_flow.py` | 90 | 98% | `test_config_flow.py` | clean |
| `timestamp_utils.py` | 38 | 98% | `test_timestamp_utils.py` (unit) | clean |
| `models/models.py` | 124 | 98% | `test_models.py` (unit) | clean |
| `maps/map_manager.py` | 93 | 100% | `test_maps_map_manager.py` (unit) | clean |
| `entity_helpers.py` | 72 | 99% | `test_platform_files.py` | **bare x8** |
| `_frontend_url.py` | 18 | 100% | `test_platform_files.py` | **bare x8** |

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
  adds a button; RENAMING one swaps the entity object under the same
  `unique_id`, and the next notification writes state rather than swapping
  again). The **model gate** is also asserted at this platform's call site, not
  only in its own unit tests.
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

`map_manager.rebuild_map_bucket` treats its stored `rooms` as an **outside input**,
and three tests say why. The map it reads was written by whatever build last saved
it, and a rebuild is the thing a user triggers to *recover* from stored data that
has gone bad — so it is the one path that must not die on the data it exists to
repair. `MAP-5f` feeds it a `rooms` entry that is not a dict (without the
`isinstance` guard, building the slug index calls `.get` on a string and the
rebuild raises); `MAP-5g` feeds a slug-matched room whose `room_id` will not
convert, driving **both** exceptions the `except` names — `None` for `TypeError`
and `"16.0"`, the shape a payload that sent `16.0` leaves behind, for `ValueError`
— so narrowing the tuple to either one reddens its own parameter.

`MAP-5e` covers `preserve_existing_settings=False`. Its claim lives entirely in a
**comparison**: asserting on the `preserve=False` result alone cannot work, because
every value it would check is also what a legitimately fresh room gets, so a
rebuild that ignored the flag and carried everything would be caught by nothing.
The test runs one seed builder and one discovery builder **twice** — identical
input by construction, since `rebuild_map_bucket` mutates `data` and a shared
literal would let the first run's writes reach the second — and asserts the two
results disagree field by field. It compares counts, flags, lists, colour and
order rather than `clean_mode`: that axis resolves through the brand's default
profile, and pinning a word there would pin one brand's vocabulary into a core test.

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
`button.py`'s share of that residue is closed as of 2026-11-08 — see
the `button.py` section below, which also
corrects what this paragraph used to say about it. `number.py` (98%, missing
258-259) has a small residual gap.

### `button.py` — 88% → 95.58% (2026-11-08)

> ⚠ The paragraph above USED to describe this gap as needing "a **full
> entity-platform registration** harness (a registered entity on a real platform)
> rather than the recording `async_add_entities` the current tests use; only
> white-box spies are otherwise possible." **That was wrong, and it is the reason
> the gap survived two campaigns.** `BE-14`..`BE-16` close it on the existing
> `[BE-11]`/`[BE-13]` recording harness, with two `create_autospec` doubles per
> entity — the same thing `[BE-13]` was already doing one line away. The registry
> half is not a spy either: `BE-14` creates a real registry entry, gives it a real
> user name override, and asserts both survive the swap.
>
> Its line citations had also rotted (it cited 100, 111-120, 164, 169, 283) and its
> percentage was a point high. A wrong "this needs a bigger harness" is worse than
> a wrong line number, because the line number rots visibly and the claim does not.

**The real gap was one behaviour, and the code said so itself.** The comment on the
rename-swap branch read `⚠ NO TEST REACHES THIS BRANCH (ledger T4, open)` and named
the covered sensor twin, `[INIT-13]`
`test_room_rename_swaps_entity_keeping_unique_id`. So EP-5 / SN-4's fix for a
forgotten sibling — the sensor platform got the rename swap and the button platform
did not — was itself unguarded: **delete the branch and the suite stayed green**,
measured. That one behaviour was 12 of the 22 uncovered units.

| id | what it holds |
|---|---|
| `BE-14` | a renamed profile swaps the entity OBJECT under the same `unique_id`, and the registry entry plus any user name override survive |
| `BE-15` | the swapped-in object is ADOPTED, so a second notification writes state instead of swapping again |
| `BE-16` | a notification with no rename writes state on EVERY existing button |
| `BE-17` | the model gate's UNRESOLVED arm at this call site: no model code, so a guide-only component is dropped and a sensor-backed one survives |
| `BE-18` | the model gate's RESOLVED arm, which is the half that proves the regime TABLE is read: a SENSOR-BACKED component the regime omits is dropped |

**`BE-17` is a call-site reachability gap, not a logic gap**, and the distinction is
the finding. The gate function is heavily tested — `MGT-1`..`MGT-6` in
`tests/adapters/test_model_gate.py` pin `components_for_model` and
`model_has_component` directly, including the REGIME_UNRESOLVED ruling — but a grep
of `tests/` for either name outside that file returned **zero** hits, against four
production call sites (`button.py`, `number.py`, `sensor/__init__.py`,
`maintenance/manager.py`). Nothing proved any platform consults it. `BE-17` plus
`BE-18` close one of the four; the other three are still unproven at their call
sites.

> ⚠ **IT TOOK TWO TESTS, AND THE FIRST DRAFT SHIPPED WITH ONE.** `BE-17` alone was
> recorded here as closing this call site. It does not: it runs in
> REGIME_UNRESOLVED, where `_emitted` is **already** `None`, so replacing the whole
> `components_for_model(...)` call with `_emitted = None` is an IDENTITY rather than
> a mutation — measured, it reddened nothing, while the control (hardcoding a model
> code the regime KNOWS) did redden `BE-17`, which is what shows the probe could see
> the call and the null was real. `BE-17` pins `model_has_component`; `BE-18` pins
> the regime table being read at all. This is
> `feedback_retirement_isnt_done_until_uncited`'s central shape — **a claim whose
> subject has gone identically zero stops being able to fail** — and it was found by
> an adversarial audit of the commit that introduced it, not by the suite.

**Three of these tests needed a second input to stop being vacuous, and the pattern
is the same each time: the interesting row was LAST.**

- `BE-16` seeds TWO exposed profiles. With one, the matched row is the only row, and
  `continue` → `break` is invisible — measured: the single-profile version stays
  green under that mutation along with the whole file.
- `BE-17` declares the DROPPED component FIRST in its catalog. **Do not tidy that
  order.** With the dropped component last, ablating the gate's `continue` to `break`
  leaves the test green at its exact asserted set; declared first, the same mutation
  empties the set and the test goes red.
- `BE-15` exists ONLY because one notification cannot distinguish an adopted entity
  map from an un-adopted one. Deleting `entity_map[unique_id] = entity` leaves
  `BE-14` and all 15 pre-existing tests green; `BE-15` is the single test that sees
  it. Ledger note: line 135 is **covered by `BE-14`, pinned by `BE-15`**.

**The swallowing layer is why every assertion is a recorded call.**
`core/manager.py::_notify_run_profiles_updated` wraps each run-profile callback in a
blanket `except Exception` that logs and continues, so a raise inside the
reconciliation callback produces no test failure at all. Each assertion is therefore
a `create_autospec` call record or the `async_add_entities` capture list, never an
escaping exception — and every named red input was confirmed red THROUGH that layer.
The stubs are not convenience: an unstubbed `async_write_ha_state` on an entity
never added to a platform raises, and the raise is swallowed, so the test would
observe nothing rather than fail.

**Eight units stay, all three clusters classified, so 95.58% is the honest ceiling.**

- `102->105` is **UNREACHABLE**. `_on_run_profiles_updated` is a plain `def`, so no
  `await` is possible anywhere in it; `stale_ids` is filtered from
  `list(entity_map.keys())`, dict keys are distinct, and every stored value is a
  freshly constructed entity — so `entity_map.pop(unique_id, None)` cannot miss. The
  one synchronous re-entrancy vector was checked: the integration has exactly one
  `EVENT_ENTITY_REGISTRY_UPDATED` listener, it returns at its first guard when the
  action is not `update`, and no file under `listeners/` can reach the notifier. If
  the arm is ever made reachable (deriving `stale_ids` from the registry instead
  would do it), its observable must be the registry removal or the log, **never an
  exception**, because of the swallow above.
- `106->100` is **SUBSUMED**, and the swallower is Home Assistant itself rather than
  an `except`. `er.EntityRegistry.async_remove` opens with `if entity_id not in
  self.entities: return`, carrying its own comment that removing a non-existent
  entity is *allowed* because "there will be races during cleanup" — before the
  pop, the deleted-entry write, the event fire and the save. Measured:
  `async_remove(None)` raises nothing, and replacing the guard with an unconditional
  call left the FULL suite green. The early return is present at the `hacs.json`
  floor (2025.6.0) too, not only in the image's version, so the tolerance holds
  across the supported range. **This is the identical classification `switch.py`'s
  stale-sweep guard already carries below** — same guard, same reason, found twice.
- The three **non-dict guards** are **UNREACHABLE** — `library` in
  `_build_run_profile_buttons_for_map` and in
  `EufyVacuumSavedRunProfileButton._profile`, plus `profile` in the former's
  loop. (Named by symbol, not line: they were `188`/`193`/`307` when this
  section was written and became `197`/`202`/`316` the same day, when a comment
  above them was corrected.) The sole producer,
  `profiles/manager.py::get_saved_run_profiles`, builds `"library"` as a dict
  COMPREHENSION already guarded by `isinstance(profile, dict)`, and each surviving
  value is `_enrich_saved_run_profile`, whose only return is a `{**profile, ...}`
  literal. Fifty garbage shapes driven through the real producer came back with
  `library` a dict every time. They are the shadow of a filter that already ran.

Two honesty caveats on that last group, because the walk turned up limits the
classification does not cover:

1. The store is filtered at the MAP level (`_get_saved_run_profile_store` returns
   `{}` for a non-dict), **not above it**. `core/storage.py::async_load` does not
   normalise `run_profiles` at all, so a corrupt store with a non-dict at
   `data["run_profiles"]` or `["run_profiles"][vac]` raises `AttributeError` on
   `.setdefault` one layer BELOW these guards. The conclusion is unaffected — it
   raises before `library` is read — but that raise belongs to
   `profiles/manager.py`, not here.
2. These units ARE coverable by substituting the producer: the repo ships
   `make_manager_mock(run_profiles=...)` and seven button tests already use it. Note
   the trap if anyone tries — that factory coerces its argument to `{"library":
   run_profiles or {}}`, so `[]`, `""`, `0` and `None` are all turned into `{}` and
   never reach the guard; only truthy garbage bites. By this repo's recorded
   standard (see `EufyVacuumOptionsFlow._resolution_gaps` further down) such a test
   asserts the author's reading of the contract rather than the contract, so it is
   left unwritten — stated as a choice rather than by omission.

**`BE-10` is a RETIRED id, not a free one** — removed in `7164c076` with
`_slugify_profile_name`. Do not fill the gap.

### `switch.py` — 84% → 98.37% (2026-11-08), and the entry this corrects

> ⚠ This section said `switch.py` "now has every *statement* covered (0 missing
> lines)" and named one partial branch pair, `83->85 and 86->81`. It had **fourteen
> missing lines** and a different pair of arms. The whole gap was one thing, and the
> count being wrong is what hid it: `EufyVacuumCleanOrderOverrideSwitch` was named
> NOWHERE in the suite and its creation gate never fired either way, so the class and
> both arms that build it were dead to the tests.

That matters more than the percentage, because this switch is the consent surface for
an action its own docstring flags twice: pressing **Apply edits a persistent,
map-level setting in the user's vendor app**, and toggling off must not silently clear
it — "that would destroy a sequence the USER set in their app". `SWO-*` in
`test_switch_entity.py` (the room switch owns `SW-*`; check both before minting an id):

| id | what it holds |
|---|---|
| `SWO-1` | the switch exists only where the adapter+model declares the WRITE half — `can_write` is MODEL-gated, so a Qrevo/B01 must gain no entity rather than one that does nothing |
| `SWO-2` | a manager with no `clean_order` grows no switch, **and does not take every room switch down with it** |
| `SWO-3` | the card finds it by `role` without its entity_id |
| `SWO-4` / `SWO-4b` | `is_on` reads the manager both ways, and fails CLOSED when the subsystem disappears under a live entity |
| `SWO-5` | toggling stores intent and reaches **no device** |
| `SWO-6` | the stale sweep removes every stale switch, not just the first |

**`SWO-3` asserts an ambiguity, not just an attribute.** The entity_id is not
guaranteed: with `_attr_has_entity_name` plus a `translation_key`, HA composes the id
from the device and entity names, and the name is unresolvable when the platform adds
the entity — observed live 2026-08-24 as a bare `switch.ivy`, and an entity_id is
sticky. So the card scans states. `vacuum_entity_id` alone cannot identify this switch
because every per-room switch carries it too, so the test proves that directly:
filtering the real platform's output by that attribute yields more than one entity,
filtering by `role` yields exactly one. Name-matching is not an alternative — the name
is translated, so a Chinese install reads `覆盖清扫顺序`.

**`SWO-5` is the safety claim.** `set_override_enabled` must be called with the right
vacuum and flag, **and no device-facing call may be recorded at all**. The stub carries
`async_apply`, `async_clear` and `write` so such a call is recorded and nameable rather
than raising an AttributeError somebody has to read a traceback to understand. The
ablation is the plausible tidy-up — making toggle-off symmetrical with Apply — and it
reddens `SWO-5` alone.

**Two arms stay, both classified, so 98.37% is the honest ceiling here.** The
`if stale is not None:` arm is UNREACHABLE: the `uid` comes from
`list(entity_map.items())` two statements earlier in the same synchronous callback, so
the pop cannot miss. The `if entity_id:` arm is **SUBSUMED** —
`er.EntityRegistry.async_remove` opens with `if entity_id not in self.entities:
return`, carrying its own comment that removing a non-existent entity is *allowed*
because "there will be races during cleanup"; measured, `async_remove(None)` raises
nothing and leaves the registry size unchanged. That one was found the hard way:
ablating the guard reddened nothing, which sent me to read HA's source rather than
trust the test's claimed red input.

**The swallowing layer is why `SWO-6` asserts a log.**
`core/manager.py::_notify_rooms_updated` wraps each room-update callback in a blanket
`except` that logs "Room update callback failed" and continues, so anything raising in
there produces no test failure by itself — two drafts of `SWO-6` passed while the
callback died on every run, on two different unwired attributes.

**Defensive guards and `# pragma: no cover` branches (intentional).** The rest
is defensive and deliberately uncovered: the wrong-map / wrong-vacuum early
returns in `sensor/lifecycle.py` (125, 128, 153, 164, 166), the
`# pragma: no cover` `except` blocks and fallback branches in the top-level
`__init__.py` (92%, grown from 193 to 317 statements — exercised end-to-end by
`test_init_setup`, not per-unit), and trivial leaf lines (`room_entities.py`
241; `sensor/error.py` 67; `models/models.py` 11-12).

**Three of the lines this paragraph used to dismiss are now tested, and the
dismissal was wrong about them.** The two early returns in
`binary_sensor.py::async_setup_entry` and
`binary_sensor.py::ActiveRunHasErrorBinarySensor._on_tracker_update`, and the
`except OSError` in `_frontend_url.py::cards_module_url`, were all listed here as
"defensive … not worth covering".
Each turned out to carry a real failure, and each is now pinned by a test with a
named red input:

- **`async_setup_entry`** (`manager is None or tracker is None`) — `BIN-3`.
  A compound guard, so it is driven **per half** with a both-present control:
  with only the runtime removed, the `or tracker is None` shoulder stays unproven
  and an entity gets built holding `None` as its tracker. Ablating just that half
  reddens `BIN-3` alone.
- **`_on_tracker_update`** (the wrong-vacuum early return) — `BIN-4`. One
  `ErrorTracker` serves every vacuum and broadcasts to all listeners, so without
  this the entity writes state on another robot's error while `is_on` still reads
  its own latch — a state change with no cause. The test's stub **records**; it
  must not raise, because `call_soon_threadsafe` sits inside
  `try: … except Exception: pass` and a raising stub is swallowed, passing the
  test inverted.
- **`cards_module_url`** (`except OSError: return None`) — `FU-3`, and the
  reason it is not a leaf: this URL is registered as a **global** frontend module,
  so advertising a missing bundle 404s on every HA page, not just inside the panel.
  `panel_js_url` degrades to `?v=0` on the same failure and must; the opposite
  answers are why `FU-1` and `FU-3` are separate tests. `FU-2` covers the live
  shape and imports `_CARDS_BASE_URL` rather than spelling it out — that string is
  also what `__init__.async_setup` registers, and a literal here would be a second
  copy that keeps passing through a rename.

⚠ **`_on_tracker_update`'s `if hass is None: return` is SUBSUMED**, and its red
set is declared empty in the test file rather than left looking like a gap. The
guard sits directly above `hass.loop.call_soon_threadsafe(...)`, which is itself
inside `try: … except Exception: pass` — so with the guard ablated, `None.loop`
raises into that `except` and the method returns silently either way. Measured
over 3 inputs (`hass` never set, `hass` set to `None`, `hass` with a recording
loop): identical answers, identical schedule counts, nothing escaping. Written
down because the obvious next move, "add a test for that guard", cannot succeed.

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
