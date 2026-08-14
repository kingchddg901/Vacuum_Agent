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

from ..const import DOMAIN
from ..entity_helpers import get_floor_type_label
from ..maps.map_manager import ensure_map_bucket, get_map_bucket
from ..profiles.room_profiles import (
    PROTECTED_ROOM_PROFILE_NAMES,
    apply_room_profile_to_config,
    canonical_clean_mode,
    get_default_room_profiles,
    is_mop_clean_mode,
    merge_profile_dicts,
    VOCABULARY_FIELDS,
    declared_profile_fields,
    no_water_value,
    coerce_clean_intensity,
    normalize_room_profile,
    resolve_profile_catalog,
    resolve_room_profile_for_room,
)
from ..rooms.room_manager import build_room_selection_summary
from ..timestamp_utils import utc_now_iso
from ..step_types import plan_requires_stepped_execution, step_requires_stepped_execution
from homeassistant.exceptions import ServiceValidationError

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

# The canonical profile KEY space, owned by core. Sourced from a brand catalog
# until 2026-08-07, which made one brand's dict decide what every user could
# rename — and left core unable to protect a name if that brand stopped shipping.
_PROTECTED_ROOM_PROFILE_NAMES: frozenset[str] = PROTECTED_ROOM_PROFILE_NAMES


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

    def _protected_room_config(
        self, room: dict[str, Any], *, vacuum_entity_id: str
    ) -> dict[str, Any]:
        """Return a room config with impossible mode/surface combinations removed.

        Carpet rooms are downgraded away from mop-only modes; any non-mop mode
        clears water_level and edge_mopping regardless of floor type.

        "No water" is a framework concept; the WORD for it belongs to the brand, so
        ``vacuum_entity_id`` selects whose. This assigned the literal ``"Off"`` — Eufy's
        casing — which is how every Roborock room on a live install came to store a value
        absent from that brand's own declared options. It is the THIRD copy of this
        predicate: ``resolve_room_profile_for_room`` and ``apply_capability_gate`` were
        each fixed separately, and this one was missed both times.
        """
        no_water = no_water_value(self._catalog_for(vacuum_entity_id))
        protected = dict(room)

        floor_type = str(protected.get("floor_type", "")).lower()
        clean_mode = str(protected.get("clean_mode", "")).lower()

        is_carpet = floor_type.startswith("carpet")
        # ISSUE #48: one shared predicate. "wash" is kept as an extra tolerance
        # this copy had and the canonical table does not cover.
        is_mop_mode = is_mop_clean_mode(clean_mode) or "wash" in clean_mode

        if is_carpet:
            # Was `clean_mode in {"mop", "vacuum_mop"}` — the same exact,
            # case-sensitive membership test that lost Edge Mopping on the read
            # path. Here it under-fired instead: a carpet room stored as
            # "Vacuum and mop" (the spelling the card actually writes) was NOT
            # downgraded, so it kept a mop mode with water and edge forced off —
            # the carpet invariant half-applied.
            if is_mop_clean_mode(clean_mode):
                protected["clean_mode"] = "vacuum"
                clean_mode = "vacuum"
                is_mop_mode = False

            protected["water_level"] = no_water
            protected["edge_mopping"] = False

        if not is_mop_mode:
            protected["water_level"] = no_water
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

    def _catalog_for(self, vacuum_entity_id: str) -> dict[str, Any]:
        """Resolve the room-profile catalog DECLARED by this vacuum's adapter.

        Every resolution path goes through here. Core ships no catalog of its own,
        so a caller that cannot name a vacuum cannot resolve a profile — which is
        the point: the four call sites that used to omit this were silently
        resolving every brand's rooms against Eufy's vocabulary, and the omission
        was invisible precisely because the framework had a default to give them.

        Local import mirrors the other ``get_adapter_config`` call sites and keeps
        the registry out of this module's import cycle.
        """
        from ..adapters.registry import get_adapter_config

        return resolve_profile_catalog(
            (get_adapter_config(vacuum_entity_id) or {}).get("room_profiles")
        )

    def _match_profile_from_fields(
        self, room: dict[str, Any], *, vacuum_entity_id: str
    ) -> str | None:
        """Return matching profile name if the room's protected fields match a preset.

        Both sides run through the SAME resolve -> protect pipeline under the room's
        ``floor_type``, so floor-driven invariants apply symmetrically. Previously the
        candidate was resolved from a bare ``{profile_name}`` (no floor_type), which
        picked up the hardwood water default ("Low") while a vacuum room's protected
        water is forced "Off" -> a plain vacuum room never matched its vacuum preset
        and always fell through to "custom". Resolving + protecting the candidate
        under the room's floor closes that asymmetry.

        ``vacuum_entity_id`` selects the catalog both sides resolve against. Matching
        a room against another brand's presets is how a room silently became
        "custom" — or worse, matched a preset whose values the device cannot accept.
        """
        catalog = self._catalog_for(vacuum_entity_id)
        profiles = self.get_room_profiles(vacuum_entity_id=vacuum_entity_id)["profiles"]
        stored_profiles = self._data.get("profiles", {}).get("room_profiles", {})
        protected_room = self._protected_room_config(room, vacuum_entity_id=vacuum_entity_id)
        room_floor_type = room.get("floor_type")

        for name, profile in profiles.items():
            candidate_config: dict[str, Any] = {"profile_name": name}
            if room_floor_type:
                candidate_config["floor_type"] = room_floor_type
            effective_profile = self._protected_room_config(
                resolve_room_profile_for_room(
                    room_config=candidate_config,
                    stored_profiles=stored_profiles,
                    catalog=catalog,
                ),
                vacuum_entity_id=vacuum_entity_id,
            )
            if (
                # clean_mode is compared through the canonical owner, the other five
                # legs are not. ISSUE #48: _normalize_profile_match_value only folds
                # case and the off/true/false/numeric literals, so it compared the
                # stored display label "Vacuum and mop" against the catalog's token
                # "vacuum_mop" and returned unequal — every card-saved non-carpet mop
                # room failed to match ANY preset and was stamped profile_name
                # "custom". Carpet rooms escaped only because the carpet guard
                # downgrades them to vacuum first.
                #
                # Only this leg. The other five compare a BRAND's vocabulary, which
                # core does not own and has no canonical form for; widening the shared
                # normalizer would assert a framework opinion about words like "Max"
                # and "Quick" that belong to the adapter.
                canonical_clean_mode(protected_room.get("clean_mode"))
                == canonical_clean_mode(effective_profile.get("clean_mode"))
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

    def _finalize_room_update(
        self, room: dict[str, Any], *, vacuum_entity_id: str
    ) -> dict[str, Any]:
        """Return a fully sanitized room dict produced by the protection → derive → profile-match pipeline.

        Applies carpet/mop invariants, syncs ``path_type`` from the resolved profile,
        and snaps ``profile_name`` to the best-matching preset (or ``"custom"``).
        Returns a new dict; does not mutate the input.

        ``vacuum_entity_id`` names whose catalog the room resolves against. It is
        required rather than defaulted because this runs on EVERY room save: a room
        finalized against the wrong brand's catalog is written to disk with values
        the device will not accept, and nothing downstream can tell that happened.
        """
        result = self._protected_room_config(room, vacuum_entity_id=vacuum_entity_id)
        _stored_profiles = self._data.get("profiles", {}).get("room_profiles", {})
        _resolved = resolve_room_profile_for_room(
            room_config=result,
            stored_profiles=_stored_profiles,
            catalog=self._catalog_for(vacuum_entity_id),
        )
        # Guarded: an unconditional write put path_type="" (or None) on rooms of every
        # brand, including ones with no path axis, before the declaration strip below
        # could see it. The strip still runs — this just stops the key being created
        # when nobody declared it, so a catalog-less call cannot mint one either.
        if _resolved.get("path_type"):
            result["path_type"] = _resolved["path_type"]
        else:
            result.pop("path_type", None)

        # A room carries only the axes its brand HAS. normalize_room_profile always
        # emits all nine ProfileRecord keys, and this pipeline writes the result back,
        # so without this a brand with no intensity axis got clean_intensity restored
        # as "" on every save — undoing the one-shot store repair one room at a time.
        # The discriminator is shared with that repair so the two cannot diverge again.
        _declared = declared_profile_fields(self._catalog_for(vacuum_entity_id))
        if _declared:
            for _field in VOCABULARY_FIELDS:
                if _field in result and _field not in _declared:
                    result.pop(_field, None)

        matched = self._match_profile_from_fields(result, vacuum_entity_id=vacuum_entity_id)
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

    def get_room_profiles(self, *, vacuum_entity_id: str | None = None) -> dict[str, Any]:
        """Return available room profiles — user-saved, plus a brand's built-ins.

        The saved library is global; BUILT-INS belong to a brand. Naming a vacuum
        is therefore what makes the built-in half answerable, and omitting it
        returns the saved library ALONE with ``built_ins_included: False`` rather
        than quietly serving whichever brand core used to carry. The caller gets a
        smaller answer, never somebody else's vocabulary.

        Optional rather than required only because this backs a shipped service
        that callers already invoke with no arguments; the flag is what keeps the
        no-argument answer honest instead of fail-soft.
        """
        self._data.setdefault("profiles", {})
        stored_profiles = self._data["profiles"].get("room_profiles", {})
        catalog = (
            self._catalog_for(vacuum_entity_id) if vacuum_entity_id else resolve_profile_catalog(None)
        )
        merged = merge_profile_dicts(
            built_in_profiles=get_default_room_profiles(catalog=catalog),
            stored_profiles=stored_profiles,
            catalog=catalog,
        )
        return {
            "profile_count": len(merged),
            "profiles": merged,
            "protected_profile_names": sorted(_PROTECTED_ROOM_PROFILE_NAMES),
            "built_ins_included": bool(vacuum_entity_id),
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
            catalog=self._catalog_for(vacuum_entity_id),
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
            },
            vacuum_entity_id=vacuum_entity_id,
        )
        clean_mode = str(protected.get("clean_mode", "")).lower()

        return {
            "clean_mode": protected.get("clean_mode"),
            "fan_speed": protected.get("fan_speed"),
            "water_level": protected.get("water_level"),
            "clean_intensity": protected.get("clean_intensity"),
            # ``or None`` so a brand with no path axis reads as null rather than "",
            # which is what the card's ``?? `` fallbacks are written against.
            "path_type": resolved.get("path_type") or None,
            "default_clean_passes": protected.get("clean_passes", 1),
            "default_edge_mopping": protected.get("edge_mopping", False),
            # ISSUE #48: the LAST private copy of the predicate. Expressed exactly as
            # _protected_room_config expresses it — same file, same question, and the
            # two are read off the same `protected` dict a few lines apart, so a
            # disagreement between them is the original #48 shape in miniature.
            #
            # Identical on every value that exists: the live store holds only
            # "Vacuum", "vacuum" and "Vacuum and mop", and the old substring test and
            # this agree on all three. They part only on a hypothetical brand mode
            # that merely MENTIONS mopping ("Mopping after sweeping"), and that
            # narrowing was already the sibling's choice — inherited here rather than
            # introduced, because the two answering differently is worse than either
            # answer. If that tolerance is ever wanted back it belongs in
            # is_mop_clean_mode, once, not in a fourth private copy.
            "mop_required": is_mop_clean_mode(clean_mode) or "wash" in clean_mode,
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

        # Custom profiles are authored WITHOUT mop_required (the editor does not expose
        # it), so derive it from the mode rather than letting normalize_room_profile
        # default it False — which mis-stored a deep-mop custom profile as not-mop.
        #
        # path_type is NOT derived here any more. This used to compute it from
        # clean_intensity ("deep" -> narrow, else wide), which is core deriving one
        # brand's axis from another brand's word — and the derivation was itself the
        # proof that the two are one axis under two names. A brand that genuinely has a
        # separate path axis declares it in its own profiles; nothing synthesizes it.
        # ISSUE #48, the fifth and last copy — and the worst-placed, because
        # get_effective_room_details forty lines up produces the SAME mop_required
        # field through the shared owner. Two producers of one field, disagreeing by
        # construction, in one file. They agree on every value that exists today,
        # which is exactly how the original defect stayed invisible: a substring test
        # and a canonical test give the same answer right up until a brand ships a
        # mode that only one of them recognises.
        _clean_mode_l = str(clean_mode).lower()
        _mop_required = is_mop_clean_mode(_clean_mode_l) or "wash" in _clean_mode_l
        profile = normalize_room_profile(
            {
                "label": label,
                "clean_mode": clean_mode,
                "fan_speed": fan_speed,
                "water_level": water_level,
                "clean_intensity": clean_intensity,
                "clean_passes": clean_passes,
                "edge_mopping": edge_mopping,
                "mop_required": _mop_required,
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
            # "" is "nobody said", the one value core owns. These read as harmless
            # last-resort defaults, but the room being saved belongs to SOME brand and
            # these are Eufy's words — a Roborock room reaching them was saved a suction
            # level its device does not accept.
            fan_speed=str(effective.get("fan_speed", room.get("fan_speed", ""))),
            water_level=str(effective.get("water_level", room.get("water_level", ""))),
            clean_intensity=coerce_clean_intensity(effective.get("clean_intensity", room.get("clean_intensity", ""))),
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

    def _find_rooms_referencing_profile(self, profile_name: str) -> list[dict[str, Any]]:
        """Every room, across every vacuum/map, whose profile_name references
        ``profile_name`` (RP-016/RF-20). delete/rename must know about these
        before mutating the store -- rename repoints them, delete refuses
        unless the caller says force=True.
        """
        referrers: list[dict[str, Any]] = []
        for vac, maps in self._data.get("maps", {}).items():
            if not isinstance(maps, dict):
                continue
            for map_id, bucket in maps.items():
                if not isinstance(bucket, dict):
                    continue
                for room_id, room in bucket.get("rooms", {}).items():
                    if isinstance(room, dict) and str(room.get("profile_name", "")) == profile_name:
                        referrers.append({
                            "vacuum_entity_id": vac,
                            "map_id": map_id,
                            "room_id": room_id,
                            "name": room.get("name"),
                        })
        return referrers

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

        repointed_rooms: list[dict[str, Any]] = []
        if target_name != normalized_name:
            del stored_profiles[normalized_name]
            # RP-016/RF-20: the store key just moved -- every room still
            # carrying the OLD name would silently orphan under it otherwise.
            for referrer in self._find_rooms_referencing_profile(normalized_name):
                room = (
                    self._data.get("maps", {})
                    .get(referrer["vacuum_entity_id"], {})
                    .get(referrer["map_id"], {})
                    .get("rooms", {})
                    .get(referrer["room_id"])
                )
                if isinstance(room, dict):
                    room["profile_name"] = target_name
                    repointed_rooms.append(referrer)
        stored_profiles[target_name] = updated_profile

        return {
            "renamed": True,
            "profile_name": target_name,
            "previous_profile_name": normalized_name,
            "profile": updated_profile,
            "repointed_rooms": repointed_rooms,
        }

    def delete_room_profile(self, *, profile_name: str, force: bool = False) -> dict[str, Any]:
        """Delete one existing custom room profile.

        RP-016/RF-20: refuses when rooms still reference this profile unless
        ``force=True`` -- an unconditional delete left the referring room's
        profile_name pointing at nothing (resolve_room_profile_for_room falls
        back silently, but the record itself is orphaned with no signal that
        happened). ``force`` deletes anyway and leaves referrers pointing at
        the now-gone name, same as the old unconditional behaviour -- but as
        an informed choice, not a silent default.
        """
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

        referrers = self._find_rooms_referencing_profile(normalized_name)
        if referrers and not force:
            return {
                "deleted": False,
                "reason": "has_referrers",
                "profile_name": normalized_name,
                "referring_rooms": referrers,
                "message": (
                    f"{len(referrers)} room(s) still use this profile -- "
                    "pass force=true to delete anyway."
                ),
            }

        stored_profiles = self._get_custom_room_profile_store()
        del stored_profiles[normalized_name]
        return {
            "deleted": True,
            "profile_name": normalized_name,
            "referring_rooms": referrers,
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
        profiles = self.get_room_profiles(vacuum_entity_id=vacuum_entity_id)["profiles"]
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
        # Coerce safely and drop anything that is not a real (non-negative) room id.
        # (The service schema already Coerces room_ids to int; this also makes a direct
        # caller robust — a bad id becomes -1 and is filtered, never admitted or raised.)
        normalized_ids = [rid for rid in (_safe_int(r, -1) for r in room_ids) if rid >= 0]

        # The adapter's own catalog fills any omitted profile field from ITS
        # normalize_defaults. There is no framework catalog behind this: an absent
        # declaration resolves empty rather than to Eufy's words.
        catalog = self._catalog_for(vacuum_entity_id)

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
                ),
                vacuum_entity_id=vacuum_entity_id,
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
            # A SNAPSHOT records what the room had. A room missing a field should
            # snapshot as absent, not as one brand's value invented on its behalf.
            "fan_speed": str(room.get("fan_speed", "")),
            "water_level": str(room.get("water_level", "")),
            "clean_intensity": coerce_clean_intensity(room.get("clean_intensity", "")),
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
        target_battery_percent:int clamped 1..100}), a wait ({type:'wait',
        wait_minutes:int clamped 1..1440}), or a zone ({type:'zone', zone_ids:[str,...]}
        naming saved zones cleaned together in one phase). Invalid/empty entries are dropped.

        room_group entries are coerced to well-formed ``{room_id:int, ...}`` dicts: a
        bare int is wrapped; an entry whose room_id doesn't parse to a positive int is
        dropped. A group left with no valid room is dropped entirely, so dispatch never
        sees an unparseable room_id. zone entries keep a de-duplicated, order-preserving
        list of non-empty string ids; existence + brand caps are enforced at dispatch
        (where the saved-zone store and the adapter's zone limit are known), so normalize
        stays brand-agnostic and shape-only — the same discipline room_id gets."""
        out, _dropped = ProfileManager._normalize_steps_reporting(steps)
        return ProfileManager._reject_unbracketed_break(out)

    @staticmethod
    def _normalize_steps_reporting(
        steps: Any,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Normalize, and REPORT what was discarded. Returns ``(kept, dropped)``.

        RP-021b / #13:A5-RUNPROF-4. The tolerant behaviour below is correct for
        READS and wrong for WRITES, and until now there was only one path for
        both. A read must never fail to start a legacy profile, so unknown or
        malformed steps are skipped. A WRITE that silently skips them tells a
        YAML author `saved: True` for a profile that quietly lost its charge
        stop — the robot then runs the whole sequence in one go and can strand
        mid-run instead of docking to charge.

        So the drop list is now returned rather than thrown away.
        ``normalize_run_profile_steps`` ignores it (reads stay tolerant);
        ``set_run_profile_steps`` refuses on it (writes are strict). One
        implementation, two policies — rather than a second normalizer that can
        disagree with this one.
        """
        out: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []

        def _drop(index: int, reason: str, step: Any) -> None:
            dropped.append({"index": index, "reason": reason, "step": step})

        for index, step in enumerate(steps if isinstance(steps, list) else []):
            if not isinstance(step, dict):
                _drop(index, "not_an_object", step)
                continue
            stype = str(step.get("type") or "").strip().lower()
            if stype == "room_group":
                rooms = step.get("rooms")
                if not isinstance(rooms, list):
                    _drop(index, "rooms_not_a_list", step)
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
                    if len(clean_rooms) != len(rooms):
                        _drop(index, "some_room_ids_invalid", step)
                else:
                    _drop(index, "no_valid_room_ids", step)
            elif stype == "charge_wait":
                try:
                    tgt = int(step.get("target_battery_percent"))
                except (TypeError, ValueError):
                    _drop(index, "target_battery_percent_missing_or_unparseable", step)
                    continue
                clamped = max(1, min(tgt, 100))
                out.append({"type": "charge_wait", "target_battery_percent": clamped})
                if clamped != tgt:
                    # A silently clamped 250 -> 100 is a caller error too: the
                    # author asked for something impossible and got something else.
                    _drop(index, f"target_battery_percent_out_of_range_{tgt}", step)
            elif stype == "wait":
                try:
                    mins = int(step.get("wait_minutes"))
                except (TypeError, ValueError):
                    _drop(index, "wait_minutes_missing_or_unparseable", step)
                    continue
                clamped = max(1, min(mins, 1440))
                out.append({"type": "wait", "wait_minutes": clamped})
                if clamped != mins:
                    _drop(index, f"wait_minutes_out_of_range_{mins}", step)
            elif stype == "zone":
                raw_ids = step.get("zone_ids")
                if not isinstance(raw_ids, list):
                    _drop(index, "zone_ids_not_a_list", step)
                    continue
                clean_ids: list[str] = []
                for z in raw_ids:
                    zid = str(z).strip()
                    if zid and zid not in clean_ids:
                        clean_ids.append(zid)
                if clean_ids:
                    out.append({"type": "zone", "zone_ids": clean_ids})
                else:
                    _drop(index, "no_valid_zone_ids", step)
            else:
                _drop(index, f"unknown_step_type_{stype or '<missing>'}", step)
        return out, dropped

    @staticmethod
    def _reject_unbracketed_break(out: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Q17: a leading/trailing charge_wait or wait has nothing to bracket, so it can
        # never run — it is unsupported, not silently droppable (RP-021a clause 1). A
        # single-entry list (every ``queue_breaks`` call site normalizes one already-
        # positioned break in isolation) is never "leading" or "trailing" in this sense,
        # so the check only applies once there is a real sequence to be first/last in.
        if len(out) > 1:
            if out[0].get("type") in ("charge_wait", "wait"):
                raise ServiceValidationError(
                    "A run profile cannot start with a charge/wait break",
                    translation_domain=DOMAIN,
                    translation_key="leading_break_unsupported",
                )
            if out[-1].get("type") in ("charge_wait", "wait"):
                raise ServiceValidationError(
                    "A run profile cannot end with a charge/wait break",
                    translation_domain=DOMAIN,
                    translation_key="trailing_break_unsupported",
                )
        return out

    @staticmethod
    def run_profile_steps(profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Return a profile's ordered steps, back-filling a legacy rooms-only profile
        as a single room_group step. Sequencing intent (room grouping + charge
        boundaries) lives in the steps list; old profiles carried only ``rooms``."""
        steps = profile.get("steps") if isinstance(profile, dict) else None
        if isinstance(steps, list) and steps:
            try:
                return ProfileManager.normalize_run_profile_steps(steps)
            except ServiceValidationError:
                # A profile saved before Q17's leading/trailing-break rejection existed.
                # Reading it must never fail to start — strip the unsupported break(s)
                # loudly and normalize what remains.
                def _is_break(entry: Any) -> bool:
                    return (
                        isinstance(entry, dict)
                        and str(entry.get("type", "")).lower() in ("charge_wait", "wait")
                    )

                trimmed = list(steps)
                while trimmed and _is_break(trimmed[0]):
                    _LOGGER.info(
                        "Dropping legacy leading break from a stored run profile "
                        "(unsupported since Q17): %r", trimmed.pop(0),
                    )
                while trimmed and _is_break(trimmed[-1]):
                    _LOGGER.info(
                        "Dropping legacy trailing break from a stored run profile "
                        "(unsupported since Q17): %r", trimmed.pop(),
                    )
                return ProfileManager.normalize_run_profile_steps(trimmed)
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
            # ISSUE #50. Absent on every profile saved before this key existed, and the
            # `.get(..., False)` default is deliberately the pre-existing behaviour: a
            # stored profile that predates the flag keeps path-optimised dispatch, so
            # nothing changes for anyone until they tick the box.
            "strict_order": bool(profile.get("strict_order", False)),
            "steps": steps,
            "has_charge_steps": any(s.get("type") == "charge_wait" for s in steps),
            # has_stops == "this is a SEQUENCED run, not a plain queue": any break step
            # (charge_wait / wait / zone) OR more than one room_group. DISTINCT from the
            # charge-only has_charge_steps. The frontend gates stepped preview/routing
            # on has_stops. (SHARED CONTRACT with the frontend lane.)
            # The step-type tuple MUST mirror the stepped-path gates at
            # profiles/manager.py:1308, planning/run_plan.py:1348/1353 and
            # core/manager.py:1647 — "zone" was added to those and missed here.
            "has_stops": (
                plan_requires_stepped_execution(steps)
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
        strict_order: bool = False,
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
            "strict_order": bool(strict_order),
            "rooms": enabled_rooms,
            "created_at": now,
            "updated_at": now,
        }
        # Capture the current queue's WHOLE stepped plan (room groups + charge/wait breaks +
        # zones) so a composed one-off run can be saved intact, not flattened to a bare room
        # clean. Flat queues stay rooms-only (the steps back-fill reconstructs a single
        # room_group at apply); the room_groups are id-only because apply restores the saved
        # rooms' settings to the entities, and the run reads settings from there + sequence
        # from steps.
        queue = self._manager.get_queue_steps(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id)
        )
        if queue.get("has_breaks"):
            library[profile_id]["steps"] = queue.get("steps") or []
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
        try:
            # RP-021b / #13:A5-RUNPROF-4: the WRITE path is strict. Reads stay
            # tolerant (a legacy profile must never fail to start), but a save
            # that silently discards a step returns `saved: True` for a profile
            # that has quietly lost its charge stop — and the robot then runs the
            # whole sequence in one go and can strand mid-run. Refuse instead,
            # naming every rejected step so a YAML author can see WHICH line was
            # wrong rather than diffing the saved profile against what they wrote.
            normalized, rejected = self._normalize_steps_reporting(steps)
            normalized = self._reject_unbracketed_break(normalized)
        except ServiceValidationError as err:
            return {"vacuum_entity_id": vacuum_entity_id, "map_id": str(map_id),
                    "saved": False, "reason": err.translation_key, "profile_id": profile_id}
        if rejected:
            return {"vacuum_entity_id": vacuum_entity_id, "map_id": str(map_id),
                    "saved": False, "reason": "invalid_steps", "profile_id": profile_id,
                    "rejected_steps": rejected}
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
        strict_order: bool | None = None,
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
        # Same snapshot save_run_profile takes -- see the "steps" key below for why an
        # overwrite re-snapshots rather than blanking.
        _overwrite_queue = self._manager.get_queue_steps(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id)
        )
        _overwrite_steps = (
            (_overwrite_queue.get("steps") or [])
            if _overwrite_queue.get("has_breaks")
            else []
        )
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
            "strict_order": bool(
                existing.get("strict_order", False) if strict_order is None else strict_order
            ),
            "rooms": enabled_rooms,
            # RE-SNAPSHOT, don't blank. Overwrite means "this profile now IS the current
            # queue", so its steps must become the CURRENT queue's steps -- exactly what
            # save_run_profile captures above.
            #
            # This used to be a bare `"steps": []`. The reasoning was half right: the
            # {**existing} spread would indeed carry the STALE steps forward, and
            # run_profile_steps prefers a non-empty steps list, so the old rooms would be
            # cleaned and the new ones ignored. But blanking fixes that by destroying the
            # sequence outright -- and overwrite is reachable from the card's ONLY Save
            # button, so a save whose whole intent was a rename or an expose_as_button
            # toggle silently flattened "Downstairs, wait 30 min, then Upstairs" into one
            # pass. No charge stop, no wait, zone steps never cleaned, async_save commits
            # it, and the editor opens such a profile COLLAPSED
            # (src/state/run-profiles.js gates on has_charge_steps, not has_stops), so the
            # user never saw the steps they lost.
            #
            # The queue's own sequence is the right answer for both cases: stepped queue ->
            # its breaks are preserved; flat queue -> [] and run_profile_steps back-fills a
            # single room_group of the NEW rooms, which is what the old comment wanted.
            "steps": _overwrite_steps,
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

        # RP-031/RF-05a: resolve the profile's rooms against the CURRENT map
        # FIRST, without mutating anything -- a profile whose every referenced
        # room has since been deleted/renumbered (a re-segment) must refuse
        # without touching the map's pre-existing selection. The wipe below
        # only runs once at least one room is confirmed to apply; it used to
        # run unconditionally before this resolution, so a fully-failed apply
        # still destroyed the user's prior selection with no rollback.
        applied_room_ids: list[int] = []
        missing_room_ids: list[int] = []
        updates: dict[str, dict] = {}
        # Enable the rooms named by the profile's STEPS (room_group steps, in order).
        # Legacy rooms-only profiles are byte-identical — run_profile_steps back-fills
        # a single room_group of profile["rooms"]. Charge_wait steps carry no rooms.
        _profile_rooms = [
            r for step in self.run_profile_steps(profile) if step.get("type") == "room_group"
            for r in step.get("rooms", [])
        ]
        # RP-021b / #8:A4-PP-RP-1: a STEPPED profile's room_group entries are
        # id-only -- bare {"room_id": N}, by design (the save-side comment above
        # says so: apply restores the saved rooms' SETTINGS, steps carry only the
        # sequence). But the reads below fell straight through to current_room,
        # so every saved setting was silently replaced by the room's live state.
        #
        # Save 'Nightly' = Kitchen+Bath on mop/High water, charge to 90%, then
        # Bedrooms. Later switch the Kitchen to vacuum-only for a quick pass.
        # Pressing Run Nightly restored the right rooms in the right order with
        # the charge break -- and ran the Kitchen dry. The settings were on disk
        # the whole time, at profile["rooms"], simply never read.
        #
        # Flat/legacy profiles were never affected: run_profile_steps back-fills
        # their group FROM profile["rooms"], which already carries full settings.
        _saved_by_id: dict[int, dict] = {}
        for _saved in profile.get("rooms") or []:
            if isinstance(_saved, dict):
                _sid = _safe_int(_saved.get("room_id"), -1)
                if _sid >= 0:
                    _saved_by_id.setdefault(_sid, _saved)
        _unsnapshotted: list[int] = []

        # Last-resort field values come from the BRAND's declared custom_template,
        # never from literals here. These read as harmless — the live room almost
        # always carries every field — but "Max" and "Quick" are Eufy's words, and
        # a Roborock room reaching this line was written a suction level its device
        # does not accept. The template is the adapter's own declaration of what an
        # unspecified field means; a brand that declares none supplies None, and
        # normalization downstream sees an absent field rather than a foreign one.
        _catalog = self._catalog_for(vacuum_entity_id)
        _template = _catalog.get("custom_template") or {}

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

            # Three layers, most specific first: the STEP's own field (a per-group
            # override, e.g. vacuum this pass then mop the next) beats the
            # profile's saved snapshot, which beats the room's CURRENT live
            # state. Only the last of those is "whatever the room happens to be
            # set to today", and it must be the last resort, not the first.
            _saved_room = _saved_by_id.get(room_id) or {}
            if not _saved_room:
                _unsnapshotted.append(room_id)

            def _field(name: str, fallback, _step=room_snapshot,
                       _saved=_saved_room, _live=current_room):
                if name in _step:
                    return _step[name]
                if name in _saved:
                    return _saved[name]
                return _live.get(name, fallback)

            updated_room = self._finalize_room_update(
                {
                    **current_room,
                    "enabled": True,
                    "order": index,
                    "profile_name": str(
                        _field("profile_name", _catalog.get("default_profile"))
                    ),
                    "clean_mode": str(_field("clean_mode", _template.get("clean_mode"))),
                    "fan_speed": str(_field("fan_speed", _template.get("fan_speed"))),
                    "water_level": str(_field("water_level", _template.get("water_level"))),
                    "clean_intensity": coerce_clean_intensity(
                        _field("clean_intensity", _template.get("clean_intensity"))
                    ),
                    "clean_passes": int(_field("clean_passes", 1)),
                    "edge_mopping": bool(_field("edge_mopping", False)),
                },
                vacuum_entity_id=vacuum_entity_id,
            )
            updates[room_key] = updated_room
            applied_room_ids.append(room_id)

        if _unsnapshotted:
            # The packet's stop_condition: a profile saved before settings were
            # snapshotted has nothing to restore for these rooms, so they keep
            # their CURRENT settings. Say so rather than inventing values -- the
            # user gets the right rooms in the right order with today's settings,
            # which is recoverable; a fabricated "saved" setting is not.
            _LOGGER.info(
                "apply_run_profile %s: %d room(s) have no saved settings snapshot "
                "(%s) -- applying their CURRENT settings. Re-save the profile to "
                "capture them.",
                profile_id, len(_unsnapshotted),
                ", ".join(str(r) for r in _unsnapshotted),
            )

        if not applied_room_ids:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "map_id": str(map_id),
                "applied": False,
                "reason": "no_matching_rooms",
                "profile_id": profile_id,
                "profile": profile,
                "applied_room_ids": applied_room_ids,
                "missing_room_ids": missing_room_ids,
            }

        # Authorized: at least one profile room resolved against the current map.
        # Wipe every room's enabled flag now, then layer the resolved updates on
        # top — an unmatched room is left disabled rather than stuck at whatever
        # it was before, same end state as before this fix, just ordered so a
        # REFUSAL can never reach this point.
        for room_key, room_data in list(rooms.items()):
            if not isinstance(room_data, dict):
                continue
            rooms[room_key] = {**room_data, "enabled": False}
        rooms.update(updates)

        map_bucket["rooms"] = rooms
        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)

        # RP-021c / #8:A4-PP-RP-4: apply the profile's STRUCTURE, not only its rooms.
        #
        # This method used to enable the right rooms in the right ORDER and stop
        # there, leaving no backend record that the profile was stepped. The
        # breaks live in a different backing (map_bucket["queue_breaks"]) which
        # nothing here wrote, so a plain Start -- from a reloaded dashboard, a
        # second tab, a phone, or an automation that calls apply_run_profile then
        # start_cleaning -- ran the profile FLAT. The charge-to-90% break never
        # happened and the robot died mid-run; a wait was skipped; a zone step was
        # never cleaned at all. Silent in both directions: nothing reported that
        # the structure had been dropped.
        #
        # Derive the breaks from the profile's own steps and write them through
        # set_queue_breaks, the single replace-ALL primitive. Replace-all is doing
        # double duty, and is why this is one fix rather than two: a FLAT profile
        # derives an empty list, which WIPES whatever breaks the map was carrying
        # from an earlier composition. That was the finding's other half -- a
        # leftover charge break landing after an arbitrary room of a profile that
        # never asked for one.
        #
        # after_index counts only rooms that actually RESOLVED against this map, so
        # a break stays anchored to the room it followed even when the profile
        # references rooms a re-segment has since removed. set_queue_breaks clamps
        # to an interior slot and drops breaks entirely below two rooms, which is
        # also where a leading/trailing break resolves -- unsupported per RP-021a
        # (Q17), and handled there consistently rather than by a second rule here.
        _derived_breaks: list[dict[str, Any]] = []
        _applied_set = set(applied_room_ids)
        _rooms_emitted = 0
        for _step in self.run_profile_steps(profile):
            if not isinstance(_step, dict):
                continue
            if str(_step.get("type") or "").strip().lower() == "room_group":
                _rooms_emitted += sum(
                    1 for _r in (_step.get("rooms") or [])
                    if isinstance(_r, dict)
                    and _safe_int(_r.get("room_id"), -1) in _applied_set
                )
                continue
            if _rooms_emitted >= 1:
                _derived_breaks.append({**_step, "after_index": _rooms_emitted})

        self._manager.set_queue_breaks(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
            breaks=_derived_breaks,
        )

        # The TAG. The breaks above are what make a plain Start behave; this is the
        # provenance that makes it explicable -- which profile the live queue came
        # from, and whether it carried structure. Without it, "why does Start pause
        # to charge?" has no answer visible in stored state, and a queue composed
        # by hand is indistinguishable from one a profile applied.
        map_bucket["queue_source"] = {
            "profile_id": profile_id,
            "stepped": bool(_derived_breaks),
            "applied_at": utc_now_iso(),
        }

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
            "applied": True,
            "profile_id": profile_id,
            "profile": profile,
            "applied_room_ids": applied_room_ids,
            "missing_room_ids": missing_room_ids,
            # RP-021b / #8:A4-PP-RP-1: rooms the profile had no saved settings
            # snapshot for, so they kept their CURRENT settings. Empty for any
            # profile saved since settings were snapshotted, and for every
            # legacy rooms-only profile (whose group IS profile["rooms"]).
            # Reported rather than silent: "the right rooms ran with the wrong
            # settings" is otherwise indistinguishable from a clean apply.
            "unsnapshotted_room_ids": _unsnapshotted,
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
        strict_order: bool | None = None,
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

        # Stash the profile's step sequence so the plan builder materializes a multi-phase job
        # (e.g. [clean, charge_wait, clean] or [clean, zone]). Consumed (popped) in
        # run_plan._build_effective_start_plan; absent -> normal atomic dispatch. The gate MUST
        # mirror run_plan's stepped-path gate (charge_wait/wait/zone) — a zone is a real clean
        # step, so a rooms->zone profile fired here (the automation entry point) has to stash or
        # apply_run_profile, which never writes queue_breaks, would drop the zone to a flat clean.
        _prof = self._get_saved_run_profile_store(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
        ).get(profile_id, {})
        _prof_steps = self.run_profile_steps(_prof)
        # ISSUE #50. The profile's saved room ORDER was silently discarded on a
        # path-optimising brand (Roborock declares honors_clean_order: False), because
        # strict_order reached start_selected_rooms only from the direct service and never
        # from a profile — so the button entity, which carries no service data at all,
        # could not opt in by any route. The stored flag IS the button's only opt-in.
        # An explicit argument still wins, so a service call can override a saved profile
        # in either direction without editing it.
        _strict_order = (
            bool(_prof.get("strict_order", False))
            if strict_order is None
            else bool(strict_order)
        )
        if any(
            step_requires_stepped_execution(s) for s in _prof_steps
        ):
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
            strict_order=_strict_order,
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
