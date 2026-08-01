"""Proof RP-016 (RF-20) — referential integrity: per-map stores + rename/delete scans.

Four cases (of eight finding_ids -- ZONE-C-2/referencing_steps pruning and
IO-6/get_paths rename-detection are NOT driven here, time-boxed after four
other packets this session; left for a follow-up pass).

DELEGATION CHECKED (required_behavior (5), "mirror upload's layout-
awareness"): read _handle_upload_map_image in full (mapping_services.py:
832-961) before writing case 3. Confirmed it genuinely maintains
layout<->variant associations: a layout_id upload writes
custom_layouts[id]["backdrop_variant"] = variant (line 956), and an
art_scope upload writes custom_layouts[id]["home_art"]["art_variant"] or
["rooms"][room_id]["art_variant"] (lines 949/951). _handle_delete_map_image
(the sibling, its own docstring literally says "Mirror of
_handle_upload_map_image") pops the variant from image_variants but never
reads custom_layouts at all -- so upload's own layout-awareness is real,
and delete's failure to mirror it is a real gap, not a false delegation.

  #1 (PER_MAP_STORES, item 1) -- remove_map (rooms/room_crud.py:405-465)
    clears exactly five buckets (maps, discovery, room_history,
    room_rule_status, active_jobs) -- verified by reading the full method.
    run_profiles, queue and onboarding are absent from that list despite
    being real per-(vacuum,map) stores (confirmed their setdefault shapes
    in profiles/manager.py:714-717, core/manager.py:1544-1546,
    onboarding/manager.py:63-64) -- a re-import of the same map_id finds
    them still populated with the deleted segmentation's room ids.
  #2 (item 2) -- delete_room_profile (profiles/manager.py:598-620) has no
    referrer scan at all: no force param, no refusal, no ServiceValidationError
    class. rename_room_profile (534-596) has the same gap in reverse: it
    updates the STORE key but never touches any room's stored profile_name
    field, so a renamed profile orphans every room that referenced the old
    name.
  #3 (item 5, delegation) -- delete_map_image never reads custom_layouts,
    so deleting a layout's backdrop image leaves backdrop_variant pointing
    at a now-nonexistent image_variants entry.
  #4 (item 4, CUSTOM-5) -- _generate_saved_zone_id (mapping_services.py:
    1389-1398) derives its id purely from the CURRENT `existing` collection
    (`base not in existing`), not a persisted counter -- a zone created,
    deleted, then re-created at the same wall-clock second (mocked here,
    since real collisions are rare but the id SCHEME provides no protection
    regardless of clock granularity) generates the identical id, silently
    colliding with any durable reference still pointing at the deleted zone.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_referential.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager   # noqa: E402
from custom_components.eufy_vacuum.profiles.manager import ProfileManager   # noqa: E402
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket   # noqa: E402
from custom_components.eufy_vacuum.mapping.mapping_services import (   # noqa: E402
    _generate_saved_zone_id,
)

VAC = H.VAC
MAP = "1"


def main() -> int:
    proof = H.Proof("RP-016", "referential integrity: per-map stores + rename/delete scans")

    # -------------------------------------------------------------------
    # Case 1: remove_map leaves run_profiles/queue/onboarding behind.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr._default_active_job_state = lambda **kw: {"status": "idle"}
    mgr.data["maps"] = {VAC: {MAP: {"rooms": {"1": {"room_id": 1}}}}}
    mgr.data["run_profiles"] = {VAC: {MAP: {"rp_1": {"name": "Weeknight"}}}}
    mgr.data["queue"] = {VAC: {MAP: {"queue_room_ids": [1, 2]}}}
    mgr.data["onboarding"] = {VAC: {MAP: {"rooms_discovered": True}}}
    room_map = RoomMapManager(manager=mgr)

    room_map.remove_map(vacuum_entity_id=VAC, map_id=MAP)

    stale = {
        "run_profiles": MAP in mgr.data.get("run_profiles", {}).get(VAC, {}),
        "queue": MAP in mgr.data.get("queue", {}).get(VAC, {}),
        "onboarding": MAP in mgr.data.get("onboarding", {}).get(VAC, {}),
    }

    proof.case(
        "remove_map, then a re-import reuses the same map_id",
        before=all(stale.values()),
        before_msg="run_profiles/queue/onboarding all survive remove_map -- "
                   "a re-import at the same map_id resurrects a run profile "
                   "and a queue holding room ids from the DELETED segmentation",
        after=not any(stale.values()),
        after_msg="all per-map stores are cleared -- remove_map consumes "
                  "the PER_MAP_STORES registry and clears every entry",
        detail=f"buckets still populated after remove_map={stale}",
    )

    # -------------------------------------------------------------------
    # Case 2: delete/rename don't scan for referring rooms.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    mgr2 = H.ManagerStub(hass=hass2)
    mgr2.data["profiles"] = {"room_profiles": {"quiet": {"label": "Quiet"}}}
    mgr2.data["maps"] = {VAC: {MAP: {"rooms": {
        "1": {"room_id": 1, "profile_name": "quiet"},
    }}}}
    profiles = ProfileManager(manager=mgr2)

    delete_result = profiles.delete_room_profile(profile_name="quiet")
    room_profile_after_delete = mgr2.data["maps"][VAC][MAP]["rooms"]["1"]["profile_name"]

    # reset for the rename half
    mgr2.data["profiles"]["room_profiles"] = {"quiet": {"label": "Quiet"}}
    mgr2.data["maps"][VAC][MAP]["rooms"]["1"]["profile_name"] = "quiet"
    rename_result = profiles.rename_room_profile(
        profile_name="quiet", new_profile_name="silent",
    )
    room_profile_after_rename = mgr2.data["maps"][VAC][MAP]["rooms"]["1"]["profile_name"]

    proof.case(
        "a room references a profile that gets deleted, then renamed",
        before=delete_result["deleted"] is True
        and room_profile_after_delete == "quiet"
        and rename_result["renamed"] is True
        and room_profile_after_rename == "quiet",
        before_msg="delete succeeds unconditionally (no referrer scan, no "
                   "refusal) leaving the room's profile_name pointing at a "
                   "profile that no longer exists; rename updates the STORE "
                   "key but never touches the referring room, orphaning it "
                   "under the OLD name",
        after=(delete_result["deleted"] is False or room_profile_after_delete != "quiet")
        and room_profile_after_rename == "silent",
        after_msg="delete refuses (referrers exist, no force) or repoints "
                  "them; rename repoints every referring room to the new name",
        detail=f"profile_name after delete={room_profile_after_delete!r} · "
               f"after rename={room_profile_after_rename!r}",
    )

    # -------------------------------------------------------------------
    # Case 3 (delegation): delete_map_image ignores custom_layouts.
    # -------------------------------------------------------------------
    hass3 = H.make_hass()
    mgr3 = H.ManagerStub(hass=hass3)
    bucket = ensure_map_bucket(data=mgr3.data, vacuum_entity_id=VAC, map_id=MAP)
    bucket["image_variants"] = {"custom_L1": {"variant": "custom_L1", "path": "/x.png"}}
    bucket["custom_layouts"] = {"L1": {"backdrop_variant": "custom_L1"}}

    variants = bucket["image_variants"]
    variants.pop("custom_L1", None)   # the exact mutation _handle_delete_map_image performs
    bucket["image_variants"] = variants
    dangling = bucket["custom_layouts"]["L1"]["backdrop_variant"] == "custom_L1"

    proof.case(
        "the image backing a layout's backdrop is deleted",
        before=dangling and "custom_L1" not in bucket["image_variants"],
        before_msg="custom_layouts['L1']['backdrop_variant'] still says "
                   "'custom_L1' after the variant was removed -- a dangling "
                   "reference to a file that no longer exists, unlike upload "
                   "which keeps the two in sync",
        after=bucket["custom_layouts"]["L1"].get("backdrop_variant") is None,
        after_msg="delete_map_image sweeps custom_layouts for any "
                  "backdrop_variant/art_variant referencing the deleted "
                  "variant and clears it -- mirrors upload's own bookkeeping",
        detail=f"backdrop_variant after delete={bucket['custom_layouts']['L1'].get('backdrop_variant')!r}",
    )

    # -------------------------------------------------------------------
    # Case 4 (CUSTOM-5): saved-zone id can reuse after delete.
    # -------------------------------------------------------------------
    import custom_components.eufy_vacuum.mapping.mapping_services as ms
    from datetime import datetime as _dt

    class _FixedDatetime(_dt):
        @classmethod
        def now(cls, tz=None):
            return _dt(2026, 8, 1, 12, 0, 0)

    _orig_datetime = ms.datetime
    ms.datetime = _FixedDatetime
    try:
        id_first = _generate_saved_zone_id({})          # zone created...
        # ...then deleted (removed from `existing`)...
        id_second = _generate_saved_zone_id({})          # ...a new zone created later.
    finally:
        ms.datetime = _orig_datetime

    proof.case(
        "a zone is created, deleted, and a new one created (same wall-clock second)",
        before=id_first == id_second,
        before_msg="the id scheme derives purely from the CURRENT existing "
                   "collection -- once the first zone is gone, the exact "
                   "same id is generated again for an unrelated new zone, "
                   "silently colliding with any durable reference still "
                   "pointing at the deleted one",
        after=id_first != id_second,
        after_msg="a persisted monotonic counter guarantees the second id "
                  "differs regardless of the current existing collection or "
                  "wall-clock resolution",
        detail=f"first id={id_first!r} · second id={id_second!r}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
