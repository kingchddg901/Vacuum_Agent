# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema. The
one concrete adapter (`adapters/eufy/`) lives behind this boundary and has its
own focused suite in `tests/adapters/eufy/`. Covered by **31 framework tests
across 2 files** (`test_adapters.py` + the brand-agnostic
`test_adapter_contract.py` conformance harness), plus **160 Eufy-adapter tests**.

<!-- The two bold counts above are HAND-MAINTAINED. update_test_docs.py's
single-header model can't compute the framework-vs-Eufy split, so it WARNs and
skips this doc's headline (the WARN is expected, not a bug). Update them by hand
on adapter test changes — collect-only case counts:
  framework = tests/integration/test_adapters.py + tests/adapters/test_adapter_contract.py
  Eufy      = tests/adapters/eufy/ -->


Source: `custom_components/eufy_vacuum/adapters/`
Architecture reference: [docs/dev/21-adapter-system.md](../../dev/21-adapter-system.md), [docs/dev/22-adapter-config-reference.md](../../dev/22-adapter-config-reference.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `registry.py` | 154 | 93% | `test_adapters.py` | integration |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration |
| `config_schema.py` | 2 | 100% | `test_adapters.py` | integration |
| `eufy/segmentor.py` | 866 | 91% | `tests/adapters/eufy/` | adapter |
| `eufy/adapter.py` | 52 | 85% | `tests/adapters/eufy/` | adapter |
| `eufy/discovery.py` | 54 | 100% | `test_discovery.py` | adapter |
| `eufy/entities.py` | 28 | 100% | `test_buttons_entities.py` | adapter |
| `eufy/lifecycle.py` | 21 | 100% | `test_lifecycle.py` | adapter |
| `eufy/constants.py` | 15 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/model_catalog.py` | 12 | 100% | `test_model_catalog.py` | adapter |
| `eufy/vocabulary.py` | 12 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/const.py` | 8 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/buttons.py` | 4 | 100% | `test_buttons_entities.py` | adapter |
| `eufy/upkeep_catalog.py` | 3 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/water_config.py` | 3 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/maintenance_components.py` | 1 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/upkeep_guides.py` | 1 | 100% | `tests/adapters/eufy/` | adapter |

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
- **Eufy adapter** (separate suite, `tests/adapters/eufy/`) — `model_catalog`
  resolution (code + hint matching), `discovery` and `lifecycle` helpers, the
  `buttons`/`entities` candidate-data shape, and the CV `segmentor` wrapper +
  splitter helpers. (Charging reads are brand-agnostic now and tested in
  `tests/unit/test_charging.py` — see [01 — core](01-core.md).)
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

---

## The adapter coverage boundary

`adapters/eufy/*` is **counted in the coverage number** — we always test the
adapters we ship, so the figure includes them. The Eufy adapter is well covered
(160 tests in `tests/adapters/eufy/`): `model_catalog`, `discovery`, `lifecycle`,
and the `buttons`/`entities` data shape sit at or near 100%. The CV `segmentor`
is now **91%** — the splitter helpers, recovery / scoring / issue-tag paths, and
(via two map fixtures) the localized-bins SPLIT + child-handling are all covered;
its remaining tail is the splitter-internal *alternative* sub-branches (see Known
gaps), the natural place a second-brand effort would invest. `adapter.py` (95%) is missing
only line 110 — the `return None` guard in the small helper `_build_button_block`
when a button key is absent from both candidates and tokens maps. See
[01 — overview](../01-overview.md) for the three-layer split.

---

## Known gaps

`registry.py` (94%) leaves only defensive validator arms uncovered — the
`append`-an-issue branches that reject a malformed stored adapter config
(`room_profiles` / `dispatch` block-shape checks, missing `registry.py` lines
305, 309, 322, 409, 436, 442). The `job_segmenter` engine-validation arms
(not-a-dict / missing / unknown engine) are now covered — `test_adapters.py`
asserts that contract so an unknown engine can't silently fall back. The rest are
error paths for invalid storage, not real behavior holes. `adapter.py` (95%)
is missing one line (110), the `return None` guard in `_build_button_block`
for a component with no reset button — likewise defensive.

The one remaining thin spot is **CV `segmentor` depth** (91%, up from 70% — first
the splitter / recovery / scoring / issue-tag tests and the `_prune_localized_siblings`
extraction (`[SP-prune]`), then two map fixtures that drive the full pipeline). The
localized-bins SPLIT is the deepest tier, and it took two fixtures to pin: a dense
**over-segmented** synthetic map (`[ECV-8]`, `adversarial_map.png`) covers the
classification / scoring / overlap-dedup paths (~1357–1385, ~1427–1429), but it can
only make localized-bins *run-and-reject* — the accept gate is a narrow hue window.
The one input that reaches localized **accept** plus its child-handling (reclaim /
rank / prune of recovered room pockets) is a **real map run exactly as the integration
runs it** — dark primary + light assist — where adjacent rooms fuse with the blue
background into a single >120k-px component (`[ECV-9]`, `localized_map_*.png`);
diagnostic-confirmed as the only input that hits accept, and it exercises 502/866
statements in one pass. What's genuinely left is the splitter-internal *alternative*
sub-branches the accepted path skips (assist-hue / colour-distance / erosion variants,
~475–520, ~605–648, ~807–828, partial ~1351–1365), the env-gated scipy-absent guard
(943), and defensive continues (1056-1057, 1100, 1112, 1150) — each geometry-sensitive
or best-effort. Tested in `test_segmentor.py` + `test_segmentor_splitters.py`; held
here on purpose, a known thin spot rather than a framework miss.
