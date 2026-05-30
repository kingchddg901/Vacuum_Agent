"""AccessGraphManager — room access graph and automation rule evaluation.

Owns:
- _normalize_grants_access_to / _normalize_room_rule / _normalize_room_rules
- _normalized_managed_rooms_with_automation
- _build_room_access_views
- _format_access_graph_issue / _room_access_context
- get_room_access_editor
- get_access_graph_health
- _validate_room_access_graph
- _structural_access_graph_issues (staticmethod)
- _access_graph_state (staticmethod)
- _any_rooms_have_rules (staticmethod)
- _normalize_rule_operand / _room_rule_matches

Receives data (the integration root data dict) and hass (HomeAssistant instance).
Does not need a reference to the parent EufyVacuumManager.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from ..maps.map_manager import get_map_bucket

_LOGGER = logging.getLogger(__name__)


def _safe_int(value: Any, default: int = 0) -> int:
    """Return int value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


class AccessGraphManager:
    """Owns room access graph validation and automation rule evaluation."""

    def __init__(
        self,
        data: dict[str, Any],
        hass: HomeAssistant,
    ) -> None:
        """Initialise with the integration root data dict and hass instance.

        Args:
            data: Integration root data dict.
            hass: HomeAssistant instance (to read entity states for rule eval).
        """
        self._data = data
        self._hass = hass

    # ------------------------------------------------------------------
    # Internal ID generator
    # ------------------------------------------------------------------

    def _generate_room_rule_id(self) -> str:
        """Generate a unique room rule ID."""
        return f"rule_{datetime.now().strftime('%Y%m%dT%H%M%S%f')}"

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Managed rooms with automation metadata
    # ------------------------------------------------------------------

    def _normalized_managed_rooms_with_automation(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Return managed rooms with canonical automation metadata."""
        map_bucket = get_map_bucket(
            data=self._data,
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

    # ------------------------------------------------------------------
    # Access graph views
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Issue formatting
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Room access context (internal aggregate)
    # ------------------------------------------------------------------

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
    # Public API — access graph editor / health
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

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

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
    # Rule evaluation
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
        state_obj = self._hass.states.get(entity_id) if entity_id else None

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
