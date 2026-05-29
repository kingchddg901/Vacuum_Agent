"""The Eufy Vacuum Manager integration.

This module is the HA entry point. It owns the four contract surface
functions HA expects (async_setup, async_setup_entry, async_unload_entry,
async_remove_entry) plus the per-entry orchestration in between —
manager construction, adapter coordinator wiring, platform forwarding,
panel registration, service registration, and listener
register/teardown.

Listener registration is delegated to per-domain modules under
``listeners/``. Each one exposes ``register(hass)`` and ``remove(hass)``
and owns its private constants. See ``listeners/__init__.py`` for the
list and ``listeners/_common.py`` for shared adapter-registry helpers
and the job-finished event payload builder.
"""

from __future__ import annotations

import logging
import os

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ._frontend_url import panel_js_url
from .const import (
    CONF_VACUUM_ENTITY_ID,
    DATA_BATTERY,
    DATA_ADAPTER_COORDINATOR,
    DATA_ERROR_TRACKER,
    DATA_LEARNING,
    DATA_RUNTIME,
    DOMAIN,
)
from .adapters.registry import (
    AdapterCoordinator,
    unregister_adapter_config,
)
from .adapters.eufy.adapter import register_eufy_adapter_for_vacuum
from .adapters.config_loader import load_stored_adapter_configs
from .battery.manager import BatteryHealthManager
from .core.error_tracker import ErrorTracker
from .core.manager import EufyVacuumManager
from .learning.manager import LearningManager
from .learning.services import (
    async_register_learning_services,
    async_unregister_learning_services,
)
from .listeners import (
    discovery,
    dock_events,
    job_metrics,
    job_progress,
    lifecycle,
    path_blockers,
    pause_timeout,
)
from .mapping.mapping_services import (
    async_register_mapping_services,
    async_unregister_mapping_services,
)
from .mapping.manager import MappingManager
from .mapping.tracker import MappingTracker
from .services import async_register_services, async_unregister_services
from .theme_services import (
    async_register_theme_services,
    async_unregister_theme_services,
)

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[str] = [
    "binary_sensor",
    "button",
    "switch",
    "number",
    "sensor",
]


# ----------------------------------------------------------------------
# Domain setup
# ----------------------------------------------------------------------


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    hass.data.setdefault(DOMAIN, {})

    maps_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "maps")
    os.makedirs(maps_dir, exist_ok=True)

    # Floor textures ship with the integration so HACS delivers them on
    # every install. Previously this pointed at <config>/eufy_vacuum/textures
    # which only ever existed on the developer's machine — every other
    # install 404'd silently. cache_headers=True because these are
    # versioned, non-changing static assets (~18 MB total).
    textures_dir = os.path.join(os.path.dirname(__file__), "textures")

    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    os.makedirs(frontend_dir, exist_ok=True)

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig("/eufy_vacuum/maps", maps_dir, cache_headers=False),
            StaticPathConfig("/eufy_vacuum/textures", textures_dir, cache_headers=True),
            StaticPathConfig("/eufy_vacuum/frontend", frontend_dir, cache_headers=False),
        ]
    )

    return True


