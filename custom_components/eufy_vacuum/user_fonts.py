"""User drop-in fonts: discovery, validation, and cmap-derived locale verification.

A drop-in font is a subdirectory of config/eufy_vacuum/fonts/ holding a
``font.json`` descriptor beside its woff2 files (and its licence — OFL etc.
travels with the font)::

    config/eufy_vacuum/fonts/
        atkinson/
            font.json
            Atkinson-Regular.woff2
            Atkinson-Bold.woff2
            OFL.txt

Descriptor::

    { "id": "atkinson",
      "family": "Atkinson Hyperlegible",
      "label": "Atkinson Hyperlegible",              # optional, verbatim
      "fallback": ["Arial", "sans-serif"],           # optional
      "faces": [ {"file": "Atkinson-Regular.woff2", "weight": 400},
                 {"file": "Atkinson-Bold.woff2",    "weight": 700} ] }

The descriptor deliberately does NOT declare which locales it supports — the
font itself is the evidence. Setup parses each face's ``cmap`` (fontTools)
and compares the exact codepoints present against every locale's actual
chrome characters (the shipped locale JSONs + the English reference). The
result is written to ``catalog.json`` — the canonical font-library response
the card consumes. The card trusts the CATALOG's verdicts, never the
descriptor's claims, and never a browser-side render heuristic: rendered-text
checks can lie through per-glyph fallback (the exact instrument class that
false-exonerated live:FONT-1), while the cmap cannot.

Shaping caveat: raw codepoint coverage cannot prove JOINED rendering for
complex scripts. Locales in ``SHAPING_LOCALES`` additionally require a GSUB
table; that is still a conservative existence check, not a shaping proof —
the direction of error is under-offer, which is the right direction for an
accessibility promise.

Verification is graceful about its own dependency: without fontTools (with
its woff2/brotli support) a drop-in is catalogued as ``unverified`` with no
locales — present but never offered — and the log says why.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata

_LOGGER = logging.getLogger(__name__)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
DIR_RE = re.compile(r"^[\w-]{1,64}$")
FILE_RE = re.compile(r"^[\w][\w.-]*\.woff2$")
FAMILY_BAD_RE = re.compile(r'["\\{};\n\r]')
FALLBACK_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 -]{0,31}$")
GENERIC_FALLBACKS = {"sans-serif", "serif", "monospace"}

#: Locales whose scripts need shaping (joining) beyond codepoint coverage.
#: cmap can prove the letters exist; only GSUB machinery joins them.
SHAPING_LOCALES = {"ar"}

#: Characters below/at SPACE never count against coverage.
_MIN_CODEPOINT = 0x21


def _is_textual(ch: str) -> bool:
    """Whether a character counts against a font's coverage.

    Only LETTERS (with combining marks) and decimal digits do. Punctuation,
    symbols, arrows, check marks, emoji — the ✓ → · ⚠ class the chrome uses
    decoratively — deliberately do NOT: every font-family here is a real
    fallback CHAIN, a symbol falling through it renders correctly from the
    fallback, and no text typeface ships the full symbol repertoire. Demanding
    them would fail every real font for every locale (observed live: the
    shipped OpenDyslexic, human-verified for en, failed a full-chrome check).
    The promise stays: the locale's TEXT renders in the chosen font.
    """
    if ord(ch) < _MIN_CODEPOINT:
        return False
    cat = unicodedata.category(ch)
    return cat.startswith(("L", "M")) or cat == "Nd"


def validate_descriptor(raw: object) -> dict | None:
    """Normalize one ``font.json``; conservative — reject anything that could
    smuggle CSS, a path, or an implausible face. Field-level tolerance where
    harmless (bad weight -> 400, bad fallback entry -> dropped)."""
    if not isinstance(raw, dict):
        return None
    font_id = raw.get("id")
    if not isinstance(font_id, str) or not ID_RE.match(font_id):
        return None

    family = raw.get("family")
    if not isinstance(family, str):
        return None
    family = family.strip()
    if not family or len(family) > 64 or FAMILY_BAD_RE.search(family):
        return None

    label = raw.get("label")
    label = (
        re.sub(r'[<>"\\\n\r]', "", label.strip())[:64]
        if isinstance(label, str) and label.strip()
        else family
    )

    fallback: list[str] = []
    raw_fallback = raw.get("fallback")
    if isinstance(raw_fallback, list):
        for item in raw_fallback[:4]:
            if isinstance(item, str) and (
                item in GENERIC_FALLBACKS or FALLBACK_NAME_RE.match(item)
            ):
                fallback.append(item)
    if not fallback or fallback[-1] not in GENERIC_FALLBACKS:
        fallback.append("sans-serif")

    faces: list[dict] = []
    raw_faces = raw.get("faces")
    if isinstance(raw_faces, list):
        for f in raw_faces[:4]:
            if not isinstance(f, dict):
                continue
            file = f.get("file")
            if not isinstance(file, str) or not FILE_RE.match(file) or ".." in file:
                continue
            weight = f.get("weight")
            if not isinstance(weight, int) or not 100 <= weight <= 900:
                weight = 400
            faces.append({"file": file, "weight": weight})
    if not faces:
        return None

    return {
        "id": font_id,
        "family": family,
        "label": label,
        "fallback": fallback,
        "faces": faces,
    }


def _face_codepoints(path: str) -> tuple[set[int], bool] | None:
    """(codepoints, has_gsub) for one face, or None when fontTools (with
    woff2 support) is unavailable. A present-but-unreadable face returns an
    empty set — which correctly verifies as covering nothing."""
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415 - optional dep
    except ImportError:
        return None
    try:
        font = TTFont(path, lazy=True)
        try:
            cmap = font.getBestCmap() or {}
            return set(cmap.keys()), "GSUB" in font
        finally:
            font.close()
    except ImportError:
        # fontTools present but its woff2 DECODER dependency (brotli) is not —
        # newer fonttools dropped the [woff2] extra, so declare brotli
        # explicitly (manifest does). This is "cannot verify", never "covers
        # nothing": the two verdicts must not be conflated.
        return None
    except Exception as err:  # noqa: BLE001 - a broken drop-in must not break setup
        _LOGGER.warning("user font face %s is unreadable: %s", path, err)
        return set(), False


def strip_jsonc(text: str) -> str:
    """Remove ``//`` line comments from JSONC, quote-aware (URLs inside
    strings survive). The English reference catalogue ships as JSONC."""
    out_lines = []
    for line in text.splitlines():
        in_string = False
        escaped = False
        cut = len(line)
        for i, ch in enumerate(line):
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                cut = i
                break
        out_lines.append(line[:cut])
    return "\n".join(out_lines)


def _string_values(node: object, out: list[str]) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _string_values(v, out)
    elif isinstance(node, list):
        for v in node:
            _string_values(v, out)


def locale_char_requirements(shipped_locales_dir: str) -> dict[str, set[int]]:
    """lang -> the codepoints that locale's chrome can render. Every locale's
    requirement includes the ENGLISH base — untranslated keys fall back to
    English strings at runtime, so those characters are part of its chrome."""
    en_chars: set[int] = set()
    reqs: dict[str, set[int]] = {}
    ref = os.path.join(shipped_locales_dir, "en.reference.jsonc")
    try:
        with open(ref, encoding="utf-8") as fh:
            data = json.loads(strip_jsonc(fh.read()))
        strings: list[str] = []
        _string_values(data, strings)
        en_chars = {ord(c) for s in strings for c in s if _is_textual(c)}
    except (OSError, ValueError) as err:
        _LOGGER.warning("user fonts: English reference unreadable (%s)", err)
    reqs["en"] = set(en_chars)

    try:
        names = os.listdir(shipped_locales_dir)
    except OSError:
        return reqs
    for name in sorted(names):
        if not name.endswith(".json") or name == "index.json":
            continue
        lang = name[: -len(".json")]
        try:
            with open(os.path.join(shipped_locales_dir, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as err:
            _LOGGER.warning("user fonts: locale %s unreadable (%s)", name, err)
            continue
        strings = []
        _string_values(data, strings)
        chars = {ord(c) for s in strings for c in s if _is_textual(c)}
        reqs[lang] = chars | en_chars
    return reqs


def build_catalog(user_fonts_dir: str, shipped_locales_dir: str) -> int:
    """Discover + validate + verify every drop-in and write ``catalog.json``
    into ``user_fonts_dir``. Returns the number of catalogued fonts. Never
    raises — a broken drop-in is logged and skipped."""
    entries: list[dict] = []
    reqs: dict[str, set[int]] | None = None
    fonttools_missing = False

    try:
        subdirs = sorted(os.listdir(user_fonts_dir))
    except OSError:
        subdirs = []

    for sub in subdirs:
        dir_path = os.path.join(user_fonts_dir, sub)
        if not DIR_RE.match(sub) or not os.path.isdir(dir_path) or os.path.islink(dir_path):
            continue
        desc_path = os.path.join(dir_path, "font.json")
        if not os.path.isfile(desc_path) or os.path.islink(desc_path):
            continue
        try:
            with open(desc_path, encoding="utf-8") as fh:
                desc = validate_descriptor(json.load(fh))
        except (OSError, ValueError) as err:
            _LOGGER.warning("user font %s: descriptor unreadable (%s)", sub, err)
            continue
        if desc is None:
            _LOGGER.warning("user font %s: descriptor rejected", sub)
            continue

        face_paths = []
        for face in desc["faces"]:
            p = os.path.join(dir_path, face["file"])
            if not os.path.isfile(p) or os.path.islink(p):
                _LOGGER.warning("user font %s: missing face %s", sub, face["file"])
                face_paths = None
                break
            face_paths.append(p)
        if face_paths is None:
            continue

        # A character is renderable only if EVERY declared face carries it —
        # a bold-only (or regular-only) glyph would render mixed-family text.
        # Conservative by design.
        codepoints: set[int] | None = None
        has_gsub = True
        for p in face_paths:
            parsed = _face_codepoints(p)
            if parsed is None:
                fonttools_missing = True
                codepoints = None
                break
            cps, gsub = parsed
            codepoints = cps if codepoints is None else (codepoints & cps)
            has_gsub = has_gsub and gsub

        if codepoints is None:
            status = "unverified"
            verified: list[str] = []
        else:
            status = "verified"
            if reqs is None:
                reqs = locale_char_requirements(shipped_locales_dir)
            verified = [
                lang
                for lang, need in sorted(reqs.items())
                if need
                and need.issubset(codepoints)
                and (lang not in SHAPING_LOCALES or has_gsub)
            ]

        entries.append(
            {
                "id": desc["id"],
                "family": desc["family"],
                "label": desc["label"],
                "dir": sub,
                "faces": desc["faces"],
                "fallback": desc["fallback"],
                "locales": verified,
                "status": status,
            }
        )

    # De-duplicate ids: first directory (sorted) wins, the rest are dropped.
    seen: set[str] = set()
    unique = []
    for e in entries:
        if e["id"] in seen:
            _LOGGER.warning("user font id %s duplicated — keeping the first", e["id"])
            continue
        seen.add(e["id"])
        unique.append(e)

    if fonttools_missing:
        _LOGGER.info(
            "user fonts: fontTools (with woff2 support) is not installed — "
            "drop-in fonts are catalogued but cannot be locale-verified, so "
            "they will not be offered"
        )

    try:
        with open(
            os.path.join(user_fonts_dir, "catalog.json"), "w", encoding="utf-8"
        ) as fh:
            json.dump(unique, fh, ensure_ascii=False)
    except OSError as err:
        _LOGGER.warning("user fonts: could not write catalog.json (%s)", err)
        return 0
    return len(unique)
