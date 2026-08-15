"""The Vacuum Agent integration.

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

import asyncio
import functools
import json
import logging
import os
from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_started

from ._frontend_url import cards_module_url, panel_js_url
from .user_fonts import build_catalog
from .panels import (
    DEFAULT_PANEL_TITLE,
    PANEL_ICON,
    WEBCOMPONENT_NAME,
    async_register_vacuum_panel,
    effective_panel_title,
    panel_url_for,
)
from .const import (
    CONF_VACUUM_ENTITY_ID,
    DATA_BATTERY,
    DATA_ADAPTER_COORDINATOR,
    DATA_ERROR_TRACKER,
    DATA_LEARNING,
    DATA_RUNTIME,
    DOMAIN,
    ENTITY_OVERRIDES_KEY,
)
from .adapters.registry import (
    AdapterCoordinator,
    unregister_adapter_config,
)
from .adapters.brands import register_brand_adapter
from .adapters.config_loader import load_stored_adapter_configs
from .adapters.registry import get_adapter_config
from .core.vacuum_identity import sweep_orphaned_vacuums
from .core.pause_timeout_migration import migrate_pause_timeout_defaults
from .rooms.vocabulary_migration import migrate_room_vocabulary
from .battery.manager import BatteryHealthManager
from .core.error_tracker import ErrorTracker
from .core.manager import EufyVacuumManager
from .learning.history_store import LearningHistoryStore
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
    pose_sampler,
    stall_capture,
)
from .mapping.mapping_services import (
    async_register_mapping_services,
    async_unregister_mapping_services,
)
from .mapping.tracker import MappingTracker
from .services import async_register_services, async_unregister_services
from .themes import (
    async_register_theme_services,
    async_unregister_theme_services,
)

_LOGGER = logging.getLogger(__name__)

# Config-entry-only integration — there is no YAML configuration for the domain
# (everything is set up via the config/options flow). Declaring this satisfies
# hassfest's CONFIG_SCHEMA requirement for integrations that implement async_setup.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# battery_rebaseline's call schema. A module-level CONSTANT, not the inline
# vol.Schema({...}) literal it used to be, because tests/unit/
# test_service_declaration_parity.py can only field-check a schema it can resolve
# by name — an inline literal made this the ONE documented service its
# services.yaml-vs-schema parity assertion had to skip, and a services.yaml field
# the schema rejects then lived in that skip for twelve days.
_BATTERY_REBASELINE_SCHEMA = vol.Schema({vol.Required("vacuum_entity_id"): cv.entity_id})


PLATFORMS: list[str] = [
    "binary_sensor",
    "button",
    "switch",
    "select",
    "number",
    "sensor",
]


# ----------------------------------------------------------------------
# Domain setup
# ----------------------------------------------------------------------


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    hass.data.setdefault(DOMAIN, {})

    integration_dir = os.path.dirname(__file__)

    def _prepare_static_dirs() -> tuple[str, str, str, str]:
        """Create the served directories and regenerate the auto-indexes.

        All filesystem work (makedirs / listdir / open) lives here so it runs in
        the executor — never on the event loop.

        Floor textures ship with the integration so HACS delivers them on every
        install (cache_headers=True; versioned, non-changing ~18 MB assets). The
        animal index and the drop-in locale index are auto-generated so the
        frontend can load every file without editing — dropping a .js into
        animals/ (or a <code>.json into config/eufy_vacuum/locales/) and
        restarting is enough.
        """
        maps_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "maps")
        os.makedirs(maps_dir, exist_ok=True)

        # Drop-in locales: user-supplied translation JSON in
        # config/eufy_vacuum/locales/ (persistent across HACS updates, like
        # maps). Auto-index the "<code>.json" files so the card can discover +
        # load each at runtime — drop a file and restart. index.json is excluded.
        locales_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "locales")
        os.makedirs(locales_dir, exist_ok=True)
        # Auto-index real .json files only — never index.json, never a symlink.
        # The dir is served statically (like HA's /local/), so an authenticated
        # user can read whatever they place here; keeping the index limited to
        # regular locale files means a stray symlink is never advertised or
        # auto-loaded by the card. (Document: locale JSON only belongs here.)
        locale_files = sorted(
            f
            for f in os.listdir(locales_dir)
            if f.endswith(".json")
            and f != "index.json"
            and os.path.isfile(os.path.join(locales_dir, f))
            and not os.path.islink(os.path.join(locales_dir, f))
        )
        with open(
            os.path.join(locales_dir, "index.json"), "w", encoding="utf-8"
        ) as fh:
            json.dump(locale_files, fh)

        frontend_dir = os.path.join(integration_dir, "frontend")
        os.makedirs(frontend_dir, exist_ok=True)

        animals_dir = os.path.join(frontend_dir, "animal-svg", "animals")
        if os.path.isdir(animals_dir):
            animal_files = sorted(
                f for f in os.listdir(animals_dir) if f.endswith(".js")
            )
            with open(
                os.path.join(animals_dir, "index.json"), "w", encoding="utf-8"
            ) as fh:
                json.dump(animal_files, fh)

        # SHIPPED locales (de/fr/es/nl/it/pt/ru) — ripped out of the minified
        # card bundle, they ship as nested JSON here and load at runtime. Auto-
        # index them (same as animals) so the card discovers each without an
        # edit; served via the existing /eufy_vacuum/frontend static path.
        shipped_locales_dir = os.path.join(frontend_dir, "locales")
        if os.path.isdir(shipped_locales_dir):
            shipped_locale_files = sorted(
                f
                for f in os.listdir(shipped_locales_dir)
                if f.endswith(".json") and f != "index.json"
            )
            with open(
                os.path.join(shipped_locales_dir, "index.json"), "w", encoding="utf-8"
            ) as fh:
                json.dump(shipped_locale_files, fh)

        # Drop-in fonts: user-supplied typefaces in config/eufy_vacuum/fonts/
        # (persistent across HACS updates) — one SUBDIRECTORY per font holding
        # font.json + its woff2 files + its licence. build_catalog() validates
        # each descriptor, parses each face's cmap (fontTools), derives which
        # locales the font PROVABLY covers (against the shipped locale
        # catalogues above + the English reference), and writes catalog.json —
        # the canonical font-library response the card consumes. The card
        # never trusts a descriptor's claims and never render-verifies in the
        # browser (rendered-text checks lie through per-glyph fallback): the
        # font file is the evidence. Runs AFTER the shipped-locales index so
        # the requirements it verifies against are current.
        user_fonts_dir = os.path.join(hass.config.config_dir, "eufy_vacuum", "fonts")
        os.makedirs(user_fonts_dir, exist_ok=True)
        build_catalog(user_fonts_dir, shipped_locales_dir)

        return (
            maps_dir,
            os.path.join(integration_dir, "textures"),
            frontend_dir,
            locales_dir,
            user_fonts_dir,
        )

    maps_dir, textures_dir, frontend_dir, locales_dir, user_fonts_dir = (
        await hass.async_add_executor_job(_prepare_static_dirs)
    )
    fonts_dir = os.path.join(frontend_dir, "fonts")

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig("/eufy_vacuum/maps", maps_dir, cache_headers=False),
            StaticPathConfig("/eufy_vacuum/textures", textures_dir, cache_headers=True),
            StaticPathConfig("/eufy_vacuum/frontend", frontend_dir, cache_headers=False),
            # Fonts get their OWN path purely for cache_headers=True. The bundle
            # path deliberately disables caching so a redeploy is picked up without
            # a hard refresh; a woff2 never changes between releases and must not
            # be re-fetched on every page load. Same directory tree, shipped in the
            # same HACS package — this is not an external asset.
            StaticPathConfig("/eufy_vacuum/fonts", fonts_dir, cache_headers=True),
            # User drop-in fonts: cache OFF like the other drop-in dirs — a
            # user iterating on a descriptor must see the edit on refresh; the
            # woff2 files ride heuristic caching, which is acceptable churn for
            # a user-supplied asset that can change under the same name.
            StaticPathConfig("/eufy_vacuum/user_fonts", user_fonts_dir, cache_headers=False),
            StaticPathConfig("/eufy_vacuum/locales", locales_dir, cache_headers=False),
        ]
    )

    # Register the standalone cards bundle as a GLOBAL frontend module, so the
    # room-card and the dashboard card are defined on every HA page — including a
    # cold dashboard that never opens the sidebar panel (a wall tablet, a hard
    # refresh). add_extra_js_url with es5=False registers an ES module
    # (DATA_EXTRA_MODULE_URL -> <script type="module">), which is the bundle's
    # format. Two guards: the bundle must exist (an older deploy skips it rather
    # than advertise a 404), and the frontend component must be set up (it's an
    # after_dependency — present in real HA, absent in headless/test contexts, so
    # we skip cleanly there). The full panel bundle also defines these cards; the
    # frontend defineCard guard makes the double-registration a no-op.
    cards_url = cards_module_url()
    if cards_url and frontend.DATA_EXTRA_MODULE_URL in hass.data:
        frontend.add_extra_js_url(hass, cards_url)

    return True


# ----------------------------------------------------------------------
# Config entry lifecycle
# ----------------------------------------------------------------------


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vacuum Agent from a config entry."""
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
    # RP-003/INIT-1: registered BEFORE async_initialize so a mid-setup failure
    # after construction still tears down (async_shutdown is idempotent — a
    # never-initialized manager has empty ledgers and cancels nothing).
    entry.async_on_unload(manager.async_shutdown)
    try:
        await manager.async_initialize()
    except Exception as exc:
        raise ConfigEntryNotReady(
            f"eufy_vacuum: failed to initialise storage — will retry"
        ) from exc

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
            _LOGGER.exception(  # pragma: no cover
                "eufy_vacuum: failed to register config-entry vacuum %s",
                configured_vacuum,
            )

    # Reload the entry whenever options change so a new vacuum_entity_id
    # (or notes update) takes effect without a full HA restart.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # One-time cleanup: remove orphaned icon-select entities from earlier
    # versions. The per-room icon-select ENTITIES were dropped (the card stopped
    # surfacing those pickers) — the "select" platform itself is still live (now
    # the debug flight-recorder target select). Without removing the registry
    # entries HA would show them as "unavailable" forever. Match by the unique_id
    # prefix the deleted EufyVacuumIconSelect class used.
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
            _LOGGER.info(  # pragma: no cover
                "eufy_vacuum: removed %d orphaned icon-select entit%s from earlier versions",
                len(_orphans),
                "y" if len(_orphans) == 1 else "ies",
            )
    except Exception:
        _LOGGER.debug("eufy_vacuum: icon-select cleanup pass failed", exc_info=True)

    # RP-039/RF-16: everything from here to `return True` registers a resource
    # that must be undone if a LATER step in this same setup fails. The only
    # existing safety net for this stretch is manager.async_shutdown (ledgered
    # above via entry.async_on_unload — HA itself calls every entry.async_on_unload
    # callback, in LIFO order, when async_setup_entry raises; see
    # ConfigEntry.__async_setup_with_context's finally block); nothing else here
    # was covered.
    #
    # _unwind_stack is a LOCAL, mid-setup-only ledger — deliberately NOT
    # entry.async_on_unload for these steps. That ledger fires again on every
    # NORMAL unload too (via ConfigEntry.async_unload's own finally), which
    # already has its own explicit, hand-ordered teardown below in
    # async_unload_entry; joining the same undo actions to entry.async_on_unload
    # as well would run each one twice per real unload. Each undo is pushed
    # BEFORE the step that could partially fail (not after) — a step that starts
    # a loop (register_vacuum per vacuum, panel registration per vacuum) reads
    # the SAME mutable object the step itself is populating, so it is undone
    # correctly however far that step actually got before raising. Walked in
    # reverse (LIFO, same discipline as HA's own on_unload processing) on any
    # exception, then the exception is re-raised untouched.
    _unwind_stack: list[Callable[[], Any]] = []

    try:
        # Load stored adapter configs (UI-configured brands) before code
        # adapter registration. Code adapters registered below will overwrite
        # stored configs for the same vacuum — code adapters always win.
        _stored_count = load_stored_adapter_configs(hass, manager.data)
        if _stored_count > 0:
            _LOGGER.debug(  # pragma: no cover
                "eufy_vacuum: loaded %d stored adapter config(s)",
                _stored_count,
            )

        # Register the brand code adapter for each managed vacuum. This overwrites any
        # stored config for the same vacuum. Which brand runs is decided by the registrar
        # table in adapters/brands.py — an explicit per-vacuum override, else positive
        # detection, else the declared default arm. Adding a brand is a row in that table,
        # not an edit here. (No unwind: this writes into the AdapterCoordinator
        # constructed just above async_initialize, outside this stretch — a failed
        # attempt's coordinator is simply replaced by a fresh one on the next
        # attempt, never referenced again.)
        # live:ENT-7 — TWO SURFACES WRITE ONE CONTRACT, so merge them here.
        #
        # The panel's Setup tab writes entity overrides into the manager's own
        # data; the options flow can only write config-entry OPTIONS, because a
        # flow has no business mutating runtime state. Reading only one of those
        # would silently ignore whichever surface the user happened to use.
        #
        # Entry options WIN: the options flow is the guaranteed-reachable rescue
        # path, the one still available when the frontend is not, so a choice
        # made there must not be overruled by a stale panel value.
        _brand_data = manager.data
        _entry_overrides = entry.options.get(ENTITY_OVERRIDES_KEY)
        if isinstance(_entry_overrides, dict) and _entry_overrides:
            _brand_data = {
                **manager.data,
                ENTITY_OVERRIDES_KEY: {
                    **(manager.data.get(ENTITY_OVERRIDES_KEY) or {}),
                    **_entry_overrides,
                },
            }

        for _vacuum_entity_id in manager.get_known_vacuum_ids():
            try:
                register_brand_adapter(hass, _vacuum_entity_id, data=_brand_data)
            except Exception:
                _LOGGER.exception(  # pragma: no cover
                    "eufy_vacuum: failed to register adapter config for %s",
                    _vacuum_entity_id,
                )

        # One-shot repair of rooms written under the framework's former Eufy default
        # (see rooms/vocabulary_migration.py). Rooms are only rewritten when edited, so
        # without this an untouched room keeps a value its device cannot accept
        # indefinitely — the fallback removal alone stops new ones, it cannot heal old
        # ones. Failure here must never block setup; an unrepaired room behaves exactly
        # as it did before.
        #
        # DEFERRED TO HA-STARTED, not run inline here. The rules are driven entirely by
        # what each brand DECLARES, and adapters are registered from vacuum entities
        # owned by OTHER integrations. Running at raw setup time only works if those
        # happened to set up first: on a cold boot they often have not, every vacuum is
        # skipped for want of a declaration, and the repair does nothing. Waiting is not
        # available to us — HA gives no "after that integration" hook — but this is the
        # primitive it gives instead. async_at_started fires once everything has set up,
        # and fires IMMEDIATELY when HA is already running, so a live config-entry
        # reload still repairs promptly. Exactly the reasoning and primitive the
        # discovery listener already uses for its reload pass, where get_maps is not yet
        # registered at setup time; this call site was its forgotten sibling.
        #
        # The migration's own latch is the second half: a run that cannot evaluate every
        # target no longer records itself as done, so a deferral is retried rather than
        # silently consumed.
        @callback
        def _schedule_vocabulary_migration(_hass: HomeAssistant) -> None:
            async def _do() -> None:
                try:
                    _migration = migrate_room_vocabulary(
                        data=manager.data, get_config=get_adapter_config,
                    )
                    # Rides the same start hook, but is INDEPENDENT of it: this one
                    # needs no adapter declaration to judge a target, so it cannot be
                    # deferred by a provider that has not finished setting up, and a
                    # failure above must not skip it.
                    _pause_migration = migrate_pause_timeout_defaults(data=manager.data)
                    if _migration["changes"] or _pause_migration["changes"]:
                        await manager.async_save()
                except Exception:  # pragma: no cover
                    _LOGGER.exception(
                        "eufy_vacuum: room vocabulary migration failed; rooms left as stored"
                    )

            hass.async_create_task(_do())

        entry.async_on_unload(async_at_started(hass, _schedule_vocabulary_migration))

        # One-shot sweep of per-vacuum records naming a vacuum this install does not
        # have. Two reached a live install: the CARD'S OWN PLACEHOLDER
        # ("vacuum.your_vacuum"), persisted because a status query created the record
        # it was asking about, and a truncated entity id carrying a full setup record.
        # Harmless individually; the problem is the set only ever grew. Guards in
        # setup/drift.py and onboarding/manager.py stop new ones; this clears the old.
        # Runs here rather than in async_initialize because is_real_vacuum consults
        # the entity registry, which needs hass to be up.
        try:
            _sweep = sweep_orphaned_vacuums(hass, manager.data)
            if _sweep["removed"]:
                for _bucket, _key in _sweep["removed"]:
                    _LOGGER.info(
                        "eufy_vacuum: removed orphaned %s record for %r "
                        "(no such vacuum entity)", _bucket, _key,
                    )
                await manager.async_save()
        except Exception:
            _LOGGER.exception(  # pragma: no cover
                "eufy_vacuum: orphaned-vacuum sweep failed; records left as stored"
            )

        hass.data[DOMAIN][DATA_RUNTIME] = manager
        _unwind_stack.append(lambda: hass.data.get(DOMAIN, {}).pop(DATA_RUNTIME, None))
        entry.runtime_data = manager  # Bronze: store runtime object in ConfigEntry.runtime_data
        _unwind_stack.append(
            lambda: object.__delattr__(entry, "runtime_data")
            if hasattr(entry, "runtime_data") else None
        )
        hass.data[DOMAIN][DATA_LEARNING] = LearningManager(hass)
        _unwind_stack.append(lambda: hass.data.get(DOMAIN, {}).pop(DATA_LEARNING, None))

        # Warm the learning read caches off-loop, so the (loop-bound) dashboard-snapshot
        # estimate never blocks on disk reading room_stats.json / accuracy_stats.json /
        # job_stats.json — not even on the first snapshot after a restart. See
        # LearningHistoryStore.warm_estimate_caches. (No unwind: a pure read-cache
        # warm with its own swallowing try/except — never leaves anything to undo.)
        _learning_store = LearningHistoryStore(hass)
        for _vac in manager.get_known_vacuum_ids():
            try:
                await hass.async_add_executor_job(
                    functools.partial(_learning_store.warm_estimate_caches, vacuum_entity_id=_vac)
                )
            except Exception:  # pragma: no cover - never block setup on a cache warm
                _LOGGER.debug(
                    "eufy_vacuum: learning cache warm failed for %s", _vac, exc_info=True
                )

        battery_manager = BatteryHealthManager(hass, runtime_manager=manager)

        def _undo_battery_manager() -> None:
            hass.data.get(DOMAIN, {}).pop(DATA_BATTERY, None)
            battery_manager.stop()

        # Pushed BEFORE start() (not after): start() has no per-vacuum try/except
        # of its own, so a failure partway through must still unwind whichever
        # vacuums it already wired — stop() reads the manager's own live internal
        # state at call time, so it does the right thing however far start() got.
        _unwind_stack.append(_undo_battery_manager)
        battery_manager.start(manager.get_known_vacuum_ids())
        hass.data[DOMAIN][DATA_BATTERY] = battery_manager

        # Active-run error tracker. Wires state-change listeners on each
        # vacuum's error_message + vacuum entity, latches errors, persists
        # them across restarts. The two error sensors and the
        # active_run_has_error binary sensor read from this tracker.
        error_tracker = ErrorTracker(hass, runtime_manager=manager)

        def _undo_error_tracker() -> None:
            hass.data.get(DOMAIN, {}).pop(DATA_ERROR_TRACKER, None)
            error_tracker.stop()

        _unwind_stack.append(_undo_error_tracker)
        error_tracker.start(manager.get_known_vacuum_ids())
        hass.data[DOMAIN][DATA_ERROR_TRACKER] = error_tracker

        async def _handle_rebaseline(call: ServiceCall) -> None:
            vacuum_entity_id = call.data["vacuum_entity_id"]
            bm = hass.data.get(DOMAIN, {}).get(DATA_BATTERY)
            if bm is None:
                _LOGGER.warning(  # pragma: no cover
                    "battery: rebaseline service called but battery manager is not loaded"
                )
                return
            ok = bm.rebaseline(vacuum_entity_id)
            if not ok:
                _LOGGER.warning(  # pragma: no cover
                    "battery: rebaseline service called for %s but no record was found",
                    vacuum_entity_id,
                )

        hass.services.async_register(
            DOMAIN,
            "battery_rebaseline",
            _handle_rebaseline,
            schema=_BATTERY_REBASELINE_SCHEMA,
        )
        _unwind_stack.append(lambda: hass.services.async_remove(DOMAIN, "battery_rebaseline"))

        mapping_tracker = MappingTracker(hass)

        def _undo_mapping_tracker() -> None:
            hass.data.get(DOMAIN, {}).pop("mapping_tracker", None)
            mapping_tracker.unregister_all()

        _unwind_stack.append(_undo_mapping_tracker)
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
                _LOGGER.warning(  # pragma: no cover
                    "eufy_vacuum: failed to register position tracker for %s — "
                    "map position tracking will be unavailable for this vacuum",
                    _vac,
                    exc_info=True,
                )

        await async_register_services(hass)
        _unwind_stack.append(lambda: async_unregister_services(hass))
        await async_register_learning_services(hass)
        _unwind_stack.append(lambda: async_unregister_learning_services(hass))
        await async_register_theme_services(hass)
        _unwind_stack.append(lambda: async_unregister_theme_services(hass))
        await async_register_mapping_services(hass)
        _unwind_stack.append(lambda: async_unregister_mapping_services(hass))

        # Listener registration — each module owns its own state/constants
        # and exposes register(hass)/remove(hass). See listeners/ for the
        # per-group implementations.
        lifecycle.register(hass)
        _unwind_stack.append(lambda: lifecycle.remove(hass))
        job_metrics.register(hass)
        _unwind_stack.append(lambda: job_metrics.remove(hass))
        dock_events.register(hass)
        _unwind_stack.append(lambda: dock_events.remove(hass))
        path_blockers.register(hass)
        _unwind_stack.append(lambda: path_blockers.remove(hass))
        pause_timeout.register(hass)
        _unwind_stack.append(lambda: pause_timeout.remove(hass))

        # Stall capture (issue #47) — an OPT-IN consumer of EVENT_STALL_DETECTED, armed
        # per vacuum. Registered unconditionally: the switch is checked per event, so a
        # user toggling it never needs a reload, and the detector itself is untouched.
        stall_capture.register(hass)
        _unwind_stack.append(lambda: stall_capture.remove(hass))
        job_progress.register(hass)
        _unwind_stack.append(lambda: job_progress.remove(hass))
        pose_sampler.register(hass)
        _unwind_stack.append(lambda: pose_sampler.remove(hass))
        discovery.register(hass)
        _unwind_stack.append(lambda: discovery.remove(hass))

        # STOP-CONDITION check (RP-039): verified against the installed HA source
        # (ConfigEntries.async_forward_entry_setups / async_unload_platforms,
        # ConfigEntry.async_unload) that forwarded-platform unload does NOT gate on
        # the parent entry's own state — a platform's async_unload_entry only cares
        # about ITS OWN (domain, config_entry) registration, so calling
        # async_unload_platforms here (entry.state is still SETUP_IN_PROGRESS, not
        # LOADED) is exactly the same call our own async_unload_entry already makes
        # unconditionally on every normal unload. Safe to un-forward mid-setup —
        # this is not the infeasible step.
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _unwind_stack.append(
            lambda: hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        )

        # Register one sidebar panel per managed vacuum. The sidebar title is the
        # user-set per-vacuum panel_title (or "Vacuum Agent" default), read from the
        # stored record so a rename survives restart/reload. See panels.py.
        registered_panels: list[str] = []

        def _undo_panels() -> None:
            for _url in registered_panels:
                try:
                    frontend.async_remove_panel(hass, _url)
                except Exception:  # pragma: no cover - defensive (panel may not exist)
                    _LOGGER.debug(
                        "eufy_vacuum: failed to remove panel /%s during mid-setup unwind",
                        _url, exc_info=True,
                    )
            hass.data.get(DOMAIN, {}).pop(f"_panels_{entry.entry_id}", None)

        _unwind_stack.append(_undo_panels)
        _vacuum_records = manager.data.get("vacuums", {}) or {}
        for vacuum_entity_id in manager.get_known_vacuum_ids():
            panel_url = await async_register_vacuum_panel(
                hass,
                vacuum_entity_id,
                title=effective_panel_title(_vacuum_records.get(vacuum_entity_id)),
            )
            if panel_url:
                registered_panels.append(panel_url)

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
                    # INF-1: the three literals below are DEFAULT_PANEL_TITLE /
                    # PANEL_ICON / WEBCOMPONENT_NAME from panels.py — that module's
                    # own docstring claims this is the single source of truth for
                    # all panel-registration call sites; this fallback path used
                    # to hand-retype them instead of importing the constants.
                    webcomponent_name=WEBCOMPONENT_NAME,
                    js_url=panel_js_url(),
                    sidebar_title=DEFAULT_PANEL_TITLE,
                    sidebar_icon=PANEL_ICON,
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
    except Exception:
        for _undo in reversed(_unwind_stack):
            try:
                _result = _undo()
                if asyncio.iscoroutine(_result):
                    await _result
            except Exception:  # pragma: no cover - defensive; unwind must not mask the original error
                _LOGGER.exception("eufy_vacuum: mid-setup unwind step failed")
        raise


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
        # RP-007 step 4 (SRC-5): a reloaded entry must not serve the previous
        # life's room-source cache as fresh — its freshness stamps survive the
        # reload but its world may not (this is exactly the reload seam RP-003
        # hardened for timers; the cache is the read-side analogue).
        from .rooms.source_refresh import invalidate_room_source_cache

        invalidate_room_source_cache(hass)

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
        stall_capture.remove(hass)
        job_progress.remove(hass)
        pose_sampler.remove(hass)
        discovery.remove(hass)

        await async_unregister_mapping_services(hass)
        await async_unregister_learning_services(hass)
        await async_unregister_theme_services(hass)
        await async_unregister_services(hass)
        hass.services.async_remove(DOMAIN, "battery_rebaseline")

        # Restore the package logger if a debug capture was left active, so a
        # reload doesn't inherit a propagate=False / DEBUG logger (idempotent).
        from .debug_capture import get_capture

        get_capture().stop()

        domain_data = hass.data.get(DOMAIN, {})
        mapping_tracker = domain_data.pop("mapping_tracker", None)
        if mapping_tracker is not None:
            mapping_tracker.unregister_all()
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


