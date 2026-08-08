# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema.
Two concrete adapters now live behind this boundary — **Eufy**
(`adapters/eufy/`) and **Roborock** (`adapters/roborock/`) — each with its own
focused suite, plus `adapters/brands.py` (which registrar runs for a given
vacuum) and the brand-agnostic conformance harness that runs every contract
test once per shipped brand. Covered by **94 framework tests across 3 files**
(`test_adapters.py`, `test_adapter_contract.py` — parametrized over both
brands — and `test_brand_selection.py`), plus **212 Eufy-adapter tests** and
**37 Roborock-adapter tests**.

<!-- The three bold counts above are HAND-MAINTAINED. update_test_docs.py's
single-header model can't compute the framework/Eufy/Roborock split, so it WARNs
and skips this doc's headline (the WARN is expected, not a bug). Update them by
hand on adapter test changes — collect-only case counts:
  framework  = tests/integration/test_adapters.py + tests/adapters/test_adapter_contract.py + tests/adapters/test_brand_selection.py
  Eufy       = tests/adapters/eufy/
  Roborock   = tests/adapters/roborock/ -->

Source: `custom_components/eufy_vacuum/adapters/`
Architecture reference: [docs/dev/21-adapter-system.md](../../dev/21-adapter-system.md), [docs/dev/22-adapter-config-reference.md](../../dev/22-adapter-config-reference.md)

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

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `registry.py` | 215 | 91% | `test_adapters.py` | integration | clean |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration | clean |
| `config_schema.py` | 64 | 94% | `test_adapters.py` | integration | clean |
| `brands.py` | 58 | 100% | `test_brand_selection.py` | integration | clean |
| `eufy/segmentor.py` | 866 | 91% | `tests/adapters/eufy/` | adapter | - |
| `eufy/adapter.py` | 52 | 85% | `tests/adapters/eufy/` | adapter | - |
| `eufy/entities.py` | 28 | 100% | `test_buttons_entities.py` | adapter | clean |
| `eufy/lifecycle.py` | 21 | 100% | `test_lifecycle.py` | adapter | clean |
| `eufy/constants.py` | 15 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/model_catalog.py` | 12 | 100% | `test_model_catalog.py` | adapter | clean |
| `eufy/vocabulary.py` | 43 | 100% | `test_error_source.py` + `tests/adapters/eufy/` | adapter | clean |
| `eufy/const.py` | 8 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/buttons.py` | 4 | 100% | `test_buttons_entities.py` | adapter | clean |
| `eufy/upkeep_catalog.py` | 3 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/water_config.py` | 3 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/maintenance_components.py` | 1 | 100% | `test_maintenance_config.py` | adapter | clean |
| `eufy/eufy_upkeep_guides.py` | 1 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/upkeep_guides_i18n/*.py` (17 languages) | 19 | 100% | `test_upkeep_guides_i18n.py` | adapter |
| `roborock/adapter.py` | 46 | 96% | `roborock/test_adapter.py` | adapter | - |
| `roborock/model_catalog.py` | 7 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/vocabulary.py` | 18 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/entities.py` | 22 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/const.py` | 6 | 100% | `roborock/test_adapter.py` | adapter | - |
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
