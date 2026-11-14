"""Drop-in floor materials — descriptor validation and catalogue (user_materials.py).

A drop-in material is user-supplied content that reaches the renderer, so the validator
is the only thing between a stranger's directory and the card. Two of its failure modes
are SILENT, and those are the ones these tests exist for:

  * a mask at the wrong canvas misaligns rather than erroring, because the per-type
    feature scales are tuned to 2048 and the decode path never reads the bitmap's width;
  * an RGB mask costs ~3x the bytes and nothing downstream complains, which is how 20 MB
    of unreferenced RGB shipped inert for four months until ``d902c5af``.

LEGEND
  UMAT-1   a well-formed drop-in is accepted, and its shape is the catalogue's
  UMAT-2   wrong canvas is refused, naming the size
  UMAT-3   a non-greyscale PNG is refused
  UMAT-4   a non-8-bit PNG is refused
  UMAT-5   a file that is not a PNG at all is refused
  UMAT-6   path traversal in ``file`` is refused
  UMAT-7   an absolute ``from`` is refused
  UMAT-8   a ``from`` that escapes the shipped textures tree is refused
  UMAT-9   a legitimate borrow of a shipped mask is accepted
  UMAT-10  an id equal to a reserved floor type is refused
  UMAT-11  an id that PREFIXES a reserved name is refused
  UMAT-12  an id PREFIXED BY a reserved name is refused
  UMAT-13  two layers marked primary is refused
  UMAT-14  a preset naming a token outside its namespace is refused
  UMAT-15  more layers than the cap is refused
  UMAT-16  an out-of-range opacity is refused
  UMAT-17  a duplicate suffix is refused
  UMAT-18  build_catalog writes catalog.json and skips the broken one
  UMAT-19  build_catalog never raises on an unreadable directory
  UMAT-20  png_header reads IHDR without a decoder
  UMAT-21  a layer with NO opacity at all is refused -- the requiredness is
           LOAD-BEARING for a line that never mentions it: user-materials.js:94 reads
           ``Number(l.opacity)`` bare, no finite guard and no fallback. It is safe only
           because this check cannot let a layer through without one. Relaxing it to
           "optional, defaults to 1" would reintroduce the top-level null bug one level
           down -- Number(null) is 0, 0 is finite, and every card layer span would
           multiply to invisible. [UM-9] in user-materials.test.mjs guards the TOP-LEVEL
           path and would not catch it.
"""

from __future__ import annotations

import json
import os
import struct
import sys
import zlib

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "custom_components", "eufy_vacuum"),
)
import user_materials as um  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..", "..")
TEXTURES = os.path.join(REPO, "custom_components", "eufy_vacuum", "textures")
BACKSLASH = "wood" + chr(92) + ".." + chr(92) + "x.png"


def _png(width: int, height: int, colour_type: int, bpp: int, depth: int = 8) -> bytes:
    """A real, decodable PNG. Built rather than fixtured so the ONE property under test
    (canvas / colour type / depth) is the only thing that differs between cases."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, depth, colour_type, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(width * bpp) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


GOOD_MASK = _png(um.CANVAS, um.CANVAS, 0, 1)


def _descriptor(**over) -> dict:
    d = {
        "schema": 1,
        "id": "probe",
        "name": "Probe",
        "family": "stone",
        "layers": [
            {"file": "m.png", "suffix": "base", "color": "#808080", "opacity": 0.5},
        ],
    }
    d.update(over)
    return d


def _material(tmp_path, descriptor: dict, extra_files: dict | None = None):
    """Write one drop-in directory and validate it. Returns the entry or None."""
    d = tmp_path / "probe"
    d.mkdir(exist_ok=True)
    (d / "m.png").write_bytes(GOOD_MASK)
    for name, data in (extra_files or {}).items():
        (d / name).write_bytes(data)
    (d / "material.json").write_text(json.dumps(descriptor), encoding="utf-8")
    return um.validate_material(str(d), TEXTURES)


def _borrow(descriptor: dict, value: str) -> dict:
    descriptor["layers"][0].pop("file", None)
    descriptor["layers"][0]["from"] = value
    return descriptor


def test_well_formed_material_is_accepted(tmp_path):
    """[UMAT-1] The accepted shape IS the catalogue's — id, layers, suffix, primary."""
    entry = _material(tmp_path, _descriptor())
    assert entry is not None
    assert entry["id"] == "probe"
    assert entry["family"] == "stone"
    assert [l["suffix"] for l in entry["layers"]] == ["base"]
    assert entry["layers"][0]["borrowed"] is False
    assert entry["layers"][0]["primary"] is False


@pytest.mark.parametrize(
    ("legend", "filename", "data"),
    [
        ("UMAT-2", "small.png", _png(1024, 1024, 0, 1)),
        ("UMAT-3", "rgb.png", _png(um.CANVAS, um.CANVAS, 2, 3)),
        ("UMAT-4", "deep.png", _png(um.CANVAS, um.CANVAS, 0, 2, depth=16)),
        ("UMAT-5", "notpng.png", b"this is not a png"),
    ],
)
def test_the_file_is_the_evidence(tmp_path, legend, filename, data):
    """[UMAT-2..5] The header decides, not the descriptor's claims.

    Each case is a REAL file differing in exactly one property, so a pass cannot come
    from the file being unreadable for some other reason.
    """
    d = _descriptor()
    d["layers"][0]["file"] = filename
    assert _material(tmp_path, d, {filename: data}) is None, legend


