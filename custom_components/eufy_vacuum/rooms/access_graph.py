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


def structural_issue_key(issue: dict[str, Any]) -> tuple:
    """A stable identity for one structural access-graph violation.

    A6-AGX-2. ``update_room_fields`` validates the WHOLE graph after an edit and
    rejects the edit if any structural issue exists — absolute, not a delta. So a
    violation already stored (reconciliation rewrites grants through an id remap
    and only de-dupes WITHIN one room's list, never re-checking the cross-room
    single-inbound constraint) rejects edits that have nothing to do with it: a
    fan-speed change, an enable toggle, a colour. Comparing post-edit issues
    against a pre-edit baseline needs an identity for "the same violation", which
    is this.

    The payload fields are load-bearing, not decoration:

    - ``source_room_ids`` (multiple_inbound) must be in the key. Adding a THIRD
      source to a room that already has two changes the key, so that edit is still
      correctly rejected as making an existing violation worse.
    - ``rooms`` is NOT sorted, deliberately. It is a cycle CHAIN for
      cycle_detected (order carries meaning) and is already sorted at source for
      multiple_dock_rooms. Sorting would collapse two different cycles over the
      same room set into one key, masking a newly-created cycle as pre-existing.
    """
    return (
        str(issue.get("type", "")).strip().lower(),
        _safe_int(issue.get("room_id"), -1),
        _safe_int(issue.get("target_room_id"), -1),
        tuple(_safe_int(value, -1) for value in list(issue.get("rooms", []) or [])),
        tuple(sorted(
            _safe_int(value, -1)
            for value in list(issue.get("source_room_ids", []) or [])
        )),
    )


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
    # anchor: BN9HSWTX
    # Internal ID generator
    # ------------------------------------------------------------------

    def _generate_room_rule_id(self) -> str:
        """Generate a unique room rule ID."""
        return f"rule_{datetime.now().strftime('%Y%m%dT%H%M%S%f')}"

    # ------------------------------------------------------------------
    # anchor: BNQHVRGC
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

        # Modifier rules may fan their effect out to additional rooms. The
        # field is authored by the card and must survive normalization, or
        # _build_effective_start_plan never applies the fan-out (the rule it
        # iterates is this normalized dict, not the raw stored one).
        fan_out_room_ids: list[int] = []
        if kind == "modifier":
            seen_fan_out: set[int] = set()
            for raw_target in (raw_rule.get("fan_out_room_ids") or []):
                target_id = _safe_int(raw_target, -1)
                if target_id <= 0 or target_id in seen_fan_out:
                    continue
                seen_fan_out.add(target_id)
                fan_out_room_ids.append(target_id)

        normalized_rule: dict[str, Any] = {
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
        if fan_out_room_ids:
            normalized_rule["fan_out_room_ids"] = fan_out_room_ids
        return normalized_rule

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
    # anchor: BNB031V0
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
                # Canonicalize room_id back onto the room (as an int, falling back to
                # the dict KEY when the value lacks the field) so every downstream
                # consumer gets a guaranteed int — matching the key-fallback the access
                # views already use. Without this, a room stored with a valid key but no
                # room_id field survives here without one and int(None)-crashes the whole
                # start plan (run_plan._build_effective_start_plan).
                "room_id": room_id,
                "is_dock_room": bool(room_data.get("is_dock_room", False)),
                "grants_access_to": self._normalize_grants_access_to(
                    room_data.get("grants_access_to", []),
                    room_id=room_id,
                ),
                "rules": self._normalize_room_rules(room_data.get("rules", [])),
            }
        return normalized

    # ------------------------------------------------------------------
    # anchor: BNX8KSJR
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
    # anchor: BNYV5NW7
    # Issue formatting
    # ------------------------------------------------------------------

    # anchor: INNPA4ZV  a user-facing message is a CODE plus PARAMS; the sentence,
    # and its punctuation, belong to the locale -- so lists are never pre-joined
    def _format_access_graph_issue(
        self,
        *,
        issue: dict[str, Any],
        room_names: dict[int, str],
    ) -> dict[str, Any]:
        """Convert one raw graph issue into a card-facing issue payload.

        Returns ``{code, message, params, room_ids}``.

        INNPA4ZV / A6-AGX-4: ``message`` is ENGLISH PROSE built here and is kept unchanged —
        it is the documented response-service surface (docs/advanced/03-services.md)
        that automations and non-card consumers read, so it cannot move. ``params``
        is the translation seam beside it: the values the sentence interpolates, as
        strings, never pre-joined. List-valued params (``rooms``, ``sources``) stay
        lists so the CARD chooses the separator — joining them here would bake an
        English list convention into every locale.
        """
        issue_type = str(issue.get("type", "")).strip().lower()

        if issue_type == "self_reference":
            room_id = _safe_int(issue.get("room_id"), -1)
            room_label = room_names.get(room_id, f"Room {room_id}") if room_id > 0 else "Room"
            return {
                "code": "self_reference",
                "message": f"{room_label} cannot grant access to itself.",
                "params": {"room": room_label},
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
                "params": {"room": room_label, "missing_room": missing_label},
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
                "params": {"room": room_label, "target": target_label},
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
                "params": {"rooms": list(cycle_labels)},
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
                "params": {"room": room_label, "sources": list(source_labels)},
                # A6-AGX-4: this used to be
                #   [str(room_id) if room_id > 0 else None] + [...]
                # which put a literal None into the contract whenever room_id was
                # unresolvable. Every sibling branch already filters; this one did
                # not. A6-AGX-5's per-room filter has to defend against that None
                # precisely because it could appear here.
                "room_ids": (
                    ([str(room_id)] if room_id > 0 else [])
                    + [str(s) for s in source_ids]
                ),
            }

        if issue_type == "missing_dock_room":
            return {
                "code": "missing_dock_room",
                "message": "One room must be marked as the dock room before access links can be considered healthy.",
                "params": {},
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
                "params": {"rooms": list(dock_labels)},
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
                "params": {"room": room_label, "dock": dock_label},
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
                "params": {"room": room_label, "dock": dock_label},
                "room_ids": [
                    value
                    for value in (str(room_id) if room_id > 0 else None, str(dock_room_id) if dock_room_id > 0 else None)
                    if value is not None
                ],
            }

        return {
            "code": issue_type or "unknown_issue",
            "message": "The access graph contains an unknown issue.",
            "params": {},
            "room_ids": [],
        }

    # ------------------------------------------------------------------
    # anchor: BNDK0JMV
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
    # anchor: BNS70XJJ
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

        # A6-AGX-3: the SAME delta question as A6-AGX-2's gate, deliberately via
        # the same helper. Selectability asked "is the candidate graph legal?"
        # absolutely, so ONE pre-existing violation anywhere — a stored
        # multiple_inbound, a second dock room, a cycle reconciliation created —
        # greyed out EVERY unselected target on EVERY room's editor, with the
        # contentless "Not selectable due to graph legality." because the reason
        # lookup could not find an issue naming this room.
        #
        # Hoisted out of the loop: it was recomputing the whole-graph validation
        # per candidate target, which is O(targets x graph) for an answer that
        # does not vary.
        baseline_keys = {
            structural_issue_key(issue)
            for issue in self._structural_access_graph_issues(context["validation"])
        }

        editable_targets: list[dict[str, Any]] = []
        for target_room_id, target_name in sorted(room_names.items(), key=lambda item: str(item[1]).lower()):
            if target_room_id == room_id_int:
                continue

            selected = target_room_id in selected_valid_targets
            selectable = True
            reason = None
            reason_code = None

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
                # Only what adding THIS edge breaks that was not already broken.
                new_issues = [
                    issue for issue in candidate_structural_issues
                    if structural_issue_key(issue) not in baseline_keys
                ]
                if new_issues:
                    selectable = False

                    def _names_edge(issue: dict[str, Any]) -> bool:
                        """Does this issue name either END of the candidate edge?

                        The old predicate matched only the EDITING room, so the
                        commonest refusal — multiple_inbound, which is keyed on the
                        TARGET with the editing room merely listed as a source —
                        matched nothing and fell through to the contentless
                        fallback. Both endpoints, and both id-carrying shapes.
                        """
                        ids = {
                            _safe_int(issue.get("room_id"), -1),
                            _safe_int(issue.get("target_room_id"), -1),
                        }
                        ids |= {
                            _safe_int(value, -1)
                            for value in list(issue.get("rooms", []) or [])
                        }
                        ids |= {
                            _safe_int(value, -1)
                            for value in list(issue.get("source_room_ids", []) or [])
                        }
                        return room_id_int in ids or target_room_id in ids

                    candidate_issue = next(
                        (
                            issue for issue in new_issues
                            if isinstance(issue, dict) and _names_edge(issue)
                        ),
                        None,
                    )
                    issue_type = str(candidate_issue.get("type", "")).strip().lower() if isinstance(candidate_issue, dict) else ""
                    # reason_code is the localizable half — A6-AGX-4's card
                    # resolver keys on it. `reason` stays English prose for now and
                    # crosses the same untranslated seam as the rest of that
                    # finding; do NOT localize it here, or it gets done twice.
                    if issue_type == "cycle_detected":
                        reason, reason_code = "Would create a loop.", "would_cycle"
                    elif issue_type == "duplicate_edge":
                        reason, reason_code = "Already linked.", "already_linked"
                    elif issue_type == "missing_room":
                        reason, reason_code = "Target is not available.", "target_unavailable"
                    elif issue_type == "self_reference":
                        reason, reason_code = "A room cannot link to itself.", "self_link"
                    elif issue_type == "multiple_inbound":
                        reason, reason_code = (
                            "Target already has an inbound access room.",
                            "target_has_inbound",
                        )
                    else:
                        # Now genuinely a last resort: every known structural type
                        # is handled above and _names_edge reaches all of them.
                        reason, reason_code = (
                            "Not selectable due to graph legality.",
                            "graph_illegal",
                        )

            editable_targets.append(
                {
                    "room_id": str(target_room_id),
                    "name": target_name,
                    "selectable": selectable,
                    "selected": selected,
                    "missing": False,
                    "reason": reason,
                    # A6-AGX-3: the localizable half. `reason` is English prose
                    # crossing the untranslated seam A6-AGX-4 owns; the card
                    # resolver keys on this instead.
                    "reason_code": reason_code,
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

        def _issue_applies(issue: dict[str, Any]) -> bool:
            """A6-AGX-5: graph-scoped issues reach EVERY room's editor.

            An issue carrying no ``room_ids`` (missing_dock_room, unknown_issue) is
            a property of the whole graph, not of one room — but the old membership
            test dropped it from every room, so a user opening a room editor while
            the map was unusable saw a clean panel.

            The ``is not None`` filter is load-bearing rather than tidiness:
            _format_access_graph_issue's multiple_inbound branch can emit a literal
            None inside room_ids, and a ``[None]`` list is truthy — without the
            filter it would read as "scoped to some room" and wrongly suppress the
            widening.
            """
            room_ids = [
                str(value) for value in list(issue.get("room_ids", []) or [])
                if value is not None
            ]
            return not room_ids or str(room_id_int) in room_ids

        # NOTE: multiple_dock_rooms is graph-scoped in effect but names only the
        # dock rooms, so an ordinary room still sees nothing here while the map is
        # blocked. That is deliberate — the whole-map verdict belongs on
        # get_access_graph_health (A6-AGX-1), not duplicated per room. Do not
        # "fix" it a second time in this filter.
        room_related_issues = [
            issue for issue in context["issues"] if _issue_applies(issue)
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
        managed_rooms = context["managed_rooms"]
        validation = context["validation"]
        block_code = self.access_graph_block_code(managed_rooms, validation)
        dock_room_ids = [
            str(room_id) for room_id in list(validation.get("dock_room_ids", []))
        ]
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "dock_room_ids": dock_room_ids,
            "missing_rooms": context["missing_rooms"],
            "issues": context["issues"],
            # --- A6-AGX-1: additive, so existing consumers are unaffected. ---
            # Without these a BLANK graph and a PARTIAL one are indistinguishable
            # here — identical issues, identical dock_room_ids, identical
            # missing_rooms — while one allows every run and the other refuses
            # every run.
            "state": self._access_graph_state(managed_rooms, validation),
            "runs_blocked": block_code is not None,
            "block_code": block_code,
            # The rooms that will become missing_dependency the MOMENT a dock room
            # is set — i.e. the cost of following this report's own advice. A blank
            # graph's only issue is "no dock room", so acting on it flips the state
            # to partial and blocks everything; naming the rooms up front is what
            # stops that being a trap.
            "unlinked_room_ids": sorted(
                (
                    str(room_id)
                    for room_id, parents in (context["requires_map"] or {}).items()
                    if not parents and str(room_id) not in dock_room_ids
                ),
                key=lambda value: _safe_int(value, 0),
            ),
        }

    # ------------------------------------------------------------------
    # anchor: BNRYWGGQ
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

        blank    — no dock room and no grants anywhere.

                   ⚠ NOT unconditionally permissive, and this line said "basic runs
                   are allowed" until 2026-08-24. `access_graph_block_code` in this
                   same file returns `access_graph_required_for_rules` for the blank
                   state whenever ANY room carries rules, and `_any_rooms_have_rules`
                   tests `bool(room.get("rules"))` only — so a DISABLED rule counts.
                   `run_plan` turns any non-None block code into blocked/unavailable
                   and returns before the queue is built, so on a blank graph with a
                   single rule anywhere every run is refused. This docstring is the
                   definition sheet for the three states and is what a maintainer
                   reasons from when deciding whether blank needs a block path — it
                   already has one. (R3)
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
    def access_graph_block_code(
        managed_rooms: dict[str, Any],
        validation: dict[str, Any] | None = None,
    ) -> str | None:
        """The reason runs are blocked by the access graph, or None.

        anchor: INSJM6KC  a gate judges only the DELTA, and the state it judges
        carries a VERDICT -- blank and partial must not be indistinguishable.

        A6-AGX-1. "Do runs block on the graph?" was asked in exactly one place —
        an inline if/elif inside planning/run_plan.py — and nowhere else could
        answer it. get_access_graph_health, the DOCUMENTED diagnostic a user or
        automation calls to find out, returned only dock_room_ids / missing_rooms
        / issues, and a BLANK graph (runs allowed) and a PARTIAL one (every run
        refused) produce byte-identical payloads: both carry exactly
        [{'type': 'missing_dock_room'}] with empty dock_room_ids and missing_rooms.
        The diagnostic could not distinguish "fine" from "everything is blocked".

        This is the de-dup ladder's HELPER rung — the QUESTION gets one owner
        rather than two copies that can drift. run_plan keeps its own
        reason -> message lookup; only the decision moves here.
        """
        state = AccessGraphManager._access_graph_state(managed_rooms, validation)
        if state == "partial":
            return "incomplete_access_graph"
        if state == "blank" and AccessGraphManager._any_rooms_have_rules(managed_rooms):
            return "access_graph_required_for_rules"
        return None

    @staticmethod
    def access_graph_block_rooms(
        managed_rooms: dict[str, Any],
        validation: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Return the rooms the block is ABOUT, as [{room_id, name}], name-sorted.

        A5-AG-2. `access_graph_block_code` answers "are runs blocked?"; this
        answers "because of which rooms?" — the half no shipped surface could
        answer. A map rebuild that discovers one new room makes the graph
        `partial`, and every Start on that map is then refused with a sentence
        that names no room, on a map that may have eleven. The user is told to
        "complete it or clear all access settings" with nothing to act on.

        Reads the RAW validation issues (``type`` + ``room_id``), not the
        card-facing formatted ones — this runs inside the start path, which
        never formats. Issues that name no room (``missing_dock_room``) yield
        nothing rather than a placeholder: an empty list is the honest answer
        and the caller has a sentence for it.

        Does NOT change what blocks. The map-wide block for a single
        unconfigured room is the other half of A5-AG-2 and is a semantics
        decision that stays with Chris; this only makes the existing refusal
        explicable.
        """
        if not validation:
            return []

        room_ids: list[int] = []
        for issue in validation.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            single = issue.get("room_id")
            if single is not None:
                room_ids.append(_safe_int(single, -1))
            # cycle_detected / multiple_dock_rooms name a SET of rooms; a cycle
            # chain repeats its entry room, so dedup below is load-bearing.
            for value in issue.get("rooms", []) or []:
                room_ids.append(_safe_int(value, -1))

        names: dict[int, str] = {}
        for room_id_key, room in managed_rooms.items():
            if not isinstance(room, dict):
                continue
            resolved = _safe_int(room.get("room_id", room_id_key), -1)
            if resolved > 0:
                names[resolved] = str(room.get("name") or f"Room {resolved}")

        seen: set[int] = set()
        unique = [
            room_id
            for room_id in room_ids
            if room_id > 0 and not (room_id in seen or seen.add(room_id))
        ]
        return [
            {"room_id": str(room_id), "name": names.get(room_id, f"Room {room_id}")}
            for room_id in sorted(unique, key=lambda item: names.get(item, f"Room {item}").lower())
        ]

    @staticmethod
    def _any_rooms_have_rules(managed_rooms: dict[str, Any]) -> bool:
        """Return True if any room has at least one rule configured."""
        return any(
            isinstance(room, dict) and bool(room.get("rules"))
            for room in managed_rooms.values()
        )

    # ------------------------------------------------------------------
    # anchor: BNX4QZGD
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

    # RP-008 (GUARD-1): states that mean "the sensor is not answering", not a
    # value of the world. A rule is a statement about the world; it cannot bind
    # to ignorance — so no VALUE-COMPARING operator (including the negating ones
    # and `missing`) may match while the rule entity reads one of these. GATE4
    # Q18: nothing in any install depends on matching these; if
    # fail-closed-on-dropout is ever wanted it arrives as an explicit per-rule
    # `when_unavailable` field, never by string-matching sentinels.
    #
    # ⚠ `exists` IS THE EXCEPTION, and this comment said "NO operator" until
    # 2026-08-24. `_room_rule_matches_known` returns for `exists` BEFORE reaching
    # the sentinel check — "presence of the entity is an observable fact either
    # way" — and an entity reading `unavailable` still yields a state object, so
    # `exists` matches while the sensor is dark. The carve-out is deliberate and
    # is NOT being changed here; what was wrong is this comment claiming a
    # universal that the code one screen down contradicts.
    #
    # It matters because of who reads this: an auditor checking dropout safety, or
    # whoever implements the promised `when_unavailable`, reads "NO operator ...
    # may match" and skips `exists` as already covered. A blocker rule using
    # `exists` on a door sensor keeps blocking, and a modifier keeps mutating fan
    # speed and water level, while that sensor is reading `unavailable` — the
    # exact dropout GUARD-1 was written to stop. (R2)
    INDETERMINATE_STATE_VALUES = frozenset({"unavailable", "unknown"})

    def _room_rule_matches_known(self, rule: dict[str, Any]) -> tuple[bool, bool]:
        """Evaluate one room rule -> (matched, known).

        known=False is INDETERMINATE: the rule entity is absent or reads a
        dropout sentinel, so there is no fact to compare. Callers must treat
        INDETERMINATE as hold-previous (runtime) or no-match (plan time) — a
        dropout used to read as an ordinary string and a `not_equals` rule then
        cancelled a live run because a door sensor's battery died.
        """
        entity_id = str(rule.get("entity_id", "")).strip()
        operator = str(rule.get("operator", "equals")).strip().lower()
        state_obj = self._hass.states.get(entity_id) if entity_id else None

        if operator == "exists":
            # Presence of the entity is an observable fact either way.
            return (state_obj is not None, True)
        if operator == "missing":
            # An absent entity is the definition of not-knowing — `missing`
            # matching it would be a rule firing on ignorance (dead by design;
            # GATE4 Q18 records the principle and the future opt-in shape).
            return (False, state_obj is not None)
        if state_obj is None:
            return (False, False)

        state_value = state_obj.state
        if str(state_value).strip().lower() in self.INDETERMINATE_STATE_VALUES:
            return (False, False)
        matched = self._room_rule_value_matches(
            operator=operator, state_value=state_value, target_value=rule.get("value")
        )
        return (matched, True)

    def _room_rule_matches(self, rule: dict[str, Any]) -> bool:
        """Boolean compat wrapper — INDETERMINATE never matches (plan-time rule)."""
        matched, known = self._room_rule_matches_known(rule)
        return matched and known

    def _room_rule_value_matches(
        self, *, operator: str, state_value: Any, target_value: Any
    ) -> bool:
        """The value-comparison core, on a KNOWN state only."""
        normalized_state = self._normalize_rule_operand(state_value)

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
