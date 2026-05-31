"""Phase 3 integration fixtures — manager construction without async_setup_entry."""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import AdapterCoordinator
from custom_components.eufy_vacuum.const import DATA_ADAPTER_COORDINATOR, DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.core.manager import EufyVacuumManager


@pytest.fixture
async def manager(hass, mock_config_entry):
    """Fully initialized EufyVacuumManager with no entity states required.

    Constructs the manager directly (bypassing async_setup_entry) so tests
    can exercise manager logic without entity listeners, panels, or
    service registration.  The AdapterCoordinator is wired so the
    module-level adapter-registry shims resolve correctly.
    """
    hass.data.setdefault(DOMAIN, {})

    coordinator = AdapterCoordinator(hass, mock_config_entry)
    hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR] = coordinator

    m = EufyVacuumManager(hass)
    await m.async_initialize()
    hass.data[DOMAIN][DATA_RUNTIME] = m
    return m


# ---------------------------------------------------------------------------
# Data-seeding helpers (used by multiple test modules)
# ---------------------------------------------------------------------------

def seed_discovery(
    manager: EufyVacuumManager,
    vacuum_id: str,
    map_id: str,
    rooms: list[dict],
) -> None:
    """Pre-populate manager.data['discovery'] so save_managed_rooms can read it."""
    manager.data.setdefault("discovery", {})
    manager.data["discovery"].setdefault(vacuum_id, {})[str(map_id)] = {
        "active_map_id": str(map_id),
        "rooms": rooms,
    }


def make_rooms(map_id: str, count: int) -> list[dict]:
    """Return a list of minimal discovered-room dicts for the given map."""
    return [
        {"room_id": i, "map_id": str(map_id), "name": f"Room {i}"}
        for i in range(1, count + 1)
    ]


def setup_map(
    manager: EufyVacuumManager,
    vacuum_id: str,
    map_id: str,
    count: int = 3,
    enabled_room_ids: list[int] | None = None,
) -> dict:
    """Seed discovery and save managed rooms; return the save result."""
    rooms = make_rooms(map_id, count)
    seed_discovery(manager, vacuum_id, map_id, rooms)
    return manager.save_managed_rooms(
        vacuum_entity_id=vacuum_id,
        map_id=str(map_id),
        enabled_room_ids=enabled_room_ids,
    )
