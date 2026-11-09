"""Unit tests for the Roborock v1 raw-map segment decoder.

Pure decoder (no HA, no device): a synthetic v1 map blob built to the exact
little-endian block structure mirrored from vacuum-map-parser-roborock, plus the
per-pixel resolve table and the malformed-blob guards.

Coverage targets
----------------
[RRD-1]  decode: a well-formed IMAGE block -> resolved room-id raster + dims + ids.
[RRD-2]  resolve_rid: room / inside-catch-all / scan / wall / outside / obstacle-bit collision.
[RRD-3]  decode: a blob with no IMAGE block -> None.
[RRD-4]  decode: empty / truncated / garbage bytes -> None (never raises).
[RRD-5]  decode: IMAGE dims larger than the pixel data -> None; (5b) ROBORO-7: header_len
         below the real 24-byte v1 layout -> None (no bogus dims read out of overlapping fields).
[RRD-6]  render_data: a decoded raster -> the generic room_pixels_v1 render-data shape.
[RRD-7]  render_data: empty / None decoded input -> None; (7b) ROBORO-1: zero-room decode
         (room_ids empty) -> present:False, reason:no_rooms, not a false present:True.
[RRD-8]  render_data_from_candidates: BFS to a MapContent -> decode its raw_api_response.
[RRD-9]  raster_room_bboxes: per-room normalized bbox from the resolved raster.
[RRD-10] geometry_drift: overlay parser vs raster bboxes -> aligned / flip / set-mismatch.
[RRD-12] raster_room_bboxes: flip_y honored -> raw top rows land at the rendered bottom (Ivy).
[RRD-13] A7-ROBORO-4: the decoded IMAGE top/left survive into the payload
         (emitted, not applied — ro_dx/dy stay 0).
[RRD-14] decode: an unwalkable block header STOPS the scan -- the parser refuses to
         resync, even past a block a later valid IMAGE follows.
[RRD-15] decode: a block that makes no forward progress terminates instead of spinning.
[RRD-16] decode: dims that the data cannot satisfy -> None (zero width/height, and
         a pixel count exceeding the block's declared data_len).
[RRD-17] render_data: a caller-supplied `version` is passed through, not re-hashed.
[RRD-18] raster_room_bboxes: an absent or shapeless decode -> {} rather than a raise.
[RRD-19] raster_room_bboxes: flip_y FALSE keeps raw rows where they are -- the other
         half of [RRD-12], and only the pair shows the flip is consulted.
[RRD-20] geometry_drift: a malformed parser room is SKIPPED and the walk continues;
         a non-overlapping pair scores IoU 0.
"""

from __future__ import annotations

import base64
import struct

import pytest

from custom_components.eufy_vacuum.mapping.roborock_raw_map import (
    CATCH_ALL_RID,
    decode_roborock_v1_segments,
    geometry_drift,
    raster_room_bboxes,
    resolve_rid,
    roborock_render_data,
)


def _u16(v: int) -> bytes:
    return struct.pack("<H", v)


def _u32(v: int) -> bytes:
    return struct.pack("<I", v)


def _image_block(width: int, height: int, data: bytes, *, top: int = 0, left: int = 0) -> bytes:
    """A 24-byte IMAGE (type 2) block header + its pixel data, v1 layout."""
    hdr = bytearray(24)
    hdr[0:2] = _u16(2)                       # block type = IMAGE
    hdr[2:4] = _u16(24)                      # header length
    hdr[4:8] = _u32(len(data))               # data length
    hdr[8:12] = _u32(top)                    # image_top   @ header_len-16
    hdr[12:16] = _u32(left)                  # image_left  @ header_len-12
    hdr[16:20] = _u32(height)                # image_height@ header_len-8
    hdr[20:24] = _u32(width)                 # image_width @ header_len-4
    return bytes(hdr) + data


def _blob(*blocks: bytes) -> bytes:
    """A 20-byte map header (map_header_length @ 0x02) followed by the given blocks."""
    header = bytearray(20)
    header[2:4] = _u16(20)                   # map header length -> first block at offset 20
    return bytes(header) + b"".join(blocks)


