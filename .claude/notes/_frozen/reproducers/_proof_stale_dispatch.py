"""Proof (RP-007 / #7:DQ-ACT-1, DQ-DE-1): when live slug-resolution TOTALLY misses —
the map was re-segmented and no stored slug exists on it any more — dispatch falls
back to the STALE stored segment ids and cleans whatever rooms now wear those numbers.

Drives the real _resolve_live_dispatch_payload (dispatch/manager.py) with a stubbed
room source. Two cases:
  total miss : stored slugs kitchen/den; live map has neither  -> stale ids on the wire
  partial    : live map has kitchen only                       -> den skipped (correct)

Run: docker eufy-vacuum-test -> python .claude/notes/_proof_stale_dispatch.py
"""
import asyncio
import sys
from types import SimpleNamespace

import custom_components.eufy_vacuum.dispatch.manager as dm
import custom_components.eufy_vacuum.rooms.source_refresh as source_refresh
import custom_components.eufy_vacuum.rooms.room_discovery as room_discovery

VAC = "vacuum.ivy"
STORED_PAYLOAD = {"segments": [5, 7], "repeat": 1}       # ids from the OLD segmentation
STORED_ROOMS = [{"room_id": 5, "slug": "kitchen"}, {"room_id": 7, "slug": "den"}]


async def run_case(mgr, live_rooms):
    async def fake_refresh(hass, entity_id, **kw):
        return {"ok": True}

    def fake_discover(hass, *, vacuum_entity_id, map_id):
        return live_rooms

    source_refresh.async_refresh_room_source = fake_refresh
    room_discovery.discover_rooms_for_vacuum = fake_discover
    try:
        return await mgr._resolve_live_dispatch_payload(
            vacuum_entity_id=VAC, map_id="Main floor",
            payload=dict(STORED_PAYLOAD), resolved_rooms=STORED_ROOMS,
        )
    except Exception as err:                              # repaired code refuses
        return err


async def main() -> int:
    dm._get_adapter_config = lambda _vac: {
        "dispatch": {"resolve_live_ids_by_slug": True, "rooms_field": "segments"}
    }
    mgr = dm.DispatchManager(manager=SimpleNamespace(hass=SimpleNamespace(data={})))
    rc = 0

    # --- case 1: TOTAL miss (re-segmented map, all-new slugs) -----------------
    out = await run_case(mgr, [{"room_id": 3, "slug": "studio"},
                               {"room_id": 4, "slug": "loft"}])
    if isinstance(out, Exception):
        print(f"total miss refused: {out}")
    elif out.get("segments") == STORED_PAYLOAD["segments"]:
        print(f"total miss dispatched stored ids: {out['segments']} "
              "(rooms 5 and 7 of the NEW segmentation are whatever the vendor "
              "renumbered there — the wrong rooms get cleaned)")
    else:
        print(f"UNEXPECTED SHAPE (total miss): {out}")
        rc = 1

    # --- case 2: partial miss (kitchen survives as live id 12) ----------------
    out = await run_case(mgr, [{"room_id": 12, "slug": "kitchen"},
                               {"room_id": 13, "slug": "attic"}])
    if isinstance(out, Exception):
        print(f"UNEXPECTED refusal on partial miss: {out}")
        rc = 1
    elif out.get("segments") == [12]:
        print("partial miss skipped den (unmatched slug dropped, kitchen "
              "re-resolved 5->12) — correct either way")
        print("partial miss skipped B")
    else:
        print(f"UNEXPECTED SHAPE (partial): {out}")
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
