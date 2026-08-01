"""Proof RP-018 (RF-25b) — slug-led carry + Q5 enablement semantics.

Both reachable room writers (rooms/room_manager.py:build_managed_rooms and
maps/map_manager.py:rebuild_map_bucket) carry per-room settings forward by
NUMERIC id: `existing_rooms.get(str(room_id), {})` / `existing_rooms.get(
room_id_key, {})`. Verified at source in both files — same lookup, same bug,
independently written. A re-segment renumber (Kitchen 16->21, a new room
takes over 16) transplants Kitchen's settings onto whatever physical room the
freed id now names, and Kitchen itself (now at 21) gets brand-new defaults as
if it had never been configured.

Four cases, covering all six finding_ids (both writers share the transplant
and Q5-violation bugs, so one case each proves both REC-8+CRUD-2 and
DQ-Q-5+CRUD-6 at once):

  REC-8 + CRUD-2 — numeric-id transplant, both writers.
  DQ-Q-5 + CRUD-6 — auto-enable/auto-approve a room the user never saw, both
    writers (`existing.get("enabled", True)` / `previous.get("enabled",
    True)` — the SAME default regardless of first-import vs incremental).
  CRUD-3 — floor-type auto-confirm. No separate "floor type confirmed" field
    exists in RoomConfig (checked: only `floor_type: str` and `is_configured:
    bool`), so this proof reads "floor-type confirmation" as gating the
    EXISTING is_configured flag on whether `floor_types` supplied an entry
    for that room -- the packet names no new field, and is_configured is the
    only flag the onboarding gate actually reads. Flagged as an
    interpretation, not a verified requirement: if the eventual fix adds a
    separate field instead, this case's AFTER predicate will never match and
    the proof will keep reading BEFORE post-repair -- a safe failure
    direction (under-claims closure) rather than a false AFTER.
  CRUD-5 — build_managed_rooms has NO rejected_rooms parameter at all
    (checked its full signature). rejected_rooms is an existing, real concept
    (setup/drift.py stores int room-id lists under that exact name). Probed
    with a TypeError-tolerant call using that name — the natural one, since
    the packet does not specify the parameter shape.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_slug_carry.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.rooms.room_manager import build_managed_rooms   # noqa: E402
from custom_components.eufy_vacuum.maps.map_manager import rebuild_map_bucket   # noqa: E402

VAC = H.VAC
MAP = "1"

_DEFAULTS: dict = {}


def _kitchen_at(room_id: int) -> dict:
    return {"room_id": room_id, "map_id": MAP, "name": "Kitchen", "slug": "kitchen"}


def _bedroom_at(room_id: int) -> dict:
    return {"room_id": room_id, "map_id": MAP, "name": "Bedroom", "slug": "bedroom"}


def main() -> int:
    proof = H.Proof("RP-018", "slug-led carry + Q5 enablement semantics")

    # -------------------------------------------------------------------
    # Case 1 (REC-8 + CRUD-2): renumber transplant, both writers.
    # Kitchen was stored at id 16 with distinctive settings. Re-segment:
    # Kitchen now discovered at 21, a brand-new Bedroom takes over 16.
    # -------------------------------------------------------------------
    kitchen_settings = {
        "room_id": 16, "name": "Kitchen", "slug": "kitchen", "enabled": True,
        "is_dock_room": True, "grants_access_to": ["hallway"], "floor_type": "tile",
        "is_configured": True,
    }
    existing = {"16": kitchen_settings}
    discovered = [_kitchen_at(21), _bedroom_at(16)]

    managed_a = build_managed_rooms(
        discovered_rooms=discovered, new_room_defaults=_DEFAULTS, existing_rooms=existing,
    )
    rebuilt_data = {"maps": {VAC: {MAP: {"rooms": dict(existing)}}}}
    rebuilt_b = rebuild_map_bucket(
        data=rebuilt_data, vacuum_entity_id=VAC, map_id=MAP, discovered_rooms=discovered,
    )["rooms"]

    def _transplanted(managed: dict) -> bool:
        # id 16 is now physically Bedroom but carries Kitchen's dock/grants;
        # id 21 is now physically Kitchen but got brand-new (non-dock) defaults.
        return (
            managed["16"]["is_dock_room"] is True
            and managed["16"]["grants_access_to"] == ["hallway"]
            and managed["21"]["is_dock_room"] is False
        )

    def _followed_kitchen(managed: dict) -> bool:
        # slug-led: whichever id now carries slug "kitchen" (21) has Kitchen's
        # settings; whichever carries "bedroom" (16) does not.
        by_slug = {r["slug"]: r for r in managed.values()}
        return (
            by_slug["kitchen"]["is_dock_room"] is True
            and by_slug["kitchen"]["grants_access_to"] == ["hallway"]
            and by_slug["bedroom"]["is_dock_room"] is False
            and by_slug["bedroom"]["grants_access_to"] == []
        )

    proof.case(
        "Kitchen renumbers 16->21; a new Bedroom takes over 16 (both writers)",
        before=_transplanted(managed_a) and _transplanted(rebuilt_b),
        before_msg="both writers carry by numeric id: Bedroom (now id 16) "
                   "inherits Kitchen's dock flag + access grants; Kitchen "
                   "(now id 21) lost its own settings to brand-new defaults",
        after=_followed_kitchen(managed_a) and _followed_kitchen(rebuilt_b),
        after_msg="slug-led carry: settings follow the SLUG regardless of "
                  "which numeric id it now occupies -- Kitchen's dock/grants "
                  "stay with Kitchen, Bedroom gets fresh defaults",
        detail=f"build_managed_rooms[16].is_dock_room={managed_a['16']['is_dock_room']} "
               f"[21].is_dock_room={managed_a['21']['is_dock_room']} · "
               f"rebuild_map_bucket[16].is_dock_room={rebuilt_b['16']['is_dock_room']} "
               f"[21].is_dock_room={rebuilt_b['21']['is_dock_room']}",
    )

    # -------------------------------------------------------------------
    # Case 2 (DQ-Q-5 + CRUD-6): first-import enables all; incremental
    # discovery must NOT silently enable a genuinely-new room.
    # -------------------------------------------------------------------
    # incremental: map already has "kitchen" saved+enabled; discovery now
    # ALSO finds a brand-new "office" room never seen before.
    existing_incremental = {"1": {"room_id": 1, "name": "Kitchen", "slug": "kitchen",
                                   "enabled": True, "is_configured": True}}
    discovered_incremental = [
        {"room_id": 1, "map_id": MAP, "name": "Kitchen", "slug": "kitchen"},
        {"room_id": 2, "map_id": MAP, "name": "Office", "slug": "office"},
    ]
    managed_inc = build_managed_rooms(
        discovered_rooms=discovered_incremental, new_room_defaults=_DEFAULTS,
        existing_rooms=existing_incremental,
    )
    rebuilt_inc = rebuild_map_bucket(
        data={"maps": {VAC: {MAP: {"rooms": dict(existing_incremental)}}}},
        vacuum_entity_id=VAC, map_id=MAP, discovered_rooms=discovered_incremental,
    )["rooms"]

    proof.case(
        "incremental discovery on an ALREADY-IMPORTED map finds a new Office",
        before=managed_inc["2"]["enabled"] is True and rebuilt_inc["2"]["enabled"] is True,
        before_msg="both writers default a room with no existing entry to "
                   "enabled=True regardless of first-import vs incremental -- "
                   "the new Office silently joins the active clean queue",
        after=managed_inc["2"]["enabled"] is False and rebuilt_inc["2"]["enabled"] is False,
        after_msg="incremental discovery on a non-empty map (existing_rooms "
                  "was non-empty before this write) adds the new room "
                  "DISABLED and unconfirmed",
        detail=f"build_managed_rooms Office.enabled={managed_inc['2']['enabled']} · "
               f"rebuild_map_bucket Office.enabled={rebuilt_inc['2']['enabled']}",
    )

    # -------------------------------------------------------------------
    # Case 3 (CRUD-3): floor-type auto-confirm via is_configured.
    # -------------------------------------------------------------------
    managed_no_floor = build_managed_rooms(
        discovered_rooms=[{"room_id": 5, "map_id": MAP, "name": "Attic", "slug": "attic"}],
        new_room_defaults=_DEFAULTS, existing_rooms={}, enabled_room_ids=[5],
        floor_types={},   # wizard never supplied a floor type for room 5
    )
    proof.case(
        "a room approved via enabled_room_ids but with NO floor_types entry",
        before=managed_no_floor["5"]["is_configured"] is True
        and managed_no_floor["5"]["floor_type"] == "hardwood",
        before_msg="is_configured is stamped True unconditionally -- the "
                   "GUESSED 'hardwood' default reads as user-confirmed to "
                   "every is_configured consumer (onboarding gate included)",
        after=managed_no_floor["5"]["is_configured"] is False,
        after_msg="is_configured requires floor_types to have SUPPLIED an "
                  "entry for this room -- an unsupplied floor type is not "
                  "silently confirmed",
        detail=f"is_configured={managed_no_floor['5']['is_configured']} · "
               f"floor_type={managed_no_floor['5']['floor_type']!r}",
    )

    # -------------------------------------------------------------------
    # Case 4 (CRUD-5): rejected_rooms is never consulted.
    # -------------------------------------------------------------------
    rejected_room = {"room_id": 9, "map_id": MAP, "name": "Garage", "slug": "garage"}
    managed_plain = build_managed_rooms(
        discovered_rooms=[rejected_room], new_room_defaults=_DEFAULTS, existing_rooms={},
    )
    resurrected_today = "9" in managed_plain

    try:
        managed_filtered = build_managed_rooms(
            discovered_rooms=[rejected_room], new_room_defaults=_DEFAULTS,
            existing_rooms={}, rejected_rooms={9},
        )
        accepts_param = True
        resurrected_after = "9" in managed_filtered
    except TypeError:
        accepts_param = False
        resurrected_after = True   # can't have been filtered if the call itself failed

    proof.case(
        "a room the user explicitly rejected (setup/drift.py's rejected_rooms) "
        "is rediscovered",
        before=resurrected_today and not accepts_param,
        before_msg="build_managed_rooms takes no rejected_rooms argument at "
                   "all (confirmed: the call above only succeeds without it) "
                   "-- a rejected room resurrects the instant it is "
                   "rediscovered, with no way to suppress it",
        after=accepts_param and not resurrected_after,
        after_msg="build_managed_rooms consults rejected_rooms and excludes "
                  "a rejected id from the managed set",
        detail=f"resurrected without the param={resurrected_today} · "
               f"accepts a rejected_rooms kwarg={accepts_param}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