# Pixel byte helpers: a room-N pixel is (N << 3) | 0x07.
def _room(n: int) -> int:
    return (n << 3) | 0x07


# ---------------------------------------------------------------------------
# [RRD-1] decode a well-formed blob
# ---------------------------------------------------------------------------

def test_decode_wellformed_image_block():
    """[RRD-1] a 4x3 IMAGE block decodes to the resolved room-id raster."""
    data = bytes([
        _room(5), _room(5), _room(6), 0xFF,   # -> 5, 5, 6, 31(catch-all)
        0x01,     0x00,     0x07,     0x08,    # wall, outside, scan, grey-wall -> 0,0,0,0
        _room(5), _room(6), _room(6), 0xFF,    # -> 5, 6, 6, 31
    ])
    out = decode_roborock_v1_segments(_blob(_image_block(4, 3, data)))

    assert out is not None
    assert out["width"] == 4 and out["height"] == 3
    assert out["rid_shift"] == 0 and out["catch_all_rid"] == CATCH_ALL_RID
    assert out["flip_y"] is True
    assert out["room_pixels"] == bytes([5, 5, 6, 31, 0, 0, 0, 0, 5, 6, 6, 31])
    assert out["room_ids"] == [5, 6]          # 31 is the catch-all, not a room


# ---------------------------------------------------------------------------
# [RRD-2] resolve_rid — the per-pixel encoding
# ---------------------------------------------------------------------------

def test_resolve_rid_rooms_and_sentinels():
    """[RRD-2] room = byte>>3 when low-3-bits==7; 0xFF catch-all; scan/wall/outside -> 0."""
    assert resolve_rid(_room(1)) == 1          # 0x0F
    assert resolve_rid(_room(5)) == 5          # 0x2F
    assert resolve_rid(_room(30)) == 30        # 0xF7 — max room
    assert resolve_rid(0xFF) == CATCH_ALL_RID  # MAP_INSIDE -> 31
    assert resolve_rid(0x07) == 0              # MAP_SCAN is NOT a room
    assert resolve_rid(0x01) == 0              # wall
    assert resolve_rid(0x00) == 0              # outside


def test_resolve_rid_obstacle_bit_collision():
    """[RRD-2] the trap: 0x08 has room-bits 1 (0x08>>3) but obstacle-bits 0 -> NOT a room.

    A naive `byte >> 3` would mislabel this grey-wall pixel as room 1; the mask on the
    low 3 bits is what prevents it.
    """
    assert 0x08 >> 3 == 1                       # what a naive shift would say
    assert resolve_rid(0x08) == 0              # obstacle-bits != 7 -> background
    assert resolve_rid(0x09) == 0              # obstacle-bits 1 (wall v2)


# ---------------------------------------------------------------------------
# [RRD-3]/[RRD-4]/[RRD-5] absence + malformed
# ---------------------------------------------------------------------------

def test_decode_no_image_block_is_none():
    """[RRD-3] a blob whose only block isn't an IMAGE block -> None."""
    other = bytearray(8)
    other[0:2] = _u16(5)                        # some non-IMAGE block type
    other[2:4] = _u16(8)                        # header length
    other[4:8] = _u32(0)                        # no data
    assert decode_roborock_v1_segments(_blob(bytes(other))) is None


def test_decode_garbage_is_none_never_raises():
    """[RRD-4] empty / truncated / random bytes -> None, no exception."""
    for junk in (b"", b"\x00", b"\x14\x00", b"\xff\xff\xff\xff", bytes(range(30)), None):
        assert decode_roborock_v1_segments(junk) is None


def test_decode_short_pixel_data_is_none():
    """[RRD-5] IMAGE dims claim more pixels than the data holds -> None."""
    # header says 4x3 = 12 pixels, but only 4 data bytes are present.
    out = decode_roborock_v1_segments(_blob(_image_block(4, 3, bytes([_room(1)] * 4))))
    assert out is None


# ---------------------------------------------------------------------------
# [RRD-6]/[RRD-7] render-data builder (the decode -> frontend-contract bridge)
# ---------------------------------------------------------------------------

