"""Proof RP-030 (mapping small-correctness batch) — pure-function members driven here.

RP-030 is 21 grouped independents, explicitly "REJECTED as a family — each site keeps its
own authority". This file drives every member that is a PURE function fix in map_source.py /
map_source_runtime.py / roborock_raw_map.py. Three members are deliberately NOT driven here:

  - ROBORO-5 (flip_y default disagreement) has its OWN dedicated, already-frozen proof at
    .claude/notes/_frozen/reproducers/_proof_flip_y_disagreement.py.
  - EXT-4 (room_outline offset sign) was investigated and found to already be CORRECTLY
    implemented (the packet's claim was stale) — no code change, so no case.
  - POSE-6 (resolve_furnished_render's map-geometry-version limitation) is adjudicated
    DOC-ONLY (docstring caveat, no behavior change) — nothing to prove behaviorally.

The remaining ~6 members that land in mapping_services.py / tracker.py (FURNIS-3/5/6,
IMAGE--9/11, TRK-6) are handler-level and HA-coupled; they are verified via the regular
pytest integration suite (tests/integration/test_mapping_furnished_render.py,
test_mapping_services.py, test_mapping_tracker_events.py), not this pure-function harness.

Table-driven per the packet's reproducer_script — each case prints its finding id and the
before/after fragment.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_mapping_batch.py
"""

from __future__ import annotations

