"""Proof RP-030 (batch riders) -- ROBORO-5: two flip_y readers disagree on absence.

ONE case, out of 21 independent one-line findings in this "grouped
independents ... REJECTED as a family" batch -- each site keeps its own
authority, so this proof targets exactly the ROBORO-5 line named in the
packet's own expected_before ("flip_y defaults disagree"). The other 20
members are NOT driven here, each its own unrelated mechanism.

roborock_raw_map.py has two readers of the SAME `decoded` dict's flip_y key,
with two DIFFERENT defaults for when the key is absent:
  - roborock_render_data (line 174): `bool(decoded.get("flip_y", True))`
    -- absent -> True.
  - raster_room_bboxes (line 198): `bool(decoded.get("flip_y"))`
    -- absent -> False (bool(None) is False; no default arg at all).

decode_roborock_v1_segments (the primary decoder) always sets flip_y=True
explicitly, so in practice `decoded` usually carries the key -- the
disagreement only surfaces when SOME OTHER caller hands either function a
decoded dict that omits it (a legacy/alternate decode path, or a hand-built
fixture). raster_room_bboxes' own docstring states the two functions MUST
"land in the SAME rendered frame ... otherwise the two are a whole Y-flip
apart and never overlap" -- exactly the failure this proof demonstrates: the
flip transform (line 218-221) maps a raw-row-0 room to normalized y in
[0.75, 1.0] under flip=True, or y in [0.0, 0.25] under flip=False for a
4-row raster -- opposite quarters, zero overlap.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_flip_y_disagreement.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.mapping.roborock_raw_map import (   # noqa: E402
    roborock_render_data,
    raster_room_bboxes,
)


def main() -> int:
    proof = H.Proof("RP-030", "ROBORO-5: roborock_render_data and raster_room_bboxes disagree on absent flip_y")

    # 4x4 raster; room rid=1 occupies ONLY raw row 0 (indices 0-3). Deliberately
    # NO "flip_y" key -- the disagreement case both functions' docstrings warn
    # against but neither function guards against on its own. "room_ids" IS
    # included (decode_roborock_v1_segments always sets it on real output) so
    # this fixture isn't ALSO tripping the sibling ROBORO-1 fix (a decode with no
    # rooms now reports present:False before flip_y is even considered) --
    # that's a different, unrelated finding this proof doesn't drive.
    decoded = {
        "width": 4,
        "height": 4,
        "room_pixels": bytes([1, 1, 1, 1] + [0] * 12),
        "room_ids": [1],
    }

    render_data = roborock_render_data(decoded, room_names={1: "Kitchen"})
    bboxes = raster_room_bboxes(decoded)
    room1_bbox = bboxes.get(1)

    # render_data's own flip_y says True -> under that reading, raw row 0
    # (the room's actual pixels) should land in the BOTTOM quarter: y in
    # [0.75, 1.0]. raster_room_bboxes silently computed as flip=False instead,
    # which would place the SAME room in the TOP quarter: y in [0.0, 0.25].
    bottom_quarter = room1_bbox is not None and room1_bbox[1] >= 0.75
    top_quarter = room1_bbox is not None and room1_bbox[3] <= 0.25

    proof.case(
        "the SAME decoded raster (flip_y key absent) fed to both readers",
        before=(render_data.get("flip_y") is True and top_quarter and not bottom_quarter),
        before_msg="roborock_render_data reports flip_y=True (its own "
                   "absent-default) while raster_room_bboxes silently computed "
                   "under flip=False (its own, DIFFERENT absent-default) -- "
                   "the room's bbox lands in the TOP quarter of normalized "
                   "space when the reported orientation says it should be in "
                   "the BOTTOM quarter -- 'a whole Y-flip apart', exactly what "
                   "the docstring warns never to let happen",
        after=(render_data.get("flip_y") is True and bottom_quarter and not top_quarter),
        after_msg="a single shared module constant/default backs both "
                  "readers, so an absent flip_y resolves identically "
                  "everywhere -- the bbox lands in the quarter the reported "
                  "orientation actually implies",
        detail=f"render_data.flip_y={render_data.get('flip_y')} · room1_bbox={room1_bbox}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
