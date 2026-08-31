"""Score every Dreame guide string against the manual it claims to come from.

``dreame_upkeep_guides.py`` asserts that its content is Dreame's own wording. That is a
provenance claim, and provenance claims should be checkable rather than trusted. This
scores each authored step and note by BIGRAM OVERLAP with the care section of its
source manual.

WHAT IT CAN AND CANNOT DO — read this before believing a green run:

  * an entirely invented step scores ~8%                    -> caught
  * a wrong item swapped into a list of parts scores ~47%   -> caught
  * ONE swapped word in a faithful sentence scores ~93%     -> NOT caught

So it is a net for wholesale drift, not a proofreader. It exists because the first
attempt at this check used ``difflib`` longest-contiguous-match and flagged all 156
strings, including verbatim ones: the manuals' text layer interleaves adjacent columns,
so no long contiguous run survives extraction. Bigrams survive it; contiguity does not.
The lesson generalises — a probe that fires on everything is broken, not thorough.

Three entries score low legitimately, because they are RECAST rather than transcribed:
``sensor`` (a numbered figure legend folded into a sentence), ``filter`` (assembled
from the "Dust Box and Filter" section, which has no filter section of its own), and
the ``caster_wheel`` note (a bullet tail lifted out with its subject restored). Anything
else below the threshold is a defect.

Some manuals (notably the api-fetch/ corpus) embed a subsetted font with no ToUnicode
map, so their text layer extracts as mojibake even though the page renders perfectly.
Those pages are OCR'd from a 300-dpi render (pymupdf + the tesseract binary) so the family
is scored against its OWN manual rather than exempted. When a garbled page is hit and OCR
tooling is absent the run FAILS with an actionable message instead of emitting false
defects — an unverifiable provenance claim must not read as green.

NOT A CI GATE, and cannot become one: the manuals are vendor copyright and stay out of
the repo. Run it by hand after authoring or editing a family.

    python scripts/verify_dreame_guide_provenance.py [--manuals DIR] [--min 0.85]
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import unicodedata
from pathlib import Path

DEFAULT_MANUALS = Path.home() / "Documents/durable/dreame-port-fixture/manuals"

#: family -> (manual filename, EN care-section pages, 1-based inclusive)
#:
#: ⚠ PATHS REFRESHED for the post-dedup corpus layout (files moved to manuals/robot/ under
#: canonical names). The page ranges were probed against the ORIGINAL editions; where the
#: dedup kept a DIFFERENT edition of the same R-code the pages may not transfer and need
#: re-probing — flagged inline. Same-R-code editions (x50, x60_ultra, l50, l10s, both
#: aqua10) should still align.
SOURCES = {
    "x50": ("robot/x50_R2489A.pdf", range(22, 31)),
    "x60_ultra": ("robot/x60-ultra_R5089B.pdf", range(13, 16)),
    # edition drift: fixture now holds the 28-language R6001; re-probe if it flags.
    "x60_pro_ultra_complete": ("robot-unmatched/r6001-x60-series-en-de-fr-it-es-pl-nl-no-sv-el-p.pdf", range(14, 17)),
    # edition drift: fixture now holds the "Complete+1" R2394A; re-probe if it flags.
    "l20": ("robot/l20-ultra-complete+1_R2394A.pdf", range(20, 27)),
    # edition drift: fixture now holds the "Complete+1" R2416A; re-probe if it flags.
    "x40": ("robot/x40-ultra-complete+1_R2416A.pdf", range(19, 27)),
    "l50": ("robot/l50-ultra_R9493.pdf", range(23, 31)),
    "l10s_gen2": ("robot/l10s-ultra-gen-2_R2469X.pdf", range(19, 26)),
    # Both live under manuals/robot/. Page numbers here are PDF pages. NOTE the
    # fixture Track copy is the 220-page ONE-UP edition; the 110-page file that
    # arrived by hand is a two-up imposition of the same content, so its page
    # numbers do NOT transfer. Located by probing for "Routine Maintenance" and
    # "Charging Contacts and Signaling Area" rather than by arithmetic.
    "aqua10_ultra_track": ("robot/aqua10-ultra-track_R9528A.pdf", range(12, 15)),
    "aqua10_ultra_roller": ("robot/aqua10-ultra-roller_R9535.pdf", range(13, 16)),
    # --- overnight batch 2026-08-31: authored from the api-fetch corpus (Care/Maintenance
    # section page ranges are PDF pages, located by the agent that transcribed each) ---
    "matrix10": ("api-fetch/dreame.vacuum.r2513a__3f71ba99.pdf", range(14, 17)),
    "l60_ultra": ("api-fetch/dreame.vacuum.r5090a__a0c79c98.pdf", range(13, 16)),
    "l60_ultra_pe": ("api-fetch/dreame.vacuum.r50393__5bb8de70.pdf", range(14, 17)),
    "l40s_ultra": ("api-fetch/dreame.vacuum.r2551a__acbc1fa4.pdf", range(23, 32)),
    "d30_ultra": ("api-fetch/dreame.vacuum.r5057a__def7d841.pdf", range(13, 16)),
    # r2566a's text layer is a non-extractable (CID) font — scored via the OCR fallback
    # below. Care section is 1-based pages 10-13 (the bulk on p12).
    "d20_pro_plus": ("api-fetch/dreame.vacuum.r2566a__dbe6320d.pdf", range(10, 14)),
    "d20_plus": ("api-fetch/dreame.vacuum.r2564b__1fb0f250.pdf", range(12, 15)),
}

#: The recasts documented in the guide file's docstring. Expected to score low.
#:
#: ⚠ THIS IS AN EXEMPTION, SO IT NEEDS ITS OWN FLOOR. Waving a component/kind pair
#: through unconditionally would hide a wholly invented sensor step behind the same
#: label that excuses a legitimate rewrite — the exemption would be a bigger hole than
#: the check is a net. Real recasts score 57-80%; invented text scores ~8%. The floor
#: sits between them with room on both sides.
KNOWN_RECASTS = {("sensor", "steps"), ("filter", "steps"), ("filter", "notes"),
                 ("caster_wheel", "notes")}
RECAST_FLOOR = 0.40

GUIDES = (
    Path(__file__).resolve().parent.parent
    / "custom_components/eufy_vacuum/adapters/dreame/dreame_upkeep_guides.py"
)


def tokens(text: str) -> list[str]:
    """Lowercase word tokens, punctuation stripped."""
    # NFKC first: the L50 manual sets "filter" with an fi LIGATURE (U+FB01), which a
    # naive [^a-z0-9] strip turns into "lter" — every filter sentence would then read
    # as a defect. Normalising is the difference between a probe and a false alarm.
    text = unicodedata.normalize("NFKC", text).replace("’", "'").replace("—", " ")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def bigrams(text: str) -> set[tuple[str, str]]:
    """Adjacent word pairs — the unit that survives column-interleaved extraction."""
    t = tokens(text)
    return {(t[i], t[i + 1]) for i in range(len(t) - 1)}


# --- OCR fallback for manuals whose text layer is a non-extractable (CID) font ---------
# Part of the corpus (notably the api-fetch/ files) embeds subsetted fonts with no usable
# ToUnicode map, so ``extract_text`` returns mojibake like ``溢潻ǝǝ`` even though the page
# RENDERS perfectly. We detect that and OCR the rendered page instead. Rendering needs
# pymupdf; OCR needs the tesseract binary. Both are optional: if a page is garbled and OCR
# is unavailable we do NOT emit false defects — we report the family as unverifiable and
# fail with a clear, actionable message (install tesseract), because an unverifiable
# provenance claim must not read as green.

_GARBLE_RATIO = 0.60  #: below this share of ASCII letters, the text layer is unusable


def _ascii_letter_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 1.0  # blank/figure-only page — empty, not garbled; nothing to OCR-recover
    return sum(1 for c in letters if ord(c) < 128) / len(letters)


def _find_tesseract() -> str | None:
    import shutil

    exe = shutil.which("tesseract")
    if exe:
        return exe
    for cand in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(cand).exists():
            return cand
    return None


def _ocr_context() -> dict:
    """Resolve OCR tooling once. ``tess`` is None when OCR is unavailable."""
    tess = None
    try:
        import pymupdf  # noqa: F401

        tess = _find_tesseract()
    except ImportError:
        pass
    return {"tess": tess, "docs": {}, "needed": set(), "ocred": set()}


def resolve_page_text(reader, path: Path, page_1based: int, ocr: dict) -> str:
    """Extracted text, or OCR of the rendered page when the text layer is garbled."""
    raw = reader.pages[page_1based - 1].extract_text() or ""
    if _ascii_letter_ratio(raw) >= _GARBLE_RATIO:
        return raw
    if not ocr["tess"]:
        ocr["needed"].add(path.name)
        return raw
    import subprocess
    import tempfile

    import pymupdf

    doc = ocr["docs"].get(path)
    if doc is None:
        doc = pymupdf.open(str(path))
        ocr["docs"][path] = doc
    pix = doc[page_1based - 1].get_pixmap(dpi=300)
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "page.png"
        pix.save(str(png))
        out = Path(td) / "page"
        subprocess.run(
            [ocr["tess"], str(png), str(out), "-l", "eng", "--psm", "4"],
            check=True,
            capture_output=True,
        )
        ocr["ocred"].add(path.name)
        return (out.with_suffix(".txt")).read_text(encoding="utf-8")


def main() -> int:
    """Score every guide string; exit 1 if any unexpected one is below --min."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--manuals", type=Path, default=DEFAULT_MANUALS)
    ap.add_argument("--min", type=float, default=0.85)
    args = ap.parse_args()

    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf is not installed", file=sys.stderr)
        return 2

    spec = importlib.util.spec_from_file_location("dreame_guides", GUIDES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    library = module.DREAME_UPKEEP_GUIDE_LIBRARY

    # SOURCES lists the AUTHORED families — each transcribed from ONE manual. The composed
    # TIER profiles (standard / auto_empty / wash_station / _track / _roller / _baseboard)
    # carry no single manual: their prose is the most-complete wording drawn FROM the
    # authored families and is therefore already scored below. They are skipped here, not
    # errored. A source naming a family the library no longer defines is still a defect.
    stale = set(SOURCES) - set(library)
    if stale:
        print(f"SOURCES names {sorted(stale)} which the library no longer defines.")
        return 2
    authored = [f for f in library if f in SOURCES]
    skipped = sorted(set(library) - set(SOURCES))
    if skipped:
        print(f"(skipping {len(skipped)} composed tier profiles, scored via their "
              f"authored source families: {skipped})")

    ocr = _ocr_context()
    haystacks = {}
    for family, (pdf, pages) in SOURCES.items():
        path = args.manuals / pdf
        if not path.exists():
            print(f"missing manual: {path}", file=sys.stderr)
            return 2
        reader = PdfReader(str(path))
        haystacks[family] = bigrams(
            " ".join(
                " ".join(resolve_page_text(reader, path, p, ocr).split())
                for p in pages
            )
        )
    if ocr["ocred"]:
        print(f"(OCR fallback used for non-extractable manuals: {sorted(ocr['ocred'])})")
    if ocr["needed"]:
        print(
            "\nUNVERIFIABLE: these manuals have a non-extractable text layer and no OCR "
            f"tooling is available to read them: {sorted(ocr['needed'])}.\n"
            "Install the tesseract binary (and ensure pymupdf is present) so their "
            "families can be scored; refusing to report them as verified.",
            file=sys.stderr,
        )
        return 2

    defects = 0
    total = 0
    for family in authored:
        components = library[family]
        for component, guide in components.items():
            for kind in ("steps", "notes"):
                for text in guide.get(kind, []):
                    total += 1
                    needle = bigrams(text)
                    score = len(needle & haystacks[family]) / max(len(needle), 1)
                    if score >= args.min:
                        continue
                    known = (
                        (component, kind) in KNOWN_RECASTS and score >= RECAST_FLOOR
                    )
                    label = "recast " if known else "DEFECT "
                    if not known:
                        defects += 1
                    print(f"  {label}{score:5.0%}  {family}.{component}.{kind}: {text[:70]}")

    # Cadence coverage. Steps/notes are scored against the manual above; FREQUENCIES are
    # not manual text (they are one normalised, owned map — module.COMPONENT_FREQUENCIES),
    # so instead of scoring them we assert every component in every family resolves a
    # cadence there. Before the flat-model refactor frequencies were inherited implicitly
    # and nothing checked them at all; this closes that hole.
    cadence = getattr(module, "COMPONENT_FREQUENCIES", {})
    uncovered = sorted(
        f"{family}.{component}"
        for family in library
        for component in library[family]
        if component not in cadence
    )
    if uncovered:
        print(f"\nCADENCE GAP: {len(uncovered)} components have no COMPONENT_FREQUENCIES "
              f"entry: {uncovered[:10]}", file=sys.stderr)
        return 2
    print(f"cadence: all {sum(len(library[f]) for f in library)} components resolve an "
          f"interval from COMPONENT_FREQUENCIES ({len(cadence)} component types)")

    print(f"\n{total} strings scored against {len(SOURCES)} manuals; {defects} defects")
    return 1 if defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
