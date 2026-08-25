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

NOT A CI GATE, and cannot become one: the manuals are vendor copyright and stay out of
the repo. Run it by hand after authoring or editing a family.

    python scripts/verify_dreame_guide_provenance.py [--manuals DIR] [--min 0.85]
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

DEFAULT_MANUALS = Path.home() / "Documents/durable/dreame-port-fixture/manuals"

#: family -> (manual filename, EN care-section pages, 1-based inclusive)
SOURCES = {
    "x50": ("R2489A-X50_Series-EN_DE_FR.pdf", range(22, 31)),
    "x60_ultra": ("R5089B-X60_Ultra-EN_KM.pdf", range(13, 16)),
    "x60_pro_ultra_complete": ("R6001-X60_Series-28LANG.pdf", range(14, 17)),
    "l10s_gen2": (
        "R2469X-Dreame_L10s_Ultra_Gen_2-_X-_ERP_EN_DE_FR_IT_ES.pdf",
        range(19, 26),
    ),
}

#: The recasts documented in the guide file's docstring. Expected to score low.
KNOWN_RECASTS = {("sensor", "steps"), ("filter", "steps"), ("filter", "notes"),
                 ("caster_wheel", "notes")}

GUIDES = (
    Path(__file__).resolve().parent.parent
    / "custom_components/eufy_vacuum/adapters/dreame/dreame_upkeep_guides.py"
)


def tokens(text: str) -> list[str]:
    """Lowercase word tokens, punctuation stripped."""
    text = text.replace("’", "'").replace("—", " ")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def bigrams(text: str) -> set[tuple[str, str]]:
    """Adjacent word pairs — the unit that survives column-interleaved extraction."""
    t = tokens(text)
    return {(t[i], t[i + 1]) for i in range(len(t) - 1)}


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

    missing = set(library) - set(SOURCES)
    if missing:
        print(f"NO SOURCE RECORDED for {sorted(missing)} — add it to SOURCES above.")
        return 2

    haystacks = {}
    for family, (pdf, pages) in SOURCES.items():
        path = args.manuals / pdf
        if not path.exists():
            print(f"missing manual: {path}", file=sys.stderr)
            return 2
        reader = PdfReader(str(path))
        haystacks[family] = bigrams(
            " ".join(
                " ".join((reader.pages[p - 1].extract_text() or "").split())
                for p in pages
            )
        )

    defects = 0
    total = 0
    for family, components in library.items():
        for component, guide in components.items():
            for kind in ("steps", "notes"):
                for text in guide.get(kind, []):
                    total += 1
                    needle = bigrams(text)
                    score = len(needle & haystacks[family]) / max(len(needle), 1)
                    if score >= args.min:
                        continue
                    known = (component, kind) in KNOWN_RECASTS
                    label = "recast " if known else "DEFECT "
                    if not known:
                        defects += 1
                    print(f"  {label}{score:5.0%}  {family}.{component}.{kind}: {text[:70]}")

    print(f"\n{total} strings scored against {len(SOURCES)} manuals; {defects} defects")
    return 1 if defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
