# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema. The
one concrete adapter (`adapters/eufy/`) lives behind this boundary and has its
own focused suite in `tests/adapters/eufy/`. Covered by **30 framework tests
across 2 files** (`test_adapters.py` + the brand-agnostic
`test_adapter_contract.py` conformance harness), plus **95 Eufy-adapter tests**.

Source: `custom_components/eufy_vacuum/adapters/`
Architecture reference: [docs/dev/21-adapter-system.md](../../dev/21-adapter-system.md), [docs/dev/22-adapter-config-reference.md](../../dev/22-adapter-config-reference.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `registry.py` | 141 | 91% | `test_adapters.py` | integration |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration |
| `config_schema.py` | 2 | 100% | `test_adapters.py` | integration |
| `eufy/segmentor.py` | 865 | 70% | `tests/adapters/eufy/` | adapter |
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
(95 tests in `tests/adapters/eufy/`): `model_catalog`, `discovery`, `lifecycle`,
and the `buttons`/`entities` data shape sit at or near 100%. The one visible thin
spot is the CV `segmentor` (70%), which needs heavy image fixtures and is the
natural place a second-brand effort would invest; `adapter.py` (95%) is missing
only line 110 — the `return None` guard in the small helper `_button_block_or_none`
when a button key is absent from both candidates and tokens maps. See
[01 — overview](../01-overview.md) for the three-layer split.

---

## Known gaps

`registry.py` (91%) leaves only defensive validator arms uncovered — the
`append`-an-issue branches that reject a malformed stored adapter config
(`job_segmenter` / `room_profiles` / `dispatch` block-shape checks, missing
`registry.py` lines 276, 285, 290, 305, 309, 322, 409, 436, 442). These are
error paths for invalid storage, not real behavior holes. `adapter.py` (95%)
is missing one line (110), the `return None` guard in `_button_block_or_none`
for a component with no reset button — likewise defensive.

The one substantive thin spot is **CV `segmentor` depth** (70%) — the
image-pipeline long tail that needs heavy fixtures. The uncovered lines cluster
in the localized-bins child keep/reject branches inside the main segmentation
pass (~1300–1346) and the localized dedup-prune plus count-deficit recovery loop
(~1371–1465), with scattered split-variant scoring helpers elsewhere. This is
tested in `tests/adapters/eufy/test_segmentor.py` and `test_segmentor_splitters.py`
and is held at ~70% on purpose — the natural place a second-brand effort would
invest, tracked as a known thin spot rather than a framework miss.