def test_render_data_shape():
    """[RRD-6] a decoded raster -> the generic room_pixels_v1 render-data shape."""
    decoded = decode_roborock_v1_segments(_blob(_image_block(4, 3, bytes([_room(5)] * 12))))
    rd = roborock_render_data(decoded, {5: "Kitchen"})

    assert rd["present"] is True and rd["format"] == "room_pixels_v1"
    assert rd["width"] == 4 and rd["height"] == 3
    assert rd["ro_width"] == 4 and rd["ro_height"] == 3 and rd["ro_dx"] == 0 and rd["ro_dy"] == 0
    assert rd["rid_shift"] == 0 and rd["catch_all_rid"] == CATCH_ALL_RID and rd["flip_y"] is True
    assert rd["room_names"] == {"5": "Kitchen"} and rd["version"]
    # the b64 room_pixels round-trips back to the resolved raster
    assert base64.b64decode(rd["room_pixels"]) == decoded["room_pixels"]


def test_render_data_none_input():
    """[RRD-7] empty / None decoded input -> None."""
    assert roborock_render_data(None) is None
    assert roborock_render_data({}) is None
    assert roborock_render_data({"width": 0, "height": 0, "room_pixels": b""}) is None


def test_render_data_zero_rooms_reports_absent():
    """[RRD-7b] ROBORO-1: a full-size raster whose decode found ZERO rooms (room_ids
    empty) reports present:False, reason:no_rooms -- not present:True off pixel
    dims/bytes alone. Driven both via a hand-built decoded dict and via the REAL
    decoder on an all-MAP_SCAN blob (every pixel mid-scan, no room ever assigned)."""
    decoded = {"width": 4, "height": 3, "room_pixels": bytes(12), "room_ids": []}
    rd = roborock_render_data(decoded, {5: "Kitchen"})
    assert rd == {"present": False, "reason": "no_rooms"}

    scan_blob = _blob(_image_block(4, 3, bytes([0x07] * 12)))   # MAP_SCAN everywhere
    scan_decoded = decode_roborock_v1_segments(scan_blob)
    assert scan_decoded["room_ids"] == []
    rd2 = roborock_render_data(scan_decoded, {})
    assert rd2 == {"present": False, "reason": "no_rooms"}


def test_decode_header_len_below_24_no_dims_read():
    """[RRD-5b] ROBORO-7: the v1 layout is 8 fixed prefix bytes + 16 dims bytes == 24
    (per this module's own docstring); a header_len of 20 (below that) has no real
    dims quad -- decode must refuse (None), not read a bogus 'dims' out of overlapping
    header fields."""
    hdr = bytearray(20)
    hdr[0:2] = _u16(2)      # block type = IMAGE
    hdr[2:4] = _u16(20)     # header_len = 20 (< the real 24-byte v1 layout)
    hdr[4:8] = _u32(12)     # data_len
    hdr[8:12] = _u32(0)
    hdr[12:16] = _u32(3)
    hdr[16:20] = _u32(4)
    data = bytes([0x0F] * 12)
    assert decode_roborock_v1_segments(_blob(bytes(hdr) + data)) is None


# ---------------------------------------------------------------------------
# [RRD-8] the introspection bridge (candidates -> MapContent -> decode)
# ---------------------------------------------------------------------------

def test_render_data_from_candidates_finds_raw_blob():
    """[RRD-8] the bridge BFS-walks candidate roots to a MapContent and decodes its raw blob."""
    from custom_components.eufy_vacuum.mapping.map_source_runtime import (
        roborock_render_data_from_candidates,
    )

    class _MapContent:
        def __init__(self, raw):
            self.raw_api_response = raw     # the raw map blob our decoder re-parses
            self.map_data = object()        # the parsed sibling (any non-None)

    class _Home:
        def __init__(self, mc):
            self._map_content = mc

    blob = _blob(_image_block(4, 3, bytes([_room(5)] * 12)))
    rd = roborock_render_data_from_candidates([_Home(_MapContent(blob))], {5: "Kitchen"})
    assert rd["present"] is True and rd["room_names"] == {"5": "Kitchen"}

    # nothing map-content-shaped in the candidates -> absent marker, no raise.
    assert roborock_render_data_from_candidates([object()])["present"] is False


