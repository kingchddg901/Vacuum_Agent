# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema. The
one concrete adapter (`adapters/eufy/`) lives behind this boundary and has its
own focused suite in `tests/adapters/eufy/`. Covered by **30 framework tests
across 2 files** (`test_adapters.py` + the brand-agnostic
`test_adapter_contract.py` conformance harness), plus **157 Eufy-adapter tests**.

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
| `registry.py` | 141 | 94% | `test_adapters.py` | integration |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration |
| `config_schema.py` | 2 | 100% | `test_adapters.py` | integration |
| `eufy/segmentor.py` | 866 | 85% | `tests/adapters/eufy/` | adapter |
| `eufy/adapter.py` | 40 | 95% | `tests/adapters/eufy/` | adapter |
| `eufy/discovery.py` | 54 | 100% | `test_discovery.py` | adapter |
| `eufy/entities.py` | 24 | 100% | `test_buttons_entities.py` | adapter |
| `eufy/lifecycle.py` | 21 | 100% | `test_lifecycle.py` | adapter |
| `eufy/constants.py` | 15 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/model_catalog.py` | 12 | 100% | `test_model_catalog.py` | adapter |
| `eufy/vocabulary.py` | 9 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/const.py` | 8 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/buttons.py` | 4 | 100% | `test_buttons_entities.py` | adapter |
| `eufy/upkeep_catalog.py` | 3 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/water_config.py` | 2 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/maintenance_components.py` | 1 | 100% | `tests/adapters/eufy/` | adapter |
| `eufy/upkeep_guides.py` | 1 | 100% | `tests/adapters/eufy/` | adapter |

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

---

## The adapter coverage boundary

`adapters/eufy/*` is **counted in the coverage number** — we always test the
adapters we ship, so the figure includes them. The Eufy adapter is well covered
(157 tests in `tests/adapters/eufy/`): `model_catalog`, `discovery`, `lifecycle`,
and the `buttons`/`entities` data shape sit at or near 100%. The CV `segmentor`
is now **85%** (the splitter helpers + recovery / scoring / issue-tag paths are
covered, and the localized-sibling prune is an extracted, unit-tested helper);
its remaining tail is the localized-bins pipeline branch (see Known
gaps), the natural place a second-brand effort would invest. `adapter.py` (95%) is missing
only line 110 — the `return None` guard in the small helper `_button_block_or_none`
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
is missing one line (110), the `return None` guard in `_button_block_or_none`
for a component with no reset button — likewise defensive.

The one remaining thin spot is **CV `segmentor` depth** (85%, up from 70% after
the splitter / recovery / scoring / issue-tag tests, then the
`_prune_localized_siblings` extraction — the localized-sibling rank /
overlap-dedup / top-4 cap used to be inline in the pipeline and is now a pure
helper unit-tested directly, `[SP-prune]`). What's left is the genuinely
CV-fragile long tail: the localized-bins child keep/reject + re-score branches
that only fire when a single >120k-px component splits into multiple colour
pockets inside the full pipeline (~1357–1385), the final overlap-dedup drop
(~1427–1429), and a few threshold-tuned artifact heuristics (~1339–1355) — each
needs a synthetic fill tuned to the exact HSV/morphology interplay, brittle to
force and to `--cov` perturbation. Plus the env-gated scipy-absent guard (943)
and defensive continues (1056-1057, 1100, 1112). Tested in
`test_segmentor.py` + `test_segmentor_splitters.py`; held here on purpose, a known
thin spot rather than a framework miss.
