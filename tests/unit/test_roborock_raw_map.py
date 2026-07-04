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
[RRD-5]  decode: IMAGE dims larger than the pixel data -> None.
"""

from __future__ import annotations

import struct

from custom_components.eufy_vacuum.mapping.roborock_raw_map import (
    CATCH_ALL_RID,
    decode_roborock_v1_segments,
    resolve_rid,
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
