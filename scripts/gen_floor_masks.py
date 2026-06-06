#!/usr/bin/env python3
"""
============================================================
GENERATE PROCEDURAL FLOOR MASKS
============================================================

PURPOSE
-------
Regenerate the two floor-texture luminance masks that are derived by
RULE rather than authored by hand:

    tile/tile-mask.png            (tile BASE layer)
    concrete/concrete-micro-mask.png (concrete MICRO / accent layer)

WHY THE COMPOSITING MODEL FORCES THESE SHAPES
---------------------------------------------
The card paints each layer's color token only where the mask is WHITE
(CSS `mask-mode:luminance` over a transparent container — see
src/styles/floor-texture-styles.js). Therefore:

  * A BASE layer must be a mostly-WHITE field so its color FILLS the
    surface. tile-mask was a near-black speckle field, so the gold
    --evcc-floor-tile-base never filled the tile faces (faces rendered
    transparent). FIX: invert the (good) pure-tile-grout grid -> white
    tile faces with thin dark grout-grid channels, pixel-aligned to the
    existing grout lines by construction.

  * A DETAIL layer must be a mostly-BLACK field so its color shows only
    on the detail. concrete-micro was a flat MID-GREY field, so the
    near-black --evcc-floor-concrete-accent flooded the whole card as a
    uniform dimming veil. FIX: black field + sparse white aggregate
    specks -> fine dark flecks on the slab.

NOT TOUCHED
-----------
The hand/externally-authored masks (wood, marble, carpet, granite, and
the tile grout LINE itself) are left alone.

USAGE
-----
    py scripts/gen_floor_masks.py            # write into the repo textures dir
    py scripts/gen_floor_masks.py --check    # report source stats, write nothing

Deterministic: the concrete specks use a fixed RNG seed, so re-running
produces byte-identical output (keeps the build's content-hash cache-bust
token stable unless this recipe actually changes).
============================================================
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

TEXTURES = Path(__file__).resolve().parents[1] / "custom_components" / "eufy_vacuum" / "textures"
SIZE = 512


def _stats(name: str, arr: np.ndarray) -> None:
    print(
        f"    {name:24s} min={arr.min():3.0f} max={arr.max():3.0f} "
        f"mean={arr.mean():5.1f} p50={np.percentile(arr, 50):3.0f} "
        f"lit%={(arr > 8).mean() * 100:4.1f}"
    )


def gen_tile_base(check: bool) -> None:
    """tile-mask = inverse of pure-tile-grout -> white faces + dark grid channels."""
    print("[tile] base mask  <-  invert(pure-tile-grout)")
    src = TEXTURES / "tile" / "pure-tile-grout.png"
    arr = np.asarray(Image.open(src).convert("L"), dtype=np.float64)
    _stats("source grout-line", arr)
    inv = 255.0 - arr
    _stats("output tile-mask", inv)
    if check:
        return
    out = TEXTURES / "tile" / "tile-mask.png"
    Image.fromarray(inv.astype(np.uint8), "L").save(out)
    print(f"    wrote {out.name}")


def gen_concrete_micro(check: bool) -> None:
    """concrete-micro-mask = black field + sparse white aggregate specks (fine + coarse)."""
    print("[concrete] micro mask  <-  black field + sparse aggregate specks")
    rng = np.random.default_rng(7)

    def speckle(m: int, thr: float, lo: int, hi: int) -> np.ndarray:
        """Sparse specks authored at m x m, NEAREST-upscaled to 512 so each
        speck is (512/m) px wide and survives the card's mask downscale."""
        a = np.zeros((m, m), dtype=np.float64)
        mask = rng.random((m, m)) > thr
        a[mask] = rng.integers(lo, hi, size=int(mask.sum()))
        up = Image.fromarray(a.astype(np.uint8), "L").resize((SIZE, SIZE), Image.NEAREST)
        return np.asarray(up, dtype=np.float64)

    fine = speckle(256, 0.90, 70, 170)    # dense fine grain  (~2 px)
    coarse = speckle(128, 0.975, 150, 256)  # sparse brighter chunks (~4 px)
    out = np.maximum(fine, coarse)
    _stats("output concrete-micro", out)
    if check:
        return
    dst = TEXTURES / "concrete" / "concrete-micro-mask.png"
    Image.fromarray(out.astype(np.uint8), "L").save(dst)
    print(f"    wrote {dst.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report source stats, write nothing")
    args = ap.parse_args()
    print(f"textures dir: {TEXTURES}")
    if not TEXTURES.is_dir():
        raise SystemExit(f"textures dir not found: {TEXTURES}")
    gen_tile_base(args.check)
    gen_concrete_micro(args.check)
    print("done." + (" (check only — nothing written)" if args.check else ""))


if __name__ == "__main__":
    main()
