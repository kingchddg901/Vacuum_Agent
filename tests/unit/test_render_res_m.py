"""[RESM] ``res_m`` — ONE unit for the raster cell size, across every brand.

WHY THIS TEST IS CROSS-BRAND AND NOT THREE BRAND TESTS. The ``room_pixels_v1`` payload has
carried a ``res`` field from all three producers since each was written, and the three do
not agree on its unit:

    Eufy      ``res`` is CENTIMETRES   (map_source.py; ``_area_m2`` divides by 100)
    Roborock  ``res`` is MILLIMETRES   (roborock_raw_map.py; the map/50 image scale)
    Dreame    ``res`` is MILLIMETRES   (map_source_runtime.py; ``grid_size``)

Measured on the development boxes 2026-11-14: alfred (Eufy) reports 5, ivy (Roborock) 50,
robin (Dreame) 50 — all three physically 5 cm per cell, in a field of one name holding two
units. Nothing read ``res`` on the card, so nothing was wrong; the moment something did it
would have been 10x out on two brands of three, with no value on the wire to tell it apart.

``res_m`` is the normalized field: METRES per raster cell, converted at each producer where
the unit is known. The defect it guards is ONE PRODUCER FORGETTING TO CONVERT, and a test
scoped to a single brand is blind to exactly that — it would pass on whichever brand the
author was holding in mind. So all three are asserted against ONE number here, and the
assertions are written so the failure names the brand.

BITE, per claim:
  [RESM-1] drop the /100 on Eufy and it reads 5.0 m; drop /1000 on the others and 50.0.
           Swapping the two conversions (the realistic slip) makes Eufy 0.005 and the
           other two 0.5 — which is why equality ACROSS the three is the assertion, not
           three separate constants that could each be edited to match a broken producer.
  [RESM-2] the conversion is a real division, not a constant: a different device
           resolution must move res_m proportionally. A producer that returned 0.05
           unconditionally would pass [RESM-1] and fail here.
  [RESM-3] `res` itself is left alone — asserted, not assumed. MEASURED 2026-11-14:
           NOTHING in shipped code reads this field. Grepping `src/`, all three built
           bundles and `custom_components/` finds only the three producers WRITING it;
           the pose overlays project through `map_data["resolution"]` and the Roborock
           parser's own `ImageDimensions.to_img`, never through the payload. So the
           reason for keeping it is not "three call sites depend on it" (an earlier note
           here said that, and it was false) — it is that `get_map_render_data` is a
           PUBLIC service whose response shape is an API an automation may already read,
           and quietly redefining a field's unit under a user is the one thing worse than
           an ambiguous one. The field's lack of consumers is itself worth knowing: if it
           is ever retired, this test is where to find out nothing internal will notice.
"""

from __future__ import annotations

import base64
import types

import pytest

from custom_components.eufy_vacuum.mapping.map_source import render_data_from_storage
from custom_components.eufy_vacuum.mapping.map_source_runtime import (
    dreame_render_data_from_mapdata,
)
from custom_components.eufy_vacuum.mapping.roborock_raw_map import roborock_render_data

np = pytest.importorskip("numpy")

#: 5 cm per cell — what all three development vacuums actually report.
FIVE_CM = 0.05


# --- the three producers, each from its own native input ---------------------

def _eufy(resolution_cm: int = 5) -> dict:
    """Eufy: `resolution` is centimetres."""
    raster = bytearray(10 * 10)
    for y in range(2, 5):
        for x in range(2, 5):
            raster[y * 10 + x] = 5 << 2          # rid 5, rid_shift 2
    return render_data_from_storage({
        "width": 10, "height": 10, "resolution": resolution_cm,
        "room_outline_width": 10, "room_outline_height": 10,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
        "room_names": {}, "room_pixels": base64.b64encode(bytes(raster)).decode(),
    })


def _roborock(res_mm: int = 50) -> dict:
    """Roborock: `res` is millimetres."""
    return roborock_render_data({
        "width": 4, "height": 3, "top": 0, "left": 0,
        "rid_shift": 0, "catch_all_rid": 31, "flip_y": True,
        "room_ids": [5], "room_pixels": bytes([5] * 12), "res": res_mm,
    })


def _dreame(grid_size_mm: int = 50) -> dict:
    """Dreame: `grid_size` is millimetres."""
    md = types.SimpleNamespace(
        pixel_type=np.array([[1, 1, 0], [1, 1, 0], [0, 0, 0], [0, 0, 0]], dtype=np.uint8),
        dimensions=types.SimpleNamespace(
            grid_size=grid_size_mm, top=0, left=0, width=4, height=3,
        ),
        segments={1: types.SimpleNamespace(
            id=1, x0=0, y0=0, x1=100, y1=100, name="Kitchen", x=50, y=50,
        )},
        robot_position=types.SimpleNamespace(x=0, y=0, a=0),
        charger_position=types.SimpleNamespace(x=0, y=0, a=0),
        furnitures={}, saved_furnitures={},
    )
    return dreame_render_data_from_mapdata(md)


BRANDS = (("eufy", _eufy), ("roborock", _roborock), ("dreame", _dreame))


# --- the claims --------------------------------------------------------------

def test_resm_1_every_brand_reports_the_same_physical_cell():
    """[RESM-1] Three producers, three native units, ONE metres-per-cell number.

    Asserted as equality across the set and not as three literals: the slip this guards
    is a wrong (or missing) conversion in one producer, and three independent constants
    invite whoever broke it to edit the matching one.
    """
    got = {name: build()["res_m"] for name, build in BRANDS}
    assert set(got) == {"eufy", "roborock", "dreame"}, "a producer stopped emitting res_m"
    assert len(set(got.values())) == 1, (
        "res_m disagrees across brands while the devices agree physically: "
        + ", ".join(f"{k}={v}" for k, v in sorted(got.items()))
    )
    assert got["eufy"] == pytest.approx(FIVE_CM), (
        f"5 cm/cell must be {FIVE_CM} m, got {got['eufy']} — a raw unit reached the wire"
    )


@pytest.mark.parametrize("name,build", BRANDS)
def test_resm_2_res_m_tracks_the_device_resolution(name, build):
    """[RESM-2] It is a conversion, not a constant: doubling the device's own resolution
    doubles res_m. A producer hardcoding 0.05 passes [RESM-1] and dies here."""
    base = build()["res_m"]
    # Each builder takes its OWN native unit as its first argument, so "double it" is
    # spelled once per brand rather than translated here — translating would re-introduce
    # the very unit confusion under test.
    twice = {"eufy": lambda: _eufy(10), "roborock": lambda: _roborock(100),
             "dreame": lambda: _dreame(100)}[name]()["res_m"]
    assert twice == pytest.approx(base * 2), (
        f"{name}: res_m did not track the device resolution ({base} -> {twice})"
    )


@pytest.mark.parametrize("name,build", BRANDS)
def test_resm_3_raw_res_keeps_its_own_unit(name, build):
    """[RESM-3] `res` is UNCHANGED and still brand-native. The pose overlays read it in
    those units; normalizing in place would have silently moved them. The point of res_m
    is a second field, not a rewritten one."""
    rd = build()
    expected = {"eufy": 5, "roborock": 50, "dreame": 50}[name]
    assert rd["res"] == expected, (
        f"{name}: res changed unit — pose projection reads this field raw"
    )
