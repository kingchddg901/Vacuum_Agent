"""Central orchestrator for the eufy_vacuum integration, managing vacuum state, room configuration, job control, queue building, map management, and all service handlers."""

from __future__ import annotations

import asyncio
from datetime import datetime
import hashlib
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..adapters.eufy.charging import (
    get_battery_level as _get_battery_level_impl,
    is_charging as _is_charging_impl,
    is_low_battery_return_state as _is_low_battery_return_state_impl,
)
from ..const import DATA_LEARNING, DOMAIN, EVENT_ROOM_FINISHED, EVENT_ROOM_STARTED, EVENT_STALL_DETECTED
from ..entity_helpers import get_floor_type_label
from ..jobs.job_monitor import (
    build_job_metadata_from_payload,
    build_start_blocker_from_lifecycle,
    evaluate_job_lifecycle,
)
from ..maps.map_manager import (
    ensure_map_bucket,
    get_map_bucket,
    get_vacuum_maps_summary,
    rebuild_map_bucket,
)
from ..models.models import VacuumRuntimeState
from ..queue.queue_engine import (
    advance_active_job_phase,
    build_active_job_state,
    build_queue_from_managed_rooms,
    build_room_clean_payload,
)
from ..queue.dispatch_engines import get_dispatch_engine
from ..rooms.room_discovery import discover_rooms_payload
from ..rooms.room_manager import build_managed_rooms, build_room_selection_summary
from ..timestamp_utils import parse_timestamp, utc_now_iso
from ..maintenance import maintenance_status as _maintenance_status, replacement_status as _replacement_status
from .capabilities import detect_capabilities
from .storage import EufyVacuumStorage


_LOGGER = logging.getLogger(__name__)

# Standard HA vacuum platform states that indicate an active or faulted vacuum.
# These are defined by the HA vacuum integration, not by any specific brand.
# Brand-specific active states (e.g. task_status strings) come from the adapter.
_HA_ACTIVE_VACUUM_STATES: frozenset[str] = frozenset({
    "cleaning",   # HA standard
    "returning",  # HA standard
    "paused",     # HA standard
    "error",      # HA standard
})
_PATH_BLOCK_ACTIONS = frozenset(
    {"event_only", "pause_and_event", "cancel_and_event"}
)


def _iso_now() -> str:
    """Return current UTC timestamp in stable format."""
    return utc_now_iso()


def _safe_int(value: Any, default: int = 0) -> int:
    """Return int value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return float value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_path_block_action(value: Any) -> str:
    """Return a supported path-block reaction policy."""
    normalized = str(value or "").strip().lower()
    if normalized in _PATH_BLOCK_ACTIONS:
        return normalized
    return "event_only"


def _normalize_pause_timeout_minutes(value: Any) -> int:
    """Return a safe non-negative paused-job timeout in minutes."""
    return max(_safe_int(value, 0), 0)


def _display_label(value: Any) -> str | None:
    """Return a friendly title-cased label for enum-like values."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = " ".join(text.replace("_", " ").replace("-", " ").split())
    if not normalized:
        return None
    explicit = {
        "vacuum mop": "Vacuum + Mop",
        "vacuum and mop": "Vacuum + Mop",
        "by room": "By Room",
        "by time": "By Time",
        "replace soon": "Replace Soon",
        "replace now": "Replace Now",
    }
    lowered = normalized.lower()
    if lowered in explicit:
        return explicit[lowered]
    return " ".join(part.capitalize() for part in normalized.split())