# ---------------------------------------------------------------------------
# [RRD-9]/[RRD-10] overlay the raster against the parser's bboxes (drift check)
# ---------------------------------------------------------------------------

# raster: room 5 top-left, room 6 top-right, 31 (catch-all) + 0 (background) elsewhere.
_DECODED = {"width": 4, "height": 3, "room_pixels": bytes([5, 5, 6, 31, 0, 0, 0, 0, 5, 6, 6, 31])}


def test_raster_room_bboxes():
    """[RRD-9] per-room normalized bbox from the raster's min/max pixel extents."""
    bboxes = raster_room_bboxes(_DECODED)
    assert bboxes == {5: [0.0, 0.0, 0.5, 1.0], 6: [0.25, 0.0, 0.75, 1.0]}


def test_geometry_drift_aligned():
    """[RRD-10] parser bboxes matching the raster -> aligned, IoU 1.0, zero centre drift.

    This is the on-device validator: both sides derive from the SAME segment layer, so a
    correct decode makes the two bboxes coincide.
    """
    parser = [
        {"number": 5, "bbox": [0.0, 0.0, 0.5, 1.0]},
        {"number": 6, "bbox": [0.25, 0.0, 0.75, 1.0]},
    ]
    d = geometry_drift(parser, _DECODED)
    assert d["common"] == [5, 6] and d["aligned"] is True
    assert d["max_center_delta"] == 0.0 and d["min_iou"] == 1.0


def test_geometry_drift_detects_flip_and_mismatch():
    """[RRD-10] a Y-flipped parser bbox surfaces as centre drift; a parser-only room shows in
    the set diff — the two failure modes the overlay is meant to catch."""
    parser = [
        {"number": 5, "bbox": [0.0, 0.5, 0.5, 1.0]},   # room 5 flipped to the bottom
        {"number": 6, "bbox": [0.25, 0.0, 0.75, 1.0]},
        {"number": 9, "bbox": [0.0, 0.0, 0.1, 0.1]},    # a room only the parser sees
    ]
    d = geometry_drift(parser, _DECODED)
    assert d["aligned"] is False
    assert d["only_parser"] == [9] and 9 not in d["common"]
    assert d["per_room"][5]["center_delta"] > 0.1       # the flip reads as drift


def test_geometry_drift_from_candidates_absent():
    """[RRD-10] the on-device wrapper degrades to an absent marker when a candidate yields no
    parsed MapData + raw blob pair — never raises."""
    from custom_components.eufy_vacuum.mapping.map_source_runtime import (
        roborock_geometry_drift_from_candidates,
    )

    assert roborock_geometry_drift_from_candidates([])["present"] is False
    assert roborock_geometry_drift_from_candidates([object()])["present"] is False


def test_raster_bboxes_flip_y():
    """[RRD-12] flip_y honored: a room in the raw TOP rows lands at the rendered BOTTOM, so the
    raster bbox matches the parser's flipped frame. This is the exact Ivy finding — X pixel-exact,
    Y = 1 - parser_y — which without the flip read as a false `aligned: false`."""
    top_room = {
        "width": 4, "height": 3, "flip_y": True,
        "room_pixels": bytes([5, 5, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0]),   # room 5 in the raw TOP row
    }
    b = raster_room_bboxes(top_room)[5]
    assert b[0] == 0.0 and b[2] == 1.0                    # X unchanged by the flip
    assert abs(b[1] - 2 / 3) < 1e-9 and b[3] == 1.0       # raw top row -> rendered bottom

    # a parser bbox at that flipped spot now aligns (was a false mismatch before the fix).
    d = geometry_drift([{"number": 5, "bbox": [0.0, 2 / 3, 1.0, 1.0]}], top_room)
    assert d["aligned"] is True and d["min_iou"] > 0.9


