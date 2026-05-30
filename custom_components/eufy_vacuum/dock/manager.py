"""DockManager — dock action dispatch, status gating, and event recording.

Owns:
- Dock action status (get_dock_action_status): gated availability of
  wash_mop / dry_mop / stop_dry_mop / empty_dust based on current
  lifecycle state, job state, vacuum position, and dock busy signals.
- Dock action dispatch (_async_run_dock_action and four public async
  methods): presses the upstream button entity if allowed.
- Dock event recording (record_dock_event): writes timestamps and
  increments debounced counters into data["dock_events"].
- Event counter management (set_dock_event_count, get_dock_events).

Receives a reference to the parent EufyVacuumManager so it can call
get_vacuum_capabilities, get_lifecycle_state, get_active_job, and
_find_button_entity_by_tokens without re-implementing them.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

# Noisy dock states flip 1-2x within ~30s per actual cycle.
# Debounce counters so each real dock action is counted once.
_DOCK_EVENT_DEBOUNCE_SECONDS: dict[str, int] = {
    "last_mop_wash": 60,
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _display_label(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).replace("_", " ").title()


class DockManager:
    """Owns dock action dispatch, status gating, and event recording."""

    def __init__(self, manager: "EufyVacuumManager") -> None:
        """Initialise with a reference to the parent EufyVacuumManager.

        The manager reference is needed to call get_vacuum_capabilities,
        get_lifecycle_state, get_active_job, and _find_button_entity_by_tokens.
        """
        self._manager = manager
        self._data = manager.data
        self._hass = manager.hass
        self._data.setdefault("dock_events", {})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_dock_action_entity(
        self,
        *,
        vacuum_entity_id: str,
        action: str,
    ) -> str | None:
        """Return the upstream button entity for one dock action."""
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

        registry = er.async_get(self._hass)
        for entity_id in action_candidates.get(action, []):
            if self._hass.states.get(entity_id) is not None:
                return entity_id
            if registry.async_get(entity_id) is not None:
                return entity_id

        for tokens in token_candidates.get(action, []):
            entity_id = self._manager._find_button_entity_by_tokens(
                object_id=object_id,
                required_tokens=tokens,
            )
            if entity_id is not None:
                return entity_id

        return None

    # ------------------------------------------------------------------
    # Dock action status
    # ------------------------------------------------------------------

    def get_dock_action_status(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return gated dock-action state for one vacuum/map."""
        from ..adapters.registry import get_adapter_config as _get_adapter_config
        from ..timestamp_utils import utc_now_iso

        capabilities = self._manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id, refresh=False
        )
        lifecycle = self._manager.get_lifecycle_state(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id
        )
        active_job = self._manager.get_active_job(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id
        )
        vacuum_state = self._hass.states.get(vacuum_entity_id)
        dock_status = str(lifecycle.get("dock_status") or "").strip().lower()
        vacuum_state_value = str(
            vacuum_state.state if vacuum_state is not None else ""
        ).strip().lower()
        docked = vacuum_state_value == "docked"
        active_job_running = active_job.get("status") in {"started", "paused"}

        _adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        _dock_triggers = _adapter_cfg.get("dock_events", {}).get("triggers", {})
        _adapter_vocab = _adapter_cfg.get("vocabulary", {})

        def _vocab_set(trigger_key: str) -> frozenset[str]:
            raw = _dock_triggers.get(trigger_key)
            if raw is not None:
                return frozenset(str(s).strip().lower() for s in raw)
            return frozenset()

        _wash_states: frozenset[str] = _vocab_set("last_mop_wash") or frozenset(
            {"washing", "washing mop"}
        )
        _dry_states: frozenset[str] = _vocab_set("last_dry_start") or frozenset(
            {"drying", "drying mop", "drying pads", "mop drying"}
        )
        _empty_states: frozenset[str] = _vocab_set("last_dust_empty") or frozenset(
            {"emptying dust", "emptying dust bin", "dust emptying"}
        )
        _hard_service_states: frozenset[str] = frozenset(
            str(s).strip().lower()
            for s in _adapter_vocab.get("hard_service_states", [])
        )

        def build_action_status(
            *, action: str, supported: bool, action_entity: str | None
        ) -> dict[str, Any]:
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

        wash_entity = self._get_dock_action_entity(
            vacuum_entity_id=vacuum_entity_id, action="wash_mop"
        )
        dry_entity = self._get_dock_action_entity(
            vacuum_entity_id=vacuum_entity_id, action="dry_mop"
        )
        stop_dry_entity = self._get_dock_action_entity(
            vacuum_entity_id=vacuum_entity_id, action="stop_dry_mop"
        )
        empty_entity = self._get_dock_action_entity(
            vacuum_entity_id=vacuum_entity_id, action="empty_dust"
        )

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
            "updated_at": utc_now_iso(),
        }

    # ------------------------------------------------------------------
    # Dock action dispatch
    # ------------------------------------------------------------------

    async def _async_run_dock_action(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        action: str,
    ) -> dict[str, Any]:
        """Run one gated dock action via the upstream button entity."""
        status = self.get_dock_action_status(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id
        )
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
        await self._hass.services.async_call(
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
        self, *, vacuum_entity_id: str, map_id: str
    ) -> dict[str, Any]:
        """Run gated wash-mop action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id, action="wash_mop"
        )

    async def async_dry_mop(
        self, *, vacuum_entity_id: str, map_id: str
    ) -> dict[str, Any]:
        """Run gated dry-mop action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id, action="dry_mop"
        )

    async def async_empty_dust(
        self, *, vacuum_entity_id: str, map_id: str
    ) -> dict[str, Any]:
        """Run gated empty-dust action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id, action="empty_dust"
        )

    async def async_stop_dry_mop(
        self, *, vacuum_entity_id: str, map_id: str
    ) -> dict[str, Any]:
        """Run gated stop-dry-mop action."""
        return await self._async_run_dock_action(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id, action="stop_dry_mop"
        )

    # ------------------------------------------------------------------
    # Dock event recording
    # ------------------------------------------------------------------

    def record_dock_event(
        self,
        *,
        vacuum_entity_id: str,
        event_type: str,
        dry_duration: str | None = None,
    ) -> None:
        """Record a dock event timestamp into storage."""
        from ..timestamp_utils import utc_now_iso

        self._data.setdefault("dock_events", {})
        vacuum_events = self._data["dock_events"].setdefault(vacuum_entity_id, {})
        now = utc_now_iso()
        vacuum_events[event_type] = now

        counter_map = {
            "last_mop_wash": "mop_wash_count",
            "last_dust_empty": "dust_empty_count",
            "last_dry_start": "dry_start_count",
        }
        counter_key = counter_map.get(event_type)
        if counter_key:
            debounce = _DOCK_EVENT_DEBOUNCE_SECONDS.get(event_type, 0)
            should_count = True
            if debounce > 0:
                last_counted = vacuum_events.get(f"{event_type}_last_counted_at")
                if last_counted:
                    try:
                        last_dt = datetime.fromisoformat(
                            last_counted.replace("Z", "+00:00")
                        )
                        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
                        if (now_dt - last_dt).total_seconds() < debounce:
                            should_count = False
                    except Exception:
                        pass
            if should_count:
                vacuum_events[counter_key] = (
                    _safe_int(vacuum_events.get(counter_key), 0) + 1
                )
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
        self._data.setdefault("dock_events", {})
        vacuum_events = self._data["dock_events"].setdefault(vacuum_entity_id, {})
        old_count = _safe_int(vacuum_events.get(counter_key), 0)
        vacuum_events[counter_key] = max(int(count), 0)
        return {
            "updated": True,
            "event_type": event_type,
            "old_count": old_count,
            "new_count": vacuum_events[counter_key],
        }

    def get_dock_events(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, str | None]:
        """Return stored dock event timestamps for one vacuum."""
        self._data.setdefault("dock_events", {})
        return self._data["dock_events"].get(vacuum_entity_id, {})
