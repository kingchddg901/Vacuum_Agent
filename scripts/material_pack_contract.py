#!/usr/bin/env python3
"""The drop-in material pack contract — emit it, or check a pack against it.

WHY THIS EXISTS, AND WHY IT IS NOT A SECOND COPY OF THE RULES
=============================================================
A generator (Material Author) has to write `material.json` that VA will accept. The
tempting way to make that possible is to write the rules down twice: once in
``user_materials.py`` where they are enforced, once in the generator where they are
obeyed. That is a replica, and replicas drift — ``docs/dev/00c-replicas.md`` exists
because of the ones already here.

So this module does NOT restate a single rule. It IMPORTS the shipped validator and
derives everything from it:

    --schema   a JSON Schema built from the live ID_RE / SUFFIX_RE / FILE_RE / FROM_RE /
               COLOR_RE / MAX_LAYERS / RESERVED_NAMES. If someone tightens a regex in
               user_materials.py, the schema tightens with it on the next run.
    <dir>      runs the REAL validate_material() against a pack directory and prints
               every refusal, verbatim, in the order the integration would log them.

If this file and the validator ever disagree, this file is wrong by construction —
there is nothing here to disagree with.

WHAT A SCHEMA CANNOT EXPRESS
----------------------------
Three of the hard requirements are properties of the FILES, not the descriptor, and the
validator reads them out of each PNG's IHDR rather than believing the JSON:

    canvas 2048x2048 · PNG colour type 0 (greyscale) · bit depth 8

Those are checked by the ``<dir>`` mode only. A generator that validates against the
schema alone has checked half the contract. Run the directory check.

THE UNIFORM-PRIMARY WARNING
---------------------------
One failure is legal, silent and purely visual: the SVG MAP POLYGON surface paints the PRIMARY
layer untinted as a single pattern fill, so a primary that is a near-flat field renders
as a grey wash. ``user-materials.js`` names slate as the case — its face mask is a
uniform 235, which is why slate marks ``cleft`` primary instead of defaulting to layer 0.
This warns when the primary's contrast is below a threshold CALIBRATED FROM THE SHIPPED
MASKS (see ``--calibrate``), not from a number someone liked. It is a warning, never a
refusal: a flat primary is a legitimate choice for a material that really is flat.

Needs numpy for that one check only, and says so when numpy is absent rather than
silently skipping it.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import logging
import os
import sys
import zlib

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DEFAULT_TEXTURES = os.path.join(_REPO, "custom_components", "eufy_vacuum", "textures")


def _load_validator():
    """Import the SHIPPED user_materials.py without needing Home Assistant.

    It is pure stdlib (json/logging/os/re/typing), so a direct spec load works and the
    checker runs on a bare python with no HA, no venv and no test image.
    """
    path = os.path.join(_REPO, "custom_components", "eufy_vacuum", "user_materials.py")
    spec = importlib.util.spec_from_file_location("_evcc_user_materials", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# SCHEMA — derived, never written out by hand
# ---------------------------------------------------------------------------
def build_schema(um) -> dict:
    """A JSON Schema for material.json, built from the validator's own constants."""
    colour = {"type": "string", "pattern": um.COLOR_RE.pattern,
              "description": "#rrggbb or #rrggbbaa"}
    opacity = {"type": "number", "minimum": 0.0, "maximum": 1.0}

    layer = {
        "type": "object",
        "required": ["suffix", "color", "opacity"],
        "additionalProperties": False,
        "properties": {
            "suffix": {
                "type": "string", "pattern": um.SUFFIX_RE.pattern,
                "description": "Mints --evcc-floor-<id>-<suffix>. Unique within the pack.",
            },
            "file": {
                "type": "string", "pattern": um.FILE_RE.pattern,
                "description": "A PNG in this pack's own directory. Mutually exclusive with 'from'.",
            },
            "from": {
                "type": "string", "pattern": um.FROM_RE.pattern,
                "description": "Borrow a SHIPPED mask: '<dir>/<file>.png'. Mutually exclusive with 'file'.",
            },
            "color": colour,
            "opacity": opacity,
            "primary": {
                "type": "boolean",
                "description": "At most ONE layer in the pack may set this true.",
            },
        },
        "oneOf": [
            {"required": ["file"], "not": {"required": ["from"]}},
            {"required": ["from"], "not": {"required": ["file"]}},
        ],
    }

    preset = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "tokens": {"type": "object"},
            "colors": {"type": "object"},
        },
        "description": (
            "Every key in 'tokens' and 'colors' MUST start with --evcc-floor-<id>- . "
            "One stray key rejects the whole pack, not just the preset."
        ),
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/kingchddg901/Vacuum_Agent/material-pack.schema.json",
        "title": "Vacuum Agent drop-in floor material",
        "description": (
            "GENERATED from custom_components/eufy_vacuum/user_materials.py by "
            "scripts/material_pack_contract.py --schema. Do not hand-edit. "
            "Passing this schema is NECESSARY, NOT SUFFICIENT: canvas size, PNG colour "
            "type and bit depth are read from the files and are not expressible here. "
            "Run `python scripts/material_pack_contract.py <dir>` for the whole contract."
        ),
        "type": "object",
        "required": ["schema", "id", "layers"],
        "additionalProperties": False,
        "properties": {
            "schema": {"const": 1, "description": "Exactly 1. Any other value rejects the pack."},
            "id": {
                "type": "string", "pattern": um.ID_RE.pattern,
                "not": {"enum": list(um.RESERVED_NAMES)},
                "description": (
                    "The namespace. Mints every token name, is the registry key, and is "
                    "what a room's stored floor_material references — the one "
                    "irreversible commitment in the pack. Must not EQUAL, PREFIX, or BE "
                    "PREFIXED BY (hyphen-separated) any reserved name: "
                    + ", ".join(um.RESERVED_NAMES)
                ),
            },
            "name": {"type": "string", "description": "Display name. Defaults to id. The only string a user sees."},
            "family": {"type": "string", "description": "Free-text grouping, e.g. stone / wood / glass. Never validated."},
            "scale": {
                "type": "number", "exclusiveMinimum": 0,
                "description": "Feature scale. Clamped to 0.02..2 at render (bindings/map.js). <=0 is dropped to null.",
            },
            "opacity": opacity,
            "layers": {
                "type": "array", "minItems": 1, "maxItems": um.MAX_LAYERS,
                "items": layer,
            },
            "presets": {"type": "array", "items": preset},
        },
    }


