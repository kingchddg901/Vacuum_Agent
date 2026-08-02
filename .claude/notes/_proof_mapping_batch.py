"""Proof RP-030 (mapping small-correctness batch) — two of the three named members.

RP-030 is 21 grouped independents, explicitly "REJECTED as a family — each site keeps its
own authority". Its expected_before names three: off-grid clamped to edge, zero-room raster
present:true, flip_y defaults disagree. The third is already driven by
`_proof_flip_y_disagreement.py`; this drives the other two. The remaining 18 members are
each their own unrelated mechanism and are not driven here.

Table-driven per the packet's reproducer_script — each case prints its finding id and the
before/after fragment.

  GEO-3/POSE-7 — OFF-GRID IS CLAMPED, NOT REJECTED. normalize_rendered runs both axes
    through _clamp01, so a pixel outside the grid comes back as a valid-looking point on
    the border. A pose that is off the map is indistinguishable from a robot parked
    against the wall, and the card's own decoder REJECTS off-grid — so the two ends of the
    same pipeline disagree about what a coordinate means. Silence is the damage: nothing
    surfaces that the input was outside the grid at all.

  ROBORO-1 — A RASTER THAT DECODED NO ROOMS IS REPORTED PRESENT. roborock_render_data
    gates on room_pixels/width/height and returns present:True without consulting the
    decode's own room_ids signal, which is right there in the same dict. The card is handed
    a map with dimensions and no rooms and renders it as real. decode already knows;
    nothing asks it.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_mapping_batch.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.mapping.map_source import (   # noqa: E402
    normalize_rendered,
)
from custom_components.eufy_vacuum.mapping.roborock_raw_map import (   # noqa: E402
    roborock_render_data,
)

W = HGT = 100

# (label, px, py) — every row is outside the 100x100 grid on at least one axis.
OFF_GRID = [
    ("50 px past the right edge", 150.0, 50.0),
    ("20 px above the top edge", 50.0, -20.0),
    ("off on both axes at once", -10.0, 999.0),
]


def case_off_grid_clamped(proof: H.Proof) -> None:
    results = {label: normalize_rendered(px, py, W, HGT) for label, px, py in OFF_GRID}
    # In-grid control: the legitimate path must keep working after the repair.
    control = normalize_rendered(25.0, 25.0, W, HGT)

    def in_unit_box(pt):
        return pt is not None and all(0.0 <= v <= 1.0 for v in pt)

    proof.case(
        "GEO-3/POSE-7 — three off-grid pixels normalized against a 100x100 grid",
        before=all(in_unit_box(v) for v in results.values()) and in_unit_box(control),
        before_msg="off-grid clamped to edge — every out-of-bounds point comes back as a "
                   "valid-looking coordinate on the border, so a pose off the map is "
                   "indistinguishable from a robot against the wall, and nothing "
                   "surfaces that the input was outside the grid",
        after=all(v is None for v in results.values()) and in_unit_box(control),
        after_msg="off-grid rejected (None), matching the card decoder's convention; the "
                  "in-grid control still normalizes",
        detail=" · ".join(f"{k}->{v}" for k, v in results.items())
        + f" · CONTROL in-grid (25,25)->{control}",
    )


def case_zero_room_raster_reported_present(proof: H.Proof) -> None:
    decoded = {
        "room_pixels": bytes(W * HGT),   # a full-size raster...
        "width": W, "height": HGT,
        "room_ids": [],                  # ...that decoded NO rooms. decode already knows.
        "res": 50,
    }
    render = roborock_render_data(decoded, {}, version="proof")
    present = bool((render or {}).get("present"))
    reason = (render or {}).get("reason")

    proof.case(
        "ROBORO-1 — a full-size raster whose decode found zero rooms",
        before=present and not reason,
        before_msg="zero-room raster present:true — the gate checks pixels and "
                   "dimensions and never consults the decode's own room_ids, so the card "
                   "is handed a map with size and no rooms and renders it as real",
        after=not present and reason == "no_rooms",
        after_msg="absent with reason no_rooms — the signal decode already produced is "
                  "consumed instead of ignored",
        detail=f"decoded room_ids={decoded['room_ids']} · render present={present!r} "
               f"· reason={reason!r} · render keys="
               f"{sorted(render) if isinstance(render, dict) else render!r}",
    )


def main() -> None:
    proof = H.Proof("RP-030", "mapping batch — off-grid clamping, zero-room raster")
    case_off_grid_clamped(proof)
    case_zero_room_raster_reported_present(proof)
    proof.finish()


H.run(main)
