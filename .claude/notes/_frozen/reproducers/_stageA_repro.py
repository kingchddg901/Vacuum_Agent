"""Stage A - reproduce the routed-back leads from audit #18's meta-verifier.

Each block reproduces the half that NEITHER verifier lens executed.
"""
import struct

from custom_components.eufy_vacuum.dispatch.zone_dispatch import (
    normalized_rects_to_mm, fit_normalized_to_mm, max_residual_mm)
from custom_components.eufy_vacuum.mapping import segment_primitives as sp
from custom_components.eufy_vacuum.mapping import roborock_raw_map as rrm

SEP = "=" * 78
ONE, ZERO = bytes([1]), bytes([0])

# ---------------------------------------------------------------- A6-ZONE-C-1
print(SEP)
print("A6-ZONE-C-1 (HIGH) - does the residual gate catch a wrong-map projection?")
print(SEP)

# (nx, ny, mm_x, mm_y). Two real, DIFFERENT floors. Both are exact affines.
main_floor = [(0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 6000.0, 0.0), (0.0, 1.0, 0.0, 8000.0)]
upstairs = [(0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 4000.0, 0.0), (0.0, 1.0, 0.0, 5000.0)]

zone = [[0.20, 0.30, 0.30, 0.40]]          # "under the couch", authored on Main floor
right = normalized_rects_to_mm(main_floor, zone)
wrong = normalized_rects_to_mm(upstairs, zone)

print("  authored on Main floor -> %s" % right)
print("  same rect vs Upstairs  -> %s" % wrong)
print("  near-corner displacement: %.0f mm x, %.0f mm y"
      % (abs(right[0][0] - wrong[0][0]), abs(right[0][1] - wrong[0][1])))

for name, corr in (("Main floor", main_floor), ("Upstairs", upstairs)):
    r = max_residual_mm(fit_normalized_to_mm(corr), corr)
    print("  residual gate on %-11s = %.6f mm  (tol 50.0) -> %s"
          % (name, r, "PASSES" if r <= 50 else "refuses"))
print("  => the gate validates the affine against ITS OWN correspondences, so a perfect fit")
print("     to the WRONG map passes cleanly. It cannot express 'this is not that map'.")

# ---------------------------------------------------------------- A2-POLYGO-2
print()
print(SEP)
print("A2-POLYGO-2 (HIGH) - is 'no imaging stack' distinguishable from 'nothing drawn'?")
print(SEP)

shapes = [{"type": "rect", "x": 10, "y": 10, "w": 20, "h": 20}]
if sp.PIL_Image is not None and sp.np is not None:
    n = len(sp.rasterize_primitives(shapes, width=1000, height=1000))
    print("  authored shape WITH stack      -> %d polygon points" % n)

_pil, _np = sp.PIL_Image, sp.np
sp.PIL_Image = None                        # HA Container/Core without the science stack
try:
    missing = sp.rasterize_primitives(shapes, width=1000, height=1000)
    empty = sp.rasterize_primitives([], width=1000, height=1000)
finally:
    sp.PIL_Image, sp.np = _pil, _np

print("  authored shape, NO stack       -> %r" % (missing,))
print("  genuinely empty input          -> %r" % (empty,))
print("  identical sentinel: %s" % (missing == empty))
print("  => the caller's `if not poly` cannot tell 'I cannot draw' from 'nothing to draw',")
print("     and then unconditionally assigns custom_segments and awaits async_save().")

# ---------------------------------------------------------------- A7-ROBORO-7
print()
print(SEP)
print("A7-ROBORO-7 (LOW) - confirm the meta-verifier's fixture resolution")
print(SEP)


def image_block(header_len, dims=(30, 40, 4, 4), data=ONE * 16):
    """One IMAGE block: type=2 @0, header_len @2, data_len @4, dims in the LAST 16 bytes."""
    top, left, height, width = dims
    hdr = struct.pack("<hhI", 2, header_len, len(data))
    if header_len >= 24:
        hdr += struct.pack("<IIII", top, left, height, width)
    return hdr.ljust(header_len, ZERO) + data


for hl in (24, 20, 16):
    blk = image_block(hl)
    # Read the dims exactly as roborock_raw_map.py:97-100 does.
    reads = {name: rrm._u32(blk, hl - off)
             for name, off in (("top", 16), ("left", 12), ("height", 8), ("width", 4))}
    print("  header_len=%-3d guard `>= 16` passes -> %s" % (hl, reads))
print("  header_len 24 is the real v1 layout (dims at 8/12/16/20). Below it the reads slide")
print("  backwards over type/header_len/data_len: at 20, top == data_len; at 16,")
print("  top == type | (header_len << 16) == %d." % (2 | (16 << 16)))
print("  meta-verifier's call stands: CONSTRUCTIBLE BUT NOT ACCIDENTAL. Fix (>= 24) unchanged;")
print("  priority below 'constructible', above 'unreachable'.")
