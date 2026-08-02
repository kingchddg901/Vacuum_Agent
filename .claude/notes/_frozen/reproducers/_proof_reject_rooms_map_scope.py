"""Proof RP-040 (Q10, the one product item with real required_behavior text) --
setup_reject_rooms has no map scoping, so a room_id collision across maps
destroys the wrong map's room.

ONE case. RP-040 bundles 75 closure-matrix records (59+8+8) across four
batches (SMALL-CORRECTNESS x2, DEAD-CODE, DOC-ONLY) that the packet itself
says come "per its corpus record" from a generated per-file table -- their
individual mechanisms are NOT spelled out in the synthesis packet text
(only short category labels: "A3-IO-5 (path injection)", "A3-IO-7
(fsync)", etc.), so writing a faithful proof for those would mean reading
the audit corpus directly -- against this session's standing instruction
("read packets, not the audit corpus"). Q10 is the one exception: it has
real prose required_behavior in the packet itself ("setup_reject_rooms
requires map_id, routes through the protection/confirmation standard of
the other destructive setup actions, and a setup_unreject_rooms service
reverses it"), so it is the only RP-040 member materialized here. Everything
else in this packet is left undriven -- flagged as a genuine gap in what
one packet-text pass can responsibly cover, not silently skipped.

setup_reject_rooms's schema (services/setup.py:128-133) takes only
vacuum_entity_id + room_ids -- no map_id field exists AT ALL (compare
_delete_map just above it, services/setup.py:255-261, which DOES take a
confirmation_token). The drift module's reject_rooms (setup/drift.py:
438-501) loops `for map_id, bucket in vac_maps.items()` -- EVERY map this
vacuum has -- and strips ANY room whose room_id is in the rejected set from
EVERY one of them (line 482-501). Room ids are small per-map integers
(commonly 1-11), so two different maps very plausibly both have a "room 3"
-- rejecting a phantom room 3 discovered on map A permanently destroys the
LEGITIMATE room 3 on map B too, with zero confirmation (rejected rooms
"never appear... even when discovery re-reports them" per the function's
own docstring -- this is not a transient state).

Also grep-confirmed (not re-verified at runtime, a symbol's absence isn't a
flip): zero matches for "unreject"/"UNREJECT" anywhere in services/setup.py
or const.py -- the required reversal service does not exist at all.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_reject_rooms_map_scope.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.setup.drift import reject_rooms   # noqa: E402

VAC = H.VAC


def main() -> int:
    proof = H.Proof("RP-040", "Q10: setup_reject_rooms has no map_id, so a room_id collision hits every map")

    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr.data["maps"] = {
        VAC: {
            "A": {"rooms": {"3": {"room_id": 3, "name": "Phantom (map A ghost room)"}}},
            "B": {"rooms": {"3": {"room_id": 3, "name": "Real Kitchen (map B, legitimate)"}}},
        }
    }

    # User intent: reject the PHANTOM room 3 that keeps re-appearing on map A.
    # No map_id parameter exists anywhere in the call chain to say so.
    result = reject_rooms(mgr, VAC, [3])

    map_b_room3_survived = "3" in mgr.data["maps"][VAC]["B"].get("rooms", {})

    proof.case(
        "map A and map B both happen to have a room_id=3; the user rejects "
        "map A's phantom room 3",
        before=(not map_b_room3_survived and "B" in result.get("affected_map_ids", [])),
        before_msg="reject_rooms has no map to scope to, so it strips room "
                   "id 3 from EVERY map this vacuum has -- map B's real, "
                   "legitimate Kitchen is destroyed as collateral damage "
                   "from rejecting map A's unrelated phantom, permanently "
                   "(rejected ids never re-surface even on rediscovery)",
        after=(map_b_room3_survived and "B" not in result.get("affected_map_ids", [])),
        after_msg="setup_reject_rooms requires map_id and reject_rooms "
                  "scopes its removal to that one map -- map B's room 3 is "
                  "untouched by a rejection issued against map A",
        detail=f"result={result} · map B room 3 survived={map_b_room3_survived}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
