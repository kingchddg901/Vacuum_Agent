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

## Key `hass.data[DOMAIN]` keys

Fixtures and handlers locate each other through these (defined in `const.py`):

| Constant | Value | Holds |
|----------|-------|-------|
| `DATA_RUNTIME` | `"runtime"` | the core `EufyVacuumManager` |
| `DATA_LEARNING` | `"learning"` | the `LearningManager` (lazily created) |
| `DATA_BATTERY` | `"battery"` | the battery health manager |
| `DATA_ERROR_TRACKER` | `"error_tracker"` | the `ErrorTracker` |
| `DATA_ADAPTER_COORDINATOR` | `"adapter_coordinator"` | the active `AdapterCoordinator` |
