# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema. The
one concrete adapter (`adapters/eufy/`) lives behind this boundary and has its
own focused suite in `tests/adapters/eufy/`. Covered by **30 framework tests
across 2 files** (`test_adapters.py` + the brand-agnostic
`test_adapter_contract.py` conformance harness), plus **91 Eufy-adapter tests**.

Source: `custom_components/eufy_vacuum/adapters/`
Architecture reference: [docs/dev/21-adapter-system.md](../../dev/21-adapter-system.md), [docs/dev/22-adapter-config-reference.md](../../dev/22-adapter-config-reference.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `registry.py` | 117 | 96% | `test_adapters.py` | integration |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration |
| `config_schema.py` | 2 | 100% | `test_adapters.py` | integration |
| `eufy/segmentor.py` | 865 | 70% | `tests/adapters/eufy/` | adapter |
| `eufy/adapter.py` | 39 | 93% | `tests/adapters/eufy/` | adapter |
| `eufy/*` (others) | — | 100% | `tests/adapters/eufy/` | adapter |

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
(91 tests in `tests/adapters/eufy/`): `model_catalog`, `discovery`, `lifecycle`,
and the `buttons`/`entities` data shape sit at or near 100%. The one visible thin
spot is the CV `segmentor` (70%), which needs heavy image fixtures and is the
natural place a second-brand effort would invest; `adapter.py` (the big assembly
function) is at 93%. See [01 — overview](../01-overview.md) for the three-layer
split.

---

## Known gaps

`registry.py` (94%) leaves a few defensive accessors. The real gap is **CV
`segmentor` depth** (70%) — the image-pipeline long tail that needs fixture-heavy
tests, tracked as a known thin spot rather than a framework miss.
