# 01 — Overview

## What this suite tests

`eufy_vacuum` is a Home Assistant custom integration built on an **adapter
pattern**: brand-specific entity wiring lives in `adapters/`, and a large
brand-agnostic core (the manager, the job pipeline, learning, mapping,
battery, rooms, themes, setup) sits on top. The test suite targets that core
plus the HA integration seams — config flow, services, platforms, listeners.

The goal is **regression safety for refactors**. The core is being split into
subsystem packages over time (see `docs/dev/`), and the suite exists so those
moves can happen without silently breaking behavior.

## The three layers

| Layer | Directory | Needs `hass`? | What it covers |
|-------|-----------|---------------|----------------|
| **Unit** | `tests/unit/` | No (mostly) | Pure functions and isolated class methods — timestamp parsing, battery metrics math, learning estimator/finalizer helpers, room-field resolution. Fast, no I/O. |
| **Integration** | `tests/integration/` | Yes | Anything that touches the manager, the HA service registry, platforms, or the persistent store. Uses the in-memory `hass` from `pytest-homeassistant-custom-component`. |
| **Adapter** | `tests/adapters/` | No | Brand-specific pure logic (e.g. the eufy model catalog). Kept on its own path and excluded from the core coverage number. |

Rule of thumb: **if the thing under test is a pure function, write a unit
test** — it is faster, has no shared-state pitfalls, and reads more clearly.
Reach for an integration test only when you need the manager, a real service
call, or the store.

## Directory layout

```
tests/
  conftest.py                 # root fixtures: hass enablement, config entries
  __init__.py
  unit/                       # pure-function tests
    test_timestamp_utils.py
    test_battery_metrics.py
    test_learning_estimator.py
    test_learning_job_finalizer.py
    ...
  integration/
    conftest.py               # manager + manager_with_services + seeding helpers
    test_config_flow.py
    test_manager_setup.py
    test_services_rooms.py
    test_learning_services.py
    test_button_entity.py
    test_listeners_*.py
    test_setup_*.py
    test_themes_*.py
    ...
  adapters/
    conftest.py               # adapter-suite fixtures
    test_adapter_contract.py  # brand-agnostic conformance harness
    eufy/                     # concrete-adapter tests (omitted from coverage %)
      test_model_catalog.py
      test_discovery.py
      test_lifecycle.py
      test_buttons_entities.py
      test_segmentor.py
      test_segmentor_splitters.py
```

## Toolchain

Declared in `requirements_test.txt`:

| Package | Why |
|---------|-----|
| `pytest>=9.0` | runner |
| `pytest-asyncio>=1.3` | async tests; `asyncio_mode = auto` means `async def test_*` just works, no decorator |
| `pytest-cov` | coverage + branch coverage |
| `pytest-homeassistant-custom-component>=0.13.332` | the in-memory HA harness — provides the `hass` and `enable_custom_integrations` fixtures |

Config lives in two files:

- **`pytest.ini`** — `asyncio_mode = auto`, `testpaths = tests/unit tests/integration`, and the coverage `addopts` (term-missing + HTML + branch).
- **`.coveragerc`** — coverage `source` is `custom_components/eufy_vacuum`; the eufy adapter is omitted (it has its own suite under `tests/adapters/` and is brand-specific); `exclude_lines` drops `TYPE_CHECKING`, `__repr__`, `NotImplementedError`, and `pragma: no cover`.

Note that `testpaths` deliberately **excludes** `tests/adapters` — run that path
explicitly when you want it (see [02](02-running-tests.md)).

## Coverage status

**Framework coverage: 93.6% statement** (90.8% with `--cov-branch`, which the
default `addopts` enables), across the brand-agnostic core — the Eufy adapter is
omitted via `.coveragerc` (see
[subsystems/15-adapters](subsystems/15-adapters.md)). Most subsystems sit in the
92–98% band; the per-subsystem breakdown lives in
[subsystems/README](subsystems/README.md).

Coverage is a guide, not a target — the suite favors **precision** (each test
maps to a named behavior, see [04](04-patterns-and-conventions.md)) over chasing
the last few percent. The remaining misses are, by design, one of:

- **`# pragma: no cover`** — pure log-only / best-effort `except` blocks (I/O
  writes, listener teardown). Never used where the failure path escapes into a
  returned/persisted/user-visible value.
- **Honest misses** (not tested, not pragma'd) — defensive `continue` /
  `return []` guards (real control flow) and `async_setup_entry` boot wiring that
  only runs under a full integration boot.

See [subsystems/README](subsystems/README.md#coverage-conventions-apply-everywhere)
for the full convention. 95% is not pursued: reaching it on this codebase would
mean either pragma-bombing real control flow or writing tests that exist only to
move a number.