# ---------------------------------------------------------------------------
# UNIFORMITY — the one check that needs the pixels
# ---------------------------------------------------------------------------
def _decode_grey(path: str):
    """2048x2048 greyscale PNG -> numpy uint8 array, or None if numpy is absent."""
    try:
        import numpy as np
    except ImportError:
        return None
    raw = io.open(path, "rb").read()
    w = int.from_bytes(raw[16:20], "big")
    h = int.from_bytes(raw[20:24], "big")
    idat = bytearray()
    i = 8
    while i < len(raw):
        ln = int.from_bytes(raw[i:i + 4], "big")
        typ = raw[i + 4:i + 8]
        if typ == b"IDAT":
            idat += raw[i + 8:i + 8 + ln]
        i += 12 + ln
        if typ == b"IEND":
            break
    data = zlib.decompress(bytes(idat))
    out = np.zeros((h, w), dtype=np.uint8)
    prev = np.zeros(w, dtype=np.int16)
    pos = 0
    for y in range(h):
        ft = data[pos]; pos += 1
        line = np.frombuffer(data[pos:pos + w], dtype=np.uint8).astype(np.int16).copy()
        pos += w
        if ft == 0:
            cur = line
        elif ft == 2:
            cur = (line + prev) & 0xFF
        else:
            cur = line
            for x in range(w):
                a = cur[x - 1] if x else 0
                b = prev[x]
                c = prev[x - 1] if x else 0
                if ft == 1:
                    cur[x] = (cur[x] + a) & 0xFF
                elif ft == 3:
                    cur[x] = (cur[x] + ((a + b) >> 1)) & 0xFF
                else:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    cur[x] = (cur[x] + pr) & 0xFF
        out[y] = cur.astype(np.uint8)
        prev = cur
    return out