@pytest.mark.parametrize(
    ("legend", "rel"),
    [
        ("UMAT-6", "../m.png"),
    ],
)
def test_traversal_in_file_is_refused(tmp_path, legend, rel):
    """[UMAT-6] A path is judged by where it LANDS, not how it is spelled."""
    d = _descriptor()
    d["layers"][0]["file"] = rel
    assert _material(tmp_path, d) is None, legend


@pytest.mark.parametrize(
    ("legend", "value"),
    [
        ("UMAT-7", "/etc/passwd"),
        ("UMAT-7", "C:/Windows/x.png"),
        ("UMAT-8", "wood/../../x.png"),
        ("UMAT-8", BACKSLASH),
    ],
)
def test_borrow_must_stay_inside_the_shipped_tree(tmp_path, legend, value):
    """[UMAT-7,8] ``from`` may only reach a mask the integration already ships."""
    assert _material(tmp_path, _borrow(_descriptor(), value)) is None, legend


def test_legitimate_borrow_is_accepted(tmp_path):
    """[UMAT-9] Borrowing costs no new bytes and still mints the borrower's own token."""
    entry = _material(tmp_path, _borrow(_descriptor(), "wood/wood-seam-mask.png"))
    assert entry is not None
    assert entry["layers"][0]["borrowed"] is True
    assert entry["layers"][0]["path"] == "wood/wood-seam-mask.png"


@pytest.mark.parametrize(
    ("legend", "material_id"),
    [
        ("UMAT-10", "wood"),
        ("UMAT-10", "hardwood"),
        ("UMAT-10", "default"),
        ("UMAT-11", "carpet"),
        ("UMAT-11", "granite"),
        ("UMAT-12", "wood-oak"),
    ],
)
def test_id_is_a_namespace_and_must_be_contained(tmp_path, legend, material_id):
    """[UMAT-10..12] The id decides the minted token names.

    Equal to a reserved name duplicates existing keys and assertUniqueTokenKeys throws.
    A PREFIX is worse: the scoped-theme import clears by raw prefix, so ``carpet`` would
    wipe carpet-high's and carpet-low's tokens.
    """
    assert _material(tmp_path, _descriptor(id=material_id)) is None, legend
    assert um.id_conflict(material_id) is not None, legend


def test_only_one_layer_may_be_primary(tmp_path):
    """[UMAT-13] The SVG surface shows exactly one image; two primaries is ambiguous."""
    d = _descriptor()
    d["layers"] = [
        dict(d["layers"][0], primary=True),
        dict(d["layers"][0], suffix="other", primary=True),
    ]
    assert _material(tmp_path, d) is None


def test_preset_may_not_escape_its_namespace(tmp_path):
    """[UMAT-14] Refused, not silently dropped.

    Dropping a foreign key would leave a preset that does not do what it says, and
    ``_import_scoped`` applies presets by WRITING into the theme — so a drop-in could
    recolour a shipped material.
    """
    d = _descriptor(presets=[
        {"id": "evil", "tokens": {"--evcc-floor-wood-base-opacity": 0}, "colors": {}},
    ])
    assert _material(tmp_path, d) is None


@pytest.mark.parametrize(
    ("legend", "mutate"),
    [
        ("UMAT-15", lambda d: d.update(
            layers=[dict(d["layers"][0], suffix="s%d" % i) for i in range(um.MAX_LAYERS + 1)])),
        ("UMAT-16", lambda d: d["layers"][0].update(opacity=4)),
        ("UMAT-16", lambda d: d["layers"][0].update(opacity="loads")),
        ("UMAT-17", lambda d: d.update(layers=[d["layers"][0], dict(d["layers"][0])])),
        ("UMAT-21", lambda d: d["layers"][0].pop("opacity")),
    ],
)
def test_descriptor_shape_is_enforced(tmp_path, legend, mutate):
    """[UMAT-15..17, 21] Caps, ranges, uniqueness -- and that opacity is REQUIRED."""
    d = _descriptor()
    mutate(d)
    assert _material(tmp_path, d) is None, legend


def test_build_catalog_writes_and_skips_the_broken_one(tmp_path):
    """[UMAT-18] One bad drop-in must not cost the good ones."""
    for name, material_id in (("good", "goodstone"), ("bad", "wood")):
        d = tmp_path / name
        d.mkdir()
        (d / "m.png").write_bytes(GOOD_MASK)
        (d / "material.json").write_text(
            json.dumps(_descriptor(id=material_id)), encoding="utf-8"
        )

    count = um.build_catalog(str(tmp_path), TEXTURES)
    assert count == 1
    written = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert [e["id"] for e in written] == ["goodstone"]


def test_build_catalog_never_raises_on_a_missing_directory(tmp_path):
    """[UMAT-19] A broken drop-in dir cannot stop the integration starting."""
    assert um.build_catalog(str(tmp_path / "does-not-exist"), TEXTURES) == 0


def test_png_header_reads_ihdr_without_a_decoder(tmp_path):
    """[UMAT-20] 26 bytes, no Pillow — which is why the canvas check is cheap enough
    to run on every drop-in at every startup."""
    assert um.png_header(_png(2048, 2048, 0, 1)) == (2048, 2048, 8, 0)
    assert um.png_header(_png(640, 480, 2, 3)) == (640, 480, 8, 2)
    assert um.png_header(b"too short") is None
    assert um.png_header(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40) is None
