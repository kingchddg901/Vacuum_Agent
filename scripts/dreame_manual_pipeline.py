"""Dreame manual pipeline — index → PDF links → download → locate the care section.

Authoring one guide family used to mean: find the manual by hand, download it, hunt for
the care pages, dump them. Seven families in, the remaining catalog is ~43 more manual
pages, so the hunting has to stop being manual.

    python scripts/dreame_manual_pipeline.py index            # refresh model -> slug
    python scripts/dreame_manual_pipeline.py links l40-user-manual
    python scripts/dreame_manual_pipeline.py fetch matrix10-ultra-user-manual
    python scripts/dreame_manual_pipeline.py locate R2513-*.pdf
    python scripts/dreame_manual_pipeline.py plan              # what is worth grabbing

⚠ THE MANUALS ARE VENDOR COPYRIGHT AND MUST NOT ENTER THE REPO. This script lives in
the repo because it is code; everything it downloads goes to ``--dest``, which defaults
to the git-ignored fixture directory outside the tree. Do not repoint it inside.

⚠ THE FILENAME IS NOT A MANIFEST — IT UNDER-REPORTS. Dreame's own naming cost three
wrong "that language is unavailable" conclusions in one session: two files carrying
Turkish, Indonesian and ZH-HK were labelled only "EU" and "UK" by the linking page. So
``locate`` reports what is INSIDE a file — footer language codes and scripts actually
present — and treats the filename as a hint to check against, never as the answer.
See `.claude/notes/synthesis/dreame-port/MANUAL-INVENTORY.md`.

⚠ ``locate`` FINDS PAGES, IT DOES NOT READ THEM. Extraction emits content-stream order,
which interleaves adjacent columns; a collapsed extract of one manual's "Main Brush"
block arrives with used-water-tank sentences inside it, and that produced a false
finding once. Automate the FINDING and the LAYOUT; read the prose. Hand the page range
to ``scripts/pdf_layout_dump.py``, which reconstructs visual reading order.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

INDEX_URL = "https://global.dreametech.com/pages/user-manuals-and-faqs"
PAGE_URL = "https://global.dreametech.com/pages/{slug}"
UA = {"User-Agent": "Mozilla/5.0 (compatible; vacuum-agent-docs/1.0)"}

DEFAULT_DEST = Path.home() / "Documents/durable/dreame-port-fixture/manuals"
CACHE = DEFAULT_DEST / "_pipeline_index.json"

#: The care section's heading, in the languages worth locating directly. EN is the one
#: families are authored from; the rest are here so an i18n pass can find the SAME
#: section without re-deriving page offsets.
CARE_HEADINGS = {
    "EN": r"Routine Maintenance",
    "DE": r"Regelm(ä|a)(ß|ss)ige Wartung",
    "FR": r"Entretien de routine",
    "IT": r"Manutenzione ordinaria",
    "ES": r"Mantenimiento rutinario|Mantenimiento de rutina",
    "NL": r"Routineonderhoud",
    "PL": r"Rutynowa konserwacja|Konserwacja",
    "PT": r"Manuten(ç|c)(ã|a)o de rotina",
}

#: Unicode blocks that identify a language a footer code cannot. Single-language
#: regional editions carry NO ascii footer code at all — Russian, Japanese and
#: Traditional Chinese editions were nearly reported absent for exactly this reason.
SCRIPTS = {
    "Cyrillic": (0x0400, 0x04FF),
    "Kana": (0x3040, 0x30FF),
    "Han": (0x4E00, 0x9FFF),
    "Hangul": (0xAC00, 0xD7A3),
    "Hebrew": (0x0590, 0x05FF),
    "Arabic": (0x0600, 0x06FF),
    "Greek": (0x0370, 0x03FF),
    "Thai": (0x0E00, 0x0E7F),
}


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def cmd_index(args) -> int:
    """Scrape model -> manual slug from Dreame's own index page."""
    html = _get(INDEX_URL).decode("utf-8", "replace")
    pairs = {}
    for m in re.finditer(r'href="(?:https://global\.dreametech\.com)?/pages/'
                         r'([a-z0-9\-]*user-?man?ual[a-z0-9\-]*|[a-z0-9\-]+)"'
                         r'[^>]*>([^<]{2,60})<', html):
        slug, label = m.group(1), " ".join(m.group(2).split())
        if "manual" not in slug and "manual" not in label.lower():
            continue
        pairs.setdefault(slug, label)
    args.dest.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(pairs, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(pairs)} manual pages -> {CACHE}")
    for slug, label in sorted(pairs.items())[: args.limit]:
        print(f"  {label[:40]:42} {slug}")
    return 0


def pdf_links(slug: str) -> list[str]:
    """Every PDF URL on one manual page, deduped, order preserved."""
    html = _get(PAGE_URL.format(slug=slug)).decode("utf-8", "replace")
    seen, out = set(), []
    for m in re.finditer(r'https://cdn\.shopify\.com/[^"\'\\\s]+?\.pdf[^"\'\\\s]*', html):
        url = m.group(0)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def langs_from_name(url: str) -> list[str]:
    """The languages the FILENAME claims. A hint to verify, never the answer."""
    stem = url.rsplit("/", 1)[-1].split("?")[0]
    tokens = re.split(r"[-_.]", stem)
    return [t for t in tokens
            if re.fullmatch(r"[A-Z]{2}|ZH-HK|ZH-TW|[A-Z]{2}-[A-Z]{2}", t)]


