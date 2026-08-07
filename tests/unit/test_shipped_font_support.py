"""The shipped FONT_SUPPORT list must match what the font FILES actually prove.

FONT_SUPPORT (src/i18n/font-store.js) is a static, hand-committed offering —
deliberately: no runtime cost, and a human may RESTRICT it below the evidence
(quality judgement). But it must never CLAIM more than the artifact proves,
and it must never silently rot when the woff2 files change: the 2026-08-06
widening happened precisely because the previous hand-written list was wrong
about the actual files in both directions.

This test re-derives the verifiable locale set from the shipped woff2 files
using the SAME instrument the drop-in intake uses (user_fonts: cmap
intersection across faces, textual-characters-only requirements, GSUB for
shaping locales) and asserts the baked list equals it. If a future font
release changes coverage, this fails loudly instead of the offering drifting
from the evidence. A deliberate restriction below evidence would be encoded
here as an explicit, commented exclusion — never silently.
"""

import re
from pathlib import Path

import pytest

fontTools = pytest.importorskip(
    "fontTools", reason="fonttools[woff2] required — see requirements_test.txt"
)

from custom_components.eufy_vacuum.user_fonts import (  # noqa: E402
    SHAPING_LOCALES,
    _face_codepoints,
    locale_char_requirements,
)

REPO = Path(__file__).resolve().parents[2]
FONTS_DIR = REPO / "custom_components" / "eufy_vacuum" / "frontend" / "fonts"
LOCALES_DIR = REPO / "custom_components" / "eufy_vacuum" / "frontend" / "locales"
FONT_STORE = REPO / "src" / "i18n" / "font-store.js"


def _declared_support() -> dict[str, set[str]]:
    """FONT_SUPPORT parsed out of the JS source (the shipped declaration)."""
    src = FONT_STORE.read_text(encoding="utf-8")
    block = re.search(r"export const FONT_SUPPORT = \{(.*?)\n\};", src, re.S)
    assert block, "FONT_SUPPORT literal not found — the parse contract moved"
    out: dict[str, set[str]] = {}
    for font_id, langs in re.findall(
        r"(\w+):\s*new Set\(\[(.*?)\]\)", block.group(1), re.S
    ):
        out[font_id] = set(re.findall(r'"([\w-]+)"', langs))
    assert out, "no FONT_SUPPORT entries parsed"
    return out


def test_shipped_support_matches_the_font_files():
    declared = _declared_support()
    # One shipped font today. A second one needs this test to learn the
    # id -> face-files mapping (FONT_DEFS) — extend it then, deliberately.
    assert set(declared) == {"opendyslexic"}, (
        "a new shipped font appeared — teach this test its face files so its "
        "offering is artifact-pinned like opendyslexic's"
    )

    faces = sorted(FONTS_DIR.glob("*.woff2"))
    assert faces, "shipped woff2 files missing"

    codepoints: set[int] | None = None
    has_gsub = True
    for face in faces:
        parsed = _face_codepoints(str(face))
        assert parsed is not None, "fontTools present but face parse unavailable"
        cps, gsub = parsed
        assert cps, f"{face.name}: empty cmap — unreadable face"
        codepoints = cps if codepoints is None else codepoints & cps
        has_gsub = has_gsub and gsub

    reqs = locale_char_requirements(str(LOCALES_DIR))
    derived = {
        lang
        for lang, need in reqs.items()
        if need
        and need.issubset(codepoints)
        and (lang not in SHAPING_LOCALES or has_gsub)
    }

    assert declared["opendyslexic"] == derived, (
        "FONT_SUPPORT.opendyslexic no longer matches what the shipped woff2 "
        f"files prove.\n  declared-but-unproven: {sorted(declared['opendyslexic'] - derived)}"
        f"\n  proven-but-not-offered: {sorted(derived - declared['opendyslexic'])}\n"
        "If the font files changed, update the JS list from this evidence; a "
        "deliberate restriction goes HERE as a commented exclusion."
    )
