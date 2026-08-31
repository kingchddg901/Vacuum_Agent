"""Extract the FULL text of every manual we hold, once, into a durable cache.

⚠ WHY THIS EXISTS WHEN A TEXT CACHE ALREADY DID. The previous cache sampled pages
[0..3] + the last six, because it was built to answer ONE question: which marketing
names does this manual print? Names live on the cover and in the back-matter
applicability table, so the sample was correct FOR THAT QUESTION and wrong for every
other one. Care intervals, part numbers and maintenance procedure text sit in the
MIDDLE of a manual — exactly the pages that sample skips. Authoring an upkeep guide
from that cache means re-opening the PDF, which is the cost this was supposed to remove.

⚠ TEXT-LAYER-EMPTY IS A PER-PAGE FACT, NOT A PER-FILE ONE. The old cache called a
manual image-only when its ten sampled pages came back empty. A manual whose cover is
vector art and whose body is real text reads as "unreadable" under that test. This
records the per-page count so the file-level verdict is derived, not assumed.

⚠ THESE ARE NOT SCANS. Dreame converts text to VECTOR OUTLINES: no text layer AND no
embedded image, so both `extract_text()` and `page.images` report empty for a page that
is perfectly legible. Rendering (pypdfium2) is the only thing that reads them, and
there is no OCR in this environment — so genuinely empty files are RECORDED here as a
work queue for rendering, never silently dropped.

Output layout (all under --out):
    text/<sha12>.txt        full text, PAGE_SEP separated per page
    index.json              one record per PDF: name, sha256, pages, per-page lengths

⚠ THE PAGE SEPARATOR MUST NOT OCCUR IN PAGE TEXT, AND FORM-FEED DOES. The first cut
used "\f", which is a perfectly ordinary character inside an extracted PDF text stream.
The cached fast path then reconstructs page counts by splitting on it, and the same 332
manuals came back as 37,484 pages having truly parsed to 36,806 — a silent 1.8%
inflation, in a field later code trusts. NUL cannot appear in extracted text, so
PAGE_SEP is safe; text files written before this change reconstruct approximately, and
their true counts are whatever the ORIGINAL parse recorded.

Keyed on SHA, not filename: 15 byte-identical duplicates were already caught on arrival
in this corpus and the filenames differ across channels.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import sys
from pathlib import Path

#: Page delimiter. NUL cannot occur in extracted PDF text; form-feed can.
PAGE_SEP = "\x00\f\x00"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_one(args: tuple[str, str]) -> dict:
    """Run in a worker process. Never raises — a failure is a RECORD, not a crash."""
    src, outdir = args
    path = Path(src)
    rec: dict = {"file": path.name, "size": path.stat().st_size}
    try:
        rec["sha256"] = _sha256(path)
    except Exception as err:  # unreadable on disk
        rec["error"] = f"sha:{type(err).__name__}"
        return rec

    txt_path = Path(outdir) / "text" / f"{rec['sha256'][:12]}.txt"
    # ⚠ ALWAYS BIND IT. The first cut set this key only in the exists() branch, so the
    # normal path raised KeyError further down — straight into the `except Exception`
    # that records a failure. Every file "extracted" to an error record and no text at
    # all, while eight workers stayed busy looking like progress. A broad except turns
    # a typo into a uniform negative result, which is the hardest kind to see.
    rec["cached"] = txt_path.exists()
    if rec["cached"]:
        # Keying on SHA rather than filename is what makes this survive the corpus
        # rename — the same document under a new name is still the same document.
        # Reconstruct the per-page counts from the cached text instead of re-parsing:
        # at ~520 ms/page, re-reading what we already hold is the single largest
        # avoidable cost in this pipeline.
        try:
            raw = txt_path.read_text(encoding="utf-8", errors="replace")
            # Legacy caches were written with a bare form-feed; fall back so they still
            # read, accepting that their reconstructed page counts run ~1.8% high.
            sep = PAGE_SEP if PAGE_SEP in raw else "\f"
            chunks = raw.split(sep)
            rec["page_chars"] = [len(c) for c in chunks]
            rec["pages"] = len(chunks)
            rec["chars"] = sum(rec["page_chars"])
            rec["text_pages"] = sum(1 for n in rec["page_chars"] if n >= 100)
            return rec
        except Exception:
            pass  # fall through and re-extract rather than trust a bad read

    try:
        from pypdf import PdfReader

        reader = PdfReader(src)
        pages = reader.pages
        rec["pages"] = len(pages)
        per_page: list[int] = []
        chunks: list[str] = []
        for page in pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            per_page.append(len(text))
            chunks.append(text)
        rec["page_chars"] = per_page
        rec["chars"] = sum(per_page)
        # ⚠ DERIVED, never assumed: a file is text-empty only if EVERY page is.
        rec["text_pages"] = sum(1 for n in per_page if n >= 100)
        if not rec["cached"]:
            txt_path.write_text(PAGE_SEP.join(chunks), encoding="utf-8", errors="replace")
    except Exception as err:
        rec["error"] = f"pdf:{type(err).__name__}"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manuals", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    (args.out / "text").mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in args.manuals.rglob("*.pdf"))
    # `.pd` and extensionless files exist: Windows truncated names at 255 chars.
    files += sorted(p for p in args.manuals.rglob("*.pd"))
    print(f"{len(files)} PDFs under {args.manuals}", flush=True)

    index_path = args.out / "index.json"
    done: dict[str, dict] = {}
    if index_path.exists():
        done = {r["file"]: r for r in json.loads(index_path.read_text(encoding="utf-8"))}
        print(f"  resuming: {len(done)} already indexed", flush=True)

    todo = [str(p) for p in files if p.name not in done]
    print(f"  {len(todo)} to extract", flush=True)

    results = list(done.values())
    with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, rec in enumerate(pool.map(extract_one, ((f, str(args.out)) for f in todo), chunksize=4), 1):
            results.append(rec)
            if i % 50 == 0:
                print(f"   ...{i}/{len(todo)}", flush=True)
                index_path.write_text(json.dumps(results), encoding="utf-8")

    index_path.write_text(json.dumps(results), encoding="utf-8")

    # ⚠ NEVER RENDER A VERDICT ON AN EMPTY SAMPLE — say what was measured first.
    if not results:
        print("MEASURED NOTHING — no verdict.")
        return 1
    failed = [r for r in results if "error" in r]
    empty = [r for r in results if not r.get("error") and r.get("text_pages", 0) == 0]
    partial = [
        r for r in results
        if not r.get("error") and 0 < r.get("text_pages", 0) < r.get("pages", 1)
    ]
    print(f"\nindexed {len(results)} files, {sum(r.get('pages', 0) for r in results)} pages")
    print(f"  failed to open       : {len(failed)}")
    print(f"  NO text layer at all : {len(empty)}   <- render queue (no OCR here)")
    print(f"  partial text layer   : {len(partial)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