def test_render_data_preserves_the_decoded_image_offset():
    """[RRD-13] A7-ROBORO-4: the IMAGE block's top/left survive into the payload.

    The decoder has always read them (header_len-16 / -12) and the render-data
    builder then dropped them, so nothing downstream could discover that an
    offset between the raw IMAGE frame and the render canvas even existed.

    They are EMITTED, NOT APPLIED — and as of 2026-08-05 that is VERIFIED, not
    deferred. Two independent confirmations, which is the point of running both:

    STRUCTURAL. The overlays never touch raw_top/raw_left. They project through
    `_mapdata_projector` (map_source_runtime.py:509), which calls the parser's OWN
    `ImageDimensions.to_img(point).rotated(dims)` — the transform that ALREADY
    contains the trim offset top/left describes. So top/left is the header's copy
    of a fact applied upstream, and shifting by it here would DOUBLE-apply it.
    Separately, ro_dx/dy are the OUTLINE→main-grid offset (map_source
    ._outline_geometry) — a Eufy concern, where room_pixels lives in its own
    outline frame. Roborock's raster IS the main grid, so 0 is not a placeholder,
    it is the measurement.

    ON-DEVICE. Ivy's live map carries raw_top/raw_left = 281/245 — at 50 mm/px
    that is 12.25 m x 14.05 m, so a real misalignment would throw every overlay
    clean off the map, not subtly askew. Chris enabled every overlay feature and
    confirmed no-go quads, walls, saved zones and the dock/robot anchors all land
    exactly where he drew them. The non-zero offset is what made this a falsifying
    test rather than a vacuous one: on a map where top/left are 0, applying and
    not applying are indistinguishable.

    The eye says the output is right; the structure says WHY it is right. Keep
    both — the second is what survives the next refactor.
    """
    decoded = decode_roborock_v1_segments(
        _blob(_image_block(4, 3, bytes([_room(5)] * 12), top=17, left=42))
    )
    assert decoded["top"] == 17 and decoded["left"] == 42

    rd = roborock_render_data(decoded, {5: "Kitchen"})
    assert rd["raw_top"] == 17
    assert rd["raw_left"] == 42
    # unchanged, deliberately: nothing about the render moved.
    assert rd["ro_dx"] == 0 and rd["ro_dy"] == 0
    assert rd["width"] == 4 and rd["ro_width"] == 4


# ---------------------------------------------------------------------------
# [RRD-14] - [RRD-20]  the malformed-blob guards, the un-flipped half, and the
# parser-overlay walk.
#
# This file is a PURE decoder's test file, which is why these are cheap: no HA, no
# device, no fixtures -- a synthetic blob built to the exact little-endian layout.
# ---------------------------------------------------------------------------


def _unwalkable_block(header_len: int, data_len: int) -> bytes:
    """A non-IMAGE block whose declared header_len the walker cannot trust.

    `data_len` IS NOT COSMETIC. The walker advances by `data_len + (header_len &
    0xFF)`, so it decides where the walk lands if the break is ever removed -- and
    therefore whether a test of the break can tell the two spellings apart."""
    hdr = bytearray(8)
    hdr[0:2] = _u16(99)             # some type that is not IMAGE
    hdr[2:4] = _u16(header_len)     # the value under test
    hdr[4:8] = _u32(data_len)
    return bytes(hdr)


def test_rrd14_an_unwalkable_header_stops_the_scan():
    """[RRD-14] The parser BAILS on a header it cannot walk; it does not resync.

    A blob whose block chain cannot be followed is not partially trusted. Resyncing
    to "the next thing that looks like an IMAGE header" would read dims out of
    whatever bytes happened to align.

    ⚠ `data_len=4` IS THE WHOLE TEST, AND AN EARLIER DRAFT HAD IT AT 0. The walker
    advances by `data_len + (header_len & 0xFF)` == `4 + 4` == 8, which is exactly
    this bad block's length -- so with the break removed the walk lands cleanly on
    the trailing IMAGE and decodes it. Measured: ablated DECODED, unablated None.

    WITH data_len=0 THE STEP IS 4 AND THE ABLATION CHANGES NOTHING -- the walk lands
    misaligned mid-header, finds no IMAGE, and returns None either way. That variant
    is SUBSUMED, and so is a header_len that overruns the blob (999): there the
    ablated walk reads the dims quad out of range and the `except (IndexError,
    ValueError)` net returns None, the same answer. Both were in an earlier draft of
    this test as parametrised rows, and the sweep read them DEAD.

    THE LESSON IS ABOUT THE PROBE, NOT THE CODE. I had checked that the blob WITH a
    bad header returns None while the blob WITHOUT one decodes, and read that as the
    guard biting. It is not the ablation: comparing two INPUTS says nothing about
    whether removing the GUARD changes the answer.

    RED: delete the `break`; the walk steps 8 bytes onto the valid block and decodes.
    """
    good = _image_block(2, 2, bytes([_room(1), _room(1), _room(2), _room(2)]))

    # The positive control FIRST, so a None below cannot be mistaken for "this blob was
    # never decodable".
    assert decode_roborock_v1_segments(_blob(good)) is not None, (
        "precondition: the trailing block must be decodable on its own"
    )

    # header_len 4 trips the < 8 test; data_len 4 makes the step land on `good`.
    blob = _blob(_unwalkable_block(4, 4) + good)
    assert decode_roborock_v1_segments(blob) is None


