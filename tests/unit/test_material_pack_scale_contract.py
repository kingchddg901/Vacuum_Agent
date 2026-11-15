"""The physical-scale arithmetic, and the one constant the whole derivation stands on.

``scripts/material_pack_contract.py`` tells a material author whether a declared physical
sample size will actually be drawn at the size they asked for, or silently clamped. When it
shipped it had NO TEST: the sweep was ablated by hand once, in a session, and that evidence
does not survive the session. A gate nobody can show firing reads as coverage while being
indistinguishable from a gate that cannot fail -- which is the worse of the two states,
because silence at least does not read as checked.

WHY THE CLAMP DEPENDS ON THE RASTER AND NOT ONLY THE RESOLUTION. The card supersamples a
small raster harder (``S = round(1200 / max(W, H))``), and the metres a canvas pixel covers
is ``res_m / S``. So the band of representable tile sizes moves with the raster's PIXEL
WIDTH. At 5 cm/cell that is 0.26-25.6 m at S=8, 0.41-41.0 m at S=5, 0.51-51.2 m at S=4,
0.68-68.3 m at S=3 and 1.02-102 m at S=2.

THE SWEEP WIDENED 2026-11-15, and these literals moved with it. The card's ``min(4, ...)``
cap is gone (src/textures/floor-fit.js), so a SMALL home now supersamples to 5, 6, 7 or 8 --
two of the three development vacuums moved from S=4 to S=5 on the same maps. The upper end
of the SAFE band therefore halved, from 51.2 m to 25.6 m, because the tightest ceiling
belongs to the LARGEST S now reachable. That is not a new restriction, it is one that was
always true on a small home and that the capped sweep could not see.
A 0.6 m sample is therefore fine on one of the development vacuums and clamped on another,
with nothing raised and nothing to see but a floor tiling at the wrong rate. [MPCS-3] is
that exact case, and it is the defect the pre-ship review caught.

WHY S=1 IS NOT SWEPT, pinned behaviourally by [MPCS-6]. Sweeping it made a correct 5 ft
board warn, and a warning that fires on good input teaches the author to skip the block --
which costs the warnings that matter. S=1 needs a raster over 800 px wide, i.e. 40 m across,
which is not a home. Re-adding it turns [MPCS-6] red, which is the point of stating it as
a test rather than a comment. (The old note here said S=1 needed ~1715 px / 86 m. That was
wrong independently of the cap: round(1200/801) is already 1.)

AND WHY THE SET ITSELF IS PINNED, by [MPCS-9]. These expectations are deliberately LITERAL
-- a set derived from ``_SUPERSAMPLES`` would assert the code against itself and could not
bite. The cost of literals is that they rot silently when the sweep moves, which is exactly
what happened on 2026-11-15: five tests went red at once with no single line saying why.
[MPCS-9] is that line.

Coverage targets
----------------
[MPCS-1] all four ``RNTA1EGS`` declarations of the 2048 mask canvas agree.
         Red if any one copy is edited alone -- the failure the replica note exists for.
[MPCS-2] ``sample_m_to_scale`` is the renderer's arithmetic, and its default m/px is res/4.
         Red if the formula, the canvas or the reference supersample moves.
[MPCS-3] the LOW clamp bites, and names only the S values that really clamp.
         Red if the sweep is narrowed to one S, or the per-S band arithmetic changes.
[MPCS-4] the HIGH clamp bites too. Red if only the lower bound is checked -- a one-sided
         guard looks complete from either side.
[MPCS-5] the unit trap: a raster ``scale`` value published as a ``sample_m`` is caught.
         Red if the floor of the band ever drops below 0.05 m.
[MPCS-6] the gate is SILENT on correct input -- a 5 ft board, an 8 ft slab, a 25 m sheet.
         Red if S=1 is swept again, or the tolerance is dropped to zero.
[MPCS-7] the tolerance is a materiality threshold with bite on BOTH sides: a 2% clamp is
         not reported, a 6.7% clamp is. Red if it becomes an off switch, or is removed.
[MPCS-8] the reported metres are what will be DRAWN, not what was asked for. Red if the
         report echoes the request, which would make a clamp warning unactionable.
[MPCS-9] the swept set is what the card's own formula produces over real home rasters.
         Red if the sweep moves, naming it once instead of letting 5 tests rot together.

Every value below was read off the real function, not predicted.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mpc():
    return _load(REPO / "scripts" / "material_pack_contract.py", "_mpc_under_test")


# ---------------------------------------------------------------------------
# [MPCS-1] the replica set
# ---------------------------------------------------------------------------

# REPLICA RNTA1EGS -- four runtimes, nothing to import from, nothing derives it. The sites
# are listed in docs/dev/00c-replicas.md. gen_floor_masks is read as TEXT rather than
# imported: its numpy/Pillow imports are optional dependencies this suite does not declare.
_REPLICA_SITES = (
    ("custom_components/eufy_vacuum/user_materials.py", r"^CANVAS\s*=\s*(\d+)"),
    ("scripts/material_pack_contract.py", r"^MASK_CANVAS_PX\s*=\s*(\d+)"),
    ("scripts/gen_floor_masks.py", r"^SIZE\s*=\s*(\d+)"),
    ("src/bindings/map.js", r"^const MASK_CANVAS_PX\s*=\s*(\d+)\s*;"),
)


def test_mpcs_1_mask_canvas_replicas_agree():
    """[MPCS-1] The mask canvas is declared in four places and they must all read 2048."""
    found = {}
    for rel, pattern in _REPLICA_SITES:
        path = REPO / rel
        assert path.is_file(), f"replica site missing: {rel}"
        text = path.read_text(encoding="utf-8")
        m = re.search(pattern, text, re.MULTILINE)
        assert m, (
            f"RNTA1EGS: could not read the canvas declaration in {rel}.\n"
            "Either the constant was renamed or its spelling moved -- in both cases the "
            "replica set is no longer checkable, which is worse than a mismatch."
        )
        found[rel] = int(m.group(1))

    assert len(set(found.values())) == 1, (
        "RNTA1EGS replica set DISAGREES -- a mask canvas edited in one place only:\n  "
        + "\n  ".join(f"{k} = {v}" for k, v in found.items())
        + "\nEvery copy must move together: the producer writes this size, one consumer "
          "divides a real-world measurement by it, and one gate refuses anything else."
    )
    assert set(found.values()) == {2048}, found


# ---------------------------------------------------------------------------
# [MPCS-2] the arithmetic
# ---------------------------------------------------------------------------

def test_mpcs_2_sample_m_to_scale_is_the_renderers_arithmetic(mpc):
    """[MPCS-2] scale = sample_m / (MASK_CANVAS_PX * m_per_canvas_px)."""
    assert mpc.MASK_CANVAS_PX == 2048
    # The reference m/px is 5 cm per cell at the commonest supersample, S=4.
    assert mpc.REF_M_PER_CANVAS_PX == pytest.approx(0.05 / 4)

    # An 8 ft slab (8 x 304.8 mm) on a 5 cm/cell map supersampled 4x.
    assert mpc.sample_m_to_scale(2.4384) == pytest.approx(0.09525)
    # Explicit m/px overrides the reference, so the same size resolves differently per map.
    assert mpc.sample_m_to_scale(2.4384, 0.05 / 3) == pytest.approx(0.0714375)
    assert mpc.sample_m_to_scale(2.4384, 0.05 / 2) == pytest.approx(0.047625)

    # The inverse round-trips: a scale drawn back out spans the size that produced it.
    for s in (4, 3, 2):
        m_per_px = 0.05 / s
        scale = mpc.sample_m_to_scale(2.4384, m_per_px)
        assert scale * mpc.MASK_CANVAS_PX * m_per_px == pytest.approx(2.4384)


# ---------------------------------------------------------------------------
# [MPCS-3] / [MPCS-4] the gate bites, at both ends
# ---------------------------------------------------------------------------

def _supersamples(report) -> set[int]:
    return {s for s, _scale, _drawn in report}


def test_mpcs_3_low_clamp_bites_and_names_only_the_clamping_supersamples(mpc):
    """[MPCS-3] A 0.6 m sample is representable at S=4 and clamped at S=3 and S=2.

    This is the whole reason the sweep exists. A single-S check would have called 0.6 m
    fine, and it is fine -- on two of his three vacuums.
    """
    assert _supersamples(mpc.clamping_supersamples(0.6)) == {3, 2}, (
        "a 0.6 m sample must clamp at S=3 and S=2 and NOT at S=4"
    )
    # Smaller still and there is nowhere it survives.
    assert _supersamples(mpc.clamping_supersamples(0.3)) == {6, 5, 4, 3, 2}


def test_mpcs_4_high_clamp_bites(mpc):
    """[MPCS-4] The band has an upper bound too, and a guard checked at one end only
    looks complete from that end."""
    assert _supersamples(mpc.clamping_supersamples(120.0)) == {8, 7, 6, 5, 4, 3, 2}
    assert _supersamples(mpc.clamping_supersamples(204.0)) == {8, 7, 6, 5, 4, 3, 2}


def test_mpcs_5_a_raster_scale_published_as_a_sample_m_is_caught(mpc):
    """[MPCS-5] The unit trap. `scale` is a raster multiplier around 0.02-0.25 and
    `sample_m` is metres of real floor; the two live side by side in the same descriptor
    and nothing about the VALUE says which it is. Publishing the former as the latter is
    the likeliest authoring mistake, and it must not pass quietly."""
    assert _supersamples(mpc.clamping_supersamples(0.05)) == {8, 7, 6, 5, 4, 3, 2}
    # NOT S=8, and the gap is the materiality tolerance rather than an oversight: 0.25 m
    # sits a hair under S=8's clamp floor of 0.256 m, so it IS clamped there but by 2.4%,
    # which [MPCS-7] establishes is below the reporting threshold. Read off the function,
    # not predicted -- predicting it is how this line was first written wrong.
    assert _supersamples(mpc.clamping_supersamples(0.25)) == {7, 6, 5, 4, 3, 2}


# ---------------------------------------------------------------------------
# [MPCS-6] silence on correct input -- the S=1 regression guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("sample_m", "what"),
    [
        (1.524, "a 5 ft board -- the case that warned when S=1 was swept"),
        (2.4384, "an 8 ft slab, the Material Author frame width"),
        (1.2, "a 1.2 m sheet of four 30 cm tiles"),
        (25.0, "a sheet at the top of the safe band -- 25.6 m at S=8 is the ceiling"),
    ],
)
def test_mpcs_6_correct_sizes_do_not_warn(mpc, sample_m, what):
    """[MPCS-6] A warning that fires on good input is worse than no warning."""
    assert mpc.clamping_supersamples(sample_m) == [], (
        f"{sample_m} m ({what}) must not warn -- a gate that cries on correct input "
        "teaches the author to ignore the whole block."
    )


# ---------------------------------------------------------------------------
# [MPCS-7] the tolerance has bite on both sides
# ---------------------------------------------------------------------------

def test_mpcs_7_tolerance_is_a_materiality_threshold_not_an_off_switch(mpc):
    """[MPCS-7] 1.0 m clamps to 1.024 m at S=2 -- 2.4% out, which nobody can see on a map,
    so it is not reported. 0.96 m clamps to the same 1.024 m -- 6.7% out, which is. A
    tolerance tested on one side only cannot be shown to still reject anything."""
    assert mpc._CLAMP_TOLERANCE == 0.05, (
        "this test's two fixtures straddle the tolerance; moving it invalidates them"
    )
    assert mpc.clamping_supersamples(1.0) == [], "a 2.4% clamp is below the threshold"
    assert _supersamples(mpc.clamping_supersamples(0.96)) == {2}, "6.7% is above it"


# ---------------------------------------------------------------------------
# [MPCS-8] the report says what will be drawn
# ---------------------------------------------------------------------------

def test_mpcs_8_report_gives_the_drawn_size_not_the_requested_one(mpc):
    """[MPCS-8] The author needs the number the floor will actually tile at. A report that
    echoed the request back would be unactionable while looking identical in shape."""
    report = {s: (scale, drawn) for s, scale, drawn in mpc.clamping_supersamples(0.3)}
    assert set(report) == {6, 5, 4, 3, 2}

    # Each drawn size is the clamp FLOOR for that supersample -- 0.02 * 2048 * (0.05 / S) --
    # and every one of them differs from the 0.3 m that was asked for.
    for s, expected in ((6, 0.3413333333333333), (5, 0.4096), (4, 0.512),
                        (3, 0.6826666666666666), (2, 1.024)):
        scale, drawn = report[s]
        assert scale == pytest.approx(0.3 / (2048 * (0.05 / s)))
        assert drawn == pytest.approx(expected)
        assert drawn != pytest.approx(0.3)
        # And the clamped scale is the floor, not the request.
        assert 0.02 * 2048 * (0.05 / s) == pytest.approx(drawn)



# ---------------------------------------------------------------------------
# [MPCS-9] the swept set, named once
# ---------------------------------------------------------------------------

def test_mpcs_9_the_swept_set_is_what_the_cards_formula_produces(mpc):
    """[MPCS-9] Every expectation above is a literal, on purpose -- deriving them from
    ``_SUPERSAMPLES`` would assert the module against itself. The price is that they ALL
    rot together when the sweep moves, which is what happened when the card's ``min(4, ...)``
    cap was removed: five tests went red at once and none of them said 'the sweep changed'.

    This one does. It recomputes the set from the card's formula -- not from the module's
    own tuple -- so it is red when the sweep moves and silent otherwise, and whoever reads
    it knows to re-derive the literals rather than hunt five separate failures."""
    import math

    # The card's formula, written out rather than imported, so this is a second opinion
    # and not an echo: src/textures/floor-fit.js supersampleFactor().
    def card_S(long_px: int) -> int:
        return max(1, math.floor(1200 / long_px + 0.5) or 1)

    # Real home rasters at 5 cm/cell: ~7 m across to ~40 m across.
    expected = sorted({card_S(px) for px in range(142, 801)} - {1}, reverse=True)
    assert list(mpc._SUPERSAMPLES) == expected, (
        f"the swept supersample set moved: module has {list(mpc._SUPERSAMPLES)}, the card's "
        f"formula over real home rasters gives {expected}. Re-derive the literals in "
        "[MPCS-3/4/5/6/8] before changing this -- they are not independent of it."
    )
    # S=1 stays out, and the reason is behavioural: [MPCS-6]'s 5 ft board warns if it is in.
    assert 1 not in mpc._SUPERSAMPLES
