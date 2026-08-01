"""Proof RP-015 (RF-24) — slug uniqueness at the admission boundary.

slugify_room_name (rooms/utils.py) documents distinct-name -> distinct-slug as
an INVARIANT its callers rely on, but the function itself has no uniqueness
guarantee — it is a pure per-name transform. discover_rooms_for_vacuum
(rooms/room_discovery.py) calls it once per room with no cross-room collision
check, so two same-named rooms silently share a slug.

Four findings, four cases:

  A1-ID-1 — discovery emits the collision; downstream, dispatch's
    slug_to_live_id first-wins builder (dispatch/manager.py:311-319) then
    resolves BOTH stored targets to the SAME live segment id (verified at
    source: `if not slug or slug in slug_to_live_id: continue` skips every
    slug after its first sighting).
  A2-REC-2 — the same collision fools compute_reconciliation
    (rooms/reconciliation.py, pure) into reporting a PHANTOM id_changed
    review: the second physical room (a genuinely new id) reads as the FIRST
    stored room's identity having renumbered, because both discovered rows
    share the stored room's slug.
  A1-ID-3 — an all-punctuation name strips to an EMPTY slug (slugify_room_name
    strips quote characters) and is currently admitted anyway; only the raw
    name is checked for emptiness (room_discovery.py:245-247), never the slug
    it produces.
  A6-TRK-5 — mapping/tracker.py's _detect_current_room compares live target
    names against stored rooms via _norm_room_name, which folds space/-/_ all
    to a single space — coarser than slugify_room_name (which only maps space
    -> underscore, leaving - and _ alone). Two rooms rooms/ keeps DISTINCT
    (different slugs) can therefore both "match" the same live signal under
    the tracker's own comparison, and dict-iteration order silently picks one.

Q4's stored-slug dedupe migration (required_behavior 2) is NOT a case here:
it is a wholly new function with no fixed call site yet (files_allowed lists
core/manager.py for the init wiring and room_discovery.py/utils.py for the
pure logic, but the packet does not pin which). A proof cannot faithfully
call code that does not exist without guessing a signature, and guessing one
is how a proof "certifies" a spec the executor is still free to implement
differently. Flagging as a materialization gap rather than encoding a guess:
the executor's proof update (or a follow-up materialization pass) should add
this case once the symbol lands, driving it directly and asserting the
manifest shape verbatim from required_behavior (2).

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_slug_collision.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config   # noqa: E402
from custom_components.eufy_vacuum.rooms.room_discovery import discover_rooms_for_vacuum   # noqa: E402
from custom_components.eufy_vacuum.rooms.reconciliation import compute_reconciliation   # noqa: E402
from custom_components.eufy_vacuum.dispatch.manager import DispatchManager   # noqa: E402
from custom_components.eufy_vacuum.mapping.tracker import MappingTracker   # noqa: E402

VAC = H.VAC
MAP = "1"


def _register_discovery_and_dispatch(hass) -> None:
    """entity_attribute discovery source -- no service mocking needed; the
    freshness-gate refresh short-circuits (ok=True, reason=not_service_source)
    for this source kind, verified at source (source_refresh.py:307-308)."""
    register_adapter_config(VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_map": "select.alfred_selected_map",
                     "active_cleaning_target": "sensor.alfred_target"},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "segments",
            "room_id_key": "segment_id",
            "room_name_key": "name",
        },
        "dispatch": {"resolve_live_ids_by_slug": True, "rooms_field": "segments"},
    })
    hass.states.async_set("select.alfred_selected_map", MAP)


def main() -> int:
    proof = H.Proof("RP-015", "slug uniqueness at the admission boundary")

    # -------------------------------------------------------------------
    # Case 1 (A1-ID-1 + A2-REC-2): two "Bathroom" rooms, ids 3 and 7.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    _register_discovery_and_dispatch(hass)
    hass.states.async_set(VAC, "cleaning", attributes={"segments": [
        {"segment_id": 3, "name": "Bathroom"},
        {"segment_id": 7, "name": "Bathroom"},
    ]})

    discovered = discover_rooms_for_vacuum(hass, vacuum_entity_id=VAC, map_id=MAP)
    slugs = [r["slug"] for r in discovered]

    # existing stored rooms: only room 3 has been seen/saved before (room 7 is
    # the genuinely-new physical room this discovery just found).
    existing = {"3": {"room_id": 3, "slug": "bathroom", "name": "Bathroom"}}
    recon = compute_reconciliation(discovered_rooms=discovered, existing_rooms=existing)
    phantom_id_changed = [
        r for r in recon["reviews"]
        if r["kind"] == "id_changed" and r["old_id"] == 3 and r["new_id"] == 7
    ]

    mgr = H.ManagerStub(hass=hass)
    dispatch = DispatchManager(manager=mgr)

    async def _resolve():
        return await dispatch._resolve_live_dispatch_payload(
            vacuum_entity_id=VAC, map_id=MAP,
            payload={"segments": [3, 7], "repeat": 1},
            resolved_rooms=[
                {"room_id": 3, "slug": slugs[0]},
                {"room_id": 7, "slug": slugs[1]},
            ],
        )

    import asyncio
    dispatched = asyncio.run(_resolve())

    proof.case(
        "two 'Bathroom' rooms (ids 3, 7) discovered together",
        before=slugs == ["bathroom", "bathroom"]
        and len(phantom_id_changed) == 1
        and dispatched["segments"] == [3, 3],
        before_msg="both rooms slug=bathroom; reconciliation reports a PHANTOM "
                   "id_changed (3->7) for a room that never renumbered; second "
                   "dispatched first's segment (both resolve to live id 3)",
        after=slugs == ["bathroom", "bathroom_r7"]
        and len(phantom_id_changed) == 0
        and dispatched["segments"] == [3, 7],
        after_msg="bathroom + bathroom_r7 (lowest room_id keeps the bare slug); "
                  "no phantom reconciliation review; distinct segments dispatched",
        detail=f"slugs={slugs} · phantom_id_changed={phantom_id_changed} · "
               f"dispatched segments={dispatched.get('segments')}",
    )

    # -------------------------------------------------------------------
    # Case 2 (A1-ID-3): an all-quote name slugifies to empty and is admitted.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    _register_discovery_and_dispatch(hass2)
    hass2.states.async_set(VAC, "cleaning", attributes={"segments": [
        {"segment_id": 9, "name": '""'},
    ]})
    discovered2 = discover_rooms_for_vacuum(hass2, vacuum_entity_id=VAC, map_id=MAP)

    proof.case(
        "an all-quote raw name (slugify strips both quote chars to '')",
        before=len(discovered2) == 1 and discovered2[0]["slug"] == "",
        before_msg="the room is admitted with slug='' -- only the RAW name is "
                   "checked for emptiness (room_discovery.py:245-247), never the "
                   "slug it produces",
        after=len(discovered2) == 0,
        after_msg="refused at discovery -- the room is skipped (a slug that "
                  "strips to empty never reaches the room list)",
        detail=f"discovered={discovered2}",
    )

    # -------------------------------------------------------------------
    # Case 3 (A6-TRK-5): _norm_room_name merges what slugify_room_name splits.
    # -------------------------------------------------------------------
    hass3 = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_cleaning_target": "sensor.alfred_target"},
    })
    hass3.states.async_set("sensor.alfred_target", "Foo Bar")
    tracker = MappingTracker(hass3)
    # room 22 (slug "foo-bar") deliberately iterated BEFORE room 11 (slug
    # "foo_bar", the room whose STORED NAME is an exact match for the live
    # signal) so a wrong-room match is not an artefact of favourable dict order.
    rooms = {
        "22": {"room_id": 22, "slug": "foo-bar", "name": "Foo-Bar", "is_transition": False},
        "11": {"room_id": 11, "slug": "foo_bar", "name": "Foo Bar", "is_transition": False},
    }
    resolved = tracker._detect_current_room(VAC, rooms)

    from custom_components.eufy_vacuum.rooms.utils import slugify_room_name
    live_slug = slugify_room_name("Foo Bar")

    proof.case(
        "live target 'Foo Bar' vs stored rooms foo-bar (id 22) / foo_bar (id 11)",
        before=resolved == "22",
        before_msg="_norm_room_name folds '-' and '_' both to a space: "
                   "'foo-bar' and 'foo_bar' both normalize to 'foo bar' and the "
                   "live signal matches whichever room the dict visits first -- "
                   "here the WRONG room (22), even though its own name is "
                   "'Foo Bar' verbatim",
        after=resolved == "11",
        after_msg="_detect_current_room now resolves to room 11 -- the "
                  "PHYSICALLY correct room, matched via slugify_room_name "
                  "('Foo Bar' -> 'foo_bar', room 11's exact stored slug) "
                  "rather than the coarser _norm_room_name fold",
        detail=f"_detect_current_room (current _norm_room_name impl) -> "
               f"{resolved!r} · slugify_room_name('Foo Bar')={live_slug!r} "
               f"(the AFTER comparison RP-015 replaces _norm_room_name with)",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