def test_rrd15_a_block_with_no_forward_progress_terminates():
    """[RRD-15] A zero-length step ends the walk instead of spinning on it forever.

    `step = data_len + the int8 at header[0x02]`, and both terms are unsigned -- so the
    only way to reach `step <= 0` is for BOTH to be zero. That needs a header_len whose
    LOW byte is zero (the int8 the walker re-reads) and a zero data_len, i.e. header_len
    256 here: large enough to pass the >= 8 test, and `256 & 0xFF == 0`.

    ⚠ THE RED INPUT IS NON-TERMINATION, NOT A FAILING ASSERTION, and that is recorded
    rather than smoothed over. With the `break` removed, `pos += 0` forever and this
    test never completes -- so it is DELIBERATELY EXCLUDED from the ablation sweep,
    which would stall on it rather than report it. Verified once, out of band, with a
    bounded timeout. A guard whose only alternative is a hang cannot be proven by a
    harness that waits for an exit code, and saying so is more honest than pretending
    the sweep covers it.
    """
    stuck = bytearray(256)
    stuck[0:2] = _u16(99)
    stuck[2:4] = _u16(256)          # low byte 0 -> the walker's step contribution is 0
    stuck[4:8] = _u32(0)            # data_len 0
    good = _image_block(2, 2, bytes([_room(1)] * 4))

    # Reaching this line at all is the assertion.
    assert decode_roborock_v1_segments(_blob(bytes(stuck) + good)) is None


def _truncated_image_block(width: int, height: int, present: int) -> bytes:
    """An IMAGE block whose DECLARED data_len is honest about the dims but whose
    bytes run out early -- a truncated transfer rather than a malformed header.

    `_image_block` cannot express this: it derives data_len from the data it is
    given, so the dims and the declaration always agree."""
    hdr = bytearray(24)
    hdr[0:2] = _u16(2)
    hdr[2:4] = _u16(24)
    hdr[4:8] = _u32(width * height)      # DECLARED: enough for the dims
    hdr[8:12] = _u32(0)
    hdr[12:16] = _u32(0)
    hdr[16:20] = _u32(height)
    hdr[20:24] = _u32(width)
    return bytes(hdr) + bytes(present)   # PRESENT: fewer


