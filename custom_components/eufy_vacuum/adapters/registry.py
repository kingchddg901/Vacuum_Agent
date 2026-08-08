"""
Adapter config registry for the ha_vacuum_manager framework.

This module owns the per-vacuum adapter config mapping. There are two
co-existing access surfaces, kept aligned during the migration from
module-level state to a per-config-entry coordinator:

  1. **AdapterCoordinator** — the new pattern. One instance is constructed
     in ``__init__.py:async_setup_entry`` and stashed under
     ``hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR]``. Its public methods
     mirror the bare module-level functions one-for-one. New code should
     use the coordinator.

  2. **Bare module-level functions** — the legacy pattern. These exist
     as thin shims that route to the active coordinator when one is
     present, falling back to a module-level ``_REGISTRY`` dict
     otherwise. The shims keep the ~99 existing call sites working
     without simultaneous code churn. They can be migrated to
     ``coordinator.get_adapter_config(...)`` in subsequent passes and
     deleted once the last call site is converted.

Storage on disk (the user-built "config adapter" overlay) is handled
by ``config_loader.py`` and writes into ``manager.data``, independent
of the registry — both the legacy and coordinator surfaces consume
those entries the same way.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback module-level registry.
#
# Used for two purposes:
#   - As the backing store when no AdapterCoordinator has been constructed
#     yet (e.g. during unit tests that exercise the registry directly,
#     or any code path that runs before async_setup_entry completes).
#   - As the *only* store before the coordinator wiring is added to
#     async_setup_entry. After that wiring is in place, the coordinator
#     becomes the canonical store and this dict stays empty in normal
#     operation.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Active coordinator pointer.
#
# Set by AdapterCoordinator.__init__ when an instance is constructed and
# cleared by AdapterCoordinator.shutdown(). The bare-function shims below
# check this pointer first; only when it's None do they fall back to
# _REGISTRY. The single-instance guard on this integration
# (async_set_unique_id(DOMAIN)) means there's never more than one
# coordinator alive at a time, so this pointer is a safe lookup vehicle.
# ---------------------------------------------------------------------------

_active_coordinator: AdapterCoordinator | None = None


def _set_active_coordinator(coordinator: AdapterCoordinator | None) -> None:
    """Set or clear the module-level active coordinator pointer.

    Called from AdapterCoordinator's own lifecycle methods. External code
    should not call this directly — go through the coordinator's
    constructor and ``shutdown()``.
    """
    global _active_coordinator
    _active_coordinator = coordinator


def get_active_coordinator() -> AdapterCoordinator | None:
    """Return the currently-active coordinator, or None if none constructed.

    Useful for code paths that prefer the coordinator API but need to
    handle the pre-setup / test-fixture case gracefully.
    """
    return _active_coordinator


# ---------------------------------------------------------------------------
# AdapterCoordinator class.
#
# One instance per config entry. Holds the adapter registry as instance
# state (an attribute, not a module-level dict). When the integration
# unloads, the coordinator is dropped from hass.data and its registry
# goes with it — no manual unregistration loop needed.
# ---------------------------------------------------------------------------


class AdapterCoordinator:
    """Per-config-entry adapter registry.

    Single owner of the in-memory ``vacuum_entity_id -> adapter_config``
    mapping for one config entry. Instance methods mirror the module-level
    function names so callers can migrate one-for-one without rewriting
    their lookup logic.

    Lifecycle:
      - Constructed in ``async_setup_entry`` (in ``__init__.py``).
      - Stashed under ``hass.data[DOMAIN][DATA_ADAPTER_COORDINATOR]``.
      - Sets itself as the module-level active coordinator so legacy
        bare-function callers route through it.
      - Torn down in ``async_unload_entry`` via ``shutdown()``, which
        clears the active pointer and drops the instance registry.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        # Per-instance registry. The module-level _REGISTRY is left
        # alone — it's only consulted by the bare-function fallback
        # when no coordinator is active.
        self._registry: dict[str, dict[str, Any]] = {}
        _set_active_coordinator(self)
        _LOGGER.debug(
            "AdapterCoordinator: constructed for entry %s", entry.entry_id
        )

    def shutdown(self) -> None:
        """Clear the registry and detach from the module-level pointer.

        Called from ``async_unload_entry``. Safe to call multiple times.
        """
        if _active_coordinator is self:
            _set_active_coordinator(None)
        self._registry.clear()
        _LOGGER.debug(
            "AdapterCoordinator: shutdown for entry %s", self.entry.entry_id
        )

    # ----- registry methods -------------------------------------------------

    def register_adapter_config(
        self,
        vacuum_entity_id: str,
        config: dict[str, Any],
    ) -> None:
        """Register an adapter config for one vacuum.

        Idempotent — re-registering the same vacuum overwrites the previous
        config. Runs ``_validate_adapter`` and logs every issue.

        RP-033/RF-32: a STORED config (``source == "config"``, UI/service-authored)
        now HARD-RAISES when issues are found — a broken stored config used to
        register cleanly and shadow the live adapter, with every block it omitted
        silently resolving to that block's own absent-default (Eufy-shaped)
        behaviour. A CODE-sourced config (the two shipped brand adapters,
        registered at startup) stays warn-only: both pass validation cleanly
        today, but a future code-adapter regression must degrade to a warning,
        not take every install's startup down with it. Non-dict configs still
        hard-fail regardless of source — always were structurally unusable.
        """
        issues = _validate_adapter(config)
        if issues:
            adapter_id = (
                config.get("adapter_id", "unknown")
                if isinstance(config, dict) else "unknown"
            )
            for issue in issues:
                _LOGGER.warning(
                    "adapter_registry: %s for %s — %s",
                    adapter_id, vacuum_entity_id, issue,
                )
            if not isinstance(config, dict):
                raise TypeError(
                    f"adapter config for {vacuum_entity_id} is not a dict; "
                    f"refusing to register"
                )
            if config.get("source") == "config":
                raise ServiceValidationError(
                    f"adapter config '{adapter_id}' for {vacuum_entity_id} failed "
                    f"registration validation: " + "; ".join(issues)
                )

        _warn_eufy_fallbacks(vacuum_entity_id, config)
        _warn_completion_gate_orphan(vacuum_entity_id, config)

        self._registry[vacuum_entity_id] = config
        _LOGGER.debug(
            "adapter_registry: registered adapter '%s' for %s (source=%s)",
            config.get("adapter_id", "unknown"),
            vacuum_entity_id,
            config.get("source", "unknown"),
        )

    def get_adapter_config(
        self,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Return the adapter config for one vacuum, or None if not registered."""
        return self._registry.get(vacuum_entity_id)

    def get_all_adapter_configs(self) -> dict[str, dict[str, Any]]:
        """Return a snapshot of all registered adapter configs."""
        return dict(self._registry)

    def unregister_adapter_config(self, vacuum_entity_id: str) -> None:
        """Remove the adapter config for one vacuum. Safe if absent."""
        self._registry.pop(vacuum_entity_id, None)

    def clear_registry(self) -> None:
        """Clear all registered configs. Used by tests and on full reset."""
        self._registry.clear()

    # ----- convenience lookups ---------------------------------------------

    def get_adapter_value(
        self,
        vacuum_entity_id: str,
        *path: str,
        fallback: Any = None,
    ) -> Any:
        """Convenience: nested-path lookup with a default."""
        node: Any = self._registry.get(vacuum_entity_id) or {}
        for key in path:
            if not isinstance(node, dict):
                return fallback
            node = node.get(key)
            if node is None:
                return fallback
        return node


# ---------------------------------------------------------------------------
# Validation helper.
#
# Lives at module scope (not on the class) so it can be called from the
# bare-function shims as well as the coordinator method. The shape is
# stable: dict-of-config -> list-of-issue-strings.
# ---------------------------------------------------------------------------


#: Blocks whose ABSENCE resolves to concrete Eufy behaviour rather than to a refusal, and
#: what the framework will silently do instead. Keyed by block -> (what it decides, the
#: Eufy default, the opt-out declaration).
#:
#: The engine resolvers already warn on an UNKNOWN name; an ABSENT block was silent,
#: because a resolver only receives a name and cannot tell "no adapter registered at all"
#: (legacy, fine) from "an adapter registered and omitted this" (a brand-3 bug). At
#: registration the whole config is in hand and the difference is knowable, so that is
#: where the advisory belongs.
_EUFY_FALLBACK_BLOCKS: dict[str, tuple[str, str, str]] = {
    "mapping": (
        "map segmentation",
        "eufy_cv_v1 (Eufy computer-vision room splitting)",
        "declare mapping.segmenter_engine='noop_fallback' if the brand yields no map image",
    ),
    "job_segmenter": (
        "per-room run boundaries",
        "eufy_counter_v1 (Eufy counter-plateau detection)",
        "declare job_segmenter.engine='noop_job_fallback' if the brand emits no per-room signal",
    ),
    "room_attribution": (
        "external-run room attribution",
        "eufy_anchor_winding_v1 (Eufy live-pose anchor winding)",
        "declare room_attribution.engine='noop_room_attribution' to disable auto-attribution",
    ),
}


def _warn_eufy_fallbacks(vacuum_entity_id: str, config: dict[str, Any]) -> None:
    """Log once per registration for each engine block this adapter did not declare.

    RC-4: every permissive default in this framework resolves to a concrete EUFY answer,
    not to a refusal. A brand-3 config assembled from the schema therefore runs Eufy's
    counter-plateau segmenter and anchor-winding attribution against a device emitting
    neither signal — no crash, no warning, wrong learned boundaries.

    Both shipped brands declare all three blocks, so this is silent on every real install
    today. It exists to make the NEXT brand's omission audible at setup rather than
    discoverable months later in bad learning data.

    Advisory only — deliberately not an entry in the validation issues list, because an
    omission is legal and the framework does still work. It just should not be quiet.
    """
    if not isinstance(config, dict):
        return
    adapter_id = config.get("adapter_id", "unknown")
    for block, (decides, default, opt_out) in _EUFY_FALLBACK_BLOCKS.items():
        if config.get(block) is not None:
            continue
        _LOGGER.warning(
            "adapter '%s' for %s declares no '%s' block, so %s falls back to %s. "
            "If that is wrong for this brand, %s.",
            adapter_id, vacuum_entity_id, block, decides, default, opt_out,
        )


#: Keys of ``room_profiles`` that carry BRAND VOCABULARY. Core holds none of it,
#: so each must be stated explicitly — there is nothing to inherit.
#: ``default_profile`` is deliberately NOT here: it names WHICH profile a new room
#: starts on, not what is inside one, and core legitimately owns that key.
_ROOM_PROFILE_VOCABULARY_KEYS = (
    "builtins",
    "custom_template",
    "normalize_defaults",
    "legacy_aliases",
    "floor_type_water_defaults",
    "floor_type_fan_defaults",
)


def _validate_room_profiles(config: dict[str, Any]) -> list[str]:
    """An adapter must DECLARE its profile vocabulary. Declaring none fails it.

    The gate is the block, not each key. An adapter that declares nothing at all
    is a porter who has not reached this part of the port yet, and it cannot
    resolve a single room — so it fails here rather than at the first clean. An
    adapter that declares SOME keys has engaged with the contract, and its
    undeclared keys resolve empty, which is a defined answer rather than an
    inherited one.

    That asymmetry is the whole design. Before 2026-08-07 an absent key silently
    inherited the framework catalog, which was Eufy's vocabulary: a Roborock room
    stored ``fan_speed: "Max"``, a word the device does not use, the card's chips
    matched nothing, ``per_room_live_settings`` filtered the value out, and an
    unedited room applied NO SUCTION AT ALL. Nothing here falls back now, so the
    only state still worth failing on is the one that means "not written yet".

    ``{}`` fails alongside an absent block for the same reason: a brand with zero
    profile vocabulary can resolve nothing, so it is never a working declaration.
    "Supplies none" is stated per key (``builtins: {}``), which leaves the rest of
    the block visible as deliberate.
    """
    if "room_profiles" not in config:
        return [
            "room_profiles: undeclared — an adapter must state its profile vocabulary; "
            "there is no framework catalog to inherit. Declare the keys it has and set "
            f"the rest empty ({{}}): {', '.join(_ROOM_PROFILE_VOCABULARY_KEYS)}."
        ]
    block = config.get("room_profiles")
    if not isinstance(block, dict):
        return ["room_profiles: must be a dict"]
    if not block:
        return [
            "room_profiles: declared empty — a brand with no profile vocabulary at all "
            "cannot resolve a room. State emptiness per key (e.g. legacy_aliases: {}) so "
            "the keys it DOES supply stay visible."
        ]
    return []


def _validate_adapter(config: dict[str, Any]) -> list[str]:
    """Return a list of validation issue strings; empty = config is valid.

    Currently checks:
      - mapping.segmenter_engine resolves to a known engine
      - mapping.segmenter_tuning passes the engine's own tuning validator

    More rules (required entities, completion block presence, dispatch
    template recognition) land here as the framework's expectations
    harden.
    """
    issues: list[str] = []

    if not isinstance(config, dict):
        return ["adapter config must be a dict"]

    issues.extend(_validate_room_profiles(config))

    # Segmenter engine check — deferred import keeps the registry module
    # free of mapping dependencies at import time.
    mapping_block = config.get("mapping")
    if mapping_block is not None:
        if not isinstance(mapping_block, dict):
            issues.append("'mapping' must be a dict if present")
        else:
            from ..mapping.segmenter_engines import (
                known_engine_names,
                get_segmenter_engine,
            )

            engine_name = mapping_block.get("segmenter_engine")
            if engine_name is None:
                issues.append(
                    "mapping.segmenter_engine is required when 'mapping' is "
                    "present; declare 'noop_fallback' to disable segmentation"
                )
            elif engine_name not in known_engine_names():
                issues.append(
                    f"mapping.segmenter_engine {engine_name!r} is unknown; "
                    f"valid names: {sorted(known_engine_names())}"
                )
            else:
                tuning = mapping_block.get("segmenter_tuning") or {}
                engine = get_segmenter_engine(engine_name)
                issues.extend(engine.validate_tuning(tuning))

    # Job-segmenter engine check — mirrors the mapping check (deferred import). A
    # declared block must name a registered job-segmenter engine and pass its tuning
    # validator. Absent block → the consumers fall back to the Eufy counter engine.
    job_block = config.get("job_segmenter")
    if job_block is not None:
        if not isinstance(job_block, dict):
            issues.append("'job_segmenter' must be a dict if present")
        else:
            from ..learning.job_segmenter_engines import (
                known_job_engine_names,
                get_job_segmenter_engine,
            )

            engine_name = job_block.get("engine")
            if engine_name is None:
                issues.append(
                    "job_segmenter.engine is required when 'job_segmenter' is "
                    "present; declare 'noop_job_fallback' to disable counter segmentation"
                )
            elif engine_name not in known_job_engine_names():
                issues.append(
                    f"job_segmenter.engine {engine_name!r} is unknown; "
                    f"valid names: {sorted(known_job_engine_names())}"
                )
            else:
                tuning = job_block.get("tuning") or {}
                engine = get_job_segmenter_engine(engine_name)
                issues.extend(engine.validate_tuning(tuning))

    # Room-attribution engine check — mirrors the job-segmenter check. A declared block
    # must name a registered room-attribution engine and pass its tuning validator.
    # Absent block → external-run auto-attribution falls back to the Eufy engine.
    attr_block = config.get("room_attribution")
    if attr_block is not None:
        if not isinstance(attr_block, dict):
            issues.append("'room_attribution' must be a dict if present")
        else:
            from ..learning.room_attribution_engines import (
                known_room_attribution_names,
                get_room_attribution_engine,
            )

            engine_name = attr_block.get("engine")
            if engine_name is None:
                issues.append(
                    "room_attribution.engine is required when 'room_attribution' is "
                    "present; declare 'noop_room_attribution' to disable auto-attribution"
                )
            elif engine_name not in known_room_attribution_names():
                issues.append(
                    f"room_attribution.engine {engine_name!r} is unknown; "
                    f"valid names: {sorted(known_room_attribution_names())}"
                )
            else:
                tuning = attr_block.get("tuning") or {}
                engine = get_room_attribution_engine(engine_name)
                issues.extend(engine.validate_tuning(tuning))

    # Room-profile catalog check — a declared block must be a dict with sane field
    # types. The framework merges it over the in-code defaults (resolve_profile_catalog),
    # so a partial block is fine; this only catches a malformed declaration.
    room_profiles_block = config.get("room_profiles")
    if room_profiles_block is not None:
        if not isinstance(room_profiles_block, dict):
            issues.append("'room_profiles' must be a dict if present")
        else:
            default_profile = room_profiles_block.get("default_profile")
            if default_profile is not None and not isinstance(default_profile, str):
                issues.append(
                    f"room_profiles.default_profile must be a string (got {default_profile!r})"
                )
            for key in (
                "builtins",
                "custom_template",
                "legacy_aliases",
                "floor_type_water_defaults",
                "floor_type_fan_defaults",
                "normalize_defaults",
            ):
                value = room_profiles_block.get(key)
                if value is not None and not isinstance(value, dict):
                    issues.append(f"room_profiles.{key} must be a dict if present")

    # capability_hints check — an unrecognised hint key is a SILENT no-op: the reader does
    # `_hints.get(name)`, misses, and the derived/default value stands. So a typo is
    # indistinguishable from declaring nothing, which is how a brand saying "I cannot do
    # this" gets ignored. Caught here rather than at "why is this control showing?".
    hints_block = config.get("capability_hints")
    if hints_block is not None:
        if not isinstance(hints_block, dict):
            issues.append("'capability_hints' must be a dict if present")
        else:
            from ..core.capabilities import KNOWN_CAPABILITY_HINTS

            for key in sorted(set(hints_block) - KNOWN_CAPABILITY_HINTS):
                issues.append(
                    f"capability_hints.{key!r} is not a known capability flag and will be "
                    f"silently ignored; valid: {sorted(KNOWN_CAPABILITY_HINTS)}"
                )

    # Dispatch template check — a declared template must resolve to a registered
    # dispatch engine. A schema-valid template with no engine yet (e.g.
    # dreame_room_clean before its engine ships) is rejected at registration
    # rather than silently falling back to the Eufy shape and cleaning wrong.
    dispatch_block = config.get("dispatch")
    if isinstance(dispatch_block, dict):
        from ..queue.dispatch_engines import known_dispatch_templates

        template = dispatch_block.get("template")
        if template is not None and template not in known_dispatch_templates():
            issues.append(
                f"dispatch.template {template!r} is unknown; "
                f"valid names: {sorted(known_dispatch_templates())}"
            )

        # RP-033/WD-5 (registration half): a nonsensical phase_timing override
        # (a 0 poll interval busy-loops; 0 max_attempts means the watchdog never
        # even tries) used to only surface downstream as a silent runtime clamp
        # (core/manager.py._phase_timing's own _minimums table, which STAYS as a
        # defense-in-depth safety net — this is a separate, earlier check on the
        # same values). Caught here so a bad stored config refuses outright.
        phase_timing = dispatch_block.get("phase_timing")
        if phase_timing is not None:
            if not isinstance(phase_timing, dict):
                issues.append("'dispatch.phase_timing' must be a dict if present")
            else:
                for key, value in phase_timing.items():
                    if (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and value <= 0
                    ):
                        issues.append(
                            f"dispatch.phase_timing.{key}={value!r} must be a "
                            f"positive number"
                        )

    # Setup-steps check — RP-033/SETUP-9. Three places in this codebase already
    # claim an unknown step id is "rejected at registration"
    # (config_schema.py's own setup.steps description, setup/drift.py:52-53 and
    # :102-104's docstring) while nothing here actually did that. The allowed set
    # is read from ADAPTER_CONFIG_SCHEMA itself (not re-declared here) so the two
    # never drift apart.
    setup_block = config.get("setup")
    if setup_block is not None:
        if not isinstance(setup_block, dict):
            issues.append("'setup' must be a dict if present")
        else:
            steps = setup_block.get("steps")
            if steps is not None and isinstance(steps, list):
                from .config_schema import ADAPTER_CONFIG_SCHEMA

                known_steps = set(
                    ADAPTER_CONFIG_SCHEMA.get("setup", {})
                    .get("fields", {})
                    .get("steps", {})
                    .get("values", [])
                )
                unknown_steps = sorted(s for s in steps if s not in known_steps)
                if unknown_steps:
                    issues.append(
                        f"setup.steps contains unknown step id(s) {unknown_steps}; "
                        f"valid ids: {sorted(known_steps)}"
                    )

    return issues


def _warn_completion_gate_orphan(vacuum_entity_id: str, config: dict[str, Any]) -> None:
    """RP-033/COMMON-2: warn (never raise) when completion.require_job_active_clear
    is set without entities.job_active being declared.

    Unlike ``_validate_adapter``'s issues list (hard-raised for a stored config by
    the caller), this is a standalone advisory for BOTH source types — the runtime
    already degrades gracefully in this case (listeners/_common.py's
    completion_secondary_satisfied now falls through to the sentinel check instead
    of unconditionally returning True), so refusing registration over it would be
    stricter than the actual failure mode warrants.
    """
    if not isinstance(config, dict):
        return
    completion_block = config.get("completion")
    if not isinstance(completion_block, dict):
        return
    if not completion_block.get("require_job_active_clear"):
        return
    entities = config.get("entities")
    job_active = entities.get("job_active") if isinstance(entities, dict) else None
    if job_active:
        return
    _LOGGER.warning(
        "adapter '%s' for %s sets completion.require_job_active_clear without "
        "declaring entities.job_active — the flag has no effect at runtime and "
        "completion falls back to the default active_cleaning_target sentinel check",
        config.get("adapter_id", "unknown"), vacuum_entity_id,
    )


# ---------------------------------------------------------------------------
# Bare-function shims.
#
# These match the legacy module-level API exactly. They route to the
# active coordinator when one is present; otherwise they touch the
# module-level _REGISTRY so test fixtures and pre-setup paths still work.
#
# Net effect during the migration window: legacy callers
# (~99 call sites across 22 files) keep working unchanged while the
# underlying storage relocates from a module-level dict to coordinator
# instance state.
#
# When migration completes (every call site uses
# coordinator.method(...) explicitly), these shims and the fallback
# _REGISTRY dict can be deleted together. Until then they're the
# safety net.
# ---------------------------------------------------------------------------


def register_adapter_config(
    vacuum_entity_id: str,
    config: dict[str, Any],
) -> None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        _active_coordinator.register_adapter_config(vacuum_entity_id, config)
        return

    # Fallback path — no coordinator constructed yet.
    issues = _validate_adapter(config)
    if issues:
        adapter_id = (
            config.get("adapter_id", "unknown")
            if isinstance(config, dict) else "unknown"
        )
        for issue in issues:
            _LOGGER.warning(
                "adapter_registry (fallback): %s for %s — %s",
                adapter_id, vacuum_entity_id, issue,
            )
        if not isinstance(config, dict):
            raise TypeError(
                f"adapter config for {vacuum_entity_id} is not a dict; "
                f"refusing to register"
            )
        # RP-033/RF-32: same source-based hard-raise as the coordinator method —
        # see its docstring for the rationale.
        if config.get("source") == "config":
            raise ServiceValidationError(
                f"adapter config '{adapter_id}' for {vacuum_entity_id} failed "
                f"registration validation: " + "; ".join(issues)
            )

    _warn_eufy_fallbacks(vacuum_entity_id, config)
    _warn_completion_gate_orphan(vacuum_entity_id, config)

    _REGISTRY[vacuum_entity_id] = config
    _LOGGER.debug(
        "adapter_registry (fallback): registered adapter '%s' for %s (source=%s)",
        config.get("adapter_id", "unknown"),
        vacuum_entity_id,
        config.get("source", "unknown"),
    )


def get_adapter_config(
    vacuum_entity_id: str,
) -> dict[str, Any] | None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        return _active_coordinator.get_adapter_config(vacuum_entity_id)
    return _REGISTRY.get(vacuum_entity_id)


def get_all_adapter_configs() -> dict[str, dict[str, Any]]:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        return _active_coordinator.get_all_adapter_configs()
    return dict(_REGISTRY)


def unregister_adapter_config(vacuum_entity_id: str) -> None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        _active_coordinator.unregister_adapter_config(vacuum_entity_id)
        return
    _REGISTRY.pop(vacuum_entity_id, None)


def clear_registry() -> None:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        _active_coordinator.clear_registry()
        return
    _REGISTRY.clear()


def get_adapter_value(
    vacuum_entity_id: str,
    *path: str,
    fallback: Any = None,
) -> Any:
    """Legacy shim — routes to the active coordinator if present."""
    if _active_coordinator is not None:
        return _active_coordinator.get_adapter_value(
            vacuum_entity_id, *path, fallback=fallback
        )
    node: Any = _REGISTRY.get(vacuum_entity_id) or {}
    for key in path:
        if not isinstance(node, dict):
            return fallback
        node = node.get(key)
        if node is None:
            return fallback
    return node


def adapter_honors_clean_order(vacuum_entity_id: str) -> bool:
    """Whether this brand cleans rooms in the DISPATCHED queue order.

    THE ONE READ OF ``capabilities.honors_clean_order``. It lives here, next to
    ``get_adapter_value``, because five unrelated subsystems ask the question and
    one of them used to answer it differently:

      - ``core/manager.py`` — clears the bounds-exit gate, and exports the flag
        into the dashboard snapshot the card reads.
      - ``jobs/active_job.py`` — gates stall / running-long / skipped anomalies.
      - ``jobs/phase_runner.py`` — gates whether a multi-room group phase's
        per-room timings are SEGMENTED (admitted to learning) or apportioned
        evenly (excluded).
      - ``planning/run_plan.py`` — the run-start "order is advisory" note and
        the strict-order phase split.

    ONLY A LITERAL ``False`` MEANS "DOES NOT HONOR ORDER". The declared contract
    is default-True (``adapters/config_schema.py``, ``docs/dev/22-adapter-config-reference.md``
    §14): a brand OPTS OUT by declaring False, so absent / ``None`` / an
    unreadable capabilities block all mean the default, True. The snapshot
    exporter used ``bool(_caps_cfg.get("honors_clean_order", True))`` instead,
    which folds ``None``/``0``/``""`` to False — so an adapter declaring
    ``honors_clean_order: null`` was read as order-honoring by the four gates
    and as path-optimizing by the snapshot. That is the wrong direction to be
    wrong in: a false "does not honor order" sends confidently-wrong evenly-
    apportioned per-room baselines into learning. Answer conservatively here
    and there is only one answer to be wrong about.

    Non-dict ``capabilities`` returns True for the same reason — an unreadable
    declaration is not a declaration of False.
    """
    capabilities = get_adapter_value(vacuum_entity_id, "capabilities")
    if not isinstance(capabilities, dict):
        return True
    return capabilities.get("honors_clean_order") is not False