def cmd_links(args) -> int:
    for slug in args.slugs:
        print(f"\n### {slug}")
        try:
            urls = pdf_links(slug)
        except Exception as err:
            print(f"   FAILED: {err}")
            continue
        if not urls:
            print("   no PDF links found — the page may render them via JS")
        for url in urls:
            claimed = langs_from_name(url)
            size = f"{len(claimed)} langs claimed" if claimed else "no langs in name"
            print(f"   [{size}] {url.rsplit('/', 1)[-1].split('?')[0][:78]}")
            if args.verbose:
                print(f"        {url}")
    return 0


def cmd_fetch(args) -> int:
    """Download every PDF for the given slugs into --dest (skipping ones already there)."""
    args.dest.mkdir(parents=True, exist_ok=True)
    grabbed = skipped = failed = 0
    empty: list[str] = []
    for slug in args.slugs:
        try:
            urls = pdf_links(slug)
        except Exception as err:
            print(f"  FAIL  {slug}: {err}")
            failed += 1
            continue
        # ⚠ DO NOT RANK PDFs BY THEIR FILENAMES — TAKE THEM ALL.
        #
        # The first cut had a --biggest-only that preferred names claiming the most
        # languages. It was WRONG IN THE EXACT DIRECTION THIS PROJECT ALREADY
        # DOCUMENTED: a filename under-reports, so the files claiming NOTHING
        # (`R9526-F20.pdf`, `R9434L-X50_Master_-_A01_ERP.pdf`) are the ones most likely
        # to be the big multi-language editions, and the heuristic ranked them LAST. It
        # downloaded the Estonian and Khmer editions of four models and reported
        # success. Worse than nothing: it looks like the manual is in hand.
        #
        # PDFs are 2-20 MB and disk is cheap; opening the file is the only thing that
        # tells the truth. Take everything, then let `locate` say what is inside.
        wanted = urls if args.all or not args.max_per_page else urls[: args.max_per_page]
        got_here = 0
        for url in wanted:
            name = url.rsplit("/", 1)[-1].split("?")[0]
            dest = args.dest / name
            if dest.exists():
                print(f"  have  {name[:76]}")
                skipped += 1
                got_here += 1
                continue
            try:
                data = _get(url, timeout=180)
                dest.write_bytes(data)
                print(f"  GOT   {name[:64]}  {len(data)/1e6:.1f} MB")
                grabbed += 1
                got_here += 1
            except Exception as err:
                print(f"  FAIL  {name[:60]}: {err}")
                failed += 1
    print(f"\n{grabbed} downloaded, {skipped} already present, {failed} failed")
    return 1 if failed else 0


def cmd_locate(args) -> int:
    """What is INSIDE a manual: languages actually present, and the care pages."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf is not installed", file=sys.stderr)
        return 2

    for path in sorted(p for pat in args.pdfs for p in args.dest.glob(pat)):
        print(f"\n### {path.name}")
        try:
            reader = PdfReader(str(path))
        except Exception as err:
            print(f"   unreadable: {err}")
            continue
        pages = []
        footers: Counter = Counter()
        scripts: Counter = Counter()
        for i, page in enumerate(reader.pages, 1):
            text = " ".join((page.extract_text() or "").split())
            pages.append(text)
            for m in re.finditer(r"\b\d{1,3}\s?([A-Z]{2})\b", text):
                footers[m.group(1)] += 1
            for ch in text[:3000]:
                code = ord(ch)
                for name, (lo, hi) in SCRIPTS.items():
                    if lo <= code <= hi:
                        scripts[name] += 1
                        break
        present = sorted(c for c, n in footers.items() if n >= 4 and c != "QR")
        claimed = sorted(set(langs_from_name(path.name)))
        print(f"   pages {len(reader.pages)}")
        print(f"   filename claims : {claimed or '(none)'}")
        print(f"   footers present : {present or '(none — likely single-language)'}")
        if scripts:
            print(f"   scripts         : {dict(scripts.most_common(4))}")
        missed = [c for c in present if c not in claimed]
        if missed:
            print(f"   ⚠ IN THE FILE BUT NOT IN ITS NAME: {missed}")

        for lang, pattern in CARE_HEADINGS.items():
            hits = [i for i, t in enumerate(pages, 1)
                    if re.search(pattern, unicodedata.normalize("NFKC", t), re.I)]
            if hits:
                runs, start, prev = [], hits[0], hits[0]
                for h in hits[1:]:
                    if h != prev + 1:
                        runs.append((start, prev))
                        start = h
                    prev = h
                runs.append((start, prev))
                shown = ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in runs[:4])
                print(f"   care [{lang}]      : pp {shown}")
        print(f"   -> read with: python scripts/pdf_layout_dump.py "
              f"\"{path}\" <first>-<last>")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                    help="where PDFs live (git-ignored fixture dir; NOT the repo)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("index", help="refresh the model -> slug list")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("links", help="show PDF URLs for manual page slugs")
    p.add_argument("slugs", nargs="+")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_links)

    p = sub.add_parser("fetch", help="download PDFs for manual page slugs")
    p.add_argument("slugs", nargs="+")
    p.add_argument("--all", action="store_true", default=True,
                   help="take every PDF on the page (the default, and the safe one)")
    p.add_argument("--max-per-page", type=int, default=0,
                   help="cap files per page; 0 = no cap. A cap can MISS the "
                        "multi-language edition, because filenames under-report.")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("locate", help="languages present + care-section pages")
    p.add_argument("pdfs", nargs="+", help="glob(s) within --dest")
    p.set_defaults(func=cmd_locate)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
