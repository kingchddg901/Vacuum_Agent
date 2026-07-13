"""Run planning and water estimation subsystem.

Owns:
- Water model helpers (_normalize_water_level_key, _water_rate_ml_per_minute,
  _get_station_clean_water_percent, _get_water_model_config,
  _derive_wash_frequency_config)
- Water usage estimation (estimate_job_water_usage)
- Effective start plan construction (_build_effective_start_plan and helpers)
- Room rule status snapshot (_update_room_rule_status_snapshot)
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..entity_helpers import get_floor_type_label
from ..queue.queue_engine import build_queue_from_managed_rooms
from ..queue.dispatch_engines import get_dispatch_engine
from ..timestamp_utils import utc_now_iso

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level pure helpers (duplicated from core/manager.py where also used)
# ---------------------------------------------------------------------------

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


def _room_surface_labels(
    *,
    floor_type: Any = None,
) -> dict[str, Any]:
    """Return reusable room floor display labels."""
    floor_value = str(floor_type or "").strip().lower() or None
    return {
        "floor_type_label": get_floor_type_label(floor_value) if floor_value else None,
    }


# ---------------------------------------------------------------------------
# RunPlanManager
# ---------------------------------------------------------------------------

class RunPlanManager:
    """Owns water estimation and effective start-plan construction."""

    def __init__(self, manager: EufyVacuumManager) -> None:
        """Initialise with a back-reference to the owning manager."""
        self._manager = manager

    # ------------------------------------------------------------------
    # Water model helpers
    # ------------------------------------------------------------------

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
        rate_override: dict[str, Any] | None = None,
    ) -> float:
        """Return first-pass floor application water rate (ml/min) by water level.

        ``rate_override`` (adapter ``water_model_configs[...]["water_rates"]``, keyed by
        canonical level) carries the brand's measured flow rates — Eufy declares the X10
        table in its adapter (see adapters/eufy/water_config.py). Core keeps NO brand-measured
        table: with no override it applies ``off`` = 0 (no water, a universal) and a single
        generic ~4 ml/min to other levels, rather than imposing one brand's numbers on another."""
        normalized = self._normalize_water_level_key(water_level, aliases=aliases)
        table = rate_override if (isinstance(rate_override, dict) and rate_override) else {"off": 0.0}
        return _safe_float(table.get(normalized, 4.0), 4.0)

    def _get_station_clean_water_percent(
        self,
        *,
        vacuum_entity_id: str,
        capabilities: dict[str, Any] | None = None,
    ) -> float | None:
        """Return current dock clean-water percent when exposed as a numeric state."""
        caps = capabilities or self._manager.get_vacuum_capabilities(vacuum_entity_id=vacuum_entity_id, refresh=False)
        station_water_entity = caps.get("entities", {}).get("water_level") or caps.get("entities", {}).get("station_water")
        state = self._manager.hass.states.get(station_water_entity) if station_water_entity else None
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
        model_meta = self._manager._get_upkeep_model_meta(vacuum_entity_id=vacuum_entity_id)
        model_code = model_meta.get("code")
        config = dict(_water_model_configs.get(model_code or "", {}))
        # Capture availability before injecting meta keys — otherwise the
        # model_code/model_name entries below make ``config`` truthy
        # unconditionally and the model_unsupported guard becomes dead code.
        available = bool(config)
        config["model_code"] = model_code
        config["model_name"] = model_meta.get("name")
        config["available"] = available
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
        mode_state = self._manager.hass.states.get(mode_entity_id) if mode_entity_id else None
        interval_state = self._manager.hass.states.get(interval_entity_id) if interval_entity_id else None

        _wf_vocab = (_get_adapter_config(vacuum_entity_id) or {}).get("vocabulary", {})
        _wash_freq_aliases: dict[str, str] = _wf_vocab.get("wash_frequency_mode_aliases") or {}
        raw_mode = str(mode_state.state if mode_state is not None else "").strip().lower().replace("-", " ").replace("_", " ")
        compact_mode = " ".join(raw_mode.split())
        mode_key = _wash_freq_aliases.get(compact_mode, "unknown")

        # Wash-cadence interval bounds (minutes) are BRAND-owned via ``wash_frequency_bounds``
        # — the Eufy X10 firmware range (15-25, default 20) lives in the Eufy adapter. Core
        # falls back to a generic, effectively non-clamping range so an undeclared brand is
        # not forced into another brand's firmware limits.
        _wf_bounds = (_get_adapter_config(vacuum_entity_id) or {}).get("wash_frequency_bounds", {})
        _wf_default = _safe_float(_wf_bounds.get("default"), 20.0)
        _wf_min = _safe_float(_wf_bounds.get("min"), 1.0)
        _wf_max = _safe_float(_wf_bounds.get("max"), 1440.0)
        interval_minutes = _safe_float(interval_state.state if interval_state is not None else None, _wf_default)
        if interval_minutes <= 0:
            interval_minutes = _wf_default
        interval_minutes = max(_wf_min, min(_wf_max, interval_minutes))

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
        capabilities = self._manager.get_vacuum_capabilities(vacuum_entity_id=vacuum_entity_id, refresh=False)
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
                    room_robot_water_ml = estimated_minutes * self._water_rate_ml_per_minute(
                        water_level, aliases=_water_level_aliases, rate_override=model_config.get("water_rates")
                    )
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
            # Low-margin warning threshold defaults to 300 ml (Eufy dock tuning);
            # adapters override via water_model_configs[...]["low_clean_water_margin_ml"].
            _low_margin_ml = _safe_float(model_config.get("low_clean_water_margin_ml"), 300.0)
            low_clean_water_margin = (
                not not_enough_clean_water
                and estimated_clean_tank_remaining_ml is not None
                and estimated_clean_tank_remaining_ml <= _low_margin_ml
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
    # Run planning helpers
    # ------------------------------------------------------------------

    def _room_estimate_minutes_map(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[int, float]:
        """Return estimated minutes per room for the current map."""
        learning = self._manager._get_learning_manager()
        if learning is None:
            return {}
        try:
            estimate = learning.get_room_learning_estimates(
                self._manager,
                vacuum_entity_id,
                str(map_id),
                current_battery=float(self._manager._get_battery_level(vacuum_entity_id)),
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

    def _mop_carpet_warning(
        self,
        *,
        vacuum_entity_id: str,
        effective_rooms: dict[str, Any],
        included_room_ids: list[int],
    ) -> str | None:
        """Return a caution string when a tank-driven mop will run over carpet.

        Tank-based mops with no auto-lift (Roborock S6) wet-drag their pad over
        every surface they cross, so an attached water tank + an included carpet
        room means the run WILL mop that carpet whatever the room's vacuum-only
        software setting says. Returns None for brands that declare no tank sensor
        (``entities.mop_active``), when the tank isn't attached, or when no
        included room is carpet.
        """
        mop_active_entity = (
            (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {}) or {}
        ).get("mop_active")
        if not mop_active_entity:
            return None
        tank_state = self._manager.hass.states.get(mop_active_entity)
        if tank_state is None or str(tank_state.state).strip().lower() != "on":
            return None

        carpet_names: list[str] = []
        for room_id in included_room_ids:
            room = effective_rooms.get(str(room_id))
            if not isinstance(room, dict):
                continue
            if str(room.get("floor_type", "")).strip().lower().startswith("carpet"):
                carpet_names.append(str(room.get("name") or f"Room {room_id}"))
        if not carpet_names:
            return None

        rooms_label = ", ".join(carpet_names)
        plural = "rooms" if len(carpet_names) > 1 else "room"
        return (
            f"The water tank is attached, so the mop will wet the carpet "
            f"{plural}: {rooms_label}. Remove the tank to vacuum only."
        )

    def _order_advisory(
        self,
        *,
        vacuum_entity_id: str,
        included_room_ids: list[int],
    ) -> str | None:
        """Return a note when this brand doesn't honor the card's room order.

        Some brands path-optimize and ignore the dispatched order (Roborock
        ``app_segment_clean``) unless an order is saved in the vacuum's own app —
        so the card's queue order is advisory. Surfaced at run start (non-blocking)
        for those brands when 2+ rooms will run. Returns None for brands that
        honor order (``capabilities.honors_clean_order`` defaults True — Eufy) or
        a single-room run (order is moot).
        """
        honors = (
            (_get_adapter_config(vacuum_entity_id) or {})
            .get("capabilities", {})
            .get("honors_clean_order", True)
        )
        if honors or len(included_room_ids) < 2:
            return None
        return (
            "Cleaning order shown here is advisory: this vacuum cleans rooms in "
            "the order saved in its own app (set a cleaning Sequence there to "
            "enforce it) or optimizes the path itself."
        )

    def _update_room_rule_status_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        managed_rooms: dict[str, Any],
        selected_room_ids: list[int],
        included_room_ids: list[int],
        blocked_rooms: list[dict[str, Any]],
        modified_rooms: list[dict[str, Any]],
        preflight: dict[str, Any],
    ) -> None:
        """Persist per-room rule status snapshot — delegates to manager."""
        self._manager._update_room_rule_status_snapshot(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            managed_rooms=managed_rooms,
            selected_room_ids=selected_room_ids,
            included_room_ids=included_room_ids,
            blocked_rooms=blocked_rooms,
            modified_rooms=modified_rooms,
            preflight=preflight,
        )

    def _build_dispatch_phases(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        managed_rooms: dict[str, Any],
        queue_room_ids: list[int],
        strict_order: bool = False,
    ) -> list[dict[str, Any]]:
        """Resolve the brand's dispatch engine and return its phase list.

        For atomic engines (every adapter today) this is a single phase whose
        ``[0]`` element is byte-identical to ``build_room_clean_payload`` — so
        ``phases[0]`` is a drop-in for the old ``payload_state``.

        ``strict_order`` (opt-in, only meaningful for path-optimizing brands that
        ignore the dispatched order) asks the engine for one phase PER ROOM so the
        sequenced job model cleans them strictly in queue order. Atomic engines
        ignore it. Gated on ``capabilities.honors_clean_order`` being False so it
        never alters an order-honoring brand (Eufy), even if requested.
        """
        dispatch_cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        honors_order = (
            (_get_adapter_config(vacuum_entity_id) or {})
            .get("capabilities", {})
            .get("honors_clean_order", True)
        )
        effective_strict = bool(strict_order) and not honors_order
        engine = get_dispatch_engine(dispatch_cfg.get("template"))
        return engine.build_phases(
            strict_order=effective_strict,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=managed_rooms,
            queue_room_ids=queue_room_ids,
            stored_profiles=self._manager.data.get("profiles", {}).get("room_profiles", {}),
            capabilities=self._manager.get_vacuum_capabilities(
                vacuum_entity_id=vacuum_entity_id,
                refresh=False,
            ),
            dispatch=dispatch_cfg,
        )

    def _build_steps_phases(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        effective_rooms: dict[str, Any],
        included_room_ids: set,
        run_steps: list[dict[str, Any]],
        strict_order: bool = False,
    ) -> list[dict[str, Any]]:
        """Materialize a run profile's ordered steps into a phase list.

        Each room_group step -> its brand dispatch phase(s), scoped to the group's
        INCLUDED (enabled + not-blocked) room ids; each charge_wait step -> a
        charge_wait phase. Leading/trailing/duplicate charge phases (nothing to
        bracket) are dropped so phase 0 is always a real clean the initial dispatch
        can send. If no charge phase survives, falls back to one atomic clean.
        """
        phases: list[dict[str, Any]] = []
        for step in run_steps:
            if not isinstance(step, dict):
                continue
            if step.get("type") == "room_group":
                # Coerce each room_id defensively (safe-int, drop non-positive) so a
                # malformed value never reaches int() and crashes the dispatch — the
                # same discipline build_room_clean_payload uses. Carry the parsed id
                # alongside the raw entry so the membership test, queue ids, and the
                # group_managed key all reuse ONE validated int.
                group_rooms = [
                    (rid, r)
                    for r in step.get("rooms", [])
                    if isinstance(r, dict)
                    for rid in (_safe_int(r.get("room_id"), -1),)
                    if rid > 0 and rid in included_room_ids
                ]
                group_ids = [rid for rid, _ in group_rooms]
                if not group_ids:
                    continue  # whole group blocked / not enabled -> skip
                # Per-group settings: overlay each group room's OWN settings over the
                # global effective-room view, so the SAME room can run a different
                # mode/fan in different phases (e.g. vacuum this group, mop the next).
                # The group's fields win; queue_room_ids stays authoritative for order.
                group_managed = dict(effective_rooms)
                for rid, r in group_rooms:
                    key = str(rid)
                    merged = dict(effective_rooms.get(key, {}))
                    for field, value in r.items():
                        if field != "room_id":
                            merged[field] = value
                    group_managed[key] = merged
                phases.extend(self._build_dispatch_phases(
                    vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
                    managed_rooms=group_managed, queue_room_ids=group_ids,
                    strict_order=strict_order,
                ))
            elif step.get("type") == "charge_wait":
                phases.append({
                    "phase_type": "charge_wait",
                    "target_battery_percent": int(step.get("target_battery_percent", 100)),
                    "resolved_rooms": [], "queue_room_ids": [], "queue_rooms": [],
                    "payload": {}, "room_count": 0,
                })
            elif step.get("type") == "wait":
                phases.append({
                    "phase_type": "wait",
                    "wait_minutes": int(step.get("wait_minutes", 5)),
                    "resolved_rooms": [], "queue_room_ids": [], "queue_rooms": [],
                    "payload": {}, "room_count": 0,
                })
            elif step.get("type") == "zone":
                # A zone is a CLEAN action (not a pause): resolve its saved-zone ids to
                # dispatch rects now and carry them on the phase. Skipped if nothing
                # resolves (like an empty room_group). Brand count/size caps ride
                # dispatch_zone_clean at dispatch time.
                zone_ids = step.get("zone_ids") or []
                rects = self._manager._resolve_saved_zone_rects(
                    vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
                    zone_ids=list(zone_ids),
                )
                if not rects:
                    continue
                phases.append({
                    "phase_type": "zone",
                    "zone_ids": [str(z) for z in zone_ids],
                    "zones": rects,
                    "resolved_rooms": [], "queue_room_ids": [], "queue_rooms": [],
                    "payload": {}, "room_count": 0,
                })
        # charge_wait + wait are "break" phases (dock + hold). A break with no clean to
        # bracket is pointless -> drop leading/trailing breaks; collapse consecutive SAME-type
        # breaks (two charges -> last target; two waits -> last duration); mixed breaks kept.
        _BREAKS = ("charge_wait", "wait")
        while phases and phases[0].get("phase_type") in _BREAKS:
            phases.pop(0)
        while phases and phases[-1].get("phase_type") in _BREAKS:
            phases.pop()
        collapsed: list[dict[str, Any]] = []
        for p in phases:
            pt = p.get("phase_type")
            if pt in _BREAKS and collapsed and collapsed[-1].get("phase_type") == pt:
                collapsed[-1] = p  # consecutive same-type breaks -> keep the last
            else:
                collapsed.append(p)
        # A zone is a real clean phase, so a rooms+zone run (no charge/wait) must STAY
        # multi-phase — only collapse to one atomic clean when there is nothing but
        # room_group dispatch phases (no breaks AND no zones).
        if not any(
            p.get("phase_type") in _BREAKS or p.get("phase_type") == "zone"
            for p in collapsed
        ):
            all_ids = [rid for p in collapsed for rid in p.get("queue_room_ids", [])]
            return self._build_dispatch_phases(
                vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
                managed_rooms=effective_rooms,
                queue_room_ids=all_ids or sorted(included_room_ids),
                strict_order=strict_order,
            )
        return collapsed

    def _build_effective_start_plan(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        strict_order: bool = False,
        consume_pending_steps: bool = False,
    ) -> dict[str, Any]:
        """Return the effective queue, payload, and preflight plan for a job start.

        This is the authoritative rule evaluation point for job start.  Blocker
        and modifier rules are evaluated here against live HA entity states
        immediately before the user confirms or the job fires.  Rules are not
        evaluated earlier because their conditions can change at any moment.

        The only other rule evaluation site is ``get_runtime_path_block_report``,
        which re-evaluates blocker rules mid-job as entity states change.
        """
        managed_rooms = self._manager._normalized_managed_rooms_with_automation(
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

        validation = self._manager._validate_room_access_graph(managed_rooms=managed_rooms)
        grants_map, requires_map = self._manager._build_room_access_views(managed_rooms=managed_rooms)

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

        graph_state = self._manager._access_graph_state(
            managed_rooms=managed_rooms, validation=validation
        )
        any_rules = self._manager._any_rooms_have_rules(managed_rooms=managed_rooms)

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
                "payload_state": self._build_dispatch_phases(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    managed_rooms=managed_rooms,
                    queue_room_ids=selected_room_ids,
                )[0],
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
                "payload_state": self._build_dispatch_phases(
                    vacuum_entity_id=vacuum_entity_id,
                    map_id=str(map_id),
                    managed_rooms=managed_rooms,
                    queue_room_ids=selected_room_ids,
                )[0],
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
                if not self._manager._room_rule_matches(rule):
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
                if not self._manager._room_rule_matches(rule):
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
            updated_room = self._manager.protected_room_config({**room_data, **updates})
            matched_profile = self._manager._match_profile_from_fields(updated_room)
            updated_room["profile_name"] = matched_profile if matched_profile else "custom"
            effective_rooms[room_key] = updated_room
            if modifier:
                modified_rooms.append(modifier)

        capabilities = self._manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        queue_state = build_queue_from_managed_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            managed_rooms=effective_rooms,
        )
        # A run profile with a charge step stashes its ordered steps (start_run_profile);
        # materialize a multi-phase [clean, charge_wait, clean] job. Absent (normal room
        # dispatch) -> the single atomic phase as before. We only POP (consume) the stash
        # on the REAL dispatch; preflight callers (get_start_status, path-block report) PEEK,
        # so a preflight can't eat the stash before the dispatch builds its plan.
        _pending_map = (
            self._manager.data.get("_pending_run_steps", {})
            .get(vacuum_entity_id, {})
        )
        _run_steps = (
            _pending_map.pop(str(map_id), None)
            if consume_pending_steps
            else _pending_map.get(str(map_id))
        )
        # No applied-profile stash -> fall back to the LIVE QUEUE's own breaks (the
        # ad-hoc stepped queue). get_queue_steps is derived, not consumed, so a
        # preflight PEEK and the real dispatch agree. An explicit start_run_profile
        # stash takes precedence; the queue breaks only drive a plain Start.
        if not _run_steps:
            _queue_steps = self._manager.get_queue_steps(
                vacuum_entity_id=vacuum_entity_id, map_id=str(map_id)
            ).get("steps")
            if _queue_steps and any(
                isinstance(s, dict) and s.get("type") in ("charge_wait", "wait")
                for s in _queue_steps
            ):
                _run_steps = _queue_steps
        if _run_steps and any(
            isinstance(s, dict) and s.get("type") in ("charge_wait", "wait") for s in _run_steps
        ):
            # A stepped run WITH STOPS is a deliberate sequence, so force strict order:
            # a path-optimizing brand (Roborock, honors_clean_order False) must then run
            # each group's rooms in the exact order shown instead of silently re-ordering
            # them inside one app_segment_clean. No-op for an order-honoring brand (Eufy):
            # _build_dispatch_phases folds effective_strict to False when honors_clean_order
            # is True, so Eufy stays byte-identical. Group boundaries (the stops) are already
            # enforced by the phase structure regardless; this only pins INTRA-group order.
            phases = self._build_steps_phases(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                effective_rooms=effective_rooms,
                included_room_ids=set(queue_state.get("queue_room_ids", []) or []),
                run_steps=_run_steps,
                strict_order=True,
            )
        else:
            phases = self._build_dispatch_phases(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                managed_rooms=effective_rooms,
                queue_room_ids=queue_state.get("queue_room_ids", []),
                strict_order=strict_order,
            )
        payload_state = phases[0]

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

        # Carpet + water-tank caution: a tank-driven mop (Roborock S6) with no
        # auto-lift wet-drags its pad across whatever it drives over. If the tank
        # is physically attached AND an included room is carpet, the run will mop
        # that carpet regardless of the room's vacuum-only software setting.
        # Non-blocking advisory; only for brands that declare a tank sensor.
        mop_carpet_warning = self._mop_carpet_warning(
            vacuum_entity_id=vacuum_entity_id,
            effective_rooms=effective_rooms,
            included_room_ids=included_room_ids,
        )

        # Clean-order advisory: some brands don't honor the queue order — the
        # device path-optimizes (Roborock app_segment_clean) unless an order is
        # set in the vacuum's own app. For those, the card's order is advisory, so
        # surface that at run start. Non-blocking; only when 2+ rooms will run.
        # Suppressed when strict_order is active — order is then ENFORCED (the
        # sequenced per-room dispatch), so the advisory would contradict.
        order_advisory = (
            None if strict_order
            else self._order_advisory(
                vacuum_entity_id=vacuum_entity_id,
                included_room_ids=included_room_ids,
            )
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
                "mop_carpet_warning": mop_carpet_warning,
                "order_advisory": order_advisory,
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
            "phases": phases,
            "preflight": preflight,
        }

    def get_runtime_path_block_report(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        trigger_entity_id: str | None = None,
        trigger_entity_state: Any = None,
    ) -> dict[str, Any] | None:
        """Return a runtime path-block report for one active job, if relevant.

        Re-evaluates blocker rules mid-job as entity states change. This is the
        sibling rule-evaluation site to ``_build_effective_start_plan`` (which
        runs at job start). Returns None when nothing actionable changed
        (deduped by a per-job signature) so the caller only fires events on a
        genuine new block.
        """
        active_job = self._manager._normalize_active_job(
            self._manager.get_active_job(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        )
        if active_job.get("status") not in {"started", "paused"}:
            return None

        managed_rooms = self._manager._normalized_managed_rooms_with_automation(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        validation = self._manager._validate_room_access_graph(managed_rooms=managed_rooms)
        if self._manager._structural_access_graph_issues(validation):
            return None

        queue_room_ids = [
            _safe_int(room_id, -1)
            for room_id in active_job.get("queue_room_ids", [])
            if _safe_int(room_id, -1) > 0
        ]
        if not queue_room_ids:
            return None

        completed_room_ids = {
            _safe_int(room_id, -1)
            for room_id in active_job.get("completed_room_ids", [])
            if _safe_int(room_id, -1) > 0
        }
        remaining_room_ids = [
            room_id for room_id in queue_room_ids if room_id not in completed_room_ids
        ]
        if not remaining_room_ids:
            active_job.pop("last_path_block_signature", None)
            return None

        grants_map, requires_map = self._manager._build_room_access_views(
            managed_rooms=managed_rooms
        )
        queue_room_id_set = set(queue_room_ids)

        direct_blocked: dict[int, dict[str, Any]] = {}
        room_names: dict[int, str] = {}
        triggered_rule_ids: list[str] = []
        blocker_rules_present = False

        for room_id in queue_room_ids:
            room = managed_rooms.get(str(room_id), {})
            if not isinstance(room, dict):
                continue
            room_names[room_id] = (
                str(room.get("name", f"Room {room_id}")).strip() or f"Room {room_id}"
            )
            for rule in room.get("rules", []):
                if not isinstance(rule, dict) or not bool(rule.get("enabled", True)):
                    continue
                if str(rule.get("kind", "")).strip().lower() != "blocker":
                    continue
                blocker_rules_present = True
                entity_id = str(rule.get("entity_id", "")).strip()
                if not entity_id or not self._manager._room_rule_matches(rule):
                    continue

                effect = (
                    rule.get("effect", {})
                    if isinstance(rule.get("effect"), dict)
                    else {}
                )
                direct_blocked.setdefault(
                    room_id,
                    self._build_blocked_room_entry(
                        room_id=room_id,
                        name=room_names[room_id],
                        source="direct_rule",
                        reason=str(
                            effect.get("reason") or rule.get("label") or entity_id
                        ).strip() or "rule_blocked",
                        triggered_rule_id=str(rule.get("id", "")).strip() or None,
                        trigger_entity_id=entity_id,
                    ),
                )
                if str(rule.get("id", "")).strip():
                    triggered_rule_ids.append(str(rule.get("id")).strip())

        if blocker_rules_present and not any(
            isinstance(room.get("grants_access_to"), list) and room.get("grants_access_to")
            for room in managed_rooms.values()
            if isinstance(room, dict)
        ):
            return None

        accessible_room_ids = {
            room_id
            for room_id in queue_room_ids
            if not requires_map.get(room_id)
        }
        accessible_room_ids -= set(direct_blocked)

        changed = True
        while changed:
            changed = False
            for room_id in queue_room_ids:
                if room_id in accessible_room_ids or room_id in direct_blocked:
                    continue
                parent_ids = [
                    parent_id
                    for parent_id in requires_map.get(room_id, [])
                    if parent_id in queue_room_id_set
                ]
                if parent_ids and any(
                    parent_id in accessible_room_ids for parent_id in parent_ids
                ):
                    accessible_room_ids.add(room_id)
                    changed = True

        affected_remaining_rooms: list[dict[str, Any]] = []
        directly_blocked_remaining_room_ids: list[int] = []
        indirectly_blocked_remaining_room_ids: list[int] = []
        for room_id in remaining_room_ids:
            if room_id in direct_blocked:
                affected_remaining_rooms.append(dict(direct_blocked[room_id]))
                directly_blocked_remaining_room_ids.append(room_id)
                continue
            if room_id in accessible_room_ids:
                continue

            parent_ids = [
                parent_id
                for parent_id in requires_map.get(room_id, [])
                if parent_id in queue_room_id_set
            ]
            blocked_by_room_id = parent_ids[0] if parent_ids else None
            affected_remaining_rooms.append(
                {
                    "room_id": room_id,
                    "name": room_names.get(room_id, f"Room {room_id}"),
                    "source": "access_dependency",
                    "reason": "access_blocked",
                    "triggered_rule_id": None,
                    "trigger_entity_id": trigger_entity_id,
                    "blocked_by_room_id": blocked_by_room_id,
                    "blocked_by_room_name": (
                        room_names.get(blocked_by_room_id, f"Room {blocked_by_room_id}")
                        if blocked_by_room_id is not None
                        else None
                    ),
                }
            )
            indirectly_blocked_remaining_room_ids.append(room_id)

        if not affected_remaining_rooms:
            active_job.pop("last_path_block_signature", None)
            self._manager.data.setdefault("active_jobs", {}).setdefault(
                vacuum_entity_id, {}
            )[str(map_id)] = active_job
            return None

        signature = hashlib.sha1(
            "|".join(
                [
                    str(trigger_entity_id or ""),
                    str(trigger_entity_state or ""),
                    ",".join(str(room["room_id"]) for room in affected_remaining_rooms),
                    ",".join(sorted(triggered_rule_ids)),
                ]
            ).encode("utf-8")
        ).hexdigest()[:16]
        if str(active_job.get("last_path_block_signature", "")).strip() == signature:
            return None

        active_job["last_path_block_signature"] = signature
        self._manager.data.setdefault("active_jobs", {}).setdefault(
            vacuum_entity_id, {}
        )[str(map_id)] = active_job

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "job_id": active_job.get("job_id"),
            "trigger_entity_id": trigger_entity_id,
            "trigger_entity_state": trigger_entity_state,
            "affected_remaining_room_ids": [
                str(item["room_id"]) for item in affected_remaining_rooms
            ],
            "affected_remaining_room_names": [
                str(item.get("name") or f"Room {item['room_id']}")
                for item in affected_remaining_rooms
            ],
            "directly_blocked_room_ids": [
                str(room_id) for room_id in directly_blocked_remaining_room_ids
            ],
            "indirectly_blocked_room_ids": [
                str(room_id) for room_id in indirectly_blocked_remaining_room_ids
            ],
            "remaining_room_ids": [str(room_id) for room_id in remaining_room_ids],
            "reason_codes": sorted(
                {
                    str(item.get("reason") or "").strip()
                    for item in affected_remaining_rooms
                    if str(item.get("reason") or "").strip()
                }
            ),
            "affected_rooms": affected_remaining_rooms,
            "requires_attention": True,
            "event_scope": "active_job_path_blocked",
        }
