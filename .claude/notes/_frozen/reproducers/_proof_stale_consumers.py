"""Proof RP-027 (RF-10) — staleness reaches every consumer.

Two cases (of eight finding_ids -- the memory-frame/storage-frame geometry
repoint (POSE-1/GEO-1/POSE-3, required_behavior (4)) is architecturally
deep -- a coordinate-space parity fix across the live-pose reader and its
storage fallback -- and is NOT driven here, time-boxed after four other
packets this session; left for a follow-up pass).

  Hold-path phantom (required_behavior (1), consumer split) --
    _commit_result (map_source_coordinator.py:78-137) holds the last-good
    result through a transient dropout by copying it VERBATIM
    (`held = dict(cached_res)`, line 126) and only stamping stale/
    stale_since/stale_reason -- present stays True and the moving fields
    (current_room, robot_anchor, path) are the FROZEN ones from before the
    dropout. Driven for real: seeds a present result showing the robot in
    "Kitchen", then commits an absent (transient) result for the same
    map_id and reads what the hold path actually returns.
  mtime pose re-serve (required_behavior (3)) --
    _refresh_storage_map_source's cache-hit branch (lines 260-266,
    `if mtime is not None and cached.get("mtime") == mtime: return
    cached["result"]`) returns the cached result UNCHANGED whenever the
    .storage file's mtime hasn't moved -- bypassing _apply_inmem_pose_to_
    result entirely, which is only reached past that early return (line
    284-287). An unchanged file is the COMMON case while the robot moves
    (the fork's .storage write cadence is much coarser than its in-memory
    pose), so the live pose the override exists to apply is silently
    skipped on most cache hits. Driven for real: two calls with the SAME
    mtime, where _read_inmem_pose (a leaf HA-state read, stubbed the same
    class as mocking a vendor service call, not the domain logic under
    test) reports a DIFFERENT live position on the second call.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_stale_consumers.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.mapping.map_source_coordinator import (   # noqa: E402
    MapSourceCoordinator,
)
from custom_components.eufy_vacuum.mapping import map_source_runtime as _msr   # noqa: E402

VAC = H.VAC
MAP = "1"


def main() -> int:
    proof = H.Proof("RP-027", "staleness reaches every consumer")

    # -------------------------------------------------------------------
    # Case 1: a transient dropout re-serves a phantom current_room.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr._map_state_source_cache = {}
    coord = MapSourceCoordinator(manager=mgr)

    present_result = {
        "present": True, "current_room": "Kitchen",
        "robot_anchor": [0.5, 0.5], "path": [[0.1, 0.1], [0.2, 0.2]],
    }
    coord._commit_result(VAC, MAP, present_result)   # a genuine, live-present read

    # the source goes transiently absent (e.g. a Roborock cloud entity idles)
    held = coord._commit_result(VAC, MAP, {"present": False, "reason": "no_parsed_map"})

    proof.case(
        "the map source drops out transiently while the robot was in the Kitchen",
        before=held.get("present") is True and held.get("current_room") == "Kitchen"
        and held.get("stale") is True,
        before_msg="present:True + current_room:'Kitchen' re-served with a "
                   "stale flag NOTHING downstream reads -- a docked/idle "
                   "robot attributes a phantom room at whatever cadence the "
                   "attribution consumer polls",
        after=held.get("current_room") is None and held.get("robot_anchor") is None
        and held.get("path") == [] and held.get("held_static") is True,
        after_msg="the hold nulls the moving fields for the attribution "
                  "surface (current_room=None/robot_anchor=None/path=[]) "
                  "plus held_static=True -- the display surface keeps its "
                  "own frozen-statics path unchanged",
        detail=f"held result: present={held.get('present')} "
               f"current_room={held.get('current_room')!r} stale={held.get('stale')}",
    )

    # -------------------------------------------------------------------
    # Case 2: an unchanged mtime re-serves a frozen live pose.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    mgr2 = H.ManagerStub(hass=hass2)
    mgr2._map_state_source_cache = {}
    coord2 = MapSourceCoordinator(manager=mgr2)

    _orig_store_path = _msr.eufy_store_path
    _orig_load_json = _msr.load_store_json
    _orig_result_from_store = _msr.eufy_result_from_store
    _msr.eufy_store_path = lambda hass_arg, vac, cfg: "/fake/store.json"
    _msr.load_store_json = lambda path: {"data": {"map_data": {"width": 100, "height": 100}}}
    _msr.eufy_result_from_store = lambda store_json, *, expected_version, present: {
        "present": True, "robot_anchor": None,
    }

    poses = iter([
        {"present": True, "robot_pixel": (10, 10), "dock_pixel": None,
         "robot_heading": None, "trail_pixels": None},
        {"present": True, "robot_pixel": (90, 90), "dock_pixel": None,
         "robot_heading": None, "trail_pixels": None},
    ])
    coord2._read_inmem_pose = lambda vac, cfg: next(poses)

    import asyncio

    async def _two_calls():
        cfg = {"backend": "storage", "live_pose": {"robot_pixel_attrs": ["x"]}}
        r1 = await coord2._refresh_storage_map_source(
            vacuum_entity_id=VAC, map_id=MAP, source_cfg=cfg, present=True,
        )
        # same mtime (the fake stat below is patched to a constant) -> a cache hit.
        r2 = await coord2._refresh_storage_map_source(
            vacuum_entity_id=VAC, map_id=MAP, source_cfg=cfg, present=True,
        )
        return r1, r2

    import custom_components.eufy_vacuum.mapping.map_source_coordinator as _msc
    _orig_stat = _msc._stat_mtime
    _msc._stat_mtime = lambda path: 12345.0   # constant -- the file "never changes"
    try:
        r1, r2 = asyncio.run(_two_calls())
    finally:
        _msc._stat_mtime = _orig_stat
        _msr.eufy_store_path = _orig_store_path
        _msr.load_store_json = _orig_load_json
        _msr.eufy_result_from_store = _orig_result_from_store

    proof.case(
        "the robot moves between two snapshots but the .storage file's mtime doesn't",
        before=r1.get("robot_anchor") is not None and r2.get("robot_anchor") == r1.get("robot_anchor"),
        before_msg="the second call's cache hit returns the FIRST call's "
                   "robot_anchor verbatim -- the live pose (robot_pixel "
                   "moved from (10,10) to (90,90)) was never re-applied",
        after=r2.get("robot_anchor") is not None and r2.get("robot_anchor") != r1.get("robot_anchor"),
        after_msg="the cache-hit branch re-applies _apply_inmem_pose_to_result "
                  "before returning -- the cache holds geometry, not the "
                  "pose overlay, so the second call reflects the robot's "
                  "actual current position",
        detail=f"robot_anchor call 1={r1.get('robot_anchor')} · call 2={r2.get('robot_anchor')}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
