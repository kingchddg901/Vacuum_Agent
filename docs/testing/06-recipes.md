# 06 — Recipes

Copy-paste starting points. Each is a complete, runnable skeleton — change the
names, the target IDs, and the assertions. The point of this file is that you
never rebuild this scaffolding from memory.

---

## New-file checklist

1. Pick a unique target prefix (e.g. `MQ` for manager-queue).
2. Open with a module docstring listing coverage targets.
3. Put `_VAC` / `_MAP` constants at the top.
4. Choose the fixture:
   - pure function → no fixture, import and call.
   - manager method → `manager`.
   - service call → `manager_with_services`.
   - learning service → register `learning_services` locally.
   - entity/platform → mock the manager.
5. Reuse seeding helpers from `tests/integration/conftest.py` before writing
   your own.
6. Run just your file with `--no-cov` while iterating.

---

## Recipe A — Service handler (integration)

```python
"""Phase N integration tests — <area> service handlers.

Coverage targets
----------------
[XX-1]  <service> persists/returns <thing>.
[XX-2]  <service> errors on <bad input>.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


async def test_service_persists(hass, manager_with_services):
    """[XX-1] <service> writes the expected state."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)

    await hass.services.async_call(
        DOMAIN, "<service_name>",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )

    assert _VAC in manager_with_services.data["maps"]


async def test_service_returns_payload(hass, manager_with_services):
    """[XX-2] <service> returns a response dict."""
    result = await hass.services.async_call(
        DOMAIN, "<service_name>",
        {"vacuum_entity_id": _VAC},
        blocking=True, return_response=True,
    )
    assert isinstance(result, dict)
```

---

## Recipe B — Entity / platform (unit, mocked manager)

```python
"""Phase N integration tests — <platform> entity.

Coverage targets
----------------
[XE-1]  <Entity>.unique_id encodes <fields>.
[XE-2]  <Entity>.async_press calls manager.<method> + async_save.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.eufy_vacuum.<platform> import <Entity>


_VAC = "vacuum.alfred"


def _make_manager() -> MagicMock:
    manager = MagicMock()
    manager.async_save = AsyncMock()
    manager.<method> = MagicMock()
    return manager


def test_unique_id():
    """[XE-1] unique_id encodes the expected fields."""
    ent = <Entity>(manager=_make_manager(), vacuum_entity_id=_VAC, ...)
    assert ent.unique_id == "expected"


async def test_press_calls_manager():
    """[XE-2] async_press delegates to the manager and saves."""
    manager = _make_manager()
    ent = <Entity>(manager=manager, vacuum_entity_id=_VAC, ...)
    await ent.async_press()
    manager.<method>.assert_called_once()
    manager.async_save.assert_awaited_once()
```

---

## Recipe C — Pure function (unit)

```python
"""Unit tests for <module> — pure-function helpers."""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.<module> import <func>


def test_happy_path():
    assert <func>("input") == "expected"


def test_edge_returns_none():
    assert <func>("") is None


@pytest.mark.parametrize("value,expected", [
    (0.90, "strong"),
    (0.50, "building"),
    (0.10, "low"),
])
def test_bands(value, expected):
    assert <func>(value) == expected
```

No `hass`, no fixtures — these run fast and have none of the shared-state
pitfalls. Prefer this layer whenever the thing under test is pure.

---

## Recipe D — Learning finalize (integration, the happy path)

The finalize pipeline has the most setup. This template gives a job real shape
so `used_for_learning` stays `True` (see
[05 §4](05-gotchas-and-pitfalls.md)).

