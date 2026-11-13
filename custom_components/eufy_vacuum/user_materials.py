"""Drop-in floor materials: discover, validate, catalogue.

A drop-in material is a subdirectory of ``config/eufy_vacuum/materials/`` holding a
``material.json`` descriptor and its greyscale mask PNGs::

    config/eufy_vacuum/materials/
      slate/
        material.json
        cleft.png  joint.png  cut-a.png  ...

That location is deliberate and matches the drop-in fonts and locales: it lives under the
HA **config** dir, which survives a HACS/Marketplace update. The integration directory
does not — it is replaced wholesale — and it is also the release payload, so anything put
there ships to every user (see ``scripts/check-texture-assets.mjs``, and the 20 MB of
generator sources that shipped inert from 2026-07-04 until ``d902c5af``).

THE FILE IS THE EVIDENCE, NOT THE DESCRIPTOR. That is ``user_fonts.py``'s governing rule
and it applies with more force here, because two of the failure modes are silent:

* **Canvas.** ``FLOOR_TEXTURE_MASK_SCALE_BY_TYPE`` in ``src/bindings/map.js`` is tuned by
  eye against 2048x2048 and the decode path never reads the bitmap's own width, so a mask
  at another size changes tile period and feature size together and two layers from
  different canvases desynchronise. No error, just misalignment.
* **Colour type.** The compositor reads luminance only. An RGB mask costs ~3x the bytes
  for no gain, and nothing downstream would complain.

Both are readable from 26 bytes of PNG header, so neither is expensive to refuse.

THE ID IS A NAMESPACE. Token names are minted from it by rule
(``--evcc-floor-<id>-<suffix>``), so an id equal to a shipped floor type mints keys that
already exist, and ``assertUniqueTokenKeys`` in ``src/theme-tokens/index.js`` *throws* --
with the initial ``rebuild()`` unguarded, which takes the card down. An id that is a
PREFIX of a shipped name is worse than it looks: the scoped-theme import clears by raw
prefix (``themes/manager.py``: ``prefix = f"--evcc-floor-{name}-"``), so importing
``carpet`` would wipe ``carpet-high``'s and ``carpet-low``'s tokens. Hence: not equal, not
a prefix, not prefixed by.

WHAT THIS MODULE DOES NOT TOUCH: ``floor_type``. That field carries the carpet-water-off
guarantee (``profiles/room_profiles.py::no_water_value``, plus ``startswith("carpet")`` at
fourteen sites) and stays a closed eight-value vocabulary. A drop-in material is selected
through the separate ``floor_material`` key, so a stranger's naming can never decide
whether a room gets mopped.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

CANVAS = 2048
MAX_LAYERS = 8          # marble is the shipped maximum at 4; slate needs 7

DIR_RE = re.compile(r"^[\w-]{1,64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
SUFFIX_RE = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
FILE_RE = re.compile(r"^[\w][\w.-]*\.png$")
FROM_RE = re.compile(r"^[a-z_]+/[\w][\w.-]*\.png$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
ENCODED_SEP_RE = re.compile(r"%2e|%2f|%5c", re.IGNORECASE)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# ⚠ REPLICA of the floor vocabulary. The authoritative list is JS -- the keys of
# FLOOR_TEXTURE_REGISTRY (src/textures/floor-texture-registry.js), surfaced hyphenated by
# floorTypeNames() -- and Python cannot import it. Both spellings are reserved because a
# custom id is compared against names the card will mint tokens for, and the persisted
# vocabulary in profiles/room_profiles.py::_normalize_floor_type uses the underscored
# form. Adding a shipped material means adding it here too; see docs/dev/00c-replicas.md.
RESERVED_NAMES: tuple[str, ...] = (
    # registry keys, hyphenated (what floorTypeNames() returns)
    "carpet-high", "carpet-low", "concrete", "granite-light", "marble", "tile", "wood",
    # persisted floor_type values
    "carpet_high_pile", "carpet_low_pile", "granite", "hardwood", "laminate",
    # the registry's fallback entry
    "default",
)


def png_header(data: bytes) -> tuple[int, int, int, int] | None:
    """``(width, height, bit_depth, colour_type)`` from a PNG's IHDR, or ``None``.

    The PNG spec fixes IHDR as the first chunk, so these sit at bytes 16-25 of any valid
    PNG and no decoder is needed -- which matters because Pillow is an OPTIONAL dependency
    here (the manifest declares none).

    ⚠ ``mapping/mapping_services.py::_png_dimensions`` reads the same bytes for the upload
    path but returns width/height only. Two readers of one header is a replica; this one
    needs the two extra bytes, that one predates it and is separately tested. If either
    changes, change both.
    """
    if len(data) < 26 or not data.startswith(_PNG_MAGIC) or data[12:16] != b"IHDR":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return (width, height, data[24], data[25])


def contained_path(base_dir: str, rel: str) -> str:
    """Resolve ``rel`` under ``base_dir``, or return a REASON string.

    A regex is a denylist of spellings; what matters is where the path LANDS. Two holes a
    pattern cannot see: a symlink (and a symlinked DIRECTORY defeats a check on the leaf
    alone, which is why ``user_fonts.py`` refuses ``islink`` at three separate places),
    and anything the pattern is later loosened to admit.
    """
    if not rel:
        return "empty path"
    if os.path.isabs(rel) or re.match(r"^[A-Za-z]:", rel):
        return "absolute paths are not allowed"
    if "\\" in rel:
        return "use / as the separator, not a backslash"
    if ENCODED_SEP_RE.search(rel):
        return "percent-encoded path separators are not allowed"
    if "\x00" in rel:
        return "null byte in path"

    base = os.path.realpath(base_dir)
    target = os.path.normpath(os.path.join(base, rel))
    if target != base and not target.startswith(base + os.sep):
        return f"escapes {base_dir}"

    # Walk every component: a symlinked directory defeats a leaf-only test.
    cur = base
    for part in os.path.relpath(target, base).split(os.sep):
        if not part or part == ".":
            continue
        cur = os.path.join(cur, part)
        if not os.path.exists(cur):
            return f"missing: {os.path.relpath(cur, base)}"
        if os.path.islink(cur):
            return f"symlink in the path at {os.path.relpath(cur, base)}"
    if not os.path.isfile(target):
        return "not a regular file"
    return target


def id_conflict(material_id: str, reserved: tuple[str, ...] = RESERVED_NAMES) -> str | None:
    """Why this id may not be used, or ``None``. See the module docstring."""
    for name in reserved:
        if material_id == name:
            return (
                f'"{material_id}" is a reserved floor-type name -- minting its tokens '
                f"would duplicate existing keys, and assertUniqueTokenKeys throws"
            )
        if name.startswith(material_id + "-"):
            return (
                f'"{material_id}" is a PREFIX of reserved "{name}" -- a scoped theme '
                f"import of it clears every --evcc-floor-{material_id}-* key, "
                f"which includes {name}'s"
            )
        if material_id.startswith(name + "-"):
            return (
                f'"{material_id}" is prefixed BY reserved "{name}" -- a scoped theme '
                f'import of "{name}" would clear this material\'s tokens'
            )
    return None


def _layer_problem(layer: Any, index: int, seen: set[str]) -> str | None:
    """Shape-only checks. Containment and the file header are done by the caller."""
    where = f"layer {index}"
    if not isinstance(layer, dict):
        return f"{where}: not an object"
    borrowed = isinstance(layer.get("from"), str)
    if borrowed:
        if not FROM_RE.match(layer["from"]):
            return f'{where}: from must be "<dir>/<file>.png" under the shipped textures'
    else:
        f = layer.get("file")
        if not isinstance(f, str) or not FILE_RE.match(f):
            return f"{where}: file must match {FILE_RE.pattern}"
    suffix = layer.get("suffix")
    if not isinstance(suffix, str) or not SUFFIX_RE.match(suffix):
        return f"{where}: suffix must match {SUFFIX_RE.pattern}"
    if suffix in seen:
        return f'{where}: duplicate suffix "{suffix}"'
    colour = layer.get("color")
    if not isinstance(colour, str) or not COLOR_RE.match(colour):
        return f"{where}: color must be #rrggbb or #rrggbbaa"
    try:
        opacity = float(layer.get("opacity"))
    except (TypeError, ValueError):
        return f"{where}: opacity must be a number 0..1"
    if not 0.0 <= opacity <= 1.0:
        return f"{where}: opacity {opacity} is outside 0..1"
    return None


def validate_material(
    dir_path: str,
    textures_dir: str,
    reserved: tuple[str, ...] = RESERVED_NAMES,
) -> dict | None:
    """Validate one drop-in directory into a catalogue entry, or ``None``.

    Conservative: every rejection is logged with the material and the reason, because a
    material that half-loads renders as nothing, and that reads exactly like a theme
    problem rather than a bad drop-in.
    """
    name = os.path.basename(dir_path.rstrip(os.sep))
    desc_path = contained_path(dir_path, "material.json")
    if not os.path.isabs(desc_path):
        _LOGGER.warning("user material %s: %s", name, desc_path)
        return None
    try:
        with open(desc_path, encoding="utf-8") as fh:
            desc = json.load(fh)
    except (OSError, ValueError) as err:
        _LOGGER.warning("user material %s: descriptor unreadable (%s)", name, err)
        return None

    if not isinstance(desc, dict) or desc.get("schema") != 1:
        _LOGGER.warning("user material %s: schema must be 1", name)
        return None
    material_id = desc.get("id")
    if not isinstance(material_id, str) or not ID_RE.match(material_id):
        _LOGGER.warning("user material %s: id must match %s", name, ID_RE.pattern)
        return None
    clash = id_conflict(material_id, reserved)
    if clash:
        _LOGGER.warning("user material %s: %s", name, clash)
        return None

    raw_layers = desc.get("layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        _LOGGER.warning("user material %s: no layers", name)
        return None
    if len(raw_layers) > MAX_LAYERS:
        _LOGGER.warning(
            "user material %s: %d layers, max %d", name, len(raw_layers), MAX_LAYERS
        )
        return None

    seen: set[str] = set()
    layers: list[dict] = []
    for i, layer in enumerate(raw_layers):
        problem = _layer_problem(layer, i, seen)
        if problem:
            _LOGGER.warning("user material %s: %s", name, problem)
            return None
        seen.add(layer["suffix"])

        borrowed = isinstance(layer.get("from"), str)
        root = textures_dir if borrowed else dir_path
        rel = layer["from"] if borrowed else layer["file"]
        resolved = contained_path(root, rel)
        if not os.path.isabs(resolved):
            _LOGGER.warning("user material %s: layer %d (%s): %s", name, i, rel, resolved)
            return None

        try:
            with open(resolved, "rb") as fh:
                header = png_header(fh.read(32))
        except OSError as err:
            _LOGGER.warning("user material %s: layer %d unreadable (%s)", name, i, err)
            return None
        if header is None:
            _LOGGER.warning("user material %s: layer %d (%s) is not a PNG", name, i, rel)
            return None
        width, height, depth, colour_type = header
        if (width, height) != (CANVAS, CANVAS):
            _LOGGER.warning(
                "user material %s: layer %d (%s) is %dx%d, must be %dx%d -- the feature "
                "scales are tuned to that canvas and the decode path never reads the "
                "bitmap's own width, so another size misaligns silently",
                name, i, rel, width, height, CANVAS, CANVAS,
            )
            return None
        if colour_type != 0:
            _LOGGER.warning(
                "user material %s: layer %d (%s) has PNG colour type %d, must be 0 "
                "(greyscale) -- the compositor reads luminance only",
                name, i, rel, colour_type,
            )
            return None
        if depth != 8:
            _LOGGER.warning(
                "user material %s: layer %d (%s) is %d-bit, must be 8",
                name, i, rel, depth,
            )
            return None

        layers.append({
            "suffix": layer["suffix"],
            "color": layer["color"],
            "opacity": float(layer["opacity"]),
            "borrowed": borrowed,
            "path": rel,
            "primary": layer.get("primary") is True,
        })

    primaries = [l for l in layers if l["primary"]]
    if len(primaries) > 1:
        _LOGGER.warning(
            "user material %s: %d layers marked primary (%s); exactly one may be",
            name, len(primaries), ", ".join(l["suffix"] for l in primaries),
        )
        return None

    # A preset may only name tokens in its OWN namespace. Silently dropping a foreign key
    # is worse than refusing: the preset would not do what it says, and _import_scoped
    # applies presets by WRITING into the theme, so a drop-in could recolour a shipped
    # material.
    namespace = f"--evcc-floor-{material_id}-"
    presets: list[dict] = []
    for preset in desc.get("presets") or []:
        if not isinstance(preset, dict):
            continue
        keys = list((preset.get("tokens") or {})) + list((preset.get("colors") or {}))
        stray = [k for k in keys if not str(k).startswith(namespace)]
        if stray:
            _LOGGER.warning(
                "user material %s: preset %s names tokens outside %s (%s) -- rejected",
                name, preset.get("id"), namespace, ", ".join(map(str, stray[:4])),
            )
            return None
        presets.append({
            "id": str(preset.get("id") or ""),
            "name": str(preset.get("name") or preset.get("id") or ""),
            "tokens": preset.get("tokens") or {},
            "colors": preset.get("colors") or {},
        })

    return {
        "id": material_id,
        "name": str(desc.get("name") or material_id),
        "family": str(desc.get("family") or "") or None,
        "scale": float(desc["scale"]) if isinstance(desc.get("scale"), (int, float)) else None,
        "opacity": float(desc["opacity"]) if isinstance(desc.get("opacity"), (int, float)) else None,
        "dir": name,
        "layers": layers,
        "presets": presets,
    }


def build_catalog(materials_dir: str, textures_dir: str) -> int:
    """Validate every drop-in under ``materials_dir`` and write ``catalog.json``.

    Returns the number catalogued. Never raises -- a broken drop-in is logged and skipped,
    exactly as ``user_fonts.build_catalog`` does, so one bad directory cannot stop the
    integration starting.
    """
    entries: list[dict] = []
    try:
        subdirs = sorted(os.listdir(materials_dir))
    except OSError:
        subdirs = []

    seen_ids: set[str] = set()
    for sub in subdirs:
        dir_path = os.path.join(materials_dir, sub)
        if not DIR_RE.match(sub) or not os.path.isdir(dir_path) or os.path.islink(dir_path):
            continue
        entry = validate_material(dir_path, textures_dir)
        if entry is None:
            continue
        if entry["id"] in seen_ids:
            _LOGGER.warning(
                "user material %s: id %r already used by another drop-in -- skipped",
                sub, entry["id"],
            )
            continue
        seen_ids.add(entry["id"])
        entries.append(entry)

    try:
        with open(os.path.join(materials_dir, "catalog.json"), "w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False)
    except OSError as err:
        _LOGGER.warning("user materials: could not write catalog.json (%s)", err)
        return 0
    return len(entries)