# ----------------------------------------------------------------------
# Config entry lifecycle
# ----------------------------------------------------------------------


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eufy Vacuum Manager from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # AdapterCoordinator owns the per-entry adapter registry. Constructing
    # it sets it as the module-level active coordinator so legacy
    # bare-function lookups in adapters/registry.py route through it.
    # Must be constructed BEFORE any adapter registration so the stored
    # adapters and code adapters land in the coordinator's registry, not
    # the fallback module-level dict.
    coordinator = AdapterCoordinator(hass, entry)
    hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR] = coordinator

    manager = EufyVacuumManager(hass)
    await manager.async_initialize()

    # If the config entry carries a vacuum_entity_id (collected by the
    # config flow or set later via options), make sure it shows up as a
    # managed vacuum so panel registration can find it. Options override
    # data so users can change their pick via Configure.
    configured_vacuum = entry.options.get(
        CONF_VACUUM_ENTITY_ID,
        entry.data.get(CONF_VACUUM_ENTITY_ID),
    )
    if configured_vacuum:
        try:
            manager.ensure_vacuum_record(vacuum_entity_id=configured_vacuum)
            _LOGGER.debug(
                "eufy_vacuum: ensured managed-vacuum record for %s from config entry",
                configured_vacuum,
            )
        except Exception:
            _LOGGER.exception(
                "eufy_vacuum: failed to register config-entry vacuum %s",
                configured_vacuum,
            )

    # Reload the entry whenever options change so a new vacuum_entity_id
    # (or notes update) takes effect without a full HA restart.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # One-time cleanup: remove orphaned icon-select entities from earlier
    # versions. The "select" platform was dropped (the card stopped surfacing
    # those pickers), and without removing the registry entries HA would show
    # them as "unavailable" forever. Match by unique_id prefix the deleted
    # EufyVacuumIconSelect class used.
    try:
        from homeassistant.helpers import entity_registry as _er
        registry = _er.async_get(hass)
        _orphans = [
            entry_id
            for entry_id, ent in registry.entities.items()
            if ent.platform == DOMAIN and (ent.unique_id or "").startswith("eufy_vacuum_icon_")
        ]
        for _entry_id in _orphans:
            registry.async_remove(_entry_id)
        if _orphans:
            _LOGGER.info(
                "eufy_vacuum: removed %d orphaned icon-select entit%s from earlier versions",
                len(_orphans),
                "y" if len(_orphans) == 1 else "ies",
            )
    except Exception:
        _LOGGER.debug("eufy_vacuum: icon-select cleanup pass failed", exc_info=True)

    # Load stored adapter configs (UI-configured brands) before code
    # adapter registration. Code adapters registered below will overwrite
    # stored configs for the same vacuum — code adapters always win.
    _stored_count = load_stored_adapter_configs(hass, manager.data)
    if _stored_count > 0:
        _LOGGER.debug(
            "eufy_vacuum: loaded %d stored adapter config(s)",
            _stored_count,
        )

    # Register Eufy code adapter for each managed vacuum.
    # This overwrites any stored config for the same vacuum.
    for _vacuum_entity_id in manager.get_known_vacuum_ids():
        try:
            register_eufy_adapter_for_vacuum(hass, _vacuum_entity_id)
        except Exception:
            _LOGGER.exception(
                "eufy_vacuum: failed to register adapter config for %s",
                _vacuum_entity_id,
            )

    hass.data[DOMAIN][DATA_RUNTIME] = manager
    hass.data[DOMAIN][DATA_LEARNING] = LearningManager(hass)

    battery_manager = BatteryHealthManager(hass, runtime_manager=manager)
    battery_manager.start(manager.get_known_vacuum_ids())
    hass.data[DOMAIN][DATA_BATTERY] = battery_manager

    # Active-run error tracker. Wires state-change listeners on each
    # vacuum's error_message + vacuum entity, latches errors, persists
    # them across restarts. The two error sensors and the
    # active_run_has_error binary sensor read from this tracker.
    error_tracker = ErrorTracker(hass, runtime_manager=manager)
    error_tracker.start(manager.get_known_vacuum_ids())
    hass.data[DOMAIN][DATA_ERROR_TRACKER] = error_tracker

    async def _handle_rebaseline(call: ServiceCall) -> None:
        vacuum_entity_id = call.data["vacuum_entity_id"]
        bm = hass.data.get(DOMAIN, {}).get(DATA_BATTERY)
        if bm is None:
            _LOGGER.warning(
                "battery: rebaseline service called but battery manager is not loaded"
            )
            return
        ok = bm.rebaseline(vacuum_entity_id)
        if not ok:
            _LOGGER.warning(
                "battery: rebaseline service called for %s but no record was found",
                vacuum_entity_id,
            )

    hass.services.async_register(
        DOMAIN,
        "battery_rebaseline",
        _handle_rebaseline,
        schema=vol.Schema({vol.Required("vacuum_entity_id"): cv.entity_id}),
    )

    mapping_manager = MappingManager(hass)
    mapping_tracker = MappingTracker(hass, mapping_manager)
    hass.data[DOMAIN]["mapping_manager"] = mapping_manager
    hass.data[DOMAIN]["mapping_tracker"] = mapping_tracker
    for _vac in manager.get_known_vacuum_ids():
        try:
            _caps = manager.get_vacuum_capabilities(vacuum_entity_id=_vac, refresh=False)
            _x_entity = _caps.get("entities", {}).get("robot_position_x")
            _y_entity = _caps.get("entities", {}).get("robot_position_y")
            if _x_entity and _y_entity:
                mapping_tracker.register_vacuum(
                    vacuum_entity_id=_vac,
                    position_x_entity_id=_x_entity,
                    position_y_entity_id=_y_entity,
                )
        except Exception:
            pass

    await async_register_services(hass)
    await async_register_learning_services(hass)
    await async_register_theme_services(hass)
    await async_register_mapping_services(hass)

    # Listener registration — each module owns its own state/constants
    # and exposes register(hass)/remove(hass). See listeners/ for the
    # per-group implementations.
    lifecycle.register(hass)
    job_metrics.register(hass)
    dock_events.register(hass)
    path_blockers.register(hass)
    pause_timeout.register(hass)
    job_progress.register(hass)
    discovery.register(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register one sidebar panel per managed vacuum.
    registered_panels: list[str] = []
    for vacuum_entity_id in manager.get_known_vacuum_ids():
        object_id = vacuum_entity_id.split(".", 1)[-1]
        panel_url = f"eufy-vacuum-{object_id}"
        try:
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path=panel_url,
                webcomponent_name="eufy-vacuum-command-center",
                js_url=panel_js_url(),
                sidebar_title="Eufy Vacuum",
                sidebar_icon="mdi:robot-vacuum",
                config={"vacuum_entity_id": vacuum_entity_id},
                require_admin=False,
                embed_iframe=False,
            )
            registered_panels.append(panel_url)
            _LOGGER.debug("eufy_vacuum: registered panel /%s for %s", panel_url, vacuum_entity_id)
        except ValueError:
            _LOGGER.debug("eufy_vacuum: panel /%s already registered", panel_url)

    # Fallback panel for fresh installs that haven't pointed at a vacuum
    # yet. Without this, users see no sidebar entry at all and have no
    # in-UI affordance to add their vacuum. The card detects an empty
    # `vacuum_entity_id` config and renders a setup placeholder that
    # points back at Settings → Devices & Services → Configure.
    if not registered_panels:
        fallback_panel_url = "eufy-vacuum"
        try:
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path=fallback_panel_url,
                webcomponent_name="eufy-vacuum-command-center",
                js_url=panel_js_url(),
                sidebar_title="Eufy Vacuum",
                sidebar_icon="mdi:robot-vacuum",
                config={},  # no vacuum_entity_id — card renders setup placeholder
                require_admin=False,
                embed_iframe=False,
            )
            registered_panels.append(fallback_panel_url)
            _LOGGER.debug(
                "eufy_vacuum: no managed vacuums yet — registered fallback /%s panel",
                fallback_panel_url,
            )
        except ValueError:
            _LOGGER.debug("eufy_vacuum: fallback panel /%s already registered", fallback_panel_url)

    hass.data[DOMAIN][f"_panels_{entry.entry_id}"] = registered_panels

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change.

    Triggered by adding/changing the vacuum_entity_id via Configure → Options.
    The reload re-runs async_setup_entry, which adds the new vacuum to the
    manager and registers the per-vacuum panel (and removes the fallback).
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        for panel_url in domain_data.pop(f"_panels_{entry.entry_id}", []):
            # panel_custom doesn't expose an unregister API; the panel is
            # registered into HA's frontend component, which is where the
            # remove helper lives.
            try:
                frontend.async_remove_panel(hass, panel_url)
            except Exception:  # pragma: no cover - defensive
                _LOGGER.debug("eufy_vacuum: failed to remove panel /%s", panel_url, exc_info=True)

        lifecycle.remove(hass)
        job_metrics.remove(hass)
        dock_events.remove(hass)
        path_blockers.remove(hass)
        pause_timeout.remove(hass)
        job_progress.remove(hass)
        discovery.remove(hass)

        await async_unregister_mapping_services(hass)
        await async_unregister_learning_services(hass)
        await async_unregister_theme_services(hass)
        await async_unregister_services(hass)

        domain_data = hass.data.get(DOMAIN, {})
        mapping_tracker = domain_data.pop("mapping_tracker", None)
        if mapping_tracker is not None:
            mapping_tracker.unregister_all()
        domain_data.pop("mapping_manager", None)
        battery_manager = domain_data.pop(DATA_BATTERY, None)
        if battery_manager is not None:
            try:
                battery_manager.stop()
            except Exception:  # pragma: no cover
                _LOGGER.exception("Failed to stop battery health manager")
        error_tracker = domain_data.pop(DATA_ERROR_TRACKER, None)
        if error_tracker is not None:
            try:
                error_tracker.stop()
            except Exception:  # pragma: no cover
                _LOGGER.exception("Failed to stop error tracker")
        # Unregister adapter configs on unload. Wrapped in try/finally so
        # the coordinator shutdown ALWAYS runs even if individual
        # unregister calls raise — otherwise stale module-level pointer
        # state could leak into the next setup_entry.
        try:
            _runtime_manager = domain_data.get(DATA_RUNTIME)
            if _runtime_manager is not None:
                for _vacuum_entity_id in list(_runtime_manager.get_known_vacuum_ids()):
                    try:
                        unregister_adapter_config(_vacuum_entity_id)
                    except Exception:  # pragma: no cover — defensive
                        _LOGGER.exception(
                            "Failed to unregister adapter config for %s",
                            _vacuum_entity_id,
                        )
        finally:
            # Coordinator shutdown clears the registry and detaches the
            # module-level active pointer. Drop the slot from hass.data.
            coordinator = domain_data.pop(DATA_ADAPTER_COORDINATOR, None)
            if coordinator is not None:
                try:
                    coordinator.shutdown()
                except Exception:  # pragma: no cover — defensive
                    _LOGGER.exception("Failed to shut down AdapterCoordinator")

        domain_data.pop(DATA_RUNTIME, None)
        domain_data.pop(DATA_LEARNING, None)

        if not domain_data:
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear persistent storage when the entry is deleted."""
    from homeassistant.helpers.storage import Store

    from .core.storage import STORAGE_KEY, STORAGE_VERSION

    store = Store[dict](hass, STORAGE_VERSION, STORAGE_KEY)
    await store.async_remove()
    _LOGGER.debug("eufy_vacuum: storage cleared on entry removal")
