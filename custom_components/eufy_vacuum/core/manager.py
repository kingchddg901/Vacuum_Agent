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
from ..profiles.room_profiles import (
    BUILT_IN_ROOM_PROFILES,
    apply_room_profile_to_config,
    get_default_room_profiles,
    merge_profile_dicts,
    normalize_room_profile,
    resolve_room_profile_for_room,
)
from ..queue.queue_engine import (
    build_active_job_state,
    build_queue_from_managed_rooms,
    build_room_clean_payload,
)
from ..rooms.room_discovery import discover_rooms_payload
from ..rooms.room_manager import build_managed_rooms, build_room_selection_summary
from ..timestamp_utils import parse_timestamp, utc_now_iso
from .capabilities import detect_capabilities
from .storage import EufyVacuumStorage


_LOGGER = logging.getLogger(__name__)
_PROTECTED_ROOM_PROFILE_NAMES = frozenset(BUILT_IN_ROOM_PROFILES.keys())

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
        except Exception:
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
        except Exception:
            _LOGGER.exception("Failed to auto-save integration data")

    def _get_learning_manager(self):
        """Return learning manager if loaded."""
        return self.hass.data.get(DOMAIN, {}).get(DATA_LEARNING)

    def _get_battery_level(self, vacuum_entity_id: str) -> int:
        """Return current battery level from sensor first, then vacuum entity."""
        return _get_battery_level_impl(self.hass, vacuum_entity_id)

    def _normalize_water_level_key(
        self,
        value: Any,
        *,
        aliases: dict[str, str] | None = None,
    ) -> str:
        """Normalize room water level into stable estimator keys.

        aliases — brand-specific display string → canonical key map, sourced
        from adapter_config.vocabulary.water_level_aliases. Callers with
        vacuum_entity_id in scope should read and pass it; pass None (or
        omit) when aliases are unavailable.
        """
        text = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
        compact = " ".join(text.split())
        # Empty input — no water level configured.
        if not compact:
            return "off"
        # Canonical keys pass through unchanged.
        if compact in {"off", "low", "medium", "high"}:
            return compact
        # Adapter alias lookup.
        if aliases:
            mapped = aliases.get(compact)
            if mapped is not None:
                return mapped
        # Unknown values pass through as-is.
        return compact

    def _water_rate_ml_per_minute(
        self,
        water_level: Any,
        *,
        aliases: dict[str, str] | None = None,
    ) -> float:
        """Return first-pass floor application water rate by water level."""
        normalized = self._normalize_water_level_key(water_level, aliases=aliases)
        rates = {
            "off": 0.0,
            "low": 3.2,
            "medium": 4.0,
            "high": 5.3,
        }
        return rates.get(normalized, 4.0)

    def _get_station_clean_water_percent(
        self,
        *,
        vacuum_entity_id: str,
        capabilities: dict[str, Any] | None = None,
    ) -> float | None:
        """Return current dock clean-water percent when exposed as a numeric state."""
        caps = capabilities or self.get_vacuum_capabilities(vacuum_entity_id=vacuum_entity_id, refresh=False)
        station_water_entity = caps.get("entities", {}).get("water_level") or caps.get("entities", {}).get("station_water")
        state = self.hass.states.get(station_water_entity) if station_water_entity else None
        if state is None:
            return None

        percent = _safe_float(state.state, -1.0)
        if percent < 0:
            return None
        return max(min(percent, 100.0), 0.0)

    def _get_water_model_config(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return model-based water configuration if known."""
        _water_model_configs = (_get_adapter_config(vacuum_entity_id) or {}).get("water_model_configs", {})
        model_meta = self._get_upkeep_model_meta(vacuum_entity_id=vacuum_entity_id)
        model_code = model_meta.get("code")
        config = dict(_water_model_configs.get(model_code or "", {}))
        config["model_code"] = model_code
        config["model_name"] = model_meta.get("name")
        config["available"] = bool(config)
        return config

    def _derive_wash_frequency_config(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return current mop-wash cadence configuration from helper entities."""
        _wf_entities = (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {})
        mode_entity_id = _wf_entities.get("wash_frequency_mode")
        interval_entity_id = _wf_entities.get("wash_frequency_value_time")
        mode_state = self.hass.states.get(mode_entity_id)
        interval_state = self.hass.states.get(interval_entity_id)

        _wf_vocab = (_get_adapter_config(vacuum_entity_id) or {}).get("vocabulary", {})
        _wash_freq_aliases: dict[str, str] = _wf_vocab.get("wash_frequency_mode_aliases") or {}
        raw_mode = str(mode_state.state if mode_state is not None else "").strip().lower().replace("-", " ").replace("_", " ")
        compact_mode = " ".join(raw_mode.split())
        mode_key = _wash_freq_aliases.get(compact_mode, "unknown")

        interval_minutes = _safe_float(interval_state.state if interval_state is not None else None, 20.0)
        if interval_minutes <= 0:
            interval_minutes = 20.0
        interval_minutes = max(15.0, min(25.0, interval_minutes))

        return {
            "mode": mode_key,
            "mode_label": mode_state.state if mode_state is not None else None,
            "mode_entity_id": mode_entity_id,
            "interval_entity_id": interval_entity_id,
            "interval_minutes": round(interval_minutes, 2),
            "mode_available": mode_state is not None,
            "interval_available": interval_state is not None,
        }

    # ------------------------------------------------------------------
    # Water usage estimation
    # ------------------------------------------------------------------

    def estimate_job_water_usage(
        self,
        *,
        vacuum_entity_id: str,
        resolved_rooms: list[dict[str, Any]],
        room_timeline: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Estimate clean-water usage for the current job plan."""
        model_config = self._get_water_model_config(vacuum_entity_id=vacuum_entity_id)
        if not model_config.get("available"):
            return {
                "available": False,
                "reason": "model_unsupported",
                "message": "No water model is available for this vacuum.",
            }

        _water_vocab = (_get_adapter_config(vacuum_entity_id) or {}).get("vocabulary", {})
        _water_level_aliases: dict[str, str] = _water_vocab.get("water_level_aliases") or {}
        capabilities = self.get_vacuum_capabilities(vacuum_entity_id=vacuum_entity_id, refresh=False)
        station_water_percent = self._get_station_clean_water_percent(
            vacuum_entity_id=vacuum_entity_id,
            capabilities=capabilities,
        )
        wash_config = self._derive_wash_frequency_config(vacuum_entity_id=vacuum_entity_id)

        timeline_by_room_id: dict[int, dict[str, Any]] = {}
        timeline_by_slug: dict[str, dict[str, Any]] = {}
        for entry in room_timeline or []:
            room_id = _safe_int(entry.get("room_id", -1), -1)
            slug = str(entry.get("slug", "")).strip().lower()
            if room_id >= 0:
                timeline_by_room_id[room_id] = entry
            if slug:
                timeline_by_slug[slug] = entry

        robot_water_used_ml = 0.0
        projected_mop_minutes = 0.0
        mopping_room_count = 0
        rooms: list[dict[str, Any]] = []

        for room in resolved_rooms or []:
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            slug = str(room.get("slug", "")).strip().lower()
            clean_mode = str(room.get("clean_mode", "")).strip().lower()
            water_level = room.get("water_level")
            clean_intensity = str(room.get("clean_intensity", "")).strip() or None
            path_type = str(room.get("path_type", "")).strip() or None
            clean_passes = _safe_int(room.get("clean_passes"), 1)
            edge_mopping = bool(room.get("edge_mopping", False))
            selected_profile_name = str(room.get("selected_profile_name", "")).strip() or None
            resolved_profile_name = str(room.get("resolved_profile_name", "")).strip() or None
            timeline_entry = timeline_by_room_id.get(room_id) if room_id >= 0 else None
            if timeline_entry is None and slug:
                timeline_entry = timeline_by_slug.get(slug)
            estimated_minutes = _safe_float(
                timeline_entry.get("minutes") if isinstance(timeline_entry, dict) else None,
                0.0,
            )
            # Gate on the user's clean_mode choice, not on water_level. If the
            # user picked vacuum_mop or mop, the dock will still wash the pad
            # after the run regardless of water flow during cleaning — and
            # _water_rate_ml_per_minute already returns 0 ml/min for
            # water_level=off, so robot-water accounting stays self-correcting.
            # Water level is a knob within mop mode, not a gate on whether
            # mop mode is active.
            is_mop = "mop" in clean_mode
            room_robot_water_ml = 0.0
            if is_mop:
                mopping_room_count += 1
                if estimated_minutes > 0:
                    projected_mop_minutes += estimated_minutes
                    room_robot_water_ml = estimated_minutes * self._water_rate_ml_per_minute(water_level, aliases=_water_level_aliases)
                    robot_water_used_ml += room_robot_water_ml

            room_entry = {
                "room_id": room_id if room_id >= 0 else None,
                "name": str(room.get("name", "")).strip() or None,
                "slug": slug or None,
                "clean_mode": clean_mode,
                "water_level": water_level,
                "clean_intensity": clean_intensity,
                "path_type": path_type,
                "clean_passes": clean_passes,
                "edge_mopping": edge_mopping,
                "selected_profile_name": selected_profile_name,
                "resolved_profile_name": resolved_profile_name,
                "effective_clean_mode": clean_mode,
                "effective_water_level": water_level,
                "effective_clean_intensity": clean_intensity,
                "effective_path_type": path_type,
                "effective_clean_passes": clean_passes,
                "effective_edge_mopping": edge_mopping,
                "estimated_minutes": round(estimated_minutes, 2),
                "estimated_robot_water_used_ml": round(room_robot_water_ml, 2),
                "mop_active": is_mop,
            }
            room_entry.update(
                _settings_profile_display(
                    room_name=room_entry.get("name") or room_entry.get("slug"),
                    selected_profile_name=selected_profile_name,
                    resolved_profile_name=resolved_profile_name,
                    clean_mode=clean_mode,
                    clean_intensity=clean_intensity,
                    fan_speed=room.get("fan_speed"),
                    water_level=water_level,
                    path_type=path_type,
                    clean_passes=clean_passes,
                    edge_mopping=edge_mopping,
                )
            )
            room_entry.update(
                _room_surface_labels(
                    floor_type=room.get("floor_type"),
                )
            )
            rooms.append(room_entry)

        if wash_config["mode"] == "by_room":
            wash_cycle_count = mopping_room_count
        elif wash_config["mode"] == "by_time" and projected_mop_minutes > 0:
            wash_cycle_count = int(projected_mop_minutes // max(wash_config["interval_minutes"], 1.0))
        else:
            wash_cycle_count = 0

        # Pre-wash + post-wash always happen when any mopping is on the plan,
        # regardless of frequency mode. Floor at 2 so a single short mopped
        # room (by_room=1) or a sub-interval mop run (by_time=0) still
        # accounts for both bookend washes.
        if mopping_room_count > 0:
            wash_cycle_count = max(wash_cycle_count, 2)

        robot_internal_tank_ml = _safe_float(model_config.get("robot_internal_tank_ml"), 0.0)
        dock_clean_tank_capacity_ml = _safe_float(model_config.get("dock_clean_tank_capacity_ml"), 0.0)
        dock_wash_overhead_ml_per_cycle = _safe_float(model_config.get("dock_wash_overhead_ml_per_cycle"), 0.0)

        estimated_dock_refill_water_used_ml = robot_water_used_ml
        estimated_dock_wash_water_used_ml = wash_cycle_count * dock_wash_overhead_ml_per_cycle
        estimated_total_dock_clean_water_used_ml = (
            estimated_dock_refill_water_used_ml + estimated_dock_wash_water_used_ml
        )

        available_clean_tank_ml = None
        estimated_clean_tank_remaining_ml = None
        estimated_clean_tank_remaining_percent = None
        clean_water_shortfall_ml = None
        low_clean_water_margin = False
        not_enough_clean_water = False

        if station_water_percent is not None and dock_clean_tank_capacity_ml > 0:
            available_clean_tank_ml = round((station_water_percent / 100.0) * dock_clean_tank_capacity_ml, 2)
            estimated_clean_tank_remaining_ml = round(
                available_clean_tank_ml - estimated_total_dock_clean_water_used_ml,
                2,
            )
            estimated_clean_tank_remaining_percent = round(
                max(min((estimated_clean_tank_remaining_ml / dock_clean_tank_capacity_ml) * 100.0, 100.0), 0.0),
                2,
            )
            clean_water_shortfall_ml = round(
                max(estimated_total_dock_clean_water_used_ml - available_clean_tank_ml, 0.0),
                2,
            )
            not_enough_clean_water = clean_water_shortfall_ml > 0
            low_clean_water_margin = (
                not not_enough_clean_water
                and estimated_clean_tank_remaining_ml is not None
                and estimated_clean_tank_remaining_ml <= 300.0
            )

        return {
            "available": True,
            "reason": "ready",
            "message": "Water usage estimate ready.",
            "model_code": model_config.get("model_code"),
            "model_name": model_config.get("model_name"),
            "robot_internal_tank_ml": round(robot_internal_tank_ml, 2),
            "dock_clean_tank_capacity_ml": round(dock_clean_tank_capacity_ml, 2),
            "station_clean_water_percent": station_water_percent,
            "available_clean_tank_ml": available_clean_tank_ml,
            "wash_frequency_mode": wash_config.get("mode"),
            "wash_frequency_mode_label": wash_config.get("mode_label"),
            "wash_interval_minutes": wash_config.get("interval_minutes"),
            "wash_cycle_count": wash_cycle_count,
            "dock_wash_overhead_ml_per_cycle": round(dock_wash_overhead_ml_per_cycle, 2),
            "mopping_room_count": mopping_room_count,
            "projected_mop_minutes": round(projected_mop_minutes, 2),
            "estimated_robot_water_used_ml": round(robot_water_used_ml, 2),
            "estimated_dock_refill_water_used_ml": round(estimated_dock_refill_water_used_ml, 2),
            "estimated_dock_wash_water_used_ml": round(estimated_dock_wash_water_used_ml, 2),
            "estimated_total_dock_clean_water_used_ml": round(estimated_total_dock_clean_water_used_ml, 2),
            "estimated_clean_tank_remaining_ml": estimated_clean_tank_remaining_ml,
            "estimated_clean_tank_remaining_percent": estimated_clean_tank_remaining_percent,
            "clean_water_shortfall_ml": clean_water_shortfall_ml,
            "not_enough_clean_water": not_enough_clean_water,
            "low_clean_water_margin": low_clean_water_margin,
            "rooms": rooms,
        }

    # ------------------------------------------------------------------
    # Active job tracking
    # ------------------------------------------------------------------

    def _parse_job_timestamp(self, value: str | None) -> datetime | None:
        """Parse persisted job timestamps."""
        return parse_timestamp(value)

    def _default_active_job_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return the default active-job structure."""
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "queue_room_ids": [],
            "queue_stable_keys": [],
            "queue_rooms": [],
            "payload": {"map_id": str(map_id), "rooms": []},
            "resolved_rooms": [],
            "room_count": 0,
            "status": "idle",
            "paused_at": None,
            "paused_duration_seconds": 0,
            "completed_room_ids": [],
            "completed_rooms": [],
            "current_room_id": None,
            "current_room_started_at": None,
            "current_room_paused_seconds": 0,
            "observed_mid_job_recharge": False,
            "observed_mid_job_recharge_started_at": None,
            "observed_mid_job_recharge_count": 0,
            "recharge_seconds_accumulated": 0,
            "pending_mid_job_recharge_return": False,
            "pending_mid_job_recharge_return_at": None,
            "observed_mop_wash_count": 0,
            "observed_mop_wash_last_at": None,
            # Per-cycle observation log. List of {"observed_at": <iso ts>}.
            # Tracks individual wash events (vs. the rollup count above) so
            # post-job analysis can correlate wash cadence with mop minutes.
            "observed_mop_wash_cycles": [],
            "state_transitions": [],
            "water_estimate": None,
            "path_block_action": "event_only",
            "pause_timeout_minutes": 0,
            "has_observed_active_lifecycle": False,
        }

    def _derive_active_job_current_room_id(self, active_job: dict[str, Any]) -> int | None:
        """Return the next unresolved room id for an active job."""
        completed_ids = {
            _safe_int(room_id, -1)
            for room_id in active_job.get("completed_room_ids", [])
            if _safe_int(room_id, -1) >= 0
        }

        for room in active_job.get("resolved_rooms", []):
            room_id = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            if room_id >= 0 and room_id not in completed_ids:
                return room_id

        for room_id in active_job.get("queue_room_ids", []):
            normalized = _safe_int(room_id, -1)
            if normalized >= 0 and normalized not in completed_ids:
                return normalized

        return None

    def _normalize_active_job(self, active_job: dict[str, Any]) -> dict[str, Any]:
        """Ensure an active-job record contains progress fields."""
        normalized = dict(active_job) if isinstance(active_job, dict) else {}
        normalized.setdefault("queue_room_ids", [])
        normalized.setdefault("queue_stable_keys", [])
        normalized.setdefault("queue_rooms", [])
        normalized.setdefault("payload", {})
        normalized.setdefault("resolved_rooms", [])
        normalized.setdefault("room_count", 0)
        normalized.setdefault("status", "idle")
        normalized.setdefault("paused_at", None)
        normalized.setdefault("paused_duration_seconds", 0)
        normalized.setdefault("completed_room_ids", [])
        normalized.setdefault("completed_rooms", [])
        normalized.setdefault("current_room_paused_seconds", 0)
        normalized.setdefault("observed_mid_job_recharge", False)
        normalized.setdefault("observed_mid_job_recharge_started_at", None)
        normalized.setdefault("observed_mid_job_recharge_count", 0)
        normalized.setdefault("recharge_seconds_accumulated", 0)
        normalized.setdefault("pending_mid_job_recharge_return", False)
        normalized.setdefault("pending_mid_job_recharge_return_at", None)
        normalized.setdefault("observed_mop_wash_count", 0)
        normalized.setdefault("observed_mop_wash_last_at", None)
        normalized.setdefault("observed_mop_wash_cycles", [])
        normalized.setdefault("state_transitions", [])
        normalized.setdefault("water_estimate", None)
        normalized.setdefault("has_observed_active_lifecycle", False)
        normalized["path_block_action"] = _normalize_path_block_action(
            normalized.get("path_block_action")
        )
        normalized["pause_timeout_minutes"] = _normalize_pause_timeout_minutes(
            normalized.get("pause_timeout_minutes")
        )

        if "current_room_id" not in normalized:
            normalized["current_room_id"] = self._derive_active_job_current_room_id(normalized)

        if "current_room_started_at" not in normalized:
            normalized["current_room_started_at"] = normalized.get("started_at")

        return normalized

    def _compute_current_room_elapsed_minutes(
        self,
        *,
        active_job: dict[str, Any],
        now: str | None = None,
    ) -> float:
        """Return elapsed active minutes for the current room, excluding pauses."""
        current_started_at = str(active_job.get("current_room_started_at", "")).strip()
        started_dt = self._parse_job_timestamp(current_started_at)
        now_dt = self._parse_job_timestamp(now or _iso_now())
        if started_dt is None or now_dt is None:
            return 0.0

        elapsed_seconds = max(int((now_dt - started_dt).total_seconds()), 0)
        paused_seconds = max(_safe_int(active_job.get("current_room_paused_seconds"), 0), 0)
        paused_at = str(active_job.get("paused_at", "")).strip()
        paused_dt = self._parse_job_timestamp(paused_at)
        if paused_dt is not None and active_job.get("status") == "paused":
            paused_seconds += max(int((now_dt - paused_dt).total_seconds()), 0)

        return round(max((elapsed_seconds - paused_seconds) / 60.0, 0.0), 2)

    def _is_charging(self, vacuum_entity_id: str) -> bool:
        """Definitive "is the vacuum charging right now" check."""
        return _is_charging_impl(self.hass, vacuum_entity_id)

    def _is_low_battery_return_state(
        self,
        *,
        current_battery: int,
        vacuum_state: str | None,
        task_status: str | None,
    ) -> bool:
        """Return whether the robot is returning to dock due to low battery."""
        return _is_low_battery_return_state_impl(
            current_battery=current_battery,
            vacuum_state=vacuum_state,
            task_status=task_status,
        )

    def update_active_job_recharge_observation(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Record that the active job has actually entered a recharge-like state."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        vacuum_state = self.hass.states.get(vacuum_entity_id)
        _recharge_entities = (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {})
        task_status_state = self.hass.states.get(_recharge_entities.get("task_status"))
        current_battery = self._get_battery_level(vacuum_entity_id)
        observed_at_value = observed_at or _iso_now()

        if self._is_low_battery_return_state(
            current_battery=current_battery,
            vacuum_state=vacuum_state.state if vacuum_state is not None else None,
            task_status=task_status_state.state if task_status_state is not None else None,
        ):
            if not bool(active_job.get("pending_mid_job_recharge_return", False)):
                active_job["pending_mid_job_recharge_return"] = True
                active_job["pending_mid_job_recharge_return_at"] = observed_at_value

        if not bool(active_job.get("pending_mid_job_recharge_return", False)):
            self.data.setdefault("active_jobs", {})
            self.data["active_jobs"].setdefault(vacuum_entity_id, {})
            self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
            return active_job

        if not self._is_charging(vacuum_entity_id):
            self.data.setdefault("active_jobs", {})
            self.data["active_jobs"].setdefault(vacuum_entity_id, {})
            self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
            return active_job

        tracker = self.hass.data.get(DOMAIN, {}).get("mapping_tracker")

        if bool(active_job.get("observed_mid_job_recharge", False)):
            # Recharge already in progress — check if it ended (vacuum resumed cleaning).
            if not self._is_charging(vacuum_entity_id):
                started_str = str(active_job.get("observed_mid_job_recharge_started_at") or "").strip()
                if started_str:
                    started_dt = parse_timestamp(started_str)
                    ended_dt = parse_timestamp(observed_at_value)
                    if started_dt and ended_dt and ended_dt > started_dt:
                        elapsed = int((ended_dt - started_dt).total_seconds())
                        current = max(_safe_int(active_job.get("recharge_seconds_accumulated"), 0), 0)
                        active_job["recharge_seconds_accumulated"] = current + elapsed
                active_job["observed_mid_job_recharge"] = False
                active_job["observed_mid_job_recharge_started_at"] = None
                if tracker is not None:
                    tracker.resume_sampling(vacuum_entity_id)
            self.data.setdefault("active_jobs", {})
            self.data["active_jobs"].setdefault(vacuum_entity_id, {})
            self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
            return active_job

        active_job["observed_mid_job_recharge"] = True
        active_job["observed_mid_job_recharge_started_at"] = observed_at_value
        active_job["observed_mid_job_recharge_count"] = max(
            _safe_int(active_job.get("observed_mid_job_recharge_count"), 0),
            0,
        ) + 1
        active_job["pending_mid_job_recharge_return"] = False
        active_job["pending_mid_job_recharge_return_at"] = None

        if tracker is not None:
            tracker.pause_sampling(vacuum_entity_id)

        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    _MOP_WASH_DEBOUNCE_SECONDS = 60

    def update_active_job_mop_wash_observation(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Record a debounced mop-wash event on the active job.

        The dock_status "Washing" state flips 1-2 times within a ~30-second
        window per actual wash cycle. A 60-second cooldown collapses those
        noise flips into a single counted event.
        """
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        now_str = observed_at or _iso_now()
        last_at = active_job.get("observed_mop_wash_last_at")

        if last_at:
            try:
                last_dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
                now_dt = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
                if (now_dt - last_dt).total_seconds() < self._MOP_WASH_DEBOUNCE_SECONDS:
                    return active_job
            except Exception:
                pass

        active_job["observed_mop_wash_count"] = (
            _safe_int(active_job.get("observed_mop_wash_count"), 0) + 1
        )
        active_job["observed_mop_wash_last_at"] = now_str

        # Append per-cycle timestamp. Capped at 50 to bound storage in case
        # dock_status oscillates beyond what the 60s debounce above catches —
        # a real mop-heavy job has 5-10 wash cycles, so this is wildly more
        # than expected.
        cycles = [
            entry for entry in (active_job.get("observed_mop_wash_cycles") or [])
            if isinstance(entry, dict)
        ]
        cycles.append({"observed_at": now_str})
        active_job["observed_mop_wash_cycles"] = cycles[-50:]

        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    def record_active_job_transition(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        entity_id: str,
        from_state: str | None,
        to_state: str | None,
        changed_at: str | None = None,
    ) -> dict[str, Any]:
        """Append one relevant state transition to the tracked active job."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        from_state_n = str(from_state or "").strip()
        to_state_n = str(to_state or "").strip()
        if not to_state_n or from_state_n == to_state_n:
            return active_job

        transitions = [
            dict(entry)
            for entry in active_job.get("state_transitions", [])
            if isinstance(entry, dict)
        ]
        transitions.append(
            {
                "entity_id": entity_id,
                "from_state": from_state_n,
                "to_state": to_state_n,
                "changed_at": changed_at or _iso_now(),
            }
        )
        active_job["state_transitions"] = transitions[-12:]

        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    def _room_name_from_active_job(self, active_job: dict[str, Any], room_id: int | None) -> str | None:
        """Return room name for one room id from active-job state."""
        if room_id is None:
            return None
        normalized_room_id = _safe_int(room_id, -1)
        if normalized_room_id < 0:
            return None

        for room in active_job.get("resolved_rooms", []):
            candidate = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            if candidate == normalized_room_id:
                return str(room.get("name", room.get("room_name", room.get("slug", "")))).strip() or None

        for room in active_job.get("queue_rooms", []):
            candidate = _safe_int(room.get("room_id", room.get("id", -1)), -1)
            if candidate == normalized_room_id:
                return str(room.get("name", room.get("room_name", room.get("slug", "")))).strip() or None

        return None

    def _timing_completion_threshold_minutes(self, room: dict[str, Any]) -> float:
        """Return a conservative elapsed-minutes threshold for timing rollover."""
        estimated_minutes = max(_safe_float(room.get("minutes"), 0.0), 1.0)
        confidence_score = max(min(_safe_float(room.get("confidence_score"), 0.0), 1.0), 0.0)
        sample_count = max(_safe_int(room.get("sample_count"), 0), 0)
        drift_ratio = max(_safe_float(room.get("accuracy_drift_ratio"), 0.0), 0.0)

        if confidence_score >= 0.85:
            overrun_ratio = 0.06
        elif confidence_score >= 0.65:
            overrun_ratio = 0.10
        elif confidence_score >= 0.45:
            overrun_ratio = 0.15
        else:
            overrun_ratio = 0.22

        slack_minutes = max(0.75, estimated_minutes * overrun_ratio)

        if sample_count <= 1:
            slack_minutes += 1.0
        elif sample_count <= 3:
            slack_minutes += 0.5

        if drift_ratio > 0:
            slack_minutes += min(estimated_minutes * drift_ratio * 0.25, 1.5)

        slack_minutes = min(slack_minutes, max(4.0, estimated_minutes * 0.35))
        return round(estimated_minutes + slack_minutes, 2)

    # Floor on elapsed-cleaning time before the mapping tracker's
    # fast-rollover signal is acted on. Calibrated to the smallest room
    # in a representative install with no floor blockers — anything
    # finished faster than this is much more likely a transit through
    # the room than a genuine clean. The tracker's own time/movement-
    # factor model already filters most noise; this is a final floor.
    _MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER = 1.5  # 90 s

    def _robot_outside_room_bounds(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
    ) -> bool | None:
        """Return True/False if the robot's current position is outside the
        room's learned bounds, or None when either the position or the
        bounds aren't available (caller should treat as "unknown" — neither
        triggers nor blocks rollover).
        """
        pos = self._get_robot_position(vacuum_entity_id)
        if pos is None:
            return None

        mapping_manager = self.hass.data.get(DOMAIN, {}).get("mapping_manager")
        if mapping_manager is None:
            return None

        try:
            bounds_snapshot = mapping_manager.get_room_bounds_snapshot(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
        except Exception:
            _LOGGER.debug(
                "EufyManager: bounds snapshot fetch failed (vacuum=%s room=%s)",
                vacuum_entity_id, room_id,
            )
            return None

        room_bounds = (
            bounds_snapshot.get("rooms", {})
            .get(str(room_id), {})
            .get("bounds")
        )
        if room_bounds is None:
            return None

        vx, vy = pos
        inside = (
            room_bounds["min_x"] <= vx <= room_bounds["max_x"]
            and room_bounds["min_y"] <= vy <= room_bounds["max_y"]
        )
        return not inside

    def _maybe_roll_current_room_by_timing(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        active_job: dict[str, Any],
        raw_timeline: list[dict[str, Any]],
        current_room_id: int | None,
        current_room_elapsed_minutes: float,
        completed_room_ids: list[int],
    ) -> dict[str, Any]:
        """Advance one room when elapsed time + bounds together justify rollover.

        Two paths:
          - **Slow room**: timing has reached or exceeded the per-room
            learned threshold AND the robot has left the room's bounds
            (single-sample bounds check — we already waited for timing).
            Fires ``EVENT_ROOM_FINISHED`` with ``source="timing_rollover"``.
          - **Fast room**: the mapping tracker's confidence model has
            decided the robot finished and exited the room (set via the
            ``_pending_fast_rollover`` flag on active_job — see
            ``MappingTracker._signal_fast_rollover``). The tracker's
            time-in-room - movement-count threshold filters doorway
            transits; we additionally require ``elapsed >=
            _MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER`` as a final floor.
            Fires ``EVENT_ROOM_FINISHED`` with ``source="bounds_exit_early"``.
        """
        if active_job.get("status") != "started":
            return active_job
        if current_room_id is None:
            return active_job

        unresolved_room_ids = [
            _safe_int(room.get("room_id", -1), -1)
            for room in raw_timeline
            if _safe_int(room.get("room_id", -1), -1) not in completed_room_ids
        ]
        if current_room_id not in unresolved_room_ids:
            return active_job

        current_index = unresolved_room_ids.index(current_room_id)
        if current_index >= len(unresolved_room_ids) - 1:
            return active_job

        current_room = next(
            (
                dict(room)
                for room in raw_timeline
                if _safe_int(room.get("room_id", -1), -1) == current_room_id
            ),
            None,
        )
        if not current_room:
            return active_job

        threshold_minutes = self._timing_completion_threshold_minutes(current_room)
        elapsed = current_room_elapsed_minutes

        if elapsed < threshold_minutes:
            # Fast-room path: only the mapping tracker's confidence
            # signal can advance us before the timing threshold. The
            # signal lives on active_job as _pending_fast_rollover and
            # is consumed (popped) when we act on it.
            pending = active_job.get("_pending_fast_rollover")
            if not isinstance(pending, dict):
                return active_job
            try:
                signalled_room_id = int(pending.get("room_id"))
            except (TypeError, ValueError):
                signalled_room_id = None
            if signalled_room_id != current_room_id:
                # Stale signal for a room the queue has already moved
                # past — leave it; the next confident exit overwrites.
                return active_job
            if elapsed < self._MIN_ELAPSED_MIN_FOR_BOUNDS_ROLLOVER:
                return active_job

            # Consume the signal so it can't trigger again on the next tick.
            active_job.pop("_pending_fast_rollover", None)
            rollover_source = "bounds_exit_early"
        else:
            # Slow-room path: timing has reached threshold; require the
            # robot to be outside bounds before allowing rollover. A
            # single sample is sufficient here because the room already
            # ran long — we're confirming completion, not detecting it.
            # When bounds are unavailable, timing alone wins (matches
            # pre-existing behaviour).
            outside = self._robot_outside_room_bounds(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                room_id=current_room_id,
            )
            if outside is False:
                return active_job
            rollover_source = "timing_rollover"

        completed_at = _iso_now()
        room_name = self._room_name_from_active_job(active_job, current_room_id)
        confidence_score = _safe_float(current_room.get("confidence_score"), 0.0)
        updated_active_job = self.record_completed_room(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=current_room_id,
            room_name=room_name,
            actual_duration_minutes=current_room_elapsed_minutes,
            completed_at=completed_at,
            source=rollover_source,
            confidence=confidence_score if confidence_score > 0 else None,
        )

        self.hass.bus.async_fire(
            EVENT_ROOM_FINISHED,
            {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "job_id": updated_active_job.get("job_id"),
                "room_id": str(current_room_id),
                "room_name": room_name,
                "completed_at": completed_at,
                "source": rollover_source,
                "actual_duration_minutes": round(current_room_elapsed_minutes, 2),
                "confidence": round(confidence_score, 4) if confidence_score > 0 else None,
                "completed_room_ids": updated_active_job.get("completed_room_ids", []),
            },
        )

        next_room_id = _safe_int(updated_active_job.get("current_room_id"), -1)
        if next_room_id >= 0:
            self.hass.bus.async_fire(
                EVENT_ROOM_STARTED,
                {
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "job_id": updated_active_job.get("job_id"),
                    "room_id": str(next_room_id),
                    "room_name": self._room_name_from_active_job(updated_active_job, next_room_id),
                    "started_at": updated_active_job.get("current_room_started_at"),
                    "source": rollover_source,
                    "completed_room_ids": updated_active_job.get("completed_room_ids", []),
                },
            )

        self.hass.async_create_task(self._async_save_logged())
        return updated_active_job

    # ------------------------------------------------------------------
    # Transition-room position detection
    # ------------------------------------------------------------------

    def _access_graph_path(
        self,
        managed_rooms: dict[str, Any],
        from_room_id: int,
        to_room_id: int,
    ) -> list[int]:
        """Return intermediate room IDs on the access-graph path from → to.

        Performs a BFS over ``grants_access_to`` edges.  Returns only the
        rooms that lie *between* from_room_id and to_room_id (neither
        endpoint is included).  Returns [] when the rooms are directly
        adjacent or no path exists.
        """
        rooms = managed_rooms.get("rooms", managed_rooms)

        # Build adjacency map: room_id → [granted_room_id, ...]
        grants_map: dict[int, list[int]] = {}
        for room_id_key, room in rooms.items():
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room_id_key), -1)
            if room_id <= 0:
                continue
            raw_grants = room.get("grants_access_to") or []
            neighbors = [_safe_int(g, -1) for g in raw_grants if _safe_int(g, -1) > 0]
            grants_map[room_id] = neighbors

        if from_room_id not in grants_map:
            return []

        # BFS — track full paths so we can extract intermediate rooms.
        from collections import deque
        queue: deque[list[int]] = deque([[from_room_id]])
        visited: set[int] = {from_room_id}

        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == to_room_id:
                return path[1:-1]   # strip from/to endpoints
            for neighbor in grants_map.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        return []   # no path found

    def _get_robot_position(self, vacuum_entity_id: str) -> tuple[float, float] | None:
        """Read the current robot X/Y from HA sensor entities.

        Returns (vx, vy) in the vacuum's native coordinate space, or None
        when the sensors are unavailable or report a non-numeric state.
        """
        caps = self.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        entities = caps.get("entities", {})
        x_entity_id = entities.get("robot_position_x")
        y_entity_id = entities.get("robot_position_y")
        if not x_entity_id or not y_entity_id:
            return None

        x_state = self.hass.states.get(x_entity_id)
        y_state = self.hass.states.get(y_entity_id)
        if x_state is None or y_state is None:
            return None

        try:
            vx = float(x_state.state)
            vy = float(y_state.state)
        except (ValueError, TypeError):
            return None

        return (vx, vy)

    def _detect_transition_room_from_position(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        from_room_id: int | None,
        to_room_id: int | None,
    ) -> int | None:
        """Return the transition room the robot is currently in, or None.

        Called when the robot has finished a queued room (by timing) but has
        not yet entered the next queued room.  Walks the access-graph path
        between the two rooms and checks the robot's live position against
        each intermediate room's learned bounds.

        Returns None when:
        - robot position is unavailable
        - no transition path exists in the access graph
        - robot is not detected inside any transition room's bounds
        """
        if from_room_id is None or to_room_id is None:
            return None

        pos = self._get_robot_position(vacuum_entity_id)
        if pos is None:
            return None
        vx, vy = pos

        managed_rooms = self.get_managed_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        transition_ids = self._access_graph_path(managed_rooms, from_room_id, to_room_id)
        if not transition_ids:
            return None

        # Fetch room bounds from the mapping manager.
        mapping_manager = self.hass.data.get(DOMAIN, {}).get("mapping_manager")
        if mapping_manager is None:
            return None

        try:
            bounds_snapshot = mapping_manager.get_room_bounds_snapshot(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
        except Exception:
            _LOGGER.debug(
                "EufyManager: failed to read room bounds for transition detection "
                "(vacuum=%s map=%s)",
                vacuum_entity_id,
                map_id,
            )
            return None

        map_rooms = bounds_snapshot.get("rooms", {})

        for t_id in transition_ids:
            bounds = map_rooms.get(str(t_id), {}).get("bounds")
            if not bounds:
                continue
            # Inline AABB check — mirrors MappingManager._point_in_bounds()
            if (
                bounds["min_x"] <= vx <= bounds["max_x"]
                and bounds["min_y"] <= vy <= bounds["max_y"]
            ):
                return t_id

        return None

    def _job_status_summary(
        self,
        *,
        active_job: dict[str, Any],
        lifecycle_state: dict[str, Any] | None = None,
        progress_snapshot: dict[str, Any] | None = None,
    ) -> str:
        """Return a concise card-facing job summary."""
        lifecycle_state = lifecycle_state or {}
        progress_snapshot = progress_snapshot or {}
        status = str(active_job.get("status", "idle")).strip().lower()
        room_name = self._room_name_from_active_job(
            active_job,
            _safe_int(progress_snapshot.get("current_room_id", active_job.get("current_room_id")), -1),
        )

        if status == "paused":
            return f"Paused in {room_name}" if room_name else "Job paused"
        if status == "started":
            return f"Cleaning {room_name}" if room_name else "Cleaning in progress"
        if status == "completed":
            outcome_status = (
                str(active_job.get("finalize_summary", {}).get("status", "")).strip().lower()
            )
            if outcome_status == "cancelled":
                return "Job cancelled"
            if outcome_status == "failed":
                return "Job failed"
            if outcome_status == "interrupted":
                return "Job interrupted"
            return "Job completed"

        lifecycle_name = str(lifecycle_state.get("lifecycle_state", "")).strip().lower()
        if lifecycle_name == "ready":
            return "Ready to start"
        if lifecycle_name == "dock_drying":
            return "Dock drying"
        return str(lifecycle_state.get("message", "")).strip() or "Idle"

    def _maintenance_status(
        self,
        *,
        remaining_hours: float,
        interval_hours: float,
    ) -> str:
        """Return maintenance status bucket for one item."""
        if interval_hours <= 0:
            return "unknown"
        ratio = remaining_hours / interval_hours
        if remaining_hours <= 0:
            return "replace_now"
        if ratio <= 0.1:
            return "replace_soon"
        if ratio <= 0.25:
            return "warning"
        return "good"

    def _replacement_status(
        self,
        *,
        state_value: Any,
    ) -> str:
        """Return replacement status bucket from upstream remaining value."""
        try:
            numeric = float(state_value)
        except (TypeError, ValueError):
            return "unknown"
        if numeric <= 5:
            return "replace_now"
        if numeric <= 15:
            return "replace_soon"
        if numeric <= 30:
            return "warning"
        return "good"

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

    def _get_upkeep_model_meta(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return upkeep model metadata derived from the upstream device registry."""
        _catalog = (_get_adapter_config(vacuum_entity_id) or {}).get("upkeep_catalog", {})
        model_names = _catalog.get("model_names", {})
        model_guide_families = _catalog.get("model_guide_families", {})
        guide_family_names = _catalog.get("guide_family_names", {})
        guide_library = _catalog.get("guide_library", {})

        model_code = self._get_registry_model_code(vacuum_entity_id=vacuum_entity_id)
        guide_family = model_guide_families.get(model_code or "")
        guide_map = guide_library.get(guide_family or "", {})
        return {
            "code": model_code,
            "name": model_names.get(model_code or "", model_code),
            "source": "device_registry" if model_code else None,
            "guide_family": guide_family,
            "guide_family_name": guide_family_names.get(guide_family or "", guide_family),
            "guide_available": bool(guide_map),
            "supported_guide_components": sorted(guide_map.keys()),
        }

    def _get_upkeep_item_guide(
        self,
        *,
        vacuum_entity_id: str,
        model_code: str | None,
        component: str,
        item_kind: str,
    ) -> dict[str, Any] | None:
        """Return model-specific upkeep guide metadata for one component."""
        _catalog = (_get_adapter_config(vacuum_entity_id) or {}).get("upkeep_catalog", {})
        model_names = _catalog.get("model_names", {})
        model_guide_families = _catalog.get("model_guide_families", {})
        guide_family_names = _catalog.get("guide_family_names", {})
        guide_library = _catalog.get("guide_library", {})

        guide_family = model_guide_families.get(model_code or "")
        guide = dict(guide_library.get(guide_family or "", {}).get(component, {}))
        if not guide:
            return None

        guide["source_model_code"] = model_code
        guide["source_model_name"] = model_names.get(model_code or "", model_code)
        guide["source_guide_family"] = guide_family
        guide["source_guide_family_name"] = guide_family_names.get(guide_family or "", guide_family)
        guide["available"] = True
        guide["maintenance"] = {
            "frequency": guide.get("clean_frequency"),
            "steps": list(guide.get("steps", [])),
            "notes": list(guide.get("notes", [])),
            "available": bool(guide.get("clean_frequency") or guide.get("steps") or guide.get("notes")),
        }
        guide["replacement"] = {
            "frequency": guide.get("replace_frequency"),
            "steps": list(guide.get("steps", [])),
            "notes": list(guide.get("notes", [])),
            "available": bool(guide.get("replace_frequency")),
        }
        guide["display_kind"] = item_kind
        guide["display"] = dict(
            guide["replacement"] if item_kind == "replacement" else guide["maintenance"]
        )
        return guide

    def _get_dock_action_entity(
        self,
        *,
        vacuum_entity_id: str,
        action: str,
    ) -> str | None:
        """Return underlying upstream button entity for one dock action."""
        object_id = vacuum_entity_id.split(".", 1)[1]
        action_candidates: dict[str, list[str]] = {
            "wash_mop": [
                f"button.{object_id}_wash_mop",
                f"button.{object_id}_mop_wash",
            ],
            "dry_mop": [
                f"button.{object_id}_dry_mop",
                f"button.{object_id}_mop_dry",
            ],
            "stop_dry_mop": [
                f"button.{object_id}_stop_dry_mop",
                f"button.{object_id}_stop_mop_dry",
            ],
            "empty_dust": [
                f"button.{object_id}_empty_dust",
                f"button.{object_id}_empty_dust_bin",
            ],
        }
        token_candidates: dict[str, list[list[str]]] = {
            "wash_mop": [["wash", "mop"]],
            "dry_mop": [["dry", "mop"], ["dry", "pad"]],
            "stop_dry_mop": [["stop", "dry", "mop"], ["stop", "dry", "pad"]],
            "empty_dust": [["empty", "dust"]],
        }

        for entity_id in action_candidates.get(action, []):
            if self.hass.states.get(entity_id) is not None:
                return entity_id
            if er.async_get(self.hass).async_get(entity_id) is not None:
                return entity_id

        for tokens in token_candidates.get(action, []):
            entity_id = self._find_button_entity_by_tokens(
                object_id=object_id,
                required_tokens=tokens,
            )
            if entity_id is not None:
                return entity_id

        return None

    def _get_replacement_reset_entity(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
    ) -> str | None:
        """Return upstream replacement reset button entity for one component."""
        object_id = vacuum_entity_id.split(".", 1)[1]
        action_candidates: dict[str, list[str]] = {
            "filter": [f"button.{object_id}_reset_filter"],
            "sensor": [f"button.{object_id}_reset_sensors", f"button.{object_id}_reset_sensor"],
            "side_brush": [f"button.{object_id}_reset_side_brush"],
            "rolling_brush": [f"button.{object_id}_reset_rolling_brush"],
            "mopping_cloth": [f"button.{object_id}_reset_mopping_cloth"],
            "cleaning_tray": [f"button.{object_id}_reset_cleaning_tray"],
            "swivel_wheel": [f"button.{object_id}_reset_swivel_replacement", f"button.{object_id}_reset_swivel_wheel"],
        }
        token_candidates: dict[str, list[list[str]]] = {
            "filter": [["reset", "filter"]],
            "sensor": [["reset", "sensor"], ["reset", "sensors"]],
            "side_brush": [["reset", "side", "brush"]],
            "rolling_brush": [["reset", "rolling", "brush"]],
            "mopping_cloth": [["reset", "mopping", "cloth"], ["reset", "mop", "cloth"]],
            "cleaning_tray": [["reset", "cleaning", "tray"]],
            "swivel_wheel": [["reset", "swivel", "replacement"], ["reset", "swivel"]],
        }

        registry = er.async_get(self.hass)
        for entity_id in action_candidates.get(component, []):
            if self.hass.states.get(entity_id) is not None:
                return entity_id
            if registry.async_get(entity_id) is not None:
                return entity_id

        for tokens in token_candidates.get(component, []):
            entity_id = self._find_button_entity_by_tokens(
                object_id=object_id,
                required_tokens=tokens,
            )
            if entity_id is not None and "maintenance" not in entity_id.lower():
                return entity_id

        return None

    # ------------------------------------------------------------------
    # Dock actions
    # ------------------------------------------------------------------

    def get_dock_action_status(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return gated dock-action state for one vacuum/map."""
        capabilities = self.get_vacuum_capabilities(vacuum_entity_id=vacuum_entity_id, refresh=False)
        lifecycle = self.get_lifecycle_state(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        vacuum_state = self.hass.states.get(vacuum_entity_id)
        dock_status = str(lifecycle.get("dock_status") or "").strip().lower()
        vacuum_state_value = str(vacuum_state.state if vacuum_state is not None else "").strip().lower()
        docked = vacuum_state_value == "docked"
        active_job_running = active_job.get("status") in {"started", "paused"}

        # Resolve dock state vocabulary from adapter registry.
        # dock_events.triggers maps framework event keys to the dock_status strings
        # that signal each dock action is currently in progress.
        # vocabulary.hard_service_states covers the generic "dock busy" catch-all.
        # Fall back to the imported Eufy constants when the adapter doesn't declare them.
        _adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        _dock_triggers = _adapter_cfg.get("dock_events", {}).get("triggers", {})
        _adapter_vocab = _adapter_cfg.get("vocabulary", {})

        def _vocab_set(trigger_key: str) -> frozenset[str]:
            raw = _dock_triggers.get(trigger_key)
            if raw is not None:
                return frozenset(str(s).strip().lower() for s in raw)
            return frozenset()

        _wash_states: frozenset[str] = _vocab_set("last_mop_wash") or frozenset({"washing", "washing mop"})
        _dry_states: frozenset[str] = _vocab_set("last_dry_start") or frozenset({"drying", "drying mop", "drying pads", "mop drying"})
        _empty_states: frozenset[str] = _vocab_set("last_dust_empty") or frozenset({"emptying dust", "emptying dust bin", "dust emptying"})
        _hard_service_states: frozenset[str] = frozenset(
            str(s).strip().lower() for s in _adapter_vocab.get("hard_service_states", [])
        )

        def build_action_status(*, action: str, supported: bool, action_entity: str | None) -> dict[str, Any]:
            reason = "ready"
            message = "Ready."
            allowed = True

            if not supported:
                reason = "unsupported_feature"
                message = "This vacuum does not support that dock action."
                allowed = False
            elif action_entity is None:
                reason = "missing_action_entity"
                message = "The upstream dock control entity was not found."
                allowed = False
            elif active_job_running:
                reason = "job_active"
                message = "Finish, pause, or cancel the tracked job before using dock actions."
                allowed = False
            elif not docked:
                reason = "not_docked"
                message = "The vacuum must be docked before using that dock action."
                allowed = False
            elif action == "wash_mop" and dock_status in _wash_states:
                reason = "already_washing"
                message = "The dock is already washing the mop."
                allowed = False
            elif action == "dry_mop" and dock_status in _dry_states:
                reason = "already_drying"
                message = "The dock is already drying the mop."
                allowed = False
            elif action == "stop_dry_mop" and dock_status not in _dry_states:
                reason = "not_drying"
                message = "Stop dry is only useful while the dock is actively drying."
                allowed = False
            elif action == "empty_dust" and dock_status in _empty_states:
                reason = "already_emptying"
                message = "The dock is already emptying dust."
                allowed = False
            elif action != "stop_dry_mop" and dock_status in _hard_service_states:
                reason = "dock_busy"
                message = "The dock is currently busy with another service action."
                allowed = False

            return {
                "supported": supported,
                "entity_id": action_entity,
                "allowed": allowed,
                "reason": reason,
                "reason_label": _display_label(reason),
                "message": message,
            }

        wash_entity = self._get_dock_action_entity(vacuum_entity_id=vacuum_entity_id, action="wash_mop")
        dry_entity = self._get_dock_action_entity(vacuum_entity_id=vacuum_entity_id, action="dry_mop")
        stop_dry_entity = self._get_dock_action_entity(vacuum_entity_id=vacuum_entity_id, action="stop_dry_mop")
        empty_entity = self._get_dock_action_entity(vacuum_entity_id=vacuum_entity_id, action="empty_dust")

        actions = {
            "wash_mop": build_action_status(
                action="wash_mop",
                supported=bool(capabilities.get("supports_mop_wash")),
                action_entity=wash_entity,
            ),
            "dry_mop": build_action_status(
                action="dry_mop",
                supported=bool(capabilities.get("supports_mop_dry")),
                action_entity=dry_entity,
            ),
            "stop_dry_mop": build_action_status(
                action="stop_dry_mop",
                supported=bool(capabilities.get("supports_mop_dry")),
                action_entity=stop_dry_entity,
            ),
            "empty_dust": build_action_status(
                action="empty_dust",
                supported=bool(capabilities.get("supports_empty_dust")),
                action_entity=empty_entity,
            ),
        }

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "docked": docked,
            "dock_status": lifecycle.get("dock_status"),
            "dock_status_label": _display_label(lifecycle.get("dock_status")),
            "lifecycle_state": lifecycle.get("lifecycle_state"),
            "lifecycle_state_label": _display_label(lifecycle.get("lifecycle_state")),
            "lifecycle_message": lifecycle.get("message"),
            "active_job_status": active_job.get("status"),
            "active_job_status_label": _display_label(active_job.get("status")),
            "actions": actions,
            "can_wash_mop": actions["wash_mop"]["allowed"],
            "can_dry_mop": actions["dry_mop"]["allowed"],
            "can_stop_dry_mop": actions["stop_dry_mop"]["allowed"],
            "can_empty_dust": actions["empty_dust"]["allowed"],
            "updated_at": _iso_now(),
        }

    async def _async_run_dock_action(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        action: str,
    ) -> dict[str, Any]:
        """Run one gated dock action via the upstream button entity."""
        status = self.get_dock_action_status(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        action_status = dict(status.get("actions", {}).get(action, {}))
        if not action_status.get("allowed", False):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "action": action,
                "performed": False,
                "allowed": False,
                "reason": action_status.get("reason"),
                "message": action_status.get("message"),
                "dock_status": status.get("dock_status"),
                "lifecycle_state": status.get("lifecycle_state"),
            }

        entity_id = action_status.get("entity_id")
        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "action": action,
            "performed": True,
            "allowed": True,
            "reason": "performed",
            "message": "Dock action sent.",
            "entity_id": entity_id,
            "dock_status": status.get("dock_status"),
            "lifecycle_state": status.get("lifecycle_state"),
        }

    async def async_wash_mop(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Run gated wash-mop action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            action="wash_mop",
        )

    async def async_dry_mop(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Run gated dry-mop action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            action="dry_mop",
        )

    async def async_empty_dust(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Run gated empty-dust action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            action="empty_dust",
        )

    async def async_stop_dry_mop(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Run gated stop-dry-mop action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            action="stop_dry_mop",
        )

    def _generate_job_id(self) -> str:
        """Generate stable job id."""
        return f"job_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"

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
    # Room profiles (clean settings presets)
    # ------------------------------------------------------------------

    def get_room_profiles(self) -> dict[str, Any]:
        """Return available room profiles."""
        self.data.setdefault("profiles", {})
        stored_profiles = self.data["profiles"].get("room_profiles", {})
        merged = merge_profile_dicts(
            built_in_profiles=get_default_room_profiles(),
            stored_profiles=stored_profiles,
        )

        return {
            "profile_count": len(merged),
            "profiles": merged,
            "protected_profile_names": sorted(_PROTECTED_ROOM_PROFILE_NAMES),
        }

    def _get_custom_room_profile_store(self) -> dict[str, Any]:
        """Return mutable storage for custom room profiles."""
        self.data.setdefault("profiles", {})
        self.data["profiles"].setdefault("room_profiles", {})
        return self.data["profiles"]["room_profiles"]

    def _get_editable_room_profile(self, profile_name: str) -> tuple[str, dict[str, Any] | None]:
        """Return one editable custom room profile by name."""
        normalized = str(profile_name or "").strip()
        if not normalized or normalized in _PROTECTED_ROOM_PROFILE_NAMES:
            return normalized, None
        stored_profiles = self._get_custom_room_profile_store()
        profile = stored_profiles.get(normalized)
        return normalized, profile if isinstance(profile, dict) else None

    def save_user_room_profile(
        self,
        *,
        label: str,
        clean_mode: str,
        fan_speed: str,
        water_level: str,
        clean_intensity: str,
        clean_passes: int,
        edge_mopping: bool,
        profile_name: str | None = None,
    ) -> dict[str, Any]:
        """Save one custom room profile."""
        self.data.setdefault("profiles", {})
        self.data["profiles"].setdefault("room_profiles", {})

        target_profile_name = str(profile_name or "").strip() or "user_1"
        if target_profile_name in _PROTECTED_ROOM_PROFILE_NAMES:
            return {
                "saved": False,
                "reason": "protected_profile",
                "profile_name": target_profile_name,
                "message": "Core built-in room profiles cannot be overwritten.",
            }

        profile = normalize_room_profile(
            {
                "label": label,
                "clean_mode": clean_mode,
                "fan_speed": fan_speed,
                "water_level": water_level,
                "clean_intensity": clean_intensity,
                "clean_passes": clean_passes,
                "edge_mopping": edge_mopping,
            }
        )
        self.data["profiles"]["room_profiles"][target_profile_name] = profile

        return {
            "saved": True,
            "profile_name": target_profile_name,
            "profile": profile,
        }

    def overwrite_room_profile(
        self,
        *,
        profile_name: str,
        label: str,
        clean_mode: str,
        fan_speed: str,
        water_level: str,
        clean_intensity: str,
        clean_passes: int,
        edge_mopping: bool,
    ) -> dict[str, Any]:
        """Overwrite one existing custom room profile from explicit fields."""
        normalized_name, existing = self._get_editable_room_profile(profile_name)
        if normalized_name in _PROTECTED_ROOM_PROFILE_NAMES:
            return {
                "overwritten": False,
                "reason": "protected_profile",
                "profile_name": normalized_name,
                "message": "Core built-in room profiles cannot be overwritten.",
            }
        if existing is None:
            return {
                "overwritten": False,
                "reason": "profile_not_found",
                "profile_name": normalized_name,
            }

        saved = self.save_user_room_profile(
            profile_name=normalized_name,
            label=label,
            clean_mode=clean_mode,
            fan_speed=fan_speed,
            water_level=water_level,
            clean_intensity=clean_intensity,
            clean_passes=clean_passes,
            edge_mopping=edge_mopping,
        )
        return {
            "overwritten": bool(saved.get("saved")),
            "profile_name": saved.get("profile_name", normalized_name),
            "profile": saved.get("profile"),
            "reason": saved.get("reason"),
            "message": saved.get("message"),
        }

    def save_room_profile_from_room(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        label: str,
        profile_name: str | None = None,
    ) -> dict[str, Any]:
        """Save a new custom room profile from one room's current effective settings."""
        clean_label = str(label or "").strip()
        if not clean_label:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "saved": False,
                "reason": "missing_label",
            }

        map_bucket = get_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        rooms = map_bucket.get("rooms", {})
        room = rooms.get(str(int(room_id)))
        if not isinstance(room, dict):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "saved": False,
                "reason": "room_not_found",
            }

        effective = self.get_effective_room_details(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            room_id=int(room_id),
        )
        if not isinstance(effective, dict):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "saved": False,
                "reason": "room_details_unavailable",
            }

        target_profile_name = str(profile_name or "").strip() or self._generate_room_profile_id()
        if target_profile_name in _PROTECTED_ROOM_PROFILE_NAMES:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "saved": False,
                "reason": "protected_profile",
                "profile_name": target_profile_name,
                "message": "Core built-in room profiles cannot be overwritten.",
            }
        saved = self.save_user_room_profile(
            profile_name=target_profile_name,
            label=clean_label,
            clean_mode=str(effective.get("clean_mode", room.get("clean_mode", "vacuum"))),
            fan_speed=str(effective.get("fan_speed", room.get("fan_speed", "Max"))),
            water_level=str(effective.get("water_level", room.get("water_level", "Off"))),
            clean_intensity=str(effective.get("clean_intensity", room.get("clean_intensity", "Standard"))),
            clean_passes=int(effective.get("default_clean_passes", room.get("clean_passes", 1))),
            edge_mopping=bool(effective.get("default_edge_mopping", room.get("edge_mopping", False))),
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": int(room_id),
            "saved": True,
            "profile_name": saved.get("profile_name"),
            "profile": saved.get("profile"),
        }

    def overwrite_room_profile_from_room(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        profile_name: str,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Overwrite one existing custom room profile from one room's current settings."""
        normalized_name, existing = self._get_editable_room_profile(profile_name)
        if normalized_name in _PROTECTED_ROOM_PROFILE_NAMES:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "overwritten": False,
                "reason": "protected_profile",
                "profile_name": normalized_name,
                "message": "Core built-in room profiles cannot be overwritten.",
            }
        if existing is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "overwritten": False,
                "reason": "profile_not_found",
                "profile_name": normalized_name,
            }

        target_label = str(label or existing.get("label") or "").strip()
        if not target_label:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": int(room_id),
                "overwritten": False,
                "reason": "missing_label",
                "profile_name": normalized_name,
            }

        saved = self.save_room_profile_from_room(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            room_id=int(room_id),
            label=target_label,
            profile_name=normalized_name,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": int(room_id),
            "overwritten": bool(saved.get("saved")),
            "profile_name": saved.get("profile_name", normalized_name),
            "profile": saved.get("profile"),
            "reason": saved.get("reason"),
            "message": saved.get("message"),
        }

    def rename_room_profile(
        self,
        *,
        profile_name: str,
        new_profile_name: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Rename one existing custom room profile key and/or display label."""
        normalized_name, existing = self._get_editable_room_profile(profile_name)
        if normalized_name in _PROTECTED_ROOM_PROFILE_NAMES:
            return {
                "renamed": False,
                "reason": "protected_profile",
                "profile_name": normalized_name,
                "message": "Core built-in room profiles cannot be renamed.",
            }
        if existing is None:
            return {
                "renamed": False,
                "reason": "profile_not_found",
                "profile_name": normalized_name,
            }

        target_name = str(new_profile_name or normalized_name).strip() or normalized_name
        if target_name in _PROTECTED_ROOM_PROFILE_NAMES:
            return {
                "renamed": False,
                "reason": "protected_profile",
                "profile_name": normalized_name,
                "target_profile_name": target_name,
                "message": "Core built-in room profile names are reserved.",
            }

        stored_profiles = self._get_custom_room_profile_store()
        if target_name != normalized_name and target_name in stored_profiles:
            return {
                "renamed": False,
                "reason": "profile_name_exists",
                "profile_name": normalized_name,
                "target_profile_name": target_name,
            }

        updated_profile = dict(existing)
        if label is not None:
            clean_label = str(label).strip()
            if not clean_label:
                return {
                    "renamed": False,
                    "reason": "missing_label",
                    "profile_name": normalized_name,
                }
            updated_profile["label"] = clean_label

        if target_name != normalized_name:
            del stored_profiles[normalized_name]
        stored_profiles[target_name] = updated_profile

        return {
            "renamed": True,
            "profile_name": target_name,
            "previous_profile_name": normalized_name,
            "profile": updated_profile,
        }

    def delete_room_profile(self, *, profile_name: str) -> dict[str, Any]:
        """Delete one existing custom room profile."""
        normalized_name, existing = self._get_editable_room_profile(profile_name)
        if normalized_name in _PROTECTED_ROOM_PROFILE_NAMES:
            return {
                "deleted": False,
                "reason": "protected_profile",
                "profile_name": normalized_name,
                "message": "Core built-in room profiles cannot be deleted.",
            }
        if existing is None:
            return {
                "deleted": False,
                "reason": "profile_not_found",
                "profile_name": normalized_name,
            }

        stored_profiles = self._get_custom_room_profile_store()
        del stored_profiles[normalized_name]
        return {
            "deleted": True,
            "profile_name": normalized_name,
        }

    def _protected_room_config(self, room: dict[str, Any]) -> dict[str, Any]:
        """Return a room config with impossible mode/surface combinations removed.

        Carpet rooms are downgraded away from mop-only modes; any non-mop mode
        clears water_level and edge_mopping regardless of floor type.
        """
        protected = dict(room)

        floor_type = str(protected.get("floor_type", "")).lower()
        clean_mode = str(protected.get("clean_mode", "")).lower()

        is_carpet = floor_type.startswith("carpet")
        is_mop_mode = "mop" in clean_mode or "wash" in clean_mode

        if is_carpet:
            if clean_mode in {"mop", "vacuum_mop"}:
                protected["clean_mode"] = "vacuum"
                clean_mode = "vacuum"
                is_mop_mode = False

            protected["water_level"] = "Off"
            protected["edge_mopping"] = False

        if not is_mop_mode:
            protected["water_level"] = "Off"
            protected["edge_mopping"] = False

        return protected

    def _finalize_room_update(self, room: dict[str, Any]) -> dict[str, Any]:
        """Return a fully sanitized room dict produced by the protection → derive → profile-match pipeline.

        Applies carpet/mop invariants, syncs ``path_type`` from the resolved profile,
        and snaps ``profile_name`` to the best-matching preset (or ``"custom"``).
        Returns a new dict; does not mutate the input.
        """
        result = self._protected_room_config(room)
        # path_type is profile-derived — write it back so reads never need
        # to re-resolve the profile just to get this field.
        _stored_profiles = self.data.get("profiles", {}).get("room_profiles", {})
        _resolved = resolve_room_profile_for_room(
            room_config=result,
            stored_profiles=_stored_profiles,
        )
        result["path_type"] = _resolved.get("path_type")
        matched = self._match_profile_from_fields(result)
        result["profile_name"] = matched if matched else "custom"
        return result

    def get_effective_room_details(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int | str,
    ) -> dict[str, Any] | None:
        """Return the resolved and protection-sanitized settings for one stored room.

        Returns None if the room is not found on the given map.
        """
        map_bucket = get_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        rooms = map_bucket.get("rooms", {})
        room = rooms.get(str(room_id))
        if room is None:
            return None

        stored_profiles = self.data.get("profiles", {}).get("room_profiles", {})
        resolved = resolve_room_profile_for_room(
            room_config=room,
            stored_profiles=stored_profiles,
        )
        protected = self._protected_room_config(
            {
                **room,
                "clean_mode": resolved.get("clean_mode"),
                "fan_speed": resolved.get("fan_speed"),
                "water_level": resolved.get("water_level"),
                "clean_intensity": resolved.get("clean_intensity"),
                "clean_passes": resolved.get("clean_passes", room.get("clean_passes", 1)),
                "edge_mopping": resolved.get("edge_mopping", room.get("edge_mopping", False)),
            }
        )
        clean_mode = str(protected.get("clean_mode", "")).lower()

        return {
            "clean_mode": protected.get("clean_mode"),
            "fan_speed": protected.get("fan_speed"),
            "water_level": protected.get("water_level"),
            "clean_intensity": protected.get("clean_intensity"),
            "path_type": resolved.get("path_type"),
            "default_clean_passes": protected.get("clean_passes", 1),
            "default_edge_mopping": protected.get("edge_mopping", False),
            "mop_required": "mop" in clean_mode or "wash" in clean_mode,
            "selected_profile_name": resolved.get("selected_profile_name"),
            "resolved_profile_name": resolved.get("resolved_profile_name"),
            "floor_type": room.get("floor_type"),
            "floor_type_label": get_floor_type_label(room.get("floor_type", "hardwood")),
        }


    def _normalize_profile_match_value(self, value: Any) -> Any:
        """Normalize room/profile values before preset matching."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        lowered = text.lower()

        if lowered == "off":
            return "off"
        if lowered == "true":
            return True
        if lowered == "false":
            return False

        try:
            return float(text)
        except (TypeError, ValueError):
            return lowered

    def _match_profile_from_fields(self, room: dict[str, Any]) -> str | None:
        """Return matching profile name if protected room fields match a preset."""
        profiles = self.get_room_profiles()["profiles"]
        protected_room = self._protected_room_config(room)

        for name, profile in profiles.items():
            effective_profile = self._protected_room_config(
                {
                    **room,
                    "clean_mode": profile.get("clean_mode"),
                    "fan_speed": profile.get("fan_speed"),
                    "water_level": profile.get("water_level"),
                    "clean_intensity": profile.get("clean_intensity"),
                    "clean_passes": profile.get(
                        "default_clean_passes",
                        profile.get("clean_passes", 1),
                    ),
                    "edge_mopping": profile.get(
                        "default_edge_mopping",
                        profile.get("edge_mopping", False),
                    ),
                }
            )

            if (
                self._normalize_profile_match_value(protected_room.get("clean_mode"))
                == self._normalize_profile_match_value(effective_profile.get("clean_mode"))
                and self._normalize_profile_match_value(protected_room.get("fan_speed"))
                == self._normalize_profile_match_value(effective_profile.get("fan_speed"))
                and self._normalize_profile_match_value(protected_room.get("water_level"))
                == self._normalize_profile_match_value(effective_profile.get("water_level"))
                and self._normalize_profile_match_value(protected_room.get("clean_intensity"))
                == self._normalize_profile_match_value(effective_profile.get("clean_intensity"))
                and self._normalize_profile_match_value(protected_room.get("clean_passes", 1))
                == self._normalize_profile_match_value(effective_profile.get("clean_passes", 1))
                and self._normalize_profile_match_value(protected_room.get("edge_mopping", False))
                == self._normalize_profile_match_value(effective_profile.get("edge_mopping", False))
            ):
                return name

        return None

    def apply_room_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_ids: list[int] | list[str],
        profile_name: str,
    ) -> dict[str, Any]:
        """Apply a room profile to one or more rooms on a map."""
        profiles = self.get_room_profiles()["profiles"]
        profile = profiles.get(profile_name)

        if profile is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "profile_name": profile_name,
                "updated_room_ids": [],
                "error": "profile_not_found",
            }

        map_bucket = ensure_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        rooms = map_bucket.get("rooms", {})
        updated_room_ids: list[int] = []

        normalized_ids: set[int] = set()
        for raw_room_id in room_ids:
            try:
                normalized_ids.add(int(raw_room_id))
            except (TypeError, ValueError):
                continue

        for room_id in normalized_ids:
            room_key = str(room_id)
            room = rooms.get(room_key)
            if room is None:
                continue

            updated_room = self._finalize_room_update(
                apply_room_profile_to_config(
                    room_config=room,
                    profile_name=profile_name,
                    profile=profile,
                )
            )

            rooms[room_key] = updated_room
            updated_room_ids.append(room_id)

        map_bucket["rooms"] = rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)
        self._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._room_history_cache_ready.discard(vacuum_entity_id)

        self._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "profile_name": profile_name,
            "updated_room_ids": sorted(updated_room_ids),
            "room_count": len(updated_room_ids),
        }

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

    def discover_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str | None = None,
    ) -> dict[str, Any]:
        """Discover rooms for one vacuum and cache them in ``data["discovery"]``.

        Does not create a map bucket.  Map buckets are created only when
        ``save_managed_rooms`` is called after the user confirms the room list.
        """
        self.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)

        payload = discover_rooms_payload(
            self.hass,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        _disc_map_id = str(payload.get("active_map_id") or map_id or "")
        self.data.setdefault("discovery", {})
        self.data["discovery"].setdefault(vacuum_entity_id, {})[_disc_map_id] = payload

        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.active_map_id = payload.get("active_map_id")

        return payload

    def save_managed_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        enabled_room_ids: list[int] | list[str] | None = None,
        floor_types: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        """Convert discovered rooms into managed room configuration and save it."""
        self.ensure_vacuum_record(vacuum_entity_id=vacuum_entity_id)

        discovery = (
            self.data.get("discovery", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        discovered_rooms = discovery.get("rooms", [])

        filtered_rooms = [
            room for room in discovered_rooms if str(room.get("map_id")) == str(map_id)
        ]

        map_bucket = ensure_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        existing_rooms = map_bucket.get("rooms", {})

        managed_rooms = build_managed_rooms(
            discovered_rooms=filtered_rooms,
            existing_rooms=existing_rooms,
            enabled_room_ids=enabled_room_ids,
            floor_types=floor_types or {},
        )

        map_bucket["rooms"] = managed_rooms
        summary = build_room_selection_summary(managed_rooms=managed_rooms)
        map_bucket["summary"] = summary
        self._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._room_history_cache_ready.discard(vacuum_entity_id)

        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.selected_map_id = str(map_id)

        if managed_rooms:
            self.mark_rooms_discovered(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            for room_id_key in managed_rooms:
                self.confirm_floor_type(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    room_id=room_id_key,
                )

        self._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_count": len(managed_rooms),
            "rooms": managed_rooms,
            "summary": summary,
        }

    def get_managed_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return managed room config for one vacuum/map."""
        map_bucket = get_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        rooms = map_bucket.get("rooms", {})
        summary = map_bucket.get("summary", build_room_selection_summary(managed_rooms=rooms))

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_count": len(rooms),
            "rooms": {
                key: {
                    k: list(v) if isinstance(v, list) else v
                    for k, v in value.items()
                }
                for key, value in rooms.items()
                if isinstance(value, dict)
            },
            "summary": summary,
            "metadata": {k: dict(v) if isinstance(v, dict) else v for k, v in map_bucket.get("metadata", {}).items()},
        }

    def remove_map(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Remove one imported map and all associated integration data.

        Does not affect the upstream Eufy map.  Callers must fire
        ``_notify_rooms_updated`` afterward so platform callbacks remove
        stale entities.  Returns a summary of what was removed.
        """
        map_id_str = str(map_id)
        removed: dict[str, Any] = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_str,
            "rooms_removed": 0,
            "history_removed": False,
            "rule_status_removed": False,
            "discovery_removed": False,
            "active_job_cleared": False,
        }

        vacuum_maps = self.data.get("maps", {}).get(vacuum_entity_id, {})
        if map_id_str in vacuum_maps:
            rooms = vacuum_maps[map_id_str].get("rooms", {})
            removed["rooms_removed"] = len(rooms)
            del vacuum_maps[map_id_str]

        disc = self.data.get("discovery", {}).get(vacuum_entity_id, {})
        if map_id_str in disc:
            del disc[map_id_str]
            removed["discovery_removed"] = True

        hist = self.data.get("room_history", {}).get(vacuum_entity_id, {})
        if map_id_str in hist:
            del hist[map_id_str]
            removed["history_removed"] = True

        rule_st = self.data.get("room_rule_status", {}).get(vacuum_entity_id, {})
        if map_id_str in rule_st:
            del rule_st[map_id_str]
            removed["rule_status_removed"] = True

        # Reset the active-job slot to a blank state rather than deleting it,
        # so callers can always find a key for any known vacuum/map pair.
        vac_jobs = self.data.get("active_jobs", {}).get(vacuum_entity_id, {})
        if map_id_str in vac_jobs:
            vac_jobs[map_id_str] = self._default_active_job_state(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id_str,
            )
            removed["active_job_cleared"] = True

        # Drop stale room-id references from any remaining map's access graph.
        remaining_maps = self.data.get("maps", {}).get(vacuum_entity_id, {})
        for other_bucket in remaining_maps.values():
            for room in other_bucket.get("rooms", {}).values():
                gat = room.get("grants_access_to")
                if isinstance(gat, list) and gat:
                    room["grants_access_to"] = [
                        rid for rid in gat
                        if rid not in removed.get("_deleted_room_ids", set())
                    ]

        return removed

    def get_vacuum_maps(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return summary of known maps for one vacuum."""
        return get_vacuum_maps_summary(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
        )

    def rebuild_map(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        preserve_existing_settings: bool = True,
    ) -> dict[str, Any]:
        """Rebuild one map from the latest discovered rooms."""
        discovery = (
            self.data.get("discovery", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
        discovered_rooms = discovery.get("rooms", [])

        filtered_rooms = [
            room for room in discovered_rooms if str(room.get("map_id")) == str(map_id)
        ]

        rebuilt = rebuild_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            discovered_rooms=filtered_rooms,
            preserve_existing_settings=preserve_existing_settings,
        )

        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.selected_map_id = str(map_id)

        self._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._notify_rooms_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        return rebuilt

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

    def _get_saved_run_profile_store(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Return the saved run-profile library for one vacuum/map."""
        self.data.setdefault("run_profiles", {})
        self.data["run_profiles"].setdefault(vacuum_entity_id, {})
        self.data["run_profiles"][vacuum_entity_id].setdefault(str(map_id), {})
        store = self.data["run_profiles"][vacuum_entity_id][str(map_id)]
        return store if isinstance(store, dict) else {}

    def _snapshot_room_for_run_profile(self, room: dict[str, Any]) -> dict[str, Any]:
        """Return the persisted room fields relevant to a saved run profile."""
        return {
            "room_id": int(room.get("room_id")),
            "name": room.get("name"),
            "slug": room.get("slug"),
            "order": int(room.get("order", 999)),
            "profile_name": str(room.get("profile_name", "vacuum_quick")),
            "clean_mode": str(room.get("clean_mode", "vacuum")),
            "fan_speed": str(room.get("fan_speed", "Max")),
            "water_level": str(room.get("water_level", "Off")),
            "clean_intensity": str(room.get("clean_intensity", "Standard")),
            "clean_passes": int(room.get("clean_passes", 1)),
            "edge_mopping": bool(room.get("edge_mopping", False)),
        }

    def _run_profile_summary(self, rooms: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a compact human-facing summary for one saved run profile."""
        room_names = [
            str(room.get("name", "")).strip()
            for room in rooms
            if isinstance(room, dict) and str(room.get("name", "")).strip()
        ]
        return {
            "room_count": len(rooms),
            "room_ids": [
                int(room.get("room_id"))
                for room in rooms
                if isinstance(room, dict) and _safe_int(room.get("room_id"), -1) >= 0
            ],
            "room_names": room_names,
            "room_names_label": ", ".join(room_names),
        }

    def _enrich_saved_run_profile(self, profile_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Return one normalized saved run profile with derived metadata."""
        rooms = profile.get("rooms", [])
        if not isinstance(rooms, list):
            rooms = []
        summary = self._run_profile_summary(rooms)
        return {
            **profile,
            "id": str(profile.get("id", profile_id)),
            "name": str(profile.get("name", "Untitled")).strip() or "Untitled",
            "room_count": int(profile.get("room_count", summary["room_count"])),
            "room_ids": list(profile.get("room_ids", summary["room_ids"])),
            "room_names": list(profile.get("room_names", summary["room_names"])),
            "room_names_label": str(profile.get("room_names_label", summary["room_names_label"])),
            "expose_as_button": bool(profile.get("expose_as_button", False)),
            "summary": str(profile.get("room_names_label", summary["room_names_label"])),
            "summary_detail": {
                "room_count": int(profile.get("room_count", summary["room_count"])),
                "room_ids": list(profile.get("room_ids", summary["room_ids"])),
                "room_names": list(profile.get("room_names", summary["room_names"])),
                "room_names_label": str(profile.get("room_names_label", summary["room_names_label"])),
            },
        }

    def _current_enabled_rooms_for_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> list[dict[str, Any]]:
        """Return current enabled rooms in queue order for run-profile save/overwrite."""
        map_bucket = get_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        rooms = map_bucket.get("rooms", {})
        enabled_rooms = [
            self._snapshot_room_for_run_profile(room)
            for room in rooms.values()
            if isinstance(room, dict) and bool(room.get("enabled", False))
        ]
        enabled_rooms.sort(key=lambda room: (int(room.get("order", 999)), str(room.get("name", ""))))
        return enabled_rooms

    def get_saved_run_profiles(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return saved multi-room run profiles for one vacuum/map."""
        library = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        profiles = []
        for profile_id, profile in library.items():
            if not isinstance(profile, dict):
                continue
            enriched = self._enrich_saved_run_profile(str(profile_id), profile)
            profiles.append(
                {
                    "id": enriched["id"],
                    "name": enriched["name"],
                    "room_count": enriched["room_count"],
                    "room_ids": enriched["room_ids"],
                    "room_names": enriched["room_names"],
                    "room_names_label": enriched["room_names_label"],
                    "expose_as_button": enriched["expose_as_button"],
                    "created_at": enriched.get("created_at"),
                    "updated_at": enriched.get("updated_at"),
                    "summary": enriched.get("room_names_label", ""),
                }
            )
        profiles.sort(key=lambda item: str(item.get("name", "")).lower())
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "profile_count": len(profiles),
            "profiles": profiles,
            "library": {
                str(profile_id): self._enrich_saved_run_profile(str(profile_id), profile)
                for profile_id, profile in library.items()
                if isinstance(profile, dict)
            },
        }

    def save_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        name: str,
        expose_as_button: bool = False,
    ) -> dict[str, Any]:
        """Save the current enabled-room run as a reusable named profile."""
        clean_name = str(name or "").strip()
        if not clean_name:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "saved": False,
                "reason": "missing_name",
            }

        enabled_rooms = self._current_enabled_rooms_for_run_profile(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        if not enabled_rooms:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "saved": False,
                "reason": "no_rooms_selected",
            }

        library = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        profile_id = self._generate_run_profile_id()
        now = _iso_now()
        summary = self._run_profile_summary(enabled_rooms)
        library[profile_id] = {
            "id": profile_id,
            "name": clean_name,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_count": summary["room_count"],
            "room_ids": summary["room_ids"],
            "room_names": summary["room_names"],
            "room_names_label": summary["room_names_label"],
            "expose_as_button": bool(expose_as_button),
            "rooms": enabled_rooms,
            "created_at": now,
            "updated_at": now,
        }
        self._notify_run_profiles_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "saved": True,
            "profile_id": profile_id,
            "profile": self._enrich_saved_run_profile(profile_id, library[profile_id]),
        }

    def overwrite_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        profile_id: str,
        name: str | None = None,
        expose_as_button: bool | None = None,
    ) -> dict[str, Any]:
        """Overwrite one saved run profile with the current enabled-room run snapshot."""
        library = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        existing = library.get(profile_id)
        if not isinstance(existing, dict):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "overwritten": False,
                "reason": "profile_not_found",
                "profile_id": profile_id,
            }

        enabled_rooms = self._current_enabled_rooms_for_run_profile(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        if not enabled_rooms:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "overwritten": False,
                "reason": "no_rooms_selected",
                "profile_id": profile_id,
            }

        clean_name = str(name if name is not None else existing.get("name", "Untitled")).strip() or "Untitled"
        summary = self._run_profile_summary(enabled_rooms)
        updated_profile = {
            **existing,
            "id": profile_id,
            "name": clean_name,
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_count": summary["room_count"],
            "room_ids": summary["room_ids"],
            "room_names": summary["room_names"],
            "room_names_label": summary["room_names_label"],
            "expose_as_button": bool(existing.get("expose_as_button", False) if expose_as_button is None else expose_as_button),
            "rooms": enabled_rooms,
            "updated_at": _iso_now(),
        }
        library[profile_id] = updated_profile
        self._notify_run_profiles_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "overwritten": True,
            "profile_id": profile_id,
            "profile": self._enrich_saved_run_profile(profile_id, updated_profile),
        }

    def rename_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        profile_id: str,
        name: str,
    ) -> dict[str, Any]:
        """Rename one saved run profile."""
        library = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        if profile_id not in library:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "renamed": False,
                "reason": "profile_not_found",
                "profile_id": profile_id,
            }
        clean_name = str(name or "").strip() or "Untitled"
        library[profile_id]["name"] = clean_name
        library[profile_id]["updated_at"] = _iso_now()
        self._notify_run_profiles_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "renamed": True,
            "profile_id": profile_id,
            "profile": self._enrich_saved_run_profile(profile_id, library[profile_id]),
        }

    def delete_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        profile_id: str,
    ) -> dict[str, Any]:
        """Delete one saved run profile."""
        library = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        if profile_id not in library:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "deleted": False,
                "reason": "profile_not_found",
                "profile_id": profile_id,
            }
        del library[profile_id]
        self._notify_run_profiles_updated(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "deleted": True,
            "profile_id": profile_id,
        }

    def apply_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        profile_id: str,
    ) -> dict[str, Any]:
        """Apply a saved multi-room run profile back onto map room settings."""
        library = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        profile = library.get(profile_id)
        if not isinstance(profile, dict):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "applied": False,
                "reason": "profile_not_found",
                "profile_id": profile_id,
            }

        map_bucket = ensure_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        rooms = map_bucket.get("rooms", {})
        if not isinstance(rooms, dict):
            rooms = {}

        for room_key, room_data in list(rooms.items()):
            if not isinstance(room_data, dict):
                continue
            rooms[room_key] = {**room_data, "enabled": False}

        applied_room_ids: list[int] = []
        missing_room_ids: list[int] = []
        for index, room_snapshot in enumerate(profile.get("rooms", []), start=1):
            if not isinstance(room_snapshot, dict):
                continue
            room_id = _safe_int(room_snapshot.get("room_id"), -1)
            if room_id < 0:
                continue
            room_key = str(room_id)
            current_room = rooms.get(room_key)
            if not isinstance(current_room, dict):
                missing_room_ids.append(room_id)
                continue

            updated_room = self._finalize_room_update(
                {
                    **current_room,
                    "enabled": True,
                    "order": index,
                    "profile_name": str(room_snapshot.get("profile_name", current_room.get("profile_name", "vacuum_quick"))),
                    "clean_mode": str(room_snapshot.get("clean_mode", current_room.get("clean_mode", "vacuum"))),
                    "fan_speed": str(room_snapshot.get("fan_speed", current_room.get("fan_speed", "Max"))),
                    "water_level": str(room_snapshot.get("water_level", current_room.get("water_level", "Off"))),
                    "clean_intensity": str(room_snapshot.get("clean_intensity", current_room.get("clean_intensity", "Standard"))),
                    "clean_passes": int(room_snapshot.get("clean_passes", current_room.get("clean_passes", 1))),
                    "edge_mopping": bool(room_snapshot.get("edge_mopping", current_room.get("edge_mopping", False))),
                }
            )
            rooms[room_key] = updated_room
            applied_room_ids.append(room_id)

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
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "applied": bool(applied_room_ids),
            "profile_id": profile_id,
            "profile": profile,
            "applied_room_ids": applied_room_ids,
            "missing_room_ids": missing_room_ids,
        }

    def _normalize_grants_access_to(
        self,
        raw_value: Any,
        *,
        room_id: int,
    ) -> list[int]:
        """Return one canonical grants_access_to list."""
        if not isinstance(raw_value, list):
            return []
        normalized: list[int] = []
        seen: set[int] = set()
        for raw_room_id in raw_value:
            target_room_id = _safe_int(raw_room_id, -1)
            if target_room_id <= 0 or target_room_id == room_id or target_room_id in seen:
                continue
            seen.add(target_room_id)
            normalized.append(target_room_id)
        return normalized

    def _normalize_room_rule(self, raw_rule: Any) -> dict[str, Any] | None:
        """Return one canonical room automation rule."""
        if not isinstance(raw_rule, dict):
            return None

        kind = str(raw_rule.get("kind", "")).strip().lower()
        if kind not in {"blocker", "modifier"}:
            return None

        operator = str(raw_rule.get("operator", "equals")).strip().lower() or "equals"
        allowed_operators = {
            "equals",
            "not_equals",
            "in",
            "not_in",
            "gt",
            "gte",
            "lt",
            "lte",
            "is_on",
            "is_off",
            "exists",
            "missing",
        }
        if operator not in allowed_operators:
            operator = "equals"

        effect = raw_rule.get("effect", {})
        if not isinstance(effect, dict):
            effect = {}

        action = str(effect.get("action", "exclude" if kind == "blocker" else "mutate")).strip().lower()
        if kind == "blocker":
            action = "exclude"
        elif action != "mutate":
            action = "mutate"

        changes: dict[str, Any] = {}
        if action == "mutate" and isinstance(effect.get("changes"), dict):
            source_changes = effect.get("changes", {})
            for key in (
                "clean_mode",
                "fan_speed",
                "water_level",
                "clean_intensity",
                "clean_passes",
                "edge_mopping",
            ):
                if key in source_changes:
                    changes[key] = source_changes.get(key)

        return {
            "id": str(raw_rule.get("id") or self._generate_room_rule_id()).strip(),
            "label": str(raw_rule.get("label", "")).strip() or None,
            "entity_id": str(raw_rule.get("entity_id", "")).strip(),
            "kind": kind,
            "operator": operator,
            "value": raw_rule.get("value"),
            "enabled": bool(raw_rule.get("enabled", True)),
            "effect": {
                "action": action,
                "reason": str(effect.get("reason", "")).strip() or None,
                "changes": changes,
            },
        }

    def _normalize_room_rules(self, raw_rules: Any) -> list[dict[str, Any]]:
        """Return canonical room automation rules."""
        if not isinstance(raw_rules, list):
            return []
        normalized: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for raw_rule in raw_rules:
            rule = self._normalize_room_rule(raw_rule)
            if not isinstance(rule, dict):
                continue
            rule_id = str(rule.get("id", "")).strip()
            if not rule_id or rule_id in seen_ids:
                rule["id"] = self._generate_room_rule_id()
                rule_id = str(rule.get("id"))
            seen_ids.add(rule_id)
            normalized.append(rule)
        return normalized

    def _normalized_managed_rooms_with_automation(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Return managed rooms with canonical automation metadata."""
        map_bucket = get_map_bucket(
            data=self.data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        managed_rooms = map_bucket.get("rooms", {})
        normalized: dict[str, dict[str, Any]] = {}
        for room_key, room_data in managed_rooms.items():
            if not isinstance(room_data, dict):
                continue
            room_id = _safe_int(room_data.get("room_id", room_key), -1)
            normalized[room_key] = {
                **room_data,
                "is_dock_room": bool(room_data.get("is_dock_room", False)),
                "grants_access_to": self._normalize_grants_access_to(
                    room_data.get("grants_access_to", []),
                    room_id=room_id,
                ),
                "rules": self._normalize_room_rules(room_data.get("rules", [])),
            }
        return normalized

    def _build_room_access_views(
        self,
        *,
        managed_rooms: dict[str, dict[str, Any]],
    ) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
        """Return grants and derived requires-access maps."""
        grants_map: dict[int, list[int]] = {}
        requires_map: dict[int, list[int]] = {}
        valid_room_ids = {
            _safe_int(room.get("room_id", room_id_key), -1)
            for room_id_key, room in managed_rooms.items()
            if isinstance(room, dict)
        }
        valid_room_ids.discard(-1)

        for room_id_key, room in managed_rooms.items():
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room_id_key), -1)
            if room_id <= 0:
                continue
            grants = [
                target_room_id
                for target_room_id in self._normalize_grants_access_to(
                    room.get("grants_access_to", []),
                    room_id=room_id,
                )
                if target_room_id in valid_room_ids
            ]
            grants_map[room_id] = grants
            requires_map.setdefault(room_id, [])
            for target_room_id in grants:
                requires_map.setdefault(target_room_id, [])
                if room_id not in requires_map[target_room_id]:
                    requires_map[target_room_id].append(room_id)

        for room_id in valid_room_ids:
            grants_map.setdefault(room_id, [])
            requires_map.setdefault(room_id, [])

        return grants_map, requires_map

    def _format_access_graph_issue(
        self,
        *,
        issue: dict[str, Any],
        room_names: dict[int, str],
    ) -> dict[str, Any]:
        """Convert one raw graph issue into a card-facing issue payload."""
        issue_type = str(issue.get("type", "")).strip().lower()

        if issue_type == "self_reference":
            room_id = _safe_int(issue.get("room_id"), -1)
            room_label = room_names.get(room_id, f"Room {room_id}") if room_id > 0 else "Room"
            return {
                "code": "self_reference",
                "message": f"{room_label} cannot grant access to itself.",
                "room_ids": [str(room_id)] if room_id > 0 else [],
            }

        if issue_type == "missing_room":
            room_id = _safe_int(issue.get("room_id"), -1)
            target_room_id = _safe_int(issue.get("target_room_id"), -1)
            room_label = room_names.get(room_id, f"Room {room_id}") if room_id > 0 else "Room"
            missing_label = f"Room {target_room_id}" if target_room_id > 0 else "Missing room"
            return {
                "code": "missing_room",
                "message": f"{room_label} still references missing room {missing_label}.",
                "room_ids": [
                    value
                    for value in (str(room_id) if room_id > 0 else None, str(target_room_id) if target_room_id > 0 else None)
                    if value is not None
                ],
            }

        if issue_type == "duplicate_edge":
            room_id = _safe_int(issue.get("room_id"), -1)
            target_room_id = _safe_int(issue.get("target_room_id"), -1)
            room_label = room_names.get(room_id, f"Room {room_id}") if room_id > 0 else "Room"
            target_label = room_names.get(target_room_id, f"Room {target_room_id}") if target_room_id > 0 else "that room"
            return {
                "code": "duplicate_edge",
                "message": f"{room_label} has the same access target listed more than once for {target_label}.",
                "room_ids": [
                    value
                    for value in (str(room_id) if room_id > 0 else None, str(target_room_id) if target_room_id > 0 else None)
                    if value is not None
                ],
            }

        if issue_type == "cycle_detected":
            cycle_rooms = [
                _safe_int(room_id, -1)
                for room_id in list(issue.get("rooms", []))
                if _safe_int(room_id, -1) > 0
            ]
            cycle_labels = [room_names.get(room_id, f"Room {room_id}") for room_id in cycle_rooms]
            return {
                "code": "cycle_detected",
                "message": f"Access links create a loop: {' -> '.join(cycle_labels)}."
                if cycle_labels
                else "Access links create a loop.",
                "room_ids": [str(room_id) for room_id in cycle_rooms],
            }

        if issue_type == "multiple_inbound":
            room_id = _safe_int(issue.get("room_id"), -1)
            source_ids = [
                _safe_int(s, -1)
                for s in list(issue.get("source_room_ids", []))
                if _safe_int(s, -1) > 0
            ]
            room_label = room_names.get(room_id, f"Room {room_id}") if room_id > 0 else "Room"
            source_labels = [room_names.get(s, f"Room {s}") for s in source_ids]
            return {
                "code": "multiple_inbound",
                "message": f"{room_label} is granted access by more than one room ({', '.join(source_labels)}). Each room can only have one inbound link.",
                "room_ids": [str(room_id) if room_id > 0 else None]
                + [str(s) for s in source_ids],
            }

        if issue_type == "missing_dock_room":
            return {
                "code": "missing_dock_room",
                "message": "One room must be marked as the dock room before access links can be considered healthy.",
                "room_ids": [],
            }

        if issue_type == "multiple_dock_rooms":
            dock_rooms = [
                _safe_int(room_id, -1)
                for room_id in list(issue.get("rooms", []))
                if _safe_int(room_id, -1) > 0
            ]
            dock_labels = [room_names.get(room_id, f"Room {room_id}") for room_id in dock_rooms]
            return {
                "code": "multiple_dock_rooms",
                "message": f"Only one dock room is allowed. Current dock rooms: {', '.join(dock_labels)}."
                if dock_labels
                else "Only one dock room is allowed.",
                "room_ids": [str(room_id) for room_id in dock_rooms],
            }

        if issue_type == "missing_dependency":
            room_id = _safe_int(issue.get("room_id"), -1)
            dock_room_id = _safe_int(issue.get("dock_room_id"), -1)
            room_label = room_names.get(room_id, f"Room {room_id}") if room_id > 0 else "Room"
            dock_label = room_names.get(dock_room_id, f"Room {dock_room_id}") if dock_room_id > 0 else "dock room"
            return {
                "code": "missing_dependency",
                "message": f"{room_label} needs an inbound dependency so it can be reached from {dock_label}.",
                "room_ids": [
                    value
                    for value in (str(room_id) if room_id > 0 else None, str(dock_room_id) if dock_room_id > 0 else None)
                    if value is not None
                ],
            }

        if issue_type == "unreachable_from_dock":
            room_id = _safe_int(issue.get("room_id"), -1)
            dock_room_id = _safe_int(issue.get("dock_room_id"), -1)
            room_label = room_names.get(room_id, f"Room {room_id}") if room_id > 0 else "Room"
            dock_label = room_names.get(dock_room_id, f"Room {dock_room_id}") if dock_room_id > 0 else "dock room"
            return {
                "code": "unreachable_from_dock",
                "message": f"{room_label} is not reachable from {dock_label} through the current access links.",
                "room_ids": [
                    value
                    for value in (str(room_id) if room_id > 0 else None, str(dock_room_id) if dock_room_id > 0 else None)
                    if value is not None
                ],
            }

        return {
            "code": issue_type or "unknown_issue",
            "message": "The access graph contains an unknown issue.",
            "room_ids": [],
        }

    def _room_access_context(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return canonical room access context for one vacuum/map."""
        managed_rooms = self._normalized_managed_rooms_with_automation(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        room_names: dict[int, str] = {}
        for room_id_key, room in managed_rooms.items():
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room_id_key), -1)
            if room_id <= 0:
                continue
            room_names[room_id] = str(room.get("name", f"Room {room_id}")).strip() or f"Room {room_id}"

        validation = self._validate_room_access_graph(managed_rooms=managed_rooms)
        grants_map, requires_map = self._build_room_access_views(managed_rooms=managed_rooms)
        formatted_issues = [
            self._format_access_graph_issue(issue=issue, room_names=room_names)
            for issue in validation.get("issues", [])
            if isinstance(issue, dict)
        ]

        missing_rooms: dict[int, dict[str, Any]] = {}
        for issue in validation.get("issues", []):
            if not isinstance(issue, dict) or str(issue.get("type", "")).strip().lower() != "missing_room":
                continue
            missing_room_id = _safe_int(issue.get("target_room_id"), -1)
            referenced_by_room_id = _safe_int(issue.get("room_id"), -1)
            if missing_room_id <= 0 or referenced_by_room_id <= 0:
                continue
            entry = missing_rooms.setdefault(
                missing_room_id,
                {
                    "missing_room_id": str(missing_room_id),
                    "missing_room_name": None,
                    "referenced_by": [],
                },
            )
            entry["referenced_by"].append(
                {
                    "room_id": str(referenced_by_room_id),
                    "room_name": room_names.get(referenced_by_room_id, f"Room {referenced_by_room_id}"),
                }
            )

        for entry in missing_rooms.values():
            entry["referenced_by"].sort(key=lambda item: str(item.get("room_name", "")).lower())

        return {
            "managed_rooms": managed_rooms,
            "room_names": room_names,
            "grants_map": grants_map,
            "requires_map": requires_map,
            "validation": validation,
            "issues": formatted_issues,
            "missing_rooms": sorted(
                missing_rooms.values(),
                key=lambda item: str(item.get("missing_room_id", "")),
            ),
        }

    # ------------------------------------------------------------------
    # Access graph editor / health
    # ------------------------------------------------------------------

    def get_room_access_editor(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int | str,
    ) -> dict[str, Any]:
        """Return the backend-authored access editor payload for one room."""
        room_id_int = _safe_int(room_id, -1)
        context = self._room_access_context(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        managed_rooms = context["managed_rooms"]
        room_key = str(room_id_int)
        room = managed_rooms.get(room_key)
        if not isinstance(room, dict):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "room_id": str(room_id),
                "reason": "room_not_found",
                "issues": [],
            }

        room_name = str(room.get("name", f"Room {room_id_int}")).strip() or f"Room {room_id_int}"
        room_names = context["room_names"]
        grants_map = context["grants_map"]
        requires_map = context["requires_map"]
        dock_room_ids = list(context["validation"].get("dock_room_ids", []))
        active_dock_room_id = dock_room_ids[0] if len(dock_room_ids) == 1 else None
        selected_valid_targets = list(grants_map.get(room_id_int, []))
        raw_selected_targets = self._normalize_grants_access_to(
            room.get("grants_access_to", []),
            room_id=room_id_int,
        )
        missing_selected_targets = [
            target_room_id
            for target_room_id in raw_selected_targets
            if target_room_id not in room_names
        ]

        editable_targets: list[dict[str, Any]] = []
        for target_room_id, target_name in sorted(room_names.items(), key=lambda item: str(item[1]).lower()):
            if target_room_id == room_id_int:
                continue

            selected = target_room_id in selected_valid_targets
            selectable = True
            reason = None

            if not selected:
                candidate_rooms = {
                    key: dict(value) if isinstance(value, dict) else value
                    for key, value in managed_rooms.items()
                }
                candidate_room = dict(candidate_rooms.get(room_key, {}))
                candidate_room["grants_access_to"] = selected_valid_targets + [target_room_id]
                candidate_rooms[room_key] = candidate_room
                candidate_validation = self._validate_room_access_graph(
                    managed_rooms=candidate_rooms,
                )
                candidate_structural_issues = self._structural_access_graph_issues(
                    candidate_validation
                )
                if candidate_structural_issues:
                    selectable = False
                    candidate_issue = next(
                        (
                            issue
                            for issue in candidate_structural_issues
                            if isinstance(issue, dict)
                            and (
                                _safe_int(issue.get("room_id"), -1) == room_id_int
                                or room_id_int in [
                                    _safe_int(issue_room_id, -1)
                                    for issue_room_id in list(issue.get("rooms", []))
                                ]
                            )
                        ),
                        None,
                    )
                    issue_type = str(candidate_issue.get("type", "")).strip().lower() if isinstance(candidate_issue, dict) else ""
                    if issue_type == "cycle_detected":
                        reason = "Would create a loop."
                    elif issue_type == "duplicate_edge":
                        reason = "Already linked."
                    elif issue_type == "missing_room":
                        reason = "Target is not available."
                    elif issue_type == "self_reference":
                        reason = "A room cannot link to itself."
                    elif issue_type == "multiple_inbound":
                        reason = "Target already has an inbound access room."
                    else:
                        reason = "Not selectable due to graph legality."

            editable_targets.append(
                {
                    "room_id": str(target_room_id),
                    "name": target_name,
                    "selectable": selectable,
                    "selected": selected,
                    "missing": False,
                    "reason": reason,
                }
            )

        for missing_room_id in missing_selected_targets:
            editable_targets.append(
                {
                    "room_id": str(missing_room_id),
                    "name": f"Missing Room {missing_room_id}",
                    "selectable": False,
                    "selected": True,
                    "missing": True,
                    "reason": "Stale reference. Remove this link to restore graph health.",
                }
            )

        room_related_issues = [
            issue
            for issue in context["issues"]
            if str(room_id_int) in list(issue.get("room_ids", []))
        ]

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": str(room_id_int),
            "name": room_name,
            "is_dock_room": bool(room.get("is_dock_room", False)),
            "dock_room_id": str(active_dock_room_id) if active_dock_room_id is not None else None,
            "grants_access_to": [str(target_room_id) for target_room_id in raw_selected_targets],
            "requires_access_from": [str(source_room_id) for source_room_id in requires_map.get(room_id_int, [])],
            "editable_targets": editable_targets,
            "inbound_rooms": [
                {
                    "room_id": str(source_room_id),
                    "name": room_names.get(source_room_id, f"Room {source_room_id}"),
                    "missing": False,
                }
                for source_room_id in sorted(requires_map.get(room_id_int, []), key=lambda item: str(room_names.get(item, f"Room {item}")).lower())
            ],
            "issues": room_related_issues,
        }

    def get_access_graph_health(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return whole-map access graph health for the card sidebar."""
        context = self._room_access_context(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "dock_room_ids": [
                str(room_id)
                for room_id in list(context["validation"].get("dock_room_ids", []))
            ],
            "missing_rooms": context["missing_rooms"],
            "issues": context["issues"],
        }

    def _validate_room_access_graph(
        self,
        *,
        managed_rooms: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Return validation result for the room access graph."""
        valid_room_ids = {
            _safe_int(room.get("room_id", room_id_key), -1)
            for room_id_key, room in managed_rooms.items()
            if isinstance(room, dict)
        }
        valid_room_ids.discard(-1)

        grants_map: dict[int, list[int]] = {}
        issues: list[dict[str, Any]] = []
        dock_room_ids: list[int] = []

        for room_id_key, room in managed_rooms.items():
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id", room_id_key), -1)
            if room_id <= 0:
                continue
            if bool(room.get("is_dock_room", False)):
                dock_room_ids.append(room_id)

            raw_targets = room.get("grants_access_to", [])
            if not isinstance(raw_targets, list):
                raw_targets = []
            seen: set[int] = set()
            grants_map[room_id] = []
            for raw_target in raw_targets:
                target_room_id = _safe_int(raw_target, -1)
                if target_room_id <= 0:
                    continue
                if target_room_id == room_id:
                    issues.append(
                        {
                            "type": "self_reference",
                            "room_id": room_id,
                            "target_room_id": target_room_id,
                        }
                    )
                    continue
                if target_room_id not in valid_room_ids:
                    issues.append(
                        {
                            "type": "missing_room",
                            "room_id": room_id,
                            "target_room_id": target_room_id,
                        }
                    )
                    continue
                if target_room_id in seen:
                    issues.append(
                        {
                            "type": "duplicate_edge",
                            "room_id": room_id,
                            "target_room_id": target_room_id,
                        }
                    )
                    continue
                seen.add(target_room_id)
                grants_map[room_id].append(target_room_id)

        # Single-inbound constraint: each non-dock room may only be
        # granted access by exactly one other room.
        inbound_count: dict[int, list[int]] = {}
        for source_id, targets in grants_map.items():
            for target_id in targets:
                inbound_count.setdefault(target_id, []).append(source_id)

        for target_id, sources in inbound_count.items():
            if len(sources) > 1:
                issues.append(
                    {
                        "type": "multiple_inbound",
                        "room_id": target_id,
                        "source_room_ids": sorted(sources),
                    }
                )

        if not dock_room_ids:
            issues.append({"type": "missing_dock_room"})
        elif len(dock_room_ids) > 1:
            issues.append({"type": "multiple_dock_rooms", "rooms": sorted(dock_room_ids)})

        if len(dock_room_ids) == 1:
            dock_room_id = dock_room_ids[0]
            grants_view, requires_view = self._build_room_access_views(
                managed_rooms=managed_rooms,
            )
            reachable: set[int] = set()
            stack = [dock_room_id]
            while stack:
                current_room_id = stack.pop()
                if current_room_id in reachable:
                    continue
                reachable.add(current_room_id)
                stack.extend(grants_view.get(current_room_id, []))

            for room_id in sorted(valid_room_ids):
                if room_id == dock_room_id:
                    continue
                if not requires_view.get(room_id):
                    issues.append(
                        {
                            "type": "missing_dependency",
                            "room_id": room_id,
                            "dock_room_id": dock_room_id,
                        }
                    )
                    continue
                if room_id not in reachable:
                    issues.append(
                        {
                            "type": "unreachable_from_dock",
                            "room_id": room_id,
                            "dock_room_id": dock_room_id,
                        }
                    )

        cycle_chain: list[int] = []
        visit_state: dict[int, int] = {}
        stack: list[int] = []

        def _visit(room_id: int) -> bool:
            nonlocal cycle_chain
            state = visit_state.get(room_id, 0)
            if state == 1:
                if room_id in stack:
                    start_index = stack.index(room_id)
                    cycle_chain = stack[start_index:] + [room_id]
                else:
                    cycle_chain = [room_id]
                return True
            if state == 2:
                return False

            visit_state[room_id] = 1
            stack.append(room_id)
            for target_room_id in grants_map.get(room_id, []):
                if _visit(target_room_id):
                    return True
            stack.pop()
            visit_state[room_id] = 2
            return False

        for room_id in grants_map:
            if visit_state.get(room_id, 0) == 0 and _visit(room_id):
                issues.append(
                    {
                        "type": "cycle_detected",
                        "rooms": cycle_chain,
                    }
                )
                break

        return {
            "valid": not issues,
            "issues": issues,
            "grants_map": grants_map,
            "dock_room_ids": sorted(dock_room_ids),
        }

    @staticmethod
    def _structural_access_graph_issues(
        validation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return only the access-graph issues that make the graph structurally illegal."""
        structural_issue_types = frozenset(
            {
                "self_reference",
                "duplicate_edge",
                "cycle_detected",
                "multiple_inbound",
                "multiple_dock_rooms",
            }
        )
        return [
            issue
            for issue in validation.get("issues", [])
            if isinstance(issue, dict)
            and str(issue.get("type", "")).strip().lower() in structural_issue_types
        ]

    @staticmethod
    def _access_graph_state(
        managed_rooms: dict[str, Any],
        validation: dict[str, Any] | None = None,
    ) -> str:
        """Return 'blank', 'partial', or 'complete' for the access graph.

        blank    — no dock room and no grants anywhere; basic runs are allowed.
        partial  — some configuration exists but the graph is not valid; worse
                   than blank, always blocked.
        complete — graph is fully valid; all runs and rules are allowed.
        """
        has_dock = any(
            isinstance(room, dict) and bool(room.get("is_dock_room", False))
            for room in managed_rooms.values()
        )
        has_grants = any(
            isinstance(room, dict) and bool(room.get("grants_access_to"))
            for room in managed_rooms.values()
        )
        if not has_dock and not has_grants:
            return "blank"
        if validation is not None:
            return "complete" if validation.get("valid") else "partial"
        return "partial"

    @staticmethod
    def _any_rooms_have_rules(managed_rooms: dict[str, Any]) -> bool:
        """Return True if any room has at least one rule configured."""
        return any(
            isinstance(room, dict) and bool(room.get("rules"))
            for room in managed_rooms.values()
        )

    # ------------------------------------------------------------------
    # Room automation rules
    # ------------------------------------------------------------------

    def _normalize_rule_operand(self, value: Any) -> Any:
        """Normalize one rule comparison operand."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value if value is not None else "").strip()
        lowered = text.lower()
        if lowered in {"true", "on"}:
            return True
        if lowered in {"false", "off"}:
            return False
        try:
            return float(text)
        except (TypeError, ValueError):
            return lowered

    def _room_rule_matches(self, rule: dict[str, Any]) -> bool:
        """Return whether one room rule matches the current HA state."""
        entity_id = str(rule.get("entity_id", "")).strip()
        operator = str(rule.get("operator", "equals")).strip().lower()
        state_obj = self.hass.states.get(entity_id) if entity_id else None

        if operator == "exists":
            return state_obj is not None
        if operator == "missing":
            return state_obj is None
        if state_obj is None:
            return False

        state_value = state_obj.state
        normalized_state = self._normalize_rule_operand(state_value)
        target_value = rule.get("value")

        if operator == "is_on":
            return str(state_value).strip().lower() == "on"
        if operator == "is_off":
            return str(state_value).strip().lower() == "off"
        if operator in {"equals", "not_equals"}:
            matched = normalized_state == self._normalize_rule_operand(target_value)
            return matched if operator == "equals" else not matched
        if operator in {"in", "not_in"}:
            options = target_value if isinstance(target_value, list) else [target_value]
            normalized_options = {
                self._normalize_rule_operand(option)
                for option in options
            }
            matched = normalized_state in normalized_options
            return matched if operator == "in" else not matched
        if operator in {"gt", "gte", "lt", "lte"}:
            try:
                state_number = float(state_value)
                target_number = float(target_value)
            except (TypeError, ValueError):
                return False
            if operator == "gt":
                return state_number > target_number
            if operator == "gte":
                return state_number >= target_number
            if operator == "lt":
                return state_number < target_number
            return state_number <= target_number

        return False

    def _room_estimate_minutes_map(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[int, float]:
        """Return estimated minutes per room for the current map."""
        learning = self._get_learning_manager()
        if learning is None:
            return {}
        try:
            estimate = learning.get_room_learning_estimates(
                self,
                vacuum_entity_id,
                str(map_id),
                current_battery=float(self._get_battery_level(vacuum_entity_id)),
            )
        except Exception:
            _LOGGER.exception("Failed to get learning estimates for %s map %s", vacuum_entity_id, map_id)
            return {}

        rooms = estimate.get("rooms", []) if isinstance(estimate, dict) else []
        minutes_map: dict[int, float] = {}
        for room in rooms:
            if not isinstance(room, dict):
                continue
            room_id = _safe_int(room.get("room_id"), -1)
            if room_id <= 0:
                continue
            minutes = room.get("minutes")
            if minutes is None:
                continue
            minutes_map[room_id] = _safe_float(minutes, 0.0)
        return minutes_map

    @staticmethod
    def _build_blocked_room_entry(
        *,
        room_id: int,
        name: str | None,
        source: str,
        reason: str,
        triggered_rule_id: str | None = None,
        trigger_entity_id: str | None = None,
        blocked_by_room_id: int | None = None,
        blocked_by_room_name: str | None = None,
    ) -> dict[str, Any]:
        """Return a canonical blocked-room record.

        Used by both ``_build_effective_start_plan`` (preflight) and
        ``get_runtime_path_block_report`` (mid-job path-block check).
        ``trigger_entity_id`` is populated only by the mid-job path.
        """
        return {
            "room_id": room_id,
            "name": name,
            "source": source,
            "reason": reason,
            "triggered_rule_id": triggered_rule_id,
            "trigger_entity_id": trigger_entity_id,
            "blocked_by_room_id": blocked_by_room_id,
            "blocked_by_room_name": blocked_by_room_name,
        }

    @staticmethod
    def _build_modified_room_entry(
        *,
        room_id: int,
        name: str | None,
        derived: bool = False,
        source_room_id: int | None = None,
        source_room_name: str | None = None,
        source_rule_id: str | None = None,
        source_rule_name: str | None = None,
    ) -> dict[str, Any]:
        """Return an initial modified-room record.

        ``changes`` and ``triggered_rule_ids`` are populated incrementally
        as matching modifier rules are accumulated after construction.

        Fan-out fields (``derived``, ``source_*``) are populated only when
        the entry is created purely by a rule fan-out expansion (a rule
        whose ``fan_out_room_ids`` includes this room, with no direct
        rule on this room). When a direct rule later contributes to the
        same entry, ``derived`` flips to False — direct rules win the
        attribution at the entry level. Per-field provenance is out of
        scope for now; ``triggered_rule_ids`` still lists every
        contributing rule for traceability.
        """
        return {
            "room_id": room_id,
            "name": name,
            "changes": {},
            "triggered_rule_ids": [],
            "derived": derived,
            "source_room_id": source_room_id,
            "source_room_name": source_room_name,
            "source_rule_id": source_rule_id,
            "source_rule_name": source_rule_name,
        }

    def _confirmation_token_for_preflight(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        selected_room_ids: list[int],
        included_room_ids: list[int],
        blocked_room_ids: list[int],
    ) -> str:
        """Return deterministic confirmation token for a reduced run."""
        digest = hashlib.sha1(
            "|".join(
                [
                    vacuum_entity_id,
                    str(map_id),
                    ",".join(str(item) for item in selected_room_ids),
                    ",".join(str(item) for item in included_room_ids),
                    ",".join(str(item) for item in blocked_room_ids),
                ]
            ).encode("utf-8")
        ).hexdigest()
        return digest[:12]

    def _build_effective_start_plan(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return the effective queue, payload, and preflight plan for a job start.

        This is the authoritative rule evaluation point for job start.  Blocker
        and modifier rules are evaluated here against live HA entity states
        immediately before the user confirms or the job fires.  Rules are not
        evaluated earlier because their conditions can change at any moment.

        The only other rule evaluation site is ``get_runtime_path_block_report``,
        which re-evaluates blocker rules mid-job as entity states change.
        """
        managed_rooms = self._normalized_managed_rooms_with_automation(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        selected_rooms = sorted(
            [
                room
                for room in managed_rooms.values()
                if isinstance(room, dict) and bool(room.get("enabled", False))
            ],
            key=lambda room: (int(room.get("order", 999)), str(room.get("name", ""))),
        )
        selected_room_ids = [int(room.get("room_id")) for room in selected_rooms]

        validation = self._validate_room_access_graph(managed_rooms=managed_rooms)
        grants_map, requires_map = self._build_room_access_views(managed_rooms=managed_rooms)

        preflight: dict[str, Any] = {
            "available": True,
            "blocked": False,
            "requires_confirmation": False,
            "confirm_token": None,
            "reason": "ready",
            "message": "Ready to start cleaning.",
            "selected_room_ids": list(selected_room_ids),
            "included_room_ids": list(selected_room_ids),
            "blocked_room_ids": [],
            "selected_room_count": len(selected_room_ids),
            "included_room_count": len(selected_room_ids),
            "blocked_room_count": 0,
            "selected_expected_minutes": 0.0,
            "included_expected_minutes": 0.0,
            "blocked_expected_minutes": 0.0,
            "blocked_ratio_rooms": 0.0,
            "blocked_ratio_time": 0.0,
            "blocked_rooms": [],
            "modified_rooms": [],
            "warnings": [],
            "graph": {
                "valid": bool(validation.get("valid", True)),
                "issues": validation.get("issues", []),
                "grants_access_to": grants_map,
                "requires_access_from": requires_map,
            },
        }

        graph_state = self._access_graph_state(
            managed_rooms=managed_rooms, validation=validation
        )
        any_rules = self._any_rooms_have_rules(managed_rooms=managed_rooms)

        _graph_block_reason: str | None = None
        _graph_block_message: str | None = None

        if graph_state == "partial":
            _graph_block_reason = "incomplete_access_graph"
            _graph_block_message = (
                "Room access graph is partially configured. "
                "Complete it or clear all access settings to allow basic runs."
            )
        elif graph_state == "blank" and any_rules:
            _graph_block_reason = "access_graph_required_for_rules"
            _graph_block_message = (
                "Room rules require a complete access graph. "
                "Configure the dock room and room connections before using rules."
            )

        if _graph_block_reason:
            preflight.update(
                {
                    "blocked": True,
                    "reason": _graph_block_reason,
                    "message": _graph_block_message,
                    "warnings": [_graph_block_reason],
                }
            )
            self._update_room_rule_status_snapshot(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                managed_rooms=managed_rooms,
                selected_room_ids=selected_room_ids,
                included_room_ids=list(selected_room_ids),
                blocked_rooms=[],
                modified_rooms=[],
                preflight=preflight,
            )
            return {
                "managed_rooms": managed_rooms,
                "queue_state": build_queue_from_managed_rooms(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    managed_rooms=managed_rooms,
                ),
                "payload_state": build_room_clean_payload(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    managed_rooms=managed_rooms,
                    queue_room_ids=selected_room_ids,
                    stored_profiles=self.data.get("profiles", {}).get("room_profiles", {}),
                    capabilities=self.get_vacuum_capabilities(
                        vacuum_entity_id=vacuum_entity_id,
                        refresh=False,
                    ),
                    dispatch=(_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {}),
                ),
                "preflight": preflight,
            }

        selected_room_id_set = set(selected_room_ids)
        all_rooms = [
            room
            for room in managed_rooms.values()
            if isinstance(room, dict)
        ]
        all_rooms_by_id = {
            int(room.get("room_id")): room
            for room in all_rooms
            if room.get("room_id") is not None
        }
        direct_blocked: dict[int, dict[str, Any]] = {}
        modifier_matches: dict[int, dict[str, Any]] = {}
        selected_rooms_by_id = {
            int(room.get("room_id")): room
            for room in selected_rooms
        }

        has_blocker_rules = any(
            rule.get("kind") == "blocker"
            for room in all_rooms
            for rule in room.get("rules", [])
            if isinstance(rule, dict)
        )
        has_access_graph = any(
            isinstance(room.get("grants_access_to"), list) and room.get("grants_access_to")
            for room in managed_rooms.values()
            if isinstance(room, dict)
        )
        if has_blocker_rules and not has_access_graph:
            preflight.update(
                {
                    "blocked": True,
                    "reason": "access_graph_required",
                    "message": "Room blockers require a manual room access graph before they can be used.",
                    "warnings": ["access_graph_required"],
                }
            )
            self._update_room_rule_status_snapshot(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                managed_rooms=managed_rooms,
                selected_room_ids=selected_room_ids,
                included_room_ids=list(selected_room_ids),
                blocked_rooms=[],
                modified_rooms=[],
                preflight=preflight,
            )
            return {
                "managed_rooms": managed_rooms,
                "queue_state": build_queue_from_managed_rooms(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    managed_rooms=managed_rooms,
                ),
                "payload_state": build_room_clean_payload(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    managed_rooms=managed_rooms,
                    queue_room_ids=selected_room_ids,
                    stored_profiles=self.data.get("profiles", {}).get("room_profiles", {}),
                    capabilities=self.get_vacuum_capabilities(
                        vacuum_entity_id=vacuum_entity_id,
                        refresh=False,
                    ),
                    dispatch=(_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {}),
                ),
                "preflight": preflight,
            }

        for room in all_rooms:
            room_id = int(room.get("room_id"))
            for rule in room.get("rules", []):
                if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
                    continue
                entity_id = str(rule.get("entity_id", "")).strip()
                if not entity_id:
                    continue
                if not self._room_rule_matches(rule):
                    continue

                effect = rule.get("effect", {}) if isinstance(rule.get("effect"), dict) else {}
                if rule.get("kind") == "blocker":
                    direct_blocked.setdefault(
                        room_id,
                        self._build_blocked_room_entry(
                            room_id=room_id,
                            name=room.get("name"),
                            source="direct_rule",
                            reason=str(effect.get("reason") or rule.get("label") or entity_id).strip() or "rule_blocked",
                            triggered_rule_id=rule.get("id"),
                        ),
                    )
                    continue

                if room_id not in selected_room_id_set or rule.get("kind") != "modifier":
                    continue

                change_set = effect.get("changes", {}) if isinstance(effect.get("changes"), dict) else {}
                if room_id not in modifier_matches:
                    modifier_matches[room_id] = self._build_modified_room_entry(
                        room_id=room_id,
                        name=room.get("name"),
                    )
                modifier_matches[room_id]["changes"].update(change_set)
                modifier_matches[room_id]["triggered_rule_ids"].append(str(rule.get("id")))

        accessible_room_ids = {
            room_id
            for room_id in all_rooms_by_id
            if not requires_map.get(room_id)
        }
        accessible_room_ids -= set(direct_blocked)

        changed = True
        while changed:
            changed = False
            for room_id in all_rooms_by_id:
                if room_id in accessible_room_ids or room_id in direct_blocked:
                    continue
                parent_ids = list(requires_map.get(room_id, []))
                if parent_ids and any(parent_id in accessible_room_ids for parent_id in parent_ids):
                    accessible_room_ids.add(room_id)
                    changed = True

        blocked_rooms: list[dict[str, Any]] = []
        blocked_room_ids: list[int] = []

        for room_id in selected_room_ids:
            if room_id in direct_blocked:
                blocked_rooms.append(direct_blocked[room_id])
                blocked_room_ids.append(room_id)
                continue
            if room_id in accessible_room_ids:
                continue

            parent_ids = list(requires_map.get(room_id, []))
            blocked_by_room_id = next(
                (
                    parent_id
                    for parent_id in parent_ids
                    if parent_id not in accessible_room_ids or parent_id in direct_blocked
                ),
                parent_ids[0] if parent_ids else None,
            )
            blocked_rooms.append(
                self._build_blocked_room_entry(
                    room_id=room_id,
                    name=selected_rooms_by_id.get(room_id, {}).get("name"),
                    source="access_dependency",
                    reason="access_blocked",
                    blocked_by_room_id=blocked_by_room_id,
                    blocked_by_room_name=selected_rooms_by_id.get(blocked_by_room_id, {}).get("name")
                    if blocked_by_room_id is not None
                    else None,
                )
            )
            blocked_room_ids.append(room_id)

        included_room_ids = [room_id for room_id in selected_room_ids if room_id not in set(blocked_room_ids)]

        # ------------------------------------------------------------------
        # Pass 2 — rule fan-out expansion.
        #
        # A modifier rule may declare ``fan_out_room_ids: [..]`` to apply
        # its effect to additional rooms beyond the rule's owning room.
        # The spec (rule fan-out, locked 2026-05-28) defines:
        #
        #   - The rule's trigger condition is evaluated independently of
        #     whether the owning room is in the selection. If the user's
        #     "quiet mode" toggle is on, fan-out targets get quiet
        #     settings even if the source bedroom is excluded from this
        #     run.
        #   - Direct rules win per field. We merge with ``setdefault`` so
        #     a target room's own direct-rule fields are preserved; only
        #     fields the direct rules did NOT set get filled in by
        #     fan-out.
        #   - Among multiple fan-out sources hitting the same target,
        #     iterate source rules in ascending source-room-id order
        #     (deterministic; first-wins per field).
        #   - Targets not in the current selection are skipped (no point
        #     modifying a room that won't be cleaned).
        #   - Targets in ``blocked_room_ids`` are skipped (same — direct
        #     modifiers also skip blocked rooms).
        #   - Self-fan-out is silently ignored; user-facing UI prevents
        #     it from being authored, this is defense in depth.
        #
        # Reporting: when an entry is created purely by fan-out (no
        # direct rule contributed first), the entry is flagged
        # ``derived: True`` with ``source_*`` fields naming the rule and
        # source room. When a direct rule already populated the entry
        # before fan-out merges in, ``derived`` stays False — direct
        # wins the entry-level attribution.
        # ------------------------------------------------------------------
        selected_set = set(selected_room_ids)
        blocked_set = set(blocked_room_ids)

        for source_room_id in sorted(all_rooms_by_id.keys()):
            source_room = all_rooms_by_id[source_room_id]
            for rule in source_room.get("rules", []):
                if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
                    continue
                if rule.get("kind") != "modifier":
                    continue
                fan_out_raw = rule.get("fan_out_room_ids")
                if not isinstance(fan_out_raw, list) or not fan_out_raw:
                    continue
                entity_id = str(rule.get("entity_id", "")).strip()
                if not entity_id:
                    continue
                if not self._room_rule_matches(rule):
                    continue

                effect = rule.get("effect", {}) if isinstance(rule.get("effect"), dict) else {}
                change_set = effect.get("changes", {}) if isinstance(effect.get("changes"), dict) else {}
                if not change_set:
                    continue

                rule_id = str(rule.get("id"))
                rule_name = rule.get("label") or entity_id
                source_name = source_room.get("name")

                for raw_target_id in fan_out_raw:
                    # Runtime filter — unknown / non-numeric IDs are
                    # silently dropped so stale references from before a
                    # room delete don't error out the planning pass.
                    try:
                        target_id = int(raw_target_id)
                    except (TypeError, ValueError):
                        continue
                    if target_id not in all_rooms_by_id:
                        continue
                    if target_id == source_room_id:
                        continue
                    if target_id not in selected_set:
                        continue
                    if target_id in blocked_set:
                        continue

                    target_room = all_rooms_by_id[target_id]
                    if target_id not in modifier_matches:
                        modifier_matches[target_id] = self._build_modified_room_entry(
                            room_id=target_id,
                            name=target_room.get("name"),
                            derived=True,
                            source_room_id=source_room_id,
                            source_room_name=source_name,
                            source_rule_id=rule_id,
                            source_rule_name=rule_name,
                        )

                    existing_changes = modifier_matches[target_id]["changes"]
                    for field_name, field_value in change_set.items():
                        existing_changes.setdefault(field_name, field_value)

                    triggered = modifier_matches[target_id]["triggered_rule_ids"]
                    if rule_id not in triggered:
                        triggered.append(rule_id)

        effective_rooms = {
            room_key: dict(room_data)
            for room_key, room_data in managed_rooms.items()
            if isinstance(room_data, dict)
        }

        next_order = 1
        modified_rooms: list[dict[str, Any]] = []
        for room_id in selected_room_ids:
            room_key = str(room_id)
            room_data = effective_rooms.get(room_key)
            if not isinstance(room_data, dict):
                continue
            if room_id in blocked_room_ids:
                effective_rooms[room_key] = {**room_data, "enabled": False}
                continue

            updates = {
                "enabled": True,
                "order": next_order,
            }
            next_order += 1
            modifier = modifier_matches.get(room_id)
            if modifier:
                updates.update(modifier.get("changes", {}))
            updated_room = self._protected_room_config({**room_data, **updates})
            matched_profile = self._match_profile_from_fields(updated_room)
            updated_room["profile_name"] = matched_profile if matched_profile else "custom"
            effective_rooms[room_key] = updated_room
            if modifier:
                modified_rooms.append(modifier)

        capabilities = self.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        queue_state = build_queue_from_managed_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=effective_rooms,
        )
        payload_state = build_room_clean_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=effective_rooms,
            queue_room_ids=queue_state.get("queue_room_ids", []),
            stored_profiles=self.data.get("profiles", {}).get("room_profiles", {}),
            capabilities=capabilities,
            dispatch=(_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {}),
        )

        room_minutes_map = self._room_estimate_minutes_map(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        selected_expected_minutes = round(
            sum(room_minutes_map.get(room_id, 0.0) for room_id in selected_room_ids),
            2,
        )
        blocked_expected_minutes = round(
            sum(room_minutes_map.get(room_id, 0.0) for room_id in blocked_room_ids),
            2,
        )
        included_expected_minutes = round(
            max(selected_expected_minutes - blocked_expected_minutes, 0.0),
            2,
        )

        blocked_ratio_rooms = (
            round(len(blocked_room_ids) / len(selected_room_ids), 4)
            if selected_room_ids
            else 0.0
        )
        blocked_ratio_time = (
            round(blocked_expected_minutes / selected_expected_minutes, 4)
            if selected_expected_minutes > 0
            else 0.0
        )

        requires_confirmation = bool(
            blocked_room_ids
            and (
                blocked_ratio_time >= 0.20
                or blocked_ratio_rooms >= 0.40
            )
        )
        confirm_token = (
            self._confirmation_token_for_preflight(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                selected_room_ids=selected_room_ids,
                included_room_ids=included_room_ids,
                blocked_room_ids=blocked_room_ids,
            )
            if requires_confirmation
            else None
        )

        message = "Ready to start cleaning."
        warnings: list[str] = []
        if blocked_room_ids:
            warnings.append("rooms_blocked")
            message = (
                f"{len(blocked_room_ids)} room(s) are blocked and will be skipped."
            )
        if requires_confirmation:
            message = (
                f"Start confirmation required: {round(blocked_ratio_time * 100)}% of expected job time "
                "will be removed by blockers."
            )

        preflight.update(
            {
                "requires_confirmation": requires_confirmation,
                "confirm_token": confirm_token,
                "reason": "confirmation_required" if requires_confirmation else ("rooms_blocked" if blocked_room_ids else "ready"),
                "message": message,
                "selected_room_ids": selected_room_ids,
                "included_room_ids": included_room_ids,
                "blocked_room_ids": blocked_room_ids,
                "selected_room_count": len(selected_room_ids),
                "included_room_count": len(included_room_ids),
                "blocked_room_count": len(blocked_room_ids),
                "selected_expected_minutes": selected_expected_minutes,
                "included_expected_minutes": included_expected_minutes,
                "blocked_expected_minutes": blocked_expected_minutes,
                "blocked_ratio_rooms": blocked_ratio_rooms,
                "blocked_ratio_time": blocked_ratio_time,
                "blocked_rooms": blocked_rooms,
                "modified_rooms": modified_rooms,
                "warnings": warnings,
            }
        )
        self._update_room_rule_status_snapshot(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=managed_rooms,
            selected_room_ids=selected_room_ids,
            included_room_ids=included_room_ids,
            blocked_rooms=blocked_rooms,
            modified_rooms=modified_rooms,
            preflight=preflight,
        )

        return {
            "managed_rooms": managed_rooms,
            "effective_rooms": effective_rooms,
            "queue_state": queue_state,
            "payload_state": payload_state,
            "preflight": preflight,
        }

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

        payload = build_room_clean_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=managed_rooms,
            queue_room_ids=queue_room_ids,
            stored_profiles=stored_profiles,
            capabilities=capabilities,
            dispatch=(_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {}),
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
        task_status_state = self.hass.states.get(_lifecycle_entities.get("task_status"))
        dock_status_state = self.hass.states.get(_lifecycle_entities.get("dock_status"))
        active_map_state = self.hass.states.get(_lifecycle_entities.get("active_map"))
        active_target_state = self.hass.states.get(_lifecycle_entities.get("active_cleaning_target"))

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

    def record_active_lifecycle_observed(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Set ``has_observed_active_lifecycle`` on the stored active-job record.

        This flag is the pre-condition for auto-finalization.  Callers that
        hold a local copy returned by ``get_active_job()`` should set the flag
        on their copy too, since ``get_active_job()`` returns a normalized copy
        rather than a live reference.
        """
        self.data.setdefault("active_jobs", {}).setdefault(vacuum_entity_id, {})
        active_job = self.data["active_jobs"][vacuum_entity_id].get(str(map_id))
        if not isinstance(active_job, dict):
            return
        active_job["has_observed_active_lifecycle"] = True
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job

    def get_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return active job state for one vacuum/map."""
        return self._normalize_active_job((
            self.data.get("active_jobs", {})
            .get(vacuum_entity_id, {})
            .get(
                str(map_id),
                self._default_active_job_state(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=map_id,
                ),
            )
        ))

    def record_active_job_sensor_value(
        self,
        *,
        vacuum_entity_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Write a sensor-derived value into all in-flight active jobs for a vacuum.

        Writes to every map bucket that has a started_at and no ended_at —
        normally only one bucket is active at a time, but the loop is
        defensive. Returns True if at least one job was updated.

        Called from the job-metrics state listener in __init__.py whenever
        a tracked sensor (cleaning_time, cleaning_area, etc.) changes during
        a run. Finalization then reads from active_job_state instead of
        issuing a live HA state read at job-end, avoiding the DPS timing race.
        """
        per_map = self.data.get("active_jobs", {}).get(vacuum_entity_id, {})
        if not isinstance(per_map, dict):
            return False
        updated = False
        for job in per_map.values():
            if not isinstance(job, dict):
                continue
            if job.get("started_at") and not job.get("ended_at"):
                job[key] = value
                updated = True
        if updated:
            try:
                self.hass.async_create_task(self.async_save())
            except Exception:
                pass
        return updated

    def clear_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Clear active job state for one vacuum/map."""
        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = self._default_active_job_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.active_job_room_ids = []

        return self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

    def pause_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        paused_at: str | None = None,
    ) -> dict[str, Any]:
        """Mark one active job as paused without losing elapsed runtime."""
        active_job = self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        if active_job.get("status") != "started":
            return active_job

        active_job["status"] = "paused"
        active_job["paused_at"] = paused_at or _iso_now()
        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    def resume_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        resumed_at: str | None = None,
    ) -> dict[str, Any]:
        """Resume one paused job and accumulate paused wall-clock time."""
        active_job = self.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        if active_job.get("status") != "paused":
            return active_job

        resumed_at_str = resumed_at or _iso_now()
        paused_seconds = _safe_int(active_job.get("paused_duration_seconds"), 0)
        paused_at_str = str(active_job.get("paused_at", "")).strip()
        paused_dt = self._parse_job_timestamp(paused_at_str)
        resumed_dt = self._parse_job_timestamp(resumed_at_str)
        if paused_dt is not None and resumed_dt is not None:
            pause_delta_seconds = max(int((resumed_dt - paused_dt).total_seconds()), 0)
            paused_seconds += pause_delta_seconds
            active_job["current_room_paused_seconds"] = max(
                _safe_int(active_job.get("current_room_paused_seconds"), 0) + pause_delta_seconds,
                0,
            )

        active_job["status"] = "started"
        active_job["paused_at"] = None
        active_job["paused_duration_seconds"] = paused_seconds
        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

    def record_completed_room(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_name: str | None = None,
        actual_duration_minutes: float | None = None,
        completed_at: str | None = None,
        source: str = "event",
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Record one room as completed for the tracked active job."""
        active_job = self._normalize_active_job(
            self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        )
        if active_job.get("status") not in {"started", "paused"}:
            return active_job

        normalized_room_id = _safe_int(room_id, -1)
        if normalized_room_id < 0:
            return active_job

        completed_ids = [
            _safe_int(existing_room_id, -1)
            for existing_room_id in active_job.get("completed_room_ids", [])
            if _safe_int(existing_room_id, -1) >= 0
        ]
        if normalized_room_id not in completed_ids:
            completed_ids.append(normalized_room_id)
        active_job["completed_room_ids"] = completed_ids

        # Upsert: strip any existing entry for this room then append the new one.
        # De-duplication bounds the list to at most one entry per unique room ID,
        # so the safety cap below matches the job's own room count.
        _queue_room_count = len(active_job.get("queue_room_ids") or [])
        _completed_rooms_cap = max(_queue_room_count + 1, 20)

        completed_rooms = [
            dict(entry)
            for entry in active_job.get("completed_rooms", [])
            if _safe_int(entry.get("room_id", -1), -1) != normalized_room_id
        ]
        entry = {
            "room_id": normalized_room_id,
            "slug": None,
            "room_name": room_name,
            "completed_at": completed_at or _iso_now(),
            "source": source,
        }
        if actual_duration_minutes is not None:
            entry["actual_duration_minutes"] = round(float(actual_duration_minutes), 2)
        if confidence is not None:
            entry["confidence"] = round(float(confidence), 4)
        completed_rooms.append(entry)
        active_job["completed_rooms"] = completed_rooms[-_completed_rooms_cap:]

        next_room_id = self._derive_active_job_current_room_id(active_job)
        active_job["current_room_id"] = next_room_id
        active_job["current_room_started_at"] = (completed_at or _iso_now()) if next_room_id is not None else None
        active_job["current_room_paused_seconds"] = 0
        active_job["paused_at"] = None if active_job.get("status") != "paused" else active_job.get("paused_at")

        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        return active_job

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

    def get_upkeep_snapshot(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return replacement, maintenance, and dock upkeep state for one vacuum."""
        capabilities = self.get_vacuum_capabilities(vacuum_entity_id=vacuum_entity_id, refresh=False)
        model_meta = self._get_upkeep_model_meta(vacuum_entity_id=vacuum_entity_id)
        model_code = model_meta.get("code")
        sources = capabilities.get("maintenance_sources", {})
        replacement_items: list[dict[str, Any]] = []
        maintenance_items: list[dict[str, Any]] = []
        attention_count = 0
        highest_priority_status = "good"
        priority_rank = {"unknown": 0, "good": 1, "warning": 2, "replace_soon": 3, "replace_now": 4}

        _maintenance_components = (_get_adapter_config(vacuum_entity_id) or {}).get("maintenance_components", {})
        for component, meta in _maintenance_components.items():
            label = meta.get("label", component.replace("_", " ").title())
            source_entity = sources.get(component)
            replacement_state = self.hass.states.get(source_entity) if source_entity else None
            replacement_reset_entity = self._get_replacement_reset_entity(
                vacuum_entity_id=vacuum_entity_id,
                component=component,
            )
            replacement_status = "unknown"
            replacement_value: float | str | None = None
            replacement_unit = None
            replacement_hours = None
            usage_hours = None
            total_life_hours = None
            remaining_percent = None

            if replacement_state is not None:
                replacement_value = replacement_state.state
                replacement_unit = replacement_state.attributes.get("unit_of_measurement")
                replacement_status = self._replacement_status(state_value=replacement_state.state)
                try:
                    usage_hours = float(replacement_state.attributes.get("usage_hours"))
                except (TypeError, ValueError):
                    usage_hours = None
                try:
                    total_life_hours = float(replacement_state.attributes.get("total_life_hours"))
                except (TypeError, ValueError):
                    total_life_hours = None
                try:
                    remaining_hours = float(replacement_state.state)
                except (TypeError, ValueError):
                    remaining_hours = None
                replacement_hours = remaining_hours
                if total_life_hours and total_life_hours > 0 and remaining_hours is not None:
                    remaining_percent = round(
                        max(min((remaining_hours / total_life_hours) * 100.0, 100.0), 0.0),
                        2,
                    )

            replacement_item = {
                "component": component,
                "label": label,
                "component_label": _display_label(component) or label,
                "kind": "replacement",
                "kind_label": "Replacement",
                "source": "upstream",
                "entity_id": source_entity,
                "remaining_value": replacement_value,
                "remaining_unit": replacement_unit,
                "remaining_hours": replacement_hours,
                "usage_hours": round(usage_hours, 2) if usage_hours is not None else None,
                "total_life_hours": round(total_life_hours, 2) if total_life_hours is not None else None,
                "max_life_hours": round(total_life_hours, 2) if total_life_hours is not None else None,
                "remaining_percent": remaining_percent,
                "status": replacement_status,
                "status_label": _display_label(replacement_status),
                "available": replacement_state is not None,
                "can_reset": replacement_reset_entity is not None,
                "reset_kind": "upstream" if replacement_reset_entity is not None else None,
                "reset_kind_label": "Upstream" if replacement_reset_entity is not None else None,
                "reset_service": "button.press" if replacement_reset_entity is not None else None,
                "reset_service_data": (
                    {"entity_id": replacement_reset_entity}
                    if replacement_reset_entity is not None
                    else None
                ),
                "remaining_summary": (
                    f"{round(remaining_percent)}% remaining"
                    if remaining_percent is not None
                    else (_hours_text(replacement_hours) + " remaining" if replacement_hours is not None else None)
                ),
                "usage_summary": (
                    _hours_text(usage_hours) + " used"
                    if usage_hours is not None
                    else None
                ),
                "guide": self._get_upkeep_item_guide(
                    vacuum_entity_id=vacuum_entity_id,
                    model_code=model_code,
                    component=component,
                    item_kind="replacement",
                ),
            }
            replacement_items.append(replacement_item)

            # Honor a user-saved interval override stored at
            # data["maintenance"][vacuum][component]["interval_hours"]
            # (written by set_maintenance_interval and by the
            # EufyVacuumMaintenanceIntervalNumber entity). Fall back to
            # the adapter-declared default when no override exists or
            # the stored value can't be coerced. Same precedence the
            # sensor entity uses — keeps card + entity + dashboard
            # snapshot all reporting the same value.
            default_interval = float(meta.get("default_interval_hours", 0.0) or 0.0)
            override_raw = (
                self.data.get("maintenance", {})
                .get(vacuum_entity_id, {})
                .get(component, {})
                .get("interval_hours")
            )
            try:
                interval_hours = float(override_raw) if override_raw is not None else default_interval
            except (TypeError, ValueError):
                interval_hours = default_interval
            maintenance = self.get_maintenance_remaining(
                vacuum_entity_id=vacuum_entity_id,
                component=component,
                interval_hours=interval_hours,
            )
            maintenance_status = self._maintenance_status(
                remaining_hours=float(maintenance.get("remaining_hours", 0.0) or 0.0),
                interval_hours=float(maintenance.get("interval_hours", interval_hours) or interval_hours),
            )
            remaining_percent = None
            if interval_hours > 0:
                remaining_percent = round(
                    max(min((float(maintenance.get("remaining_hours", 0.0) or 0.0) / interval_hours) * 100.0, 100.0), 0.0),
                    2,
                )

            maintenance_item = {
                "component": component,
                "label": label,
                "component_label": _display_label(component) or label,
                "kind": "maintenance",
                "kind_label": "Maintenance",
                "source": "integration",
                "entity_id": maintenance.get("source_entity"),
                "remaining_hours": maintenance.get("remaining_hours"),
                "used_since_reset_hours": maintenance.get("used_since_reset_hours"),
                "interval_hours": maintenance.get("interval_hours"),
                # Surface the adapter-declared bounds so the card's maintenance
                # modal can render an interval editor with the right defaults
                # and validation cap. Per maintenance_components.py: default is
                # the manufacturer recommendation; max is the absolute ceiling
                # for a user override (set generously, e.g. 720h for filter).
                "default_interval_hours": float(meta.get("default_interval_hours", 0.0) or 0.0),
                "max_interval_hours": float(meta.get("max_interval_hours", 0.0) or 0.0),
                "current_usage_hours": maintenance.get("current_usage_hours"),
                "reset_at": maintenance.get("reset_at"),
                "remaining_percent": remaining_percent,
                "status": maintenance_status,
                "status_label": _display_label(maintenance_status),
                "available": bool(maintenance.get("source_available")),
                "can_reset": True,
                "reset_kind": "integration",
                "reset_kind_label": "Integration",
                "reset_service": f"{DOMAIN}.reset_maintenance",
                "reset_service_data": {
                    "vacuum_entity_id": vacuum_entity_id,
                    "component": component,
                },
                "remaining_summary": (
                    f"{round(remaining_percent)}% remaining"
                    if remaining_percent is not None
                    else (_hours_text(maintenance.get("remaining_hours")) + " left" if maintenance.get("remaining_hours") is not None else None)
                ),
                "usage_summary": (
                    _hours_text(maintenance.get("used_since_reset_hours")) + " used since reset"
                    if maintenance.get("used_since_reset_hours") is not None
                    else None
                ),
                "guide": self._get_upkeep_item_guide(
                    vacuum_entity_id=vacuum_entity_id,
                    model_code=model_code,
                    component=component,
                    item_kind="maintenance",
                ),
            }
            maintenance_items.append(maintenance_item)

            for status_value in (replacement_status, maintenance_status):
                if status_value in {"warning", "replace_soon", "replace_now"}:
                    attention_count += 1
                if priority_rank.get(status_value, 0) > priority_rank.get(highest_priority_status, 0):
                    highest_priority_status = status_value

        dock_entity = capabilities.get("entities", {}).get("dock_status")
        station_water_entity = capabilities.get("entities", {}).get("water_level") or capabilities.get("entities", {}).get("station_water")
        dock_state = self.hass.states.get(dock_entity) if dock_entity else None
        station_water_state = self.hass.states.get(station_water_entity) if station_water_entity else None
        dock_events = dict(self.get_dock_events(vacuum_entity_id=vacuum_entity_id))
        dock_counts = {
            "mop_wash_count": _safe_int(dock_events.get("mop_wash_count"), 0),
            "dust_empty_count": _safe_int(dock_events.get("dust_empty_count"), 0),
            "dry_start_count": _safe_int(dock_events.get("dry_start_count"), 0),
        }

        attention_summary = (
            f"{attention_count} upkeep item(s) need attention."
            if attention_count > 0
            else "No upkeep items need attention."
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "dock_status": dock_state.state if dock_state is not None else capabilities.get("sources", {}).get("dock_status_value"),
            "dock_status_label": _display_label(dock_state.state if dock_state is not None else capabilities.get("sources", {}).get("dock_status_value")),
            "dock_status_entity": dock_entity,
            "station_water": station_water_state.state if station_water_state is not None else None,
            "station_water_label": (
                f"{round(_safe_float(station_water_state.state, 0.0))}%"
                if station_water_state is not None and station_water_state.state not in {None, "", "unknown", "unavailable"}
                else _display_label(station_water_state.state if station_water_state is not None else None)
            ),
            "station_water_entity": station_water_entity,
            "dock_events": {
                "last_mop_wash": dock_events.get("last_mop_wash"),
                "last_dust_empty": dock_events.get("last_dust_empty"),
                "last_dry_start": dock_events.get("last_dry_start"),
                "last_dry_duration": dock_events.get("last_dry_duration"),
                **dock_counts,
            },
            "model_meta": model_meta,
            "replacement_items": replacement_items,
            "maintenance_items": maintenance_items,
            "attention_count": attention_count,
            "highest_priority_status": highest_priority_status,
            "highest_priority_status_label": _display_label(highest_priority_status),
            "attention_summary": attention_summary,
            "updated_at": _iso_now(),
        }

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

    def mark_active_job_finalized(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        finalize_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Mark one tracked job finalized in runtime storage."""
        self.data.setdefault("active_jobs", {})
        self.data["active_jobs"].setdefault(vacuum_entity_id, {})
        active_job = self.data["active_jobs"][vacuum_entity_id].get(str(map_id), {})
        if not isinstance(active_job, dict):
            active_job = {}

        active_job["status"] = "completed"
        active_job["finalized"] = True
        active_job["paused_at"] = None
        active_job["has_observed_active_lifecycle"] = False
        active_job["finalized_at"] = (
            finalize_result.get("completed_job", {}).get("finalized_at")
            if isinstance(finalize_result, dict)
            else None
        )
        if isinstance(finalize_result, dict):
            active_job["finalize_summary"] = {
                "job_id": finalize_result.get("job_id"),
                "job_path": finalize_result.get("job_path"),
                "used_for_learning": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("used_for_learning")
                ),
                "sanity_passed": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("sanity_passed")
                ),
                "sanity_flags": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("sanity_flags")
                ),
                "learning_blockers": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("learning_blockers")
                ),
                "status": (
                    finalize_result.get("completed_job", {})
                    .get("outcome", {})
                    .get("status")
                ),
            }

        self.data["active_jobs"][vacuum_entity_id][str(map_id)] = active_job
        runtime = self.ensure_runtime(vacuum_entity_id)
        runtime.active_job_room_ids = []
        return active_job

    async def async_pause_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Pause the vacuum and mark the tracked job paused."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") != "started":
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "paused": False,
                "reason": "no_started_job",
                "active_job": active_job,
            }

        await self.hass.services.async_call(
            "vacuum",
            "pause",
            {"entity_id": vacuum_entity_id},
            blocking=True,
        )
        paused_job = self.pause_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "paused": True,
            "reason": "paused",
            "active_job": paused_job,
        }

    async def async_resume_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Resume the vacuum and the tracked paused job."""
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") != "paused":
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "resumed": False,
                "reason": "no_paused_job",
                "active_job": active_job,
            }

        await self.hass.services.async_call(
            "vacuum",
            "start",
            {"entity_id": vacuum_entity_id},
            blocking=True,
        )
        resumed_job = self.resume_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "resumed": True,
            "reason": "resumed",
            "active_job": resumed_job,
        }

    # How long to wait for the device to reach a terminal state after return_to_base.
    _CANCEL_CONFIRM_TIMEOUT_S: int = 30
    _CANCEL_POLL_INTERVAL_S: float = 2.0

    async def async_cancel_active_job(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        forced_lifecycle_state: str | None = None,
        forced_lifecycle_message: str | None = None,
        cancel_reason: str | None = None,
    ) -> dict[str, Any]:
        """Cancel one tracked job by returning the vacuum to base and finalizing.

        After ``return_to_base``, polls for a terminal device state (docked /
        idle / task_status Completed) before writing the learning finalization
        record.  This prevents recording a "cancelled" outcome against a
        still-running session.  If the device does not confirm within
        ``_CANCEL_CONFIRM_TIMEOUT_S`` seconds, logs a warning and finalizes
        anyway so the active-job snapshot is never stuck in "started".
        """
        active_job = self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if active_job.get("status") not in {"started", "paused"}:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "cancelled": False,
                "reason": "no_active_job",
                "active_job": active_job,
            }

        await self.hass.services.async_call(
            "vacuum",
            "return_to_base",
            {"entity_id": vacuum_entity_id},
            blocking=True,
        )

        task_status_entity_id = (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get("task_status")
        deadline = self.hass.loop.time() + self._CANCEL_CONFIRM_TIMEOUT_S
        confirmed = False
        last_vac_state: str | None = None
        last_task_status: str | None = None

        while self.hass.loop.time() < deadline:
            await asyncio.sleep(self._CANCEL_POLL_INTERVAL_S)
            vac_state_obj = self.hass.states.get(vacuum_entity_id)
            last_vac_state = vac_state_obj.state if vac_state_obj else None
            task_state_obj = self.hass.states.get(task_status_entity_id)
            last_task_status = task_state_obj.state if task_state_obj else None
            task_lower = str(last_task_status or "").strip().lower()

            if last_vac_state in {"docked", "idle"} or task_lower in {"completed", "complete"}:
                confirmed = True
                break

        if not confirmed:
            _LOGGER.warning(
                "async_cancel_active_job: %s did not reach a terminal state within %ds "
                "— finalizing anyway (task_status=%s, vacuum_state=%s)",
                vacuum_entity_id,
                self._CANCEL_CONFIRM_TIMEOUT_S,
                last_task_status,
                last_vac_state,
            )

        finalize_result = await self.finalize_learning_for_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            rebuild_stats=True,
            rebuild_csv=False,
            forced_outcome_status="cancelled",
            forced_lifecycle_state=forced_lifecycle_state or "job_cancelled",
            forced_lifecycle_message=(
                forced_lifecycle_message or "Job was cancelled by return_to_base."
            ),
        )
        self.mark_active_job_finalized(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            finalize_result=finalize_result,
        )
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "cancelled": True,
            "confirmed": confirmed,
            "reason": str(cancel_reason or "cancelled"),
            "finalize_result": finalize_result,
        }

    def get_paused_job_timeout_report(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        now: str | None = None,
    ) -> dict[str, Any] | None:
        """Return a timeout report if a paused job has exceeded its limit."""
        active_job = self._normalize_active_job(
            self.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        )
        if active_job.get("status") != "paused":
            return None

        pause_timeout_minutes = _normalize_pause_timeout_minutes(
            active_job.get("pause_timeout_minutes")
        )
        if pause_timeout_minutes <= 0:
            return None

        paused_at = str(active_job.get("paused_at", "")).strip()
        paused_dt = self._parse_job_timestamp(paused_at)
        now_dt = self._parse_job_timestamp(now or _iso_now())
        if paused_dt is None or now_dt is None:
            return None

        paused_elapsed_seconds = max(int((now_dt - paused_dt).total_seconds()), 0)
        pause_timeout_seconds = pause_timeout_minutes * 60
        if paused_elapsed_seconds < pause_timeout_seconds:
            return None

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "job_id": active_job.get("job_id"),
            "pause_timeout_minutes": pause_timeout_minutes,
            "paused_at": paused_at,
            "paused_elapsed_seconds": paused_elapsed_seconds,
            "forced_lifecycle_state": "pause_timeout_cancelled",
            "forced_lifecycle_message": (
                f"Paused for over {pause_timeout_minutes} minutes. Job canceled."
            ),
            "cancel_reason": "pause_timeout",
        }

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

    def get_maintenance_state(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return current maintenance reset snapshots for one vacuum."""
        self.data.setdefault("maintenance", {})
        return self.data["maintenance"].setdefault(vacuum_entity_id, {})

    def reset_maintenance(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
    ) -> dict[str, Any]:
        """Snapshot current usage_hours for a component as the new reset point."""
        capabilities = self.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        source_entity = sources.get(component)

        if source_entity is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "no_source_entity",
            }

        state = self.hass.states.get(source_entity)
        if state is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "source_unavailable",
                "source_entity": source_entity,
            }

        try:
            usage_hours = float(state.attributes.get("usage_hours", 0))
        except (TypeError, ValueError):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "invalid_usage_hours",
                "source_entity": source_entity,
            }

        maintenance = self.get_maintenance_state(vacuum_entity_id=vacuum_entity_id)
        maintenance[component] = {
            "reset_at_usage_hours": usage_hours,
            "reset_at": _iso_now(),
        }

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "component": component,
            "reset": True,
            "reset_at_usage_hours": usage_hours,
            "reset_at": maintenance[component]["reset_at"],
            "source_entity": source_entity,
        }

    # ------------------------------------------------------------------
    # Onboarding
    # ------------------------------------------------------------------

    def _get_onboarding_data(self) -> dict:
        """Return root onboarding dict."""
        self.data.setdefault("onboarding", {})
        return self.data["onboarding"]

    def _get_map_onboarding(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict:
        """Return onboarding state for one vacuum/map, creating defaults if absent."""
        ob = self._get_onboarding_data()
        ob.setdefault(vacuum_entity_id, {})
        ob[vacuum_entity_id].setdefault(
            str(map_id),
            {
                "rooms_discovered": False,
                "floor_types_confirmed": {},
                "room_count_at_last_check": 0,
                "discovery_notified": False,
                "rebuild_notified": False,
            },
        )
        return ob[vacuum_entity_id][str(map_id)]

    def get_onboarding_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return full onboarding status for one vacuum/map."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        map_bucket = self.data.get("maps", {}).get(
            vacuum_entity_id, {}
        ).get(str(map_id), {})
        rooms = map_bucket.get("rooms", {})

        confirmed = map_ob.get("floor_types_confirmed", {})
        enabled_rooms_needing_floor_type: list[str] = []

        for room_id_key, room_data in rooms.items():
            if not room_data.get("enabled", False):
                continue
            if not confirmed.get(str(room_id_key), False):
                enabled_rooms_needing_floor_type.append(str(room_id_key))

        rooms_discovered = bool(map_ob.get("rooms_discovered", False)) and len(rooms) > 0
        floor_types_complete = len(enabled_rooms_needing_floor_type) == 0
        onboarding_complete = rooms_discovered and floor_types_complete

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "rooms_discovered": rooms_discovered,
            "room_count": len(rooms),
            "floor_types_complete": floor_types_complete,
            "onboarding_complete": onboarding_complete,
            "enabled_rooms_needing_floor_type": enabled_rooms_needing_floor_type,
            "status": (
                "complete" if onboarding_complete
                else "floor_type_needed" if rooms_discovered
                else "rooms_needed"
            ),
        }

    def mark_rooms_discovered(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> None:
        """Mark rooms as discovered for one map."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        map_ob["rooms_discovered"] = True

        rooms = (
            self.data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
            .get("rooms", {})
        )
        map_ob["room_count_at_last_check"] = len(rooms)

    def confirm_floor_type(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        room_id: str,
    ) -> None:
        """Mark a room's floor type as explicitly confirmed by the user."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        map_ob.setdefault("floor_types_confirmed", {})
        map_ob["floor_types_confirmed"][str(room_id)] = True

    def check_for_new_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> bool:
        """Return True if room count has grown since last check."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )

        vacuum_state = self.hass.states.get(vacuum_entity_id)
        if vacuum_state is None:
            return False

        segments = vacuum_state.attributes.get("segments")
        if not isinstance(segments, list):
            return False

        current_count = len(segments)
        last_count = int(map_ob.get("room_count_at_last_check", 0))

        return current_count > last_count

    def get_rooms_onboarding_summary(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return onboarding status across all known maps for one vacuum."""
        maps = self.data.get("maps", {}).get(vacuum_entity_id, {})
        summaries = []
        any_incomplete = False

        for map_id in maps.keys():
            state = self.get_onboarding_state(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
            )
            summaries.append(state)
            if not state["onboarding_complete"]:
                any_incomplete = True

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "all_complete": not any_incomplete,
            "maps": summaries,
        }

    def reset_onboarding(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Clear onboarding state for one map, forcing re-check on next evaluation."""
        ob = self._get_onboarding_data()
        ob.setdefault(vacuum_entity_id, {})
        ob[vacuum_entity_id][str(map_id)] = {
            "rooms_discovered": False,
            "floor_types_confirmed": {},
            "room_count_at_last_check": 0,
            "discovery_notified": False,
            "rebuild_notified": False,
        }
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "reset": True,
        }

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
    # Dock events
    # ------------------------------------------------------------------

    # Noisy states (e.g. "Washing") flip 1-2 times within ~30s per actual
    # cycle. Debounce per-event-type counters with this window so each real
    # dock action is counted once.
    _DOCK_EVENT_DEBOUNCE_SECONDS: dict[str, int] = {
        "last_mop_wash": 60,
    }

    def record_dock_event(
        self,
        *,
        vacuum_entity_id: str,
        event_type: str,
        dry_duration: str | None = None,
    ) -> None:
        """Record a dock event timestamp into storage."""
        self.data.setdefault("dock_events", {})
        vacuum_events = self.data["dock_events"].setdefault(vacuum_entity_id, {})
        now = _iso_now()
        vacuum_events[event_type] = now

        counter_map = {
            "last_mop_wash": "mop_wash_count",
            "last_dust_empty": "dust_empty_count",
            "last_dry_start": "dry_start_count",
        }
        counter_key = counter_map.get(event_type)
        if counter_key:
            debounce = self._DOCK_EVENT_DEBOUNCE_SECONDS.get(event_type, 0)
            should_count = True
            if debounce > 0:
                last_counted = vacuum_events.get(f"{event_type}_last_counted_at")
                if last_counted:
                    try:
                        last_dt = datetime.fromisoformat(last_counted.replace("Z", "+00:00"))
                        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
                        if (now_dt - last_dt).total_seconds() < debounce:
                            should_count = False
                    except Exception:
                        pass
            if should_count:
                vacuum_events[counter_key] = _safe_int(vacuum_events.get(counter_key), 0) + 1
                vacuum_events[f"{event_type}_last_counted_at"] = now

        if event_type == "last_dry_start" and dry_duration is not None:
            vacuum_events["last_dry_duration"] = dry_duration

    def set_dock_event_count(
        self,
        *,
        vacuum_entity_id: str,
        event_type: str,
        count: int,
    ) -> dict[str, Any]:
        """Overwrite a dock event counter to a specific value."""
        counter_map = {
            "last_mop_wash": "mop_wash_count",
            "last_dust_empty": "dust_empty_count",
            "last_dry_start": "dry_start_count",
        }
        counter_key = counter_map.get(event_type)
        if not counter_key:
            return {"updated": False, "error": f"Unknown event_type: {event_type}"}
        self.data.setdefault("dock_events", {})
        vacuum_events = self.data["dock_events"].setdefault(vacuum_entity_id, {})
        old_count = _safe_int(vacuum_events.get(counter_key), 0)
        vacuum_events[counter_key] = max(int(count), 0)
        return {"updated": True, "event_type": event_type, "old_count": old_count, "new_count": vacuum_events[counter_key]}

    def get_dock_events(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, str | None]:
        """Return stored dock event timestamps for one vacuum."""
        self.data.setdefault("dock_events", {})
        return self.data["dock_events"].get(vacuum_entity_id, {})

    def get_maintenance_remaining(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
        interval_hours: float,
    ) -> dict[str, Any]:
        """Return remaining maintenance hours for one component."""
        capabilities = self.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        source_entity = sources.get(component)

        current_usage: float = 0.0
        source_available = False

        if source_entity:
            state = self.hass.states.get(source_entity)
            if state is not None:
                try:
                    current_usage = float(state.attributes.get("usage_hours", 0))
                    source_available = True
                except (TypeError, ValueError):
                    pass

        maintenance = self.get_maintenance_state(vacuum_entity_id=vacuum_entity_id)
        component_data = maintenance.get(component, {})
        reset_snapshot = float(component_data.get("reset_at_usage_hours", 0.0))
        reset_at = component_data.get("reset_at")

        used_since_reset = max(current_usage - reset_snapshot, 0.0)
        remaining = max(interval_hours - used_since_reset, 0.0)

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "component": component,
            "remaining_hours": round(remaining, 2),
            "used_since_reset_hours": round(used_since_reset, 2),
            "interval_hours": interval_hours,
            "current_usage_hours": round(current_usage, 2),
            "reset_at_usage_hours": reset_snapshot,
            "reset_at": reset_at,
            "source_entity": source_entity,
            "source_available": source_available,
        }

    # ------------------------------------------------------------------
    # Job start / run-profile start
    # ------------------------------------------------------------------

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

        # Read dispatch config so the service call honors brand-specific
        # service_domain/service_name/command. Eufy-shape defaults preserve
        # legacy behavior when no adapter is registered.
        _dispatch_cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        _service_domain = _dispatch_cfg.get("service_domain", "vacuum")
        _service_name = _dispatch_cfg.get("service_name", "send_command")
        _command = _dispatch_cfg.get("command", "room_clean")

        # Two envelope shapes — switched by whether the adapter declared
        # a `command` field. Wrapped form is the HA send_command pattern
        # (Eufy, Roborock); direct form is the merge-payload-into-data
        # pattern used by integrations like dreame_vacuum that expose
        # their own vacuum_clean_segment service.
        if _command:
            _service_data = {
                "entity_id": vacuum_entity_id,
                "command": _command,
                "params": payload,
            }
        else:
            _service_data = {"entity_id": vacuum_entity_id, **payload}

        await self.hass.services.async_call(
            _service_domain,
            _service_name,
            _service_data,
            blocking=True,
        )

        active_job = build_active_job_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            queue_state=queue_state,
            payload_state=payload_state,
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