```python
"""Phase N integration tests — learning finalize.

Coverage targets
----------------
[LF-1]  A completed, learning-eligible run records metrics.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.learning.services import (
    async_register_learning_services,
    async_unregister_learning_services,
    _get_learning_manager,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
async def learning_services(hass, manager):
    await async_register_learning_services(hass)
    yield manager
    await async_unregister_learning_services(hass)


def _seed_active_job(manager, vac, map_id, **extra):
    manager.data.setdefault("active_jobs", {}).setdefault(vac, {})[str(map_id)] = {
        "status": "started", "vacuum_entity_id": vac, "map_id": str(map_id), **extra,
    }


async def test_finalize_happy_path(hass, learning_services):
    """[LF-1] A completed run with a resolved room finalizes for learning."""
    _seed_active_job(learning_services, _VAC, _MAP, resolved_rooms=[
        {"room_id": 1, "slug": "kitchen", "name": "Kitchen",
         "clean_mode": "vacuum", "clean_intensity": "standard",
         "clean_times": 1, "is_carpet": False},
    ])

    core_manager = hass.data[DOMAIN]["runtime"]
    learning = _get_learning_manager(hass)

    result = await hass.async_add_executor_job(
        lambda: learning.finalize_completed_job(
            manager=core_manager,
            vacuum_entity_id=_VAC, map_id=_MAP,
            battery_start=85, battery_end=60,
            started_at="2026-01-01T09:00:00+00:00",
            ended_at="2026-01-01T09:30:00+00:00",
            used_for_learning=True, rebuild_stats=False,
        )
    )
    assert result["vacuum_entity_id"] == _VAC
```

---

## Recipe E — Adapter-config-dependent path

For code that reads adapter entities or vocabulary.

```python
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config


_TASK_STATUS = "sensor.alfred_task_status"


def _register_adapter(*, with_task_status=True, exclusions=None):
    register_adapter_config("vacuum.alfred", {
        "adapter_id": "test",
        "source": "test",
        "entities": {"task_status": _TASK_STATUS} if with_task_status else {},
        "vocabulary": {"cancel_service_exclusion_states": list(exclusions or [])},
    })


async def test_path_reads_adapter_entity(hass, manager):
    """The code under test resolves the task_status entity from the adapter."""
    _register_adapter()
    # ... call the method that reads get_adapter_config(...) ...
```

The `manager` fixture makes the registration active and isolated per test. Omit
a `mapping` block to skip segmenter validation.

---

## Recipe F — Service error-wrapping contract

For the `except Exception as err: raise HomeAssistantError(...)` wrappers in the
service layer (the HA Silver action-exception contract). Force the manager call
to raise, assert the wrapped type — don't test the happy path here.

```python
import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.eufy_vacuum.const import DOMAIN

_VAC = "vacuum.alfred"
_MAP = "1"


@pytest.mark.parametrize("service,method,data", [
    ("save_run_profile", "save_run_profile", {"name": "x"}),
    ("delete_run_profile", "delete_run_profile", {"profile_id": "p"}),
])
async def test_handler_wraps_manager_error(
    hass, manager_with_services, monkeypatch, service, method, data
):
    """[XX-N] a manager-layer failure surfaces as HomeAssistantError."""
    def _boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(manager_with_services, method, _boom)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, service,
            {"vacuum_entity_id": _VAC, "map_id": _MAP, **data},
            blocking=True, return_response=True)
```

For an `async_save` failure path, patch with an async stub instead:
`monkeypatch.setattr(mgr, "async_save", _async_boom)`.

---

## Recipe G — Delegation smoke (the #11/#13 net)

When a manager method is a thin forwarder (`return self.<subsystem>.x(...)`),
prove it still forwards — a delegation lost in a refactor while a caller still
uses it is a real bug class. Call each seam through the manager; the return value
is incidental, the point is that it doesn't `AttributeError`.

```python
def test_seams_forward(mgr):
    """[MD-N] manager seams forward to their subsystems."""
    assert isinstance(mgr.get_maintenance_state(vacuum_entity_id=_VAC), dict)
    mgr.pause_active_job(vacuum_entity_id=_VAC, map_id=_MAP)
    mgr.record_completed_room(vacuum_entity_id=_VAC, map_id=_MAP, room_id=1)
    # … one line per seam; a missing/misrouted forwarder raises here.
```

---

## Where to look when stuck

- An existing test in the same domain almost always has the seeding helper you
  need — grep `tests/` for the manager method or service name first.
- The data layout is in [05](05-gotchas-and-pitfalls.md); the fixtures are in
  [03](03-fixtures-and-helpers.md).
- If a test passes alone but fails in the full run, suspect shared `config_dir`
  accumulation ([05 §2](05-gotchas-and-pitfalls.md)).
