# 03 — Fixtures and Helpers

Two `conftest.py` files supply everything. Know what each gives you before
writing a new test — most scaffolding you might reach to build already exists.

## Root: `tests/conftest.py`

Applies to the whole suite.

| Fixture | Scope | What it gives you |
|---------|-------|-------------------|
| `auto_enable_custom_integrations` | autouse | Wraps phac's `enable_custom_integrations` so HA's loader can see `custom_components/eufy_vacuum`. Without it, phac blocks custom integrations for isolation. You never call this — it just runs. |
| `mock_config_entry` | function | A `MockConfigEntry` for the typical first-time setup: `vacuum.alfred` + a tested model + notes, empty options, `unique_id = DOMAIN`. |
| `mock_entry_no_vacuum` | function | Entry where the user skipped the vacuum entity (model only). For setup-flow edge cases. |
| `mock_options_entry` | function | Entry where `vacuum_entity_id` was set via the options flow instead of initial data. |

The `hass` fixture itself comes from `pytest-homeassistant-custom-component` —
you do not define it. Just add `hass` as a test parameter and you get a fresh
in-memory Home Assistant.

## Integration: `tests/integration/conftest.py`

The workhorses.

### `manager`

A fully initialized `EufyVacuumManager`, constructed **directly** (bypassing
`async_setup_entry`) so tests can exercise manager logic without entity
listeners, panels, or service registration.

What it wires for you:

- Constructs an `AdapterCoordinator` and stashes it at
  `hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR]`, so the module-level adapter
  registry shims (`register_adapter_config`, `get_adapter_config`) resolve
  correctly.
- Calls `await m.async_initialize()`.
- Sets `hass.data[DOMAIN][DATA_RUNTIME] = m` so service handlers and the
  learning manager can locate it.

Use this when you are testing manager methods directly and do **not** need the
service registry.

### `manager_with_services`

`manager` plus every domain service registered through
`async_register_services` (the same path `async_setup_entry` uses), with
`async_unregister_services` on teardown.

Use this whenever your test calls `hass.services.async_call(DOMAIN, ...)`.

```python
async def test_something(hass, manager_with_services):
    await hass.services.async_call(DOMAIN, "save_managed_rooms",
        {"vacuum_entity_id": "vacuum.alfred", "map_id": "1"}, blocking=True)
    assert "vacuum.alfred" in manager_with_services.data["maps"]
```

> Learning services are **not** part of `async_register_services`. Test files
> that need them register their own scoped fixture — see the `learning_services`
> fixture inside `test_learning_services.py`, which calls
> `async_register_learning_services` / `async_unregister_learning_services`.

### Seeding helpers (importable functions, not fixtures)

Import these from `.conftest` in any integration test:

| Helper | Signature | What it does |
|--------|-----------|--------------|
| `seed_discovery` | `(manager, vac, map_id, rooms)` | Pre-populates `manager.data["discovery"][vac][map_id]` so `save_managed_rooms` has something to read. |
| `make_rooms` | `(map_id, count) -> list[dict]` | Returns `count` minimal discovered-room dicts (`room_id`, `map_id`, `name`). |
| `setup_map` | `(manager, vac, map_id, count=3, enabled_room_ids=None) -> dict` | Seeds discovery **and** calls `save_managed_rooms`. The one-liner to get managed rooms in place. |

```python
from .conftest import setup_map

async def test_x(hass, manager_with_services):
    setup_map(manager_with_services, "vacuum.alfred", "1", count=2)
    # rooms now live at manager.data["maps"]["vacuum.alfred"]["1"]["rooms"]
```

## Per-file helpers

Larger test files define their own private seeding helpers at module scope.
The richest example is `test_learning_services.py`:

| Helper | What it seeds |
|--------|---------------|
| `_seed_completed_job(hass, vac, job_id, *, room_slugs, status, used_for_learning, duration_minutes)` | Writes a completed-job payload via `LearningHistoryStore`. |
| `_seed_active_job(manager, vac, map_id, **extra)` | Writes active-job state into `manager.data["active_jobs"][vac][map_id]`. |

