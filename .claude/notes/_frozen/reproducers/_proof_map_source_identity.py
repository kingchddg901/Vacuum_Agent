"""Proof RP-026 (RF-09) — LC-3 only: the mtime cache hit omits the map_id check.

ONE case, deliberately -- not the whole packet. RP-026's required_behavior
opens with a VERIFY-FIRST GATE ("before Sonnet assignment, main agent:
confirm on the LIVE fork version that EufyCleanCoordinator carries
device_id... If no deterministic linkage exists, the EUFY half returns to
synthesis"): items (1)/(2)/(4)/(6) (multi-device candidate selection,
roborock candidate/map matching, rejected-candidate walk continuation) all
depend on that unperformed external verification and are NOT driven here.

LC-3 is independent of that gate -- a same-process cache-key bug, not a
multi-device linkage question -- and DELEGATION CHECKED per this session's
standing instruction: "mirror _commit_result's map_id equality check" was
verified against _commit_result itself (map_source_coordinator.py:117,
read in full while materializing RP-027 this session): `cached.get(
"map_id") == str(map_id)  # never serve another map's geometry` is a real,
present check there. _refresh_storage_map_source's OWN cache-hit branch
(same file, lines 260-266) checks mtime + present_gate + result-is-a-dict
but never map_id -- so mirroring is a real gap, not a false delegation.

Concretely: the Eufy fork's .storage file is per-VACUUM, not per-map (it
holds whichever map is currently active), so its mtime does not vary by
which map_id a caller happens to be asking about. Two calls for two
DIFFERENT map ids, close enough together that the file hasn't changed,
legitimately share one mtime -- and the cache-hit branch, having no map_id
check, serves the first map's cached result back for the second's query.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_map_source_identity.py
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


def main() -> int:
    proof = H.Proof("RP-026", "LC-3: mtime cache hit omits the map_id check")
    import asyncio
    import custom_components.eufy_vacuum.mapping.map_source_coordinator as _msc

    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr._map_state_source_cache = {}
    coord = MapSourceCoordinator(manager=mgr)

    _orig_store_path = _msr.eufy_store_path
    _orig_load_json = _msr.load_store_json
    _orig_result_from_store = _msr.eufy_result_from_store
    _orig_stat = _msc._stat_mtime
    # the SAME physical .storage path/mtime regardless of which map_id is
    # asked about -- the real Eufy fork's file is per-vacuum, not per-map.
    _msr.eufy_store_path = lambda hass_arg, vac, cfg: "/fake/store.json"
    _msr.load_store_json = lambda path: {"data": {"map_data": {"width": 10, "height": 10}}}
    _msc._stat_mtime = lambda path: 555.0

    call_n = {"n": 0}

    def _result_from_store(store_json, *, expected_version, present):
        call_n["n"] += 1
        # map A's content, distinguishable from map B's.
        return {"present": True, "map_marker": "MAP_A_CONTENT"}
    _msr.eufy_result_from_store = _result_from_store

    try:
        cfg = {"backend": "storage"}

        async def _two_maps():
            a = await coord._refresh_storage_map_source(
                vacuum_entity_id=VAC, map_id="A", source_cfg=cfg, present=True,
            )
            b = await coord._refresh_storage_map_source(
                vacuum_entity_id=VAC, map_id="B", source_cfg=cfg, present=True,
            )
            return a, b

        result_a, result_b = asyncio.run(_two_maps())
    finally:
        _msc._stat_mtime = _orig_stat
        _msr.eufy_store_path = _orig_store_path
        _msr.load_store_json = _orig_load_json
        _msr.eufy_result_from_store = _orig_result_from_store

    proof.case(
        "map A is queried, then map B, with the SAME mtime (one unchanged file)",
        before=result_b.get("map_marker") == "MAP_A_CONTENT" and call_n["n"] == 1,
        before_msg="the cache-hit branch checks mtime+present_gate only -- "
                   "map B's query returns map A's cached result verbatim "
                   "(the underlying parse never ran a second time), served "
                   "as if it were map B's own geometry",
        after=result_b.get("map_marker") != "MAP_A_CONTENT" or call_n["n"] == 2,
        after_msg="the mtime early-return adds the map_id equality check "
                  "(mirroring _commit_result's own), so a cache entry for a "
                  "DIFFERENT map_id is not treated as a hit -- map B's "
                  "query re-parses rather than inheriting map A's result",
        detail=f"result_a={result_a} · result_b={result_b} · "
               f"eufy_result_from_store call count={call_n['n']}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