def _remove_panel_for_vacuum(hass: HomeAssistant, vacuum_entity_id: str) -> None:
    """Remove one vacuum's sidebar panel + drop its url from the tracking list."""
    panel_url = panel_url_for(vacuum_entity_id)
    try:
        frontend.async_remove_panel(hass, panel_url)
    except Exception:  # pragma: no cover - defensive (panel may not exist)
        _LOGGER.debug("eufy_vacuum: no panel /%s to remove", panel_url, exc_info=True)
    # Drop it from whichever _panels_<entry_id> list holds it so a later unload
    # doesn't try to remove an already-gone panel.
    for key, urls in hass.data.get(DOMAIN, {}).items():
        if key.startswith("_panels_") and isinstance(urls, list) and panel_url in urls:
            urls.remove(panel_url)


async def _teardown_vacuum(hass: HomeAssistant, vacuum_entity_id: str) -> None:
    """Tear down ONE managed vacuum in place — without touching the others.

    Deliberately does NOT reload the config entry. This is a singleton domain
    where one entry manages many vacuums, so a reload would bounce every other
    vacuum's panel + entities, and (because ``async_schedule_reload`` starts the
    unload eagerly) would also race HA's own post-hook device+entity removal.
    Instead we unwind exactly this vacuum's in-memory subsystem wiring + sidebar
    panel, then drop its storage; HA removes the device + its entities itself
    (the caller returns True). RP-039/RF-16: discovery's auto-refresh triggers now
    get the same per-vacuum teardown (discovery.remove_vacuum) — previously the
    ONLY listener group with no per-vacuum unregister API, so a removed vacuum's
    state-change listeners kept firing against a now-nonexistent manager record
    until the next reload/restart. lifecycle.py's watched-entities set has no
    per-vacuum path either, and is NOT in scope here (a distinct, larger
    subsystem — see lifecycle.py's own register()/remove() docstring); a
    subscription to a now-deleted entity there is inert until the next reload.
    """
    domain_data = hass.data.get(DOMAIN, {})

    # In-memory per-vacuum subsystem teardown — each best-effort + isolated so
    # one failure can't strand the rest.
    mapping_tracker = domain_data.get("mapping_tracker")
    if mapping_tracker is not None:
        try:
            mapping_tracker.unregister_vacuum(vacuum_entity_id)
        except Exception:  # pragma: no cover
            _LOGGER.exception(
                "eufy_vacuum: mapping-tracker teardown failed for %s", vacuum_entity_id
            )
    battery_manager = domain_data.get(DATA_BATTERY)
    if battery_manager is not None:
        try:
            battery_manager.unregister_vacuum(vacuum_entity_id)
        except Exception:  # pragma: no cover
            _LOGGER.exception(
                "eufy_vacuum: battery teardown failed for %s", vacuum_entity_id
            )
    error_tracker = domain_data.get(DATA_ERROR_TRACKER)
    if error_tracker is not None:
        try:
            error_tracker.unregister_vacuum(vacuum_entity_id)
        except Exception:  # pragma: no cover
            _LOGGER.exception(
                "eufy_vacuum: error-tracker teardown failed for %s", vacuum_entity_id
            )
    try:
        discovery.remove_vacuum(hass, vacuum_entity_id)
    except Exception:  # pragma: no cover
        _LOGGER.exception(
            "eufy_vacuum: discovery-listener teardown failed for %s", vacuum_entity_id
        )
    try:
        unregister_adapter_config(vacuum_entity_id)
    except Exception:  # pragma: no cover
        _LOGGER.exception(
            "eufy_vacuum: adapter unregister failed for %s", vacuum_entity_id
        )

    # Sidebar panel — the user-visible "still there after disable" symptom.
    _remove_panel_for_vacuum(hass, vacuum_entity_id)

    # Storage last: drop the record + every per-vacuum bucket, then persist so
    # the removal survives a restart and can't resurrect on a later reload.
    manager = domain_data.get(DATA_RUNTIME)
    if manager is not None:
        # In-memory caches remove_vacuum_record deliberately doesn't touch (it's
        # storage-only) — see clear_vacuum_runtime_caches' own docstring.
        manager.clear_vacuum_runtime_caches(vacuum_entity_id=vacuum_entity_id)
        manager.remove_vacuum_record(vacuum_entity_id=vacuum_entity_id)
        await manager.async_save()


