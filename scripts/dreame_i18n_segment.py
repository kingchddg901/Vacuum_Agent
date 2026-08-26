"""Stage 0 for i18n: split a Dreame manual into LANGUAGE BLOCKS and emit feedable text.

This is not a documentation corpus and it does not need to know what a main brush is.
Its whole job is to be very good at saying: here are the Korean pages, here are the
German pages, here is the English maintenance section — and **nothing got lost,
reordered, or blended.**

    python scripts/dreame_i18n_segment.py "R2513-*.pdf" --out corpus.jsonl
    python scripts/dreame_i18n_segment.py "*.pdf" --verify-only

One record per language block:

    manual_id  model  language  page_start  page_end
    section_heading  raw_text  normalized_text  source_pdf_sha

``raw_text`` is in VISUAL reading order (via ``pdf_layout_dump``), not content-stream
order — the latter interleaves adjacent columns and has already produced one false
finding on these manuals. ``normalized_text`` is what the i18n machinery consumes;
``raw_text`` plus the page range is what an agent verifies a translation against.

⚠ BLENDING IS THE FAILURE THAT MATTERS, AND IT IS SILENT. A single Dreame PDF carries
up to 35 languages laid end to end. Miss a boundary by one page and a German warning
reaches the translator as Dutch — downstream that does not look like an error, it looks
like a translation. So: every page is assigned exactly one language, the assignment is
checked to cover the whole document, and anything ambiguous is REPORTED rather than
resolved quietly. ``--verify-only`` runs those checks and writes nothing.

⚠ THE FILENAME IS NOT A MANIFEST. Dreame's naming under-reports — files labelled only
"EU" and "UK" turned out to carry Turkish, Indonesian and ZH-HK, which cost three wrong
"that language is unavailable" conclusions in one session. Language is decided by what
is INSIDE the file; the name is printed only so the two can be compared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_DEST = Path.home() / "Documents/durable/dreame-port-fixture/manuals"

#: Unicode blocks that identify a language no footer code can. Single-language regional
#: editions carry NO ascii footer at all — Russian, Japanese and Traditional Chinese
#: editions were nearly reported absent for exactly this reason.
SCRIPTS = {
    "Cyrillic": (0x0400, 0x04FF), "Kana": (0x3040, 0x30FF),
    "Hangul": (0xAC00, 0xD7A3), "Hebrew": (0x0590, 0x05FF),
    "Arabic": (0x0600, 0x06FF), "Greek": (0x0370, 0x03FF),
    "Thai": (0x0E00, 0x0E7F), "Han": (0x4E00, 0x9FFF),
}

#: ⚠ A FOOTER CODE MUST BE A REAL LANGUAGE, OR THE CORPUS INVENTS ONE.
#:
#: The first cut accepted any two capitals after a digit, because that is what a page
#: footer looks like ("20EN"). Run across 44 manuals it produced blocks labelled DX, HQ,
#: KX, LO, LQ, NU, OT, RS, RW, UL, UX, XL, ZJ — table data and part numbers, not
#: languages. Feeding a block labelled "ZJ" to i18n is the blend failure wearing a
#: different hat: the text is real, the label is fiction.
#:
#: Codes Dreame actually ships, taken from the corpus filenames themselves rather than
#: typed from memory, plus the regional pairs.
KNOWN_LANGS = {
    "EN", "DE", "FR", "IT", "ES", "PL", "NL", "NO", "SV", "EL", "PT", "HE", "AR", "TR",
    "VI", "TH", "ID", "MS", "FI", "DA", "KK", "UZ", "UA", "CZ", "SK", "SL", "HU", "SR",
    "LT", "LV", "RO", "RU", "KO", "JA", "ET", "KM", "BG", "HR", "IS", "GA", "MT", "CS",
    "UK", "ZH", "ZH-HK", "ZH-TW", "ZH-CN", "EN-US", "EN-GB", "PT-BR", "ES-MX",
}

CARE_HEADINGS = {
    "EN": r"Routine Maintenance",
    "DE": r"Regelm(a|ä)(ss|ß)ige Wartung",
    "FR": r"Entretien de routine",
    "IT": r"Manutenzione ordinaria",
    "ES": r"Mantenimiento (rutinario|de rutina)",
    "NL": r"Routineonderhoud",
    "PT": r"Manuten(c|ç)(a|ã)o de rotina",
    "PL": r"Rutynowa konserwacja",
}

LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "—": " - ", "–": "-", " ": " ",
}


def normalize(text: str) -> str:
    """NFKC + ligature/punctuation folding + whitespace collapse.

    The L50 manual sets "filter" with an fi LIGATURE (U+FB01); a naive strip turns it
    into "lter". Normalising is the difference between a corpus and a landmine.
    """
    text = unicodedata.normalize("NFKC", text)
    for bad, good in LIGATURES.items():
        text = text.replace(bad, good)
    return " ".join(text.split())


def page_language(text: str) -> tuple[str | None, str, dict[str, int]]:
    """(language, how_it_was_decided) for ONE page.

    Two independent signals, kept separate so disagreement stays visible:
      * footer — "20EN" / "54 DE" page furniture; reliable in multi-language editions
      * script — the only signal a single-language regional edition gives at all
    """
    # ⚠ CAPTURE THE REGIONAL SUFFIX. `[A-Z]{2}` collapsed ZH-HK and ZH-TW into a single
    # "ZH", which is not a cosmetic loss: Hong Kong and Taiwan Traditional differ in
    # wording, this project ships them as separate packs, and a merged block would feed
    # one variant's text as the other's. It also showed up as a FALSE "non-contiguous
    # language" warning, because one manual carries both.
    footers = Counter(
        m.group(1)
        for m in re.finditer(r"\b\d{1,3}\s?([A-Z]{2}(?:-[A-Z]{2})?)\b", text)
    )
    footers.pop("QR", None)
    # ⚠ REJECT, BUT REPORT WHAT WAS REJECTED. An allowlist that silently drops is the
    # same defect as one that silently accepts — if a language Dreame really ships is
    # missing from KNOWN_LANGS, the only way anyone finds out is by seeing it here.
    rejected = {c: n for c, n in footers.items() if c not in KNOWN_LANGS}
    footers = Counter({c: n for c, n in footers.items() if c in KNOWN_LANGS})
    if footers:
        top, n = footers.most_common(1)[0]
        rival = [c for c, m in footers.items() if c != top and m >= n * 0.6]
        return top, ("footer" if not rival else "footer-AMBIGUOUS"), rejected
    scripts: Counter = Counter()
    for ch in text:
        code = ord(ch)
        for name, (lo, hi) in SCRIPTS.items():
            if lo <= code <= hi:
                scripts[name] += 1
                break
    if scripts:
        return "script:" + scripts.most_common(1)[0][0], "script", rejected
    return None, "none", rejected


def runs_of(assigned: list[str | None]) -> list[tuple[str | None, int, int]]:
    """Contiguous (language, first_page, last_page) runs, 1-based inclusive."""
    out: list[list] = []
    for i, lang in enumerate(assigned, 1):
        if out and out[-1][0] == lang:
            out[-1][2] = i
        else:
            out.append([lang, i, i])
    return [(a, b, c) for a, b, c in out]


def segment_one(path: Path, model: str | None, want_text: bool):
    """Language blocks for one PDF, plus every problem found while deciding them."""
    from pypdf import PdfReader

    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    reader = PdfReader(str(path))
    texts = [" ".join((pg.extract_text() or "").split()) for pg in reader.pages]
    decided = [page_language(t) for t in texts]
    assigned: list[str | None] = [d[0] for d in decided]

    # Carry the previous page's language across pages that give NO signal (figure-only
    # pages are common mid-section). NEVER carry across a page that gave a DIFFERENT
    # signal — that is precisely the blend this script exists to prevent.
    carried = 0
    last: str | None = None
    for i, lang in enumerate(assigned):
        if lang is None and last is not None:
            assigned[i] = last
            carried += 1
        elif lang is not None:
            last = lang

    # FRONT MATTER ENDS WHERE PAGE NUMBERING BEGINS, and that is a fact in the file
    # rather than a guess. Each language block restarts at its own page 1 ("1 EN Usage
    # Restrictions"), so the first "1 XX" footer in the document is the first page of
    # real content; everything before it is cover and contents.
    #
    # This replaced a weaker rule that only labelled pages with NO signal at all. The
    # contents page lists every language in its own words ("Manual Pengguna",
    # "Käyttöohjeet", ...) and carries an MS footer, so it was being read as a one-page
    # Malay block sitting inside English — a real blend, caught only because
    # single-page islands are reported rather than absorbed quietly.
    content_start = next(
        (i for i, t in enumerate(texts)
         if re.search(r"\b1\s?[A-Z]{2}(?:-[A-Z]{2})?\b", t)),
        None,
    )
    if content_start:
        for i in range(content_start):
            assigned[i] = "front-matter"

    # ⚠ ABSORB ONE-PAGE ISLANDS, BUT NEVER SILENTLY. A single page inside an English
    # block matched "MS" (a stray token, not a Malay page) and split pp 4-22 into three
    # blocks. Absorb only when BOTH neighbours agree, and count it — an island that
    # keeps appearing is a boundary being misread, not noise.
    absorbed: list[tuple[int, str]] = []
    merged_script: list[tuple] = []
    for lang, first, last_pg in runs_of(assigned):
        if lang is None or last_pg - first > 0:
            continue
        before = assigned[first - 2] if first >= 2 else None
        after = assigned[last_pg] if last_pg < len(assigned) else None
        if before is not None and before == after and before != lang:
            absorbed.append((first, lang))
            assigned[first - 1] = before

    # A script-derived label sitting next to a footer-derived block of a COMPATIBLE
    # language is the tail of that block, not a new one: the last page of the Taiwanese
    # section carries Han characters and no footer, and was becoming a one-page
    # "script:Han" block of its own. Merge only where the script genuinely belongs to
    # the neighbour's language, never on adjacency alone.
    SCRIPT_OF = {
        "ZH-HK": "Han", "ZH-TW": "Han", "ZH": "Han", "JA": "Kana", "KO": "Hangul",
        "RU": "Cyrillic", "UA": "Cyrillic", "KK": "Cyrillic", "UZ": "Cyrillic",
        "SR": "Cyrillic", "EL": "Greek", "HE": "Hebrew", "AR": "Arabic", "TH": "Thai",
    }
    for lang, first, last_pg in runs_of(assigned):
        if not (lang or "").startswith("script:"):
            continue
        script = lang.split(":", 1)[1]
        prev = assigned[first - 2] if first >= 2 else None
        nxt = assigned[last_pg] if last_pg < len(assigned) else None
        for neighbour in (prev, nxt):
            if neighbour and SCRIPT_OF.get(neighbour) == script:
                for i in range(first - 1, last_pg):
                    assigned[i] = neighbour
                merged_script.append((first, lang, neighbour))
                break

    blocks = [r for r in runs_of(assigned) if r[0] is not None]
    covered = sum(b - a + 1 for _, a, b in blocks)
    problems: list[str] = []
    if covered != len(texts):
        problems.append(f"{len(texts) - covered} page(s) UNASSIGNED to any language")
    repeats = sorted(l for l, n in Counter(l for l, _, _ in blocks).items() if n > 1)
    if repeats:
        problems.append(f"non-contiguous language block(s): {repeats}")
    ambiguous = [i for i, d in enumerate(decided, 1) if d[1].endswith("AMBIGUOUS")]
    rejected: Counter = Counter()
    for d in decided:
        rejected.update(d[2])
    if merged_script:
        print(f"   merged {len(merged_script)} script-only page-run(s) into their "
              f"language neighbour: {merged_script[:4]}")
    if absorbed:
        problems.append(
            "absorbed one-page island(s) " + str(absorbed[:6])
            + " — verify these are stray tokens and not real boundaries"
        )

    records = []
    for lang, first, last_pg in blocks:
        raw = ""
        heading = None
        if want_text:
            from pdf_layout_dump import dump as layout_dump

            raw = "\n".join(layout_dump(str(path), p) for p in range(first, last_pg + 1))
            norm = normalize(raw)
            pattern = CARE_HEADINGS.get(lang)
            if pattern and re.search(pattern, norm, re.I):
                heading = "care"
        records.append({
            "manual_id": path.stem[:70],
            "model": model or path.stem.split("-")[0],
            "language": lang,
            "page_start": first,
            "page_end": last_pg,
            "section_heading": heading,
            "raw_text": raw,
            "normalized_text": normalize(raw) if want_text else "",
            "source_pdf_sha": sha,
        })
    return records, problems, ambiguous, carried, len(texts), sha, rejected


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdfs", nargs="+", help="glob(s) inside --dest")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--out", help="write JSONL records here")
    ap.add_argument("--model", help="value for the `model` field")
    ap.add_argument("--verify-only", action="store_true",
                    help="run the no-loss / no-blend checks and write nothing")
    args = ap.parse_args()

    paths = sorted({p for pat in args.pdfs for p in args.dest.glob(pat)})
    if not paths:
        print(f"no PDFs matched {args.pdfs} in {args.dest}", file=sys.stderr)
        return 2

    all_records, all_problems = [], []
    for path in paths:
        try:
            recs, probs, ambiguous, carried, pages, sha, rejected = segment_one(
                path, args.model, want_text=not args.verify_only
            )
        except Exception as err:  # pragma: no cover - a bad PDF must not kill the run
            print(f"\n### {path.name}\n   FAILED: {err}")
            all_problems.append(f"{path.name}: unreadable ({err})")
            continue
        langs = [r["language"] for r in recs]
        print(f"\n### {path.name}  ({pages} pages, sha {sha})")
        print(f"   {len(langs)} language block(s); "
              f"{sum(r['page_end'] - r['page_start'] + 1 for r in recs)}/{pages} pages "
              f"assigned" + (f"; {carried} carried from the previous page" if carried else ""))
        for r in recs:
            care = "  [care section]" if r["section_heading"] else ""
            print(f"     {r['language']:18} pp {r['page_start']:>3}-{r['page_end']:<3}{care}")
        if rejected:
            top = ", ".join(f"{c}x{n}" for c, n in rejected.most_common(6))
            print(f"   rejected {sum(rejected.values())} non-language footer token(s): {top}")
            print("     (if any of those IS a language Dreame ships, add it to KNOWN_LANGS)")
        if ambiguous:
            print(f"   ⚠ {len(ambiguous)} boundary page(s) carry rival footer codes: "
                  f"{ambiguous[:10]}")
        for p_ in probs:
            print(f"   ⚠ {p_}")
        all_problems += [f"{path.name}: {p_}" for p_ in probs]
        all_records += recs

    if args.out and not args.verify_only:
        with open(args.out, "w", encoding="utf-8") as fh:
            for rec in all_records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"\n{len(all_records)} records -> {args.out}")

    print()
    if all_problems:
        print(f"⚠ {len(all_problems)} PROBLEM(S) — do not feed these to i18n yet:")
        for p_ in all_problems:
            print(f"   {p_}")
        return 1
    print(f"OK — {len(paths)} manual(s), every page assigned, every block contiguous.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