When you start a new test file for a subsystem, look for an existing file in the
same domain first — the seeding helper you need has often already been written.

## Shared factories: `tests/_factories.py`

Behaviour-preserving builders for the setup the suite had copy-pasted. Each is an
*extraction* — it produces exactly the data or effect the inline code it replaces
produced — so a refactored test asserts the identical thing. Import from anywhere
(`tests` is a package): `from tests._factories import ...`.

| Helper | Signature | Replaces |
|--------|-----------|----------|
| `VAC` / `MAP` / `ENTRY_ID` | constants | the per-file `_VAC = "vacuum.alfred"` / `_MAP = "1"` / `_ENTRY_ID = "test_entry_id"` literals |
| `get_room_data` | `(manager, room_id, *, vac=VAC, map_id=MAP) -> dict` | the copy-pasted `manager.data.get("maps",{})…get(str(room_id),{})` lookup chain in `_make_*` entity builders (returns `{}` when absent) |
| `set_room_field` | `(manager, room_id, *, vac=VAC, map_id=MAP, **fields) -> dict` | inline writes like `manager.data["maps"][VAC][MAP]["rooms"]["1"]["enabled"] = False` (mutates an **existing** room; does not create rooms or pop keys) |
| `make_manager_mock` | `(*, run_profiles=None, **attrs) -> MagicMock` | the stub-manager builder (`async_save` as an `AsyncMock`, `reset_maintenance` / `start_run_profile`, a preloaded saved-run-profile library) used by button/platform tests |

Two conventions keep refactored tests readable:

- **Defaults cover what a test does NOT assert on.** A test that asserts a field
  passes it explicitly, so "what's under test" stays visible at the call site.
- **Extract from real use.** Add a helper only when a live test needs it, and only
  if it reproduces that test's inline code exactly — never speculatively.

Route only **setup** through the factory; keep assertions verbatim. The helpers are
pure dict/mock operations and touch no production code, so they never change which
`custom_components` lines a test exercises.

> Not every duplicated line belongs in the factory. A one-off `.values()` loop or a
> bespoke per-test seed is clearer left inline — forcing it through a helper is
> churn, not dedup. `make_mock_hass` (the `MagicMock()` + `config.config_dir`
> idiom) is deliberately **not** in the factory yet: a two-line block in large
> files, too low-value to justify a refactor.

### Refactoring setup safely: `scripts/diff_test_equiv.py`

When extracting a helper from an existing test, prove the change is
behaviour-preserving **before** it lands. The differential harness runs an
untouched ORIGINAL and a factored CLONE and checks three things hold:

1. same set of test names (nothing dropped, renamed, or added),
2. both fully green with the same pass count,
3. identical executed-line set on the module(s) under test — the objective proof
   the clone exercises the same code paths.

```
docker run --rm -v "<repo>:/workspace" -w /workspace eufy-vacuum-test \
    python scripts/diff_test_equiv.py <original> <clone> \
        --cov custom_components/eufy_vacuum
```

`=> EQUIVALENT` (exit 0) means the refactor is safe to cut over. Point `--cov` at
the specific module under test, or at the whole `custom_components/eufy_vacuum`
package for the strongest (line-for-line) check. The recommended flow: clone into
a staging dir excluded from the gate, validate every clone EQUIVALENT, then cut
over all at once.

## Key `hass.data[DOMAIN]` keys

Fixtures and handlers locate each other through these (defined in `const.py`):

| Constant | Value | Holds |
|----------|-------|-------|
| `DATA_RUNTIME` | `"runtime"` | the core `EufyVacuumManager` |
| `DATA_LEARNING` | `"learning"` | the `LearningManager` (lazily created) |
| `DATA_BATTERY` | `"battery"` | the battery health manager |
| `DATA_ERROR_TRACKER` | `"error_tracker"` | the `ErrorTracker` |
| `DATA_ADAPTER_COORDINATOR` | `"adapter_coordinator"` | the active `AdapterCoordinator` |
