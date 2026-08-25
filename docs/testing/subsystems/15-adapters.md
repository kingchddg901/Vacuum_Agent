# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema.
Two concrete adapters now live behind this boundary — **Eufy**
(`adapters/eufy/`) and **Roborock** (`adapters/roborock/`) — each with its own
focused suite, plus `adapters/brands.py` (which registrar runs for a given
vacuum) and the brand-agnostic conformance harness that runs every contract
test once per shipped brand. Covered by **166 framework tests across 10 files**
(`test_adapters.py`, `test_adapter_contract.py` — parametrized over both
brands — and `test_brand_selection.py`), plus **212 Eufy-adapter tests** and
**37 Roborock-adapter tests**.

A third adapter directory, `adapters/dreame/`, holds **data only and is deliberately
not wired** — it has no `BRAND_REGISTRARS` row, so the conformance harness above does
not reach it and none of those counts include it. Its 19 tests live in
`tests/adapters/dreame/` and are documented below; they exist precisely because nothing
else in the tree can fail on that directory.

<!-- The three bold counts above are HAND-MAINTAINED. update_test_docs.py's
single-header model can't compute the framework/Eufy/Roborock split, so it WARNs
and skips this doc's headline (the WARN is expected, not a bug). Update them by
hand on adapter test changes — collect-only case counts:
  framework  = tests/integration/test_adapters.py + tests/adapters/test_adapter_contract.py + tests/adapters/test_brand_selection.py
  Eufy       = tests/adapters/eufy/
  Roborock   = tests/adapters/roborock/
tests/adapters/dreame/ is NOT part of this split and must not be added to it — Dreame
is unwired data, and folding it into a "Roborock-adapter tests"-style count would read
as a third shipped brand. -->

Source: `custom_components/eufy_vacuum/adapters/`
Architecture reference: [22 — The Adapter Contract](../../dev/22-adapter-contract.md)

### `test_entity_resolve.py` — when a DERIVED entity id does not match the install

Adapters build companion entity ids from the vacuum's object_id
(`build_entity_id` → `sensor.{object_id}{suffix}`). That assumes one device per vacuum,
and two shipping cases break it: **Eufy's dock is a separate device**, so its entities are
named for that device (declared `sensor.alfred_total_cleaning_area`, actual
`sensor.dining_room_alfred_total_cleaning_area` — four dock-owned roles unresolved on live
hardware), and **a renamed device or entity** breaks every derived id at once.

