"""Per-room rule-status sensor.

Surfaces the most recent rule / preflight evaluation outcome for a
single room, so automations can react to "the bedroom is blocked
right now" or "the kitchen got a modifier applied" without parsing
the full preflight payload.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from ..room_entities import EufyVacuumRoomEntity


class EufyVacuumRoomRuleStatusSensor(EufyVacuumRoomEntity, SensorEntity):
    """Per-room last rule/preflight evaluation report sensor."""

    _attr_icon = "mdi:clipboard-text-clock-outline"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator_key: str,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_data: dict[str, Any],
    ) -> None:
        """Initialize room rule-status sensor."""
        super().__init__(
            coordinator_key=coordinator_key,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            room_id=room_id,
            room_data=room_data,
            label="Rule Status",
            unique_suffix="rule_status",
        )

    def _get_rule_status(self) -> dict[str, Any]:
        """Return the latest stored rule/preflight evaluation status."""
        return self.manager.get_room_rule_status(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
        )

    @property
    def native_value(self) -> str:
        """Return the last evaluation result for this room."""
        return str(self._get_rule_status().get("last_result", "never"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full rule/preflight evaluation detail for automation reporting."""
        status = self._get_rule_status()
        return {
            **super().extra_state_attributes,
            "last_evaluated_at": status.get("last_evaluated_at"),
            "last_result": status.get("last_result"),
            "last_selected": status.get("last_selected"),
            "last_included": status.get("last_included"),
            "last_block_reason": status.get("last_block_reason"),
            "last_block_source": status.get("last_block_source"),
            "last_blocked_by_room_id": status.get("last_blocked_by_room_id"),
            "last_blocked_by_room_name": status.get("last_blocked_by_room_name"),
            "last_triggered_rule_ids": status.get("last_triggered_rule_ids"),
            "last_modifier_changes": status.get("last_modifier_changes"),
            "last_requires_confirmation": status.get("last_requires_confirmation"),
            "last_preflight_reason": status.get("last_preflight_reason"),
            "last_warning_codes": status.get("last_warning_codes"),
            "last_evaluation_scope": status.get("last_evaluation_scope"),
        }