def _profile_name_label(value: Any) -> str | None:
    """Return a friendly label for known preset names."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.lower()
    explicit = {
        "vacuum_quick": "Vacuum Quick",
        "vacuum_deep": "Vacuum Deep",
        "vacuum_mop_quick": "Vacuum + Mop Quick",
        "vacuum_mop_deep": "Vacuum + Mop Deep",
        "custom": "Custom",
        "user_1": "Custom",
    }
    return explicit.get(normalized) or _display_label(normalized)


def _settings_profile_display(
    *,
    room_name: Any = None,
    selected_profile_name: Any = None,
    resolved_profile_name: Any = None,
    clean_mode: Any = None,
    clean_intensity: Any = None,
    fan_speed: Any = None,
    water_level: Any = None,
    path_type: Any = None,
    clean_passes: Any = None,
    edge_mopping: Any = None,
) -> dict[str, Any]:
    """Return human-facing labels for one room/settings bundle."""
    room_label = _display_label(room_name)
    selected_profile_label = _profile_name_label(selected_profile_name)
    resolved_profile_label = _profile_name_label(resolved_profile_name)
    mode_label = _display_label(clean_mode)
    intensity_label = _display_label(clean_intensity)
    fan_label = _display_label(fan_speed)
    water_label = _display_label(water_level)
    path_label = _display_label(path_type)
    passes = max(_safe_int(clean_passes, 1), 1)
    edge_enabled = bool(edge_mopping)

    selected_normalized = str(selected_profile_name or "").strip().lower()
    resolved_normalized = str(resolved_profile_name or "").strip().lower()
    is_custom = selected_normalized in {"", "custom", "user_1"} or (
        selected_normalized != resolved_normalized
        and selected_normalized not in {"vacuum_quick", "vacuum_deep", "vacuum_mop_quick", "vacuum_mop_deep"}
    )

    if not is_custom and selected_profile_label:
        profile_label = f"{room_label} {selected_profile_label}".strip() if room_label else selected_profile_label
    else:
        profile_parts = [room_label, "Custom", mode_label]
        if passes > 1:
            profile_parts.append(f"{passes} Pass")
        profile_label = " ".join(part for part in profile_parts if part).strip() or "Custom Profile"

    subtitle_bits: list[str] = []
    for bit in (intensity_label, fan_label):
        if bit:
            subtitle_bits.append(bit)
    if water_label and str(water_label).lower() != "off":
        subtitle_bits.append(water_label)
    if path_label:
        subtitle_bits.append(path_label)
    if passes > 1:
        subtitle_bits.append(f"{passes} Passes")
    if edge_enabled:
        subtitle_bits.append("Edge Mopping")

    return {
        "profile_label": profile_label,
        "profile_subtitle": " • ".join(subtitle_bits) if subtitle_bits else None,
        "selected_profile_label": selected_profile_label,
        "resolved_profile_label": resolved_profile_label,
        "clean_mode_label": mode_label,
        "clean_intensity_label": intensity_label,
        "fan_speed_label": fan_label,
        "water_level_label": water_label,
        "path_type_label": path_label,
        "clean_passes_label": f"{passes} Pass" if passes == 1 else f"{passes} Passes",
        "edge_mopping_label": "Edge Mopping" if edge_enabled else "Edge Mopping Off",
        "is_custom_profile": is_custom,
    }


def _hours_text(value: Any) -> str | None:
    """Return a simple human-readable hours label."""
    number = _safe_float(value, -1.0)
    if number < 0:
        return None
    rounded = round(number, 1)
    if abs(rounded - round(rounded)) < 0.05:
        integer = int(round(rounded))
        return f"{integer} hour" if integer == 1 else f"{integer} hours"
    return f"{rounded:g} hours"


def _room_surface_labels(
    *,
    floor_type: Any = None,
) -> dict[str, Any]:
    """Return reusable room floor display labels."""
    floor_value = str(floor_type or "").strip().lower() or None
    return {
        "floor_type_label": get_floor_type_label(floor_value) if floor_value else None,
    }



class EufyVacuumManager:
    """Singleton runtime manager that owns all persistent integration state and exposes the full service API."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager with a reference to the HA instance."""
        self.hass = hass
        self.storage = EufyVacuumStorage(hass)
        self.data: dict[str, Any] = {}
        self.runtime: dict[str, VacuumRuntimeState] = {}
        self._room_history_cache_ready: set[str] = set()

    async def async_initialize(self) -> None:
        """Load persistent storage and bring all data structures up to the current schema.

        Seeds required top-level keys, backfills new room fields on stored rooms,
        collapses legacy flat discovery payloads into per-map-id dicts, and seeds
        the preloaded theme library exactly once so the per-call read path stays fast.
        """
        self.data = await self.storage.async_load()
        self.data.setdefault("vacuums", {})
        self.data.setdefault("capabilities", {})
        self.data.setdefault("room_history", {})
        self.data.setdefault("room_rule_status", {})

        # Drop the deprecated "icons" storage block. The icon-selects platform
        # was removed (the card no longer surfaces those entities); leaving the
        # block intact just bloats the storage file on existing installs.
        if "icons" in self.data:
            self.data.pop("icons", None)

        # Construct ThemeManager after data is loaded - it seeds and owns
        # the data["theme"] sub-tree and holds the update-callback list.
        from ..themes import ThemeManager
        self.themes = ThemeManager(self.data)

        # Construct MaintenanceManager - owns upkeep metadata, replacement discovery,
        # maintenance reset snapshots, remaining-hours logic, and upkeep snapshot.
        from ..maintenance import MaintenanceManager
        self.maintenance = MaintenanceManager(manager=self)

        # Construct DockManager - owns dock action dispatch, status gating,
        # and dock event recording.
        from ..dock import DockManager
        self.dock = DockManager(manager=self)

        # Construct OnboardingManager - owns data["onboarding"] + room-discovery state.
        from ..onboarding import OnboardingManager
        self.onboarding = OnboardingManager(data=self.data, hass=self.hass)

        # Construct ProfileManager - owns room profile + run profile CRUD.
        from ..profiles import ProfileManager
        self.profiles = ProfileManager(manager=self)

        from ..rooms import AccessGraphManager
        self.access_graph = AccessGraphManager(data=self.data, hass=self.hass)

        from ..jobs import ActiveJobTracker
        self.active_job = ActiveJobTracker(manager=self)

        from ..planning import RunPlanManager
        self.run_plan = RunPlanManager(manager=self)

        from ..rooms import RoomMapManager
        self.room_map = RoomMapManager(manager=self)

        # Backfill fields added after initial release; rooms that already have
        # the key are untouched by setdefault.
        for _vac_maps in self.data.get("maps", {}).values():
            for _map_bucket in _vac_maps.values():
                if not isinstance(_map_bucket, dict):
                    continue
                for _room in _map_bucket.get("rooms", {}).values():
                    if not isinstance(_room, dict):
                        continue
                    _room.setdefault("path_type", None)
                    _room.setdefault("is_dock_room", False)
                    _room.setdefault("is_transition", False)
                    _room.setdefault("grants_access_to", [])
                    _room.setdefault("rules", [])
                    _room.setdefault("floor_type", "hardwood")
                    _room.setdefault("profile_name", "vacuum_quick")
                    # Compact floor_type="carpet" + carpet_type sub-field into the
                    # canonical "carpet_low_pile" / "carpet_high_pile" single value.
                    if _room.get("floor_type") == "carpet":
                        _ct = _room.pop("carpet_type", "low_pile") or "low_pile"
                        _room["floor_type"] = f"carpet_{_ct}"
                    else:
                        _room.pop("carpet_type", None)
                    # `carpet` is fully derived from floor_type at read time.
                    _room.pop("carpet", None)

        # Flatten discovery entries that use the old top-level "rooms" key into
        # the current per-map-id dict shape.
        for _vac_id, _disc in list(self.data.get("discovery", {}).items()):
            if isinstance(_disc, dict) and "rooms" in _disc:
                _old_map_id = str(_disc.get("active_map_id") or "unknown")
                self.data["discovery"][_vac_id] = {_old_map_id: _disc}

        # One-time migration: back-fill setup_progress for existing installs
        # whose data predates the explicit setup state machine. Detects
        # vacuums that already have managed rooms and stamps their setup as
        # complete so the new framework code doesn't prompt for onboarding
        # that was already done. Idempotent — re-running is a no-op.
        self._migrate_setup_progress()

        self._room_update_callbacks: list = []
        self._run_profile_update_callbacks: list = []
        self._room_history_update_callbacks: list = []
        self._room_rule_status_update_callbacks: list = []
        self._room_history_cache_loading: set[str] = set()

    def _migrate_setup_progress(self) -> None:
        """One-time back-fill of setup_progress for pre-state-machine installs.

        Before the explicit setup state machine landed, "setup complete"
        was inferred from data shape ("rooms exist == map imported ==
        setup done"). This migration converts that implicit state to
        the explicit setup_progress record.

        Rules:
          - Vacuums already in setup_progress are skipped (idempotent).
          - Vacuums with no managed rooms are skipped (they genuinely
            haven't completed setup; let the normal flow handle them).
          - Vacuums with managed rooms get all three legacy Eufy steps
            stamped complete: add_vacuum, import_active_map, save_rooms.
          - Every room without an is_configured field gets stamped True
            with the current timestamp.

        Invisible to users in the success path. The only signal is the
        absence of an onboarding prompt that would otherwise appear.
        """
        from ..learning.utils import _iso_now

        self.data.setdefault("setup_progress", {})
        now = _iso_now()

        for vacuum_entity_id, vac_record in (
            self.data.get("vacuums", {}) or {}
        ).items():
            if not isinstance(vac_record, dict):
                continue
            if vacuum_entity_id in self.data["setup_progress"]:
                continue  # already migrated

            vac_maps = self.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
            has_rooms = any(
                isinstance(bucket, dict) and bucket.get("rooms")
                for bucket in vac_maps.values()
            )
            if not has_rooms:
                continue  # never completed setup; normal flow applies

            self.data["setup_progress"][vacuum_entity_id] = {
                "completed_steps": [
                    "add_vacuum",
                    "import_active_map",
                    "save_rooms",
                ],
                "last_advanced_at": now,
                "migrated_at": now,
                "rejected_rooms": [],
                "room_drift_history": {},
            }

            for bucket in vac_maps.values():
                if not isinstance(bucket, dict):
                    continue
                for room in (bucket.get("rooms") or {}).values():
                    if not isinstance(room, dict):
                        continue
                    if "is_configured" not in room:
                        room["is_configured"] = True
                        room.setdefault("configured_at", now)

    # ------------------------------------------------------------------
    # Callback registration / notification
    # ------------------------------------------------------------------

    def register_room_update_callback(self, callback) -> None:
        """Register a callback to fire when rooms are updated."""
        self._room_update_callbacks.append(callback)

    def unregister_room_update_callback(self, callback) -> None:
        """Unregister a room update callback."""
        if callback in self._room_update_callbacks:
            self._room_update_callbacks.remove(callback)

    def register_run_profile_update_callback(self, callback) -> None:
        """Register a callback to fire when saved run profiles are updated."""
        self._run_profile_update_callbacks.append(callback)

    def unregister_run_profile_update_callback(self, callback) -> None:
        """Unregister a saved run profile update callback."""
        if callback in self._run_profile_update_callbacks:
            self._run_profile_update_callbacks.remove(callback)

    def register_room_history_update_callback(self, callback) -> None:
        """Register a callback to fire when per-room cleaning history updates."""
        self._room_history_update_callbacks.append(callback)

    def unregister_room_history_update_callback(self, callback) -> None:
        """Unregister a room history update callback."""
        if callback in self._room_history_update_callbacks:
            self._room_history_update_callbacks.remove(callback)

    def register_room_rule_status_update_callback(self, callback) -> None:
        """Register a callback to fire when per-room rule status updates."""
        self._room_rule_status_update_callbacks.append(callback)

    def unregister_room_rule_status_update_callback(self, callback) -> None:
        """Unregister a room rule status update callback."""
        if callback in self._room_rule_status_update_callbacks:
            self._room_rule_status_update_callbacks.remove(callback)

    def register_theme_update_callback(self, callback) -> None:
        """Register a theme update callback - delegates to ThemeManager."""
        self.themes.register_update_callback(callback)

    def unregister_theme_update_callback(self, callback) -> None:
        """Unregister a theme update callback - delegates to ThemeManager."""
        self.themes.unregister_update_callback(callback)


    def _notify_rooms_updated(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Fire all registered room update callbacks."""
        for cb in list(self._room_update_callbacks):
            try:
                cb(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Room update callback failed for %s map %s",
                    vacuum_entity_id, map_id,
                )

    def _notify_run_profiles_updated(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Fire all registered saved-run-profile update callbacks."""
        for cb in list(self._run_profile_update_callbacks):
            try:
                cb(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Run profile update callback failed for %s map %s",
                    vacuum_entity_id, map_id,
                )

    def _notify_room_history_updated(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Fire all registered room-history update callbacks."""
        for cb in list(self._room_history_update_callbacks):
            try:
                cb(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Room history update callback failed for %s map %s",
                    vacuum_entity_id,
                    map_id,
                )

    def _notify_room_rule_status_updated(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Fire all registered room-rule-status update callbacks."""
        for cb in list(self._room_rule_status_update_callbacks):
            try:
                cb(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Room rule status update callback failed for %s map %s",
                    vacuum_entity_id,
                    map_id,
                )

    def _refresh_room_derived_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Refresh queue and payload snapshots after room configuration changes."""
        try:
            self.build_queue(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            self.build_room_payload(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
        except Exception:  # pragma: no cover - best-effort refresh, logs and swallows
            _LOGGER.exception(
                "Failed refreshing derived room state for %s map %s",
                vacuum_entity_id,
                map_id,
            )

    # ------------------------------------------------------------------
    # Vacuum / capability management
    # ------------------------------------------------------------------

    def get_pause_timeout_settings(self, *, vacuum_entity_id: str) -> dict[str, Any]:
        """Return persisted paused-job timeout settings for one vacuum."""
        vacuum_bucket = self.data.setdefault("vacuums", {}).setdefault(
            vacuum_entity_id, {}
        )
        default_minutes = _normalize_pause_timeout_minutes(
            vacuum_bucket.get("pause_timeout_minutes_default")
        )
        vacuum_bucket["pause_timeout_minutes_default"] = default_minutes
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "pause_timeout_minutes_default": default_minutes,
        }

    def set_pause_timeout_settings(
        self,
        *,
        vacuum_entity_id: str,
        pause_timeout_minutes_default: int,
    ) -> dict[str, Any]:
        """Persist the default paused-job timeout for one vacuum."""
        vacuum_bucket = self.data.setdefault("vacuums", {}).setdefault(
            vacuum_entity_id, {}
        )
        default_minutes = _normalize_pause_timeout_minutes(
            pause_timeout_minutes_default
        )
        vacuum_bucket["pause_timeout_minutes_default"] = default_minutes
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "updated": True,
            "pause_timeout_minutes_default": default_minutes,
        }

    def _clear_room_selections_after_start(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Turn all rooms off after a successful start so the next run begins empty."""
        map_bucket = ensure_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        rooms = map_bucket.get("rooms", {})
        if not isinstance(rooms, dict) or not rooms:
            return

        changed = False
        for room_key, room_data in list(rooms.items()):
            if not isinstance(room_data, dict):
                continue
            if not bool(room_data.get("enabled", False)):
                continue
            rooms[room_key] = {
                **room_data,
                "enabled": False,
            }
            changed = True

        if not changed:
            return

        map_bucket["rooms"] = rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)
        self._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

    async def async_save(self) -> None:
        """Save persistent data."""
        await self.storage.async_save(self.data)

    async def _async_save_logged(self) -> None:
        """Save persistent data, logging any storage failure."""
        try:
            await self.storage.async_save(self.data)
        except Exception:  # pragma: no cover - best-effort save, logs and swallows
            _LOGGER.exception("Failed to auto-save integration data")

    def _get_learning_manager(self):
        """Return learning manager if loaded."""
        return self.hass.data.get(DOMAIN, {}).get(DATA_LEARNING)

    def _get_battery_level(self, vacuum_entity_id: str) -> int:
        """Return current battery level from sensor first, then vacuum entity."""
        return _get_battery_level_impl(self.hass, vacuum_entity_id)

    # ------------------------------------------------------------------
    # Water model helpers + estimation -- delegates to RunPlanManager
    # ------------------------------------------------------------------

    def _normalize_water_level_key(self, value, *, aliases=None):
        """Delegate to RunPlanManager."""
        return self.run_plan._normalize_water_level_key(value, aliases=aliases)

    def _water_rate_ml_per_minute(self, water_level, *, aliases=None):
        """Delegate to RunPlanManager."""
        return self.run_plan._water_rate_ml_per_minute(water_level, aliases=aliases)

    def _get_station_clean_water_percent(self, *, vacuum_entity_id, capabilities=None):
        """Delegate to RunPlanManager."""
        return self.run_plan._get_station_clean_water_percent(
            vacuum_entity_id=vacuum_entity_id, capabilities=capabilities
        )

    def _get_water_model_config(self, *, vacuum_entity_id):
        """Delegate to RunPlanManager."""
        return self.run_plan._get_water_model_config(vacuum_entity_id=vacuum_entity_id)

    def _derive_wash_frequency_config(self, *, vacuum_entity_id):
        """Delegate to RunPlanManager."""
        return self.run_plan._derive_wash_frequency_config(vacuum_entity_id=vacuum_entity_id)

    def estimate_job_water_usage(self, **kwargs):
        """Delegate to RunPlanManager."""
        return self.run_plan.estimate_job_water_usage(**kwargs)

    # ------------------------------------------------------------------
    # Active job tracking — delegates to ActiveJobTracker
    # ------------------------------------------------------------------

    def _parse_job_timestamp(self, value):
        """Delegate to ActiveJobTracker."""
        return self.active_job._parse_job_timestamp(value)

    def _default_active_job_state(self, *, vacuum_entity_id: str, map_id: str):
        """Delegate to ActiveJobTracker."""
        return self.active_job._default_active_job_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)

    def _derive_active_job_current_room_id(self, active_job):
        """Delegate to ActiveJobTracker."""
        return self.active_job._derive_active_job_current_room_id(active_job)

    def _normalize_active_job(self, active_job):
        """Delegate to ActiveJobTracker."""
        return self.active_job._normalize_active_job(active_job)

    def _compute_current_room_elapsed_minutes(self, *, active_job, now=None):
        """Delegate to ActiveJobTracker."""
        return self.active_job._compute_current_room_elapsed_minutes(active_job=active_job, now=now)

    def _is_charging(self, vacuum_entity_id: str):
        """Delegate to ActiveJobTracker."""
        return self.active_job._is_charging(vacuum_entity_id)

    def _is_low_battery_return_state(self, *, current_battery, vacuum_state, task_status):
        """Delegate to ActiveJobTracker."""
        return self.active_job._is_low_battery_return_state(
            current_battery=current_battery,
            vacuum_state=vacuum_state,
            task_status=task_status,
        )

    def update_active_job_recharge_observation(self, **kwargs):
        """Record a recharge observation — delegates to ActiveJobTracker."""
        return self.active_job.update_active_job_recharge_observation(**kwargs)

    def update_active_job_mop_wash_observation(self, **kwargs):
        """Record a mop-wash observation — delegates to ActiveJobTracker."""
        return self.active_job.update_active_job_mop_wash_observation(**kwargs)

    def record_active_job_transition(self, **kwargs):
        """Append one state transition to the active job — delegates to ActiveJobTracker."""
        return self.active_job.record_active_job_transition(**kwargs)

    def _room_name_from_active_job(self, active_job, room_id):
        """Delegate to ActiveJobTracker."""
        return self.active_job._room_name_from_active_job(active_job, room_id)

    def _timing_completion_threshold_minutes(self, room):
        """Delegate to ActiveJobTracker."""
        return self.active_job._timing_completion_threshold_minutes(room)

    def _robot_outside_room_bounds(self, *, vacuum_entity_id: str, map_id: str, room_id: int):
        """Delegate to ActiveJobTracker."""
        return self.active_job._robot_outside_room_bounds(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=room_id,
        )

    def _maybe_roll_current_room_by_timing(self, **kwargs):
        """Delegate to ActiveJobTracker."""
        return self.active_job._maybe_roll_current_room_by_timing(**kwargs)

    def _get_robot_position(self, vacuum_entity_id: str):
        """Delegate to ActiveJobTracker."""
        return self.active_job._get_robot_position(vacuum_entity_id)

    def _access_graph_path(self, managed_rooms, from_room_id: int, to_room_id: int):
        """Delegate to ActiveJobTracker."""
        return self.active_job._access_graph_path(managed_rooms, from_room_id, to_room_id)

    def _detect_transition_room_from_position(self, *, vacuum_entity_id: str, map_id: str, from_room_id, to_room_id):
        """Delegate to ActiveJobTracker."""
        return self.active_job._detect_transition_room_from_position(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            from_room_id=from_room_id,
            to_room_id=to_room_id,
        )

    def _job_status_summary(self, *, active_job, lifecycle_state=None, progress_snapshot=None):
        """Delegate to ActiveJobTracker."""
        return self.active_job._job_status_summary(
            active_job=active_job,
            lifecycle_state=lifecycle_state,
            progress_snapshot=progress_snapshot,
        )



    def _find_button_entity_by_tokens(
        self,
        *,
        object_id: str,
        required_tokens: list[str],
    ) -> str | None:
        """Find a button entity for one vacuum by required tokens."""
        registry = er.async_get(self.hass)
        prefix = f"button.{object_id}_".lower()
        for entry in registry.entities.values():
            entity_id = str(entry.entity_id).lower()
            if not entity_id.startswith(prefix):
                continue
                if all(token in entity_id for token in required_tokens):
                    return entry.entity_id
        return None

    def _get_registry_model_code(
        self,
        *,
        vacuum_entity_id: str,
    ) -> str | None:
        """Return the upstream device-registry model code for one vacuum."""
        entity_entry = er.async_get(self.hass).async_get(vacuum_entity_id)
        if entity_entry is None or not entity_entry.device_id:
            return None

        device_entry = dr.async_get(self.hass).async_get(entity_entry.device_id)
        if device_entry is None:
            return None

        model = str(device_entry.model or "").strip()
        return model or None

    def _get_upkeep_model_meta(self, **kwargs):
        """Delegate to MaintenanceManager."""
        return self.maintenance._get_upkeep_model_meta(**kwargs)

    def _get_upkeep_item_guide(self, **kwargs):
        """Delegate to MaintenanceManager."""
        return self.maintenance._get_upkeep_item_guide(**kwargs)

    def _get_replacement_reset_entity(self, **kwargs):
        """Delegate to MaintenanceManager."""
        return self.maintenance._get_replacement_reset_entity(**kwargs)

    # ------------------------------------------------------------------
    # Dock actions — delegates to DockManager
    # ------------------------------------------------------------------

    def get_dock_action_status(self, **kwargs) -> dict[str, Any]:
        """Return gated dock-action state — delegates to DockManager."""
        return self.dock.get_dock_action_status(**kwargs)

    async def async_wash_mop(self, **kwargs) -> dict[str, Any]:
        """Run gated wash-mop action — delegates to DockManager."""
        return await self.dock.async_wash_mop(**kwargs)

    async def async_dry_mop(self, **kwargs) -> dict[str, Any]:
        """Run gated dry-mop action — delegates to DockManager."""
        return await self.dock.async_dry_mop(**kwargs)

    async def async_empty_dust(self, **kwargs) -> dict[str, Any]:
        """Run gated empty-dust action — delegates to DockManager."""
        return await self.dock.async_empty_dust(**kwargs)

    async def async_stop_dry_mop(self, **kwargs) -> dict[str, Any]:
        """Run gated stop-dry-mop action — delegates to DockManager."""
        return await self.dock.async_stop_dry_mop(**kwargs)

    def _generate_job_id(self) -> str:
        """Delegate to ActiveJobTracker."""
        return self.active_job._generate_job_id()

    def ensure_vacuum_record(
        self,
        *,
        vacuum_entity_id: str,
        detected_model: str | None = None,
    ) -> dict[str, Any]:
        """Ensure managed vacuum record exists."""
        self.data.setdefault("vacuums", {})
        registry_model = self._get_registry_model_code(vacuum_entity_id=vacuum_entity_id)
        effective_model = detected_model or registry_model
        record = self.data["vacuums"].setdefault(
            vacuum_entity_id,
            {
                "vacuum_entity_id": vacuum_entity_id,
                "detected_model": effective_model,
                "is_managed": True,
            },
        )

        if detected_model:
            record["detected_model"] = detected_model
        elif not record.get("detected_model") and registry_model:
            record["detected_model"] = registry_model

        return record

    def get_managed_vacuums(self) -> dict[str, Any]:
        """Return summary of managed vacuums."""
        self.data.setdefault("vacuums", {})

        items: list[dict[str, Any]] = []
        for vacuum_entity_id, record in sorted(self.data["vacuums"].items()):
            capabilities = self.data.get("capabilities", {}).get(vacuum_entity_id, {})
            items.append(
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "detected_model": record.get("detected_model"),
                    "is_managed": bool(record.get("is_managed", True)),
                    "supports_rooms": capabilities.get("supports_rooms"),
                    "supports_mop_features": capabilities.get("supports_mop_features"),
                    "supports_active_map": capabilities.get("supports_active_map"),
                    "supports_robot_position": capabilities.get("supports_robot_position"),
                }
            )

        return {
            "vacuum_count": len(items),
            "vacuums": items,
        }

    def refresh_vacuum_capabilities(
        self,
        *,
        vacuum_entity_id: str,
        detected_model: str | None = None,
    ) -> dict[str, Any]:
        """Detect and store capabilities for one vacuum."""
        record = self.ensure_vacuum_record(
            vacuum_entity_id=vacuum_entity_id,
            detected_model=detected_model,
        )
        self.data.setdefault("capabilities", {})

        registry_model = self._get_registry_model_code(vacuum_entity_id=vacuum_entity_id)
        effective_model = detected_model or record.get("detected_model") or registry_model

        # Build detect_capabilities inputs from the adapter registry so the
        # refresh uses the same entity candidates and model hints as startup.
        # Falls back gracefully (empty candidates, no hints) if the adapter
        # is not registered — detect_capabilities returns a minimal result.
        _adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        _adapter_entities = _adapter_cfg.get("entities", {})
        _entity_candidates: dict[str, list[str]] = {
            k: [v] for k, v in _adapter_entities.items() if v
        }
        _capability_hints: dict[str, bool] = {
            k: bool(v)
            for k, v in _adapter_cfg.get("capabilities", {}).items()
            if isinstance(v, bool)
        }
        _maintenance_components = _adapter_cfg.get("maintenance_components") or None

        payload = detect_capabilities(
            self.hass,
            vacuum_entity_id=vacuum_entity_id,
            detected_model=effective_model,
            entity_candidates=_entity_candidates or None,
            capability_hints=_capability_hints or None,
            maintenance_components=_maintenance_components,
        )

        if effective_model:
            payload["detected_model"] = effective_model
            record["detected_model"] = effective_model

        self.data["capabilities"][vacuum_entity_id] = payload
        return payload

    def get_vacuum_capabilities(
        self,
        *,
        vacuum_entity_id: str,
        detected_model: str | None = None,
        refresh: bool = True,
    ) -> dict[str, Any]:
        """Return stored or freshly detected capabilities for one vacuum.

        When no stored snapshot exists yet, detection runs even if
        ``refresh=False`` so the capability snapshot is always available
        after restart without requiring a manual refresh.
        """
        record = self.ensure_vacuum_record(
            vacuum_entity_id=vacuum_entity_id,
            detected_model=detected_model,
        )
        self.data.setdefault("capabilities", {})

        stored = self.data["capabilities"].get(vacuum_entity_id)
        registry_model = self._get_registry_model_code(vacuum_entity_id=vacuum_entity_id)
        effective_model = detected_model or record.get("detected_model") or registry_model

        if refresh or stored is None:
            return self.refresh_vacuum_capabilities(
                vacuum_entity_id=vacuum_entity_id,
                detected_model=effective_model,
            )

        if effective_model and not stored.get("detected_model"):
            return self.refresh_vacuum_capabilities(
                vacuum_entity_id=vacuum_entity_id,
                detected_model=effective_model,
            )

        return stored

    def ensure_runtime(self, vacuum_entity_id: str) -> VacuumRuntimeState:
        """Ensure runtime state exists for one vacuum."""
        if vacuum_entity_id not in self.runtime:
            self.runtime[vacuum_entity_id] = VacuumRuntimeState(
                vacuum_entity_id=vacuum_entity_id,
            )
        return self.runtime[vacuum_entity_id]

    # ------------------------------------------------------------------
    # Room profiles — delegates to ProfileManager
    # ------------------------------------------------------------------

    def get_room_profiles(self) -> dict[str, Any]:
        """Return available room profiles — delegates to ProfileManager."""
        return self.profiles.get_room_profiles()

    def get_effective_room_details(self, **kwargs):
        """Return resolved room settings — delegates to ProfileManager."""
        return self.profiles.get_effective_room_details(**kwargs)

    def save_user_room_profile(self, **kwargs) -> dict[str, Any]:
        """Save one custom room profile — delegates to ProfileManager."""
        return self.profiles.save_user_room_profile(**kwargs)

    def overwrite_room_profile(self, **kwargs) -> dict[str, Any]:
        """Overwrite one custom room profile — delegates to ProfileManager."""
        return self.profiles.overwrite_room_profile(**kwargs)

    def save_room_profile_from_room(self, **kwargs) -> dict[str, Any]:
        """Save profile from room settings — delegates to ProfileManager."""
        return self.profiles.save_room_profile_from_room(**kwargs)

    def overwrite_room_profile_from_room(self, **kwargs) -> dict[str, Any]:
        """Overwrite profile from room settings — delegates to ProfileManager."""
        return self.profiles.overwrite_room_profile_from_room(**kwargs)

    def rename_room_profile(self, **kwargs) -> dict[str, Any]:
        """Rename one custom room profile — delegates to ProfileManager."""
        return self.profiles.rename_room_profile(**kwargs)

    def delete_room_profile(self, **kwargs) -> dict[str, Any]:
        """Delete one custom room profile — delegates to ProfileManager."""
        return self.profiles.delete_room_profile(**kwargs)

    def apply_room_profile(self, **kwargs) -> dict[str, Any]:
        """Apply a room profile to rooms — delegates to ProfileManager."""
        return self.profiles.apply_room_profile(**kwargs)

    # Private shims: used by update_room_fields and run-planning methods.
    def _protected_room_config(self, room: dict) -> dict:
        return self.profiles._protected_room_config(room)

    def _match_profile_from_fields(self, room: dict) -> str | None:
        return self.profiles._match_profile_from_fields(room)

    def _finalize_room_update(self, room: dict) -> dict:
        return self.profiles._finalize_room_update(room)

    def update_room_fields(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        enabled: bool | None = None,
        clean_mode: str | None = None,
        fan_speed: str | None = None,
        water_level: str | None = None,
        clean_intensity: str | None = None,
        clean_passes: int | None = None,
        edge_mopping: bool | None = None,
        is_dock_room: bool | None = None,
        is_transition: bool | None = None,
        grants_access_to: list[int] | list[str] | None = None,
        rules: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Apply per-room field overrides and persist the result.

        Protection rules enforce carpet/mop invariants before the room is saved.
        Returns an error payload (``ok=False``) if the access-graph changes are
        structurally illegal; completeness issues (no dock room, unreachable rooms)
        are only enforced at queue-build time.
        """
        map_bucket = ensure_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        rooms = map_bucket.get("rooms", {})
        room_key = str(int(room_id))
        room = rooms.get(room_key)

        if room is None:
            return {
                "ok": False,
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "updated": False,
                "error": "room_not_found",
                "reason": "room_not_found",
                "reason_detail": "The selected room was not found on this map.",
            }

        updates: dict[str, Any] = {}

        if enabled is not None:
            updates["enabled"] = bool(enabled)

        if clean_mode is not None:
            updates["clean_mode"] = str(clean_mode)

        if fan_speed is not None:
            updates["fan_speed"] = str(fan_speed)

        if water_level is not None:
            updates["water_level"] = str(water_level)

        if clean_intensity is not None:
            updates["clean_intensity"] = str(clean_intensity)

        if clean_passes is not None:
            updates["clean_passes"] = int(clean_passes)

        if edge_mopping is not None:
            updates["edge_mopping"] = bool(edge_mopping)

        if is_dock_room is not None:
            updates["is_dock_room"] = bool(is_dock_room)

        if is_transition is not None:
            updates["is_transition"] = bool(is_transition)

        if grants_access_to is not None:
            updates["grants_access_to"] = self._normalize_grants_access_to(
                grants_access_to,
                room_id=int(room_id),
            )

        if rules is not None:
            updates["rules"] = self._normalize_room_rules(rules)

        updated_room = self._finalize_room_update({**room, **updates})

        previous_room = dict(room)
        rooms[room_key] = updated_room

        validation = self._validate_room_access_graph(managed_rooms=rooms)

        structural_issues = self._structural_access_graph_issues(validation)

        if structural_issues:
            rooms[room_key] = previous_room
            room_names = {
                _safe_int(item.get("room_id", key), -1): str(item.get("name", f"Room {_safe_int(item.get('room_id', key), -1)}")).strip() or f"Room {_safe_int(item.get('room_id', key), -1)}"
                for key, item in rooms.items()
                if isinstance(item, dict) and _safe_int(item.get("room_id", key), -1) > 0
            }
            return {
                "ok": False,
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "updated": False,
                "error": "invalid_access_graph",
                "reason": "invalid_access_graph",
                "reason_detail": "The requested access links would make the graph invalid.",
                "issues": [
                    self._format_access_graph_issue(issue=issue, room_names=room_names)
                    for issue in structural_issues
                ],
            }

        map_bucket["rooms"] = rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)
        self._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        self._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        return {
            "ok": True,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": int(room_id),
            "updated": True,
            "profile_name": updated_room["profile_name"],
                "room": rooms[room_key],
        }

    # ------------------------------------------------------------------
    # Room / map management
    # ------------------------------------------------------------------

    def discover_rooms(self, **kwargs) -> dict:
        """Delegate to RoomMapManager."""
        return self.room_map.discover_rooms(**kwargs)

    def save_managed_rooms(self, **kwargs) -> dict:
        """Delegate to RoomMapManager."""
        return self.room_map.save_managed_rooms(**kwargs)

    def get_managed_rooms(self, **kwargs) -> dict:
        """Delegate to RoomMapManager."""
        return self.room_map.get_managed_rooms(**kwargs)

    def remove_map(self, **kwargs) -> dict:
        """Delegate to RoomMapManager."""
        return self.room_map.remove_map(**kwargs)

    def get_vacuum_maps(self, **kwargs) -> dict:
        """Delegate to RoomMapManager."""
        return self.room_map.get_vacuum_maps(**kwargs)

    def rebuild_map(self, **kwargs) -> dict:
        """Delegate to RoomMapManager."""
        return self.room_map.rebuild_map(**kwargs)

    # ------------------------------------------------------------------
    # Queue / payload building
    # ------------------------------------------------------------------

    def build_queue(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Build queue from enabled rooms in one map."""
        map_bucket = get_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        managed_rooms = map_bucket.get("rooms", {})

        payload = build_queue_from_managed_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=managed_rooms,
        )

        self.data.setdefault("queue", {})
        self.data["queue"].setdefault(vacuum_entity_id, {})
        self.data["queue"][vacuum_entity_id][str(map_id)] = payload

        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.selected_map_id = str(map_id)
        runtime.queue_room_ids = payload.get("queue_room_ids", [])

        return payload

    def set_rooms_enabled_subset(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_ids: list[int] | list[str],
    ) -> dict[str, Any]:
        """Enable only the specified rooms and disable all others on the map.

        Does not change any other room settings.  Rebuilds the queue summary
        and fires the rooms-updated notification.  Returns a summary dict with
        ``enabled_count`` and ``total_count``.
        """
        map_bucket = ensure_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        rooms = map_bucket.get("rooms", {})
        if not isinstance(rooms, dict):
            rooms = {}

        wanted: set[str] = {str(int(rid)) for rid in room_ids if str(rid).strip()}

        for room_key, room_data in list(rooms.items()):
            if not isinstance(room_data, dict):
                continue
            rooms[room_key] = {**room_data, "enabled": room_key in wanted}

        map_bucket["rooms"] = rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)

        self._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        enabled_count = sum(
            1 for r in rooms.values() if isinstance(r, dict) and r.get("enabled")
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "enabled_count": enabled_count,
            "total_count": len(rooms),
            "wanted_room_ids": sorted(wanted),
        }

    def get_queue_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return queue state for one vacuum/map."""
        return (
            self.data.get("queue", {})
            .get(vacuum_entity_id, {})
            .get(
                str(map_id),
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "room_count": 0,
                    "queue_room_ids": [],
                    "queue_rooms": [],
                },
            )
        )

    def clear_queue(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Clear queue state for one vacuum/map."""
        self.data.setdefault("queue", {})
        self.data["queue"].setdefault(vacuum_entity_id, {})
        self.data["queue"][vacuum_entity_id][str(map_id)] = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_count": 0,
            "queue_room_ids": [],
            "queue_rooms": [],
        }

        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.queue_room_ids = []

        return self.get_queue_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

    # ------------------------------------------------------------------
    # Run profiles — delegates to ProfileManager
    # ------------------------------------------------------------------

    def get_saved_run_profiles(self, **kwargs) -> dict[str, Any]:
        """Return saved run profiles — delegates to ProfileManager."""
        return self.profiles.get_saved_run_profiles(**kwargs)

    def save_run_profile(self, **kwargs) -> dict[str, Any]:
        """Save current room selection as run profile — delegates to ProfileManager."""
        return self.profiles.save_run_profile(**kwargs)

    def overwrite_run_profile(self, **kwargs) -> dict[str, Any]:
        """Overwrite one saved run profile — delegates to ProfileManager."""
        return self.profiles.overwrite_run_profile(**kwargs)

    def rename_run_profile(self, **kwargs) -> dict[str, Any]:
        """Rename one saved run profile — delegates to ProfileManager."""
        return self.profiles.rename_run_profile(**kwargs)

    def delete_run_profile(self, **kwargs) -> dict[str, Any]:
        """Delete one saved run profile — delegates to ProfileManager."""
        return self.profiles.delete_run_profile(**kwargs)

    def apply_run_profile(self, **kwargs) -> dict[str, Any]:
        """Apply a saved run profile to room settings — delegates to ProfileManager."""
        return self.profiles.apply_run_profile(**kwargs)

    # ------------------------------------------------------------------
    # Access graph — delegates to AccessGraphManager
    # ------------------------------------------------------------------

    def _normalize_grants_access_to(self, raw_value, *, room_id: int):
        """Delegate to AccessGraphManager."""
        return self.access_graph._normalize_grants_access_to(raw_value, room_id=room_id)

    def _normalize_room_rules(self, raw_rules):
        """Delegate to AccessGraphManager."""
        return self.access_graph._normalize_room_rules(raw_rules)

    def _validate_room_access_graph(self, *, managed_rooms):
        """Delegate to AccessGraphManager."""
        return self.access_graph._validate_room_access_graph(managed_rooms=managed_rooms)

    def _structural_access_graph_issues(self, validation):
        """Delegate to AccessGraphManager."""
        return self.access_graph._structural_access_graph_issues(validation)

    def _format_access_graph_issue(self, *, issue, room_names):
        """Delegate to AccessGraphManager."""
        return self.access_graph._format_access_graph_issue(issue=issue, room_names=room_names)

    def _normalized_managed_rooms_with_automation(self, *, vacuum_entity_id: str, map_id: str):
        """Delegate to AccessGraphManager."""
        return self.access_graph._normalized_managed_rooms_with_automation(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

    def _build_room_access_views(self, *, managed_rooms):
        """Delegate to AccessGraphManager."""
        return self.access_graph._build_room_access_views(managed_rooms=managed_rooms)

    def _access_graph_state(self, managed_rooms=None, validation=None, **kwargs):
        """Delegate to AccessGraphManager."""
        _rooms = managed_rooms if managed_rooms is not None else kwargs.get("managed_rooms")
        return self.access_graph._access_graph_state(_rooms, validation)

    def _any_rooms_have_rules(self, managed_rooms=None, **kwargs):
        """Delegate to AccessGraphManager."""
        _rooms = managed_rooms if managed_rooms is not None else kwargs.get("managed_rooms")
        return self.access_graph._any_rooms_have_rules(_rooms)

    def _room_rule_matches(self, rule):
        """Delegate to AccessGraphManager."""
        return self.access_graph._room_rule_matches(rule)

    def get_room_access_editor(self, **kwargs):
        """Return access editor payload — delegates to AccessGraphManager."""
        return self.access_graph.get_room_access_editor(**kwargs)

    def get_access_graph_health(self, **kwargs):
        """Return access graph health — delegates to AccessGraphManager."""
        return self.access_graph.get_access_graph_health(**kwargs)


    # ------------------------------------------------------------------
    # Run planning -- delegates to RunPlanManager
    # ------------------------------------------------------------------

    def _room_estimate_minutes_map(self, *, vacuum_entity_id, map_id):
        """Delegate to RunPlanManager."""
        return self.run_plan._room_estimate_minutes_map(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id
        )

    def _build_blocked_room_entry(self, **kwargs):
        """Delegate to RunPlanManager."""
        return self.run_plan._build_blocked_room_entry(**kwargs)

    def get_runtime_path_block_report(self, **kwargs):
        """Delegate to RunPlanManager."""
        return self.run_plan.get_runtime_path_block_report(**kwargs)

    def _build_modified_room_entry(self, **kwargs):
        """Delegate to RunPlanManager."""
        return self.run_plan._build_modified_room_entry(**kwargs)

    def _confirmation_token_for_preflight(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        selected_room_ids,
        included_room_ids,
        blocked_room_ids,
    ):
        """Delegate to RunPlanManager."""
        return self.run_plan._confirmation_token_for_preflight(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            selected_room_ids=selected_room_ids,
            included_room_ids=included_room_ids,
            blocked_room_ids=blocked_room_ids,
        )

    def _update_room_rule_status_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        managed_rooms: dict[str, dict[str, Any]],
        selected_room_ids: list[int],
        included_room_ids: list[int],
        blocked_rooms: list[dict[str, Any]],
        modified_rooms: list[dict[str, Any]],
        preflight: dict[str, Any],
    ) -> None:
        """Store a per-room rule/preflight evaluation snapshot and fire the update callback."""
        selected_set = {int(room_id) for room_id in selected_room_ids}
        included_set = {int(room_id) for room_id in included_room_ids}
        blocked_by_room_id: dict[int, dict[str, Any]] = {
            _safe_int(item.get("room_id"), -1): item
            for item in blocked_rooms
            if isinstance(item, dict) and _safe_int(item.get("room_id"), -1) > 0
        }
        modified_by_room_id: dict[int, dict[str, Any]] = {
            _safe_int(item.get("room_id"), -1): item
            for item in modified_rooms
            if isinstance(item, dict) and _safe_int(item.get("room_id"), -1) > 0
        }

        evaluation_at = _iso_now()
        status_root = self.data.setdefault("room_rule_status", {})
        vacuum_status = status_root.setdefault(vacuum_entity_id, {})
        map_status = vacuum_status.setdefault(str(map_id), {})

        changed = False
        for room_key, room in managed_rooms.items():
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room_key), -1)
            if room_id <= 0:
                continue

            blocked = blocked_by_room_id.get(room_id)
            modified = modified_by_room_id.get(room_id)
            selected = room_id in selected_set
            included = room_id in included_set

            if not selected:
                result = "not_selected"
            elif blocked and modified:
                result = "blocked_and_modified"
            elif blocked:
                result = "blocked"
            elif modified:
                result = "modified"
            else:
                result = "allowed"

            prior = map_status.get(str(room_id), {})
            next_entry: dict[str, Any] = {
                "room_id": room_id,
                "map_id": str(map_id),
                "room_name": str(room.get("name", f"Room {room_id}")).strip() or f"Room {room_id}",
                "last_evaluated_at": evaluation_at,
                "last_result": result,
                "last_selected": selected,
                "last_included": included,
                "last_block_reason": blocked.get("reason") if blocked else None,
                "last_block_source": blocked.get("source") if blocked else None,
                "last_blocked_by_room_id": (
                    str(blocked.get("blocked_by_room_id"))
                    if blocked and blocked.get("blocked_by_room_id") not in (None, "")
                    else None
                ),
                "last_blocked_by_room_name": blocked.get("blocked_by_room_name") if blocked else None,
                "last_triggered_rule_ids": sorted(
                    {
                        str(v)
                        for v in (
                            ([blocked.get("triggered_rule_id")] if blocked and blocked.get("triggered_rule_id") else [])
                            + (list(modified.get("triggered_rule_ids", [])) if modified else [])
                        )
                        if str(v).strip()
                    }
                ),
                "last_modifier_changes": dict(modified.get("changes", {})) if modified else {},
                "last_requires_confirmation": bool(preflight.get("requires_confirmation", False)),
                "last_preflight_reason": str(preflight.get("reason", "ready")).strip() or "ready",
                "last_warning_codes": (
                    list(preflight.get("warnings", []))
                    if isinstance(preflight.get("warnings"), list)
                    else []
                ),
                "last_evaluation_scope": "start_preflight",
            }

            if next_entry != prior:
                map_status[str(room_id)] = next_entry
                changed = True

        if changed:
            self._notify_room_rule_status_updated(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )

    def get_room_rule_status(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int | str,
    ) -> dict[str, Any]:
        """Return the latest stored rule/preflight evaluation status for one room."""
        map_id_str = str(map_id)
        room_id_int = _safe_int(room_id, -1)
        room = (
            self.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(map_id_str, {})
            .get("rooms", {})
            .get(str(room_id_int), {})
        )
        room_name = str(room.get("name", f"Room {room_id_int}")).strip() or f"Room {room_id_int}"

        entry = (
            self.data.get("room_rule_status", {})
            .get(vacuum_entity_id, {})
            .get(map_id_str, {})
            .get(str(room_id_int), {})
        )
        if not isinstance(entry, dict):
            entry = {}

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_str,
            "room_id": str(room_id_int),
            "room_name": room_name,
            "last_evaluated_at": entry.get("last_evaluated_at"),
            "last_result": entry.get("last_result", "never"),
            "last_selected": bool(entry.get("last_selected", False)),
            "last_included": bool(entry.get("last_included", False)),
            "last_block_reason": entry.get("last_block_reason"),
            "last_block_source": entry.get("last_block_source"),
            "last_blocked_by_room_id": entry.get("last_blocked_by_room_id"),
            "last_blocked_by_room_name": entry.get("last_blocked_by_room_name"),
            "last_triggered_rule_ids": (
                list(entry.get("last_triggered_rule_ids", []))
                if isinstance(entry.get("last_triggered_rule_ids"), list)
                else []
            ),
            "last_modifier_changes": (
                dict(entry.get("last_modifier_changes", {}))
                if isinstance(entry.get("last_modifier_changes"), dict)
                else {}
            ),
            "last_requires_confirmation": bool(entry.get("last_requires_confirmation", False)),
            "last_preflight_reason": entry.get("last_preflight_reason"),
            "last_warning_codes": (
                list(entry.get("last_warning_codes", []))
                if isinstance(entry.get("last_warning_codes"), list)
                else []
            ),
            "last_evaluation_scope": entry.get("last_evaluation_scope"),
        }

    # ------------------------------------------------------------------
    # Room history cache and accessors
    # ------------------------------------------------------------------

    @staticmethod
    def _room_mode_uses_vacuum(clean_mode: Any) -> bool:
        """Return whether one room clean mode includes vacuuming."""
        mode = str(clean_mode or "").strip().lower()
        return mode in {"vacuum", "vacuum_mop"} or "vacuum" in mode

    @staticmethod
    def _room_mode_uses_mop(clean_mode: Any) -> bool:
        """Return whether one room clean mode includes mopping."""
        mode = str(clean_mode or "").strip().lower()
        return mode in {"mop", "vacuum_mop"} or "mop" in mode

    def _ensure_room_history_cache(self, *, vacuum_entity_id: str) -> None:
        """Schedule a room-history cache preload if one is not already in progress."""
        vacuum_key = str(vacuum_entity_id)
        if vacuum_key in self._room_history_cache_ready:
            return
        if vacuum_key in self._room_history_cache_loading:
            return
        self.hass.async_create_task(
            self.async_preload_room_history_cache(vacuum_entity_id=vacuum_key)
        )

    def _load_room_history_cache_sync(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Build and return room-history data from the learning store (executor thread).

        All state is local until the caller writes the result back to self.data
        on the event loop.
        """
        vacuum_key = str(vacuum_entity_id)
        temp_root: dict[str, Any] = {vacuum_key: {}}
        try:
            from ..learning.history_store import LearningHistoryStore

            store = LearningHistoryStore(self.hass)
            index_payload = store.load_jobs_index(vacuum_entity_id=vacuum_key)
            entries = (
                index_payload.get("jobs", [])
                if isinstance(index_payload, dict)
                else []
            )
            _is_old_index_format = (
                isinstance(entries, list)
                and bool(entries)
                and isinstance(entries[0], dict)
                and "rooms" in entries[0]
                and "status" not in entries[0]
            )
            loaded_from_index = False

            if _is_old_index_format:
                for entry in entries:
                    self._ingest_jobs_index_entry_into_room_history(
                        vacuum_entity_id=vacuum_key,
                        index_entry=entry,
                        _history_root=temp_root,
                    )
                loaded_from_index = True

            if not loaded_from_index:
                completed_jobs = store.load_all_completed_jobs(
                    vacuum_entity_id=vacuum_key,
                )
                for completed_job in completed_jobs:
                    self._ingest_completed_job_into_room_history(
                        vacuum_entity_id=vacuum_key,
                        completed_job=completed_job,
                        _history_root=temp_root,
                    )
        except Exception:
            _LOGGER.exception(
                "Failed rebuilding room history cache for %s", vacuum_key
            )
        return temp_root.get(vacuum_key, {})

    async def async_preload_room_history_cache(
        self,
        *,
        vacuum_entity_id: str,
    ) -> None:
        """Load one vacuum's room-history cache without blocking the event loop."""
        vacuum_key = str(vacuum_entity_id)
        if vacuum_key in self._room_history_cache_ready:
            return
        if vacuum_key in self._room_history_cache_loading:
            return
        self._room_history_cache_loading.add(vacuum_key)
        try:
            vacuum_history = await self.hass.async_add_executor_job(
                self._load_room_history_cache_sync,
                vacuum_key,
            )
            self.data.setdefault("room_history", {})[vacuum_key] = vacuum_history
            self._room_history_cache_ready.add(vacuum_key)
            map_ids = list(
                self.data.get("room_history", {}).get(vacuum_key, {}).keys()
            ) or ["unknown"]
            for map_id in map_ids:
                self._notify_room_history_updated(
                    vacuum_entity_id=vacuum_key,
                    map_id=str(map_id),
                )
        finally:
            self._room_history_cache_loading.discard(vacuum_key)

    def _ingest_jobs_index_entry_into_room_history(
        self,
        *,
        vacuum_entity_id: str,
        index_entry: dict[str, Any],
        _history_root: dict[str, Any] | None = None,
    ) -> bool:
        """Merge one jobs-index entry into the room-history cache."""
        if not isinstance(index_entry, dict):
            return False
        ended_at = str(index_entry.get("ended_at") or "").strip()
        ended_dt = parse_timestamp(ended_at)
        if ended_dt is None:
            return False
        map_id = str(index_entry.get("map_id") or "unknown")
        rooms = index_entry.get("rooms", [])
        if not isinstance(rooms, list):
            return False
        history_root = (
            _history_root if _history_root is not None
            else self.data.setdefault("room_history", {})
        )
        vacuum_history = history_root.setdefault(str(vacuum_entity_id), {})
        map_history = vacuum_history.setdefault(map_id, {})
        updated = False
        for room in rooms:
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room.get("id")), -1)
            if room_id <= 0:
                continue
            room_key = str(room_id)
            current = dict(map_history.get(room_key, {}))
            room_name = (
                str(room.get("room_name", room.get("name", current.get("room_name", f"Room {room_id}")))).strip()
                or f"Room {room_id}"
            )

            def _is_newer_idx(field_name: str) -> bool:
                existing_dt = parse_timestamp(current.get(field_name))
                return existing_dt is None or ended_dt >= existing_dt

            next_entry = dict(current)
            next_entry["room_id"] = room_id
            next_entry["map_id"] = map_id
            next_entry["room_name"] = room_name
            if room.get("last_cleaned_at") and _is_newer_idx("last_cleaned_at"):
                next_entry["last_cleaned_at"] = room["last_cleaned_at"]
                next_entry["last_job_mode"] = room.get("clean_mode")
            if room.get("last_vacuumed_at") and _is_newer_idx("last_vacuumed_at"):
                next_entry["last_vacuumed_at"] = room["last_vacuumed_at"]
            if room.get("last_mopped_at") and _is_newer_idx("last_mopped_at"):
                next_entry["last_mopped_at"] = room["last_mopped_at"]
            if next_entry != current:
                map_history[room_key] = next_entry
                updated = True
        return updated

    def _ingest_completed_job_into_room_history(
        self,
        *,
        vacuum_entity_id: str,
        completed_job: dict[str, Any],
        _history_root: dict[str, Any] | None = None,
    ) -> bool:
        """Merge one successful completed job into the room-history cache."""
        if not isinstance(completed_job, dict):
            return False
        if str(completed_job.get("record_type", "")).strip().lower() != "completed_job":
            return False
        outcome = completed_job.get("outcome", {})
        if not isinstance(outcome, dict):
            return False
        if str(outcome.get("status", "")).strip().lower() != "completed":
            return False
        job_info = completed_job.get("job", {})
        if not isinstance(job_info, dict):
            job_info = {}
        ended_at = str(
            job_info.get("ended_at") or completed_job.get("finalized_at") or ""
        ).strip()
        ended_dt = parse_timestamp(ended_at)
        if ended_dt is None:
            return False
        map_id = str(
            completed_job.get("job_profile", {}).get("map_id")
            or completed_job.get("queue", {}).get("map_id")
            or "unknown"
        )
        resolved_rooms = completed_job.get("resolved_rooms", [])
        if not isinstance(resolved_rooms, list):
            return False
        history_root = (
            _history_root if _history_root is not None
            else self.data.setdefault("room_history", {})
        )
        vacuum_history = history_root.setdefault(str(vacuum_entity_id), {})
        map_history = vacuum_history.setdefault(map_id, {})
        updated = False
        for room in resolved_rooms:
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room.get("id")), -1)
            if room_id <= 0:
                continue
            room_key = str(room_id)
            current = dict(map_history.get(room_key, {}))
            room_name = (
                str(room.get("name", current.get("room_name", f"Room {room_id}"))).strip()
                or f"Room {room_id}"
            )
            clean_mode = str(room.get("clean_mode", "")).strip().lower() or None

            def _is_newer_job(field_name: str) -> bool:
                existing_dt = parse_timestamp(current.get(field_name))
                return existing_dt is None or ended_dt >= existing_dt

            next_entry = dict(current)
            next_entry["room_id"] = room_id
            next_entry["map_id"] = map_id
            next_entry["room_name"] = room_name
            if _is_newer_job("last_cleaned_at"):
                next_entry["last_cleaned_at"] = ended_at
                next_entry["last_job_mode"] = clean_mode
            if clean_mode and self._room_mode_uses_vacuum(clean_mode) and _is_newer_job("last_vacuumed_at"):
                next_entry["last_vacuumed_at"] = ended_at
            if clean_mode and self._room_mode_uses_mop(clean_mode) and _is_newer_job("last_mopped_at"):
                next_entry["last_mopped_at"] = ended_at
            if next_entry != current:
                map_history[room_key] = next_entry
                updated = True
        return updated

    def get_room_cleaning_history(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int | str,
    ) -> dict[str, Any]:
        """Return the current cleaning-history summary for one room."""
        self._ensure_room_history_cache(vacuum_entity_id=vacuum_entity_id)
        map_id_str = str(map_id)
        room_id_int = _safe_int(room_id, -1)
        room = (
            self.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(map_id_str, {})
            .get("rooms", {})
            .get(str(room_id_int), {})
        )
        room_name = str(room.get("name", f"Room {room_id_int}")).strip() or f"Room {room_id_int}"
        entry = (
            self.data.get("room_history", {})
            .get(vacuum_entity_id, {})
            .get(map_id_str, {})
            .get(str(room_id_int), {})
        )
        if not isinstance(entry, dict):
            entry = {}
        now_dt = parse_timestamp(_iso_now())

        def _hours_since(timestamp_value: Any) -> float | None:
            if now_dt is None:
                return None
            value_dt = parse_timestamp(timestamp_value)
            if value_dt is None:
                return None
            return round(max((now_dt - value_dt).total_seconds() / 3600.0, 0.0), 2)

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_str,
            "room_id": str(room_id_int),
            "room_name": room_name,
            "last_cleaned_at": entry.get("last_cleaned_at"),
            "last_vacuumed_at": entry.get("last_vacuumed_at"),
            "last_mopped_at": entry.get("last_mopped_at"),
            "hours_since_last_vacuum": _hours_since(entry.get("last_vacuumed_at")),
            "hours_since_last_mop": _hours_since(entry.get("last_mopped_at")),
            "last_job_mode": entry.get("last_job_mode"),
        }

    def _build_effective_start_plan(self, *, vacuum_entity_id, map_id):
        """Delegate to RunPlanManager."""
        return self.run_plan._build_effective_start_plan(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id
        )

    # ------------------------------------------------------------------
    # Lifecycle / start status
    # ------------------------------------------------------------------

    def build_room_payload(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Build room_clean payload from one map's queue."""
        map_bucket = get_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        # Enforce carpet/mop invariants on every room before passing to the payload builder.
        managed_rooms = {
            room_id: self._protected_room_config(room_data)
            for room_id, room_data in map_bucket.get("rooms", {}).items()
        }

        queue_state = self.get_queue_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        queue_room_ids = queue_state.get("queue_room_ids", [])
        stored_profiles = self.data.get("profiles", {}).get("room_profiles", {})
        capabilities = self.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )

        _dispatch_cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        payload = get_dispatch_engine(_dispatch_cfg.get("template")).build_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=managed_rooms,
            queue_room_ids=queue_room_ids,
            stored_profiles=stored_profiles,
            capabilities=capabilities,
            dispatch=_dispatch_cfg,
        )

        self.data.setdefault("payloads", {})
        self.data["payloads"].setdefault(vacuum_entity_id, {})
        self.data["payloads"][vacuum_entity_id][str(map_id)] = payload

        return payload

    def get_payload_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return payload state for one vacuum/map."""
        payload_state = dict(
            self.data.get("payloads", {})
            .get(vacuum_entity_id, {})
            .get(
                str(map_id),
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "payload": {"map_id": str(map_id), "rooms": []},
                    "resolved_rooms": [],
                    "room_count": 0,
                },
        )
        )

        resolved_rooms = payload_state.get("resolved_rooms", [])
        if isinstance(resolved_rooms, list):
            enriched_rooms: list[dict[str, Any]] = []
            for room in resolved_rooms:
                if not isinstance(room, dict):
                    continue
                enriched = dict(room)
                enriched.update(
                    _settings_profile_display(
                        room_name=enriched.get("name") or enriched.get("slug"),
                        selected_profile_name=enriched.get("selected_profile_name"),
                        resolved_profile_name=enriched.get("resolved_profile_name"),
                        clean_mode=enriched.get("clean_mode"),
                        clean_intensity=enriched.get("clean_intensity"),
                        fan_speed=enriched.get("fan_speed"),
                        water_level=enriched.get("water_level"),
                        path_type=enriched.get("path_type"),
                        clean_passes=enriched.get("clean_passes", enriched.get("clean_times", 1)),
                        edge_mopping=enriched.get("edge_mopping"),
                    )
                )
                enriched.update(
                    _room_surface_labels(
                        floor_type=enriched.get("floor_type"),
                    )
                )
                enriched_rooms.append(enriched)
            payload_state["resolved_rooms"] = enriched_rooms

        return payload_state

    def get_lifecycle_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        hard_service_states: frozenset[str] | None = None,
        drying_states: frozenset[str] | None = None,
        active_run_task_states: frozenset[str] | None = None,
        active_vacuum_states: frozenset[str] | None = None,
    ) -> dict[str, Any]:
        """Return normalized lifecycle state for one vacuum/map."""
        # Read vocabulary from adapter registry when not supplied by caller.
        # Callers that pass explicit sets (e.g. __init__.py lifecycle listener)
        # bypass this lookup — their values take precedence.
        if any(v is None for v in (hard_service_states, drying_states, active_run_task_states)):
            _vocab = (_get_adapter_config(vacuum_entity_id) or {}).get("vocabulary", {})

            def _vocab_frozenset(key: str, fallback: frozenset[str]) -> frozenset[str]:
                raw = _vocab.get(key)
                if raw:
                    return frozenset(str(s).strip().lower() for s in raw)
                return fallback

            if hard_service_states is None:
                hard_service_states = _vocab_frozenset("hard_service_states", frozenset())
            if drying_states is None:
                drying_states = _vocab_frozenset("drying_states", frozenset())
            if active_run_task_states is None:
                active_run_task_states = _vocab_frozenset("active_run_task_states", frozenset())
        if active_vacuum_states is None:
            active_vacuum_states = _HA_ACTIVE_VACUUM_STATES

        _lifecycle_entities = (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {})
        vacuum_state = self.hass.states.get(vacuum_entity_id)
        _ts = _lifecycle_entities.get("task_status")
        task_status_state = self.hass.states.get(_ts) if _ts else None
        _ds = _lifecycle_entities.get("dock_status")
        dock_status_state = self.hass.states.get(_ds) if _ds else None
        _am = _lifecycle_entities.get("active_map")
        active_map_state = self.hass.states.get(_am) if _am else None
        _at = _lifecycle_entities.get("active_cleaning_target")
        active_target_state = self.hass.states.get(_at) if _at else None

        active_job = self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        payload_state = self.get_payload_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        # Fall back to the active job's room list when the payload has been
        # cleared after job start, so lifecycle metadata reflects the running job.
        if not payload_state.get("resolved_rooms") and active_job.get("resolved_rooms"):
            payload_state = dict(payload_state)
            payload_state["resolved_rooms"] = active_job["resolved_rooms"]
            if not payload_state.get("payload") and active_job.get("payload"):
                payload_state["payload"] = active_job["payload"]

        job_metadata = build_job_metadata_from_payload(payload_state)

        lifecycle = evaluate_job_lifecycle(
            active_job_exists=active_job.get("status") in {"started", "paused"},
            active_cleaning_target=active_target_state.state if active_target_state else None,
            vacuum_state=vacuum_state.state if vacuum_state else None,
            task_status=task_status_state.state if task_status_state else None,
            dock_status=dock_status_state.state if dock_status_state else None,
            active_map_id=active_map_state.state if active_map_state else None,
            selected_map_id=str(map_id),
            job_metadata=job_metadata,
            hard_service_states=hard_service_states,
            drying_states=drying_states,
            active_run_task_states=active_run_task_states,
            active_vacuum_states=active_vacuum_states,
        )

        # Surface active-run error context. ErrorTracker holds the latch
        # in memory (and in storage) — read directly without coupling to
        # robovac_mqtt or duplicating the substring logic. None of the
        # fields below are populated when no active job is in flight or
        # when the run hasn't seen any errors yet.
        from ..const import DATA_ERROR_TRACKER as _DATA_ERROR_TRACKER

        error_tracker = self.hass.data.get(DOMAIN, {}).get(
            _DATA_ERROR_TRACKER
        )
        active_run_latch: dict[str, Any] | None = None
        if error_tracker is not None:
            try:
                active_run_latch = error_tracker.get_active_run_latch(
                    vacuum_entity_id
                )
            except Exception:  # pragma: no cover - defensive
                _LOGGER.debug(
                    "get_lifecycle_state: error_tracker read failed",
                    exc_info=True,
                )

        # Override the generic vacuum_busy / similar lifecycle message
        # with the actual error string when an error is observed mid-run.
        # Recovered-sticky mode uses a "had errors, last: …" framing so the
        # UI can communicate that the vacuum kept going after the fault.
        lifecycle_message = lifecycle["message"]
        if isinstance(active_run_latch, dict):
            error_count = int(active_run_latch.get("error_count") or 0)
            if error_count > 0:
                current_msg = active_run_latch.get("current_message") or ""
                if current_msg:
                    lifecycle_message = current_msg
                else:
                    # Derive from latest entry when current is blank
                    # (recovered mid-run).
                    entries = active_run_latch.get("errors") or []
                    last_msg = (
                        entries[-1].get("message")
                        if entries and isinstance(entries[-1], dict)
                        else None
                    )
                    if last_msg:
                        lifecycle_message = (
                            f"Run had {error_count} error(s); last: {last_msg}"
                        )

        has_error = bool(
            isinstance(active_run_latch, dict)
            and (active_run_latch.get("error_count") or 0) > 0
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "active_map_id": active_map_state.state if active_map_state else None,
            "active_cleaning_target": active_target_state.state if active_target_state else None,
            "vacuum_state": vacuum_state.state if vacuum_state else None,
            "vacuum_state_label": _display_label(vacuum_state.state if vacuum_state else None),
            "task_status": task_status_state.state if task_status_state else None,
            "task_status_label": _display_label(task_status_state.state if task_status_state else None),
            "dock_status": dock_status_state.state if dock_status_state else None,
            "dock_status_label": _display_label(dock_status_state.state if dock_status_state else None),
            "active_job_exists": active_job.get("status") in {"started", "paused"},
            "lifecycle_state": lifecycle["lifecycle_state"],
            "lifecycle_state_label": _display_label(lifecycle["lifecycle_state"]),
            "message": lifecycle_message,
            "blocking": lifecycle["blocking"],
            "job_metadata": lifecycle["job_metadata"],
            "warning": lifecycle.get("warning", False),
            # Error tracking — None when no active-run latch exists.
            "error_message": (
                active_run_latch.get("current_message")
                if isinstance(active_run_latch, dict)
                else None
            ) or None,
            "has_error": has_error,
            "error_count": (
                int(active_run_latch.get("error_count") or 0)
                if isinstance(active_run_latch, dict)
                else 0
            ),
            "recovered": (
                bool(active_run_latch.get("recovered"))
                if isinstance(active_run_latch, dict)
                else False
            ),
        }

    def get_start_status(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Build start protection status for one vacuum/map."""
        runtime = self.ensure_runtime(vacuum_entity_id)

        _active_map_entity = (
            (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("active_map")
        )
        active_map_state = self.hass.states.get(_active_map_entity) if _active_map_entity else None

        start_plan = self._build_effective_start_plan(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        queue_state = start_plan.get("queue_state", {})
        payload_state = start_plan.get("payload_state", {})
        preflight = start_plan.get("preflight", {})
        lifecycle_state = self.get_lifecycle_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        onboarding = self.get_onboarding_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        active_job = self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        if active_job.get("status") == "paused":
            runtime.start_block_reason = "job_paused"
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "selected_map_id": str(map_id),
                "active_map_id": active_map_state.state if active_map_state else None,
                "queue_room_ids": queue_state.get("queue_room_ids", []),
                "payload_room_count": int(payload_state.get("room_count", 0)),
                "lifecycle_state": lifecycle_state["lifecycle_state"],
                "lifecycle_state_label": _display_label(lifecycle_state["lifecycle_state"]),
                "lifecycle_message": lifecycle_state["message"],
                "reason": "job_paused",
                "reason_label": _display_label("job_paused"),
                "message": "A tracked job is currently paused. Resume or cancel it before starting a new one.",
                "blocked": True,
                "warning": False,
                "onboarding_status": onboarding,
                "preflight": preflight,
            }
        if not onboarding["floor_types_complete"]:
            rooms_needing = onboarding["enabled_rooms_needing_floor_type"]
            runtime.start_block_reason = "onboarding_required"
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "selected_map_id": str(map_id),
                "active_map_id": active_map_state.state if active_map_state else None,
                "queue_room_ids": queue_state.get("queue_room_ids", []),
                "payload_room_count": int(payload_state.get("room_count", 0)),
                "lifecycle_state": lifecycle_state["lifecycle_state"],
                "lifecycle_state_label": _display_label(lifecycle_state["lifecycle_state"]),
                "lifecycle_message": lifecycle_state["message"],
                "reason": "onboarding_required",
                "reason_label": _display_label("onboarding_required"),
                "message": (
                    f"{len(rooms_needing)} enabled room(s) need floor type confirmed "
                    "before cleaning can start."
                ),
                "blocked": True,
                "warning": False,
                "onboarding_status": onboarding,
                "preflight": preflight,
            }

        selected_room_count = int(preflight.get("selected_room_count", 0) or 0)
        included_room_count = int(preflight.get("included_room_count", 0) or 0)
        blocked_room_count = int(preflight.get("blocked_room_count", 0) or 0)

        if selected_room_count > 0 and included_room_count == 0 and blocked_room_count > 0:
            runtime.start_block_reason = "all_selected_rooms_blocked"
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "selected_map_id": str(map_id),
                "active_map_id": active_map_state.state if active_map_state else None,
                "queue_room_ids": queue_state.get("queue_room_ids", []),
                "payload_room_count": int(payload_state.get("room_count", 0)),
                "lifecycle_state": lifecycle_state["lifecycle_state"],
                "lifecycle_state_label": _display_label(lifecycle_state["lifecycle_state"]),
                "lifecycle_message": lifecycle_state["message"],
                "reason": "all_selected_rooms_blocked",
                "reason_label": "All Selected Rooms Blocked",
                "message": preflight.get("message") or "All selected rooms are currently blocked.",
                "blocked": True,
                "warning": bool(preflight.get("warnings")),
                "onboarding_status": onboarding,
                "preflight": preflight,
                "requires_confirmation": bool(preflight.get("requires_confirmation", False)),
                "confirm_token": preflight.get("confirm_token"),
            }

        result = build_start_blocker_from_lifecycle(
            lifecycle_state=lifecycle_state["lifecycle_state"],
            lifecycle_message=lifecycle_state["message"],
            selected_map_id=str(map_id),
            active_map_id=active_map_state.state if active_map_state else None,
            queue_room_ids=queue_state.get("queue_room_ids", []),
            payload_room_count=int(payload_state.get("room_count", 0)),
        )

        if result["blocked"]:
            runtime.start_block_reason = result["reason"]
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "selected_map_id": str(map_id),
                "active_map_id": active_map_state.state if active_map_state else None,
                "queue_room_ids": queue_state.get("queue_room_ids", []),
                "payload_room_count": int(payload_state.get("room_count", 0)),
                "lifecycle_state": lifecycle_state["lifecycle_state"],
                "lifecycle_state_label": _display_label(lifecycle_state["lifecycle_state"]),
                "lifecycle_message": lifecycle_state["message"],
                "reason": result["reason"],
                "reason_label": _display_label(result["reason"]),
                "message": result["message"],
                "blocked": True,
                "warning": bool(result.get("warning", False)),
                "onboarding_status": onboarding,
                "preflight": preflight,
                "requires_confirmation": bool(preflight.get("requires_confirmation", False)),
                "confirm_token": preflight.get("confirm_token"),
            }

        if bool(preflight.get("blocked", False)):
            runtime.start_block_reason = str(preflight.get("reason", "blocked"))
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "selected_map_id": str(map_id),
                "active_map_id": active_map_state.state if active_map_state else None,
                "queue_room_ids": queue_state.get("queue_room_ids", []),
                "payload_room_count": int(payload_state.get("room_count", 0)),
                "lifecycle_state": lifecycle_state["lifecycle_state"],
                "lifecycle_state_label": _display_label(lifecycle_state["lifecycle_state"]),
                "lifecycle_message": lifecycle_state["message"],
                "reason": preflight.get("reason", "blocked"),
                "reason_label": _display_label(preflight.get("reason", "blocked")),
                "message": preflight.get("message", "Start is blocked."),
                "blocked": True,
                "warning": bool(preflight.get("warnings")),
                "onboarding_status": onboarding,
                "preflight": preflight,
                "requires_confirmation": bool(preflight.get("requires_confirmation", False)),
                "confirm_token": preflight.get("confirm_token"),
            }

        runtime.start_block_reason = str(preflight.get("reason") or result["reason"])
        water_estimate = self.get_planned_job_estimate(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        ).get("water_estimate", {})
        water_warning = bool(
            isinstance(water_estimate, dict)
            and (water_estimate.get("not_enough_clean_water") or water_estimate.get("low_clean_water_margin"))
        )
        water_reason = None
        water_message = None
        if water_warning:
            if water_estimate.get("not_enough_clean_water"):
                water_reason = "not_enough_clean_water"
                water_message = "Not enough clean water is estimated to complete the selected job."
            else:
                water_reason = "low_clean_water_margin"
                water_message = "This job is estimated to leave very little clean water remaining."

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "selected_map_id": str(map_id),
            "active_map_id": active_map_state.state if active_map_state else None,
            "queue_room_ids": queue_state.get("queue_room_ids", []),
            "payload_room_count": int(payload_state.get("room_count", 0)),
            "lifecycle_state": lifecycle_state["lifecycle_state"],
            "lifecycle_state_label": _display_label(lifecycle_state["lifecycle_state"]),
            "lifecycle_message": lifecycle_state["message"],
            "reason": water_reason or preflight.get("reason") or result["reason"],
            "reason_label": _display_label(water_reason or preflight.get("reason") or result["reason"]),
            "message": water_message or preflight.get("message") or result["message"],
            "blocked": False,
            "warning": bool(result.get("warning", False) or water_warning or preflight.get("warnings") or preflight.get("requires_confirmation", False)),
            "water_warning": water_warning,
            "water_warning_reason": water_reason,
            "water_warning_reason_label": _display_label(water_reason),
            "water_warning_message": water_message,
            "water_estimate": water_estimate if isinstance(water_estimate, dict) else None,
            "onboarding_status": onboarding,
            "preflight": preflight,
            "requires_confirmation": bool(preflight.get("requires_confirmation", False)),
            "confirm_token": preflight.get("confirm_token"),
        }

    # ------------------------------------------------------------------
    # Singleton-ownership helpers
    # ------------------------------------------------------------------

    def get_known_vacuum_ids(self) -> list[str]:
        """Return all vacuum entity IDs known to this manager.

        Aggregates across the vacuums, maps, and active_jobs buckets.
        """
        vacuum_ids: set[str] = set(self.data.get("vacuums", {}).keys())
        vacuum_ids.update(self.data.get("maps", {}).keys())
        vacuum_ids.update(self.data.get("active_jobs", {}).keys())
        return sorted(vacuum_ids)

    def get_known_map_ids(self, vacuum_entity_id: str) -> list[str]:
        """Return all map IDs known for one vacuum.

        Aggregates across the maps and active_jobs buckets plus the runtime state.
        """
        map_ids: set[str] = set()

        for map_id in self.data.get("maps", {}).get(vacuum_entity_id, {}):
            map_ids.add(str(map_id))

        for map_id in self.data.get("active_jobs", {}).get(vacuum_entity_id, {}):
            map_ids.add(str(map_id))

        runtime = self.runtime.get(vacuum_entity_id)
        if runtime is not None:
            if getattr(runtime, "selected_map_id", None):
                map_ids.add(str(runtime.selected_map_id))
            if getattr(runtime, "active_map_id", None):
                map_ids.add(str(runtime.active_map_id))

        if not map_ids:
            map_ids.add("unknown")

        return sorted(map_ids)


    # Active job CRUD — delegates to ActiveJobTracker

    def record_active_lifecycle_observed(self, **kwargs) -> None:
        """Delegate to ActiveJobTracker."""
        return self.active_job.record_active_lifecycle_observed(**kwargs)

    def get_active_job(self, **kwargs) -> dict:
        """Return active job state — delegates to ActiveJobTracker."""
        return self.active_job.get_active_job(**kwargs)

    def record_active_job_sensor_value(self, **kwargs) -> bool:
        """Write a sensor value to in-flight jobs — delegates to ActiveJobTracker."""
        return self.active_job.record_active_job_sensor_value(**kwargs)

    def clear_active_job(self, **kwargs) -> dict:
        """Clear active job state — delegates to ActiveJobTracker."""
        return self.active_job.clear_active_job(**kwargs)

    def pause_active_job(self, **kwargs) -> dict:
        """Mark job paused — delegates to ActiveJobTracker."""
        return self.active_job.pause_active_job(**kwargs)

    def resume_active_job(self, **kwargs) -> dict:
        """Resume paused job — delegates to ActiveJobTracker."""
        return self.active_job.resume_active_job(**kwargs)

    def record_completed_room(self, **kwargs) -> dict:
        """Record one room completed — delegates to ActiveJobTracker."""
        return self.active_job.record_completed_room(**kwargs)


    # ------------------------------------------------------------------
    # Job progress / control
    # ------------------------------------------------------------------

    def get_job_progress_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return a canonical room-job progress snapshot for the card."""
        active_job = self._normalize_active_job(
            self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        )
        lifecycle = self.get_lifecycle_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        current_battery = self._get_battery_level(vacuum_entity_id)
        learning = self._get_learning_manager()

        completed_room_ids = [
            _safe_int(room_id, -1)
            for room_id in active_job.get("completed_room_ids", [])
            if _safe_int(room_id, -1) >= 0
        ]
        completed_rooms = [
            dict(entry)
            for entry in active_job.get("completed_rooms", [])
            if isinstance(entry, dict)
        ]

        timeline_source = "none"
        timeline_payload: dict[str, Any] = {}
        active_job_resolved_rooms = active_job.get("resolved_rooms") or None
        if learning is not None and active_job_resolved_rooms:
            timeline_payload = learning.estimate_from_manager(
                self,
                vacuum_entity_id,
                str(map_id),
                float(current_battery),
                1.0,
                5.0,
                active_job.get("started_at"),
                resolved_rooms=active_job_resolved_rooms,
            )
            timeline_source = "estimate"
            if completed_rooms:
                timeline_payload = learning.reanchor_timeline(
                    original_estimate=timeline_payload,
                    completed_rooms=completed_rooms,
                    reanchor_at=active_job.get("current_room_started_at") or _iso_now(),
                    current_battery=float(current_battery),
                    charge_percent_per_minute=1.0,
                    reserve_battery_percent=5.0,
                )
                timeline_source = "reanchored"

        raw_timeline = list(timeline_payload.get("room_timeline", []))
        unresolved_room_ids = [
            _safe_int(room.get("room_id", -1), -1)
            for room in raw_timeline
            if _safe_int(room.get("room_id", -1), -1) not in completed_room_ids
        ]
        current_room_id = active_job.get("current_room_id")
        current_room_id = _safe_int(current_room_id, -1)
        if current_room_id < 0 or current_room_id not in unresolved_room_ids:
            current_room_id = unresolved_room_ids[0] if unresolved_room_ids else None

        if current_room_id is None and active_job.get("status") in {"started", "paused"} and unresolved_room_ids:
            current_room_id = unresolved_room_ids[0]
            active_job["current_room_id"] = current_room_id
            active_job["current_room_started_at"] = active_job.get("current_room_started_at") or active_job.get("started_at") or _iso_now()
            self.data.setdefault("active_jobs", {})
            self.data["active_jobs"].setdefault(vacuum_entity_id, {})
            self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job

        current_room_elapsed_minutes = self._compute_current_room_elapsed_minutes(active_job=active_job)
        pre_roll_room_id = current_room_id
        active_job = self._maybe_roll_current_room_by_timing(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            active_job=active_job,
            raw_timeline=raw_timeline,
            current_room_id=current_room_id,
            current_room_elapsed_minutes=current_room_elapsed_minutes,
            completed_room_ids=completed_room_ids,
        )
        if active_job is not None:
            completed_room_ids = [
                _safe_int(room_id, -1)
                for room_id in active_job.get("completed_room_ids", [])
                if _safe_int(room_id, -1) >= 0
            ]
            completed_rooms = [
                dict(entry)
                for entry in active_job.get("completed_rooms", [])
                if isinstance(entry, dict)
            ]
            unresolved_room_ids = [
                _safe_int(room.get("room_id", -1), -1)
                for room in raw_timeline
                if _safe_int(room.get("room_id", -1), -1) not in completed_room_ids
            ]
            current_room_id = _safe_int(active_job.get("current_room_id"), -1)
            if current_room_id < 0 or current_room_id not in unresolved_room_ids:
                current_room_id = unresolved_room_ids[0] if unresolved_room_ids else None
            current_room_elapsed_minutes = self._compute_current_room_elapsed_minutes(active_job=active_job)

        # ------------------------------------------------------------------
        # Bounds-exit polling signal
        # ------------------------------------------------------------------
        # When timing says a room should be done but the robot is still
        # inside its bounds, the rollover is blocked.  Signal this to the
        # card so it can start a short-interval poll (~5 s) instead of
        # waiting for the next room event — which won't come until the
        # robot actually leaves.
        awaiting_bounds_exit = False
        if (
            active_job.get("status") == "started"
            and pre_roll_room_id is not None
            and current_room_id == pre_roll_room_id   # room did not roll
        ):
            current_room_entry = next(
                (
                    r for r in raw_timeline
                    if _safe_int(r.get("room_id", -1), -1) == current_room_id
                ),
                None,
            )
            if current_room_entry is not None:
                threshold = self._timing_completion_threshold_minutes(current_room_entry)
                if current_room_elapsed_minutes >= threshold:
                    awaiting_bounds_exit = True

        # ------------------------------------------------------------------
        # Stall detection
        # ------------------------------------------------------------------
        # A stall is when the bounds gate is already blocking rollover AND
        # the robot has been in the room for >= 2x the timing threshold.
        # Fire EVENT_STALL_DETECTED once per room per job (tracked in the
        # active job dict so the event doesn't re-fire on every snapshot call).
        # ------------------------------------------------------------------
        _STALL_RATIO = 2.0
        stall_detected = False
        stall_elapsed_minutes: float | None = None
        stall_expected_minutes: float | None = None
        stall_ratio: float | None = None

        if awaiting_bounds_exit and current_room_id is not None:
            _stall_entry = next(
                (
                    r for r in raw_timeline
                    if _safe_int(r.get("room_id", -1), -1) == current_room_id
                ),
                None,
            )
            if _stall_entry is not None:
                _stall_threshold = self._timing_completion_threshold_minutes(_stall_entry)
                if _stall_threshold > 0 and current_room_elapsed_minutes >= _stall_threshold * _STALL_RATIO:
                    stall_detected = True
                    stall_elapsed_minutes = round(current_room_elapsed_minutes, 1)
                    stall_expected_minutes = round(_stall_threshold, 1)
                    stall_ratio = round(current_room_elapsed_minutes / _stall_threshold, 2)

                    # Fire event exactly once per room per job.
                    # The set is bounded to one entry per unique room ID; cap
                    # mirrors the job's own room count as a safety valve.
                    _notified = set(active_job.get("_stall_notified_room_ids") or [])
                    if current_room_id not in _notified:
                        _notified.add(current_room_id)
                        _stall_cap = max(len(active_job.get("queue_room_ids") or []) + 1, 20)
                        active_job["_stall_notified_room_ids"] = list(_notified)[-_stall_cap:]
                        self.data.setdefault("active_jobs", {}) \
                            .setdefault(vacuum_entity_id, {})[str(map_id)] = active_job
                        _stall_room_name = (
                            self._room_name_from_active_job(active_job, current_room_id)
                            or f"Room {current_room_id}"
                        )
                        self.hass.bus.async_fire(
                            EVENT_STALL_DETECTED,
                            {
                                "vacuum_entity_id": vacuum_entity_id,
                                "map_id": str(map_id),
                                "room_id": current_room_id,
                                "room_name": _stall_room_name,
                                "elapsed_minutes": stall_elapsed_minutes,
                                "expected_minutes": stall_expected_minutes,
                                "stall_ratio": stall_ratio,
                            },
                        )

        # ------------------------------------------------------------------
        # Transition-room detection (snapshot-only — does not modify storage)
        # ------------------------------------------------------------------
        # When the robot has finished a queued room by timing but hasn't
        # entered the next queued room yet, use the access graph + live
        # robot position to find which intermediate room it's passing through.
        # position_room_id is what the card uses for the animal icon; it can
        # be a transition room that is NOT in the queue.
        # current_room_id is preserved as the next unfinished queued room so
        # the timeline is_current flags remain correct.
        position_room_id: int | None = current_room_id
        if (
            active_job.get("status") == "started"
            and current_room_id is not None
            and completed_room_ids
        ):
            last_completed_id = completed_room_ids[-1]
            transition_room_id = self._detect_transition_room_from_position(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                from_room_id=last_completed_id,
                to_room_id=current_room_id,
            )
            if transition_room_id is not None:
                position_room_id = transition_room_id

        timeline: list[dict[str, Any]] = []
        current_progress_percent = 0
        current_remaining_minutes = 0.0

        for room in raw_timeline:
            room_id = _safe_int(room.get("room_id", -1), -1)
            room_entry = dict(room)
            is_completed = room_id in completed_room_ids
            is_current = (
                room_id >= 0
                and room_id == current_room_id
                and active_job.get("status") in {"started", "paused"}
                and not is_completed
            )
            estimated_minutes = max(float(room.get("minutes", 0.0) or 0.0), 1.0)
            elapsed_minutes = 0.0
            progress_percent = 100 if is_completed else 0
            remaining_minutes = 0.0 if is_completed else round(estimated_minutes, 2)

            if is_current:
                elapsed_minutes = min(current_room_elapsed_minutes, estimated_minutes)
                progress_percent = max(min(int((elapsed_minutes / estimated_minutes) * 100), 99), 0)
                remaining_minutes = round(max(estimated_minutes - elapsed_minutes, 0.0), 2)
                current_progress_percent = progress_percent
                current_remaining_minutes = remaining_minutes

            room_entry["completed"] = is_completed
            room_entry["current"] = is_current
            room_entry["remaining"] = not is_completed and not is_current
            room_entry["skipped"] = False
            room_entry["progress_percent"] = progress_percent
            room_entry["elapsed_minutes"] = round(elapsed_minutes, 2)
            room_entry["remaining_minutes"] = remaining_minutes
            timeline.append(room_entry)

        # WHY: invert the check — terminal means "not actively running" so the
        # card's _dashboardJobIsActive doesn't latch on `idle`/cleared jobs.
        # Anything outside the active set ({started, paused}) is terminal.
        terminal_status = str(active_job.get("status", "idle")).strip().lower() not in {
            "started",
            "paused",
        }

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "job_id": active_job.get("job_id"),
            "status": active_job.get("status", "idle"),
            "terminal": terminal_status,
            "lifecycle_state": lifecycle.get("lifecycle_state"),
            "lifecycle_message": lifecycle.get("message"),
            "started_at": active_job.get("started_at"),
            "current_room_id": current_room_id,
            "position_room_id": position_room_id,
            "awaiting_bounds_exit": awaiting_bounds_exit,
            "current_room_started_at": active_job.get("current_room_started_at"),
            "completed_room_ids": completed_room_ids,
            "remaining_room_ids": [room_id for room_id in unresolved_room_ids if room_id != current_room_id],
            "skipped_room_ids": [],
            "progress_percent": current_progress_percent,
            "elapsed_minutes": round(current_room_elapsed_minutes, 2),
            "remaining_minutes": round(current_remaining_minutes, 2),
            "current_battery": current_battery,
            "timeline_source": timeline_source,
            "timeline": timeline,
            "room_timeline": timeline,
            "completed_rooms": completed_rooms,
            "mid_job_recharge_observed": bool(active_job.get("observed_mid_job_recharge", False)),
            "mid_job_recharge_started_at": active_job.get("observed_mid_job_recharge_started_at"),
            "mid_job_recharge_count": _safe_int(active_job.get("observed_mid_job_recharge_count"), 0),
            "recharge_seconds_accumulated": max(_safe_int(active_job.get("recharge_seconds_accumulated"), 0), 0),
            "pending_mid_job_recharge_return": bool(active_job.get("pending_mid_job_recharge_return", False)),
            "pending_mid_job_recharge_return_at": active_job.get("pending_mid_job_recharge_return_at"),
            "mid_job_recharge_risk": bool(timeline_payload.get("mid_job_recharge_risk", False)),
            "mid_job_recharge_needed_battery": timeline_payload.get("mid_job_recharge_needed_battery", 0.0),
            "mid_job_recharge_estimated_charge_minutes": timeline_payload.get(
                "mid_job_recharge_estimated_charge_minutes",
                0.0,
            ),
            "mapping_available": False,
            "mapping_used": False,
            "status_summary": self._job_status_summary(
                active_job=active_job,
                lifecycle_state=lifecycle,
                progress_snapshot={
                    "current_room_id": current_room_id,
                },
            ),
            "stall_detected": stall_detected,
            "stall_elapsed_minutes": stall_elapsed_minutes,
            "stall_expected_minutes": stall_expected_minutes,
            "stall_ratio": stall_ratio,
            "updated_at": _iso_now(),
        }

    def get_planned_job_estimate(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        resolved_rooms: list | None = None,
    ) -> dict[str, Any]:
        """Return the current prestart planned estimate from queue/payload state.

        Pass resolved_rooms to bypass the payload state lookup — needed when
        the payload has already been cleared after job start but active_job
        still holds the room list.
        """
        payload_state = self.get_payload_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        queue_state = self.get_queue_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        current_battery = self._get_battery_level(vacuum_entity_id)
        learning = self._get_learning_manager()

        effective_rooms: list = (
            resolved_rooms
            if resolved_rooms is not None
            else list(payload_state.get("resolved_rooms", []))
        )

        if learning is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "available": False,
                "reason": "learning_unavailable",
                "message": "Learning system is unavailable.",
                "queue_room_ids": list(queue_state.get("queue_room_ids", [])),
                "payload_room_count": int(payload_state.get("room_count", 0)),
            }

        estimate = learning.estimate_from_manager(
            self,
            vacuum_entity_id,
            str(map_id),
            float(current_battery),
            1.0,
            5.0,
            None,
            resolved_rooms=effective_rooms,
        )
        can_run_now = bool(estimate.get("can_run_now", False))
        water_estimate = self.estimate_job_water_usage(
            vacuum_entity_id=vacuum_entity_id,
            resolved_rooms=effective_rooms,
            room_timeline=list(estimate.get("room_timeline", [])),
        )
        return {
            **estimate,
            "available": can_run_now,
            "reason": "ready" if can_run_now else str(estimate.get("reason", "estimate_unavailable")),
            "message": str(estimate.get("message", "")).strip() or (
                "Planned estimate ready." if can_run_now else "Planned estimate unavailable."
            ),
            "queue_room_ids": list(queue_state.get("queue_room_ids", [])),
            "payload_room_count": int(payload_state.get("room_count", 0)),
            "current_battery": current_battery,
            "water_estimate": water_estimate,
        }

    def get_job_control_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return card-facing action state for one job."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        start_status = self.get_start_status(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        lifecycle = self.get_lifecycle_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        progress = self.get_job_progress_snapshot(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        status = str(active_job.get("status", "idle")).strip().lower()
        finalized = bool(active_job.get("finalized"))

        can_pause = status == "started"
        can_resume = status == "paused"
        can_cancel = status in {"started", "paused"}
        can_clear = status in {"completed", "cancelled", "failed", "interrupted"} or finalized
        can_start = bool(not start_status.get("blocked", False))

        reason_detail = (
            str(active_job.get("finalize_summary", {}).get("status", "")).strip()
            or str(start_status.get("reason", "")).strip()
            or str(lifecycle.get("lifecycle_state", "")).strip()
        )
        pause_timeout_settings = self.get_pause_timeout_settings(
            vacuum_entity_id=vacuum_entity_id
        )
        pause_timeout_minutes_default = _normalize_pause_timeout_minutes(
            pause_timeout_settings.get("pause_timeout_minutes_default")
        )
        pause_timeout_minutes_effective = _normalize_pause_timeout_minutes(
            active_job.get("pause_timeout_minutes")
            if status in {"started", "paused"}
            else pause_timeout_minutes_default
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "status": status,
            "status_label": _display_label(status),
            "terminal": status in {"completed", "cancelled", "failed", "interrupted"},
            "can_start": can_start,
            "can_pause": can_pause,
            "can_resume": can_resume,
            "can_cancel": can_cancel,
            "can_clear": can_clear,
            "reason": start_status.get("reason"),
            "reason_label": _display_label(start_status.get("reason")),
            "reason_detail": reason_detail,
            "message": start_status.get("message") or lifecycle.get("message"),
            "pause_timeout_minutes_default": pause_timeout_minutes_default,
            "pause_timeout_minutes_effective": pause_timeout_minutes_effective,
            "warning": bool(start_status.get("warning", False) or lifecycle.get("warning", False)),
            "status_summary": progress.get("status_summary") or self._job_status_summary(
                active_job=active_job,
                lifecycle_state=lifecycle,
                progress_snapshot=progress,
            ),
            "job_id": active_job.get("job_id"),
            "current_room_id": progress.get("current_room_id"),
        }

    # ------------------------------------------------------------------
    # Upkeep / maintenance
    # ------------------------------------------------------------------

    def get_upkeep_snapshot(self, **kwargs) -> dict:
        """Delegate to MaintenanceManager."""
        return self.maintenance.get_upkeep_snapshot(**kwargs)

    def get_dashboard_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return one card-friendly dashboard snapshot."""
        lifecycle = self.get_lifecycle_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        start_status = self.get_start_status(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        job_progress = self.get_job_progress_snapshot(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        job_control = self.get_job_control_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        upkeep = self.get_upkeep_snapshot(vacuum_entity_id=vacuum_entity_id)
        planned_job_estimate = self.get_planned_job_estimate(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        # Adapter vocabulary is the card's source for user-facing
        # dropdown option lists (clean_mode_options, fan_speed_options,
        # water_level_options, clean_intensity_options) plus the alias
        # maps. Static per adapter — the card uses whatever the adapter
        # declares rather than probing upstream select entities, which
        # only exist on some brands.
        _adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        adapter_vocabulary = _adapter_cfg.get("vocabulary", {}) or {}

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "status_summary": job_control.get("status_summary") or job_progress.get("status_summary"),
            "attention_summary": upkeep.get("attention_summary"),
            "planned_job_estimate": planned_job_estimate,
            "job_progress": job_progress,
            "job_control": job_control,
            "start_status": start_status,
            "lifecycle": lifecycle,
            "upkeep": upkeep,
            "adapter_vocabulary": adapter_vocabulary,
            "updated_at": _iso_now(),
        }


    # Job finalization — delegates to ActiveJobTracker

    def mark_active_job_finalized(self, **kwargs) -> dict:
        """Mark job finalized — delegates to ActiveJobTracker."""
        return self.active_job.mark_active_job_finalized(**kwargs)

    async def async_pause_active_job(self, **kwargs) -> dict:
        """Pause vacuum + job — delegates to ActiveJobTracker."""
        return await self.active_job.async_pause_active_job(**kwargs)

    async def async_resume_active_job(self, **kwargs) -> dict:
        """Resume vacuum + job — delegates to ActiveJobTracker."""
        return await self.active_job.async_resume_active_job(**kwargs)

    async def async_cancel_active_job(self, **kwargs) -> dict:
        """Cancel job — delegates to ActiveJobTracker."""
        return await self.active_job.async_cancel_active_job(**kwargs)

    def get_paused_job_timeout_report(self, **kwargs):
        """Return paused-job timeout report — delegates to ActiveJobTracker."""
        return self.active_job.get_paused_job_timeout_report(**kwargs)


    def save_learning_snapshot_for_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        started_at: str,
        battery_start: int,
        job_id: str,
    ) -> dict[str, Any] | None:
        """Save learning snapshot for a newly started active job."""
        learning = self._get_learning_manager()
        if learning is None:
            return None

        return learning.save_live_snapshot_from_manager(
            manager=self,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            started_at=started_at,
            battery_start=battery_start,
            job_id=job_id,
        )

    async def finalize_learning_for_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        battery_end: int | None = None,
        ended_at: str | None = None,
        rebuild_stats: bool = True,
        rebuild_csv: bool = False,
        forced_outcome_status: str | None = None,
        forced_lifecycle_state: str | None = None,
        forced_lifecycle_message: str | None = None,
    ) -> dict[str, Any] | None:
        """Finalize learning for the current active job on a map."""
        learning = self._get_learning_manager()
        if learning is None:
            return None

        active_job = self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        started_at = str(active_job.get("started_at", "")).strip()
        battery_start = _safe_int(active_job.get("battery_start"), 0)

        if not started_at:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "finalized": False,
                "reason": "missing_started_at",
            }

        if battery_end is None:
            battery_end = self._get_battery_level(vacuum_entity_id)

        result = await learning.async_finalize_completed_job(
            manager=self,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            battery_start=battery_start,
            battery_end=_safe_int(battery_end, 0),
            started_at=started_at,
            ended_at=ended_at or _iso_now(),
            used_for_learning=True,
            rebuild_stats=rebuild_stats,
            rebuild_csv=rebuild_csv,
            forced_outcome_status=forced_outcome_status,
            forced_lifecycle_state=forced_lifecycle_state,
            forced_lifecycle_message=forced_lifecycle_message,
        )
        completed_job = result.get("completed_job", {}) if isinstance(result, dict) else {}

        if self._ingest_completed_job_into_room_history(
            vacuum_entity_id=vacuum_entity_id,
            completed_job=completed_job,
        ):
            self._notify_room_history_updated(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
        return result

    def get_maintenance_state(self, **kwargs):
        """Return maintenance reset snapshots -- delegates to MaintenanceManager."""
        return self.maintenance.get_maintenance_state(**kwargs)

    def reset_maintenance(self, **kwargs):
        """Reset maintenance counter -- delegates to MaintenanceManager."""
        return self.maintenance.reset_maintenance(**kwargs)

    # ------------------------------------------------------------------
    # Onboarding — delegates to OnboardingManager
    # ------------------------------------------------------------------

    def get_onboarding_state(self, **kwargs) -> dict[str, Any]:
        """Return full onboarding status — delegates to OnboardingManager."""
        return self.onboarding.get_onboarding_state(**kwargs)

    def mark_rooms_discovered(self, **kwargs) -> None:
        """Mark rooms as discovered — delegates to OnboardingManager."""
        return self.onboarding.mark_rooms_discovered(**kwargs)

    def confirm_floor_type(self, **kwargs) -> None:
        """Mark a room's floor type as confirmed — delegates to OnboardingManager."""
        return self.onboarding.confirm_floor_type(**kwargs)

    def check_for_new_rooms(self, **kwargs) -> bool:
        """Return True if room count has grown — delegates to OnboardingManager."""
        return self.onboarding.check_for_new_rooms(**kwargs)

    def get_rooms_onboarding_summary(self, **kwargs) -> dict[str, Any]:
        """Return onboarding status across all maps — delegates to OnboardingManager."""
        return self.onboarding.get_rooms_onboarding_summary(**kwargs)

    def reset_onboarding(self, **kwargs) -> dict[str, Any]:
        """Clear onboarding state for one map — delegates to OnboardingManager."""
        return self.onboarding.reset_onboarding(**kwargs)

    # ------------------------------------------------------------------
    # Theme management - delegated to self.themes (ThemeManager)
    # ------------------------------------------------------------------

    def get_theme_library(self) -> dict:
        """Return the full theme library - delegates to ThemeManager."""
        return self.themes.get_theme_library()

    def save_theme_as_new(self, **kwargs):
        """Save vacuum's working draft as new theme - delegates to ThemeManager."""
        return self.themes.save_theme_as_new(**kwargs)

    def overwrite_theme(self, **kwargs):
        """Overwrite theme with working draft - delegates to ThemeManager."""
        return self.themes.overwrite_theme(**kwargs)

    def rename_theme(self, **kwargs):
        """Rename a theme - delegates to ThemeManager."""
        return self.themes.rename_theme(**kwargs)

    def delete_theme(self, **kwargs):
        """Delete a theme - delegates to ThemeManager."""
        return self.themes.delete_theme(**kwargs)

    def set_active_theme(self, **kwargs):
        """Set active theme - delegates to ThemeManager."""
        return self.themes.set_active_theme(**kwargs)

    def update_working_draft(self, **kwargs):
        """Update working draft - delegates to ThemeManager."""
        return self.themes.update_working_draft(**kwargs)

    def revert_draft(self, **kwargs):
        """Revert draft - delegates to ThemeManager."""
        return self.themes.revert_draft(**kwargs)

    def export_theme(self, **kwargs):
        """Export theme - delegates to ThemeManager."""
        return self.themes.export_theme(**kwargs)

    def import_theme(self, **kwargs):
        """Import theme - delegates to ThemeManager."""
        return self.themes.import_theme(**kwargs)

    # ------------------------------------------------------------------
    # Dock events — delegates to DockManager
    # ------------------------------------------------------------------

    def record_dock_event(self, **kwargs) -> None:
        """Record a dock event timestamp — delegates to DockManager."""
        return self.dock.record_dock_event(**kwargs)

    def set_dock_event_count(self, **kwargs) -> dict[str, Any]:
        """Overwrite a dock event counter — delegates to DockManager."""
        return self.dock.set_dock_event_count(**kwargs)

    def get_dock_events(self, **kwargs) -> dict[str, Any]:
        """Return stored dock event timestamps — delegates to DockManager."""
        return self.dock.get_dock_events(**kwargs)

    def get_maintenance_remaining(self, **kwargs):
        """Return remaining maintenance hours -- delegates to MaintenanceManager."""
        return self.maintenance.get_maintenance_remaining(**kwargs)

    # ------------------------------------------------------------------
    # Job start / run-profile start
    # ------------------------------------------------------------------

    async def _dispatch_clean_payload(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Send one clean payload to the vacuum service using the adapter's envelope.

        Reads dispatch config for service_domain/service_name/command. Two
        envelope shapes: wrapped ``{command, params}`` (Eufy/Roborock/Ecovacs
        send_command) when a ``command`` is declared, else direct merge-into-data
        (Dreame's vacuum_clean_segment). Shared by job start and phase advance.
        """
        cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        domain = cfg.get("service_domain", "vacuum")
        name = cfg.get("service_name", "send_command")
        command = cfg.get("command", "room_clean")
        if command:
            data = {"entity_id": vacuum_entity_id, "command": command, "params": payload}
        else:
            data = {"entity_id": vacuum_entity_id, **payload}
        await self.hass.services.async_call(domain, name, data, blocking=True)

    async def maybe_advance_phase(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> bool:
        """For a sequenced job at phase completion, advance + re-dispatch instead
        of finalizing.

        Returns True when the job advanced to a next phase (the caller must skip
        finalization); False for an atomic job or the final phase (the caller
        finalizes exactly as today). The completion hook calls this right before
        it would finalize.
        """
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        advanced = advance_active_job_phase(active_job)
        if advanced is None:
            return False

        advanced["current_room_started_at"] = _iso_now()
        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = advanced

        await self._dispatch_clean_payload(
            vacuum_entity_id=vacuum_entity_id,
            payload=advanced.get("payload", {}),
        )
        _LOGGER.debug(
            "Advanced sequenced job for %s map %s to phase %s/%s",
            vacuum_entity_id, map_id,
            advanced.get("current_phase_index"), advanced.get("phase_count"),
        )
        return True

    async def start_selected_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        confirm_reduced_run: bool = False,
        confirm_token: str | None = None,
        path_block_action: str | None = None,
        pause_timeout_minutes_override: int | None = None,
    ) -> dict[str, Any]:
        """Start selected rooms using the current queue/payload for one map."""
        start_status = self.get_start_status(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        if start_status["blocked"]:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "started": False,
                "reason": start_status["reason"],
                "message": start_status["message"],
                "warning": start_status.get("warning", False),
            }

        if start_status.get("requires_confirmation") and not (
            bool(confirm_reduced_run)
            or (
                str(confirm_token or "").strip()
                and str(confirm_token).strip() == str(start_status.get("confirm_token") or "").strip()
            )
        ):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "started": False,
                "reason": "confirmation_required",
                "message": str(start_status.get("message", "Confirmation required before starting this reduced run.")),
                "warning": True,
                "preflight": start_status.get("preflight"),
                "confirm_token": start_status.get("confirm_token"),
            }

        start_plan = self._build_effective_start_plan(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        queue_state = start_plan.get("queue_state", {})
        payload_state = start_plan.get("payload_state", {})
        self.data.setdefault("queue", {})
        self.data["queue"].setdefault(vacuum_entity_id, {})
        self.data["queue"][vacuum_entity_id][str(map_id)] = queue_state
        self.data.setdefault("payloads", {})
        self.data["payloads"].setdefault(vacuum_entity_id, {})
        self.data["payloads"][vacuum_entity_id][str(map_id)] = payload_state

        payload = payload_state.get("payload", {})
        vacuum_entity = self.hass.states.get(vacuum_entity_id)
        if vacuum_entity is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "started": False,
                "reason": "vacuum_missing",
                "message": "Vacuum entity is unavailable.",
            }

        started_at = _iso_now()
        battery_start = self._get_battery_level(vacuum_entity_id)
        job_id = self._generate_job_id()

        await self._dispatch_clean_payload(
            vacuum_entity_id=vacuum_entity_id, payload=payload
        )

        # Attach the phase sequence only for a genuine sequenced job (>1 phase).
        # Atomic jobs (every adapter today) leave the phase keys absent, keeping
        # the active-job snapshot byte-identical to pre-sequencing.
        _phases = start_plan.get("phases") or []
        active_job = build_active_job_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            queue_state=queue_state,
            payload_state=payload_state,
            phases=_phases if len(_phases) > 1 else None,
        )
        active_job["job_metadata"] = build_job_metadata_from_payload(payload_state)
        active_job["job_id"] = job_id
        active_job["started_at"] = started_at
        active_job["battery_start"] = battery_start
        active_job["current_room_started_at"] = started_at
        active_job["path_block_action"] = _normalize_path_block_action(
            path_block_action
        )
        pause_timeout_minutes_default = _normalize_pause_timeout_minutes(
            self.get_pause_timeout_settings(
                vacuum_entity_id=vacuum_entity_id
            ).get("pause_timeout_minutes_default")
        )
        active_job["pause_timeout_minutes"] = _normalize_pause_timeout_minutes(
            pause_timeout_minutes_default
            if pause_timeout_minutes_override is None
            else pause_timeout_minutes_override
        )
        active_job["water_estimate"] = self.get_planned_job_estimate(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            resolved_rooms=list(active_job.get("resolved_rooms", [])) or None,
        ).get("water_estimate")

        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        if active_job.get("current_room_id") not in (None, ""):
            self.hass.bus.async_fire(
                EVENT_ROOM_STARTED,
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "job_id": job_id,
                    "room_id": str(active_job.get("current_room_id")),
                    "room_name": self._room_name_from_active_job(
                        active_job,
                        _safe_int(active_job.get("current_room_id"), -1),
                    ),
                    "started_at": started_at,
                    "source": "job_start",
                    "completed_room_ids": active_job.get("completed_room_ids", []),
                },
            )

        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.selected_map_id = str(map_id)
        runtime.active_job_room_ids = list(queue_state.get("queue_room_ids", []))

        self._clear_room_selections_after_start(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        learning_snapshot = None
        try:
            learning_snapshot = self.save_learning_snapshot_for_active_job(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                started_at=started_at,
                battery_start=battery_start,
                job_id=job_id,
            )
        except Exception:
            _LOGGER.exception("Failed to save learning snapshot for %s map %s", vacuum_entity_id, map_id)
            learning_snapshot = {
                "saved": False,
                "reason": "snapshot_error",
            }
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "started": True,
            "reason": "started",
            "message": "Room cleaning started.",
            "warning": start_status.get("warning", False),
            "warning_message": (
                start_status["message"] if start_status.get("warning", False) else None
            ),
            "active_job": active_job,
            "learning_snapshot": learning_snapshot,
        }

    async def start_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        profile_id: str,
        confirm_reduced_run: bool = False,
        confirm_token: str | None = None,
        path_block_action: str | None = None,
        pause_timeout_minutes_override: int | None = None,
    ) -> dict[str, Any]:
        """Apply one saved run profile and start it through the normal protected path."""
        applied = self.apply_run_profile(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            profile_id=profile_id,
        )
        if not applied.get("applied"):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "profile_id": profile_id,
                "started": False,
                "reason": applied.get("reason", "profile_not_found"),
                "message": "Saved run profile could not be applied.",
                "profile": applied.get("profile"),
                "applied_room_ids": applied.get("applied_room_ids", []),
                "missing_room_ids": applied.get("missing_room_ids", []),
            }

        self.build_queue(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self.build_room_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        started = await self.start_selected_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            confirm_reduced_run=confirm_reduced_run,
            confirm_token=confirm_token,
            path_block_action=path_block_action,
            pause_timeout_minutes_override=pause_timeout_minutes_override,
        )
        started["profile_id"] = profile_id
        started["profile"] = applied.get("profile")
        return started
