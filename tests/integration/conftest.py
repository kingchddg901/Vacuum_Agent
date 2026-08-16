"""Phase 3 + Phase 4 integration fixtures — manager and service test support."""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.eufy.room_profiles import (
    BUILT_IN_ROOM_PROFILES,
    DEFAULT_CUSTOM_ROOM_PROFILE,
    DEFAULT_ROOM_PROFILE_NAME,
    FLOOR_TYPE_FAN_DEFAULTS,
    FLOOR_TYPE_WATER_DEFAULTS,
    LEGACY_PROFILE_ALIASES,
)
from custom_components.eufy_vacuum.adapters.registry import (
    AdapterCoordinator,
    register_adapter_config,
)
from custom_components.eufy_vacuum.const import DATA_ADAPTER_COORDINATOR, DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

#: The adapter these fixtures have always implicitly run against.
#:
#: Until 2026-08-07 this fixture registered NO adapter, and room resolution fell back
#: to a framework catalog that was Eufy's. So every test here was already asserting
#: Eufy vocabulary ("Max", "Quick", "vacuum_quick") — it simply never had to say so,
#: and no test could have caught a missing declaration because the fixture agreed with
#: the fallback that hid it. Declaring it changes no expectation; it states the one
#: that was always there.
#:
#: Sourced from the Eufy adapter's own constants rather than copied, so this cannot
#: drift from what the brand actually declares. Tests that should be brand-agnostic
#: build their own synthetic catalog instead (see tests/unit/test_profile_catalog.py).
TEST_ADAPTER_CONFIG = {
    "adapter_id": "test_eufy",
    "source": "code",
    "room_profiles": {
        "default_profile": DEFAULT_ROOM_PROFILE_NAME,
        "builtins": BUILT_IN_ROOM_PROFILES,
        "custom_template": DEFAULT_CUSTOM_ROOM_PROFILE,
        "legacy_aliases": LEGACY_PROFILE_ALIASES,
        "floor_type_water_defaults": FLOOR_TYPE_WATER_DEFAULTS,
        "floor_type_fan_defaults": FLOOR_TYPE_FAN_DEFAULTS,
        "normalize_defaults": DEFAULT_CUSTOM_ROOM_PROFILE,
    },
    "vocabulary": {
        "clean_mode_options": [
            {"value": "vacuum", "label": "Vacuum"},
            {"value": "mop", "label": "Mop"},
            {"value": "vacuum_mop", "label": "Vacuum & Mop"},
        ],
        "fan_speed_options": [
            {"value": "Quiet", "label": "Quiet"},
            {"value": "Standard", "label": "Standard"},
            {"value": "Turbo", "label": "Turbo"},
            {"value": "Max", "label": "Max"},
        ],
        "water_level_options": [
            {"value": "Off", "label": "Off"},
            {"value": "Low", "label": "Low"},
            {"value": "Medium", "label": "Medium"},
            {"value": "High", "label": "High"},
        ],
        "clean_intensity_options": [
            {"value": "Quick", "label": "Quick"},
            {"value": "Narrow", "label": "Narrow"},
            {"value": "Deep", "label": "Deep"},
        ],
    },
}


def register_eufy_vacuum_entity(hass, object_id: str = "alfred") -> str:
    """Put the vacuum in the entity registry as a REAL Eufy install has it.

    A real Eufy vacuum entity is created by the `robovac_mqtt` integration and therefore
    carries that `platform`. Tests that drive `async_setup_entry` need this now: brand
    resolution matches on platform, and an entity with no registry entry has none, so it
    resolves as UNSUPPORTED and gets no adapter.

    That used to be invisible — resolution ended at a Eufy default arm, so an
    unregistered fixture vacuum was indistinguishable from a real one. NOT autouse: tests
    that build their own registry entries (test_core_capabilities) must not have a second
    `vacuum.alfred` created underneath them, which silently renames theirs to
    `vacuum.alfred_2`.
    """
    from homeassistant.helpers import entity_registry as er

    return er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", f"{object_id}_unique_id",
        suggested_object_id=object_id,
    ).entity_id


@pytest.fixture
async def manager(hass, mock_config_entry):
    """Fully initialized EufyVacuumManager with no entity states required.

    Constructs the manager directly (bypassing async_setup_entry) so tests
    can exercise manager logic without entity listeners, panels, or
    service registration.  The AdapterCoordinator is wired so the
    module-level adapter-registry shims resolve correctly, and an adapter is
    REGISTERED — core carries no profile catalog of its own, so a manager with
    no adapter can resolve no rooms.
    """
    hass.data.setdefault(DOMAIN, {})

    coordinator = AdapterCoordinator(hass, mock_config_entry)
    hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR] = coordinator
    register_adapter_config("vacuum.alfred", dict(TEST_ADAPTER_CONFIG))

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


@pytest.fixture
async def manager_with_services(hass, manager):
    """Manager with all domain services registered.

    Registers via async_register_services (same path as async_setup_entry)
    and unregisters on teardown.  The ``manager`` fixture has already wired
    hass.data[DOMAIN][DATA_RUNTIME], so service handlers can locate the
    manager immediately.
    """
    from custom_components.eufy_vacuum.services import (
        async_register_services,
        async_unregister_services,
    )

    await async_register_services(hass)
    yield manager
    await async_unregister_services(hass)