def contrast(path: str):
    """Standard deviation of a mask's luminance, or None if it could not be measured."""
    try:
        img = _decode_grey(path)
    except Exception:
        return None
    if img is None:
        return None
    return float(img.std())


# MEASURED, not chosen. Two populations, and the gap between them is wide and empty:
#
#   flat field that washes   slate/face.png                     0.00   (the one case)
#   lowest structural mask   concrete/concrete-broad-mask.png   2.85
#   highest                  marble/marble-vein-minor.png      81.12
#
# 1.5 sits between, flagging nothing shipped and catching an exactly-constant mask with
# room to spare.
#
# SECOND MEMBER, 2026-11-13: Material Author's exported `base` mask also measures 0.00 —
# reported by the MA session, not measured here (its file is in that session's
# scratchpad). Its mechanism is the SAME as slate/face.png's, not an independent one:
# a VALUE map standing in for a COVERAGE map, which on a plain slab is a constant fill.
# So this is now a recurring mechanism seen from two generators, which is a reason to
# trust the CHECK — not a reason to call the threshold measured. The bad population is
# still one number, 0.00, observed twice.
#
# HONEST LIMIT: nothing has ever been observed between 0.00 and 2.85, so the threshold's
# position inside that gap is unconstrained. It stays a warning and never a refusal.
# Re-derive with --calibrate if the shipped set changes.
FLAT_PRIMARY_STD = 1.5


# ---------------------------------------------------------------------------
# CHECK
# ---------------------------------------------------------------------------
class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def check_pack(dir_path: str, textures_dir: str, quiet: bool = False) -> int:
    """Run the SHIPPED validator against one pack directory. Returns an exit code."""
    um = _load_validator()
    cap = _Capture()
    log = logging.getLogger(um.__name__)
    log.addHandler(cap)
    log.setLevel(logging.WARNING)
    log.propagate = False

    entry = um.validate_material(dir_path, textures_dir)

    name = os.path.basename(os.path.abspath(dir_path.rstrip(os.sep)))
    if entry is None:
        print(f"REFUSED  {name}")
        for line in cap.lines:
            print(f"    {line}")
        if not cap.lines:
            print("    (no reason logged - the directory name may not match "
                  f"{um.DIR_RE.pattern}, or material.json is missing)")
        return 1

    print(f"ACCEPTED {name}   id={entry['id']!r}  layers={len(entry['layers'])}  "
          f"presets={len(entry['presets'])}")
    for line in cap.lines:
        print(f"    note: {line}")

    # --- warnings the validator deliberately does not refuse on ---------------
    warns: list[str] = []

    if entry.get("scale") is None and "scale" in _raw_desc(dir_path):
        warns.append("'scale' was declared but did not survive validation - it is "
                     "coerced, never refused. Must be a JSON number.")
    if entry.get("opacity") is None and "opacity" in _raw_desc(dir_path):
        warns.append("'opacity' was declared but did not survive validation - "
                     "coerced, never refused. Must be a JSON number.")
    scale = entry.get("scale")
    if isinstance(scale, float) and not (0.02 <= scale <= 2.0):
        warns.append(f"scale {scale} is outside 0.02..2 and WILL be clamped at render "
                     "(bindings/map.js) — the declared value is not what you get.")

    primary = next((l for l in entry["layers"] if l["primary"]), entry["layers"][0])
    chosen = "declared" if any(l["primary"] for l in entry["layers"]) else "defaulted to layer 0"
    root = textures_dir if primary["borrowed"] else dir_path
    ppath = um.contained_path(root, primary["path"])
    std = contrast(ppath) if os.path.isabs(ppath) else None
    if std is None:
        warns.append(f"primary layer {primary['suffix']!r} ({chosen}): contrast NOT "
                     "measured (numpy unavailable) — the flat-primary check did not run.")
    elif std < FLAT_PRIMARY_STD:
        warns.append(
            f"primary layer {primary['suffix']!r} ({chosen}) has contrast {std:.1f}, "
            f"below {FLAT_PRIMARY_STD} - the SVG map polygon surface paints the primary "
            "UNTINTED as one pattern fill, so a near-flat primary renders as a grey "
            "wash. Mark a structural layer \"primary\": true instead."
        )
    elif not quiet:
        print(f"    primary {primary['suffix']!r} ({chosen}) contrast {std:.1f} - OK")

    for w in warns:
        print(f"    WARN: {w}")
    return 0