Both failed SILENTLY, and a declared-but-absent entity reads as "this brand does not report
that" — the capability leak this project keeps removing. HA 2026.8 removed `battery_level`
from the vacuum entity, deleting the fallback that used to hide a missed battery sensor, so
the derived id is now load-bearing alone (issue #49).

`adapters/entity_resolve.py` rescues an id that FAILS to resolve by searching the vacuum's
own config entry for a domain + suffix match. Nine tests, and most pin what it REFUSES to
do, because the refusals are what make it safe to run on every install:

| id | what it holds |
|---|---|
| `ER-1` | **a working id is never touched** — the property that makes this unable to break a healthy install, asserted even when a same-suffix sibling exists |
| `ER-2` | the live Eufy dock case is rescued, and the remap is REPORTED rather than silently applied |
| `ER-3` | two candidates it cannot disambiguate → leave the declared id; a wrong remap aims the framework at another device and is worse than the absence |
| `ER-4` | ambiguity broken only by the vacuum's own object_id — what makes `<area>_<vacuum>_<suffix>` resolvable |
| `ER-5` | domain must match; a `select.*_active_map` is never served for a declared `sensor.*_active_map` |
| `ER-6` | no config entry → no-op. Config-entry scoping IS the safety boundary, so without it we search nothing |
| `ER-7` | **the documented LIMIT** (issue #46 shape): registered-but-stateless is not a naming problem, so it resolves to nothing and reports no repair |
| `ER-8` | a raising registry degrades to the declared ids — adapter config assembly is never breakable by this |
| `ER-9` | an id not derived from this vacuum has no suffix to match on, so nothing is guessed |

### `test_adapter_isolation.py` — the boundary, not the declarations

`test_adapter_contract.py` asserts what a brand must DECLARE. Nothing asserted
what a brand may TOUCH, so `test_adapter_isolation.py` (5 tests, added
2026-08-07) fences the dependency direction: a brand package translates VA's
meaning into one provider's vocabulary, and that substitutability is only real if
it cannot reach inward.

| id | what it holds |
|---|---|
| `ISO-1` | no brand package imports outside the declared adapter SDK |
| `ISO-2` | the known-leak allowlist is SHRINK-ONLY (same discipline as `mock_allowlist.json`) |
| `ISO-3` | no dynamic import (`importlib` / `__import__` / `sys.modules`) escapes ISO-1's static read |
| `ISO-4` | no runtime reach into a passed-in object's privates — the reach an import graph cannot see |
| `ISO-5` | the detector is exercised against a MANUFACTURED leak (positive + negative), so it cannot silently stop working |

**The SDK is two entries, both adjudicated from measurement:**
`core.capabilities` (BOTH brands call `detect_capabilities` — a facility every
adapter needs is API that happens to live in `core/`) and
`mapping.segment_primitives` (brand-neutral geometry — `rdp`, `polygon_area`,
`mask_iou`; any brand shipping a map IMAGE needs it, and Roborock supplies
segments directly so imports none of it).

**The ledger is now EMPTY.** It held one entry — `profiles.room_profiles` in
`eufy/adapter.py`, because the framework's in-code profile catalog *was* Eufy's.
That import was cut on 2026-08-07: Eufy's vocabulary moved to
`adapters/eufy/room_profiles.py`, core kept only the KEY space, and the framework
fallback was deleted rather than relocated. As predicted, it was a STORED-DATA
change and not a refactor — those values were already written onto existing rooms,
so a one-shot repair ships with it (`rooms/vocabulary_migration.py`).

ISO-5 changed shape with it. It used to assert the real leak was still detected,
and instructed whoever fixed it to delete the ledger entry and ISO-5 together.
Deleting the self-test would have left the detector unexercised — the exact failure
it exists to prevent — so it now manufactures its own leaky and clean modules in a
tmp dir. The instrument stays proven with the ledger empty, which is the state it
should stay in.

### `tests/test_vocabulary_invariant.py` — the standing invariant

**Core owns the KEY space. It does not own any brand's WORDS.** Enforced (14 tests,
added 2026-08-07) by taking two signals together, because either alone is useless:

1. **Syntactic** — the literal is bound to a provider-owned field (`fan_speed`,
   `water_level`, `clean_intensity`): assigned to it, used as its `.get()` default,
   compared against it, or passed as it.
2. **Lexical** — the literal is a value an adapter actually DECLARES, and is not in
   the explicit `CORE_OWNED` set.

Lexical alone reports every `max`, `off` and `low` in the repo — `wash_frequency_bounds["max"]`
is a structural key, `confidence == "low"` is a confidence level, `state == "off"` is an
HA entity state. A gate that screams at those gets ignored. Syntactic alone cannot tell a
canonical key from a brand's word. `VI-3` pins both classes with a positive and a
negative row each, so the detector stays proven while `VI-1` sits green.

`CORE_OWNED` is the load-bearing declaration: the written statement of what the framework
owns (the canonical water estimator keys `off/low/medium/high`, the canonical
`clean_mode` and `path_type` values, and `""` for "nobody said"). Growing it to silence
a finding is how the gate dies.

**Case-sensitive on purpose.** Folding case would merge Eufy's `"Off"` with the canonical
`"off"`, so `"Off"` would be swallowed by `CORE_OWNED` and the five real leaks in
`apply_capability_gate` and `_protected_room_config` would be invisible. `"Off"` vs
`"off"` IS the bug. The accepted blind spot is RETIRED values, which no adapter declares —
that is the store migration's job.

It found seven leaks on its first run, after the manual sweep was thought complete:
`.get(field, "Max"/"Off"/"Quick")` defaults in `overwrite_room_profile_from_room`,
`_snapshot_room_for_run_profile`, and the learning ingest path (whose default was
`"standard"` — a Eufy word Eufy itself had retired). The ledger is empty.

**A second gate was measured and rejected.** "Every test-registered adapter must declare
a catalog" sounds like the natural sibling, but 208 registrations across 51 test files
declare none and the suite is green — so those tests provably never resolve a room, and
the rule is not required. Shipping it would have meant a 208-row allowlist or 51 files of
churn. What actually covers the hazard is the runtime failure: resolution raises
`UndeclaredProfileCatalogError` naming the missing declaration, so a test that reaches it
cannot get a quietly wrong answer.

### `tests/adapters/eufy/test_intensity_wire_mapping.py` — three chips, three densities

VA declares three cleaning intensities. The device has three. They were not reaching
each other (5 tests, added 2026-08-08).

robovac_mqtt resolves the payload string through `CLEAN_EXTENT_MAP`, where
`"narrow"` and `"deep"` are the SAME value — `deep` is a legacy alias:

| payload word | CleanExtent | Eufy app |
|---|---|---|
| `quick` / `fast` | QUICK (2) | Low (widest spacing) |
| `normal` / `standard` | NORMAL (0) | Medium |
| `narrow` / `deep` | NARROW (1) | High (densest) |

Sending VA's own names unmapped collapsed `Narrow` and `Deep` onto NARROW and left
NORMAL unreachable — three chips in the card, two pass densities on the floor, and
the middle one impossible to select. The fix is a `dispatch.room_fields` value_map
(`{"Narrow": "normal", "Deep": "narrow"}`), so VA's names are unchanged and no stored
room moves.

**Verified against hardware**, not inferred: the Eufy app was set to each intensity
and `select.<vac>_cleaning_intensity` read back, cross-checked against the protobuf
enum (`clean_param_pb2`: NORMAL=0, NARROW=1, QUICK=2). Note the enum is an ARBITRARY
ENUM, not an ordinal — 0 is the middle setting — so nothing may interpolate on it.
That is also why `CIW-3` pins the declared option ORDER: fastest→slowest exists only
in the declaration and cannot be recovered from the device.

`CIW-1b` is the mutation control — with the value_map removed, two of the three
collide — because `CIW-1` would otherwise pass if the map were a silent no-op. The
card carries the matching half in `_profileIntensityToEditorIntensity`; both halves
must agree or the editor shows a density the wire does not send.

### `test_declaration_contract.py` — the declaration, in all three of its states

`test_adapter_isolation.py` fences what a brand may TOUCH. This one (12 tests,
added 2026-08-07) pins what happens when a brand DECLARES — or fails to.

| id | state | what it holds |
|---|---|---|
| `DC-1` | declared + populated | every shipped brand's real config resolves ITS words |
| `DC-1b` | — | Eufy and Roborock actually DIFFER, the premise every relational test rests on |
| `DC-2` | not declared | resolution RAISES, naming the missing declaration |
| `DC-2b` | not declared | negative control: the catalog is empty, not another brand's |
| `DC-2c` | not declared | registration rejects it, so the failure lands on the porter |
| `DC-3` | declared empty | a declared-empty key is carried, not treated as absent |
| `DC-3b` | partially declared | undeclared keys resolve EMPTY; the block is the gate, not each key |
| `DC-3c` | wholly empty block | rejected — a brand with no vocabulary can resolve nothing |
| `DC-4` | — | the same validator that rejects the bad ACCEPTS every shipped brand |
| `DC-5` | — | end to end: the REGISTERED config is what resolution actually reads |

### `dreame/test_dreame_upkeep_guides.py` — the only gate on an UNWIRED adapter

19 tests, added 2026-08-25. Every other suite on this page reaches an adapter through
its `BRAND_REGISTRARS` row. The Dreame adapter has no such row — deliberately, since
that row *is* the release — so none of them touch it, and until this file landed a
Dreame family could be emptied, two families silently collapsed into one, or the
release switch thrown, with the suite staying green throughout.

| id | what it holds |
|---|---|
| `DUG-1` | there is NO `BRAND_REGISTRARS` row for Dreame — the release switch, still off |
| `DUG-2` | the four families exist and every component in them has a non-empty step |
| `DUG-3` | `x60_pro_ultra_complete` is `x60_ultra` **plus exactly** `baseboard_brush` |
| `DUG-4` | the seven measured X50-vs-X60 divergences still diverge |
| `DUG-5` | absent hardware gets no guide — no heating module or baseboard brush on the X50 |

`DUG-4` is a regression guard for a defect this data already shipped once: a shared
`_BASE` was factored out of several families because their component NAMES lined up,
which put X60 prose on five other platforms. Presence of a part and sameness of its
PROCEDURE are different claims, and only the second one was ever checked. `DUG-3`
encodes the opposite case — two families that genuinely DO share a body, because their
manuals were diffed first and came out 48 of 49 sentences identical.

All 14 mutations were ablated and all 14 went red. `DUG-1` was ablated separately, both
by adding a Dreame row and by emptying the registrar table entirely, so it cannot pass
vacuously on a table that happens to be empty.

Provenance is checked outside the suite by `scripts/verify_dreame_guide_provenance.py`,
which cannot be a gate here because the manuals are vendor copyright and stay out of
the repo.

### `../unit/test_adapter_config_parity.py` — the schema is a FLOOR, not the contract

3 tests, added 2026-08-15. `test_declaration_contract.py` above pins what happens
when a brand declares or fails to. This one pins something one level up: that
`ADAPTER_CONFIG_SCHEMA` **agrees with the other two authorities on the same config**,
because it is not the only one.

| id | holds |
|---|---|
| `ACP-1` | a key `registry._validate_adapter` rejects the ABSENCE of must not read `required: False` in the schema |
| `ACP-2` | a config field documented in a doc-22 field table must exist in the schema |
| `ACP-3` | the `SCHEMA_ABSENT_BY_DESIGN` allowlist does not rot in either direction |

Both directions were live defects, found on 2026-08-15 by a doc generator that
trusted the schema as the whole truth:

- **`room_profiles`** was `required: False` in the schema while `_validate_room_profiles`
  rejected its absence outright (`DC-2c` above is that rejection). Only the CONFIG path
  was bitten — `validate_adapter_config()`, behind the `save_adapter_config` service,
  honoured the flag and SAVED, then registration refused the stored config. The failure
  landed at registration instead of at save, which is the exact outcome
  `registry._validate_adapter`'s own docstring says it exists to prevent. Code adapters
  never noticed: they bypass the schema walk.
- **`low_clean_water_margin_ml`** was read at `planning/run_plan.py::estimate_job_water_usage` and documented
  in doc 22 with a worked example, while absent from `water_model_configs.entry_fields`.
  `entry_fields` IS enforced, unknown-key rejection included — so a porter following the
  doc wrote that key and got "key(s) not declared in the schema" on save.

**What it deliberately does NOT check**, and why the limit is in the file rather than
in someone's memory: "every key the code reads is declared" was *measured* before it was
designed — a scan of `.get("literal")` on receivers named `config`/`cfg`/`model_config`
finds 141 distinct keys, 61 of them undeclared, and nearly all 61 are room configs,
estimator internals or map-source sub-dicts rather than adapter config. A gate needing a
61-entry allowlist hides real findings instead of surfacing them. Doc 22's field tables
are the tractable proxy, and they caught the real one.

Sibling: `tests/unit/test_service_declaration_parity.py` does the same job for the
service surface.

---

State 2 is the one a normal suite never reaches, and it is why this file exists.
Before the fallback was removed it was indistinguishable from state 1 — an adapter
declaring nothing silently received Eufy's catalog. DC-5 closes the original
defect specifically: four call sites in `profiles/manager.py` resolved rooms
without ever consulting the registry, and the fallback covered for them.

**Why four checks and not one.** A `^from`-anchored grep reported the Roborock
adapter as reaching nothing; it reaches `core.capabilities` through a DEFERRED
import inside a function, deferred to dodge an import cycle. Hence AST over every
node in every file. And an import graph cannot see a runtime reach at all, hence
ISO-4. Both ISO-1 and ISO-4 were mutation-verified when added — a fresh
non-SDK import and a planted `hass._private_thing` each turn their own check red.

### `../unit/test_clean_order.py` — the shape filter that makes a log-scraped read trustworthy

18 tests, added 2026-08-20. Roborock exposes a per-map cleaning SEQUENCE, declared by
the adapter under `device_clean_order`. Reading it is the awkward part:
`vacuum.send_command` is `SupportsResponse.NONE`, so the reply never returns through
the service call — it is captured off a DEBUG log line that does **not say which
command it answers**. Everything therefore rests on `is_clean_order` telling a real
reply apart from routine poll traffic. A wrong filter reports confident nonsense,
which is the worst failure available here, because it looks like a reading.

The inputs are REAL decoded results captured from Ivy on 2026-08-19 — every distinct
shape observed across 53 replies — not invented ones.

| id | what it holds |
|---|---|
| `CO-1` | each of the ten real decoded shapes classifies correctly |
| `CO-2` | ABLATION: `[0]` arrives every ~15s poll tick and a naive "flat list of ints" filter accepts it; the known-room-id check is what rejects it. The test also asserts the ABLATED form still passes, so the ablation cannot quietly stop meaning anything |
| `CO-3` | `isinstance(True, int)` is True in Python, so `[True]` must not read as room id 1 |
| `CO-4` | one unknown id invalidates the reading whole — a dropped room would silently reorder the rest |
| `CO-5` | an unparseable payload yields `None` (→ `unavailable`), never an exception on a path a live run can touch |
| `CO-6` | with no known room ids the manager declines to read at all, rather than accept a list it cannot check |
| `CO-7` | an unread vacuum must not present as "no order saved": `[]` is a legitimate ORDER value, so the STATUS field is what carries "we have not looked yet" |

**`CO-2` is the load-bearing one.** `[0]` arrives roughly every fifteen seconds, so a
filter weakened to a type check would report it as a clean order continuously.

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `registry.py` | 226 | 92% | `test_adapters.py` | integration | clean |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration | clean |
| `config_schema.py` | 64 | 94% | `test_adapters.py` | integration | clean |
| `brands.py` | 45 | 100% | `test_brand_selection.py` | integration | clean |
| `entity_resolve.py` | 193 | 92% | `tests/unit/test_entity_resolve.py` + `tests/adapters/test_entity_resolve.py` | unit + adapter | clean |
| `eufy/segmentor.py` | 872 | 92% | `tests/adapters/eufy/` | adapter | - |
| `eufy/adapter.py` | 61 | 85% | `tests/adapters/eufy/` | adapter | - |
| `eufy/entities.py` | 29 | 100% | `test_buttons_entities.py` + `test_suffix_vocabulary.py` | adapter | clean |
| `eufy/lifecycle.py` | 21 | 100% | `test_lifecycle.py` | adapter | clean |
| `eufy/constants.py` | 15 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/model_catalog.py` | 12 | 100% | `test_model_catalog.py` | adapter | clean |
| `eufy/vocabulary.py` | 42 | 100% | `test_error_source.py` + `tests/adapters/eufy/` | adapter | clean |
| `eufy/const.py` | 9 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/buttons.py` | 4 | 100% | `test_buttons_entities.py` | adapter | clean |
| `eufy/upkeep_catalog.py` | 3 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/water_config.py` | 3 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/maintenance_components.py` | 1 | 100% | `test_maintenance_config.py` | adapter | clean |
| `eufy/eufy_upkeep_guides.py` | 1 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/upkeep_guides_i18n/*.py` (17 languages) | 19 | 100% | `test_upkeep_guides_i18n.py` | adapter |
| `roborock/adapter.py` | 50 | 96% | `roborock/test_adapter.py` | adapter | - |
| `roborock/model_catalog.py` | 7 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/vocabulary.py` | 19 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/entities.py` | 25 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/const.py` | 7 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/upkeep_catalog.py` | 7 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/roborock_upkeep_guides.py` | 8 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/maintenance_components.py` | 2 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/upkeep_guides_i18n/*.py` (17 languages) | 121 | 100% | `roborock/test_adapter.py` | adapter |

`eufy/discovery.py` no longer exists as a separate module — model detection now
lives in `eufy/adapter.py` (`_registry_model_code`, which reads the device
registry) and `eufy/model_catalog.py` (`detect_model_family`); there is no
`test_discovery.py` file to reference for it anymore.

The Eufy adapter also pins two pluggable **engine seams** that live under
`learning/` (the adapter *declares* the engine; the engine itself is
brand-agnostic — see [06 — learning](06-learning.md)):

| Engine seam (under `learning/`) | Test file | Layer |
|---------------------------------|-----------|-------|
| `room_attribution_engines.py` (`EufyAnchorWindingAttributor`) | `test_room_attribution.py` | adapter |
| `job_segmenter_engines.py` (`EufyCounterSegmenter`) | `test_job_segmenter_config.py` | adapter |

(Adapter-config *services* are in [17 — services](17-services.md) via
`test_services_adapter_config.py`.)

---

## What's tested

- **Registry** — register / get adapter config, the module-level shims
  (`get_adapter_config`, `get_adapter_value`), coordinator wiring, and the
  all-configs accessor.
- **Config loader** — loading stored adapter configs from `hass_storage` and
  registering them (incl. the per-config skip-one-on-error resilience).
- **Brand selection** (`brands.py`, `test_brand_selection.py`, `BR-1..BR-7`) —
  which registrar runs for a given vacuum: positive detection wins in table
  order; no match reaches the DECLARED default arm and reports
  `source="default"` (distinct from a positive `"detected"` match, so a log
  line can say the brand was *assumed*, not identified); an explicit
  per-vacuum override (the UI-selector seam) outranks detection; a malformed /
  unknown / absent override degrades to detection rather than raising, but an
  unknown override id is still logged, never silently dropped; a detector that
  throws is skipped rather than taking setup down; and the real Roborock
  detector resolves end-to-end against the shipped table (an unrecognised
  device — blank manufacturer/model — still resolves to the Eufy default, the
  behaviour the old `if/else` had, now reported as `"default"` instead of
  being indistinguishable from a positive match).
- **Eufy adapter** (separate suite, `tests/adapters/eufy/`) — `model_catalog`
  resolution (code + hint matching), `lifecycle` helpers, the
  `buttons`/`entities` candidate-data shape, the CV `segmentor` wrapper +
  splitter helpers, per-component `maintenance_only` flag survival through the
  adapter's explicit-key config reconstruction (`test_maintenance_config.py`,
  issue #38 regression), the localized upkeep-guide data (`test_upkeep_guides_i18n.py`,
  17 languages, subset-of-English + non-empty-and-different-steps invariants),
  and the dock-vs-robot error-SOURCE classification
  (`test_error_source.py`, `EUFY_DOCK_SOURCED_ERROR_CODES` /
  `EUFY_EVIDENCE_INVALIDATING_ERROR_CODES` in `vocabulary.py` — exists because
  `total_error_seconds` is subtracted from `cleaning_time_seconds`, so a fault
  that never stopped the robot cleaning would otherwise silently zero a
  productive run). (Charging reads are brand-agnostic now and tested in
  `tests/unit/test_charging.py` — see [01 — core](01-core.md).)
- **Roborock adapter** (separate suite, `tests/adapters/roborock/`) — the
  brand-SPECIFIC wiring: model detection, brand auto-detect (device-registry
  manufacturer/model), and the key grounded config values, verified against
  the captured `vacuum.ivy` states + a run trace. The device-registry lookup is
  monkeypatched so the tests don't depend on HA registry plumbing. The
  brand-agnostic contract (schema conformance, dispatch shape, registry
  validation, entity-id format) for Roborock is covered separately, by
  `test_adapter_contract.py` via its `ADAPTER_BUILDERS` entry — adding a brand
  there runs the whole conformance suite against it with no new test code.
- **Eufy engine seams** (also in `tests/adapters/eufy/`) — the two pluggable
  engines the Eufy adapter declares. `test_room_attribution.py` pins the ported
  `EufyAnchorWindingAttributor` (`learning/room_attribution_engines.py`) against
  the 3 adversarial external-run fixtures (the 9/9 dwell + spread + winding +
  swept-area attribution, dock-trap exclusion included). `test_job_segmenter_config.py`
  asserts the Eufy adapter declares `job_segmenter.engine = "eufy_counter_v1"`,
  that its `job_segmenter.tuning` equals `EufyCounterSegmenter.DEFAULT_TUNING`
  (no threshold drift after the move out of `live_transition`), and that the
  declared engine resolves and validates clean.
- **Brand-aware diagnostics self_check** (`DIAG-*`, integration,
  `tests/integration/test_diagnostics.py`) — `_self_check` reads a native-integration
  brand (Roborock: rooms from its own integration, no `active_map` sensor, no Eufy
  `segments` attribute) as rooms/map WORKING and brand-named, driven by the
  `roborock_geometry_drift` decode-drift block in the dump, rather than the Eufy-shaped
  "unknown / unavailable / no" the transport-only heuristic produced (`DIAG-9`); and
  degrades to a generic "native integration" + map-"pending" summary when the raw map
  hasn't decoded yet and the brand string is absent (`DIAG-10`).
- **Every adapter test file needs `hass`** for the config-registration seam —
  see [01 — overview](../01-overview.md) for which files and why.

---

## The adapter coverage boundary

`adapters/eufy/*` and `adapters/roborock/*` are **counted in the coverage
number** — we always test the adapters we ship, so the figure includes both.
The Eufy adapter is well covered: `model_catalog`, `lifecycle`, and the
`buttons`/`entities` data shape sit at or near 100%. The CV `segmentor` is
**91%** — the splitter helpers, recovery / scoring / issue-tag paths, and (via
two map fixtures) the localized-bins SPLIT + child-handling are all covered;
its remaining tail is the splitter-internal *alternative* sub-branches (see
Known gaps), the natural place a second-brand effort would invest. `adapter.py`
(85%) is missing 5 lines (124, 156-159): the `return None` guard in the small
helper `_build_button_block` when a button key is absent from both candidates
and tokens maps (124), and inside `_registry_model_code` — the
device-registry model lookup that replaced the old standalone
`discovery.py` — the device-registry `.get()` call itself (156), its
None-guard early return (157-158), and the successful resolved-model
`return` (159): the whole device-registry happy path is untested, not just
an early-return guard. (The earlier entity-registry/no-device-id guard,
154-155, is covered.) The Roborock adapter is well covered too:
`adapter.py` sits at 96%, and every other Roborock module (model catalog,
vocabulary, entities, const, upkeep) is at 100%. See
[01 — overview](../01-overview.md) for the three-layer split.

---

## Known gaps

`registry.py` (91%) leaves mostly defensive validator arms uncovered — the
`append`-an-issue branches that reject a malformed stored adapter config
(missing lines 180, 287, 378, 387, 407, 411, 424, 433, 453, 467, 489, 523, 589,
618, 651 — `--cov-report=term-missing` for the current mapping to specific
checks). The `job_segmenter` engine-validation arms (not-a-dict / missing /
unknown engine) are covered — `test_adapters.py` asserts that contract so an
unknown engine can't silently fall back. The rest are error paths for invalid
storage, not real behavior holes. `adapter.py` (85%, see above) is missing the
one defensive button-block guard plus the entire device-registry-lookup
happy path in `_registry_model_code` (156-159, see above) — that path is
untested outright, not merely a defensive early return. `config_schema.py`
(94%) is missing 3 lines
(1866, 1893, 1958) in schema-validation branches not yet re-triaged this pass.

The one remaining thin spot is **CV `segmentor` depth** (91%, up from 70% —
first the splitter / recovery / scoring / issue-tag tests and the
`_prune_localized_siblings` extraction (`[SP-prune]`), then two map fixtures
that drive the full pipeline). The localized-bins SPLIT is the deepest tier,
and it took two fixtures to pin: a dense **over-segmented** synthetic map
(`[ECV-8]`, `adversarial_map.png`) covers the classification / scoring /
overlap-dedup paths, but it can only make localized-bins *run-and-reject* —
the accept gate is a narrow hue window. The one input that reaches localized
**accept** plus its child-handling (reclaim / rank / prune of recovered room
pockets) is a **real map run exactly as the integration runs it** — dark
primary + light assist — where adjacent rooms fuse with the blue background
into a single >120k-px component (`[ECV-9]`, `localized_map_*.png`);
diagnostic-confirmed as the only input that hits accept. What's genuinely left
is the splitter-internal *alternative* sub-branches the accepted path skips
(assist-hue / colour-distance / erosion variants), the env-gated scipy-absent
guard, and defensive continues — each geometry-sensitive or best-effort.
Tested in `test_segmentor.py` + `test_segmentor_splitters.py`; held here on
purpose, a known thin spot rather than a framework miss.

The Roborock adapter has no comparable known gap — it is a much smaller,
declarative-config module (no CV pipeline), and every source file except
`adapter.py` is at 100%.
