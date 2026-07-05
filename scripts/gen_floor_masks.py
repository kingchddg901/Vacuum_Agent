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
# All masks are authored at 2048x2048 — the per-room mask-position "shift" is
# calibrated for that canvas, so every mask must match or the shift misaligns.
SIZE = 2048


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

    fine = speckle(SIZE // 2, 0.90, 70, 170)    # dense fine grain  (~2 px at output)
    coarse = speckle(SIZE // 4, 0.975, 150, 256)  # sparse brighter chunks (~4 px at output)
    out = np.maximum(fine, coarse)
    _stats("output concrete-micro", out)
    if check:
        return
    dst = TEXTURES / "concrete" / "concrete-micro-mask.png"
    Image.fromarray(out.astype(np.uint8), "L").save(dst)
    print(f"    wrote {dst.name}")


def gen_split_from_photo(check: bool, src_name: str, out_dir_name: str, prefix: str,
                         base_blur: float = 0.03, band_lo: float = 0.006, band_hi: float = 0.03,
                         base_floor: float = 0.55, detail_gamma: float = 2.6) -> None:
    """Frequency-split a full-colour PHOTO (carpet / granite) into two masks — the fix
    for single-photo materials that collapse to black at map scale (see the floor-texture
    doc). BASE = heavy blur, lifted to a mostly-WHITE broad field (its colour must FILL).
    DETAIL = a BAND-PASS (blur(band_lo) - blur(band_hi)) so it catches MEDIUM-frequency
    structure (weave clumps / aggregate) not fine noise, then a darkening gamma so it's a
    mostly-BLACK field with sparse BOLD white peaks (a mid-grey detail mask just floods the
    colour as a uniform veil — the concrete-micro lesson)."""
    from PIL import ImageFilter

    src = TEXTURES / src_name
    print(f"[{prefix}] split  <-  {src.name}")
    img = Image.open(src).convert("L").resize((SIZE, SIZE), Image.LANCZOS)
    base_r = max(1, round(SIZE * base_blur))
    lo_r = max(1, round(SIZE * band_lo))
    hi_r = max(1, round(SIZE * band_hi))

    base = np.asarray(img.filter(ImageFilter.GaussianBlur(base_r)), dtype=np.float64)
    lo = np.asarray(img.filter(ImageFilter.GaussianBlur(lo_r)), dtype=np.float64)
    hi = np.asarray(img.filter(ImageFilter.GaussianBlur(hi_r)), dtype=np.float64)

    # BASE: normalize the broad tone then lift into [base_floor, 1] -> mostly white, gentle shading.
    b = (base - base.min()) / (base.max() - base.min() + 1e-6)
    b = base_floor + (1.0 - base_floor) * b
    bmask = (b * 255.0).astype(np.uint8)

    # DETAIL: medium-frequency band magnitude, normalized then gamma>1 -> sparse bold white on black.
    band = np.abs(lo - hi)
    d = np.clip(band / (np.percentile(band, 98.0) + 1e-6), 0.0, 1.0) ** detail_gamma
    dmask = (d * 255.0).astype(np.uint8)

    _stats(f"{prefix}-base", bmask.astype(np.float64))
    _stats(f"{prefix}-detail", dmask.astype(np.float64))
    if check:
        return
    od = TEXTURES / out_dir_name
    od.mkdir(parents=True, exist_ok=True)
    Image.fromarray(bmask, "L").save(od / f"{prefix}-base-mask.png")
    Image.fromarray(dmask, "L").save(od / f"{prefix}-detail-mask.png")
    print(f"    wrote {prefix}-base-mask.png + {prefix}-detail-mask.png")


def gen_wood_planks(check: bool, plank_w: int = 256, plank_l: int = 512,
                    face_lo: float = 0.86, groove_wash: float = 0.16,
                    grain_amp: float = 90.0) -> None:
    """Procedural SEAMLESS hardwood — the replacement for the photographic wood swatch whose baked
    plank-ends read as glitchy 'stops' when the map tiles it (and whose base/grain layers, sharing
    the base colour, were invisible on the opaque map floor so only the seams showed). Writes the
    three wood layer masks with a staggered running-bond plank grid that EDGE-WRAPS (no repetition
    seam):
        wood-directional-depth-mask.png -> plank FACES  (mostly white; the base colour fills)
        wood-grain-mask.png             -> fine vertical GRAIN streaks (accent colour reveals dark)
        wood-seam-mask.png              -> plank-edge GROOVES + staggered joint ends (accent)
    Seamless because plank_w divides SIZE (whole columns) and there are exactly SIZE/plank_l planks
    per column, tones indexed mod that count, with per-column vertical offsets that wrap mod plank_l.
    On the map the grooves/grain (accent colour, distinct from the base) give the plank definition;
    on the cards the plank FACES show over the card surface too."""
    print("[wood] procedural seamless staggered planks")
    rng = np.random.default_rng(1971)
    N = SIZE
    ncol = N // plank_w
    npl = N // plank_l                       # planks per column — exact, so tones wrap seamlessly
    y = np.arange(N)

    face = np.full((N, N), 255.0)
    grain = np.zeros((N, N))
    groove = np.zeros((N, N))

    for c in range(ncol):
        x0, x1 = c * plank_w, (c + 1) * plank_w
        off = int(rng.integers(0, plank_l))
        pidx = (((y + off) // plank_l) % npl).astype(int)          # plank index, wraps -> seamless
        along = ((y + off) % plank_l) / plank_l                    # 0..1 along the plank

        # FACE: gentle per-plank tone + soft end-darkening (mostly for the card, where faces show).
        tones = rng.uniform(face_lo, 1.0, size=npl)
        fcol = tones[pidx] * (1.0 - 0.05 * (np.abs(along - 0.5) * 2.0) ** 4)
        face[:, x0:x1] = np.clip(fcol, 0.0, 1.0)[:, None] * 255.0

        # GROOVE: a thin joint line where each plank starts + a faint per-plank wash (some planks a
        # touch darker on the map, since the FACE tone itself is base-on-base and invisible there).
        gcol = np.where(((y + off) % plank_l) < 3, 255.0, 0.0)
        wash = rng.uniform(0.0, groove_wash, size=npl)[pidx] * 255.0
        groove[:, x0:x1] = np.maximum(gcol, wash)[:, None]

        # GRAIN: sparse vertical streaks, brightness modulated along y with an INTEGER number of
        # sine cycles over N so it wraps; per-column phase resets are hidden under the vert grooves.
        streak = (rng.uniform(0, 1, size=plank_w) > 0.70) * rng.uniform(0.3, 1.0, size=plank_w)
        phase = rng.uniform(0.0, 2.0 * np.pi, size=plank_w)
        ymod = 0.55 + 0.45 * np.sin(y[:, None] * (2.0 * np.pi * 32.0 / N) + phase[None, :])
        grain[:, x0:x1] = np.clip(streak[None, :] * ymod * grain_amp, 0.0, 255.0)

    # VERTICAL grooves at every plank-column boundary (full height; x=0 is also the wrapped x=N).
    for c in range(ncol):
        x = c * plank_w
        groove[:, max(0, x - 1):x + 2] = 255.0

    _stats("wood-face", face)
    _stats("wood-grain", grain)
    _stats("wood-groove", groove)
    if check:
        return
    od = TEXTURES / "wood"
    Image.fromarray(face.astype(np.uint8), "L").save(od / "wood-directional-depth-mask.png")
    Image.fromarray(grain.astype(np.uint8), "L").save(od / "wood-grain-mask.png")
    Image.fromarray(groove.astype(np.uint8), "L").save(od / "wood-seam-mask.png")
    print("    wrote wood-directional-depth + wood-grain + wood-seam masks")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report source stats, write nothing")
    args = ap.parse_args()
    print(f"textures dir: {TEXTURES}")
    if not TEXTURES.is_dir():
        raise SystemExit(f"textures dir not found: {TEXTURES}")
    gen_tile_base(args.check)
    gen_concrete_micro(args.check)
    gen_wood_planks(args.check)
    # Split the single-photo materials (carpet / granite) into base + bold detail masks.
    gen_split_from_photo(args.check, "carpet/texture-floor-carpet-low.png",     "carpet",  "carpet-low")
    gen_split_from_photo(args.check, "carpet/texture-floor-carpet-high.png",    "carpet",  "carpet-high")
    gen_split_from_photo(args.check, "granite/texture-floor-granite-light.png", "granite", "granite")
    print("done." + (" (check only — nothing written)" if args.check else ""))


if __name__ == "__main__":
    main()