def _raw_desc(dir_path: str) -> dict:
    try:
        with io.open(os.path.join(dir_path, "material.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def calibrate(textures_dir: str) -> int:
    """Print the contrast of every shipped mask, so FLAT_PRIMARY_STD is a measured number.

    The threshold must sit ABOVE the flat fields the docstring names and BELOW every
    structural mask, or it cannot do its job. This prints both populations.
    """
    rows = []
    for root, _dirs, files in os.walk(textures_dir):
        for f in sorted(files):
            if f.endswith(".png"):
                p = os.path.join(root, f)
                rows.append((contrast(p), os.path.relpath(p, textures_dir).replace("\\", "/")))
    if not rows or rows[0][0] is None:
        print("numpy unavailable — cannot calibrate.")
        return 1
    rows.sort(key=lambda r: (r[0] is None, r[0]))
    print(f"contrast (std of luminance) for {len(rows)} shipped masks, lowest first")
    print(f"current FLAT_PRIMARY_STD = {FLAT_PRIMARY_STD}")
    for std, nm in rows:
        mark = "  <-- below threshold" if std is not None and std < FLAT_PRIMARY_STD else ""
        print(f"  {std:8.2f}  {nm}{mark}")
    return 0


def main(argv=None) -> int:
    # The Windows console defaults to cp1252, which turns every em-dash in a refusal
    # message into a replacement char. The refusals are quoted from the validator and
    # are meant to be pasteable, so fix the STREAM rather than flattening the text.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dirs", nargs="*", help="pack directories to check")
    ap.add_argument("--schema", action="store_true", help="print the JSON Schema and exit")
    ap.add_argument("--calibrate", action="store_true",
                    help="print shipped-mask contrast, to justify FLAT_PRIMARY_STD")
    ap.add_argument("--verify-schema", metavar="PATH",
                    help="fail if the committed schema has drifted from the validator")
    ap.add_argument("--textures", default=_DEFAULT_TEXTURES,
                    help="shipped textures dir, for borrowed layers")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.schema:
        print(json.dumps(build_schema(_load_validator()), indent=2))
        return 0
    if args.verify_schema:
        # A committed schema is a replica of the validator and replicas drift SILENTLY.
        # This is the gate that makes the committed copy provable rather than hopeful.
        fresh = json.dumps(build_schema(_load_validator()), indent=2, sort_keys=True)
        try:
            on_disk = io.open(args.verify_schema, encoding="utf-8").read()
        except OSError as err:
            print(f"STALE: cannot read {args.verify_schema} ({err})")
            return 1
        if json.dumps(json.loads(on_disk), indent=2, sort_keys=True) != fresh:
            print(f"STALE: {args.verify_schema} no longer matches user_materials.py.\n"
                  f"       Regenerate: python scripts/material_pack_contract.py --schema "
                  f"> {args.verify_schema}")
            return 1
        print(f"CURRENT: {args.verify_schema} matches the validator")
        return 0
    if args.calibrate:
        return calibrate(args.textures)
    if not args.dirs:
        ap.print_help()
        return 2

    worst = 0
    for d in args.dirs:
        worst = max(worst, check_pack(d, args.textures, args.quiet))
    return worst


if __name__ == "__main__":
    sys.exit(main())
