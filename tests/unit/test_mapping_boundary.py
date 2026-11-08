"""[BND] mapping/boundary.py — the ray-casting point-in-polygon test (pure).

A 40-line module with one function, used live by `map_source.zone_membership` to decide
which rooms a drawn zone overlaps. It had NO direct test: the main loop was covered
incidentally through that caller, and the degenerate-polygon guard was not covered at
all.

[BND-1] a point inside a real polygon is inside, and one outside is outside.
[BND-2] a boundary-crossing count is what decides it, not a bounding box.
[BND-3] the `n < 3` guard, which is NOT the no-op it looks like.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.mapping.boundary import point_in_polygon


_SQUARE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]


def test_bnd1_a_point_inside_a_square_is_inside():
    """[BND-1] The ordinary case, so the refusals below mean something.

    Without it, every assertion in this file could be satisfied by a function that
    always returned False.
    """
    assert point_in_polygon((5.0, 5.0), _SQUARE) is True
    assert point_in_polygon((15.0, 5.0), _SQUARE) is False
    assert point_in_polygon((5.0, -1.0), _SQUARE) is False


def test_bnd2_a_concave_polygon_is_judged_by_crossings_not_by_extent():
    """[BND-2] Ray casting, not a bounding box.

    An L-shape has a notch that lies INSIDE its bounding box and OUTSIDE the polygon.
    A bounding-box implementation passes [BND-1] and fails here, which is the only
    reason [BND-1] is not the whole test.

        (0,10)-----(10,10)
          |            |
          |     (5,5)--+ (10,5)
          |       |
        (0,0)---(5,0)
    """
    l_shape = [
        [0.0, 0.0], [5.0, 0.0], [5.0, 5.0], [10.0, 5.0], [10.0, 10.0], [0.0, 10.0],
    ]

    assert point_in_polygon((2.0, 2.0), l_shape) is True, "in the tall leg"
    assert point_in_polygon((7.0, 7.0), l_shape) is True, "in the top bar"
    assert point_in_polygon((7.0, 2.0), l_shape) is False, (
        "the notch: inside the bounding box, outside the shape"
    )


def test_bnd3_a_two_point_polygon_is_refused_and_the_guard_is_not_a_no_op():
    """[BND-3] `if n < 3: return False` — and it CHANGES THE ANSWER.

    The obvious reading is that this guard is redundant: a 2-point "polygon" has no
    interior, so surely the ray-casting loop returns False anyway. It does not, and
    this test is the input that proves it.

    For n == 2 the loop runs twice over the same pair of vertices in opposite order,
    so it computes the x-intersection two ways:

        i=0, j=1:  x0 + (x1 - x0) * (py - y0) / (y1 - y0)
        i=1, j=0:  x1 + (x0 - x1) * (py - y1) / (y0 - y1)

    Algebraically identical. NOT bit-identical in IEEE 754 — on the values below they
    differ by 1.1368683772161603e-13. Put `px` exactly at the lower of the two and
    `px < higher` is True while `px < lower` is False, so `inside` is toggled exactly
    ONCE and the loop returns True. The guard is what turns that into False.

    The input was derived by directed search (4000 random segments, `py` at the
    midpoint so both edges cross the ray, `px` placed at the smaller intersection),
    not copied: 3 disagreeing parameter sets turned up, and this is the first. It is
    deterministic — IEEE 754 arithmetic, not sampling — so it reproduces exactly.

    WHAT IT COSTS: `map_source.zone_membership` passes user-drawn zone geometry here.
    A zone reduced to two points by a bad drag would, without this guard, report
    overlapping whichever rooms happened to land on the wrong side of a rounding error
    — a zone clean dispatched at rooms the user never selected, decided by the last
    bit of a division.

    RED: delete `if n < 3: return False` and this returns True.
    """
    degenerate = [
        [581.0535347062857, -283.6965910954998],
        [-450.82772528433713, 818.1205513689645],
    ]
    on_the_rounding_seam = (65.11290471097425, 267.21198013673234)

    assert point_in_polygon(on_the_rounding_seam, degenerate) is False, (
        "a two-point polygon has no interior, whatever the arithmetic says"
    )
    # the plain cases too -- fewer than three vertices is never inside anything
    assert point_in_polygon((0.0, 0.0), []) is False
    assert point_in_polygon((0.0, 0.0), [[0.0, 0.0]]) is False
