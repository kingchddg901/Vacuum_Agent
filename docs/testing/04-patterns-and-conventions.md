# 04 — Patterns and Conventions

Follow these so new tests read like the existing ones and stay easy to map back
to behavior.

## Coverage-target IDs

Every test file opens with a docstring that enumerates **coverage targets** —
short IDs, each naming one behavior, each owned by one test. The prefix is a
mnemonic for the file.

```python
"""Phase 4 integration tests — rooms service handlers.

Coverage targets
----------------
[SR-1]  save_managed_rooms service persists room config.
[SR-2]  get_vacuum_maps service returns map list for a vacuum.
[SR-3]  update_room_fields service updates a field and returns ok.
[SR-4]  update_room_fields service returns error for unknown room.
"""
```

Each test then references its target in its own docstring:

```python
async def test_save_managed_rooms_service_persists_rooms(hass, manager_with_services):
    """[SR-1] save_managed_rooms service writes rooms into manager data."""
```

Why it matters: the target list is the file's table of contents and its
contract. When you add a behavior, add a target ID and a test for it. When a
test fails, the ID tells you which behavior broke without reading the body.

Established prefixes include `LS` (learning services), `SR` (services-rooms),
`BE` (button entity), and so on — one per file. Pick a short, unique prefix for
a new file.

## Naming

| Thing | Convention | Example |
|-------|------------|---------|
| Test file | `test_<area>.py`, grouped by subsystem or platform | `test_services_queue.py`, `test_listeners_timers.py` |
| Test function | `test_<subject>_<expected>` | `test_get_vacuum_maps_service_returns_dict` |
| Module constants | `_VAC`, `_MAP` at top of file | `_VAC = "vacuum.alfred"` |
| Private helpers | leading underscore, module scope | `_seed_active_job`, `_make_manager` |

`vacuum.alfred` is the standard test vacuum across the suite. Reuse it.

## Calling a service

```python
result = await hass.services.async_call(
    DOMAIN,
    "service_name",
    {"vacuum_entity_id": _VAC, "map_id": _MAP},
    blocking=True,
    return_response=True,   # only for services that return data
)
```

- `blocking=True` — wait for completion before asserting.
- `return_response=True` — required for services that return a payload (the
  read/snapshot services). Omit it for fire-and-forget services, which return
  `None`.

After a service that schedules background work, drain the loop before
asserting:

```python
await hass.async_block_till_done()
```

## Sync manager methods: run them in the executor

Many manager methods are **synchronous** and do blocking file I/O through the
store (`finalize_completed_job`, the rebuilders, snapshot writes). HA forbids
blocking the event loop, so call them through the executor:

```python
result = await hass.async_add_executor_job(
    lambda: learning.finalize_completed_job(
        manager=core_manager,
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        battery_start=85, battery_end=60,
        started_at="2026-01-01T09:00:00+00:00",
        ended_at="2026-01-01T09:30:00+00:00",
        used_for_learning=False,
        rebuild_stats=False,
    )
)
```

The async wrappers (e.g. `async_finalize_completed_job`) do this internally —
prefer them when one exists. Drop to the sync method + executor only when you
are specifically testing the sync path.

## Unit tests: mock the manager

Entity and platform unit tests do not need a real manager — they need an object
that records calls. Build a `MagicMock`, with `AsyncMock` for the async methods:

```python
from unittest.mock import AsyncMock, MagicMock

def _make_manager(*, run_profile_data=None):
    manager = MagicMock()
    manager.async_save = AsyncMock()          # awaited by the entity
    manager.reset_maintenance = MagicMock()   # sync
    manager.get_saved_run_profiles.return_value = {"library": run_profile_data or {}}
    return manager
```

Then assert on the recorded interaction:

```python
manager = _make_manager()
button = _make_reset_button(manager)
await button.async_press()
manager.reset_maintenance.assert_called_once()
manager.async_save.assert_awaited_once()
```

Use this for anything whose logic is "translate an HA call into a manager call"
— buttons, switches, numbers, sensors. It is faster and more precise than
standing up the full manager.

## Assertions: prefer presence over exact equality

Because the integration `hass` shares its `config_dir` across tests in a run
(see [05](05-gotchas-and-pitfalls.md)), seeded jobs and stats **accumulate**.
Assert on what your test added, not on totals:

```python
# Good — robust to accumulation
assert result.get("available") is True
assert result["overview"]["job_stats"]["total_jobs"] >= 1
assert any(j["job_id"] == "j-flt-001" for j in jobs)

# Fragile — breaks when another test seeds a job
assert result["overview"]["job_stats"]["total_jobs"] == 1
```

## What not to test

The suite deliberately skips:

- Defensive `except` blocks reachable only by mocking internals to raise.
- Inactive/dead code paths (functions that currently always return early).
- Anything that needs a real device or a live HA entity setup (e.g. the
  `discover_rooms` service, which drives adapter entities — note its exclusion
  in `test_services_rooms.py`).

Coverage of those costs more than it protects. Spend the effort on real
behavior.
