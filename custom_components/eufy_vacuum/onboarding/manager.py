"""OnboardingManager — per-map room-discovery and floor-type confirmation state.

Owns:
- data["onboarding"] sub-tree (get/set helpers).
- get_onboarding_state: computes completeness from stored flags + live map data.
- mark_rooms_discovered: stamps rooms_discovered = True for one map.
- confirm_floor_type: records one room's floor type as user-confirmed.
- check_for_new_rooms: detects new segments in the vacuum entity attributes.
- get_rooms_onboarding_summary: aggregates onboarding state across all maps.
- reset_onboarding: clears onboarding state for one map.

Receives data (the integration root data dict) and hass (HomeAssistant instance).
Does not need a reference to the parent EufyVacuumManager.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config
from ..core.vacuum_identity import is_real_vacuum

_LOGGER = logging.getLogger(__name__)


def _default_map_onboarding() -> dict[str, Any]:
    """Fresh onboarding-state record for one vacuum/map (DR-ONB-4).

    Single source for the 5-key shape -- _get_map_onboarding's lazy-create
    and reset_onboarding's explicit reset used to be two hand-maintained
    copies of this same vocabulary, so a key added to one silently missed
    the other.
    """
    return {
        "rooms_discovered": False,
        "floor_types_confirmed": {},
        "room_count_at_last_check": 0,
        "discovery_notified": False,
        "rebuild_notified": False,
    }


class OnboardingManager:
    """Owns room-discovery and floor-type onboarding state per vacuum/map."""

    def __init__(
        self,
        data: dict[str, Any],
        hass: HomeAssistant,
    ) -> None:
        """Initialise with the integration root data dict and hass instance.

        Args:
            data: Integration root data dict — reads/writes data["onboarding"].
            hass: HomeAssistant instance (to read vacuum entity attributes).
        """
        self._data = data
        self._hass = hass
        self._data.setdefault("onboarding", {})

    # ------------------------------------------------------------------
    # anchor: BN3BEJTH
    # Private helpers
    # ------------------------------------------------------------------

    def _get_onboarding_data(self) -> dict:
        """Return root onboarding dict."""
        self._data.setdefault("onboarding", {})
        return self._data["onboarding"]

    def _get_map_onboarding(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        create: bool = True,
    ) -> dict:
        """Return onboarding state for one vacuum/map.

        ``create=False`` returns an EPHEMERAL default instead of persisting one — for
        callers that are only asking a question. A status query used to create the
        record it was asking about, so merely enquiring about a vacuum brought it into
        existence: a live install carried onboarding["vacuum.your_vacuum"], the CARD'S
        OWN PLACEHOLDER (src/main.js), persisted because something asked about it.

        Creation is additionally refused for an id this install has no vacuum for, so a
        typo in a WRITE cannot leave a permanent record either. The caller still gets a
        usable dict; it just never reaches the store.
        """
        ob = self._get_onboarding_data()
        existing = ob.get(vacuum_entity_id, {}).get(str(map_id))
        if existing is not None:
            return existing

        if not create or not is_real_vacuum(self._hass, self._data, vacuum_entity_id):
            if create:
                _LOGGER.warning(
                    "onboarding: refusing to create state for %r — no such vacuum "
                    "entity. Nothing is persisted for ids this install does not have.",
                    vacuum_entity_id,
                )
            return _default_map_onboarding()

        ob.setdefault(vacuum_entity_id, {})
        ob[vacuum_entity_id].setdefault(str(map_id), _default_map_onboarding())
        return ob[vacuum_entity_id][str(map_id)]

    # ------------------------------------------------------------------
    # anchor: BNW9AAN5
    # Public API
    # ------------------------------------------------------------------

    def get_onboarding_state(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Return full onboarding status for one vacuum/map. Creates nothing."""
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            create=False,
        )

        map_bucket = (
            self._data.get("maps", {})
            .get(vacuum_entity_id, {})
            .get(str(map_id), {})
        )
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
            self._data.get("maps", {})
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

    def remap_confirmed_floor_types(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        id_remap: dict[int, int],
    ) -> None:
        """Carry floor-type confirmations onto re-segmented room ids after a reconcile
        migrate. Confirmations are keyed by room id; without re-keying through the
        old->new id_remap, every renumbered-but-already-confirmed room reads as needing
        confirmation and the start gate blocks cleaning with onboarding_required until
        the user re-confirms each one. No-op when id_remap is empty (no renumbering).

        CONTRACT, independent of dict iteration order: for every (old, new) in id_remap,
        ``after[str(new)]`` is True IF ``before[str(old)]`` was True; a key never named
        as an old_id survives verbatim; a key named only as an old_id is dropped.

        ⚠ NOT "iff" — this said "iff" until 2026-08-24 and that is false (C28). The
        rebuild filters SOURCE keys only (``if key not in remap``), and the loop only
        ever WRITES True, never False. So a pre-existing confirmed key that is a remap
        TARGET but is never itself an old_id survives even when the room migrating onto
        it was unconfirmed: ``before={'27': True}`` with ``id_remap={16: 27}`` and 16
        unconfirmed leaves ``after={'27': True}``, so the migrated room reads
        ``confirmed`` for a user who never confirmed it — the start gate opens and the
        robot runs an unverified floor type (mop-on-carpet). STILL OPEN, and closing it
        is a CODE change (purge targets as well as sources), so it is not made here.
        No test covers it: [OB-6] passes because both of its keys are sources.

        One residual ambiguity, resolved deliberately: if a target new_id is ALSO a
        pre-existing confirmed key that no remap entry names as an old_id, a CONFIRMED
        migrated room's confirmation WINS. (An UNCONFIRMED one does not clear the stale
        key — that is the ⚠ above, not the deliberate part.)

        ⚠ was: "That matches rooms/room_crud.py:323-325, which purges rule-status in
        both directions on exactly this hazard." Wrong twice (D21). The line numbers are
        stale — navigate by symbol: the rule-status purge is the
        ``rule_status_map.pop(str(old_id)) / .pop(str(new_id))`` loop inside
        ``rooms/room_crud.py::RoomMapManager.reconcile_room``'s migrate arm, a few lines
        above the call into this method. And it is not a parity at all: that loop
        DISCARDS both sides, so neither wins and both rebuild on the next preflight,
        whereas this method lets one side win. Same hazard, opposite resolution."""
        if not id_remap:
            return
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        # DR-ONB-1: build from an immutable SNAPSHOT, never from the dict being
        # drained. The old loop popped from `confirmed` and wrote back into it in
        # the same pass, so a new_id that is also a LATER old_id consumed the
        # entry just written. Executed on real shapes:
        #
        #   chain {1:2, 2:3, 3:4}, rooms 1-3 confirmed -> {'4': True}
        #                                                 2 of 3 confirmations gone
        #   swap  {1:2, 2:1}, only room 1 confirmed     -> {'1': True}
        #                                                 lands on the WRONG room
        #   swap  {1:2, 2:1}, both confirmed            -> {'1': True}
        #
        # A disjoint remap like {16: 27} is correct, which is exactly why [OB-6]
        # never saw it. The damage is silent and card-reachable:
        # `RoomMapManager.reconcile_room`'s migrate arm (rooms/room_crud.py) is the
        # only caller, and a lost confirmation makes the start gate refuse with
        # onboarding_required until the user re-confirms a room they already did.
        # (⚠ the ":330" that used to be on this line was a stale pointer — navigate
        # by the symbol. The "only caller" claim itself still holds: outside tests
        # and the frozen reproducers, that call is the sole one in the package.)
        confirmed = map_ob.setdefault("floor_types_confirmed", {})
        before = dict(confirmed)                       # every read is of the OLD state
        remap = {str(old): str(new) for old, new in id_remap.items()}

        rebuilt: dict[str, bool] = {
            key: value for key, value in before.items() if key not in remap
        }
        for old_key, new_key in remap.items():
            if before.get(old_key, False):
                rebuilt[new_key] = True

        # clear+update, not reassignment: reset_onboarding and get_onboarding_state
        # both reach this dict through map_ob, so preserve object identity for
        # anything already holding a reference.
        confirmed.clear()
        confirmed.update(rebuilt)

    def check_for_new_rooms(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> bool:
        """Return True if this MAP's room count has grown since the last check.

        DR-ONB-2. The two sides of this comparison were scoped differently. The
        stored side, ``room_count_at_last_check``, is stamped by
        ``mark_rooms_discovered`` from ``data["maps"][vacuum][map_id]["rooms"]``
        — per map. The live side reads the vacuum entity's room-list attribute,
        which describes whichever map the robot currently has LOADED. On a
        multi-map vacuum, asking about map A while map B is active compared A's
        stored count against B's live one: a smaller second floor reads as "no
        new rooms" forever, and a larger one reports new rooms that belong to a
        different map.

        ⚠ THAT PREMISE IS TRUE ONLY OF A FLAT LIST, and reading it as universal was
        the second of two defects fixed here on 2026-11-08. A ``per_map_mapping``
        brand's attribute IS keyed by map, so the requested map's entry can be
        selected and the comparison made apples-to-apples — which is what DR-ONB-2
        wanted and could not have for a flat source. Dreame declares exactly that
        shape, and because this method read the attribute as a flat list
        unconditionally, ``isinstance(segments, list)`` failed on a dict that was
        never the wrong shape and the answer was a permanent False for the whole
        brand. The flat branch keeps DR-ONB-2's refusal verbatim; `[OB-3b]` pins it.

        The other defect was the companion read: ``room_list_attribute`` fell back to
        ``"segments"``, a brand's word in a brand-agnostic path. Both went together on
        purpose — removing only the fallback would have left a shorter copy of a
        predicate that still read as complete.

        NOTE, and the reason this stayed LOW: this method has NO production
        callers. It is not registered in services.yaml, and the only reference is
        an unused delegator on the parent manager (core/manager.py). Fixed rather
        than deleted because the mechanism is real and the method is public
        surface; if it stays callerless it should go, not linger as a correct
        answer nobody asks for. ``room_count_at_last_check``, the stored side of the
        comparison, is read here and nowhere else — it is write-only in practice
        (audit flag CS-2), so deleting this method would strand it.
        """
        map_ob = self._get_map_onboarding(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            create=False,
        )

        # Room list source is adapter-driven (mirrors rooms/room_discovery.py).
        # Defaults preserve Eufy behavior: the vacuum entity's "segments" attr.
        discovery = (get_adapter_config(vacuum_entity_id) or {}).get("discovery", {})
        # Deferred to match the `get_active_map_id` import below, NOT because it has
        # to be: measured both ways -- rooms.room_discovery reaches 8 modules at
        # module level and onboarding is not among them, and importing the two in
        # either order succeeds. So this is style-matching, and a future hoist of both
        # is safe. (Said "a module-level import here is a cycle" for one draft; it is
        # not, and an unverified reason at the site reads as authority.)
        from ..rooms.room_discovery import (
            ROOM_LIST_ENTITY_SELF,
            declared_room_list_entity,
            get_active_map_id,
        )
        from ..rooms.source_refresh import (
            SHAPE_PER_MAP_MAPPING,
            select_segments_for_map,
        )

        # ONE resolver for the room-list entity, shared with rooms/room_discovery.py's
        # three readers (2026-11-08). This site's own `or "vacuum_entity"` used to be
        # the ONLY place the schema's documented default existed -- and because this
        # method has no production callers, that meant the documented contract was
        # honoured in zero live paths while three live readers refused instead.
        # `.get(key, default)` is not interchangeable with the old `or`: an explicitly
        # EMPTY declaration now stays a refusal rather than silently meaning "read the
        # vacuum".
        list_entity = declared_room_list_entity(discovery)
        source_entity = (
            vacuum_entity_id if list_entity == ROOM_LIST_ENTITY_SELF else list_entity
        )
        # NO BRAND WORD. This read was `or "segments"` until 2026-11-08, commented
        # "Defaults preserve Eufy behavior" -- and `segments` is the Eufy attribute
        # name, declared by adapters/eufy/adapter.py alone and sourced from
        # robovac_mqtt. A core path whose fallback yields a brand's word is the
        # `f/eufy_is_not_the_default` failure: core owns the KEY, never the word. The
        # schema documents no default for this key, nothing live documented one, and
        # the authoritative reader (rooms/room_discovery.py) refuses without it --
        # so this now refuses too, and the four readers agree.
        #
        # Unlike `room_list_entity`, there is no sentinel that could stand in: nothing
        # can name a device's attribute for its adapter.
        attribute = discovery.get("room_list_attribute")
        if not attribute:
            _LOGGER.debug(
                "eufy_vacuum: %s declares no discovery.room_list_attribute, so the "
                "live room count cannot be read for map %s",
                vacuum_entity_id, map_id,
            )
            return False

        source_state = self._hass.states.get(source_entity)
        if source_state is None:
            return False

        raw = source_state.attributes.get(attribute)

        if discovery.get("room_list_shape") == SHAPE_PER_MAP_MAPPING:
            # THE SECOND DEFECT, AND THE LARGER ONE. This method read the attribute as
            # a flat list unconditionally, so a correctly-declared per-map brand --
            # Dreame declares `per_map_mapping` with a `rooms` attribute holding
            # {map_name: [rooms]} -- failed `isinstance(segments, list)` and returned
            # an unconditional False. Not a wrong answer about new rooms: a permanent
            # "no" for an entire brand, from a dict that was never the wrong shape.
            #
            # `select_segments_for_map` is the SAME selection rule rooms/
            # room_discovery.py uses for this shape, so the two cannot drift -- and it
            # carries the RP-019/ID-2 guard, which matters here: a resolved map id that
            # matches no key is never served another map's rooms under the requested id.
            #
            # DR-ONB-2's REFUSAL DOES NOT APPLY ON THIS BRANCH, and that is the point
            # rather than an oversight. Its premise is that "the live source cannot be
            # map-scoped -- the attribute simply has no map dimension". True of a flat
            # list; false here, where the attribute is keyed BY map. Selecting the
            # requested map's entry makes the comparison apples-to-apples, which is
            # what DR-ONB-2 wanted and could not have for a flat source.
            segments = select_segments_for_map(raw, map_id)
            if segments is None:
                return False
        else:
            # Flat list: no map dimension, so DR-ONB-2 stands exactly as written --
            # the live side describes whichever map is LOADED, and comparing it with
            # another map's stored count is an answer about a different room set.
            # [OB-3b] is this branch's pin and must stay green.
            active_map_id = get_active_map_id(self._hass, vacuum_entity_id)
            if active_map_id is not None and str(active_map_id) != str(map_id):
                return False

            segments = raw
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
        maps = self._data.get("maps", {}).get(vacuum_entity_id, {})
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

        # DR-ONB-3: any_incomplete is only ever set True INSIDE the loop
        # above, so a vacuum with zero maps leaves it False -- vacuously
        # "complete". Mirrors the `setup_complete = bool(managed) and ...` guard
        # in `setup/status.py::get_setup_status`, which already rejects the
        # identical shape. (⚠ the "(line 218)" that used to be here was a stale
        # pointer, and being prose-form it was invisible to a path-based citation
        # grep. Navigate by the symbol; do not re-add a line number.)
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "all_complete": bool(maps) and not any_incomplete,
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
        ob[vacuum_entity_id][str(map_id)] = _default_map_onboarding()
        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "reset": True,
        }
