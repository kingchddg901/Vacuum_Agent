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

- **Pure log-only / best-effort `except` blocks** — a block whose *only* effect
  is a log line (best-effort I/O writes, listener teardown). These carry
  `# pragma: no cover` instead (see below).
- **Inactive / dead code paths** — functions that currently always return early,
  or guards whose conditions are mutually exclusive (e.g. the documented dead
  branch in `core/manager.py`'s progress snapshot).
- **A real device or live HA entity setup** — e.g. the live-entity path of the
  `discover_rooms` service, which drives real adapter entities. The handler
  itself *is* covered with a mock manager (`test_services_rooms.py`
  `test_discover_handler_success` / `test_discover_handler_raises`, SR-5/SR-6);
  only the live-entity path is left to a full integration boot, the same place
  `async_setup_entry` boot wiring runs.
- **Defensive `continue` / `return []` normalization guards** — left as *honest
  misses* (real control flow, so not pragma'd), since a test that feeds garbage
  to assert it's skipped asserts plumbing, not behavior.

Coverage of those costs more than it protects. Spend the effort on real
behavior.

### But DO test an `except` that changes the surfaced result

The opposite of the first bullet: an `except` block is **behavior** — and worth
a test — when it does more than log. Test it when the failure path:

- **wraps the error** as `HomeAssistantError` / `ServiceValidationError` (the HA
  Silver action-exception contract) — `monkeypatch` the manager method to raise,
  then assert the wrapped type (see `test_services_run_profiles.py` `SRN-11`,
  `test_services_maintenance_reset.py` `MR-4/5`);
- **returns a degraded field** the caller sees (e.g. `start_selected_rooms`'
  `learning_snapshot: {saved: False, reason: snapshot_error}`, `SS-7`);
- **skips one item and continues** a fan-out loop (a failing update callback must
  not block the rest — `MD-7`).

The rule of thumb: *if removing the except would change what a caller observes,
it's behavior; if it would only change the logs, it's a `# pragma: no cover`.*

## Coverage exclusions (`# pragma: no cover`)

`.coveragerc` excludes `pragma: no cover` lines. Put it on the **`except` line
itself** (not the log line) so the whole branch drops, and append a short reason:

```python
except OSError as err:  # pragma: no cover - best-effort I/O, logs and swallows
    _LOGGER.debug("…failed to write %s: %s", path, err)
```

Use it surgically, one audited block at a time — never a blanket `_LOGGER.*`
regex, which would also silence the behavioral excepts above and leave
half-excluded branches under `--cov-branch`. The full convention is in
[subsystems/README](subsystems/README.md#coverage-conventions-apply-everywhere).
