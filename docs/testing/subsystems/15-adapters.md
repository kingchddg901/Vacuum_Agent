# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema. The
one concrete adapter (`adapters/eufy/`) lives behind this boundary and is tested
**separately**. Covered by **30 framework tests across 2 files**
(`test_adapters.py` + the brand-agnostic `test_adapter_contract.py` conformance
harness), plus **91 Eufy-adapter tests**.

Source: `custom_components/eufy_vacuum/adapters/`
Architecture reference: [docs/dev/21-adapter-system.md](../../dev/21-adapter-system.md), [docs/dev/22-adapter-config-reference.md](../../dev/22-adapter-config-reference.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `registry.py` | 111 | 94% | `test_adapters.py` | integration |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration |
| `config_schema.py` | 2 | 100% | `test_adapters.py` | integration |
| `eufy/*` | — | **omitted** | `tests/adapters/eufy/` | adapter |

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

## The brand-agnostic coverage boundary

`adapters/eufy/*` is **excluded from the framework coverage number** via
`.coveragerc` (`omit = .../adapters/eufy/*`). This keeps the headline figure
about the brand-agnostic framework, not diluted by the one concrete adapter. The
Eufy adapter **is** tested (91 tests in `tests/adapters/eufy/`): `model_catalog`,
`discovery`, `lifecycle`, and the `buttons`/`entities` data shape have focused
tests, while `adapter.py` (the big assembly function) and the CV `segmentor`
remain the thin spots — the segmentor needs heavy image fixtures and is the
natural place a second-brand effort would invest. See
[01 — overview](../01-overview.md) for the three-layer split.

---

## Known gaps

`registry.py` (94%) leaves a few defensive accessors. The real gap is **Eufy
adapter depth** — tracked as a deliberate boundary, not a framework miss.
