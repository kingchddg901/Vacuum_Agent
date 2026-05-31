"""Phase 6 integration tests — job control read-path service handlers.

Coverage targets
----------------
[JR-1]  get_active_job returns a dict when no active job exists.
[JR-2]  get_active_job result includes vacuum_entity_id.
[JR-3]  get_job_progress_snapshot returns a dict when map is set up.
[JR-4]  get_job_progress_snapshot returns a dict when no map exists.
[JR-5]  get_job_control_state returns a dict.
[JR-6]  get_job_control_state result includes vacuum_entity_id.
[JR-7]  get_lifecycle_state returns a dict.
[JR-8]  get_lifecycle_state result includes vacuum_entity_id.
[JR-9]  get_start_status returns a dict when no queue is built.
[JR-10] get_start_status returns a dict after a queue is built.

All five services use VACUUM_MAP_SCHEMA (vacuum_entity_id required, map_id
optional).  map_id is always passed explicitly to avoid entity I/O via the
resolved_call_data auto-resolve path.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"

_TASK_STATUS = "sensor.alfred_task_status"
_DOCK_STATUS = "sensor.alfred_dock_status"
_ACTIVE_MAP = "sensor.alfred_active_map"
_ACTIVE_TARGET = "sensor.alfred_active_cleaning_target"

# Minimal adapter providing all four lifecycle entity names that
# get_lifecycle_state reads via hass.states.get() — all keys must be
# present so the lookup never receives None as an entity_id.
_LIFECYCLE_ADAPTER = {
    "adapter_id": "test",
    "source": "test",
    "entities": {
        "task_status": _TASK_STATUS,
        "dock_status": _DOCK_STATUS,
        "active_map": _ACTIVE_MAP,
        "active_cleaning_target": _ACTIVE_TARGET,
    },
}


async def _setup_vacuum_with_adapter(hass, manager, *, count: int = 2) -> None:
    """Register vacuum, map, adapter, and all lifecycle entity states."""
    setup_map(manager, _VAC, _MAP, count=count)
    register_adapter_config(_VAC, _LIFECYCLE_ADAPTER)
    hass.states.async_set(_TASK_STATUS, "idle")
    hass.states.async_set(_DOCK_STATUS, "idle")
    hass.states.async_set(_ACTIVE_MAP, _MAP)
    hass.states.async_set(_ACTIVE_TARGET, "")
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [JR-1] — [JR-2] get_active_job
# ---------------------------------------------------------------------------

async def test_get_active_job_returns_dict_no_job(hass, manager_with_services):
    """[JR-1] get_active_job returns a dict even when no active job exists."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_active_job_includes_vacuum_entity_id(hass, manager_with_services):
    """[JR-2] get_active_job result includes vacuum_entity_id."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result.get("vacuum_entity_id") == _VAC


# ---------------------------------------------------------------------------
# [JR-3] — [JR-4] get_job_progress_snapshot
# ---------------------------------------------------------------------------

async def test_get_job_progress_snapshot_with_map(hass, manager_with_services):
    """[JR-3] get_job_progress_snapshot returns a dict when rooms are set up."""
    await _setup_vacuum_with_adapter(hass, manager_with_services, count=3)
    result = await hass.services.async_call(
        DOMAIN,
        "get_job_progress_snapshot",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_job_progress_snapshot_no_map(hass, manager_with_services):
    """[JR-4] get_job_progress_snapshot returns a dict when no map is set up."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _LIFECYCLE_ADAPTER)
    hass.states.async_set(_TASK_STATUS, "idle")
    hass.states.async_set(_DOCK_STATUS, "idle")
    hass.states.async_set(_ACTIVE_MAP, _MAP)
    hass.states.async_set(_ACTIVE_TARGET, "")
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        DOMAIN,
        "get_job_progress_snapshot",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [JR-5] — [JR-6] get_job_control_state
# ---------------------------------------------------------------------------

async def test_get_job_control_state_returns_dict(hass, manager_with_services):
    """[JR-5] get_job_control_state returns a dict."""
    await _setup_vacuum_with_adapter(hass, manager_with_services)
    result = await hass.services.async_call(
        DOMAIN,
        "get_job_control_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_job_control_state_includes_vacuum_entity_id(hass, manager_with_services):
    """[JR-6] get_job_control_state result includes vacuum_entity_id."""
    await _setup_vacuum_with_adapter(hass, manager_with_services)
    result = await hass.services.async_call(
        DOMAIN,
        "get_job_control_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result.get("vacuum_entity_id") == _VAC


# ---------------------------------------------------------------------------
# [JR-7] — [JR-8] get_lifecycle_state
# ---------------------------------------------------------------------------

async def test_get_lifecycle_state_returns_dict(hass, manager_with_services):
    """[JR-7] get_lifecycle_state returns a dict."""
    await _setup_vacuum_with_adapter(hass, manager_with_services)
    result = await hass.services.async_call(
        DOMAIN,
        "get_lifecycle_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_lifecycle_state_includes_vacuum_entity_id(hass, manager_with_services):
    """[JR-8] get_lifecycle_state result includes vacuum_entity_id."""
    await _setup_vacuum_with_adapter(hass, manager_with_services)
    result = await hass.services.async_call(
        DOMAIN,
        "get_lifecycle_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result.get("vacuum_entity_id") == _VAC


# ---------------------------------------------------------------------------
# [JR-9] — [JR-10] get_start_status
# ---------------------------------------------------------------------------

async def test_get_start_status_no_queue_returns_dict(hass, manager_with_services):
    """[JR-9] get_start_status returns a dict even when no queue has been built."""
    await _setup_vacuum_with_adapter(hass, manager_with_services)
    result = await hass.services.async_call(
        DOMAIN,
        "get_start_status",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


async def test_get_start_status_with_queue_returns_dict(hass, manager_with_services):
    """[JR-10] get_start_status returns a dict after a queue has been built."""
    await _setup_vacuum_with_adapter(hass, manager_with_services, count=3)
    manager_with_services.build_queue(vacuum_entity_id=_VAC, map_id=_MAP)
    result = await hass.services.async_call(
        DOMAIN,
        "get_start_status",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result