@callback
def _schedule_clear_configured_vacuum(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear ``CONF_VACUUM_ENTITY_ID`` from the entry, deferred to the next tick.

    Dropping the configured vacuum's record isn't enough on its own:
    ``async_setup_entry`` re-creates it from ``CONF_VACUUM_ENTITY_ID`` on every
    load (``ensure_vacuum_record(configured_vacuum)``), so without this it would
    **resurrect** on the next reload/restart. We can't clear it inline —
    ``async_update_entry`` fires the entry's update listener, which reloads the
    entry, and doing that mid-device-removal would race HA's own device+entity
    deletion. So we defer the update (and therefore its reload) until after the
    current removal stack unwinds.
    """

    @callback
    def _clear(_now: object = None) -> None:
        data = {k: v for k, v in entry.data.items() if k != CONF_VACUUM_ENTITY_ID}
        options = {k: v for k, v in entry.options.items() if k != CONF_VACUUM_ENTITY_ID}
        try:
            hass.config_entries.async_update_entry(entry, data=data, options=options)
        except Exception:  # pragma: no cover - the entry may already be gone
            _LOGGER.debug(
                "eufy_vacuum: could not clear configured vacuum from entry %s",
                entry.entry_id,
                exc_info=True,
            )

    async_call_later(hass, 0, _clear)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Let a user remove ONE managed vacuum by deleting its device in the UI.

    Without this hook HA only offers "Disable" on the device page — there is no
    "Delete". Each managed vacuum is its OWN service device, identified by
    ``(DOMAIN, vacuum_entity_id.replace(".", "_"))`` (see
    ``entity_helpers.build_vacuum_device_info``), so one device maps to exactly
    one vacuum. We tear that vacuum down in place (its trackers, adapter, sidebar
    panel, and stored data) WITHOUT disturbing the other managed vacuums, then
    return ``True`` so HA removes the device and its entities.

    An in-flight strict-order run's detached phase-watchdog (if any) is left to
    self-terminate — its active-job storage was just dropped, so it exits on its
    next guard check; nothing here cancels it.
    """
    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    identifier = next(
        (value for (domain, value) in device_entry.identifiers if domain == DOMAIN),
        None,
    )
    if identifier is None or manager is None:
        # Not one of ours, or nothing loaded — let HA remove the (stale) device.
        return True

    # The identifier is the sanitised entity_id (dots -> underscores). Match it
    # back by comparing against the known vacuums rather than reversing "_" -> "."
    # (which is ambiguous when an object_id itself contains underscores).
    vacuum_entity_id = next(
        (
            vid
            for vid in manager.get_known_vacuum_ids()
            if vid.replace(".", "_") == identifier
        ),
        None,
    )
    if vacuum_entity_id is None:
        # Ours, but no matching record (already removed, or a sanitisation
        # collision). Let HA drop the device; surface the oddity.
        _LOGGER.warning(
            "eufy_vacuum: device id %r is ours but matches no managed vacuum — "
            "removing the HA device only",
            identifier,
        )
        return True

    await _teardown_vacuum(hass, vacuum_entity_id)

    # If we just removed the vacuum the entry was set up with, clear it from the
    # entry too — otherwise async_setup_entry re-creates ("resurrects") it from
    # CONF_VACUUM_ENTITY_ID on the next load. (Deferred — see the helper.)
    configured = config_entry.options.get(
        CONF_VACUUM_ENTITY_ID, config_entry.data.get(CONF_VACUUM_ENTITY_ID)
    )
    if configured == vacuum_entity_id:
        _schedule_clear_configured_vacuum(hass, config_entry)

    _LOGGER.info(
        "eufy_vacuum: removed managed vacuum %s (device deleted from UI)",
        vacuum_entity_id,
    )
    return True
