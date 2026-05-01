"""Button platform for Eufy Vacuum Manager — maintenance reset and saved run profile buttons."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .core.capabilities import MAINTENANCE_COMPONENTS
from .entity_helpers import build_entity_name


def _slugify_profile_name(value: str) -> str:
    """Return a stable slug segment for a saved run profile."""
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    return text.strip("_") or "run_profile"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up maintenance reset buttons and exposed saved-run-profile buttons."""
    manager = hass.data[DOMAIN]["runtime"]
    entities: list[ButtonEntity] = []
    entity_map: dict[str, ButtonEntity] = {}

    vacuums = manager.data.get("vacuums", {})
    for vacuum_entity_id in vacuums:
        capabilities = manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})

        for component, meta in MAINTENANCE_COMPONENTS.items():
            if sources.get(component) is None:
                continue

            entity = EufyVacuumMaintenanceResetButton(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                component=component,
                label=meta["label"],
                icon=meta["icon"],
            )
            entities.append(entity)
            entity_map[entity.unique_id] = entity

    for entity in _build_run_profile_buttons(manager=manager):
        entities.append(entity)
        entity_map[entity.unique_id] = entity

    async_add_entities(entities)

    def _on_run_profiles_updated(*, vacuum_entity_id: str, map_id: str) -> None:
        """Sync dynamic saved-run-profile buttons after profile changes."""
        registry = er.async_get(hass)
        desired_entities = {
            entity.unique_id: entity
            for entity in _build_run_profile_buttons_for_map(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
        }

        prefix = _run_profile_button_unique_prefix(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        stale_ids = [
            unique_id
            for unique_id in list(entity_map.keys())
            if unique_id.startswith(prefix) and unique_id not in desired_entities
        ]

        for unique_id in stale_ids:
            existing = entity_map.pop(unique_id, None)
            if existing is not None:
                hass.async_create_task(existing.async_remove())

            entity_id = registry.async_get_entity_id("button", DOMAIN, unique_id)
            if entity_id:
                registry.async_remove(entity_id)

        new_entities: list[ButtonEntity] = []
        for unique_id, entity in desired_entities.items():
            existing = entity_map.get(unique_id)
            if existing is not None:
                existing.async_write_ha_state()
                continue
            entity_map[unique_id] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    manager.register_run_profile_update_callback(_on_run_profiles_updated)
    entry.async_on_unload(
        lambda: manager.unregister_run_profile_update_callback(
            _on_run_profiles_updated
        )
    )


def _build_run_profile_buttons(*, manager: Any) -> list[ButtonEntity]:
    """Build all exposed saved-run-profile buttons."""
    entities: list[ButtonEntity] = []
    maps = manager.data.get("maps", {})
    for vacuum_entity_id, vacuum_maps in maps.items():
        for map_id in vacuum_maps.keys():
            entities.extend(
                _build_run_profile_buttons_for_map(
                    manager=manager,
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                )
            )
    return entities


def _build_run_profile_buttons_for_map(
    *,
    manager: Any,
    vacuum_entity_id: str,
    map_id: str,
) -> list[ButtonEntity]:
    """Build exposed saved-run-profile buttons for one vacuum/map."""
    payload = manager.get_saved_run_profiles(
        vacuum_entity_id=vacuum_entity_id,
        map_id=str(map_id),
    )
    library = payload.get("library", {})
    if not isinstance(library, dict):
        return []

    entities: list[ButtonEntity] = []
    for profile_id, profile in library.items():
        if not isinstance(profile, dict):
            continue
        if not bool(profile.get("expose_as_button", False)):
            continue
        entities.append(
            EufyVacuumSavedRunProfileButton(
                manager=manager,
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                profile_id=str(profile_id),
            )
        )

    entities.sort(key=lambda entity: str(entity.name or "").lower())
    return entities


def _run_profile_button_unique_prefix(*, vacuum_entity_id: str, map_id: str) -> str:
    """Return the unique-id prefix shared by one vacuum/map's run buttons."""
    vacuum_key = vacuum_entity_id.replace(".", "_")
    return f"{vacuum_key}_{map_id}_run_profile_"


class EufyVacuumMaintenanceResetButton(ButtonEntity):
    """Button to reset the maintenance snapshot for one component."""

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
        component: str,
        label: str,
        icon: str,
    ) -> None:
        """Initialize reset button."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._component = component

        self._attr_name = build_entity_name(
            vacuum_entity_id,
            f"Reset {label} Maintenance",
        )
        self._attr_unique_id = (
            f"{vacuum_entity_id.replace('.', '_')}_{component}_maintenance_reset"
        )
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle button press and snapshot current usage hours."""
        self._manager.reset_maintenance(
            vacuum_entity_id=self._vacuum_entity_id,
            component=self._component,
        )
        await self._manager.async_save()


class EufyVacuumSavedRunProfileButton(ButtonEntity):
    """Button that starts one exposed saved run profile."""

    _attr_icon = "mdi:play-circle-outline"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        manager: Any,
        vacuum_entity_id: str,
        map_id: str,
        profile_id: str,
    ) -> None:
        """Initialize saved run profile button."""
        self._manager = manager
        self._vacuum_entity_id = vacuum_entity_id
        self._map_id = str(map_id)
        self._profile_id = str(profile_id)

    @property
    def _profile(self) -> dict[str, Any]:
        """Return the current saved profile data."""
        payload = self._manager.get_saved_run_profiles(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
        )
        library = payload.get("library", {})
        if not isinstance(library, dict):
            return {}
        profile = library.get(self._profile_id)
        return profile if isinstance(profile, dict) else {}

    @property
    def unique_id(self) -> str | None:
        """Return the stable unique id."""
        profile_name = str(self._profile.get("name", self._profile_id))
        return (
            f"{_run_profile_button_unique_prefix(vacuum_entity_id=self._vacuum_entity_id, map_id=self._map_id)}"
            f"{_slugify_profile_name(profile_name)}_{self._profile_id}"
        )

    @property
    def name(self) -> str | None:
        """Return the dynamic button name."""
        profile_name = str(self._profile.get("name", "Saved Run"))
        return build_entity_name(self._vacuum_entity_id, f"Run {profile_name}")

    @property
    def available(self) -> bool:
        """Return whether the button should be available."""
        profile = self._profile
        return bool(profile) and bool(profile.get("expose_as_button", False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return metadata that helps users inspect the saved run."""
        profile = self._profile
        return {
            "vacuum_entity_id": self._vacuum_entity_id,
            "map_id": self._map_id,
            "profile_id": self._profile_id,
            "profile_name": profile.get("name"),
            "room_count": profile.get("room_count"),
            "room_ids": profile.get("room_ids"),
            "room_names": profile.get("room_names"),
            "summary": profile.get("summary"),
            "expose_as_button": profile.get("expose_as_button", False),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
        }

    async def async_press(self) -> None:
        """Start the saved run profile using the standard protected start path."""
        self._manager.start_run_profile(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
            profile_id=self._profile_id,
        )
        await self._manager.async_save()