@pytest.mark.parametrize("block", [
    pytest.param(_image_block(0, 2, b"\x00" * 4), id="zero_width"),
    pytest.param(_image_block(2, 0, b"\x00" * 4), id="zero_height"),
    pytest.param(_image_block(4, 4, b"\x00" * 4), id="pixels_exceed_data_len"),
    pytest.param(_truncated_image_block(4, 4, 4), id="data_runs_past_the_blob"),
])
def test_rrd16_dims_the_data_cannot_satisfy_decode_to_none(block):
    """[RRD-16] A dims quad the block's own data_len cannot back is refused.

    TWO ADJACENT GUARDS, THREE LINES APART, AND THEY READ IDENTICALLY. The first
    three rows trip the arithmetic test -- dims the block's OWN declared `data_len`
    cannot back. The fourth trips its neighbour: a `data_len` honest about the dims
    while the BLOB runs out of bytes, i.e. a truncated transfer rather than a
    malformed header.

    ⚠ THE FOURTH ROW EXISTS BECAUSE I AIMED AT ONE GUARD AND HIT IT. An earlier
    draft of this docstring had the pair BACKWARDS -- it said [RRD-5] tripped the
    later guard, so the first three rows were written as the earlier test and the
    later one was left open. Measured: [RRD-5] reaches the ARITHMETIC guard, and the
    blob-overrun return stayed uncovered until the fourth row was added. Checking the
    guard you aimed at says nothing about its shoulder.

    A zero dimension is the shape worth having among the first three: it would
    otherwise hand the renderer a zero-area raster and a `width * height == 0` pixel
    slice that looks like a successful decode of nothing.

    ⚠ `pixels_exceed_data_len` IS SUBSUMED and is kept as documentation, not as a
    claim: with the arithmetic guard removed it falls straight into the overrun guard
    below and returns None anyway. Measured DEAD. Only the two zero-dim rows pin the
    arithmetic guard; only the fourth row pins the overrun guard.

    RED: delete `if width <= 0 or height <= 0 or pixel_count > data_len` and the first
    three rows decode a 0 dimension or a short slice; delete `if data_start +
    pixel_count > n` and the fourth decodes a raster shorter than its own dims claim.
    """
    assert decode_roborock_v1_segments(_blob(block)) is None


def test_rrd17_a_supplied_version_is_passed_through_not_rehashed():
    """[RRD-17] The caller's `version` wins; the content hash is only the fallback.

    The hash exists so a raster with no upstream version still gets a stable identity
    the card can cache against. A caller that HAS a real version -- a map id, a
    coordinator sequence -- must not have it silently replaced by a digest, because two
    different maps that happen to hold identical pixels would then collide.

    THE PAIR IS THE POINT: the fallback half is asserted in the same test, because
    "returns what I passed" holds trivially for an implementation that ignores the
    parameter in BOTH directions only if the hash is never exercised.

    RED: drop the `if version is None` test and hash unconditionally -- the supplied
    value is discarded.
    """
    decoded = decode_roborock_v1_segments(
        _blob(_image_block(2, 2, bytes([_room(1), _room(1), _room(2), _room(2)])))
    )
    assert decoded is not None

    supplied = roborock_render_data(decoded, version="map-7-seq-42")
    assert supplied["version"] == "map-7-seq-42"

    hashed = roborock_render_data(decoded)
    assert hashed["version"] != "map-7-seq-42"
    assert len(hashed["version"]) == 12, hashed["version"]


@pytest.mark.parametrize("decoded", [
    pytest.param(None, id="absent"),
    pytest.param({}, id="empty"),
    pytest.param({"width": 2, "height": 2}, id="no_room_pixels"),
    pytest.param({"room_pixels": b"\x01", "height": 2}, id="no_width"),
    pytest.param({"room_pixels": b"\x01", "width": 2}, id="no_height"),
])
def test_rrd18_a_shapeless_decode_yields_no_bboxes(decoded):
    """[RRD-18] `{}`, never a raise and never a partial box.

    This runs on the diagnostics path beside `geometry_drift`, which calls it
    unconditionally -- so a raise here would take down a self-validator whose entire
    job is to report that something is wrong.

    RED: delete the first guard and the `absent` row raises AttributeError on
    `None.get`; delete the second and the three shapeless rows raise on `i % w` or on
    iterating None.

    ⚠ THE `empty` ROW IS MUTUALLY SUBSUMED, measured DEAD against BOTH ablations.
    `{}` is falsy, so the first guard answers it -- and with that guard gone,
    `{}.get("room_pixels")` is None and the second guard answers it. Neither pins it,
    and it is kept because `{}` is the shape a caller actually passes.
    """
    assert raster_room_bboxes(decoded) == {}


