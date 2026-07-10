"""ProfileManager — room profile and run profile CRUD for each managed vacuum/map.

Owns:
- data["profiles"]["room_profiles"] — custom room profile library.
- data["run_profiles"] — per-vacuum/map saved run-profile library.
- Room profile helpers: get_room_profiles, save/overwrite/rename/delete,
  apply_room_profile, get_effective_room_details.
- Run profile helpers: get_saved_run_profiles, save/overwrite/rename/delete,
  apply_run_profile.
- Shared room-config utilities used internally and also delegated from
  EufyVacuumManager for use by room-management and planning code:
    _protected_room_config, _match_profile_from_fields, _finalize_room_update.

Receives a reference to the parent EufyVacuumManager so it can call
get_effective_room_details (from room profile save-from-room),
_notify_run_profiles_updated, _notify_rooms_updated, and
_refresh_room_derived_state without re-implementing them.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..entity_helpers import get_floor_type_label
from ..maps.map_manager import ensure_map_bucket, get_map_bucket
from ..profiles.room_profiles import (
    BUILT_IN_ROOM_PROFILES,
    apply_room_profile_to_config,
    get_default_room_profiles,
    merge_profile_dicts,
    normalize_room_profile,
    resolve_profile_catalog,
    resolve_room_profile_for_room,
)
from ..rooms.room_manager import build_room_selection_summary
from ..timestamp_utils import utc_now_iso

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

_PROTECTED_ROOM_PROFILE_NAMES: frozenset[str] = frozenset(BUILT_IN_ROOM_PROFILES.keys())


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


class ProfileManager:
    """Owns room-profile and run-profile CRUD for each managed vacuum/map."""

    def __init__(self, manager: "EufyVacuumManager") -> None:
        """Initialise with a reference to the parent EufyVacuumManager."""
        self._manager = manager
        self._data = manager.data

    # ------------------------------------------------------------------
    # ID generators
    # ------------------------------------------------------------------

    def _generate_room_profile_id(self) -> str:
        """Generate a stable unique key for a new custom room profile."""
        return f"user_{datetime.now().strftime('%Y%m%dT%H%M%S')}"

    def _generate_run_profile_id(self) -> str:
        """Generate a stable unique key for a new saved run profile."""
        return f"rp_{datetime.now().strftime('%Y%m%dT%H%M%S')}"

    # ------------------------------------------------------------------
    # Shared room-config utilities
    # (also delegated from EufyVacuumManager for planning / room-update code)
    # ------------------------------------------------------------------

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
        stored_profiles = self._data.get("profiles", {}).get("room_profiles", {})

        for name, profile in profiles.items():
            effective_profile = resolve_room_profile_for_room(
                room_config={"profile_name": name},
                stored_profiles=stored_profiles,
            )
            protected_room = self._protected_room_config(room)
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

    def _finalize_room_update(self, room: dict[str, Any]) -> dict[str, Any]:
        """Return a fully sanitized room dict produced by the protection → derive → profile-match pipeline.

        Applies carpet/mop invariants, syncs ``path_type`` from the resolved profile,
        and snaps ``profile_name`` to the best-matching preset (or ``"custom"``).
        Returns a new dict; does not mutate the input.
        """
        result = self._protected_room_config(room)
        _stored_profiles = self._data.get("profiles", {}).get("room_profiles", {})
        _resolved = resolve_room_profile_for_room(
            room_config=result,
            stored_profiles=_stored_profiles,
        )
        result["path_type"] = _resolved.get("path_type")
        matched = self._match_profile_from_fields(result)
        result["profile_name"] = matched if matched else "custom"
        return result

    # ------------------------------------------------------------------
    # Room profile CRUD
    # ------------------------------------------------------------------

    def _get_custom_room_profile_store(self) -> dict[str, Any]:
        """Return mutable storage for custom room profiles."""
        self._data.setdefault("profiles", {})
        self._data["profiles"].setdefault("room_profiles", {})
        return self._data["profiles"]["room_profiles"]

    def _get_editable_room_profile(
        self, profile_name: str
    ) -> tuple[str, dict[str, Any] | None]:
        """Return one editable custom room profile by name."""
        normalized = str(profile_name or "").strip()
        if not normalized or normalized in _PROTECTED_ROOM_PROFILE_NAMES:
            return normalized, None
        stored_profiles = self._get_custom_room_profile_store()
        profile = stored_profiles.get(normalized)
        return normalized, profile if isinstance(profile, dict) else None

    def get_room_profiles(self) -> dict[str, Any]:
        """Return available room profiles."""
        self._data.setdefault("profiles", {})
        stored_profiles = self._data["profiles"].get("room_profiles", {})
        merged = merge_profile_dicts(
            built_in_profiles=get_default_room_profiles(),
            stored_profiles=stored_profiles,
        )
        return {
            "profile_count": len(merged),
            "profiles": merged,
            "protected_profile_names": sorted(_PROTECTED_ROOM_PROFILE_NAMES),
        }

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
            data=self._data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )

        rooms = map_bucket.get("rooms", {})
        room = rooms.get(str(room_id))
        if room is None:
            return None

        stored_profiles = self._data.get("profiles", {}).get("room_profiles", {})
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
        self._data.setdefault("profiles", {})
        self._data["profiles"].setdefault("room_profiles", {})

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
        self._data["profiles"]["room_profiles"][target_profile_name] = profile

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
            data=self._data,
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
            data=self._data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        rooms = map_bucket.get("rooms", {})
        normalized_ids = [int(r) for r in room_ids if str(r).isdigit() or (isinstance(r, int))]

        # Resolve the adapter's room-profile catalog so a non-Eufy brand fills any
        # omitted profile field from ITS normalize_defaults, not the in-code Eufy
        # ones. Local import mirrors the other get_adapter_config call sites and
        # avoids an import cycle. Absent coordinator/config → Eufy defaults.
        from ..adapters.registry import get_adapter_config

        catalog = resolve_profile_catalog(
            (get_adapter_config(vacuum_entity_id) or {}).get("room_profiles")
        )

        updated_room_ids: list[int] = []
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
                    catalog=catalog,
                )
            )

            rooms[room_key] = updated_room
            updated_room_ids.append(room_id)

        map_bucket["rooms"] = rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)
        self._manager._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._manager._room_history_cache_ready.discard(vacuum_entity_id)
        self._manager._notify_rooms_updated(
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

    # ------------------------------------------------------------------
    # Run profile CRUD
    # ------------------------------------------------------------------

    def _get_saved_run_profile_store(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, dict[str, Any]]:
        """Return the saved run-profile library for one vacuum/map."""
        self._data.setdefault("run_profiles", {})
        self._data["run_profiles"].setdefault(vacuum_entity_id, {})
        self._data["run_profiles"][vacuum_entity_id].setdefault(str(map_id), {})
        store = self._data["run_profiles"][vacuum_entity_id][str(map_id)]
        return store if isinstance(store, dict) else {}

    def _snapshot_room_for_run_profile(self, room: dict[str, Any]) -> dict[str, Any]:
        """Return the persisted room fields relevant to a saved run profile."""
        return {
            "room_id": _safe_int(room.get("room_id", room.get("id", -1))),
            "name": str(room.get("name", "")),
            "profile_name": str(room.get("profile_name", "vacuum_quick")),
            "clean_mode": str(room.get("clean_mode", "vacuum")),
            "fan_speed": str(room.get("fan_speed", "Max")),
            "water_level": str(room.get("water_level", "Off")),
            "clean_intensity": str(room.get("clean_intensity", "Standard")),
            "clean_passes": int(room.get("clean_passes", 1)),
            "edge_mopping": bool(room.get("edge_mopping", False)),
            "order": int(room.get("order", 999)),
        }

    def _run_profile_summary(self, rooms: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a compact human-facing summary for one saved run profile."""
        room_names = [
            str(r.get("name", "")).strip()
            for r in rooms
            if str(r.get("name", "")).strip()
        ]
        room_ids = [_safe_int(r.get("room_id", -1)) for r in rooms if _safe_int(r.get("room_id", -1)) >= 0]
        return {
            "room_count": len(rooms),
            "room_ids": room_ids,
            "room_names": room_names,
            "room_names_label": ", ".join(room_names) if room_names else "",
        }

    @staticmethod
    def normalize_run_profile_steps(steps: Any) -> list[dict[str, Any]]:
        """Validate/coerce an ordered run-profile steps list. A step is a room_group
        ({type:'room_group', rooms:[...]}), a charge_wait ({type:'charge_wait',
        target_battery_percent:int clamped 1..100}), or a wait ({type:'wait',
        wait_minutes:int clamped 1..1440}). Invalid/empty entries are dropped.

        room_group entries are coerced to well-formed ``{room_id:int, ...}`` dicts: a
        bare int is wrapped; an entry whose room_id doesn't parse to a positive int is
        dropped. A group left with no valid room is dropped entirely, so dispatch never
        sees an unparseable room_id."""
        out: list[dict[str, Any]] = []
        for step in steps if isinstance(steps, list) else []:
            if not isinstance(step, dict):
                continue
            stype = str(step.get("type") or "").strip().lower()
            if stype == "room_group":
                rooms = step.get("rooms")
                if not isinstance(rooms, list):
                    continue
                clean_rooms: list[dict[str, Any]] = []
                for r in rooms:
                    if isinstance(r, dict):
                        room_id = _safe_int(r.get("room_id"), -1)
                        if room_id > 0:
                            clean_rooms.append({**r, "room_id": room_id})
                    else:
                        room_id = _safe_int(r, -1)
                        if room_id > 0:
                            clean_rooms.append({"room_id": room_id})
                if clean_rooms:
                    out.append({"type": "room_group", "rooms": clean_rooms})
            elif stype == "charge_wait":
                try:
                    tgt = int(step.get("target_battery_percent"))
                except (TypeError, ValueError):
                    continue
                out.append({"type": "charge_wait", "target_battery_percent": max(1, min(tgt, 100))})
            elif stype == "wait":
                try:
                    mins = int(step.get("wait_minutes"))
                except (TypeError, ValueError):
                    continue
                out.append({"type": "wait", "wait_minutes": max(1, min(mins, 1440))})
        return out

    @staticmethod
    def run_profile_steps(profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Return a profile's ordered steps, back-filling a legacy rooms-only profile
        as a single room_group step. Sequencing intent (room grouping + charge
        boundaries) lives in the steps list; old profiles carried only ``rooms``."""
        steps = profile.get("steps") if isinstance(profile, dict) else None
        if isinstance(steps, list) and steps:
            return ProfileManager.normalize_run_profile_steps(steps)
        rooms = (profile or {}).get("rooms", [])
        return [{"type": "room_group", "rooms": list(rooms)}] if rooms else []

    def _enrich_saved_run_profile(
        self, profile_id: str, profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Return one normalized saved run profile with derived metadata."""
        steps = self.run_profile_steps(profile)
        # Derive the room metadata from the EFFECTIVE steps (the flattened room_group
        # rooms, same flattening apply_run_profile uses) rather than profile["rooms"].
        # A stepped edit only rewrites steps; profile["rooms"] then holds the stale
        # pre-steps set. run_profile_steps back-fills a single room_group for legacy
        # rooms-only profiles, so this stays byte-identical for those.
        _room_group_steps = [s for s in steps if s.get("type") == "room_group"]
        _effective_rooms = [r for s in _room_group_steps for r in s.get("rooms", [])]
        summary = self._run_profile_summary(_effective_rooms)
        return {
            **profile,
            "id": profile_id,
            "room_count": summary["room_count"],
            "room_ids": summary["room_ids"],
            "room_names": summary["room_names"],
            "room_names_label": summary["room_names_label"],
            "expose_as_button": bool(profile.get("expose_as_button", False)),
            "steps": steps,
            "has_charge_steps": any(s.get("type") == "charge_wait" for s in steps),
            # has_stops == "this is a SEQUENCED run, not a plain queue": any break step
            # (charge_wait / wait) OR more than one room_group. DISTINCT from the
            # charge-only has_charge_steps. The frontend gates stepped preview/routing
            # on has_stops. (SHARED CONTRACT with the frontend lane.)
            "has_stops": (
                any(s.get("type") in ("charge_wait", "wait") for s in steps)
                or len(_room_group_steps) > 1
            ),
        }

    def _current_enabled_rooms_for_run_profile(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> list[dict[str, Any]]:
        """Return current enabled rooms in queue order for run-profile save/overwrite."""
        map_bucket = get_map_bucket(
            data=self._data,
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        rooms = map_bucket.get("rooms", {})
        enabled_rooms = [
            self._snapshot_room_for_run_profile(room)
            for room in rooms.values()
            if isinstance(room, dict) and bool(room.get("enabled", False))
        ]
        enabled_rooms.sort(
            key=lambda room: (int(room.get("order", 999)), str(room.get("name", "")))
        )
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
        now = utc_now_iso()
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
        self._manager._notify_run_profiles_updated(
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

    def set_run_profile_steps(
        self, *, vacuum_entity_id: str, map_id: str, profile_id: str, steps: Any
    ) -> dict[str, Any]:
        """Replace one saved profile's ordered steps (room_group | charge_wait).

        The steps list holds the sequence — room groups and the charge boundaries
        between them. Requires at least one room_group (a run must clean something).
        """
        library = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
        )
        existing = library.get(profile_id)
        if not isinstance(existing, dict):
            return {"vacuum_entity_id": vacuum_entity_id, "map_id": str(map_id),
                    "saved": False, "reason": "profile_not_found", "profile_id": profile_id}
        normalized = self.normalize_run_profile_steps(steps)
        if not any(s.get("type") == "room_group" for s in normalized):
            return {"vacuum_entity_id": vacuum_entity_id, "map_id": str(map_id),
                    "saved": False, "reason": "no_room_group", "profile_id": profile_id}
        existing["steps"] = normalized
        existing["updated_at"] = utc_now_iso()
        self._manager._notify_run_profiles_updated(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
        )
        return {"vacuum_entity_id": vacuum_entity_id, "map_id": str(map_id),
                "saved": True, "profile_id": profile_id,
                "profile": self._enrich_saved_run_profile(profile_id, existing)}

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
            "expose_as_button": bool(
                existing.get("expose_as_button", False) if expose_as_button is None else expose_as_button
            ),
            "rooms": enabled_rooms,
            # Overwrite replaces the whole run with the current enabled-room queue, so
            # any prior sequencing is intentionally discarded. The {**existing} spread
            # would otherwise carry the STALE steps list forward — and run_profile_steps
            # prefers a non-empty steps list, so apply/start would clean the old rooms
            # and ignore the new ones. Reset steps so run_profile_steps back-fills a
            # single room_group of the NEW rooms, matching the overwrite's intent.
            "steps": [],
            "updated_at": utc_now_iso(),
        }
        library[profile_id] = updated_profile
        self._manager._notify_run_profiles_updated(
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
        library[profile_id]["updated_at"] = utc_now_iso()
        self._manager._notify_run_profiles_updated(
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
        self._manager._notify_run_profiles_updated(
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
            data=self._data,
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
        # Enable the rooms named by the profile's STEPS (room_group steps, in order).
        # Legacy rooms-only profiles are byte-identical — run_profile_steps back-fills
        # a single room_group of profile["rooms"]. Charge_wait steps carry no rooms.
        _profile_rooms = [
            r for step in self.run_profile_steps(profile) if step.get("type") == "room_group"
            for r in step.get("rooms", [])
        ]
        for index, room_snapshot in enumerate(_profile_rooms, start=1):
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
        self._manager._refresh_room_derived_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._manager._notify_rooms_updated(
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
        """Apply one saved run profile and start it through the normal protected path.

        Run-profile orchestration lives with the profiles subsystem; the core manager keeps a
        thin ``start_run_profile`` delegator for its service + button-entity callers. Dispatch
        (``start_selected_rooms``) and queue/payload building stay on the core manager and are
        reached via ``self._manager``.
        """
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

        # Stash the profile's charge-step sequence so the plan builder materializes a
        # multi-phase [clean, charge_wait, clean] job. Consumed (popped) in
        # run_plan._build_effective_start_plan; absent -> normal atomic dispatch.
        _prof = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
        ).get(profile_id, {})
        _prof_steps = self.run_profile_steps(_prof)
        if any(isinstance(s, dict) and s.get("type") in ("charge_wait", "wait") for s in _prof_steps):
            self._manager.data.setdefault("_pending_run_steps", {}).setdefault(
                vacuum_entity_id, {}
            )[str(map_id)] = _prof_steps

        self._manager.build_queue(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        self._manager.build_room_payload(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        )
        started = await self._manager.start_selected_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            confirm_reduced_run=confirm_reduced_run,
            confirm_token=confirm_token,
            path_block_action=path_block_action,
            pause_timeout_minutes_override=pause_timeout_minutes_override,
        )
        # start_selected_rooms POPS the stashed steps only deep in _build_effective_start_plan,
        # which it never reaches when it returns early (blocked / confirmation-required without a
        # token / vacuum missing). That would leak the stash so the NEXT plain Start on this map
        # pops it and silently becomes a charge/wait run. If this call did NOT start, delete the
        # leftover entry (guard for absence — the legit started path already consumed it deep in
        # the plan builder, so there is nothing to delete there).
        if not started.get("started"):
            _pending_for_vac = self._manager.data.get("_pending_run_steps", {}).get(vacuum_entity_id)
            if isinstance(_pending_for_vac, dict):
                _pending_for_vac.pop(str(map_id), None)
        started["profile_id"] = profile_id
        started["profile"] = applied.get("profile")
        return started
