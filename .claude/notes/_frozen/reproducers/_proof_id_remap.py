"""Proof RP-017 (RF-25a) — id-remap coverage + CV-overlay invalidation.

Four cases. required_behavior (1)'s GENERIC walker -- "iterates RP-016's
PER_MAP_STORES entries that declare id-keyed sub-maps" -- depends on a
registry RP-016 introduces (not yet landed, not in this materialization
batch). Same disposition as RP-015's Q4 migration: not driven here, flagged
rather than guessed. What IS driven is the CONCRETE headline defect the
registry is meant to close -- trouble_rooms, named in the packet's own
problem statement as "the one store the reconcile-migrate walker forgets".

  trouble_rooms (part of required_behavior 1) -- reconcile_room's migrate
    path only ever touches room_rule_status (verified at source:
    room_crud.py:253, `for old_id, new_id in plan["id_remap"].items():
    rule_status_map.pop(...)` -- no other store is touched). trouble_rooms
    is written by learning/job_finalizer.py:_update_trouble_rooms_log, keyed
    by bare room_id with no map scoping and no slug -- confirmed untouched
    by a migrate that renumbers the very room it tracks.
  required_behavior (2), CV overlay invalidation -- mapping_services.py:1194
    carries an EXPLICIT comment stating the CURRENT (to-be-changed) design:
    "Re-analysis preserves the user's segment_room_links and
    companion_anchors -- they're independent of the image-derived segments."
    The packet's problem statement is why that premise is wrong: segment ids
    are per-run CV ordinals, not stable identities, so "preserving" a link
    across a re-analysis silently re-attaches it to whichever NEW segment
    inherits the old ordinal. Driven for real: get_segmenter_engine is
    swapped for a stub returning a successful result (the CV step itself is
    an external dependency the packet doesn't touch, not the domain logic
    under test), so _handle_analyze_map_image runs its real overlay-handling
    code path end to end.
  DR-ONB-1 -- onboarding/manager.py:remap_confirmed_floor_types mutates ONE
    dict while iterating id_remap. Proven with the packet's own example:
    id_remap={1:2, 2:3, 3:4} loses 2 of the 3 confirmations (a value written
    to key "2" in step 1 is immediately consumed as step 2's "old_id" source
    and moved again to "3", cascading down the chain).
  DR-ONB-2 -- check_for_new_rooms (same file) compares the LIVE room count
    (whichever map is currently active on the device) against map_id's
    STORED room_count_at_last_check with no check that map_id IS the active
    map -- confirmed by reading the full function: no active-map lookup
    anywhere in it.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_id_remap.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config   # noqa: E402
from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager   # noqa: E402
from custom_components.eufy_vacuum.onboarding.manager import OnboardingManager   # noqa: E402
from custom_components.eufy_vacuum.const import DOMAIN, DATA_RUNTIME   # noqa: E402

VAC = H.VAC
MAP = "1"


def main() -> int:
    proof = H.Proof("RP-017", "id-remap coverage + CV-overlay invalidation")

    # -------------------------------------------------------------------
    # Case 1: trouble_rooms is not remapped by reconcile_room's migrate.
    # -------------------------------------------------------------------
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory() as tmp:
        store = H.learning_store(tmp)
        store.save_trouble_rooms(vacuum_entity_id=VAC, payload={
            "schema_version": 1, "record_type": "trouble_rooms_log",
            "vacuum_entity_id": VAC, "updated_at": "2026-01-01T00:00:00Z",
            "rooms": {"5": {"room_id": 5, "name": "Office", "miss_count": 4,
                             "run_count": 6, "is_trouble": True}},
        })

        hass = H.make_hass(tmp)
        mgr = H.ManagerStub(hass=hass)
        mgr.onboarding = SimpleNamespace(remap_confirmed_floor_types=lambda **kw: None)
        mgr.data["maps"] = {VAC: {MAP: {"rooms": {
            "5": {"room_id": 5, "slug": "office", "name": "Office"},
        }}}}
        mgr.data["discovery"] = {VAC: {MAP: {"rooms": [
            # office renumbers 5 -> 9 in this re-map.
            {"room_id": 9, "map_id": MAP, "name": "Office", "slug": "office"},
        ]}}}
        room_map = RoomMapManager(manager=mgr)
        room_map.reconcile_room(vacuum_entity_id=VAC, map_id=MAP, action="migrate")

        _outcome, after = store.load_trouble_rooms_outcome(vacuum_entity_id=VAC)
        rooms_after = (after or {}).get("rooms", {})

        proof.case(
            "office (chronic-trouble room) renumbers 5 -> 9 via reconcile_room migrate",
            before="5" in rooms_after and "9" not in rooms_after,
            before_msg="trouble_rooms still keys the chronic-miss record under "
                       "the OLD id 5 -- reconcile_room's migrate touched "
                       "room_rule_status but never trouble_rooms, so the "
                       "record for the renumbered room is now orphaned under "
                       "a dead id",
            after="9" in rooms_after and "5" not in rooms_after
            and rooms_after.get("9", {}).get("is_trouble") is True,
            after_msg="trouble_rooms is re-keyed onto the new id (9), "
                      "preserving the chronic-trouble history through the "
                      "renumber",
            detail=f"trouble_rooms keys after migrate={sorted(rooms_after)}",
        )

    # -------------------------------------------------------------------
    # Case 2: CV overlay invalidation on re-analysis.
    # -------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp2:
        from custom_components.eufy_vacuum.mapping import segmenter_engines
        from custom_components.eufy_vacuum.mapping.mapping_services import (
            _handle_analyze_map_image,
        )
        from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket

        object_id = VAC.split(".", 1)[1]
        base_dir = os.path.join(tmp2, "eufy_vacuum", "maps", object_id)
        os.makedirs(base_dir, exist_ok=True)
        with open(os.path.join(base_dir, f"map_{MAP}.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")   # a PNG header is enough; never decoded

        hass2 = H.make_hass(tmp2)
        mgr2 = H.ManagerStub(hass=hass2)
        mgr2.async_save = H.async_noop()
        hass2.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr2

        bucket = ensure_map_bucket(data=mgr2.data, vacuum_entity_id=VAC, map_id=MAP)
        bucket["segment_room_links"] = {"3": 7}       # a per-run ordinal -> room link
        bucket["image_segment_adjustments"] = {"3": {"nudge_x": 12}}
        bucket["image_segments"] = {"available": False}   # forces a real (re)analysis

        class _StubEngine:
            def segment_map_image(self, *, image_path, tuning, context=None):
                # a DIFFERENT segment layout this run -- ordinal "3" now names a
                # different physical area than it did last run.
                return {"available": True, "segments": [{"id": "3"}, {"id": "4"}]}

        _orig_get_engine = segmenter_engines.get_segmenter_engine
        segmenter_engines.get_segmenter_engine = lambda name: _StubEngine()
        try:
            import asyncio

            class _Call:
                data = {"vacuum_entity_id": VAC, "map_id": MAP, "force_reanalyze": True}

            asyncio.run(_handle_analyze_map_image(hass2, _Call()))
        finally:
            segmenter_engines.get_segmenter_engine = _orig_get_engine

        links_after = bucket.get("segment_room_links")
        adjustments_after = bucket.get("image_segment_adjustments")

        proof.case(
            "re-analysis produces a NEW segment layout for the same map",
            before=links_after == {"3": 7} and adjustments_after == {"3": {"nudge_x": 12}},
            before_msg="segment_room_links and image_segment_adjustments "
                       "survive re-analysis UNCHANGED (verified-at-source "
                       "comment: 'Re-analysis preserves ... independent of "
                       "the image-derived segments') -- ordinal id '3' now "
                       "names a different segment, but the old nudge/link is "
                       "silently re-attached to it",
            after=links_after in ({}, None) and adjustments_after in ({}, None),
            after_msg="re-analysis INVALIDATES (clears) both overlay stores "
                      "for this map -- ids are per-run ordinals, so honest "
                      "invalidation replaces fabricated stability",
            detail=f"segment_room_links after={links_after} · "
                   f"image_segment_adjustments after={adjustments_after}",
        )

    # -------------------------------------------------------------------
    # Case 3 (DR-ONB-1): overlapping id_remap corrupts floor confirmations.
    # -------------------------------------------------------------------
    hass3 = H.make_hass()
    ob = OnboardingManager(data={}, hass=hass3)
    ob._get_map_onboarding(vacuum_entity_id=VAC, map_id=MAP)["floor_types_confirmed"] = {
        "1": True, "2": True, "3": True,
    }
    ob.remap_confirmed_floor_types(
        vacuum_entity_id=VAC, map_id=MAP, id_remap={1: 2, 2: 3, 3: 4},
    )
    confirmed_after = ob._get_map_onboarding(
        vacuum_entity_id=VAC, map_id=MAP)["floor_types_confirmed"]

    proof.case(
        "overlapping renumber chain {1:2, 2:3, 3:4} (the packet's own example)",
        before=confirmed_after == {"4": True},
        before_msg="in-place single-dict mutation while iterating: only ONE "
                   "of the three confirmations survives (loses 2 of 3, "
                   "exactly as the packet's proven example states) -- a "
                   "value written to a key in one step is immediately "
                   "consumed as the NEXT step's source",
        after=confirmed_after == {"2": True, "3": True, "4": True},
        after_msg="two-dict algorithm (build fresh, swap at end): all three "
                  "confirmations survive the renumber chain intact",
        detail=f"floor_types_confirmed after remap={confirmed_after}",
    )

    # -------------------------------------------------------------------
    # Case 4 (DR-ONB-2): check_for_new_rooms ignores the active-map gate.
    # -------------------------------------------------------------------
    hass4 = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "eufy", "source": "code",
        "entities": {"active_map": "sensor.alfred_active_map"},
        "discovery": {"room_list_entity": "vacuum_entity", "room_list_attribute": "segments"},
    })
    hass4.states.async_set("sensor.alfred_active_map", "A")
    # the device is CURRENTLY on map A, live-reporting 5 segments...
    hass4.states.async_set(VAC, "cleaning", attributes={"segments": [{}] * 5})

    ob2 = OnboardingManager(data={}, hass=hass4)
    # ...but the query asks about map B, which last had 2 rooms at its own
    # last check -- an entirely unrelated map.
    ob2._get_map_onboarding(vacuum_entity_id=VAC, map_id="B")["room_count_at_last_check"] = 2
    result_wrong_map = ob2.check_for_new_rooms(vacuum_entity_id=VAC, map_id="B")

    proof.case(
        "querying map B for new rooms while the device is active on map A",
        before=result_wrong_map is True,
        before_msg="compares map A's LIVE count (5) against map B's STORED "
                   "count (2) with no active-map check -- reports 'new rooms "
                   "found' on B based entirely on A's live data",
        after=result_wrong_map is not True,
        after_msg="the queried map is not the active map -- returns "
                  "indeterminate rather than comparing unrelated numbers",
        detail=f"check_for_new_rooms(map_id='B')={result_wrong_map!r} while "
               f"active_map='A' reports 5 live segments, B's own last count=2",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
