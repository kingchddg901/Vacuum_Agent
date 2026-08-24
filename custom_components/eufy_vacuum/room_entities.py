"""Shared room entity base classes for Vacuum Agent."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import Entity

from .adapters.registry import get_adapter_config
from .const import DOMAIN
from .entity_helpers import build_vacuum_device_info, make_room_unique_id

_LOGGER = logging.getLogger(__name__)


class EufyVacuumRoomEntity(Entity):
    """Base entity for a managed room."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator_key: str,
        vacuum_entity_id: str,
        map_id: str,
        room_id: int,
        room_data: dict[str, Any],
        unique_suffix: str,
    ) -> None:
        """Initialize room entity."""
        self._coordinator_key = coordinator_key
        self._vacuum_entity_id = vacuum_entity_id
        self._map_id = str(map_id)
        self._room_id = int(room_id)
        self._room_name = str(room_data.get("name", f"Room {room_id}"))
        self._room_slug = room_data.get("slug")

        self._attr_unique_id = make_room_unique_id(
            vacuum_entity_id=vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
            suffix=unique_suffix,
        )
        # With has_entity_name=True, the device name is prepended by HA.
        # Each room entity subclass declares _attr_translation_key; the room
        # name is injected via _attr_translation_placeholders so the label
        # suffix stays in translation files while the user-defined room name
        # stays dynamic.
        self._attr_device_info = build_vacuum_device_info(vacuum_entity_id)
        self._attr_translation_placeholders = {"room": self._room_name}
        # Tracks previous availability so log-when-unavailable fires only once
        # per state transition, not on every state write.
        self._was_available: bool | None = None

    @property
    def manager(self):
        """Return integration manager."""
        return self.hass.data[DOMAIN]["runtime"]

    # RP-009 (REVIEW D2): ownership is answered by ATTRIBUTES, never by parsing
    # the unique_id (a non-injective join — see entity_helpers.make_room_unique_id).
    # Read-only accessors so entity_helpers.entity_belongs_to consumes the public
    # surface instead of reaching for the underscore attrs.

    @property
    def vacuum_entity_id(self) -> str:
        """The owning vacuum's entity_id (ownership attribute)."""
        return self._vacuum_entity_id

    @property
    def map_id(self) -> str:
        """The owning map id (ownership attribute)."""
        return self._map_id

    @property
    def room_name(self) -> str:
        """This entity's room display name, as of its last (re)build.

        SN-4: a freshly-built entity's name comes from room storage via
        __init__ / _attr_translation_placeholders; a rename sync compares
        this against a freshly built sibling to detect a rename rather than
        reaching for the underscore attribute directly.
        """
        return self._room_name

    def _get_room_data(self) -> dict[str, Any]:
        """Return current room data from manager storage."""
        map_bucket = (
            self.manager.data.get("maps", {})
            .get(self._vacuum_entity_id, {})
            .get(self._map_id, {})
        )
        rooms = map_bucket.get("rooms", {})
        return rooms.get(str(self._room_id), {})

    def _refuse_room_write(self, reason: str) -> None:
        """Surface a REFUSED room write on the control the user just pressed.

        RP-002/RF-01 (IN5BRA39): a refusal is not a success. Both writers below
        hand back a payload that used to be DISCARDED, after which async_save()
        and async_write_ha_state() ran unconditionally — so a room deleted
        between the state write and the button press gave the user a switch that
        visibly moved and a store that never changed. An entity has no response
        channel the way the services do (both `update_room_fields` and
        `apply_room_profile` are registered supports_response=True), so an
        exception is the only way the person who pressed it finds out.

        ``reason`` is the callee's slug VERBATIM — that is the string that gets
        pasted into an issue, so it is not prettified on the way out.
        """
        raise ServiceValidationError(
            f"Could not update {self._room_name}: {reason}",
            translation_domain=DOMAIN,
            translation_key="room_update_refused",
            translation_placeholders={"room": self._room_name, "reason": reason},
        )

    async def _async_update_room(self, updates: dict[str, Any]) -> None:
        """Apply field updates to this room, persist storage, and write HA state."""
        profile_name = updates.get("profile_name")
        if isinstance(profile_name, str) and len(updates) == 1:
            result = self.manager.apply_room_profile(
                vacuum_entity_id=self._vacuum_entity_id,
                map_id=self._map_id,
                room_ids=[self._room_id],
                profile_name=profile_name,
            )
            # apply_room_profile carries NO `ok` key on ANY path, so there is
            # nothing here that reads as a verdict. An unknown profile comes back
            # with error="profile_not_found"; a room that vanished between the
            # state write and this press is `continue`d over and comes back
            # SUCCESS-SHAPED — updated_room_ids [], room_count 0, and no error key
            # at all. The one claim both paths make honestly is whether THIS room
            # id came back applied, so that is the verdict. Reading `ok` here
            # would wave the vanished-room case straight through, which is the
            # half of this defect that actually has a user pressing a button.
            applied = result.get("updated_room_ids") if isinstance(result, dict) else None
            if not isinstance(applied, list) or self._room_id not in applied:
                # "not_applied" is OURS, used only when the payload named no
                # error — never a slug invented on the callee's behalf.
                self._refuse_room_write(
                    (result.get("error") if isinstance(result, dict) else None)
                    or "not_applied"
                )
            await self.manager.async_save()
            self.async_write_ha_state()
            return

        managed_field_names = {
            "enabled",
            "clean_mode",
            "fan_speed",
            "water_level",
            "clean_intensity",
            "clean_passes",
            "edge_mopping",
        }
        managed_updates = {
            key: value
            for key, value in updates.items()
            if key in managed_field_names
        }
        remaining_updates = {
            key: value
            for key, value in updates.items()
            if key not in managed_field_names
        }
        if managed_updates:
            result = self.manager.update_room_fields(
                vacuum_entity_id=self._vacuum_entity_id,
                map_id=self._map_id,
                room_id=self._room_id,
                **managed_updates,
            )
            # This callee DOES answer `ok` on every path, and from this call site
            # exactly ONE refusal is reachable: `room_not_found`. The kwargs above
            # are the managed subset only, and the other two refusals both need an
            # access-graph field (`no_dock_room` and `invalid_access_graph` are
            # gated on grants_access_to) that can never arrive here. One refusal
            # path, so one branch — three would read as covered and never fire.
            if not (isinstance(result, dict) and result.get("ok") is True):
                self._refuse_room_write(
                    (result.get("error") if isinstance(result, dict) else None)
                    or "not_applied"
                )
            if not remaining_updates:
                await self.manager.async_save()
                self.async_write_ha_state()
                return
            # EP-7: the call carried BOTH managed and unmanaged fields (e.g. an
            # "enabled"+"color" batch), so anything outside `managed_field_names`
            # must still reach the generic merge below instead of being silently
            # dropped by an early return.
            #
            # ⚠ was: "update_room_fields only understands the managed subset above."
            # FALSE (ledger D4). The callee's signature
            # (`core/manager.py::EufyVacuumManager.update_room_fields`) also accepts
            # `color`, `is_dock_room`, `is_transition`, `grants_access_to` and
            # `rules` — `color` being this comment's own example of a field it
            # supposedly could not take. The true statement is narrower and is about
            # THIS CALL SITE, not the callee: `managed_field_names` above is a
            # hand-maintained copy that has drifted from that signature, so this call
            # site only PASSES the managed subset, and everything else must be routed
            # to the merge. Splitting here is therefore a choice, not a constraint.

        map_bucket = (
            self.manager.data.setdefault("maps", {})
            .setdefault(self._vacuum_entity_id, {})
            .setdefault(self._map_id, {})
        )
        rooms = map_bucket.setdefault("rooms", {})
        room_key = str(self._room_id)

        current = dict(rooms.get(room_key, {}))
        current.update(remaining_updates if managed_updates else updates)

        # The other two writers this method can reach BOTH finalize before they
        # store (apply_room_profile, update_room_fields); this merge did not, so
        # which branch a field happened to fall into decided whether the carpet/mop
        # invariants applied to it at all. `floor_type` is a protection INPUT
        # (profiles/manager.py::_protected_room_config) and is deliberately not a
        # managed field, so it lands in exactly this branch: a room switched to
        # carpet here kept its mop mode, its water level and its edge mopping, and
        # the store then read as a carpet room the planner was clear to send out
        # wet. Finalizing also keeps profile_name honest, which the raw merge left
        # stamped with whatever preset the room matched BEFORE the edit.
        rooms[room_key] = self.manager._finalize_room_update(
            current, vacuum_entity_id=self._vacuum_entity_id
        )

        from .rooms.room_manager import build_room_selection_summary

        map_bucket["summary"] = build_room_selection_summary(managed_rooms=rooms)
        self.manager._refresh_room_derived_state(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
        )
        self.manager._notify_rooms_updated(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
        )

        await self.manager.async_save()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return whether entity is available.

        Logs once on each unavailable / available-again transition so
        operators can diagnose room-data gaps without log spam.
        """
        now_available = bool(self._get_room_data())
        if self._was_available is not None and self._was_available != now_available:
            if not now_available:
                _LOGGER.warning(
                    "Room entity %s/%s/room_%s is unavailable",
                    self._vacuum_entity_id,
                    self._map_id,
                    self._room_id,
                )
            else:
                _LOGGER.debug(  # pragma: no cover
                    "Room entity %s/%s/room_%s is available again",
                    self._vacuum_entity_id,
                    self._map_id,
                    self._room_id,
                )
        self._was_available = now_available
        return now_available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return common room attributes."""
        room = self._get_room_data()

        raw_grants = room.get("grants_access_to", [])
        grants_access_to = (
            [str(v) for v in raw_grants]
            if isinstance(raw_grants, list)
            else []
        )

        effective = self.manager.get_effective_room_details(
            vacuum_entity_id=self._vacuum_entity_id,
            map_id=self._map_id,
            room_id=self._room_id,
        ) or {}

        # Adapter-declared dropdown vocabularies. Carried on the room
        # entity so the standalone Eufy Room Card (which reads HA state
        # directly and has no service-layer access) can populate its
        # mode/speed/water/intensity pickers from the adapter without
        # probing upstream brand integration entities. Each list is
        # `[{value, label}, ...]`; absent role keys become empty lists.
        _adapter_vocab = (
            get_adapter_config(self._vacuum_entity_id) or {}
        ).get("vocabulary", {}) or {}

        # Surface the last-cleaned timestamp from room_history on every
        # room entity so the card can render a "2d ago" pill on each
        # room card without an extra service round-trip. data shape:
        # data["room_history"][vacuum][map_id][room_id]["last_cleaned_at"]
        history_entry = (
            self.manager.data.get("room_history", {})
            .get(self._vacuum_entity_id, {})
            .get(str(self._map_id), {})
            .get(str(self._room_id), {})
        )
        if not isinstance(history_entry, dict):
            history_entry = {}

        return {
            "vacuum_entity_id": self._vacuum_entity_id,
            "map_id": self._map_id,
            "room_id": self._room_id,
            "room_name": room.get("name", self._room_name),
            "slug": room.get("slug", self._room_slug),
            "last_cleaned_at": history_entry.get("last_cleaned_at"),
            "last_vacuumed_at": history_entry.get("last_vacuumed_at"),
            "last_mopped_at": history_entry.get("last_mopped_at"),
            "last_job_mode": history_entry.get("last_job_mode"),
            "profile_name": room.get("profile_name", "vacuum_quick"),
            "floor_type": room.get("floor_type", "hardwood"),
            "clean_mode": effective.get("clean_mode"),
            "fan_speed": effective.get("fan_speed"),
            "water_level": effective.get("water_level"),
            "clean_intensity": effective.get("clean_intensity"),
            "clean_passes": effective.get("default_clean_passes", room.get("clean_passes", 1)),
            "edge_mopping": effective.get("default_edge_mopping", room.get("edge_mopping", False)),
            "carpet": str(room.get("floor_type", "")).startswith("carpet"),
            "order": room.get("order", 0),
            "enabled": room.get("enabled", False),
            "color": room.get("color"),  # per-room map fill override ("#rrggbb" or None)
            "is_dock_room": bool(room.get("is_dock_room", False)),
            "grants_access_to": grants_access_to,
            "rules": room.get("rules", []),
            "integration": self._coordinator_key,
            "clean_mode_options": _adapter_vocab.get("clean_mode_options") or [],
            "fan_speed_options": _adapter_vocab.get("fan_speed_options") or [],
            "water_level_options": _adapter_vocab.get("water_level_options") or [],
            "clean_intensity_options": _adapter_vocab.get("clean_intensity_options") or [],
        }
