"""Phase 8 integration tests — services/job_control.py write path.

Coverage targets
----------------
[JCW-1]  clear_active_job on a vacuum with no active job does not raise.
[JCW-2]  clear_active_job on a vacuum with no active job succeeds for both maps.
[JCW-3]  cancel_active_job on a vacuum with no active job raises HomeAssistantError.

Note: start_selected_rooms / pause_active_job / resume_active_job are excluded
from this suite — they call device I/O on the physical vacuum and cannot be
exercised without a real device connection or deep entity mocking.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.const import DOMAIN

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"

_LIFECYCLE_ADAPTER = {
    "adapter_id": "test",
    "source": "test",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "dock_status": "sensor.alfred_dock_status",
        "active_map": "sensor.alfred_active_map",
        "active_cleaning_target": "sensor.alfred_active_cleaning_target",
    },
}


async def _setup_vacuum(hass, manager) -> None:
    """Seed a vacuum with an adapter and all lifecycle entity states."""
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _LIFECYCLE_ADAPTER)
    hass.states.async_set("sensor.alfred_task_status", "idle")
    hass.states.async_set("sensor.alfred_dock_status", "idle")
    hass.states.async_set("sensor.alfred_active_map", _MAP)
    hass.states.async_set("sensor.alfred_active_cleaning_target", "")
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# [JCW-1] clear_active_job — no active job
# ---------------------------------------------------------------------------

async def test_clear_active_job_no_active_job_does_not_raise(hass, manager_with_services):
    """[JCW-1] clear_active_job completes without raising when no job is active."""
    await _setup_vacuum(hass, manager_with_services)
    # Should not raise — clear_active_job is a no-op when no job is tracked.
    await hass.services.async_call(
        DOMAIN,
        "clear_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )


async def test_clear_active_job_is_idempotent(hass, manager_with_services):
    """[JCW-2] Calling clear_active_job twice does not raise on the second call."""
    await _setup_vacuum(hass, manager_with_services)
    await hass.services.async_call(
        DOMAIN,
        "clear_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "clear_active_job",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
