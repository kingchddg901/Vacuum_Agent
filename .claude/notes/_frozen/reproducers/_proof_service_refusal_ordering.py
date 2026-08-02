"""Proof RP-031 (RF-14 + RF-05; Q9) — RF-05a ordering, apply_run_profile.

ONE case, out of 39 finding_ids spanning ~60 handlers across 8 service
modules -- the packet's own reproducer_script calls for a full table-driven
proof over that handler matrix, which is out of scope for a single sitting
(cost tracks finding count: this is the single largest packet in the
campaign). This proof drives the ONE concrete, fully-specified example the
packet text itself names for RF-05a: "apply_run_profile refuse BEFORE the
selection wipe — snapshot not needed once ordering is right" (RUNPROF-2/5/6).
The other 05a example sites (start_run_profile, retry_missed_rooms) and every
05b / DIAG / dock / SVC finding are NOT driven here — left for follow-up
sessions, each cheap to isolate the same way this one was.

ProfileManager.apply_run_profile (profiles/manager.py:1170-1263):
  - line 1183-1190: "profile not found" IS correctly refuse-before-mutate --
    an early return, nothing touched yet. Confirmed NOT part of this defect.
  - line 1201-1204: unconditionally sets EVERY current room's enabled=False
    across the whole map, BEFORE it has walked the profile's own room list to
    know whether any of them still exist on this map.
  - line 1206-1242: only AFTER that wipe does it discover which profile room
    ids are actually present (applied_room_ids) vs gone (missing_room_ids).
  - line 1258: applied = bool(applied_room_ids) -- so a profile whose EVERY
    referenced room has since been deleted/renumbered returns applied=False,
    but the map's PRE-EXISTING selection was already destroyed as a side
    effect of computing that failure. No rollback exists on this path.
  start_run_profile (line 1265+) calls apply_run_profile first and bails when
  not applied.get("applied") -- so the destructive wipe reaches the orchestration
  layer too, not just the library-apply service in isolation.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_service_refusal_ordering.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.profiles.manager import ProfileManager   # noqa: E402
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket   # noqa: E402

VAC = H.VAC
MAP = "1"


def main() -> int:
    proof = H.Proof("RP-031", "RF-05a ordering: apply_run_profile wipes before authorization")

    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    pm = ProfileManager(mgr)

    bucket = ensure_map_bucket(data=mgr.data, vacuum_entity_id=VAC, map_id=MAP)
    bucket["rooms"] = {
        "1": {
            "room_id": 1, "name": "Kitchen", "enabled": True,
            "profile_name": "vacuum_deep", "clean_mode": "vacuum_mop",
            "fan_speed": "Max", "water_level": "High",
        },
        "2": {
            "room_id": 2, "name": "Living Room", "enabled": True,
            "profile_name": "vacuum_quick", "clean_mode": "vacuum",
            "fan_speed": "Quiet", "water_level": "Off",
        },
    }

    # A saved profile whose only referenced room (id 99) no longer exists on
    # this map -- e.g. the map was re-segmented and rooms renumbered after the
    # profile was saved. Legacy shape: run_profile_steps back-fills "rooms"
    # into a single room_group step automatically (profiles/manager.py:816-820).
    stale_profile = {
        "name": "Weekly Deep Clean",
        "rooms": [{"room_id": 99, "name": "Now-Deleted Room"}],
    }
    library = pm._get_saved_run_profile_store(vacuum_entity_id=VAC, map_id=MAP)
    library["stale-profile-1"] = stale_profile

    result = pm.apply_run_profile(vacuum_entity_id=VAC, map_id=MAP, profile_id="stale-profile-1")

    rooms_after = bucket["rooms"]
    selection_survived = rooms_after["1"]["enabled"] is True and rooms_after["2"]["enabled"] is True

    proof.case(
        "a saved profile whose every referenced room has since been deleted/renumbered",
        before=(result.get("applied") is False and not selection_survived),
        before_msg="apply_run_profile reports applied:False (correctly -- "
                   "nothing in the profile could be applied) but the "
                   "PRE-EXISTING selection (2 enabled rooms with custom "
                   "settings) was already wiped to enabled:False as an "
                   "unconditional first step, with no rollback -- a failed "
                   "apply still destroys the user's prior selection",
        after=(result.get("applied") is False and selection_survived),
        after_msg="the wipe is deferred until AFTER the profile's rooms are "
                  "resolved against the current map (or the wipe is rolled "
                  "back on a fully-failed apply) -- a refusal leaves the "
                  "prior selection exactly as the user left it",
        detail=f"result={result} · room 1 enabled={rooms_after['1']['enabled']} "
               f"· room 2 enabled={rooms_after['2']['enabled']}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