def test_rrd19_flip_y_false_keeps_raw_rows_where_they_are():
    """[RRD-19] The other half of [RRD-12], and the pair is what proves flip is read.

    [RRD-12] pins that a raw TOP row lands at the rendered BOTTOM when `flip_y` is true
    (the Ivy finding). On its own that is satisfiable by an implementation that flips
    unconditionally. This asserts the same raster with `flip_y` FALSE keeps its rows,
    and asserts the two results DIFFER -- which is the only thing that shows the key is
    consulted rather than hardcoded.

    RED: collapse the `if flip:` arms to either branch, and one of the two assertions
    below fails.
    """
    decoded = decode_roborock_v1_segments(
        _blob(_image_block(2, 2, bytes([_room(1), _room(1), _room(2), _room(2)])))
    )
    assert decoded is not None and decoded["flip_y"] is True

    flipped = raster_room_bboxes(decoded)
    straight = raster_room_bboxes({**decoded, "flip_y": False})

    # Room 1 occupies raw row 0. Un-flipped it stays at the TOP of the frame (min_y 0);
    # flipped it belongs at the BOTTOM (max_y 1).
    assert straight[1] == [0.0, 0.0, 1.0, 0.5], straight
    assert flipped[1] == [0.0, 0.5, 1.0, 1.0], flipped
    assert straight != flipped, "the flip_y key was not consulted"


def test_rrd20_a_malformed_parser_room_is_skipped_and_the_walk_continues():
    """[RRD-20] Bad rows are dropped individually; one does not end the overlay.

    `geometry_drift` is a SELF-VALIDATOR -- it exists to report that a decode and the
    vendor parser disagree. A malformed row in the parser's output must therefore cost
    that row and nothing else; aborting the walk would report "nothing to compare",
    which reads as agreement rather than as a problem.

    EVERY BAD ROW IS DECLARED BEFORE THE GOOD ONE, and that ordering is load-bearing --
    do not tidy it. With the good room last, a `break` in place of the skip drops it
    from `common` and the assertion fails; with the good room first, both spellings
    produce identical output and the test cannot tell them apart. The three bad shapes
    cover the two distinct skip paths: the shape test (not a dict / no number / bbox
    not a 4-list) and the coercion failure inside the `try`.

    IoU 0 IS ASSERTED ON THE SAME RUN: room 1's parser box sits in the top tenth of the
    frame while its raster box is the bottom half, so they share no area at all, and
    `aligned` must be False -- a self-validator that reported alignment for disjoint
    boxes would be worse than silent.

    ⚠ THAT ASSERTION DOES NOT PIN `_bbox_iou`'S `if inter <= 0: return 0.0`, and the
    short-circuit is SUBSUMED: with it deleted the general formula computes
    `0 / (area_a + area_b)` == 0.0 and the union guard below catches the degenerate
    case, so no input distinguishes them. Measured DEAD. It is an early return, not a
    behavioural guard, and the assertion above is about the OUTCOME being 0.0 rather
    than about which line produced it.

    RED: turn either skip into a `break` and room 2 vanishes from `common`.
    """
    decoded = decode_roborock_v1_segments(
        _blob(_image_block(2, 2, bytes([_room(1), _room(1), _room(2), _room(2)])))
    )
    assert decoded is not None

    parser_rooms = [
        "not a dict",                                    # shape test: not a dict
        {"number": None, "bbox": [0.0, 0.0, 1.0, 1.0]},  # shape test: no number
        {"number": 9, "bbox": [0.0, 0.0]},               # shape test: bbox not a 4-list
        {"number": 8, "bbox": ["nope", 0.0, 1.0, 1.0]},  # coercion failure -> continue
        {"number": 1, "bbox": [0.0, 0.0, 0.1, 0.1]},     # GOOD, and deliberately LAST
        {"number": 2, "bbox": [0.0, 0.0, 1.0, 0.5]},     # GOOD
    ]

    drift = geometry_drift(parser_rooms, decoded)

    assert drift["room_ids_parser"] == [1, 2], drift["room_ids_parser"]
    assert drift["common"] == [1, 2], (
        "a malformed row ended the walk instead of being skipped: %s" % drift
    )
    # Room 1: parser says the top tenth, the raster says the bottom half -> no overlap.
    assert drift["per_room"][1]["iou"] == 0.0, drift["per_room"][1]
    assert drift["min_iou"] == 0.0, drift
    assert drift["aligned"] is False, drift