import base64
import struct
import sys
from types import SimpleNamespace

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.mapping.map_source import (   # noqa: E402
    mapdata_dict_from_obj,
    normalize_rendered,
    rooms_from_room_pixels,
    zone_membership,
)
from custom_components.eufy_vacuum.mapping.map_source_runtime import (   # noqa: E402
    _walk,
)
from custom_components.eufy_vacuum.mapping import map_source_runtime as _msr   # noqa: E402
from custom_components.eufy_vacuum.mapping.roborock_raw_map import (   # noqa: E402
    decode_roborock_v1_segments,
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
    """GEO-3/POSE-7 — off-grid rejected via the new opt-in reject_out_of_grid=True,
    while the DEFAULT (unset) behavior every other caller relies on stays clamped —
    see test_map_source.py::test_normalize_rendered for the default-preserving pin."""
    results = {
        label: normalize_rendered(px, py, W, HGT, reject_out_of_grid=True)
        for label, px, py in OFF_GRID
    }
    # In-grid control: the legitimate path must keep working after the repair.
    control = normalize_rendered(25.0, 25.0, W, HGT, reject_out_of_grid=True)

    def in_unit_box(pt):
        return pt is not None and all(0.0 <= v <= 1.0 for v in pt)

    proof.case(
        "GEO-3/POSE-7 — three off-grid pixels, opted into reject_out_of_grid",
        before=all(in_unit_box(v) for v in results.values()) and in_unit_box(control),
        before_msg="off-grid clamped to edge — every out-of-bounds point comes back as a "
                   "valid-looking coordinate on the border, so a pose off the map is "
                   "indistinguishable from a robot against the wall, and nothing "
                   "surfaces that the input was outside the grid",
        after=all(v is None for v in results.values()) and in_unit_box(control),
        after_msg="off-grid rejected (None) once the caller opts in via "
                  "reject_out_of_grid=True, matching the card decoder's convention; the "
                  "in-grid control still normalizes",
        detail=" · ".join(f"{k}->{v}" for k, v in results.items())
        + f" · CONTROL in-grid (25,25)->{control}",
    )


def case_room_bbox_extent_matches_width_m(proof: H.Proof) -> None:
    """GEO-5 — a room's bbox extent (in metres) must agree with its own width_m/
    height_m, not undercount them by one cell."""
    w = h = 10
    buf = bytearray(w * h)
    for py in range(0, 3):          # 3x3 block at px[0,2] x py[0,2]
        for px in range(0, 3):
            buf[py * w + px] = (1 << 2)
    md = {
        "width": w, "height": h, "resolution": 5,
        "room_outline_width": w, "room_outline_height": h,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
        "room_names": {"1": "Kitchen"},
        "room_pixels": base64.b64encode(bytes(buf)).decode(),
    }
    room = rooms_from_room_pixels(md)[0]
    bbox = room["bbox"]
    bbox_width_m = round((bbox[2] - bbox[0]) * w * 5 / 100.0, 2)
    bbox_height_m = round((bbox[3] - bbox[1]) * h * 5 / 100.0, 2)

    proof.case(
        "GEO-5 — room bbox extent vs width_m/height_m for a 3x3-cell room",
        before=bbox_width_m != room["width_m"] or bbox_height_m != room["height_m"],
        before_msg="bbox's own extent undercounts by exactly one cell versus "
                   "width_m/height_m's (max-min+1)-cell convention -- the two "
                   "disagree on the same room's real-world size",
        after=bbox_width_m == room["width_m"] and bbox_height_m == room["height_m"],
        after_msg="bbox extends to the far edge of the max-index cell on each axis, "
                  "so its own extent now agrees with width_m/height_m exactly",
        detail=f"bbox={bbox} · bbox_width_m={bbox_width_m} · width_m={room['width_m']} "
               f"· bbox_height_m={bbox_height_m} · height_m={room['height_m']}",
    )


def case_zone_membership_samples_cell_center(proof: H.Proof) -> None:
    """GEO-6 — zone_membership's floor-dominance walk must sample the CELL CENTER
    (this is the function's own docstring claim), not its raster corner. A single-cell
    room whose CORNER falls just outside a tight zone polygon, but whose CENTER falls
    inside, is only counted under the center convention."""
    w = h = 10
    buf = bytearray(w * h)
    buf[5 * w + 5] = (1 << 2)        # one room-1 cell at (px=5, py=5)
    md = {
        "width": w, "height": h, "resolution": 10,
        "room_outline_width": w, "room_outline_height": h,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
        "room_pixels": base64.b64encode(bytes(buf)).decode(),
    }
    # normalize_rendered(5,5,10,10) (the CORNER) = (0.5, 0.4); the CELL CENTER is
    # (0.55, 0.45). This tight box contains the center but NOT the corner.
    tight = [[0.51, 0.41], [0.60, 0.41], [0.60, 0.50], [0.51, 0.50]]
    result = zone_membership(md, tight)

    proof.case(
        "GEO-6 — a single-cell room whose CENTER (not corner) falls inside a tight zone",
        before=result["room_number"] is None,
        before_msg="the corner-sampled point (0.5, 0.4) falls just outside the tight "
                   "polygon, so the room contributes 0 floor cells and files as "
                   "Unassigned -- contradicting the docstring's own CENTER claim",
        after=result["room_number"] == 1,
        after_msg="the cell CENTER (0.55, 0.45) falls inside the tight polygon, so "
                  "the room is correctly counted and filed",
        detail=f"result={result}",
    )


def case_correspondences_reject_out_of_grid(proof: H.Proof) -> None:
    """GEO-4/RB-8 — correspondences_from_mapdata's own docstring claims 'bad/clamped
    corners are simply skipped'; prove a corner that projects OUTSIDE the image is
    actually excluded now, not silently accepted as a clamped edge point."""

    class _FP:
        def __init__(self, x, y):
            self.x, self.y = x, y

    class _Dims:
        rotation = 0

        def to_img(self, pt):
            return _FP(pt.x, pt.y)   # identity — pt.x=9999 projects WAY outside the image

    class _Room:
        def __init__(self, x0, y0, x1, y1):
            self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    class _MapData:
        image = SimpleNamespace(dimensions=_Dims(), data=SimpleNamespace(size=(100, 100)))
        rooms = {1: _Room(10, 10, 9999, 50)}   # one corner (9999, *) is far off-image

    corr = _msr.correspondences_from_mapdata(_MapData())
    off_grid_corner_present = any(mmx == 9999.0 for _, _, mmx, _ in corr)

    proof.case(
        "GEO-4/RB-8 — one room corner projects outside the image",
        before=off_grid_corner_present,
        before_msg="proj clamps unconditionally with no out-of-range signal, so the "
                   "off-grid corner is accepted as a clamped edge point and would feed "
                   "the affine fit a corrupted data point -- contradicting the "
                   "function's own docstring claim that clamped corners are skipped",
        after=not off_grid_corner_present,
        after_msg="the off-grid corner is detected (its raw pre-clamp projection falls "
                  "outside [0,1]) and skipped, making the docstring's claim true",
        detail=f"correspondences={corr}",
    )


def case_mapdata_dict_missing_geometry_returns_none(proof: H.Proof) -> None:
    """EXT-3 — mapdata_dict_from_obj must refuse (None) when a REQUIRED geometry field
    is missing, not silently return a partial dict that LOOKS usable (carries
    room_pixels) but can never feed the decoders."""
    obj = SimpleNamespace(
        room_pixels=b"\x01\x02\x03\x04",
        width=10, height=10, resolution=5,
        origin_x=0, origin_y=0,
        # room_outline_width / room_outline_height DELIBERATELY omitted --
        # _outline_geometry hard-requires both.
        room_names={},
    )
    result = mapdata_dict_from_obj(obj)

    proof.case(
        "EXT-3 — MapData object missing room_outline_width/height",
        before=result is not None and isinstance(result, dict) and "room_pixels" in result,
        before_msg="a partial dict is returned (has room_pixels, no requiredness "
                   "check beyond that) -- looks usable but _outline_geometry can "
                   "never resolve it, so it silently degrades to no-rooms everywhere "
                   "downstream instead of being recognized as unusable up front",
        after=result is None,
        after_msg="refused (None) up front, matching the room_pixels-missing "
                  "refusal path right next to it -- the caller falls back to "
                  ".storage instead of caching a dead-on-arrival dict",
        detail=f"result={result!r}",
    )


def case_walk_descends_into_slots_object(proof: H.Proof) -> None:
    """RB-7 — _walk (and _structure_tree) must descend into a __slots__ object: it has
    no __dict__, so the walk used to treat it as an opaque leaf and never find data
    nested inside it, regardless of depth budget."""

    class _SlottedRoom:
        __slots__ = ("x0", "y0", "x1", "y1")

        def __init__(self):
            self.x0, self.y0, self.x1, self.y1 = 0, 0, 1, 1

    class _SlottedHolder:
        __slots__ = ("rooms",)

        def __init__(self, rooms):
            self.rooms = rooms

    root = _SlottedHolder({"1": _SlottedRoom()})
    hit, path = _walk(root, lambda o: isinstance(o, _SlottedRoom))

    proof.case(
        "RB-7 — a target object nested inside a __slots__ holder",
        before=hit is None,
        before_msg="the holder has no __dict__, so the walk treats it as a leaf and "
                   "never descends into its slots -- the room object is silently "
                   "invisible to the BFS",
        after=hit is not None and isinstance(hit, _SlottedRoom),
        after_msg="the walk falls back to the class's declared __slots__ names when "
                  "__dict__ is absent, so the nested room is found",
        detail=f"hit={hit!r} · path={path!r}",
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


def case_header_len_below_24_rejected(proof: H.Proof) -> None:
    """ROBORO-7 — a v1 IMAGE block's header must be >= 24 bytes (8 fixed prefix + 16
    dims bytes, per this module's own docstring) before its dims quad is read. A
    header_len of 20 (>= the old 16 guard, < the real 24-byte layout) has NO real dims
    field there -- the old guard read PART of data_len and other header bytes as if
    they were top/left/height/width instead of recognizing there's no image geometry."""

    def _u16(v: int) -> bytes:
        return struct.pack("<H", v)

    def _u32(v: int) -> bytes:
        return struct.pack("<I", v)

    hdr = bytearray(20)
    hdr[0:2] = _u16(2)      # block type = IMAGE
    hdr[2:4] = _u16(20)     # header_len = 20 (< the real 24-byte v1 layout)
    hdr[4:8] = _u32(12)     # data_len -- ALSO where the old (header_len-16=4) "top" read lands
    hdr[8:12] = _u32(0)     # arbitrary header bytes the old guard misreads as "left"
    hdr[12:16] = _u32(3)    # ...misread as "height"
    hdr[16:20] = _u32(4)    # ...misread as "width"
    data = bytes([0x0F] * 12)   # 12 pixel bytes (room 1), matching the misread 4x3 "dims"

    map_header = bytearray(20)
    map_header[2:4] = _u16(20)   # map header length -> first block at offset 20
    blob = bytes(map_header) + bytes(hdr) + data

    result = decode_roborock_v1_segments(blob)

    proof.case(
        "ROBORO-7 — a 20-byte IMAGE header (below the real 24-byte v1 layout)",
        before=result is not None and result.get("width") == 4 and result.get("height") == 3,
        before_msg="header_len >= 16 lets the guard read a 'dims quad' out of a header "
                   "that has no real one -- it reads PART of data_len as 'top' and "
                   "other header bytes as left/height/width, decoding a plausible-"
                   "looking (but bogus) 4x3 image instead of recognizing there's no "
                   "image geometry in a 20-byte header",
        after=result is None,
        after_msg="header_len >= 24 (the real v1 layout) correctly refuses -- a "
                  "20-byte header never reaches the IMAGE-block dims read at all",
        detail=f"result={result if result is None else {k: result[k] for k in ('width', 'height', 'top', 'left')}}",
    )


def main() -> None:
    proof = H.Proof(
        "RP-030",
        "mapping batch — off-grid rejection, bbox parity, cell-center sampling, "
        "correspondence rejection, MapData requiredness, __slots__ walk, zero-room "
        "raster, short IMAGE header",
    )
    case_off_grid_clamped(proof)
    case_room_bbox_extent_matches_width_m(proof)
    case_zone_membership_samples_cell_center(proof)
    case_correspondences_reject_out_of_grid(proof)
    case_mapdata_dict_missing_geometry_returns_none(proof)
    case_walk_descends_into_slots_object(proof)
    case_zero_room_raster_reported_present(proof)
    case_header_len_below_24_rejected(proof)
    proof.finish()


H.run(main)
